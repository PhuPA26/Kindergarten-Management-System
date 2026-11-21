"""Attendance data needed to calculate and review a billing period."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol


class BillingAttendance(Protocol):
    @property
    def child_id(self) -> str: ...

    @property
    def class_id(self) -> str | None: ...

    @property
    def date(self) -> date: ...


class BillingCalendar(Protocol):
    def school_days(self, month: int, year: int, until: date | None = None) -> Sequence[date]: ...


class AttendanceReader(Protocol):
    @property
    def calendar(self) -> BillingCalendar: ...

    def records_in_month(self, month: int, year: int, child_id: str | None = None) -> Sequence[BillingAttendance]: ...

    def present_days_map(self, month: int, year: int) -> Mapping[str, int]: ...

    def present_days(self, child_id: str, month: int, year: int) -> int: ...
