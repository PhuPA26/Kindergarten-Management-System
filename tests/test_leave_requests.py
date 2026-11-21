"""Đơn xin nghỉ: phụ huynh tạo đơn -> giáo viên chủ nhiệm duyệt / từ chối; phụ huynh rút đơn chưa duyệt;
giáo viên ghi đơn giúp khi phụ huynh báo qua điện thoại."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from kindergarten.daily.records import LeaveApplication, LeaveStatus, MessageKind
from kindergarten.exceptions import KindergartenError, PermissionDeniedError, ValidationError


def login(system, username: str, password: str):
    system.auth.logout()
    return system.auth.login(username, password)


@pytest.fixture
def khang(seeded):
    return seeded.children.find_one(full_name="Nguyễn Minh Khang")


@pytest.fixture
def start() -> date:
    """Một ngày thứ Hai đủ xa trong tương lai - không trùng đơn nào của dữ liệu mẫu."""
    day = date.today() + timedelta(days=40)
    return day + timedelta(days=(7 - day.weekday()) % 7)


def parent_leave(system, child, start: date, days: int = 2, reason: str = "Về quê thăm ông bà"):
    login(system, "ph.mai", "phuhuynh123")
    return system.daily.parent_send(child.id, MessageKind.LEAVE, reason, for_date=start,
                                    to_date=start + timedelta(days=days - 1))


def test_parent_creates_leave_and_homeroom_teacher_approves(seeded, khang, start):
    message = parent_leave(seeded, khang, start)
    [app] = [a for a in seeded.daily.leave_applications(khang.id) if a.id == message.id]
    assert app.status is LeaveStatus.PENDING and app.source == LeaveApplication.SOURCE_PARENT
    school_days = sum(seeded.calendar.is_school_day(start + timedelta(days=i)) for i in range(2))
    assert app.can_withdraw and app.school_days == school_days and app.period_text.startswith(start.strftime("%d/%m"))
    assert seeded.attendance.leave_for(khang.id, start) is None   # chưa duyệt thì chưa tính nghỉ có phép

    login(seeded, "gv.nhung", "giaovien123")
    assert message.id in {m.id for m in seeded.daily.pending_leaves()}
    seeded.daily.review_leave(message.id, True, "Cô đã nhận đơn")
    assert seeded.attendance.leave_for(khang.id, start + timedelta(days=1)) is not None
    assert message.id not in {m.id for m in seeded.daily.pending_leaves()}
    with pytest.raises(KindergartenError, match="đã được xử lý"):
        seeded.daily.review_leave(message.id, False, "Đổi ý")

    login(seeded, "ph.mai", "phuhuynh123")
    [app] = [a for a in seeded.daily.leave_applications(khang.id) if a.id == message.id]
    assert app.status is LeaveStatus.APPROVED and app.teacher_note == "Cô đã nhận đơn" and not app.can_withdraw
    with pytest.raises(KindergartenError, match="không rút được"):
        seeded.daily.parent_withdraw_leave(message.id)


def test_teacher_declines_with_reason(seeded, khang, start):
    message = parent_leave(seeded, khang, start)
    login(seeded, "gv.nhung", "giaovien123")
    with pytest.raises(ValidationError, match="lý do"):
        seeded.daily.review_leave(message.id, False, "")
    seeded.daily.review_leave(message.id, False, "Hôm đó lớp kiểm tra sức khỏe, mời phụ huynh cho bé đi học")
    assert seeded.attendance.leave_for(khang.id, start) is None
    login(seeded, "ph.mai", "phuhuynh123")
    [app] = [a for a in seeded.daily.leave_applications(khang.id) if a.id == message.id]
    assert app.status is LeaveStatus.DECLINED and "kiểm tra sức khỏe" in app.teacher_note


def test_parent_withdraws_pending_leave(seeded, khang, start):
    message = parent_leave(seeded, khang, start)
    seeded.daily.parent_withdraw_leave(message.id)
    assert message.id not in {a.id for a in seeded.daily.leave_applications(khang.id)}
    # rút xong thì gửi lại được đơn cùng ngày
    parent_leave(seeded, khang, start, days=1)


def test_overlapping_leave_is_rejected_when_sending(seeded, khang, start):
    parent_leave(seeded, khang, start, days=3)
    with pytest.raises(ValidationError, match="đang chờ cô duyệt"):
        parent_leave(seeded, khang, start + timedelta(days=2))
    login(seeded, "gv.nhung", "giaovien123")
    request = seeded.attendance.record_leave_request(khang.id, start + timedelta(days=7), start + timedelta(days=7),
                                                     "Ốm", "Mẹ Trần Thị Mai (qua điện thoại)")
    with pytest.raises(ValidationError, match=request.id):
        parent_leave(seeded, khang, start + timedelta(days=7))
    with pytest.raises(ValidationError, match="Đến ngày"):
        seeded.daily.parent_send(khang.id, MessageKind.LEAVE, "Ốm", for_date=start + timedelta(days=20),
                                 to_date=start + timedelta(days=19))


def test_leave_recorded_by_teacher_shows_for_parent(seeded, khang, start):
    login(seeded, "gv.nhung", "giaovien123")
    request = seeded.attendance.record_leave_request(khang.id, start, start, "Sốt", "Mẹ Trần Thị Mai (qua điện thoại)")
    assert request.id in {a.id for a in seeded.daily.leave_applications_for_staff()}
    login(seeded, "ph.mai", "phuhuynh123")
    [app] = [a for a in seeded.daily.leave_applications(khang.id) if a.id == request.id]
    assert app.source == LeaveApplication.SOURCE_TEACHER and app.status is LeaveStatus.APPROVED
    assert not app.can_withdraw


def test_cancelled_after_approval_shows_as_cancelled(seeded, khang, start):
    message = parent_leave(seeded, khang, start)
    login(seeded, "gv.nhung", "giaovien123")
    seeded.daily.review_leave(message.id, True)
    seeded.attendance.cancel_leave_request(message.leave_request_id)
    login(seeded, "ph.mai", "phuhuynh123")
    [app] = [a for a in seeded.daily.leave_applications(khang.id) if a.id == message.id]
    assert app.status is LeaveStatus.CANCELLED


def test_leave_scope_and_permissions(seeded, khang, start):
    message = parent_leave(seeded, khang, start)
    other = seeded.children.find_one(full_name="Lê Bảo Ngọc")
    with pytest.raises(PermissionDeniedError):   # phụ huynh chỉ xem đơn của con mình
        seeded.daily.leave_applications(other.id)
    with pytest.raises(PermissionDeniedError):   # phụ huynh không tự duyệt đơn
        seeded.daily.review_leave(message.id, True)
    login(seeded, "gv.tuan", "giaovien123")      # giáo viên bộ môn không duyệt đơn nghỉ
    with pytest.raises(PermissionDeniedError):
        seeded.daily.review_leave(message.id, True)
    login(seeded, "admin", "admin123")           # Ban giám hiệu thấy và duyệt được
    assert message.id in {m.id for m in seeded.daily.pending_leaves()}
