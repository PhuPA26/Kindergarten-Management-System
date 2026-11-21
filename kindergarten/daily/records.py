"""Vận hành hằng ngày: nhật ký ăn - ngủ - sinh hoạt của trẻ (DailyLog) và trao đổi giáo viên - phụ huynh (Message)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from ..core.base_model import BaseModel
from ..exceptions import ValidationError
from ..utils import format_date, normalize_spaces, normalize_text, parse_date, parse_optional_date, require_text

MEALS = ("Bữa sáng", "Bữa trưa", "Bữa xế")
MEAL_LEVELS = ("Ăn hết", "Ăn khá", "Ăn ít", "Không ăn")
NAP_LEVELS = ("Ngủ ngon", "Ngủ ít", "Không ngủ")
MOODS = ("Vui vẻ", "Bình thường", "Mệt / quấy")


def _now() -> str:
    return datetime.now().isoformat(timespec="minutes")


def _choice(value: Any, options: tuple[str, ...], label: str) -> str:
    text = normalize_text(value)
    for option in options:
        if text == normalize_text(option):
            return option
    if not text:
        return ""
    raise ValidationError(f"{label} '{value}' không hợp lệ ({' / '.join(options)}).")


class DailyLog(BaseModel):
    """Bước 3 - giáo viên cập nhật ăn, ngủ, sinh hoạt của một trẻ trong ngày; gửi cho phụ huynh của trẻ đó."""

    PREFIX = "NK"

    def __init__(self, child_id: str, class_id: str, on_date: Any, meals: dict[str, str] | None = None,
                 nap: str = "", nap_minutes: Any = 0, mood: str = "", activities: str = "", health_note: str = "",
                 teacher_note: str = "", updated_by: str = "", updated_at: str = "", sent_at: str = "",
                 parent_seen_at: str = "", parent_reply: str = "", parent_reply_at: str = "",
                 id: str | None = None) -> None:
        super().__init__(id)
        self.child_id = require_text(child_id, "Mã trẻ").upper()
        self.class_id = require_text(class_id, "Mã lớp").upper()
        self.date = parse_date(on_date, "Ngày")
        self.meals = meals or {}
        self.nap = nap
        self.nap_minutes = nap_minutes
        self.mood = mood
        self.activities = activities
        self.health_note = health_note
        self.teacher_note = teacher_note
        self.updated_by = normalize_spaces(updated_by)
        self.updated_at = normalize_spaces(updated_at)
        self.sent_at = normalize_spaces(sent_at)
        self.parent_seen_at = normalize_spaces(parent_seen_at)
        self.parent_reply = parent_reply
        self.parent_reply_at = normalize_spaces(parent_reply_at)

    # ------------------------------------------------------------------ thuộc tính có kiểm tra
    @property
    def meals(self) -> dict[str, str]:
        return dict(self._meals)

    @meals.setter
    def meals(self, value: dict[str, Any]) -> None:
        result = {}
        for meal, level in dict(value or {}).items():
            name = _choice(meal, MEALS, "Bữa ăn")
            level = _choice(level, MEAL_LEVELS, f"Mức ăn {name}")
            if name and level:
                result[name] = level
        self._meals = result

    @property
    def nap(self) -> str:
        return self._nap

    @nap.setter
    def nap(self, value: Any) -> None:
        self._nap = _choice(value, NAP_LEVELS, "Giấc ngủ")

    @property
    def nap_minutes(self) -> int:
        return self._nap_minutes

    @nap_minutes.setter
    def nap_minutes(self, value: Any) -> None:
        text = str(value or "0").strip()
        if not text.isdigit() or int(text) > 240:
            raise ValidationError("Thời gian ngủ (phút) phải là số từ 0 đến 240.")
        self._nap_minutes = int(text)

    @property
    def mood(self) -> str:
        return self._mood

    @mood.setter
    def mood(self, value: Any) -> None:
        self._mood = _choice(value, MOODS, "Tâm trạng")

    @property
    def activities(self) -> str:
        return self._activities

    @activities.setter
    def activities(self, value: Any) -> None:
        self._activities = normalize_spaces(value)[:300]

    @property
    def health_note(self) -> str:
        return self._health_note

    @health_note.setter
    def health_note(self, value: Any) -> None:
        self._health_note = normalize_spaces(value)[:300]

    @property
    def teacher_note(self) -> str:
        return self._teacher_note

    @teacher_note.setter
    def teacher_note(self, value: Any) -> None:
        self._teacher_note = normalize_spaces(value)[:500]

    @property
    def parent_reply(self) -> str:
        return self._parent_reply

    @parent_reply.setter
    def parent_reply(self, value: Any) -> None:
        self._parent_reply = normalize_spaces(value)[:500]

    # ------------------------------------------------------------------ trạng thái
    @property
    def is_sent(self) -> bool:
        return bool(self.sent_at)

    @property
    def is_complete(self) -> bool:
        """Đã cập nhật đủ bữa trưa và giấc ngủ (hai mục chính của bước 3)."""
        return "Bữa trưa" in self._meals and bool(self._nap)

    def meals_text(self) -> str:
        return ", ".join(f"{m.replace('Bữa ', '')}: {lv.lower()}" for m, lv in self._meals.items()) or "-"

    def nap_text(self) -> str:
        if not self._nap:
            return "-"
        return self._nap + (f" ({self._nap_minutes} phút)" if self._nap_minutes else "")

    def summary_text(self) -> str:
        lines = [f"Ngày {format_date(self.date)}",
                 f"  Ăn uống : {self.meals_text()}",
                 f"  Giấc ngủ: {self.nap_text()}",
                 f"  Tâm trạng: {self.mood or '-'}"]
        if self.activities:
            lines.append(f"  Hoạt động: {self.activities}")
        if self.health_note:
            lines.append(f"  Sức khỏe: {self.health_note}")
        if self.teacher_note:
            lines.append(f"  Lời nhắn của cô: {self.teacher_note}")
        if self.parent_reply:
            lines.append(f"  Phụ huynh phản hồi: {self.parent_reply}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(child_id=self.child_id, class_id=self.class_id, date=self.date.isoformat(), meals=self.meals,
                    nap=self.nap, nap_minutes=self.nap_minutes, mood=self.mood, activities=self.activities,
                    health_note=self.health_note, teacher_note=self.teacher_note, updated_by=self.updated_by,
                    updated_at=self.updated_at, sent_at=self.sent_at, parent_seen_at=self.parent_seen_at,
                    parent_reply=self.parent_reply, parent_reply_at=self.parent_reply_at)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyLog":
        keys = ("meals", "nap", "nap_minutes", "mood", "activities", "health_note", "teacher_note", "updated_by",
                "updated_at", "sent_at", "parent_seen_at", "parent_reply", "parent_reply_at")
        return cls(data["child_id"], data["class_id"], data["date"], id=data["id"],
                   **{k: data[k] for k in keys if k in data})


class MessageKind(Enum):
    NOTE = "Lời nhắn"
    MEDICINE = "Dặn uống thuốc"
    LEAVE = "Xin nghỉ"
    ANNOUNCEMENT = "Thông báo"

    @classmethod
    def parse(cls, value: Any) -> "MessageKind":
        if isinstance(value, cls):
            return value
        text = normalize_text(value)
        for item in cls:
            if text in (normalize_text(item.value), item.name.lower()):
                return item
        aliases = {"thuoc": cls.MEDICINE, "dan thuoc": cls.MEDICINE, "nghi": cls.LEAVE, "nhan": cls.NOTE}
        if text in aliases:
            return aliases[text]
        raise ValidationError(f"Loại tin '{value}' không hợp lệ.")


class MessageStatus(Enum):
    NEW = "Mới"
    SEEN = "Đã xem"
    DONE = "Đã thực hiện"
    DECLINED = "Từ chối"


class Message(BaseModel):
    """Bước 4 - trao đổi hai chiều: phụ huynh nhắn/dặn thuốc/xin nghỉ; giáo viên trả lời, thông báo cho lớp."""

    PREFIX = "TN"

    def __init__(self, kind: Any, content: str, sender: str, sender_role: str, child_id: str | None = None,
                 class_id: str | None = None, for_date: Any = None, medicine: str = "", dosage: str = "",
                 time_text: str = "", to_date: Any = None, status: Any = MessageStatus.NEW, reply: str = "",
                 replied_by: str = "", replied_at: str = "", created_at: str = "", done_at: str = "",
                 leave_request_id: str = "", id: str | None = None) -> None:
        super().__init__(id)
        self.kind = MessageKind.parse(kind)
        self.content = normalize_spaces(content)[:1000]
        self.sender = normalize_spaces(sender)
        self.sender_role = normalize_spaces(sender_role)
        self.child_id = normalize_spaces(child_id).upper() or None if child_id else None
        self.class_id = normalize_spaces(class_id).upper() or None if class_id else None
        self.for_date = parse_date(for_date, "Ngày") if for_date else date.today()
        self.to_date = parse_optional_date(to_date, "Đến ngày")
        self.medicine = normalize_spaces(medicine)[:120]
        self.dosage = normalize_spaces(dosage)[:120]
        self.time_text = normalize_spaces(time_text)[:60]
        self.status = status if isinstance(status, MessageStatus) else MessageStatus(status)
        self.reply = normalize_spaces(reply)[:1000]
        self.replied_by = normalize_spaces(replied_by)
        self.replied_at = normalize_spaces(replied_at)
        self.created_at = created_at or _now()
        self.done_at = normalize_spaces(done_at)
        self.leave_request_id = normalize_spaces(leave_request_id)
        self.validate()

    def validate(self) -> None:
        if self.kind is MessageKind.MEDICINE and not self.medicine:
            raise ValidationError("Dặn uống thuốc phải ghi tên thuốc.")
        if self.kind is MessageKind.ANNOUNCEMENT:
            if not self.class_id:
                raise ValidationError("Thông báo phải gửi cho một lớp.")
        elif not self.child_id:
            raise ValidationError("Tin nhắn phải gắn với một trẻ.")
        if not self.content and self.kind is not MessageKind.MEDICINE:
            raise ValidationError("Nội dung không được để trống.")
        if self.to_date is not None and self.to_date < self.for_date:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")

    @property
    def from_parent(self) -> bool:
        return self.sender_role == "Phụ huynh"

    @property
    def needs_action(self) -> bool:
        """Tin phụ huynh gửi mà giáo viên chưa xử lý xong."""
        return self.from_parent and self.status in (MessageStatus.NEW, MessageStatus.SEEN)

    @property
    def period_text(self) -> str:
        if self.to_date and self.to_date != self.for_date:
            return f"{format_date(self.for_date)} - {format_date(self.to_date)}"
        return format_date(self.for_date)

    def detail_text(self) -> str:
        parts = [f"[{self.kind.value}] {self.period_text}"]
        if self.kind is MessageKind.MEDICINE:
            parts.append(f"Thuốc: {self.medicine}" + (f" - liều: {self.dosage}" if self.dosage else "")
                         + (f" - giờ uống: {self.time_text}" if self.time_text else ""))
        if self.content:
            parts.append(self.content)
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(kind=self.kind.name, content=self.content, sender=self.sender, sender_role=self.sender_role,
                    child_id=self.child_id, class_id=self.class_id, for_date=self.for_date.isoformat(),
                    to_date=self.to_date.isoformat() if self.to_date else None, medicine=self.medicine,
                    dosage=self.dosage, time_text=self.time_text, status=self.status.value, reply=self.reply,
                    replied_by=self.replied_by, replied_at=self.replied_at, created_at=self.created_at,
                    done_at=self.done_at, leave_request_id=self.leave_request_id)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(MessageKind[data["kind"]], data.get("content", ""), data.get("sender", ""),
                   data.get("sender_role", ""), data.get("child_id"), data.get("class_id"), data.get("for_date"),
                   data.get("medicine", ""), data.get("dosage", ""), data.get("time_text", ""), data.get("to_date"),
                   data.get("status", MessageStatus.NEW.value), data.get("reply", ""), data.get("replied_by", ""),
                   data.get("replied_at", ""), data.get("created_at", ""), data.get("done_at", ""),
                   data.get("leave_request_id", ""), id=data["id"])


class LeaveStatus(Enum):
    """Trạng thái một đơn xin nghỉ nhìn từ phía phụ huynh / giáo viên."""
    PENDING = "Chờ cô duyệt"
    APPROVED = "Đã duyệt"
    DECLINED = "Từ chối"
    CANCELLED = "Đã hủy"


@dataclass(frozen=True)
class LeaveApplication:
    """Một đơn xin nghỉ (chỉ để hiển thị) - gộp hai nguồn:
    - phụ huynh tự tạo trên ứng dụng (Message loại 'Xin nghỉ'): chờ cô duyệt -> duyệt thành đơn nghỉ có phép, hoặc
      bị từ chối kèm lý do;
    - giáo viên ghi giúp khi phụ huynh báo qua điện thoại (LeaveRequest không gắn tin nhắn nào): có hiệu lực ngay."""

    SOURCE_PARENT = "Phụ huynh gửi"
    SOURCE_TEACHER = "Cô ghi giúp (PH báo qua điện thoại)"

    id: str                       # mã tin nhắn (TN...) nếu phụ huynh gửi, mã đơn (DN...) nếu cô ghi giúp
    child_id: str
    class_id: str | None
    from_date: date
    to_date: date
    reason: str
    created_by: str
    source: str
    status: LeaveStatus
    teacher_note: str
    created_at: str
    school_days: int
    leave_request_id: str = ""    # đơn nghỉ có phép đã tạo (khi đã duyệt)

    @property
    def period_text(self) -> str:
        if self.from_date == self.to_date:
            return format_date(self.from_date)
        return f"{format_date(self.from_date)} - {format_date(self.to_date)}"

    @property
    def created_text(self) -> str:
        """'2026-11-21T14:05' -> '21/11 14:05'."""
        stamp = self.created_at
        return f"{stamp[8:10]}/{stamp[5:7]} {stamp[11:16]}" if len(stamp) >= 16 else stamp

    @property
    def can_withdraw(self) -> bool:
        """Phụ huynh chỉ rút được đơn mình gửi mà cô chưa xử lý."""
        return self.source == self.SOURCE_PARENT and self.status is LeaveStatus.PENDING
