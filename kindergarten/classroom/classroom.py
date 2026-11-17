"""T16 - Classroom: sĩ số tối đa, add_child(), remove_child(), assign_teacher().

Lớp tự kiểm tra sĩ số và độ tuổi phù hợp khi nhận trẻ.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from ..core.base_model import BaseModel
from ..exceptions import ClassFullError, DuplicateIdError, InvalidAgeError, NotFoundError, ValidationError
from ..hr.employees import Teacher
from ..people.child import Child
from ..utils import normalize_spaces, normalize_text, parse_int, require_text


class AgeGroup(Enum):
    """Khối lớp theo độ tuổi (tuổi tròn, tính cả hai đầu)."""

    NURSERY = ("Nhà trẻ", 1, 3)
    BEGINNER = ("Mầm", 3, 4)
    INTERMEDIATE = ("Chồi", 4, 5)
    SENIOR = ("Lá", 5, 6)

    def __init__(self, label: str, min_age: int, max_age: int) -> None:
        self.label = label
        self.min_age = min_age
        self.max_age = max_age

    @classmethod
    def parse(cls, value: Any) -> "AgeGroup":
        if isinstance(value, cls):
            return value
        text = normalize_text(value)
        for index, group in enumerate(cls, 1):
            if text in (group.name.lower(), normalize_text(group.label), str(index)):
                return group
        raise ValidationError(f"Khối lớp '{value}' không hợp lệ (Nhà trẻ/Mầm/Chồi/Lá).")

    @classmethod
    def for_age(cls, age: int) -> list["AgeGroup"]:
        return [g for g in cls if g.min_age <= age <= g.max_age]

    def __str__(self) -> str:
        return f"{self.label} ({self.min_age}-{self.max_age} tuổi)"


class Classroom(BaseModel):
    PREFIX = "L"
    MAX_CAPACITY = 40

    def __init__(self, name: str, age_group: Any, capacity: Any = 25, room: str = "",
                 teacher_id: str | None = None, child_ids: list[str] | None = None,
                 id: str | None = None) -> None:
        super().__init__(id)
        self._child_ids: list[str] = []
        for child_id in child_ids or []:
            key = str(child_id).strip().upper()
            if key and key not in self._child_ids:
                self._child_ids.append(key)
        self.name = name
        self.age_group = age_group
        self.capacity = capacity
        self.room = room
        self._teacher_id = str(teacher_id).strip().upper() if teacher_id else None

    # ------------------------------------------------------------------ thuộc tính
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: Any) -> None:
        self._name = require_text(value, "Tên lớp", 40)

    @property
    def age_group(self) -> AgeGroup:
        return self._age_group

    @age_group.setter
    def age_group(self, value: Any) -> None:
        self._age_group = AgeGroup.parse(value)

    @property
    def min_age(self) -> int:
        return self._age_group.min_age

    @property
    def max_age(self) -> int:
        return self._age_group.max_age

    @property
    def capacity(self) -> int:
        return self._capacity

    @capacity.setter
    def capacity(self, value: Any) -> None:
        capacity = parse_int(value, "Sĩ số tối đa", 1, self.MAX_CAPACITY)
        if capacity < self.size:
            raise ValidationError(f"Sĩ số tối đa ({capacity}) không được nhỏ hơn sĩ số hiện tại ({self.size}).")
        self._capacity = capacity

    @property
    def room(self) -> str:
        return self._room

    @room.setter
    def room(self, value: Any) -> None:
        self._room = normalize_spaces(value)

    @property
    def teacher_id(self) -> str | None:
        return self._teacher_id

    @property
    def child_ids(self) -> list[str]:
        return list(self._child_ids)

    @property
    def size(self) -> int:
        return len(self._child_ids)

    @property
    def is_full(self) -> bool:
        return self.size >= self.capacity

    @property
    def available_slots(self) -> int:
        return max(self.capacity - self.size, 0)

    @property
    def fill_rate(self) -> float:
        return self.size / self.capacity * 100

    @property
    def display_name(self) -> str:
        return f"{self.name} - {self.age_group.label} {self.min_age}-{self.max_age} tuổi"

    # ------------------------------------------------------------------ nghiệp vụ
    def has_child(self, child_id: str) -> bool:
        return str(child_id).strip().upper() in self._child_ids

    def accepts_age(self, age: int) -> bool:
        return self.min_age <= age <= self.max_age

    def check_can_accept(self, child: Child) -> None:
        """Ném lỗi nếu lớp không thể nhận trẻ (đã có trong lớp, đủ sĩ số, sai độ tuổi)."""
        if child.has_id and self.has_child(child.id):   # L22: không cấp mã cho trẻ chưa được lưu
            raise DuplicateIdError(f"{child.full_name} đã ở trong lớp {self.name}.")
        if self.is_full:
            raise ClassFullError(f"Lớp {self.name} đã đủ sĩ số ({self.size}/{self.capacity}), không nhận thêm trẻ.")
        if not self.accepts_age(child.age):
            raise InvalidAgeError(f"{child.full_name} ({child.age} tuổi) không phù hợp lớp {self.name} "
                                  f"(dành cho trẻ {self.min_age}-{self.max_age} tuổi).")

    def add_child(self, child: Child) -> None:
        self.check_can_accept(child)
        self._child_ids.append(child.id)
        child.class_id = self.id

    def remove_child(self, child: Child) -> None:
        if not self.has_child(child.id):
            raise NotFoundError(f"{child.full_name} không có trong lớp {self.name}.")
        self._child_ids.remove(child.id)
        if child.class_id == self.id:
            child.class_id = None

    def drop_child_id(self, child_id: str) -> None:
        """Bỏ mã trẻ khỏi danh sách (khi hồ sơ trẻ đã bị xóa khỏi hệ thống)."""
        key = str(child_id).strip().upper()
        if key in self._child_ids:
            self._child_ids.remove(key)

    def assign_teacher(self, teacher: Teacher) -> None:
        if not isinstance(teacher, Teacher):
            raise ValidationError("Chỉ giáo viên mới được phân công chủ nhiệm lớp.")
        self._teacher_id = teacher.id
        teacher.homeroom_class_id = self.id

    def unassign_teacher(self, teacher: Teacher | None = None) -> None:
        if teacher is not None and teacher.homeroom_class_id == self.id:
            teacher.homeroom_class_id = None
        self._teacher_id = None

    # ------------------------------------------------------------------ lưu trữ
    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(name=self.name, age_group=self.age_group.name, capacity=self.capacity, room=self.room,
                    teacher_id=self.teacher_id, child_ids=self.child_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Classroom":
        return cls(data["name"], data["age_group"], data.get("capacity", 25), data.get("room", ""),
                   data.get("teacher_id"), data.get("child_ids", []), id=data["id"])

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"
