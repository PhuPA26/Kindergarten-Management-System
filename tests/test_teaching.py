"""GV chủ nhiệm và GV bộ môn có công việc khác nhau; sổ tiết dạy bộ môn (nghiệp vụ riêng của GV bộ môn)."""
from datetime import date, timedelta

import pytest

from kindergarten.auth.user import Permission as P
from kindergarten.exceptions import PermissionDeniedError, ValidationError


def login(system, username):
    user = system.auth.login(username, "giaovien123")
    user.must_change_password = False
    return user


def last_school_day_of(system, teacher_id):
    """Ngày gần nhất (trước hôm nay) giáo viên có tiết dạy."""
    weekdays = {s.weekday for s in system.timetable.find(teacher_id=teacher_id)}
    day = date.today() - timedelta(days=1)
    while day.weekday() not in weekdays or not system.calendar.is_school_day(day):
        day -= timedelta(days=1)
    return day


def test_homeroom_and_subject_teachers_have_different_duties(seeded):
    homeroom = login(seeded, "gv.nhung")
    assert seeded.auth.role_label(homeroom) == "Giáo viên chủ nhiệm"
    for permission in (P.CHECK_IN_OUT, P.TAKE_ATTENDANCE, P.DAILY_LOG, P.PARENT_CONTACT, P.MANAGE_HEALTH):
        assert seeded.auth.has_permission(permission)
    assert not seeded.auth.has_permission(P.TEACH_SUBJECT)
    assert "subject" not in {t["key"] for t in seeded.reports.available_types()}

    subject = login(seeded, "gv.tuan")
    assert seeded.auth.role_label(subject) == "Giáo viên bộ môn"
    assert "Bộ môn" in seeded.auth.portal_of(subject)
    for permission in (P.CHECK_IN_OUT, P.TAKE_ATTENDANCE, P.DAILY_LOG, P.PARENT_CONTACT, P.MANAGE_HEALTH):
        assert not seeded.auth.has_permission(permission)
    assert seeded.auth.has_permission(P.TEACH_SUBJECT) and seeded.auth.has_permission(P.VIEW_CLASSES)
    assert {t["key"] for t in seeded.reports.available_types()} == {"subject"}
    # GV bộ môn dạy cả 3 lớp theo thời khóa biểu nhưng không đón trẻ / điểm danh được
    assert len(seeded.classes_for(subject)) == 3
    child = seeded.children_for(subject)[0]
    with pytest.raises(PermissionDeniedError):
        seeded.daily.check_in(child.id)


def test_becoming_homeroom_changes_duties(seeded):
    tuan = seeded.teacher_of(seeded.auth.find_by_username("gv.tuan"))
    assert seeded.teacher_duty_for_employee(tuan.id) == "bo_mon"
    classroom = seeded.classes.find_one(name="Mầm Sơn Ca")
    seeded.classes.change_homeroom_teacher(classroom.id, tuan.id)   # được phân công chủ nhiệm
    assert seeded.teacher_duty_for_employee(tuan.id) == "chu_nhiem"
    login(seeded, "gv.tuan")
    assert seeded.auth.has_permission(P.TAKE_ATTENDANCE) and not seeded.auth.has_permission(P.TEACH_SUBJECT)


def test_subject_teacher_logs_lessons_and_comments_children(seeded):
    user = login(seeded, "gv.lan")
    teacher = seeded.teacher_of(user)
    day = last_school_day_of(seeded, teacher.id)
    lessons = seeded.lessons
    row = next(r for r in lessons.schedule(day) if r["log"] is None) if any(
        r["log"] is None for r in lessons.schedule(day)) else None
    if row is None:   # dữ liệu mẫu đã ghi hết tiết hôm đó -> xóa để ghi lại
        row = lessons.schedule(day)[0]
        lessons.delete_lesson(row["log"].id)
    slot = row["slot"]
    log = lessons.save_lesson(slot.class_id, day, slot.activity, "Colors: red, blue", "Tốt", slot=slot)
    assert log.teacher_id == teacher.id and log.time_text == slot.time_range
    assert lessons.schedule(day)[[r["slot"].id for r in lessons.schedule(day)].index(slot.id)]["log"] is log
    with pytest.raises(ValidationError):   # mỗi tiết chỉ ghi một lần
        lessons.save_lesson(slot.class_id, day, slot.activity, "Lần 2")
    with pytest.raises(ValidationError):   # không ghi sổ trước
        lessons.save_lesson(slot.class_id, date.today() + timedelta(days=1), slot.activity, "Chưa dạy")

    kid = seeded.classes.class_list(slot.class_id)[0]
    lessons.set_child_note(log.id, kid.id, "Nổi bật", "Phát âm chuẩn")
    assert log.child_note_text(kid.id) == "Nổi bật - Phát âm chuẩn"
    lessons.set_child_note(log.id, kid.id)   # để trống = xóa nhận xét
    assert kid.id not in log.child_notes
    other = next(c for c in seeded.children.active() if c.class_id and c.class_id != slot.class_id)
    with pytest.raises(ValidationError):
        lessons.set_child_note(log.id, other.id, "Đạt")

    # GV bộ môn khác không sửa được sổ của người khác
    login(seeded, "gv.tuan")
    with pytest.raises(PermissionDeniedError):
        lessons.set_child_note(log.id, kid.id, "Đạt")
    assert all(x.teacher_id != teacher.id for x in lessons.logs())   # chỉ thấy sổ của mình
    # GV chủ nhiệm không có sổ tiết dạy
    login(seeded, "gv.nhung")
    with pytest.raises(PermissionDeniedError):
        lessons.save_lesson(slot.class_id, day, "Âm nhạc", "Không được")


def test_subject_report_counts_planned_and_logged_lessons(seeded):
    login(seeded, "gv.tuan")
    today = date.today()
    report = seeded.reports.create("subject", month=today.month, year=today.year, note="Tháng này ổn")
    summary = dict(report.data["summary"])
    planned = int(summary["Số tiết theo thời khóa biểu (đến hôm nay)"])
    logged = int(summary["Số tiết đã ghi sổ"])
    assert logged <= planned
    assert report.author_role == "Giáo viên - Bộ môn"
    assert all(row[0] == "Phạm Minh Tuấn" for row in report.data["rows"])   # chỉ tiết của mình


def test_removing_child_or_teacher_cleans_lesson_logs(seeded, make_child):
    """Như ON DELETE CASCADE trong CSDL: xóa trẻ -> bỏ nhận xét; xóa GV bộ môn -> bỏ sổ tiết dạy."""
    # Hồ sơ nhập nhầm chưa phát sinh hóa đơn vẫn có thể được xóa.
    log = next(iter(seeded.lessons))
    child_id = make_child("Nguyễn Mai Linh").id
    log.child_notes = {**log.child_notes, child_id: {"level": "", "comment": "Nhận xét thử"}}
    seeded.children.remove(child_id)
    assert child_id not in log.child_notes
    teacher_id = log.teacher_id
    seeded.employees.remove(teacher_id)
    assert not seeded.lessons.find(teacher_id=teacher_id)
    seeded.save()   # ghi CSDL không vi phạm khóa ngoại
