"""K03 - Lịch năm học: một nơi duy nhất quyết định "ngày đi học" (L04, L19, L20).

Điểm danh, sổ điểm danh, tiền ăn, dashboard và thực đơn đều hỏi `calendar.is_school_day(d)`
thay vì mỗi nơi tự viết điều kiện riêng.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .exceptions import ValidationError
from .utils import format_date, month_dates, monday_of, normalize_spaces, parse_bool, parse_date


class SchoolCalendar:
    def __init__(self, holidays: dict[Any, str] | None = None, saturday_classes: bool = False) -> None:
        self.saturday_classes = bool(saturday_classes)
        self._holidays: dict[date, str] = {}
        for day, name in (holidays or {}).items():
            self.add_holiday(day, name)

    # ------------------------------------------------------------------ ngày nghỉ lễ
    @property
    def holidays(self) -> dict[date, str]:
        return dict(sorted(self._holidays.items()))

    def add_holiday(self, day: Any, name: str = "Nghỉ lễ") -> date:
        d = parse_date(day, "Ngày nghỉ")
        self._holidays[d] = normalize_spaces(name) or "Nghỉ lễ"
        return d

    def remove_holiday(self, day: Any) -> None:
        d = parse_date(day, "Ngày nghỉ")
        if d not in self._holidays:
            raise ValidationError(f"Ngày {format_date(d)} không có trong danh sách nghỉ lễ.")
        del self._holidays[d]

    def holiday_name(self, d: date) -> str | None:
        return self._holidays.get(d)

    # ------------------------------------------------------------------ ngày học
    def is_study_weekday(self, d: date) -> bool:
        return d.weekday() < 5 or (self.saturday_classes and d.weekday() == 5)

    def is_school_day(self, d: date) -> bool:
        return self.is_study_weekday(d) and d not in self._holidays

    def reason_not_school_day(self, d: date) -> str:
        if d in self._holidays:
            return f"{format_date(d)} là ngày nghỉ ({self._holidays[d]})."
        return f"{format_date(d)} là ngày nghỉ cuối tuần."

    def ensure_school_day(self, d: date) -> None:
        if not self.is_school_day(d):
            raise ValidationError(self.reason_not_school_day(d) + " Không phải ngày đi học.")

    def school_days(self, month: int, year: int, until: date | None = None) -> list[date]:
        return [d for d in month_dates(month, year) if self.is_school_day(d) and (until is None or d <= until)]

    def week_days(self, any_date: date) -> list[date]:
        """Các ngày hiển thị trong một tuần (Thứ 2 - Thứ 6, thêm Thứ 7 nếu trường học Thứ 7)."""
        start = monday_of(any_date)
        return [start + timedelta(days=i) for i in range(6 if self.saturday_classes else 5)]

    # ------------------------------------------------------------------ lưu trữ
    def to_dict(self) -> dict[str, Any]:
        return {"saturday_classes": self.saturday_classes,
                "holidays": {d.isoformat(): name for d, name in sorted(self._holidays.items())}}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SchoolCalendar":
        data = data or {}
        return cls(data.get("holidays", {}), parse_bool(data.get("saturday_classes", False)))
