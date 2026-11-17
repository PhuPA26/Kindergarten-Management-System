"""Kiểm thử Classroom (T16), ClassManager (T17), TimeSlot/Timetable (T18)."""
import pytest

from kindergarten.exceptions import (ClassFullError, InvalidAgeError, KindergartenError, ScheduleConflictError,
                                     ValidationError)


def test_class_capacity_and_age(system, make_child):
    classroom = system.classes.create_class("Lá 1", "Lá", capacity=2)
    a, b, c = make_child("Bé An", 5), make_child("Bé Bình", 5), make_child("Bé Chi", 5)
    system.classes.enroll(a.id, classroom.id)
    system.classes.enroll(b.id, classroom.id)
    assert classroom.is_full and a.class_id == classroom.id
    with pytest.raises(ClassFullError):
        system.classes.enroll(c.id, classroom.id)
    young = make_child("Bé Nhỏ", 3)
    other = system.classes.create_class("Lá 2", "Lá", capacity=5)
    with pytest.raises(InvalidAgeError):
        system.classes.enroll(young.id, other.id)
    with pytest.raises(ValidationError):
        system.classes.update(classroom.id, capacity=1)  # nhỏ hơn sĩ số hiện tại
    with pytest.raises(KindergartenError):
        system.classes.remove(classroom.id)  # lớp còn trẻ


def test_transfer_is_safe(system, make_child):
    full = system.classes.create_class("Chồi 1", "Chồi", 1)
    source = system.classes.create_class("Chồi 2", "Chồi", 5)
    a, b = make_child("Bé An", 4), make_child("Bé Bình", 4)
    system.classes.enroll(a.id, full.id)
    system.classes.enroll(b.id, source.id)
    with pytest.raises(ClassFullError):
        system.classes.transfer(b.id, full.id)
    assert b.class_id == source.id and source.has_child(b.id)  # lớp mới đầy -> trẻ vẫn ở lớp cũ
    target = system.classes.create_class("Chồi 3", "Chồi", 5)
    system.classes.transfer(b.id, target.id)
    assert b.class_id == target.id and not source.has_child(b.id) and target.has_child(b.id)
    with pytest.raises(KindergartenError):
        system.classes.enroll(b.id, source.id)  # đã có lớp -> phải dùng chuyển lớp


def test_change_homeroom_teacher(system, make_teacher, make_child):
    t1, t2 = make_teacher("Giáo Viên Một", "0912000011"), make_teacher("Giáo Viên Hai", "0912000012")
    c1 = system.classes.create_class("Mầm 1", "Mầm", 10, teacher_id=t1.id)
    c2 = system.classes.create_class("Mầm 2", "Mầm", 10)
    with pytest.raises(KindergartenError):
        system.classes.change_homeroom_teacher(c2.id, t1.id)  # t1 đang chủ nhiệm lớp khác
    system.classes.change_homeroom_teacher(c1.id, t2.id)
    assert c1.teacher_id == t2.id and t2.homeroom_class_id == c1.id and t1.homeroom_class_id is None
    system.classes.change_homeroom_teacher(c2.id, t1.id)
    assert system.classes.homeroom_teacher(c2.id) is t1
    system.classes.enroll(make_child("Bé Ba", 3).id, c1.id)
    text = system.classes.class_list_text(c1.id)
    assert "DANH SÁCH LỚP MẦM 1" in text and "Giáo Viên Hai" in text and "Bé Ba" in text


def test_timetable_conflicts(system, make_teacher):
    music = make_teacher("Phạm Minh Tuấn", "0912000013", specialty="Âm nhạc")
    c1 = system.classes.create_class("Mầm 1", "Mầm", 10)
    c2 = system.classes.create_class("Chồi 1", "Chồi", 10)
    tt = system.timetable
    tt.add_slot(c1.id, "2", "08:00", "08:30", "Âm nhạc", music.id)
    with pytest.raises(ScheduleConflictError, match="Lớp Mầm 1"):
        tt.add_slot(c1.id, 0, "08:15", "08:45", "Tạo hình")  # trùng tiết của lớp
    with pytest.raises(ScheduleConflictError, match="Phạm Minh Tuấn"):
        tt.add_slot(c2.id, "Thứ 2", "08:00", "08:30", "Âm nhạc", music.id)  # giáo viên dạy 2 lớp cùng lúc
    ok = tt.add_slot(c2.id, 0, "08:30", "09:00", "Âm nhạc", music.id)  # nối tiếp -> hợp lệ
    with pytest.raises(ScheduleConflictError):
        tt.update(ok.id, start="08:10")  # sửa thành trùng -> bị từ chối và hoàn tác
    assert ok.start.strftime("%H:%M") == "08:30"
    with pytest.raises(ValidationError):
        tt.add_slot(c2.id, 1, "10:00", "09:00", "Sai giờ")
    headers, rows = tt.weekly_grid(class_id=c1.id)
    assert headers[1] == "Thứ 2" and rows[0][1].startswith("Âm nhạc")
    system.classes.remove(c1.id)  # xóa lớp -> tiết của lớp bị xóa theo
    assert len(tt) == 1
