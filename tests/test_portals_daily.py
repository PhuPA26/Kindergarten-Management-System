"""Kiểm thử các yêu cầu mới: 5 phân hệ theo vai trò, tự đăng ký tài khoản, vận hành hằng ngày 6 bước,
trao đổi giáo viên - phụ huynh, danh mục dịch vụ, lịch nghỉ lễ, bỏ phần tiêm chủng."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from kindergarten.auth.user import Permission, Role
from kindergarten.daily.records import MessageKind, MessageStatus
from kindergarten.exceptions import (AuthenticationError, DuplicateIdError, KindergartenError, PermissionDeniedError,
                                     ValidationError)
from kindergarten.reports.reports import EndOfDayReport
from kindergarten.school_calendar import SchoolCalendar
from kindergarten.system import KindergartenSystem
from kindergarten.ui.console.console_io import ConsoleIO
from kindergarten.ui.console.main_menu import MainMenu
from seed_data import DEMO_ACCOUNTS

pytestmark = pytest.mark.skipif(not SchoolCalendar().is_school_day(date.today()),
                                reason="Các bước vận hành chỉ chạy được vào ngày học")


def login(system, username, password):
    system.auth.logout()
    return system.auth.login(username, password)


def mam_son_ca(system):
    return system.classes.find_one(name="Mầm Sơn Ca")


# ----------------------------------------------------------------------------- phân hệ + đăng ký
def test_each_role_opens_its_own_subsystem(seeded):
    for username, password, _ in DEMO_ACCOUNTS:
        user = login(seeded, username, password)
        assert user.role.portal.startswith("Hệ thống ")
    parent = login(seeded, "ph.mai", "phuhuynh123")
    assert parent.permissions == {Permission.PARENT_PORTAL}
    assert [c.full_name for c in seeded.children_for(parent)] == ["Nguyễn Minh Khang"]
    staff = login(seeded, "nv.sau", "nhanvien123")
    assert staff.has_permission(Permission.MANAGE_MENU) and not staff.has_permission(Permission.MANAGE_FINANCE)


def test_parent_self_registration(seeded):
    child = seeded.children.find_one(full_name="Trần Gia Huy")
    father = seeded.parents.parents_of(child.id)[0]
    with pytest.raises(ValidationError):   # sai ngày sinh của con
        seeded.register_parent("ph.thang", "matkhau1", father.phone, child.id, child.dob - timedelta(days=1))
    with pytest.raises(ValidationError):   # SĐT không có trong hồ sơ
        seeded.register_parent("ph.thang", "matkhau1", "0999999999", child.id, child.dob)
    user = seeded.register_parent("ph.thang", "matkhau1", father.phone, child.id, child.dob)
    assert user.role is Role.PARENT and not user.pending
    assert [c.id for c in seeded.children_for(login(seeded, "ph.thang", "matkhau1"))] == [child.id]
    seeded.auth.logout()
    with pytest.raises(DuplicateIdError):
        seeded.register_parent("ph.thang2", "matkhau1", father.phone, child.id, child.dob)


def test_staff_registration_waits_for_approval(seeded):
    from kindergarten.hr.employees import Staff
    staff = seeded.employees.add(Staff("Lý Thị Mến", "1990-03-03", "0983456799", position="Bảo vệ"))
    with pytest.raises(ValidationError):
        seeded.register_staff("nv.men", "matkhau1", staff.id, "0900000000", Role.STAFF)
    user = seeded.register_staff("nv.men", "matkhau1", staff.id, staff.phone, Role.STAFF)
    assert user.pending and user.permissions == frozenset()
    with pytest.raises(AuthenticationError, match="chờ Ban giám hiệu duyệt"):
        seeded.auth.login("nv.men", "matkhau1")
    login(seeded, "gv.nhung", "giaovien123")
    with pytest.raises(PermissionDeniedError):
        seeded.approve_user(user.id)
    login(seeded, "admin", "admin123")
    seeded.approve_user(user.id)
    user = login(seeded, "nv.men", "matkhau1")
    assert user.role is Role.STAFF and user.duty == "bao_ve" and user.has_permission(Permission.CHECK_IN_OUT)


# ----------------------------------------------------------------------------- 6 bước vận hành
def test_daily_operations_end_to_end(seeded):
    today = date.today()
    classroom = mam_son_ca(seeded)
    khang = seeded.children.find_one(full_name="Nguyễn Minh Khang")
    ngoc = seeded.children.find_one(full_name="Lê Bảo Ngọc")

    # ① Nhân viên bảo vệ đón trẻ ở cổng -> tự điểm danh có mặt (dù không có quyền điểm danh)
    login(seeded, "nv.hung", "nhanvien123")
    record = seeded.daily.check_in(khang.id, "Mẹ Trần Thị Mai", "Hơi sổ mũi")
    assert record.is_present and record.checked_in and "sổ mũi" in record.note
    with pytest.raises(KindergartenError):
        seeded.daily.check_in(khang.id, "Mẹ Trần Thị Mai")
    seeded.daily.check_in(ngoc.id, "Bố Lê Quang Minh")
    with pytest.raises(PermissionDeniedError):
        seeded.daily.save_log(khang.id, today, nap="Ngủ ngon")   # nhân viên không ghi nhật ký ăn ngủ

    # ② Giáo viên chốt điểm danh, ③ cập nhật ăn ngủ và gửi phụ huynh
    login(seeded, "gv.nhung", "giaovien123")
    seeded.attendance.take_class_attendance(classroom.id, today)
    log = seeded.daily.save_log(khang.id, today, meals={"Bữa trưa": "Ăn ít"}, nap="Ngủ ít", nap_minutes=45,
                                mood="Mệt / quấy", health_note="Ho nhẹ buổi trưa")
    seeded.daily.fill_class_defaults(classroom.id)
    other = seeded.classes.find_one(name="Lá Vành Khuyên")
    with pytest.raises(PermissionDeniedError):   # giáo viên chỉ làm việc với lớp mình
        seeded.daily.send_logs(other.id)
    assert seeded.daily.send_logs(classroom.id) == len([c for c in classroom.child_ids
                                                         if seeded.attendance.get_record(c, today).is_present])

    # Phụ huynh xem nhật ký của con, phản hồi; không xem được con người khác
    login(seeded, "ph.mai", "phuhuynh123")
    logs = seeded.daily.logs_for_parent(khang.id)
    assert logs[0].id == log.id and logs[0].nap == "Ngủ ít"
    seeded.daily.parent_reply_log(log.id, "Tối qua bé ho, nhờ cô để ý giúp ạ")
    assert log.parent_seen_at and log.parent_reply
    with pytest.raises(PermissionDeniedError):
        seeded.daily.logs_for_parent(ngoc.id)

    # ④ Phụ huynh dặn thuốc + xin nghỉ ngày mai; giáo viên xử lý
    medicine = seeded.daily.parent_send(khang.id, MessageKind.MEDICINE, medicine="Siro ho", dosage="5 ml",
                                        time_text="Sau ăn trưa")
    tomorrow = today + timedelta(days=1)
    leave = seeded.daily.parent_send(khang.id, "Xin nghỉ", "Bé đi khám", for_date=tomorrow, to_date=tomorrow)
    with pytest.raises(ValidationError):
        seeded.daily.parent_send(khang.id, MessageKind.MEDICINE)   # thiếu tên thuốc
    login(seeded, "gv.nhung", "giaovien123")
    assert {medicine.id, leave.id} <= {m.id for m in seeded.daily.inbox(seeded.class_ids_for(seeded.auth.current_user),
                                                                      only_open=True)}
    seeded.daily.complete(medicine.id, "Cô đã cho bé uống lúc 11:40")
    seeded.daily.complete(leave.id)
    assert medicine.status is MessageStatus.DONE and leave.leave_request_id
    assert seeded.attendance.leave_for(khang.id, tomorrow) is not None
    seeded.daily.teacher_send(None, "Mai lớp đi dã ngoại", classroom.id, announcement=True)

    # ⑤ Trả trẻ
    seeded.verify_pickup(khang.id, "Nguyễn Văn Bảy")   # ông nội trong danh sách đón hộ
    assert seeded.attendance.get_record(khang.id, today).picked_up

    # ⑥ Báo cáo cuối ngày cho BGH
    login(seeded, "admin", "admin123")
    summary = seeded.daily.class_summary(classroom.id)
    assert summary["checked_in"] == 2 and summary["medicine_done"] >= 1 and summary["picked_up"] == 1
    assert summary["parent_replies"] == 1 and ("Nguyễn Minh Khang", "Ho nhẹ buổi trưa") in summary["health_notes"]
    text = EndOfDayReport(seeded).to_text()
    assert "BÁO CÁO CUỐI NGÀY" in text and "Lê Bảo Ngọc (Mầm Sơn Ca)" in text   # Ngọc chưa được đón về
    steps = seeded.daily.step_progress()
    assert [s["step"].number for s in steps] == [1, 2, 3, 4, 5, 6]

    # Phụ huynh thấy kết quả xử lý + thông báo lớp
    login(seeded, "ph.mai", "phuhuynh123")
    kinds = {(m.kind, m.status) for m in seeded.daily.messages_for_parent(khang.id)}
    assert (MessageKind.MEDICINE, MessageStatus.DONE) in kinds and (MessageKind.ANNOUNCEMENT, MessageStatus.NEW) in kinds


def test_daily_data_persists(seeded):
    khang = seeded.children.find_one(full_name="Nguyễn Minh Khang")
    seeded.daily.check_in(khang.id, "Mẹ")
    seeded.daily.save_log(khang.id, date.today(), nap="Ngủ ngon")
    seeded.save()
    again = KindergartenSystem(seeded.store.data_dir)
    again.load()
    assert again.attendance.get_record(khang.id, date.today()).checked_in
    assert again.daily.log_of(khang.id, date.today()).nap == "Ngủ ngon"
    assert len(again.daily.messages) == len(seeded.daily.messages)


# ----------------------------------------------------------------------------- dịch vụ, lịch nghỉ
def test_service_catalog_and_parent_registration(seeded):
    login(seeded, "ketoan", "ketoan123")
    seeded.save_service("Bơi lội", "400.000")
    with pytest.raises(DuplicateIdError):
        seeded.save_service("bơi  LỘI", 1)
    assert ("Bơi lội", 400_000, 0) in seeded.service_catalog()
    login(seeded, "ph.mai", "phuhuynh123")
    khang = seeded.children_for(seeded.auth.current_user)[0]
    seeded.set_child_service(khang.id, "Bơi lội", True)
    other = seeded.children.find_one(full_name="Lê Bảo Ngọc")
    with pytest.raises(PermissionDeniedError):
        seeded.set_child_service(other.id, "Bơi lội", True)
    with pytest.raises(PermissionDeniedError):
        seeded.save_service("Võ thuật", 300_000)
    login(seeded, "ketoan", "ketoan123")
    seeded.save_service("Bơi lội nâng cao", 450_000, old_name="Bơi lội")
    assert "Bơi lội nâng cao" in khang.extra_services
    fees = seeded.invoices.build_fees(khang, date.today().month, date.today().year)
    assert any(f.calculate() == 450_000 for f in fees)
    users = seeded.remove_service("Bơi lội nâng cao")
    assert khang in users and "Bơi lội nâng cao" not in khang.extra_services


def test_holiday_management(seeded):
    login(seeded, "gv.nhung", "giaovien123")
    with pytest.raises(PermissionDeniedError):
        seeded.add_holidays(date.today(), None, "Nghỉ đột xuất")
    login(seeded, "admin", "admin123")
    start = date.today() + timedelta(days=30)
    days = seeded.add_holidays(start, start + timedelta(days=4), "Tết Nguyên đán")
    assert len(days) == 5 and all(not seeded.calendar.is_school_day(d) for d in days)
    with pytest.raises(ValidationError):
        seeded.add_holidays(start, start - timedelta(days=1), "Sai")
    seeded.remove_holidays(days[:2])
    assert seeded.calendar.holiday_name(days[0]) is None and seeded.calendar.holiday_name(days[2]) == "Tết Nguyên đán"


def test_vaccination_removed(seeded):
    assert not hasattr(seeded.health, "vaccinations") and not hasattr(seeded.health, "add_vaccination")
    seeded.save()
    assert not (seeded.store.data_dir / "vaccinations.json").exists()


# ----------------------------------------------------------------------------- console
def run_console(system, inputs):
    output: list[str] = []
    answers = iter(inputs)
    io = ConsoleIO(input_func=lambda prompt: next(answers), output_func=output.append, use_color=False)
    MainMenu(system, io, demo_accounts=DEMO_ACCOUNTS).run()
    return "\n".join(output)


def test_console_parent_portal_and_registration(seeded):
    child = seeded.children.find_one(full_name="Trần Gia Huy")
    father = seeded.parents.parents_of(child.id)[0]
    out = run_console(seeded, ["dk", "1", "ph.thang", "matkhau1", "matkhau1", father.phone, child.id,
                               child.dob.strftime("%d/%m/%Y"),
                               "ph.thang", "matkhau1", "1", "", "3", "Chiều nay bà ngoại đón bé ạ", "", "0", "k"])
    assert "Đăng ký thành công" in out and "HỆ THỐNG PHỤ HUYNH" in out and "TRẦN GIA HUY" in out
    assert "Đã gửi lời nhắn" in out
    assert any(m.content == "Chiều nay bà ngoại đón bé ạ" for m in seeded.daily.messages)
