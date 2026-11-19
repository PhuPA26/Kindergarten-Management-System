"""T10 - Child kế thừa Person: tuổi tự tính, danh sách phụ huynh, người đón hộ.

Trẻ ngoài độ tuổi 1–6 bị từ chối khi tiếp nhận (InvalidAgeError).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from ..core.person import Person
from ..exceptions import NotFoundError, ValidationError
from ..utils import (age_in_months, format_age, format_date, normalize_spaces, normalize_text,
                     parse_date, require_text, validate_name, validate_phone)


@dataclass
class PickupPerson:
    """Người được phụ huynh ủy quyền đón trẻ hộ (ông bà, cô chú...)."""

    full_name: str
    relationship: str
    phone: str
    id_card: str = ""  # số CMND/CCCD (tùy chọn)

    def __post_init__(self) -> None:
        self.full_name = validate_name(self.full_name, "Họ tên người đón")
        self.relationship = require_text(self.relationship, "Quan hệ với trẻ", 40)
        self.phone = validate_phone(self.phone, field="SĐT người đón")
        self.id_card = normalize_spaces(self.id_card)
        if self.id_card and not re.fullmatch(r"\d{9}|\d{12}", self.id_card):
            raise ValidationError("Số CMND/CCCD phải gồm 9 hoặc 12 chữ số.")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PickupPerson":
        return cls(data["full_name"], data.get("relationship", ""), data.get("phone", ""),
                   data.get("id_card", ""))

    def __str__(self) -> str:
        return f"{self.full_name} ({self.relationship}) - {self.phone}"


class Child(Person):
    PREFIX = "C"
    MIN_AGE = 1
    MAX_AGE = 6
    PHONE_REQUIRED = False
    GENDER_REQUIRED = True
    STATUSES = ("Đang học", "Đã nghỉ", "Ra trường")

    def __init__(self, full_name: str, dob: Any, gender: str, address: str = "", phone: str = "",
                 nickname: str = "", parent_ids: list[str] | None = None,
                 pickup_persons: list[PickupPerson | dict] | None = None, class_id: str | None = None,
                 enrollment_date: Any = None, is_poor_household: bool = False,
                 extra_services: list[str] | None = None, notes: str = "", status: str = "Đang học",
                 leave_date: Any = None, id: str | None = None, check_age: bool = True) -> None:
        super().__init__(full_name, dob, phone=phone, address=address, gender=gender, id=id,
                         check_age=check_age)
        self.nickname = nickname
        self.status = status          # L14: Đang học / Đã nghỉ / Ra trường
        self.leave_date = leave_date
        self._parent_ids: list[str] = []
        for parent_id in parent_ids or []:
            self.add_parent_id(parent_id)
        self._pickup_persons: list[PickupPerson] = []
        for person in pickup_persons or []:
            self.add_pickup_person(person if isinstance(person, PickupPerson) else PickupPerson.from_dict(person))
        self.class_id = class_id
        self.enrollment_date = enrollment_date if enrollment_date is not None else date.today()
        self.is_poor_household = bool(is_poor_household)
        self.extra_services = extra_services or []
        self.notes = notes

    @property
    def role_name(self) -> str:
        return "Trẻ"

    # ------------------------------------------------------------------ tuổi
    @property
    def age_months(self) -> int:
        return age_in_months(self.dob)

    @property
    def age_text(self) -> str:
        return format_age(self.dob)

    # ------------------------------------------------------------------ thuộc tính
    @property
    def nickname(self) -> str:
        return self._nickname

    @nickname.setter
    def nickname(self, value: Any) -> None:
        self._nickname = normalize_spaces(value)
        self._nick_key = normalize_text(self._nickname)

    def _extra_search_text(self) -> str:
        return self._nick_key

    # ------------------------------------------------------------------ trạng thái học (L14)
    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: Any) -> None:
        key = normalize_text(value)
        for option in self.STATUSES:
            if normalize_text(option) == key:
                self._status = option
                return
        raise ValidationError(f"Trạng thái '{value}' không hợp lệ ({', '.join(self.STATUSES)}).")

    @property
    def is_active(self) -> bool:
        return self._status == "Đang học"

    @property
    def leave_date(self) -> date | None:
        return self._leave_date

    @leave_date.setter
    def leave_date(self, value: Any) -> None:
        self._leave_date = parse_date(value, "Ngày nghỉ học") if value else None

    @property
    def class_id(self) -> str | None:
        return self._class_id

    @class_id.setter
    def class_id(self, value: Any) -> None:
        text = normalize_spaces(value).upper() if value else ""
        self._class_id = text or None

    @property
    def enrollment_date(self) -> date:
        return self._enrollment_date

    @enrollment_date.setter
    def enrollment_date(self, value: Any) -> None:
        d = parse_date(value, "Ngày nhập học")
        if d < self.dob:
            raise ValidationError("Ngày nhập học không được trước ngày sinh.")
        self._enrollment_date = d

    @property
    def extra_services(self) -> list[str]:
        return list(self._extra_services)

    @extra_services.setter
    def extra_services(self, value: Any) -> None:
        items = value.split(",") if isinstance(value, str) else list(value or [])
        result: list[str] = []
        for item in items:
            name = normalize_spaces(item)
            if name and name not in result:
                result.append(name)
        self._extra_services = result

    @property
    def notes(self) -> str:
        return self._notes

    @notes.setter
    def notes(self, value: Any) -> None:
        self._notes = normalize_spaces(value)

    # ------------------------------------------------------------------ phụ huynh
    @property
    def parent_ids(self) -> list[str]:
        return list(self._parent_ids)

    def add_parent_id(self, parent_id: str) -> None:
        key = str(parent_id).strip().upper()
        if key and key not in self._parent_ids:
            self._parent_ids.append(key)

    def remove_parent_id(self, parent_id: str) -> None:
        key = str(parent_id).strip().upper()
        if key in self._parent_ids:
            self._parent_ids.remove(key)

    # ------------------------------------------------------------------ người đón hộ
    @property
    def pickup_persons(self) -> list[PickupPerson]:
        return list(self._pickup_persons)

    def add_pickup_person(self, person: PickupPerson) -> PickupPerson:
        if not isinstance(person, PickupPerson):
            raise ValidationError("Người đón hộ không hợp lệ.")
        if self.find_pickup_person(person.full_name):
            raise ValidationError(f"'{person.full_name}' đã có trong danh sách người đón hộ.")
        self._pickup_persons.append(person)
        return person

    def find_pickup_person(self, name: str) -> PickupPerson | None:
        """So khớp đúng họ tên CÓ DẤU (không phân biệt hoa thường) - 'Le Thi Hoa' khác 'Lê Thị Hòa' (L06)."""
        key = normalize_spaces(name).casefold()
        return next((p for p in self._pickup_persons if p.full_name.casefold() == key), None)

    def replace_pickup_person(self, name: str, person: PickupPerson) -> PickupPerson:
        """Sửa thông tin một người đón hộ (giữ nguyên vị trí trong danh sách). Không được trùng họ tên người khác."""
        if not isinstance(person, PickupPerson):
            raise ValidationError("Người đón hộ không hợp lệ.")
        old = self.find_pickup_person(name)
        if old is None:
            raise NotFoundError(f"Không có '{name}' trong danh sách người đón hộ của {self.full_name}.")
        other = self.find_pickup_person(person.full_name)
        if other is not None and other is not old:
            raise ValidationError(f"'{person.full_name}' đã có trong danh sách người đón hộ.")
        self._pickup_persons[self._pickup_persons.index(old)] = person
        return person

    def remove_pickup_person(self, name: str) -> PickupPerson:
        person = self.find_pickup_person(name)
        if person is None:
            raise NotFoundError(f"Không có '{name}' trong danh sách người đón hộ của {self.full_name}.")
        self._pickup_persons.remove(person)
        return person

    # ------------------------------------------------------------------ hiển thị, lưu trữ
    def profile(self) -> list[tuple[str, str]]:
        info = super().profile()
        info[5] = ("Tuổi", self.age_text)
        return info + [
            ("Tên ở nhà", self.nickname or "-"),
            ("Ngày nhập học", format_date(self.enrollment_date)),
            ("Mã lớp", self.class_id or "Chưa xếp lớp"),
            ("Trạng thái", self.status + (f" từ {format_date(self.leave_date)}" if self.leave_date else "")),
            ("Diện hộ nghèo", "Có" if self.is_poor_household else "Không"),
            ("Dịch vụ đăng ký", ", ".join(self._extra_services) or "-"),
            ("Người đón hộ", "; ".join(str(p) for p in self._pickup_persons) or "-"),
            ("Ghi chú", self.notes or "-"),
        ]

    def to_dict(self) -> dict[str, Any]:
        data = self._person_dict()
        data.update(nickname=self.nickname, parent_ids=self.parent_ids,
                    pickup_persons=[p.to_dict() for p in self._pickup_persons],
                    class_id=self.class_id, enrollment_date=self.enrollment_date.isoformat(),
                    is_poor_household=self.is_poor_household, extra_services=self.extra_services,
                    notes=self.notes, status=self.status,
                    leave_date=self.leave_date.isoformat() if self.leave_date else None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Child":
        return cls(full_name=data["full_name"], dob=data["dob"], gender=data.get("gender", ""),
                   address=data.get("address", ""), phone=data.get("phone", ""),
                   nickname=data.get("nickname", ""), parent_ids=data.get("parent_ids", []),
                   pickup_persons=data.get("pickup_persons", []), class_id=data.get("class_id"),
                   enrollment_date=data.get("enrollment_date") or data["dob"],
                   is_poor_household=data.get("is_poor_household", False),
                   extra_services=data.get("extra_services", []), notes=data.get("notes", ""),
                   status=data.get("status") or "Đang học", leave_date=data.get("leave_date"),
                   id=data["id"], check_age=False)
