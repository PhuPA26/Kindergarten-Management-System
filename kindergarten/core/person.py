"""T04 - Person (trừu tượng) và Employee (trừu tượng).

Các thuộc tính dùng @property có kiểm tra: nhập sai SĐT, ngày sinh... sẽ bị từ chối
bằng ValidationError/InvalidAgeError thay vì lưu dữ liệu sai.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, ClassVar

from ..exceptions import InvalidAgeError, ValidationError
from ..utils import (add_months, calculate_age, format_date, format_vnd, month_bounds, normalize_spaces,
                     normalize_text, parse_date, require_text, validate_name, validate_phone)
from .base_model import BaseModel

GENDERS = ("Nam", "Nữ")


def parse_gender(value: Any, required: bool = False) -> str:
    text = normalize_text(value)
    if not text:
        if required:
            raise ValidationError("Giới tính không được để trống (Nam/Nữ).")
        return ""
    if text in ("nam", "m", "male", "trai", "1"):
        return "Nam"
    if text in ("nu", "f", "female", "gai", "2"):
        return "Nữ"
    raise ValidationError(f"Giới tính '{value}' không hợp lệ (Nam/Nữ).")


class Person(BaseModel, ABC):
    """Con người nói chung: họ tên, ngày sinh, giới tính, SĐT, địa chỉ."""

    PHONE_REQUIRED: ClassVar[bool] = True
    GENDER_REQUIRED: ClassVar[bool] = False
    MIN_AGE: ClassVar[int | None] = None
    MAX_AGE: ClassVar[int | None] = None

    def __init__(self, full_name: str, dob: Any, phone: str = "", address: str = "",
                 gender: str = "", id: str | None = None, check_age: bool = True) -> None:
        super().__init__(id)
        self._check_age = check_age  # tắt khi đọc dữ liệu cũ từ file (trẻ đã lớn hơn 6 tuổi...)
        self.full_name = full_name
        self.dob = dob
        self.gender = gender
        self.phone = phone
        self.address = address
        self._check_age = True

    # ------------------------------------------------------------------ trừu tượng
    @property
    @abstractmethod
    def role_name(self) -> str:
        """Tên vai trò hiển thị: Trẻ, Phụ huynh, Giáo viên, Nhân viên..."""

    # ------------------------------------------------------------------ thuộc tính
    @property
    def full_name(self) -> str:
        return self._full_name

    @full_name.setter
    def full_name(self, value: Any) -> None:
        self._full_name = validate_name(value)
        # P08: tính sẵn khóa tìm kiếm / sắp xếp một lần khi gán tên
        self._name_key = normalize_text(self._full_name)
        self._given_key = normalize_text(self._full_name.split()[-1])

    @property
    def search_text(self) -> str:
        """Chuỗi đã chuẩn hóa dùng để tìm kiếm nhanh (tên + SĐT + các trường bổ sung của lớp con)."""
        return f"{self._name_key} {getattr(self, '_phone', '')} {self._extra_search_text()}"

    def _extra_search_text(self) -> str:
        return ""

    @property
    def given_name(self) -> str:
        """Tên (từ cuối) - người Việt sắp xếp theo tên chứ không theo họ."""
        return self._full_name.split()[-1]

    @property
    def dob(self) -> date:
        return self._dob

    @dob.setter
    def dob(self, value: Any) -> None:
        d = parse_date(value, "Ngày sinh")
        today = date.today()
        if d > today:
            raise ValidationError("Ngày sinh không được ở tương lai.")
        if d.year < 1900:
            raise ValidationError("Ngày sinh không hợp lệ.")
        # L05: chỉ kiểm tra tuổi khi ngày sinh thực sự thay đổi (trẻ đã lớn quá 6 tuổi vẫn sửa được hồ sơ)
        if self._check_age and d != getattr(self, "_dob", None):
            self.validate_age(calculate_age(d, today))
        self._dob = d

    @property
    def gender(self) -> str:
        return self._gender

    @gender.setter
    def gender(self, value: Any) -> None:
        self._gender = parse_gender(value, self.GENDER_REQUIRED)

    @property
    def phone(self) -> str:
        return self._phone

    @phone.setter
    def phone(self, value: Any) -> None:
        self._phone = validate_phone(value, required=self.PHONE_REQUIRED)

    @property
    def address(self) -> str:
        return self._address

    @address.setter
    def address(self, value: Any) -> None:
        self._address = normalize_spaces(value)

    @property
    def age(self) -> int:
        return calculate_age(self._dob)

    @property
    def sort_key(self) -> tuple[str, str]:
        return self._given_key, self._name_key

    # ------------------------------------------------------------------ nghiệp vụ
    def validate_age(self, age: int) -> None:
        too_young = self.MIN_AGE is not None and age < self.MIN_AGE
        too_old = self.MAX_AGE is not None and age > self.MAX_AGE
        if not (too_young or too_old):
            return
        if self.MIN_AGE is not None and self.MAX_AGE is not None:
            rule = f"từ {self.MIN_AGE} đến {self.MAX_AGE} tuổi"
        elif self.MIN_AGE is not None:
            rule = f"từ {self.MIN_AGE} tuổi trở lên"
        else:
            rule = f"không quá {self.MAX_AGE} tuổi"
        raise InvalidAgeError(f"{self.role_name} phải {rule} (tuổi theo ngày sinh: {age}).")

    def profile(self) -> list[tuple[str, str]]:
        """Thông tin hiển thị dạng (nhãn, giá trị); lớp con bổ sung thêm (đa hình)."""
        return [
            ("Mã", self.id),
            ("Vai trò", self.role_name),
            ("Họ tên", self.full_name),
            ("Giới tính", self.gender or "-"),
            ("Ngày sinh", format_date(self.dob)),
            ("Tuổi", str(self.age)),
            ("Điện thoại", self.phone or "-"),
            ("Địa chỉ", self.address or "-"),
        ]

    def _person_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(full_name=self.full_name, dob=self.dob.isoformat(), gender=self.gender,
                    phone=self.phone, address=self.address)
        return data

    def __str__(self) -> str:
        return f"{self.full_name} ({self.id})"


class Employee(Person, ABC):
    """Nhân sự nói chung. Mỗi loại nhân sự tự tính lương theo cách riêng (T14 - đa hình)."""

    MIN_AGE = 18

    def __init__(self, full_name: str, dob: Any, phone: str, address: str = "", gender: str = "",
                 position: str = "Nhân viên", hire_date: Any = None, id: str | None = None,
                 check_age: bool = True) -> None:
        super().__init__(full_name, dob, phone, address, gender, id=id, check_age=check_age)
        self.position = position
        self.hire_date = hire_date if hire_date is not None else date.today()

    @property
    def position(self) -> str:
        return self._position

    @position.setter
    def position(self, value: Any) -> None:
        self._position = require_text(value, "Chức vụ", 60)

    @property
    def hire_date(self) -> date:
        return self._hire_date

    @hire_date.setter
    def hire_date(self, value: Any) -> None:
        d = parse_date(value, "Ngày vào làm")
        if d > date.today():
            raise ValidationError("Ngày vào làm không được ở tương lai.")
        self._check_hire_age(self.dob, d)
        self._hire_date = d

    @staticmethod
    def _check_hire_age(dob: date, hire_date: date) -> None:
        if hire_date < add_months(dob, 18 * 12):
            raise ValidationError("Ngày vào làm phải sau ngày nhân sự đủ 18 tuổi.")

    def validate_dates(self) -> None:
        """L11: ràng buộc chéo ngày sinh - ngày vào làm (gọi lại khi sửa ngày sinh)."""
        self._check_hire_age(self.dob, self.hire_date)

    def years_of_service(self, on: date | None = None) -> int:
        on = on or date.today()
        return calculate_age(self.hire_date, on) if on >= self.hire_date else 0

    @staticmethod
    def period_end(month: int | None = None, year: int | None = None) -> date:
        """Ngày cuối của kỳ lương (mặc định: hôm nay)."""
        if month is None or year is None:
            return date.today()
        return month_bounds(month, year)[1]

    # ------------------------------------------------------------------ đa hình
    @abstractmethod
    def calculate_salary(self, month: int | None = None, year: int | None = None) -> int:
        """Lương thực lĩnh của tháng - mỗi lớp con có công thức riêng."""

    @abstractmethod
    def salary_breakdown(self, month: int | None = None, year: int | None = None) -> list[tuple[str, int]]:
        """Các khoản cấu thành lương (để in bảng lương)."""

    def salary_note(self, month: int | None = None, year: int | None = None) -> str:
        return " + ".join(f"{label} {format_vnd(amount)}"
                          for label, amount in self.salary_breakdown(month, year) if amount)

    def profile(self) -> list[tuple[str, str]]:
        return super().profile() + [
            ("Chức vụ", self.position),
            ("Ngày vào làm", format_date(self.hire_date)),
            ("Thâm niên", f"{self.years_of_service()} năm"),
            ("Lương tháng này", format_vnd(self.calculate_salary())),
        ]

    def _employee_dict(self) -> dict[str, Any]:
        data = self._person_dict()
        data.update(position=self.position, hire_date=self.hire_date.isoformat())
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Employee":
        """Đọc dữ liệu nhân sự: tự chọn đúng lớp con (Teacher/Staff) theo trường 'type'."""
        target = BaseModel.class_for(str(data.get("type", "")))
        if target is cls or not issubclass(target, cls):
            raise ValidationError(f"Kiểu nhân sự '{data.get('type')}' không hợp lệ.")
        return target.from_dict(data)
