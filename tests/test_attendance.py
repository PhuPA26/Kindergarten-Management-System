"""Kiểm thử AttendanceStatus/AttendanceRecord (T19) và AttendanceManager (T20)."""
from datetime import date, timedelta

import pytest

from kindergarten.attendance.records import AttendanceStatus
from kindergarten.exceptions import KindergartenError, ValidationError
from kindergarten.utils import previous_month, school_days


def last_school_day() -> date:
    day = date.today() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


@pytest.fixture
def klass(system, make_child):
    classroom = system.classes.create_class("Chồi 1", "Chồi", 10)
    kids = [make_child(name, 4) for name in ("Bé An", "Bé Bình", "Bé Chi")]
    for kid in kids:
        system.classes.enroll(kid.id, classroom.id)
    return classroom, kids


def test_status_enum():
    assert [s.value for s in AttendanceStatus] == ["Có mặt", "Nghỉ có phép", "Nghỉ không phép"]
    assert AttendanceStatus.parse("k") is AttendanceStatus.UNEXCUSED
    assert AttendanceStatus.parse("Nghỉ có phép") is AttendanceStatus.EXCUSED


def test_take_class_attendance(system, klass):
    classroom, (an, binh, _chi) = klass
    day = last_school_day()
    records = system.attendance.take_class_attendance(
        classroom.id, day, {an.id: "C", binh.id: (AttendanceStatus.UNEXCUSED, "Không báo")})
    assert len(records) == 3
    assert system.attendance.get_record(an.id, day).status is AttendanceStatus.PRESENT
    assert system.attendance.get_record(binh.id, day).status is AttendanceStatus.UNEXCUSED
    # chưa đón = vắng: trẻ không được đánh dấu có mặt thì chốt là vắng "chưa đến trường"
    chi_record = system.attendance.get_record(_chi.id, day)
    assert chi_record.status is AttendanceStatus.UNEXCUSED and chi_record.note == "Chưa đến trường"
    assert system.attendance.is_taken(classroom.id, day)
    system.attendance.take_class_attendance(classroom.id, day)  # điểm danh lại -> cập nhật, không nhân bản
    assert len(system.attendance) == 3
    with pytest.raises(ValidationError):
        system.attendance.take_class_attendance(classroom.id, date.today() + timedelta(days=1))


def test_leave_request(system, klass):
    _classroom, (an, binh, _chi) = klass
    day = last_school_day()
    system.attendance.mark(an.id, day, "K")
    system.attendance.record_leave_request(an.id, day, day + timedelta(days=2), "Bé bị sốt")
    assert system.attendance.get_record(an.id, day).status is AttendanceStatus.EXCUSED  # tự chuyển sang có phép
    assert system.attendance.default_status(an.id, day + timedelta(days=1))[0] is AttendanceStatus.EXCUSED
    with pytest.raises(ValidationError):
        system.attendance.record_leave_request(an.id, day + timedelta(days=1), day + timedelta(days=1), "Trùng đơn")
    with pytest.raises(ValidationError):
        system.attendance.record_leave_request(binh.id, day, day - timedelta(days=1), "Sai ngày")


def test_monthly_stats_and_present_days(system, klass):
    classroom, (an, binh, chi) = klass
    month, year = previous_month(date.today().month, date.today().year)
    days = school_days(month, year)[:4]
    for day in days:
        system.attendance.take_class_attendance(classroom.id, day, {k.id: "C" for k in (an, binh, chi)})
    system.attendance.mark(binh.id, days[0], AttendanceStatus.EXCUSED)
    system.attendance.mark(chi.id, days[1], AttendanceStatus.UNEXCUSED)
    stats = {s["child_id"]: s for s in system.attendance.monthly_stats(month, year, classroom.id)}
    assert stats[an.id]["present"] == 4 and stats[an.id]["rate"] == 100
    assert stats[binh.id]["excused"] == 1 and stats[chi.id]["unexcused"] == 1
    assert system.attendance.present_days(binh.id, month, year) == 3
    assert system.attendance.attendance_rate(month, year) == pytest.approx(10 / 12 * 100)
    headers, rows = system.attendance.monthly_grid(classroom.id, month, year)
    assert headers[:2] == ["Mã", "Họ tên"] and any("P" in row for row in rows)


def test_unassigned_child_cannot_be_marked(system, make_child):
    child = make_child("Bé Chờ Lớp", 2)
    with pytest.raises(KindergartenError):
        system.attendance.mark(child.id, date.today(), "C")
