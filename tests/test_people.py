"""Kiểm thử Parent (T09), Child (T10), ChildManager/ParentManager (T11)."""
from datetime import date

import pytest

from kindergarten.exceptions import (DuplicateIdError, InvalidAgeError, KindergartenError, NotFoundError,
                                     PermissionDeniedError, ValidationError)
from kindergarten.people.child import Child, PickupPerson


def test_child_age_is_calculated_and_range_enforced(dob_for):
    child = Child("Lê Minh Châu", dob_for(4, 5), "Nữ")
    assert child.age == 4 and child.age_months == 53 and child.age_text == "4 tuổi 5 tháng"
    for years in (0, 7):
        with pytest.raises(InvalidAgeError):
            Child("Bé Ngoài Độ Tuổi", dob_for(years, 6), "Nam")


def test_search_children(system, make_child):
    an = make_child("Nguyễn Văn An", 4)
    binh = make_child("Trần Thị Bình", 3, gender="Nữ")
    classroom = system.classes.create_class("Mầm 1", "Mầm", 10)
    system.classes.enroll(binh.id, classroom.id)
    assert system.children.search_by_name("nguyen") == [an]
    assert system.children.search_by_name("BÌNH") == [binh]
    assert system.children.find_by_class(classroom.id) == [binh]
    assert system.children.find_by_age(4) == [an]
    assert system.children.find_by_age_range(3, 4) == [an, binh]  # sắp theo tên: An, Bình
    assert system.children.find_unassigned() == [an]


def test_parent_links_and_children_of(system, make_child, make_parent):
    an, binh = make_child("Vũ Gia An", 5), make_child("Vũ Ngọc Bình", 3, gender="Nữ")
    father = make_parent("Vũ Văn Cường", "0905111222", "Bố")
    system.parents.link(father.id, an.id)
    system.parents.link(father.id, binh.id)
    assert {c.id for c in system.parents.children_of(father.id)} == {an.id, binh.id}
    assert system.parents.parents_of(an.id) == [father]
    assert father.gender == "Nam"  # tự suy ra từ quan hệ "Bố"
    assert system.children.siblings_of(an.id) == [binh]
    with pytest.raises(KindergartenError):   # L27: trẻ đang học không được mất phụ huynh cuối cùng
        system.parents.unlink(father.id, binh.id)
    system.parents.unlink(father.id, binh.id, force=True)
    assert father.child_ids == [an.id] and binh.parent_ids == []


def test_remove_child_cleans_related_data(system, make_child, make_parent):
    child = make_child("Lê Bảo Ngọc", 4, gender="Nữ")
    parent = make_parent("Lê Văn Minh", "0905333444", "Bố")
    system.parents.link(parent.id, child.id)
    classroom = system.classes.create_class("Chồi 1", "Chồi", 10)
    system.classes.enroll(child.id, classroom.id)
    system.health.add_allergy(child.id, "tôm", "Nặng")
    system.children.remove(child.id)
    assert parent.child_ids == [] and classroom.size == 0 and len(system.health.allergies) == 0


def test_unique_parent_phone(make_parent, make_child):
    """L27: hai hộ khác nhau không dùng chung SĐT; vợ chồng (cùng con / chưa liên kết con) thì được."""
    an, binh = make_child("Trần Gia An", 4), make_child("Lê Thu Bình", 4, gender="Nữ")
    make_parent("Trần Văn A", "0905000001", "Bố", child_ids=[an.id])
    with pytest.raises(DuplicateIdError):
        make_parent("Lê Văn B", "0905 000 001", "Bố", child_ids=[binh.id])
    wife = make_parent("Phạm Thị C", "0905.000.001", "Mẹ", child_ids=[an.id])
    assert wife.phone == "0905000001"


def test_replace_pickup_person_keeps_position_and_rejects_duplicates(make_child):
    child = make_child("Hồ Thiên Phúc", 5)
    child.add_pickup_person(PickupPerson("Hồ Văn Lộc", "Ông nội", "0977000444"))
    child.add_pickup_person(PickupPerson("Lê Thị Hoa", "Bà ngoại", "0977000555"))
    child.replace_pickup_person("hồ văn lộc", PickupPerson("Hồ Văn Lộc", "Ông nội", "0977000999", "012345678901"))
    assert [p.phone for p in child.pickup_persons] == ["0977000999", "0977000555"]
    with pytest.raises(ValidationError):   # đổi tên trùng người đã có
        child.replace_pickup_person("Hồ Văn Lộc", PickupPerson("Lê Thị Hoa", "Cô", "0977000111"))
    with pytest.raises(NotFoundError):
        child.replace_pickup_person("Không Có Ai", PickupPerson("Ai Đó", "Cô", "0977000111"))
    assert [p.full_name for p in child.pickup_persons] == ["Hồ Văn Lộc", "Lê Thị Hoa"]


def test_pickup_verification(system, make_child, make_parent):
    child = make_child("Hồ Thiên Phúc", 5)
    mother = make_parent("Quách Thị Yến", "0906000001", "Mẹ")
    system.parents.link(mother.id, child.id)
    child.add_pickup_person(PickupPerson("Hồ Văn Lộc", "Ông nội", "0977000444"))
    classroom = system.classes.create_class("Lá 1", "Lá", 10)
    system.classes.enroll(child.id, classroom.id)
    day = system.calendar.school_days(date.today().month, date.today().year, until=date.today())
    day = day[-1] if day else None
    if day is None:
        pytest.skip("Đầu tháng chưa có ngày học nào")
    # L06: trẻ chưa điểm danh có mặt -> không giao
    with pytest.raises(KindergartenError):
        system.verify_pickup(child.id, "Hồ Văn Lộc", day)
    system.attendance.mark(child.id, day, "Có mặt")
    assert "Ông nội" in system.verify_pickup(child.id, "hồ văn  lộc", day)   # không phân biệt hoa thường/khoảng trắng
    with pytest.raises(PermissionDeniedError):   # L06: phải đúng họ tên CÓ DẤU (Hồ Văn Lộc != Hồ Văn Lốc)
        system.verify_pickup(child.id, "ho van loc", day)
    with pytest.raises(KindergartenError, match="đã được giao"):
        system.verify_pickup(child.id, "Quách Thị Yến", day)
    record = system.attendance.get_record(child.id, day)
    assert record.picked_up_by.startswith("Hồ Văn Lộc") and record.picked_up_at
    with pytest.raises(PermissionDeniedError):
        system.verify_pickup(child.id, "Người Lạ Mặt", day)
    actions = [e["action"] for e in system.audit_log.read(20)]
    assert "Từ chối giao trẻ" in actions and "Giao trẻ" in actions
