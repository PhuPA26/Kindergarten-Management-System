"""Kiểm thử nền tảng: exceptions (T01), BaseModel (T02), BaseManager (T03), Person/Employee (T04), utils (T05)."""
from datetime import date, timedelta

import pytest

from kindergarten.core.base_manager import BaseManager
from kindergarten.core.person import Employee
from kindergarten.exceptions import (ClassFullError, DuplicateIdError, InvalidAgeError, KindergartenError,
                                     NotFoundError, PermissionDeniedError, ValidationError)
from kindergarten.hr.employees import Staff, Teacher
from kindergarten.people.child import Child
from kindergarten.utils import (format_table, format_vnd, normalize_text, parse_date, parse_money, parse_month,
                                parse_time, validate_phone)


def test_exception_hierarchy():
    for exc in (DuplicateIdError, NotFoundError, ClassFullError, InvalidAgeError, PermissionDeniedError,
                ValidationError):
        assert issubclass(exc, KindergartenError)
    assert issubclass(InvalidAgeError, ValidationError)
    assert NotFoundError().message == NotFoundError.default_message


def test_auto_generated_ids_have_prefix(dob_for):
    first = Child("Nguyễn An", dob_for(4), "Nam")
    second = Child("Trần Bình", dob_for(3), "Nữ")
    teacher = Teacher("Lê Thị Hoa", "1990-05-01", "0912000111")
    assert (first.id, second.id, teacher.id) == ("C001", "C002", "T001")


def test_rejected_object_does_not_consume_id(dob_for):
    with pytest.raises(InvalidAgeError):
        Child("Bé Quá Tuổi", dob_for(8), "Nam")
    assert Child("Bé Hợp Lệ", dob_for(4), "Nữ").id == "C001"


def test_loaded_ids_are_registered(dob_for):
    Child("Bé Cũ", dob_for(4), "Nam", id="C010")
    assert Child("Bé Mới", dob_for(4), "Nam").id == "C011"


def test_to_dict_from_dict_roundtrip(dob_for):
    child = Child("phạm  minh khôi", dob_for(5, 3), "nam", nickname="Bin", extra_services=["Tiếng Anh"])
    data = child.to_dict()
    clone = Child.from_dict(data)
    assert clone.to_dict() == data
    assert clone.full_name == "Phạm Minh Khôi" and clone.gender == "Nam"
    teacher = Teacher("Lê Thị Hoa", "1990-05-01", "0912000111", salary_coefficient=2.5)
    restored = Employee.from_dict(teacher.to_dict())  # đa hình: tự tạo đúng lớp Teacher
    assert isinstance(restored, Teacher) and restored.salary_coefficient == 2.5


def test_base_manager_crud(dob_for):
    manager: BaseManager[Child] = BaseManager("trẻ")
    an = manager.add(Child("Nguyễn Văn An", dob_for(4), "Nam"))
    binh = manager.add(Child("Trần Thị Bình", dob_for(3), "Nữ"))
    assert manager.get("c001") is an
    with pytest.raises(DuplicateIdError):
        manager.add(Child("Bé Trùng Mã", dob_for(4), "Nam", id="C001"))
    with pytest.raises(NotFoundError):
        manager.get("C999")
    manager.update(an.id, nickname="Bin", notes="Thích vẽ")
    assert an.nickname == "Bin"
    with pytest.raises(ValidationError):  # một trường sai -> hoàn tác toàn bộ
        manager.update(an.id, nickname="Bon", phone="123")
    assert an.nickname == "Bin"
    with pytest.raises(ValidationError):
        manager.update(an.id, id="X01")
    assert manager.find(gender="Nữ") == [binh]
    assert manager.find(lambda c: c.age >= 4) == [an]
    assert manager.search("nguyen van", "full_name") == [an]
    assert [c.id for c in manager.sort("full_name", reverse=True)] == ["C002", "C001"]
    manager.remove(an.id)
    assert len(manager) == 1 and an.id not in manager


def test_person_property_validation(dob_for):
    with pytest.raises(ValidationError):
        Teacher("Lê Thị Hoa", "1990-05-01", "12345")
    with pytest.raises(ValidationError):
        Child("Bé Tương Lai", date.today() + timedelta(days=1), "Nam")
    with pytest.raises(InvalidAgeError):
        Staff("Bảo Vệ Nhỏ Tuổi", dob_for(16), "0912000222")
    with pytest.raises(ValidationError):
        Child("Tên 123", dob_for(4), "Nam")
    teacher = Teacher("Lê Thị Hoa", "01/05/1990", "+84 912-000-111")
    assert teacher.phone == "0912000111"


def test_utils_validation_and_format():
    assert validate_phone("0912 345 678") == "0912345678"
    assert validate_phone("+84912345678") == "0912345678"
    assert validate_phone("", required=False) == ""
    for bad in ("0123", "1912345678", "09123456789"):
        with pytest.raises(ValidationError):
            validate_phone(bad)
    assert parse_date("05/09/2024") == parse_date("2024-09-05") == date(2024, 9, 5)
    with pytest.raises(ValidationError):
        parse_date("31/02/2024")
    assert parse_money("2.500.000 đ") == 2_500_000
    assert parse_money("300k") == 300_000
    assert parse_money("1,5tr") == 1_500_000
    with pytest.raises(ValidationError):
        parse_money("-5000")
    assert format_vnd(2500000) == "2.500.000 đ"
    assert normalize_text("  Nguyễn   ĐỨC  ") == "nguyen duc"
    assert parse_month("11/2026") == (11, 2026) and parse_month("2026-01") == (1, 2026)
    assert parse_time("7h30").strftime("%H:%M") == "07:30"
    table = format_table(["Mã", "Số tiền"], [["C001", format_vnd(1000)]])
    assert "C001" in table and "1.000 đ" in table
