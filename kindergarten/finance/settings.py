"""Cấu hình học phí, miễn giảm và các tham số lương (lưu trong settings.json, chỉnh được trong chương trình).

K07: các tham số nghiệp vụ không còn viết cứng trong mã (lương cơ sở, phụ cấp, học phí theo khối...).
L17: tỷ lệ giảm lưu đủ chữ số; không cho trùng tên dịch vụ sau khi chuẩn hóa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..exceptions import NotFoundError, ValidationError
from ..utils import normalize_spaces, normalize_text, parse_float, parse_int, parse_money


def _default_services() -> dict[str, int]:
    return {"Năng khiếu (vẽ, múa)": 300_000, "Tiếng Anh": 400_000}


@dataclass
class FeeSettings:
    monthly_tuition: int = 2_500_000      # học phí tháng (mặc định cho mọi khối)
    meal_rate_per_day: int = 35_000       # tiền ăn mỗi ngày đi học
    extra_services: dict[str, int] = field(default_factory=_default_services)  # dịch vụ tự chọn
    second_child_rate: float = 0.20       # giảm học phí cho con thứ hai trở đi
    poor_household_rate: float = 0.50     # giảm học phí cho trẻ thuộc hộ nghèo
    due_days: int = 10                    # số ngày được phép nộp kể từ ngày lập hóa đơn
    tuition_by_group: dict[str, int] = field(default_factory=dict)  # học phí riêng theo khối (tên khối -> tiền)
    base_salary_unit: int = 2_340_000     # lương cơ sở (Nghị định 73/2024/NĐ-CP)
    teacher_incentive_rate: float = 0.35  # phụ cấp ưu đãi nghề giáo viên mầm non
    homeroom_allowance: int = 500_000     # phụ cấp chủ nhiệm lớp

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.monthly_tuition = parse_money(self.monthly_tuition, "Học phí tháng")
        self.meal_rate_per_day = parse_money(self.meal_rate_per_day, "Tiền ăn/ngày")
        self.second_child_rate = round(parse_float(self.second_child_rate, "Tỷ lệ giảm con thứ hai", 0, 1), 6)
        self.poor_household_rate = round(parse_float(self.poor_household_rate, "Tỷ lệ giảm hộ nghèo", 0, 1), 6)
        self.due_days = parse_int(self.due_days, "Hạn nộp (ngày)", 0, 60)
        self.base_salary_unit = parse_money(self.base_salary_unit, "Lương cơ sở", allow_zero=False)
        self.teacher_incentive_rate = round(parse_float(self.teacher_incentive_rate, "Ưu đãi nghề", 0, 1), 6)
        self.homeroom_allowance = parse_money(self.homeroom_allowance, "Phụ cấp chủ nhiệm")
        services: dict[str, int] = {}
        seen: set[str] = set()
        for name, price in dict(self.extra_services).items():
            clean = normalize_spaces(name)
            if not clean:
                raise ValidationError("Tên dịch vụ không được để trống.")
            if normalize_text(clean) in seen:
                raise ValidationError(f"Dịch vụ '{clean}' bị trùng tên.")
            seen.add(normalize_text(clean))
            services[clean] = parse_money(price, f"Giá dịch vụ '{clean}'")
        self.extra_services = services
        self.tuition_by_group = {normalize_spaces(k): parse_money(v, f"Học phí khối {k}")
                                 for k, v in dict(self.tuition_by_group).items() if normalize_spaces(k)}

    def update(self, **changes: Any) -> None:
        """Sửa cấu hình; nếu giá trị mới sai thì giữ nguyên cấu hình cũ."""
        backup = self.to_dict()
        try:
            for key, value in changes.items():
                if not hasattr(self, key):
                    raise ValidationError(f"Không có cấu hình '{key}'.")
                setattr(self, key, value)
            self.validate()
        except Exception:
            restored = FeeSettings.from_dict(backup)
            self.__dict__.update(restored.__dict__)
            raise

    def tuition_for(self, group_label: str | None) -> int:
        """Học phí theo khối (nếu có cấu hình riêng), ngược lại dùng mức chung."""
        if group_label:
            key = normalize_text(group_label)
            for name, amount in self.tuition_by_group.items():
                if normalize_text(name) == key:
                    return amount
        return self.monthly_tuition

    def find_service(self, name: str) -> str | None:
        key = normalize_text(name)
        return next((s for s in self.extra_services if normalize_text(s) == key), None)

    def service_price(self, name: str) -> int:
        service = self.find_service(name)
        if service is None:
            raise NotFoundError(f"Không có dịch vụ '{name}' trong bảng giá.")
        return self.extra_services[service]

    def to_dict(self) -> dict[str, Any]:
        return {
            "monthly_tuition": self.monthly_tuition,
            "meal_rate_per_day": self.meal_rate_per_day,
            "extra_services": dict(self.extra_services),
            "second_child_rate": self.second_child_rate,
            "poor_household_rate": self.poor_household_rate,
            "due_days": self.due_days,
            "tuition_by_group": dict(self.tuition_by_group),
            "base_salary_unit": self.base_salary_unit,
            "teacher_incentive_rate": self.teacher_incentive_rate,
            "homeroom_allowance": self.homeroom_allowance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeeSettings":
        defaults = cls().to_dict()
        return cls(**{key: data.get(key, value) for key, value in defaults.items()})
