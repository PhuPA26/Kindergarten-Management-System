"""Sổ tiết dạy bộ môn - công việc riêng của GIÁO VIÊN BỘ MÔN (Âm nhạc, Tiếng Anh...).

GV chủ nhiệm lo chăm sóc cả ngày cho MỘT lớp (đón trả, điểm danh, ăn ngủ, sức khỏe, trao đổi phụ huynh).
GV bộ môn dạy theo tiết ở NHIỀU lớp theo thời khóa biểu, nên thay vào các việc trên là:
  - ghi sổ tiết dạy cho mỗi tiết đã dạy: nội dung bài, đánh giá chung cả lớp, ghi chú;
  - nhận xét từng trẻ theo môn học (trẻ nổi bật / cần hỗ trợ);
  - lập "Báo cáo chuyên môn bộ môn" theo tháng gửi Ban giám hiệu.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from ..auth.user import Role
from ..core.base_manager import BaseManager
from ..core.base_model import BaseModel
from ..exceptions import KindergartenError, PermissionDeniedError, ValidationError
from ..utils import format_date, normalize_spaces, normalize_text, parse_date, require_text

if TYPE_CHECKING:
    from ..classroom.timetable import TimeSlot
    from ..people.child import Child
    from ..system import KindergartenSystem

LESSON_RATINGS = ("Tốt", "Khá", "Trung bình", "Cần cố gắng")
CHILD_LEVELS = ("Nổi bật", "Đạt", "Cần hỗ trợ")


def _now() -> str:
    return datetime.now().isoformat(timespec="minutes")


def _choice(value: Any, options: tuple[str, ...], label: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    for option in options:
        if text == normalize_text(option):
            return option
    raise ValidationError(f"{label} '{value}' không hợp lệ ({' / '.join(options)}).")


class LessonLog(BaseModel):
    """Một tiết dạy bộ môn đã dạy ở một lớp trong một ngày."""

    PREFIX = "TD"

    def __init__(self, class_id: str, teacher_id: str, on_date: Any, subject: str, content: str,
                 rating: str = "", note: str = "", slot_id: str | None = None, time_text: str = "",
                 child_notes: dict[str, dict[str, str]] | None = None, created_by: str = "",
                 updated_at: str = "", id: str | None = None) -> None:
        super().__init__(id)
        self.class_id = require_text(class_id, "Mã lớp").upper()
        self.teacher_id = require_text(teacher_id, "Mã giáo viên").upper()
        self.date = parse_date(on_date, "Ngày dạy")
        self.subject = subject
        self.content = content
        self.rating = rating
        self.note = note
        self.slot_id = (normalize_spaces(slot_id).upper() or None) if slot_id else None
        self.time_text = normalize_spaces(time_text)[:20]
        self.child_notes = child_notes or {}
        self.created_by = normalize_spaces(created_by)
        self.updated_at = normalize_spaces(updated_at) or _now()

    # ------------------------------------------------------------------ thuộc tính có kiểm tra
    @property
    def subject(self) -> str:
        return self._subject

    @subject.setter
    def subject(self, value: Any) -> None:
        self._subject = require_text(value, "Môn học", 100)

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: Any) -> None:
        self._content = require_text(value, "Nội dung bài dạy", 500)

    @property
    def rating(self) -> str:
        return self._rating

    @rating.setter
    def rating(self, value: Any) -> None:
        self._rating = _choice(value, LESSON_RATINGS, "Đánh giá chung")

    @property
    def note(self) -> str:
        return self._note

    @note.setter
    def note(self, value: Any) -> None:
        self._note = normalize_spaces(value)[:500]

    @property
    def child_notes(self) -> dict[str, dict[str, str]]:
        """Mã trẻ -> {"level": mức (Nổi bật / Đạt / Cần hỗ trợ), "comment": nhận xét}."""
        return {k: dict(v) for k, v in self._child_notes.items()}

    @child_notes.setter
    def child_notes(self, value: dict[str, Any]) -> None:
        result: dict[str, dict[str, str]] = {}
        for child_id, item in dict(value or {}).items():
            if isinstance(item, str):
                item = {"level": "", "comment": item}
            level = _choice(item.get("level", ""), CHILD_LEVELS, "Mức đánh giá trẻ")
            comment = normalize_spaces(item.get("comment", ""))[:300]
            if level or comment:
                result[str(child_id).upper()] = {"level": level, "comment": comment}
        self._child_notes = result

    # ------------------------------------------------------------------ hiển thị
    def child_note_text(self, child_id: str) -> str:
        item = self._child_notes.get(str(child_id).upper())
        if not item:
            return ""
        return " - ".join(part for part in (item["level"], item["comment"]) if part)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(class_id=self.class_id, teacher_id=self.teacher_id, date=self.date.isoformat(),
                    subject=self.subject, content=self.content, rating=self.rating, note=self.note,
                    slot_id=self.slot_id, time_text=self.time_text, child_notes=self.child_notes,
                    created_by=self.created_by, updated_at=self.updated_at)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LessonLog":
        keys = ("rating", "note", "slot_id", "time_text", "child_notes", "created_by", "updated_at")
        return cls(data["class_id"], data["teacher_id"], data["date"], data["subject"], data["content"],
                   id=data["id"], **{k: data[k] for k in keys if k in data})


class LessonLogManager(BaseManager[LessonLog]):
    """Sổ tiết dạy: GV bộ môn chỉ ghi / sửa tiết của MÌNH ở lớp có trong thời khóa biểu của mình.
    Ban giám hiệu xem được toàn bộ (và ghi thay khi cần)."""

    entity_name = "tiết dạy"

    def __init__(self, system: "KindergartenSystem") -> None:
        super().__init__()
        self.system = system
        system.children.on_remove(self._on_child_removed)
        system.classes.on_remove(self._on_owner_removed("class_id"))
        system.employees.on_remove(self._on_owner_removed("teacher_id"))

    # ------------------------------------------------------------------ dữ liệu liên quan
    def _on_child_removed(self, child: "Child") -> None:
        for log in self:
            if child.id in log._child_notes:
                notes = log.child_notes
                notes.pop(child.id, None)
                log.child_notes = notes

    def _on_owner_removed(self, field: str):
        """Xóa lớp / xóa giáo viên -> bỏ luôn sổ tiết dạy liên quan (như ON DELETE CASCADE trong CSDL)."""
        def drop(owner: Any) -> None:
            for log in [x for x in self if getattr(x, field) == owner.id]:
                self._items.pop(self._key(log.id), None)
        return drop

    def _validate_new(self, log: LessonLog) -> None:
        self._validate(log)

    def _validate_update(self, log: LessonLog) -> None:
        self._validate(log)

    def _validate(self, log: LessonLog) -> None:
        if self.system.classes.get_or_none(log.class_id) is None:
            raise ValidationError(f"Không có lớp {log.class_id}.")
        if log.date > date.today():
            raise ValidationError("Chưa đến ngày dạy - không ghi sổ trước được.")
        duplicate = self.find_one(lambda x: x is not log and x.class_id == log.class_id and x.date == log.date
                                  and x.teacher_id == log.teacher_id
                                  and normalize_text(x.subject) == normalize_text(log.subject))
        if duplicate is not None:
            raise ValidationError(f"Đã ghi sổ tiết {log.subject} lớp {self.system.classes.class_name(log.class_id)} "
                                  f"ngày {format_date(log.date)} ({duplicate.id}) - hãy sửa tiết đó.")

    # ------------------------------------------------------------------ phạm vi
    @property
    def _user(self):
        return self.system.auth.current_user

    def _who(self) -> str:
        return self._user.full_name if self._user else "Hệ thống"

    def my_teacher_id(self) -> str | None:
        """Mã giáo viên của người đang đăng nhập (None = BGH / hệ thống: không giới hạn)."""
        user = self._user
        if user is None or user.role is not Role.TEACHER:
            return None
        teacher = self.system.teacher_of(user)
        if teacher is None:
            raise PermissionDeniedError("Tài khoản chưa gắn hồ sơ giáo viên.")
        return teacher.id

    def _check_owner(self, log: LessonLog) -> None:
        mine = self.my_teacher_id()
        if mine is not None and log.teacher_id != mine:
            raise PermissionDeniedError("Giáo viên chỉ sửa sổ tiết dạy của chính mình.")

    def taught_classes(self, teacher_id: str) -> list[Any]:
        ids = {slot.class_id for slot in self.system.timetable.find(teacher_id=teacher_id)}
        return [c for c in self.system.classes.all_sorted() if c.id in ids]

    def subjects_of(self, teacher_id: str) -> list[str]:
        """Môn giáo viên dạy (theo thời khóa biểu, bỏ các hoạt động của GV chủ nhiệm như đón trẻ)."""
        teacher = self.system.employees.get_or_none(teacher_id)
        names = {slot.activity for slot in self.system.timetable.find(teacher_id=teacher_id)}
        specialty = getattr(teacher, "specialty", "") if teacher is not None else ""
        if specialty:
            names.add(specialty)
        return sorted(names)

    def logs(self, teacher_id: str | None = None, class_id: str | None = None, month: int | None = None,
             year: int | None = None) -> list[LessonLog]:
        mine = self.my_teacher_id()
        teacher_id = mine or teacher_id
        result = [log for log in self
                  if (teacher_id is None or log.teacher_id == teacher_id)
                  and (class_id is None or log.class_id == class_id)
                  and (month is None or (log.date.month == month and log.date.year == year))]
        return sorted(result, key=lambda x: (x.date, x.time_text, x.class_id), reverse=True)

    # ------------------------------------------------------------------ lịch dạy trong ngày
    def schedule(self, on_date: Any = None, teacher_id: str | None = None) -> list[dict[str, Any]]:
        """Các tiết theo thời khóa biểu của giáo viên trong ngày + tiết đó đã ghi sổ chưa."""
        d = parse_date(on_date) if on_date else date.today()
        teacher_id = self.my_teacher_id() or teacher_id
        if teacher_id is None or not self.system.calendar.is_school_day(d):
            return []
        slots = sorted((s for s in self.system.timetable.find(teacher_id=teacher_id) if s.weekday == d.weekday()),
                       key=lambda s: (s.start, s.class_id))
        rows = []
        for slot in slots:
            log = self.find_one(lambda x: x.class_id == slot.class_id and x.date == d and x.teacher_id == teacher_id
                                and normalize_text(x.subject) == normalize_text(slot.activity))
            rows.append({"slot": slot, "log": log})
        return rows

    # ------------------------------------------------------------------ ghi sổ
    def save_lesson(self, class_id: str, on_date: Any, subject: str, content: str, rating: str = "",
                    note: str = "", teacher_id: str | None = None, slot: "TimeSlot | None" = None,
                    log_id: str | None = None) -> LessonLog:
        """Thêm mới (log_id=None) hoặc sửa một tiết đã ghi."""
        teacher_id = self.my_teacher_id() or (teacher_id or "").upper()
        if not teacher_id:
            raise ValidationError("Hãy chọn giáo viên dạy tiết này.")
        class_id = require_text(class_id, "Lớp").upper()
        if class_id not in {c.id for c in self.taught_classes(teacher_id)}:
            raise PermissionDeniedError(f"Giáo viên không có tiết dạy ở lớp {self.system.classes.class_name(class_id)} "
                                        "trong thời khóa biểu.")
        if log_id:
            log = self.get(log_id)
            self._check_owner(log)
            log = self.update(log.id, class_id=class_id, date=parse_date(on_date, "Ngày dạy"), subject=subject,
                              content=content, rating=rating, note=note)
        else:
            log = self.add(LessonLog(class_id, teacher_id, on_date, subject, content, rating, note,
                                     slot.id if slot else None, slot.time_range if slot else "",
                                     created_by=self._who()))
        log.updated_at = _now()
        self.system.audit("Ghi sổ tiết dạy", f"{log.subject} - {self.system.classes.class_name(log.class_id)}",
                          {"lesson": log.id, "date": log.date.isoformat()})
        return log

    def set_child_note(self, log_id: str, child_id: str, level: str = "", comment: str = "") -> LessonLog:
        """Nhận xét một trẻ trong tiết học (để trống cả hai = xóa nhận xét)."""
        self._authorize()
        log = self.get(log_id)
        self._check_owner(log)
        child = self.system.children.get(child_id)
        if child.class_id != log.class_id:
            raise ValidationError(f"{child.full_name} không thuộc lớp {self.system.classes.class_name(log.class_id)}.")
        notes = log.child_notes
        notes[child.id] = {"level": level, "comment": comment}
        log.child_notes = notes
        log.updated_at = _now()
        return log

    def delete_lesson(self, log_id: str) -> LessonLog:
        log = self.get(log_id)
        self._check_owner(log)
        return self.remove(log.id)

    # ------------------------------------------------------------------ tổng hợp
    def month_summary(self, month: int, year: int, teacher_id: str | None = None,
                      class_id: str | None = None) -> list[dict[str, Any]]:
        """Theo (giáo viên, lớp, môn): số tiết theo TKB trong tháng, số tiết đã ghi sổ, số trẻ được nhận xét."""
        teacher_id = self.my_teacher_id() or teacher_id
        calendar = self.system.calendar
        first = date(year, month, 1)
        days = [date.fromordinal(first.toordinal() + i) for i in range(31)]
        days = [d for d in days if d.month == month and d <= date.today() and calendar.is_school_day(d)]
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for slot in self.system.timetable:
            if slot.teacher_id is None or (teacher_id and slot.teacher_id != teacher_id):
                continue
            if class_id and slot.class_id != class_id:
                continue
            if self.system.teacher_duty_for_employee(slot.teacher_id) != "bo_mon":
                continue
            key = (slot.teacher_id, slot.class_id, slot.activity)
            row = groups.setdefault(key, {"planned": 0, "logged": 0, "children": set(), "need_help": set()})
            row["planned"] += sum(1 for d in days if d.weekday() == slot.weekday)
        for log in self:
            if log.date.month != month or log.date.year != year:
                continue
            if (teacher_id and log.teacher_id != teacher_id) or (class_id and log.class_id != class_id):
                continue
            key = (log.teacher_id, log.class_id, log.subject)
            row = groups.setdefault(key, {"planned": 0, "logged": 0, "children": set(), "need_help": set()})
            row["logged"] += 1
            row["children"].update(log._child_notes)
            row["need_help"].update(k for k, v in log._child_notes.items() if v["level"] == "Cần hỗ trợ")
        result = []
        for (t_id, c_id, subject), row in sorted(groups.items()):
            teacher = self.system.employees.get_or_none(t_id)
            result.append({"teacher_id": t_id, "teacher": teacher.full_name if teacher else t_id, "class_id": c_id,
                           "class_name": self.system.classes.class_name(c_id), "subject": subject,
                           "planned": row["planned"], "logged": row["logged"], "commented": len(row["children"]),
                           "need_help": len(row["need_help"])})
        return result
