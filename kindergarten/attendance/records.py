"""T19 - AttendanceStatus (Enum), AttendanceRecord; kèm LeaveRequest (đơn xin nghỉ)."""
from __future__ import annotations

import sys
from datetime import date, datetime
from enum import Enum
from typing import Any

from ..core.base_model import BaseModel
from ..exceptions import ValidationError
from ..utils import format_date, normalize_spaces, normalize_text, parse_date, require_text


class AttendanceStatus(Enum):
    PRESENT = "Có mặt"
    EXCUSED = "Nghỉ có phép"
    UNEXCUSED = "Nghỉ không phép"

    @property
    def short(self) -> str:
        """Ký hiệu trong sổ điểm danh: C = có mặt, P = có phép, K = không phép."""
        return {"PRESENT": "C", "EXCUSED": "P", "UNEXCUSED": "K"}[self.name]

    @classmethod
    def parse(cls, value: Any) -> "AttendanceStatus":
        if isinstance(value, cls):
            return value
        text = normalize_text(value)
        aliases = {"c": cls.PRESENT, "1": cls.PRESENT, "co mat": cls.PRESENT, "present": cls.PRESENT,
                   "p": cls.EXCUSED, "2": cls.EXCUSED, "nghi co phep": cls.EXCUSED, "co phep": cls.EXCUSED,
                   "excused": cls.EXCUSED,
                   "k": cls.UNEXCUSED, "3": cls.UNEXCUSED, "nghi khong phep": cls.UNEXCUSED,
                   "khong phep": cls.UNEXCUSED, "unexcused": cls.UNEXCUSED}
        if text in aliases:
            return aliases[text]
        raise ValidationError(f"Trạng thái điểm danh '{value}' không hợp lệ (C/P/K).")


class AttendanceRecord(BaseModel):
    """Kết quả điểm danh một trẻ trong một ngày."""

    PREFIX = "DD"

    def __init__(self, child_id: str, class_id: str, on_date: Any, status: Any = AttendanceStatus.PRESENT,
                 note: str = "", picked_up_by: str = "", picked_up_at: str = "", released_by: str = "",
                 arrived_at: str = "", brought_by: str = "", received_by: str = "", id: str | None = None) -> None:
        super().__init__(id)
        # P06: mọi bản ghi của cùng một trẻ dùng chung một đối tượng chuỗi mã
        self._child_id = sys.intern(require_text(child_id, "Mã trẻ").upper())
        self._class_id = sys.intern(require_text(class_id, "Mã lớp").upper())
        self._date = parse_date(on_date, "Ngày điểm danh")
        self.status = status
        self.note = note
        self.picked_up_by = picked_up_by
        self.picked_up_at = normalize_spaces(picked_up_at)   # L06: thời điểm giao trẻ
        self.released_by = normalize_spaces(released_by)     # L06: người xác nhận giao trẻ
        # Bước 1 vận hành hằng ngày - đón trẻ đầu ngày: giờ đến, người đưa, người nhận trẻ
        self.arrived_at = normalize_spaces(arrived_at)
        self.brought_by = normalize_spaces(brought_by)
        self.received_by = normalize_spaces(received_by)

    @property
    def child_id(self) -> str:
        return self._child_id

    @property
    def class_id(self) -> str:
        return self._class_id

    @property
    def date(self) -> date:
        return self._date

    @property
    def status(self) -> AttendanceStatus:
        return self._status

    @status.setter
    def status(self, value: Any) -> None:
        self._status = AttendanceStatus.parse(value)
        if self._status is not AttendanceStatus.PRESENT:   # L06: không còn có mặt thì không thể có người đón
            self._picked_up_by = ""
            self.picked_up_at = ""
            self.released_by = ""
            self.arrived_at = ""
            self.brought_by = ""
            self.received_by = ""

    @property
    def note(self) -> str:
        return self._note

    @note.setter
    def note(self, value: Any) -> None:
        self._note = normalize_spaces(value)

    @property
    def picked_up_by(self) -> str:
        return self._picked_up_by

    @picked_up_by.setter
    def picked_up_by(self, value: Any) -> None:
        self._picked_up_by = normalize_spaces(value)

    @property
    def is_present(self) -> bool:
        return self._status is AttendanceStatus.PRESENT

    @property
    def checked_in(self) -> bool:
        """Đã đến trường = có mặt. Đón trẻ và điểm danh là MỘT trạng thái: đón -> có mặt; chưa đón -> vắng."""
        return self.is_present

    @property
    def picked_up(self) -> bool:
        return bool(self.picked_up_at)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(child_id=self.child_id, class_id=self.class_id, date=self.date.isoformat(),
                    status=self.status.name, note=self.note, picked_up_by=self.picked_up_by,
                    picked_up_at=self.picked_up_at, released_by=self.released_by, arrived_at=self.arrived_at,
                    brought_by=self.brought_by, received_by=self.received_by)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttendanceRecord":
        return cls(data["child_id"], data["class_id"], data["date"], AttendanceStatus[data["status"]],
                   data.get("note", ""), data.get("picked_up_by", ""), data.get("picked_up_at", ""),
                   data.get("released_by", ""), data.get("arrived_at", ""), data.get("brought_by", ""),
                   data.get("received_by", ""), id=data["id"])

    # P02: lưu gọn mỗi bản ghi thành một mảng (bỏ tên khóa lặp lại) - còn khoảng 1/5 dung lượng
    ROW_FIELDS = ("id", "child_id", "class_id", "date", "status", "note", "picked_up_by", "picked_up_at",
                  "released_by", "arrived_at", "brought_by", "received_by")

    def to_row(self) -> list[Any]:
        row = [self.id, self.child_id, self.class_id, self.date.isoformat(), self.status.short, self.note,
               self.picked_up_by, self.picked_up_at, self.released_by, self.arrived_at, self.brought_by,
               self.received_by]
        while row and row[-1] == "":
            row.pop()
        return row

    @classmethod
    def from_storage(cls, data: Any) -> "AttendanceRecord":
        """Đọc cả định dạng mới (mảng) và định dạng cũ (đối tượng JSON)."""
        if isinstance(data, dict):
            return cls.from_dict(data)
        values = list(data) + [""] * (len(cls.ROW_FIELDS) - len(data))
        rid, child_id, class_id, day, status, note, picked_by, picked_at, released, arrived, brought, received = \
            values[:12]
        return cls(child_id, class_id, day, AttendanceStatus.parse(status), note, picked_by, picked_at, released,
                   arrived, brought, received, id=rid)


class LeaveRequest(BaseModel):
    """Đơn xin nghỉ của phụ huynh: các ngày trong khoảng sẽ được tính là nghỉ có phép."""

    PREFIX = "DN"
    MAX_DAYS = 60

    def __init__(self, child_id: str, from_date: Any, to_date: Any, reason: str, submitted_by: str = "",
                 created_at: str | None = None, converted_dates: list[Any] | None = None,
                 id: str | None = None) -> None:
        super().__init__(id)
        # L26: các ngày đã chuyển "không phép" -> "có phép" nhờ đơn này, để hoàn nguyên khi hủy đơn
        self.converted_dates: list[date] = [parse_date(d) for d in converted_dates or []]
        self._child_id = require_text(child_id, "Mã trẻ").upper()
        start, end = parse_date(from_date, "Từ ngày"), parse_date(to_date, "Đến ngày")
        if end < start:
            raise ValidationError("'Đến ngày' phải sau hoặc bằng 'Từ ngày'.")
        if (end - start).days + 1 > self.MAX_DAYS:
            raise ValidationError(f"Một đơn xin nghỉ không quá {self.MAX_DAYS} ngày.")
        self._from_date, self._to_date = start, end
        self.reason = reason
        self.submitted_by = submitted_by
        self.created_at = created_at or datetime.now().isoformat(timespec="seconds")

    @property
    def child_id(self) -> str:
        return self._child_id

    @property
    def from_date(self) -> date:
        return self._from_date

    @property
    def to_date(self) -> date:
        return self._to_date

    @property
    def reason(self) -> str:
        return self._reason

    @reason.setter
    def reason(self, value: Any) -> None:
        self._reason = require_text(value, "Lý do nghỉ", 200)

    @property
    def submitted_by(self) -> str:
        return self._submitted_by

    @submitted_by.setter
    def submitted_by(self, value: Any) -> None:
        self._submitted_by = normalize_spaces(value)

    def covers(self, d: date) -> bool:
        return self.from_date <= d <= self.to_date

    def overlaps(self, other: "LeaveRequest") -> bool:
        return self.from_date <= other.to_date and other.from_date <= self.to_date

    @property
    def school_day_count(self) -> int:
        """Số ngày đi học (Thứ 2 - Thứ 6) nằm trong đơn."""
        days = range(self.from_date.toordinal(), self.to_date.toordinal() + 1)
        return sum(1 for o in days if date.fromordinal(o).weekday() < 5)

    @property
    def period_text(self) -> str:
        if self.from_date == self.to_date:
            return format_date(self.from_date)
        return f"{format_date(self.from_date)} - {format_date(self.to_date)}"

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(child_id=self.child_id, from_date=self.from_date.isoformat(),
                    to_date=self.to_date.isoformat(), reason=self.reason, submitted_by=self.submitted_by,
                    created_at=self.created_at, converted_dates=[d.isoformat() for d in self.converted_dates])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LeaveRequest":
        return cls(data["child_id"], data["from_date"], data["to_date"], data["reason"],
                   data.get("submitted_by", ""), data.get("created_at"), data.get("converted_dates", []),
                   id=data["id"])
