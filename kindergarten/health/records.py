"""T12, T13 - Hồ sơ cân đo (HealthRecord), dị ứng (Allergy). (Phần tiêm chủng đã bỏ theo yêu cầu.)"""
from __future__ import annotations

import functools
import re
from datetime import date
from enum import Enum
from typing import Any

from ..core.base_model import BaseModel
from ..exceptions import ValidationError
from ..utils import (format_date, format_number, iso, normalize_spaces, normalize_text, parse_date,
                     parse_float, parse_int, parse_optional_date, remove_accents, require_text)


class NutritionStatus(Enum):
    UNDERWEIGHT = "Nhẹ cân"
    NORMAL = "Bình thường"
    OVERWEIGHT = "Thừa cân"
    OBESE = "Béo phì"


class HealthRecord(BaseModel):
    """T12 - Một lần cân đo: ngày đo, chiều cao, cân nặng, BMI và đánh giá dinh dưỡng."""

    PREFIX = "SK"
    # (từ tháng tuổi, đến tháng tuổi, ngưỡng nhẹ cân, ngưỡng thừa cân, ngưỡng béo phì)
    # Ngưỡng BMI tham khảo, đơn giản hóa từ chuẩn tăng trưởng WHO (-2SD, +2SD, +3SD).
    BMI_THRESHOLDS = (
        (0, 24, 14.5, 19.5, 21.0),
        (24, 48, 13.5, 18.2, 19.6),
        (48, 120, 13.0, 18.3, 20.0),
    )

    def __init__(self, child_id: str, measure_date: Any, height_cm: Any, weight_kg: Any,
                 age_months: int, note: str = "", id: str | None = None) -> None:
        super().__init__(id)
        self.child_id = require_text(child_id, "Mã trẻ").upper()
        self.measure_date = measure_date
        self.height_cm = height_cm
        self.weight_kg = weight_kg
        self.age_months = parse_int(age_months, "Tháng tuổi", 0, 120)
        self.note = note

    @property
    def measure_date(self) -> date:
        return self._measure_date

    @measure_date.setter
    def measure_date(self, value: Any) -> None:
        self._measure_date = parse_date(value, "Ngày đo")

    @property
    def height_cm(self) -> float:
        return self._height_cm

    @height_cm.setter
    def height_cm(self, value: Any) -> None:
        self._height_cm = round(parse_float(value, "Chiều cao (cm)", 40, 150), 1)

    @property
    def weight_kg(self) -> float:
        return self._weight_kg

    @weight_kg.setter
    def weight_kg(self, value: Any) -> None:
        self._weight_kg = round(parse_float(value, "Cân nặng (kg)", 3, 60), 1)

    @property
    def note(self) -> str:
        return self._note

    @note.setter
    def note(self, value: Any) -> None:
        self._note = normalize_spaces(value)

    def calc_bmi(self) -> float:
        """BMI = cân nặng (kg) / chiều cao (m)^2."""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m * height_m), 1)

    @classmethod
    def thresholds_for(cls, age_months: int) -> tuple[float, float, float]:
        for low, high, under, over, obese in cls.BMI_THRESHOLDS:
            if low <= age_months < high:
                return under, over, obese
        return cls.BMI_THRESHOLDS[-1][2:]

    def assess(self) -> NutritionStatus:
        """Đánh giá dinh dưỡng theo BMI và tháng tuổi."""
        bmi = self.calc_bmi()
        under, over, obese = self.thresholds_for(self.age_months)
        if bmi < under:
            return NutritionStatus.UNDERWEIGHT
        if bmi >= obese:
            return NutritionStatus.OBESE
        if bmi >= over:
            return NutritionStatus.OVERWEIGHT
        return NutritionStatus.NORMAL

    @property
    def bmi_text(self) -> str:
        return format_number(self.calc_bmi(), 1)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(child_id=self.child_id, measure_date=self.measure_date.isoformat(),
                    height_cm=self.height_cm, weight_kg=self.weight_kg, age_months=self.age_months,
                    note=self.note)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthRecord":
        return cls(data["child_id"], data["measure_date"], data["height_cm"], data["weight_kg"],
                   data.get("age_months", 48), data.get("note", ""), id=data["id"])


class AllergySeverity(Enum):
    MILD = "Nhẹ"
    MODERATE = "Trung bình"
    SEVERE = "Nặng"

    @classmethod
    def parse(cls, value: Any) -> "AllergySeverity":
        if isinstance(value, cls):
            return value
        text = normalize_text(value)
        for item in cls:
            if text in (normalize_text(item.value), item.name.lower()):
                return item
        aliases = {"1": cls.MILD, "2": cls.MODERATE, "3": cls.SEVERE, "tb": cls.MODERATE}
        if text in aliases:
            return aliases[text]
        raise ValidationError(f"Mức độ dị ứng '{value}' không hợp lệ (Nhẹ/Trung bình/Nặng).")


# Nhóm chất gây dị ứng: dị ứng "hải sản" thì món có tôm, cua... đều phải cảnh báo.
ALLERGEN_GROUPS: dict[str, tuple[str, ...]] = {
    "hải sản": ("tôm", "cua", "ghẹ", "mực", "nghêu", "sò", "ốc", "hến", "hàu", "bạch tuộc"),
    "sữa": ("sữa bò", "sữa tươi", "sữa chua", "phô mai", "váng sữa", "sữa bột", "bơ sữa"),
    "sữa bò": ("sữa", "sữa tươi", "sữa chua", "phô mai", "váng sữa", "sữa bột", "bơ sữa"),
    "đậu phộng": ("lạc",),
    "lạc": ("đậu phộng",),
    "trứng": ("trứng gà", "trứng vịt", "trứng cút"),
    "gluten": ("bột mì", "bánh mì", "mì"),
    "đậu nành": ("đậu hũ", "đậu phụ", "tàu hũ", "sữa đậu nành", "tương"),
    "mè": ("vừng",),
    "vừng": ("mè",),
}


_GROUPS_BY_KEY = {normalize_text(name): terms for name, terms in ALLERGEN_GROUPS.items()}


def _canonical(text: str, strip_accents: bool) -> str:
    value = normalize_spaces(text).lower()  # normalize_spaces đã chuẩn hóa Unicode NFC
    return remove_accents(value) if strip_accents else value


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


@functools.lru_cache(maxsize=4096)
def ingredient_matches_allergen(allergen: str, ingredient: str) -> bool:
    """Thành phần món ăn có chứa chất gây dị ứng không? (L07 - ưu tiên không bỏ sót)

    - Chiều thuận: thành phần CHỨA chất dị ứng hoặc một thành viên của nhóm (dị ứng "hải sản" -> "tôm sú").
    - Chiều ngược theo nhóm: món ghi tên NHÓM ("hải sản tổng hợp") mà trẻ dị ứng một thành viên ("tôm").
    - Không còn khớp ngược tùy tiện ("bò" không còn bị coi là chứa "sữa bò").
    - Chỉ bỏ dấu khi chính tên dị ứng được gõ không dấu ("tom"), nên "cá" không nhầm với "ca cao".
    Kết quả được lưu đệm (P05) vì cùng một cặp được so nhiều lần khi xem thực đơn.
    """
    strip = remove_accents(allergen) == allergen
    allergen_key, ingredient_key = _canonical(allergen, strip), _canonical(ingredient, strip)
    terms = {allergen_key, *(_canonical(t, strip) for t in _GROUPS_BY_KEY.get(normalize_text(allergen), ()))}
    if any(_contains_phrase(ingredient_key, term) for term in terms):
        return True
    for group, members in ALLERGEN_GROUPS.items():
        if _contains_phrase(ingredient_key, _canonical(group, strip)) and \
                any(_canonical(member, strip) == allergen_key for member in members):
            return True
    return False


class Allergy(BaseModel):
    """T13 - Thông tin dị ứng của trẻ."""

    PREFIX = "DU"

    def __init__(self, child_id: str, allergen: str, severity: Any = AllergySeverity.MILD,
                 reaction: str = "", id: str | None = None) -> None:
        super().__init__(id)
        self.child_id = require_text(child_id, "Mã trẻ").upper()
        self.allergen = allergen
        self.severity = severity
        self.reaction = reaction

    @property
    def allergen(self) -> str:
        return self._allergen

    @allergen.setter
    def allergen(self, value: Any) -> None:
        self._allergen = require_text(value, "Chất gây dị ứng", 60).lower()

    @property
    def severity(self) -> AllergySeverity:
        return self._severity

    @severity.setter
    def severity(self, value: Any) -> None:
        self._severity = AllergySeverity.parse(value)

    @property
    def reaction(self) -> str:
        return self._reaction

    @reaction.setter
    def reaction(self, value: Any) -> None:
        self._reaction = normalize_spaces(value)

    def matches(self, ingredient: str) -> bool:
        return ingredient_matches_allergen(self.allergen, ingredient)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(child_id=self.child_id, allergen=self.allergen, severity=self.severity.name,
                    reaction=self.reaction)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Allergy":
        return cls(data["child_id"], data["allergen"], data.get("severity", "MILD"),
                   data.get("reaction", ""), id=data["id"])
