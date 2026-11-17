"""T14 - Teacher, Staff ghi đè calculate_salary(): mỗi loại nhân sự tính lương riêng (đa hình)."""
from __future__ import annotations

from typing import Any

from ..core.person import Employee
from ..exceptions import ValidationError
from ..utils import (format_number, format_rate, format_vnd, normalize_spaces, normalize_text, parse_float,
                     parse_money, round_money)

# Lương cơ sở mặc định theo Nghị định 73/2024/NĐ-CP (áp dụng từ 01/07/2024).
# Giá trị thực tế lấy từ settings.json (K07) qua Teacher.configure().
BASE_SALARY_UNIT = 2_340_000


class Teacher(Employee):
    """Giáo viên: lương theo hệ số + phụ cấp ưu đãi nghề + thâm niên + chủ nhiệm."""

    PREFIX = "T"
    QUALIFICATIONS = ("Trung cấp", "Cao đẳng", "Đại học", "Thạc sĩ")
    BASE_UNIT = BASE_SALARY_UNIT  # lương cơ sở đang áp dụng
    INCENTIVE_RATE = 0.35        # phụ cấp ưu đãi nghề giáo viên mầm non
    HOMEROOM_ALLOWANCE = 500_000  # phụ cấp chủ nhiệm lớp

    @classmethod
    def configure(cls, base_unit: int, incentive_rate: float, homeroom_allowance: int) -> None:
        """Áp tham số lương từ cấu hình (K07)."""
        cls.BASE_UNIT, cls.INCENTIVE_RATE, cls.HOMEROOM_ALLOWANCE = base_unit, incentive_rate, homeroom_allowance

    def __init__(self, full_name: str, dob: Any, phone: str, address: str = "", gender: str = "Nữ",
                 qualification: str = "Cao đẳng", salary_coefficient: Any = 2.10, specialty: str = "",
                 hire_date: Any = None, homeroom_class_id: str | None = None, id: str | None = None,
                 check_age: bool = True) -> None:
        super().__init__(full_name, dob, phone, address, gender, position="Giáo viên",
                         hire_date=hire_date, id=id, check_age=check_age)
        self.qualification = qualification
        self.salary_coefficient = salary_coefficient
        self.specialty = specialty
        self.homeroom_class_id = homeroom_class_id

    @property
    def role_name(self) -> str:
        return "Giáo viên"

    @property
    def qualification(self) -> str:
        return self._qualification

    @qualification.setter
    def qualification(self, value: Any) -> None:
        key = normalize_text(value)
        for option in self.QUALIFICATIONS:
            if normalize_text(option) == key:
                self._qualification = option
                return
        raise ValidationError(f"Trình độ '{value}' không hợp lệ ({', '.join(self.QUALIFICATIONS)}).")

    @property
    def salary_coefficient(self) -> float:
        return self._salary_coefficient

    @salary_coefficient.setter
    def salary_coefficient(self, value: Any) -> None:
        self._salary_coefficient = round(parse_float(value, "Hệ số lương", 1.0, 10.0), 2)

    @property
    def specialty(self) -> str:
        return self._specialty

    @specialty.setter
    def specialty(self, value: Any) -> None:
        self._specialty = normalize_spaces(value)

    @property
    def homeroom_class_id(self) -> str | None:
        return self._homeroom_class_id

    @homeroom_class_id.setter
    def homeroom_class_id(self, value: Any) -> None:
        text = normalize_spaces(value).upper() if value else ""
        self._homeroom_class_id = text or None

    @property
    def is_homeroom(self) -> bool:
        return self._homeroom_class_id is not None

    # ------------------------------------------------------------------ tính lương
    def basic_salary(self) -> int:
        return round_money(self.BASE_UNIT * self.salary_coefficient)

    def seniority_rate(self, month: int | None = None, year: int | None = None) -> float:
        """Thâm niên nhà giáo: đủ 5 năm hưởng 5%, sau đó mỗi năm thêm 1%."""
        years = self.years_of_service(self.period_end(month, year))
        return years / 100 if years >= 5 else 0.0

    def calculate_salary(self, month: int | None = None, year: int | None = None) -> int:
        """Lương GV = Lương cơ sở × Hệ số + Ưu đãi nghề + Thâm niên + Phụ cấp chủ nhiệm."""
        basic = self.basic_salary()
        incentive = round_money(basic * self.INCENTIVE_RATE)
        seniority = round_money(basic * self.seniority_rate(month, year))
        homeroom = self.HOMEROOM_ALLOWANCE if self.is_homeroom else 0
        return basic + incentive + seniority + homeroom

    def salary_breakdown(self, month: int | None = None, year: int | None = None) -> list[tuple[str, int]]:
        basic = self.basic_salary()
        rate = self.seniority_rate(month, year)
        return [
            (f"Lương hệ số {format_number(self.salary_coefficient, 2)}", basic),
            (f"Ưu đãi nghề {format_rate(self.INCENTIVE_RATE)}%", round_money(basic * self.INCENTIVE_RATE)),
            (f"Thâm niên {format_rate(rate)}%", round_money(basic * rate)),
            ("Phụ cấp chủ nhiệm", self.HOMEROOM_ALLOWANCE if self.is_homeroom else 0),
        ]

    def profile(self) -> list[tuple[str, str]]:
        return super().profile() + [
            ("Trình độ", self.qualification),
            ("Hệ số lương", format_number(self.salary_coefficient, 2)),
            ("Chuyên môn", self.specialty or "Giáo viên đứng lớp"),
            ("Lớp chủ nhiệm", self.homeroom_class_id or "-"),
        ]

    def to_dict(self) -> dict[str, Any]:
        data = self._employee_dict()
        data.update(qualification=self.qualification, salary_coefficient=self.salary_coefficient,
                    specialty=self.specialty, homeroom_class_id=self.homeroom_class_id)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Teacher":
        return cls(full_name=data["full_name"], dob=data["dob"], phone=data["phone"],
                   address=data.get("address", ""), gender=data.get("gender", ""),
                   qualification=data.get("qualification", "Cao đẳng"),
                   salary_coefficient=data.get("salary_coefficient", 2.10),
                   specialty=data.get("specialty", ""), hire_date=data.get("hire_date"),
                   homeroom_class_id=data.get("homeroom_class_id"), id=data["id"], check_age=False)


class Staff(Employee):
    """Nhân viên (cấp dưỡng, bảo vệ, y tế, kế toán...): lương cố định + phụ cấp + làm thêm giờ."""

    PREFIX = "NV"
    POSITIONS = ("Cấp dưỡng", "Bảo vệ", "Nhân viên y tế", "Kế toán", "Văn thư", "Lao công")
    STANDARD_HOURS = 208          # 26 ngày × 8 giờ
    OVERTIME_MULTIPLIER = 1.5     # làm thêm ngày thường hưởng 150%

    def __init__(self, full_name: str, dob: Any, phone: str, address: str = "", gender: str = "",
                 position: str = "Cấp dưỡng", base_salary: Any = 5_000_000, allowance: Any = 0,
                 hire_date: Any = None, overtime: dict[str, Any] | None = None, id: str | None = None,
                 check_age: bool = True) -> None:
        super().__init__(full_name, dob, phone, address, gender, position=position,
                         hire_date=hire_date, id=id, check_age=check_age)
        self.base_salary = base_salary
        self.allowance = allowance
        self._overtime: dict[str, float] = {}
        for key, hours in (overtime or {}).items():
            self._overtime[str(key)] = parse_float(hours, "Số giờ làm thêm", 0, 200)

    @property
    def role_name(self) -> str:
        return "Nhân viên"

    @property
    def base_salary(self) -> int:
        return self._base_salary

    @base_salary.setter
    def base_salary(self, value: Any) -> None:
        self._base_salary = parse_money(value, "Lương cơ bản", allow_zero=False)

    @property
    def allowance(self) -> int:
        return self._allowance

    @allowance.setter
    def allowance(self, value: Any) -> None:
        self._allowance = parse_money(value, "Phụ cấp")

    # ------------------------------------------------------------------ giờ làm thêm
    @staticmethod
    def _month_key(month: int | None, year: int | None) -> str:
        end = Employee.period_end(month, year)
        return f"{end.year:04d}-{end.month:02d}"

    def set_overtime(self, month: int, year: int, hours: Any) -> None:
        self._overtime[self._month_key(month, year)] = parse_float(hours, "Số giờ làm thêm", 0, 200)

    def overtime_hours(self, month: int | None = None, year: int | None = None) -> float:
        return self._overtime.get(self._month_key(month, year), 0.0)

    def hourly_rate(self) -> float:
        return self.base_salary / self.STANDARD_HOURS

    # ------------------------------------------------------------------ tính lương
    def calculate_salary(self, month: int | None = None, year: int | None = None) -> int:
        """Lương NV = Lương cơ bản + Phụ cấp + Giờ làm thêm × (Lương cơ bản / 208) × 150%."""
        overtime_pay = round_money(self.overtime_hours(month, year) * self.hourly_rate() * self.OVERTIME_MULTIPLIER)
        return self.base_salary + self.allowance + overtime_pay

    def salary_breakdown(self, month: int | None = None, year: int | None = None) -> list[tuple[str, int]]:
        hours = self.overtime_hours(month, year)
        return [
            ("Lương cơ bản", self.base_salary),
            ("Phụ cấp", self.allowance),
            (f"Làm thêm {format_number(hours, 1)} giờ",
             round_money(hours * self.hourly_rate() * self.OVERTIME_MULTIPLIER)),
        ]

    def profile(self) -> list[tuple[str, str]]:
        return super().profile() + [
            ("Lương cơ bản", format_vnd(self.base_salary)),
            ("Phụ cấp", format_vnd(self.allowance)),
        ]

    def to_dict(self) -> dict[str, Any]:
        data = self._employee_dict()
        data.update(base_salary=self.base_salary, allowance=self.allowance, overtime=dict(self._overtime))
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Staff":
        return cls(full_name=data["full_name"], dob=data["dob"], phone=data["phone"],
                   address=data.get("address", ""), gender=data.get("gender", ""),
                   position=data.get("position", "Cấp dưỡng"), base_salary=data.get("base_salary", 5_000_000),
                   allowance=data.get("allowance", 0), hire_date=data.get("hire_date"),
                   overtime=data.get("overtime", {}), id=data["id"], check_age=False)
