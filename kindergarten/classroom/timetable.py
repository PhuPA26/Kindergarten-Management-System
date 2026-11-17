"""T18 - TimeSlot, Timetable: lập thời khóa biểu tuần, báo lỗi khi giáo viên hoặc lớp bị trùng tiết."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any

from ..core.base_manager import BaseManager
from ..core.base_model import BaseModel
from ..core.person import Employee
from ..exceptions import ScheduleConflictError, ValidationError
from ..hr.employee_manager import EmployeeManager
from ..utils import WEEKDAY_NAMES, format_table, format_time, normalize_spaces, parse_time, parse_weekday, require_text
from .class_manager import ClassManager
from .classroom import Classroom


class TimeSlot(BaseModel):
    """Một tiết/hoạt động trong tuần của một lớp."""

    PREFIX = "TS"
    MAX_MINUTES = 240

    def __init__(self, class_id: str, weekday: Any, start: Any, end: Any, activity: str,
                 teacher_id: str | None = None, id: str | None = None) -> None:
        super().__init__(id)
        self.class_id = class_id
        self.weekday = weekday
        self.start = start
        self.end = end
        self.activity = activity
        self.teacher_id = teacher_id
        self.validate()

    @property
    def class_id(self) -> str:
        return self._class_id

    @class_id.setter
    def class_id(self, value: Any) -> None:
        self._class_id = require_text(value, "Mã lớp").upper()

    @property
    def weekday(self) -> int:
        return self._weekday

    @weekday.setter
    def weekday(self, value: Any) -> None:
        day = parse_weekday(value)
        if day > 5:
            raise ValidationError("Trường không xếp tiết vào Chủ nhật.")
        self._weekday = day

    @property
    def start(self) -> time:
        return self._start

    @start.setter
    def start(self, value: Any) -> None:
        self._start = parse_time(value, "Giờ bắt đầu")

    @property
    def end(self) -> time:
        return self._end

    @end.setter
    def end(self, value: Any) -> None:
        self._end = parse_time(value, "Giờ kết thúc")

    @property
    def activity(self) -> str:
        return self._activity

    @activity.setter
    def activity(self, value: Any) -> None:
        self._activity = require_text(value, "Nội dung hoạt động", 80)

    @property
    def teacher_id(self) -> str | None:
        return self._teacher_id

    @teacher_id.setter
    def teacher_id(self, value: Any) -> None:
        text = normalize_spaces(value).upper() if value else ""
        self._teacher_id = text or None

    @property
    def duration_minutes(self) -> int:
        start = datetime.combine(datetime.min, self.start)
        end = datetime.combine(datetime.min, self.end)
        return int((end - start).total_seconds() // 60)

    @property
    def time_range(self) -> str:
        return f"{format_time(self.start)}-{format_time(self.end)}"

    @property
    def time_label(self) -> str:
        return f"{WEEKDAY_NAMES[self.weekday]} {self.time_range}"

    def validate(self) -> None:
        if self.end <= self.start:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")
        if self.duration_minutes > self.MAX_MINUTES:
            raise ValidationError(f"Một hoạt động không kéo dài quá {self.MAX_MINUTES} phút.")

    def overlaps(self, other: "TimeSlot") -> bool:
        return self.weekday == other.weekday and self.start < other.end and other.start < self.end

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(class_id=self.class_id, weekday=self.weekday, start=format_time(self.start),
                    end=format_time(self.end), activity=self.activity, teacher_id=self.teacher_id)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeSlot":
        return cls(data["class_id"], int(data["weekday"]), data["start"], data["end"], data["activity"],
                   data.get("teacher_id"), id=data["id"])


class Timetable(BaseManager[TimeSlot]):
    """Thời khóa biểu tuần của toàn trường (để phát hiện trùng tiết giữa các lớp)."""

    entity_name = "tiết học"

    def __init__(self, class_manager: ClassManager, employee_manager: EmployeeManager) -> None:
        super().__init__()
        self.classes = class_manager
        self.employees = employee_manager
        class_manager.on_remove(self._on_class_removed)
        employee_manager.on_remove(self._on_employee_removed)

    # ------------------------------------------------------------------ kiểm tra trùng tiết
    def _validate_new(self, slot: TimeSlot) -> None:
        self._validate(slot)

    def _validate_update(self, slot: TimeSlot) -> None:
        self._validate(slot)

    def _validate(self, slot: TimeSlot) -> None:
        slot.validate()
        self.classes.get(slot.class_id)
        if slot.teacher_id:
            self.employees.get_teacher(slot.teacher_id)
        conflicts = self.find_conflicts(slot)
        if conflicts:
            raise ScheduleConflictError("Trùng tiết: " + " ".join(conflicts))

    def find_conflicts(self, slot: TimeSlot) -> list[str]:
        """Danh sách mô tả các tiết bị trùng với `slot` (cùng lớp hoặc cùng giáo viên)."""
        messages = []
        for other in self:
            if other is slot or not slot.overlaps(other):
                continue
            if other.class_id == slot.class_id:
                messages.append(f"Lớp {self.classes.class_name(slot.class_id)} đã có "
                                f"'{other.activity}' vào {other.time_label}.")
            if slot.teacher_id and other.teacher_id == slot.teacher_id:
                teacher = self.employees.get_or_none(slot.teacher_id)
                messages.append(f"Giáo viên {teacher.full_name if teacher else slot.teacher_id} đã dạy lớp "
                                f"{self.classes.class_name(other.class_id)} ('{other.activity}') "
                                f"vào {other.time_label}.")
        return messages

    def _on_class_removed(self, classroom: Classroom) -> None:
        for slot in self.find(class_id=classroom.id):
            self.remove(slot.id)

    def _on_employee_removed(self, employee: Employee) -> None:
        for slot in self.find(teacher_id=employee.id):
            slot.teacher_id = None

    # ------------------------------------------------------------------ lập và xem TKB
    def add_slot(self, class_id: str, weekday: Any, start: Any, end: Any, activity: str,
                 teacher_id: str | None = None) -> TimeSlot:
        return self.add(TimeSlot(class_id, weekday, start, end, activity, teacher_id))

    @staticmethod
    def _ordered(slots: list[TimeSlot]) -> list[TimeSlot]:
        return sorted(slots, key=lambda s: (s.weekday, s.start, s.end))

    def of_class(self, class_id: str) -> list[TimeSlot]:
        return self._ordered(self.find(class_id=self.classes.get(class_id).id))

    def of_teacher(self, teacher_id: str) -> list[TimeSlot]:
        return self._ordered(self.find(teacher_id=self.employees.get(teacher_id).id))

    def weekly_grid(self, class_id: str | None = None, teacher_id: str | None = None
                    ) -> tuple[list[str], list[list[str]]]:
        """Lưới TKB: hàng = khung giờ, cột = thứ trong tuần."""
        slots = self.of_class(class_id) if class_id else self.of_teacher(teacher_id or "")
        days = 6 if any(s.weekday == 5 for s in slots) else 5
        headers = ["Giờ"] + list(WEEKDAY_NAMES[:days])
        ranges = sorted({(s.start, s.end) for s in slots})
        rows = []
        for start, end in ranges:
            row = [f"{format_time(start)}-{format_time(end)}"]
            for day in range(days):
                cell = [s for s in slots if s.weekday == day and s.start == start and s.end == end]
                texts = []
                for s in cell:
                    if class_id:
                        teacher = self.employees.get_or_none(s.teacher_id) if s.teacher_id else None
                        texts.append(s.activity + (f" ({teacher.given_name})" if teacher else ""))
                    else:
                        texts.append(f"{s.activity} - {self.classes.class_name(s.class_id)}")
                row.append("; ".join(texts))
            rows.append(row)
        return headers, rows

    def weekly_text(self, class_id: str | None = None, teacher_id: str | None = None) -> str:
        if class_id:
            title = f"THỜI KHÓA BIỂU LỚP {self.classes.get(class_id).name.upper()}"
        else:
            title = f"LỊCH DẠY CỦA GIÁO VIÊN {self.employees.get(teacher_id).full_name.upper()}"
        headers, rows = self.weekly_grid(class_id, teacher_id)
        return format_table(headers, rows, title=title, max_width=30)
