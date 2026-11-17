"""T09 - Parent kế thừa Person: hồ sơ phụ huynh, nghề nghiệp, liên kết với các con."""
from __future__ import annotations

import re
from typing import Any

from ..core.person import Person
from ..exceptions import ValidationError
from ..utils import normalize_spaces, normalize_text

_EMAIL_PATTERN = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


class Parent(Person):
    PREFIX = "PH"
    MIN_AGE = 18
    RELATIONSHIPS = ("Bố", "Mẹ", "Ông", "Bà", "Anh", "Chị", "Cô", "Dì", "Chú", "Bác", "Người giám hộ")
    _MALE = {"Bố", "Ông", "Anh", "Chú", "Bác"}
    _FEMALE = {"Mẹ", "Bà", "Chị", "Cô", "Dì"}

    def __init__(self, full_name: str, dob: Any, phone: str, address: str = "", gender: str = "",
                 occupation: str = "", relationship: str = "Người giám hộ", email: str = "",
                 child_ids: list[str] | None = None, id: str | None = None, check_age: bool = True) -> None:
        super().__init__(full_name, dob, phone, address, gender, id=id, check_age=check_age)
        self.occupation = occupation
        self.relationship = relationship
        self.email = email
        if not self.gender:  # tự suy giới tính từ quan hệ: Bố -> Nam, Mẹ -> Nữ
            if self.relationship in self._MALE:
                self.gender = "Nam"
            elif self.relationship in self._FEMALE:
                self.gender = "Nữ"
        if check_age:
            self.check_gender_matches_relationship()
        self._child_ids: list[str] = []
        for child_id in child_ids or []:
            self.add_child_id(child_id)

    @property
    def role_name(self) -> str:
        return "Phụ huynh"

    def check_gender_matches_relationship(self) -> None:
        """L27: không chấp nhận mâu thuẫn như 'Bố' + 'Nữ'."""
        if (self.relationship in self._MALE and self.gender == "Nữ") or \
                (self.relationship in self._FEMALE and self.gender == "Nam"):
            raise ValidationError(f"Quan hệ '{self.relationship}' mâu thuẫn với giới tính '{self.gender}'.")

    @property
    def occupation(self) -> str:
        return self._occupation

    @occupation.setter
    def occupation(self, value: Any) -> None:
        self._occupation = normalize_spaces(value)

    @property
    def relationship(self) -> str:
        return self._relationship

    @relationship.setter
    def relationship(self, value: Any) -> None:
        key = normalize_text(value)
        for option in self.RELATIONSHIPS:
            if normalize_text(option) == key:
                self._relationship = option
                return
        raise ValidationError(f"Quan hệ '{value}' không hợp lệ ({', '.join(self.RELATIONSHIPS)}).")

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: Any) -> None:
        text = normalize_spaces(value).lower()
        if text and not _EMAIL_PATTERN.match(text):
            raise ValidationError(f"Email '{value}' không hợp lệ.")
        self._email = text

    # ------------------------------------------------------------------ liên kết với các con
    @property
    def child_ids(self) -> list[str]:
        return list(self._child_ids)

    def add_child_id(self, child_id: str) -> None:
        key = str(child_id).strip().upper()
        if key and key not in self._child_ids:
            self._child_ids.append(key)

    def remove_child_id(self, child_id: str) -> None:
        key = str(child_id).strip().upper()
        if key in self._child_ids:
            self._child_ids.remove(key)

    def has_child(self, child_id: str) -> bool:
        return str(child_id).strip().upper() in self._child_ids

    def profile(self) -> list[tuple[str, str]]:
        return super().profile() + [
            ("Quan hệ với trẻ", self.relationship),
            ("Nghề nghiệp", self.occupation or "-"),
            ("Email", self.email or "-"),
            ("Mã các con", ", ".join(self._child_ids) or "-"),
        ]

    def to_dict(self) -> dict[str, Any]:
        data = self._person_dict()
        data.update(occupation=self.occupation, relationship=self.relationship,
                    email=self.email, child_ids=self.child_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Parent":
        return cls(full_name=data["full_name"], dob=data["dob"], phone=data.get("phone", ""),
                   address=data.get("address", ""), gender=data.get("gender", ""),
                   occupation=data.get("occupation", ""),
                   relationship=data.get("relationship", "Người giám hộ"),
                   email=data.get("email", ""), child_ids=data.get("child_ids", []),
                   id=data["id"], check_age=False)
