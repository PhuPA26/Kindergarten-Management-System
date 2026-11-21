"""Vận hành hằng ngày của trường theo 6 bước:

1. Đón trẻ (07:00-08:00)        phụ huynh đưa bé tới lớp, trường nắm sĩ số đầu ngày
2. Điểm danh (08:00-08:30)      chốt có mặt / vắng có phép / vắng không phép
3. Cập nhật ăn ngủ (10:30-14:00) giáo viên ghi ăn, ngủ, sinh hoạt của từng trẻ và gửi cho phụ huynh của trẻ đó
4. Tương tác phụ huynh (14:00-15:00) lời nhắn, dặn thuốc, xin nghỉ, thông báo - hai chiều
5. Trả trẻ (16:00-17:00)        phụ huynh đón con, trường ghi nhận người đón, giờ đón
6. Báo cáo cuối ngày (17:00-17:30) Ban giám hiệu nắm tình hình trong ngày, không cần tổng hợp thủ công
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any, Callable

from ..attendance.records import AttendanceStatus, LeaveRequest
from ..auth.user import Permission
from ..core.base_manager import BaseManager
from ..exceptions import KindergartenError, PermissionDeniedError, ValidationError
from ..people.child import Child
from ..utils import format_date, normalize_spaces, parse_date, validate_not_future
from .records import MEALS, DailyLog, LeaveApplication, LeaveStatus, Message, MessageKind, MessageStatus

if TYPE_CHECKING:
    from ..system import KindergartenSystem


@dataclass(frozen=True)
class DailyStep:
    number: int
    key: str
    title: str
    start: time
    end: time
    description: str

    @property
    def time_text(self) -> str:
        return f"{self.start:%H:%M} - {self.end:%H:%M}"

    def phase(self, now: datetime | None = None) -> str:
        """'Sắp tới' / 'Đang diễn ra' / 'Đã qua' theo giờ hiện tại."""
        current = (now or datetime.now()).time()
        if current < self.start:
            return "Sắp tới"
        if current <= self.end:
            return "Đang diễn ra"
        return "Đã qua"


DAILY_STEPS: tuple[DailyStep, ...] = (
    DailyStep(1, "checkin", "Đón trẻ", time(7, 0), time(8, 0),
              "Phụ huynh đưa bé tới lớp, nhà trường nắm sĩ số đầu ngày."),
    DailyStep(2, "attendance", "Điểm danh", time(8, 0), time(8, 30),
              "Chốt điểm danh: có mặt, nghỉ có phép, nghỉ không phép."),
    DailyStep(3, "dailylog", "Cập nhật ăn ngủ", time(10, 30), time(14, 0),
              "Giáo viên cập nhật ăn, ngủ, sinh hoạt của trẻ và gửi cho phụ huynh."),
    DailyStep(4, "contact", "Tương tác phụ huynh", time(14, 0), time(15, 0),
              "Lời nhắn, dặn thuốc, xin nghỉ, thông báo - trao đổi hai chiều."),
    DailyStep(5, "pickup", "Trả trẻ", time(16, 0), time(17, 0),
              "Phụ huynh đón con, nhà trường ghi nhận người đón và giờ đón."),
    DailyStep(6, "report", "Báo cáo cuối ngày", time(17, 0), time(17, 30),
              "Ban giám hiệu nắm nhanh tình hình trong ngày, không cần tổng hợp thủ công."),
)


def current_step(now: datetime | None = None) -> DailyStep | None:
    for step in DAILY_STEPS:
        if step.phase(now) == "Đang diễn ra":
            return step
    return None


class DailyManager:
    def __init__(self, system: "KindergartenSystem") -> None:
        self.system = system
        self.logs: BaseManager[DailyLog] = BaseManager("nhật ký ăn ngủ")
        self.messages: BaseManager[Message] = BaseManager("tin nhắn")
        self._log_index: dict[tuple[str, date], DailyLog] = {}
        self.logs.on_remove(lambda log: self._log_index.pop((log.child_id, log.date), None))
        system.children.on_remove(self._on_child_removed)

    # ------------------------------------------------------------------ tiện ích chung
    @property
    def _user(self):
        return self.system.auth.current_user

    def _who(self) -> str:
        user = self._user
        return user.full_name if user else "Hệ thống"

    def _require(self, permission: Permission) -> None:
        if self._user is not None:
            self.system.auth.check_permission(permission)

    def _child_for_staff(self, child_id: str) -> Child:
        child = self.system.children.get(child_id)
        self.system.ensure_child_access(child)
        return child

    def _child_for_parent(self, child_id: str) -> Child:
        child = self.system.children.get(child_id)
        user = self._user
        if user is not None and child.id not in {c.id for c in self.system.children_for(user)}:
            raise PermissionDeniedError(f"Bạn chỉ xem và nhắn tin cho giáo viên về con của mình.")
        return child

    def _on_child_removed(self, child: Child) -> None:
        for log in self.logs.find(child_id=child.id):
            self.logs.remove(log.id)
        for message in self.messages.find(child_id=child.id):
            self.messages.remove(message.id)

    def rebuild_index(self) -> None:
        self._log_index = {(log.child_id, log.date): log for log in self.logs}

    # ================================================================== Bước 1: đón trẻ
    def check_in(self, child_id: str, brought_by: str = "", health_note: str = "", on_date: Any = None,
                 at: str | None = None) -> Any:
        """Ghi nhận trẻ đến trường: tự điểm danh 'có mặt', lưu giờ đến, người đưa, người nhận trẻ."""
        self._require(Permission.CHECK_IN_OUT)
        child = self._child_for_staff(child_id)
        d = parse_date(on_date, "Ngày") if on_date else date.today()
        attendance = self.system.attendance
        existing = attendance.get_record(child.id, d)
        if existing is not None and existing.is_present:
            when = f" lúc {existing.arrived_at[11:16]}" if existing.arrived_at else ""
            raise KindergartenError(f"{child.full_name} đã có mặt{when}.")
        note = f"Lưu ý khi đón: {normalize_spaces(health_note)}" if normalize_spaces(health_note) else None
        with self.system.auth.elevated_scope():
            record = attendance.mark(child.id, d, AttendanceStatus.PRESENT, note)
        record.arrived_at = at or datetime.now().isoformat(timespec="minutes")
        record.brought_by = normalize_spaces(brought_by) or "Phụ huynh"
        record.received_by = self._who()
        self.system.audit("Đón trẻ", str(child), {"brought_by": record.brought_by})
        return record

    def undo_check_in(self, child_id: str, on_date: Any = None) -> None:
        self._require(Permission.CHECK_IN_OUT)
        child = self._child_for_staff(child_id)
        d = parse_date(on_date) if on_date else date.today()
        record = self.system.attendance.get_record(child.id, d)
        if record is None or not record.is_present:
            raise KindergartenError(f"{child.full_name} chưa được ghi nhận đến trường.")
        if record.picked_up:
            raise KindergartenError(f"{child.full_name} đã được trả, không hủy lượt đón được.")
        if self.log_of(child.id, d) is not None:
            raise KindergartenError(f"{child.full_name} đã có nhật ký ăn ngủ trong ngày, không hủy lượt đón được.")
        with self.system.auth.elevated_scope():
            self.system.attendance.remove_record(child.id, d)   # trở về 'chưa đến' (vắng)

    def class_day(self, class_id: str, on_date: Any = None) -> list[dict[str, Any]]:
        """Tình hình từng trẻ của một lớp trong ngày (dùng cho đón trẻ, ăn ngủ, trả trẻ)."""
        d = parse_date(on_date) if on_date else date.today()
        rows = []
        for child in self.system.classes.class_list(class_id):
            if child.enrollment_date > d:
                continue
            record = self.system.attendance.get_record(child.id, d)
            rows.append({"child": child, "record": record, "log": self.log_of(child.id, d),
                         "leave": self.system.attendance.leave_for(child.id, d)})
        return rows

    # ================================================================== Bước 3: nhật ký ăn ngủ
    def log_of(self, child_id: str, on_date: Any) -> DailyLog | None:
        return self._log_index.get((str(child_id).upper(), parse_date(on_date)))

    def save_log(self, child_id: str, on_date: Any = None, **fields: Any) -> DailyLog:
        self._require(Permission.DAILY_LOG)
        child = self._child_for_staff(child_id)
        d = parse_date(on_date, "Ngày") if on_date else date.today()
        validate_not_future(d, "Ngày")
        record = self.system.attendance.get_record(child.id, d)
        if record is None or not record.is_present:
            raise KindergartenError(f"{child.full_name} không có mặt ngày {format_date(d)} - "
                                    "hãy đón trẻ / điểm danh trước khi cập nhật ăn ngủ.")
        log = self.log_of(child.id, d)
        if log is None:
            log = DailyLog(child.id, record.class_id, d, **fields)
            self.logs.add(log)
            self._log_index[(log.child_id, log.date)] = log
        else:
            state = BaseManager.snapshot(log)
            try:
                for key, value in fields.items():
                    setattr(log, key, value)
            except Exception:
                BaseManager.restore(log, state)
                raise
        log.updated_by = self._who()
        log.updated_at = datetime.now().isoformat(timespec="minutes")
        return log

    def fill_class_defaults(self, class_id: str, on_date: Any = None) -> int:
        """Điền nhanh mặc định (ăn hết, ngủ ngon, vui vẻ) cho các trẻ có mặt chưa có nhật ký."""
        d = parse_date(on_date) if on_date else date.today()
        count = 0
        for row in self.class_day(class_id, d):
            if row["record"] is not None and row["record"].is_present and row["log"] is None:
                self.save_log(row["child"].id, d, meals={m: "Ăn hết" for m in MEALS}, nap="Ngủ ngon",
                              nap_minutes=120, mood="Vui vẻ")
                count += 1
        return count

    def send_logs(self, class_id: str, on_date: Any = None) -> int:
        """Gửi nhật ký trong ngày cho phụ huynh của từng trẻ (chỉ trẻ nào có nhật ký mới gửi)."""
        self._require(Permission.DAILY_LOG)
        self.system.ensure_class_access(class_id)
        d = parse_date(on_date) if on_date else date.today()
        stamp = datetime.now().isoformat(timespec="minutes")
        count = 0
        for row in self.class_day(class_id, d):
            log = row["log"]
            if log is not None:
                log.sent_at = stamp
                count += 1
        if count:
            self.system.audit("Gửi nhật ký ăn ngủ", self.system.classes.class_name(class_id),
                              {"date": d.isoformat(), "children": count})
        return count

    def logs_for_parent(self, child_id: str, limit: int = 60) -> list[DailyLog]:
        child = self._child_for_parent(child_id)
        logs = [log for log in self.logs.find(child_id=child.id) if log.is_sent]
        return sorted(logs, key=lambda log: log.date, reverse=True)[:limit]

    def parent_open_log(self, log_id: str) -> DailyLog:
        log = self.logs.get(log_id)
        self._child_for_parent(log.child_id)
        if not log.parent_seen_at:
            log.parent_seen_at = datetime.now().isoformat(timespec="minutes")
        return log

    def parent_reply_log(self, log_id: str, text: str) -> DailyLog:
        """Phụ huynh cập nhật/phản hồi tình hình của con trên nhật ký ngày."""
        log = self.parent_open_log(log_id)
        if not normalize_spaces(text):
            raise ValidationError("Nội dung phản hồi không được để trống.")
        log.parent_reply = text
        log.parent_reply_at = datetime.now().isoformat(timespec="minutes")
        return log

    # ================================================================== Bước 4: tương tác phụ huynh
    def parent_send(self, child_id: str, kind: Any, content: str = "", for_date: Any = None, to_date: Any = None,
                    medicine: str = "", dosage: str = "", time_text: str = "") -> Message:
        """Phụ huynh gửi lời nhắn / dặn uống thuốc / xin nghỉ cho giáo viên lớp của con."""
        self._require(Permission.PARENT_PORTAL)
        child = self._child_for_parent(child_id)
        kind = MessageKind.parse(kind)
        if kind is MessageKind.ANNOUNCEMENT:
            raise ValidationError("Phụ huynh không gửi thông báo chung cho lớp.")
        d = parse_date(for_date, "Ngày") if for_date else date.today()
        if kind in (MessageKind.MEDICINE, MessageKind.LEAVE) and d < date.today():
            raise ValidationError("Ngày dặn thuốc / xin nghỉ không được ở quá khứ.")
        if kind is MessageKind.LEAVE:
            self._check_leave_dates(child, d, parse_date(to_date, "Đến ngày") if to_date else d)
        message = Message(kind, content, self._who(), "Phụ huynh", child.id, child.class_id, d, medicine, dosage,
                          time_text, to_date if kind is MessageKind.LEAVE else None)
        self.messages.add(message)
        return message

    def teacher_send(self, child_id: str | None, content: str, class_id: str | None = None,
                     announcement: bool = False) -> Message:
        """Giáo viên nhắn riêng phụ huynh một trẻ, hoặc gửi thông báo cho cả lớp."""
        self._require(Permission.PARENT_CONTACT)
        if announcement:
            classroom = self.system.classes.get(class_id)
            self.system.ensure_class_access(classroom.id)
            message = Message(MessageKind.ANNOUNCEMENT, content, self._who(), "Giáo viên", None, classroom.id)
        else:
            child = self._child_for_staff(child_id)
            message = Message(MessageKind.NOTE, content, self._who(), "Giáo viên", child.id, child.class_id)
            message.status = MessageStatus.DONE
        self.messages.add(message)
        return message

    def _message_for_staff(self, message_id: str) -> Message:
        self._require(Permission.PARENT_CONTACT)
        message = self.messages.get(message_id)
        if message.child_id:
            self._child_for_staff(message.child_id)
        elif message.class_id:
            self.system.ensure_class_access(message.class_id)
        return message

    def mark_seen(self, message_id: str) -> Message:
        message = self._message_for_staff(message_id)
        if message.status is MessageStatus.NEW:
            message.status = MessageStatus.SEEN
        return message

    def reply(self, message_id: str, text: str, done: bool = False) -> Message:
        message = self._message_for_staff(message_id)
        message.reply = text
        message.replied_by = self._who()
        message.replied_at = datetime.now().isoformat(timespec="minutes")
        if done:
            return self.complete(message.id)
        if message.status is MessageStatus.NEW:
            message.status = MessageStatus.SEEN
        return message

    def complete(self, message_id: str, note: str = "") -> Message:
        """Đánh dấu đã thực hiện: đã cho trẻ uống thuốc / đã nhận lời nhắn / DUYỆT đơn xin nghỉ."""
        message = self._message_for_staff(message_id)
        if message.status is MessageStatus.DONE:
            raise KindergartenError("Tin này đã được xử lý.")
        if message.kind is MessageKind.LEAVE and not message.leave_request_id:
            request = self.system.attendance.record_leave_request(
                message.child_id, message.for_date, message.to_date or message.for_date,
                message.content or "Phụ huynh xin nghỉ", message.sender)
            message.leave_request_id = request.id
        if note:
            message.reply = note
            message.replied_by = self._who()
            message.replied_at = datetime.now().isoformat(timespec="minutes")
        message.status = MessageStatus.DONE
        message.done_at = datetime.now().isoformat(timespec="minutes")
        self.system.audit(f"Xử lý: {message.kind.value}", message.child_id or message.class_id or "",
                          {"message": message.id})
        return message

    def decline(self, message_id: str, reason: str) -> Message:
        message = self._message_for_staff(message_id)
        if not normalize_spaces(reason):
            raise ValidationError("Hãy ghi lý do để phụ huynh biết.")
        message.reply = reason
        message.replied_by = self._who()
        message.replied_at = datetime.now().isoformat(timespec="minutes")
        message.status = MessageStatus.DECLINED
        return message

    # ------------------------------------------------------------------ đơn xin nghỉ
    def _check_leave_dates(self, child: Child, start: date, end: date) -> None:
        """Đơn phụ huynh gửi được kiểm tra ngay lúc gửi (không đợi tới lúc cô duyệt mới báo lỗi)."""
        if end < start:
            raise ValidationError("'Đến ngày' phải sau hoặc bằng 'Nghỉ từ ngày'.")
        if (end - start).days + 1 > LeaveRequest.MAX_DAYS:
            raise ValidationError(f"Một đơn xin nghỉ không quá {LeaveRequest.MAX_DAYS} ngày.")
        for request in self.system.attendance.leave_requests.find(child_id=child.id):
            if request.from_date <= end and start <= request.to_date:
                raise ValidationError(f"{child.full_name} đã có đơn nghỉ {request.id} ({request.period_text}) "
                                      "trùng khoảng thời gian này.")
        for message in self.messages.find(child_id=child.id):
            if message.kind is MessageKind.LEAVE and message.needs_action \
                    and message.for_date <= end and start <= (message.to_date or message.for_date):
                raise ValidationError(f"Đơn {message.id} ({message.period_text}) đang chờ cô duyệt, trùng khoảng "
                                      "thời gian này. Hãy rút đơn đó trước nếu muốn sửa.")

    def _school_days(self, start: date, end: date) -> int:
        calendar = self.system.calendar
        return sum(1 for o in range(start.toordinal(), end.toordinal() + 1)
                   if calendar.is_school_day(date.fromordinal(o)))

    def _leave_applications(self, child_ids: set[str]) -> list[LeaveApplication]:
        attendance = self.system.attendance
        result: list[LeaveApplication] = []
        linked: set[str] = set()
        for m in self.messages:
            if m.kind is not MessageKind.LEAVE or m.child_id not in child_ids:
                continue
            request = attendance.leave_requests.get_or_none(m.leave_request_id) if m.leave_request_id else None
            linked.add(m.leave_request_id)
            if m.status is MessageStatus.DECLINED:
                status = LeaveStatus.DECLINED
            elif m.status is MessageStatus.DONE:
                status = LeaveStatus.APPROVED if request is not None else LeaveStatus.CANCELLED
            else:
                status = LeaveStatus.PENDING
            end = m.to_date or m.for_date
            result.append(LeaveApplication(
                m.id, m.child_id, m.class_id, m.for_date, end, m.content, m.sender, LeaveApplication.SOURCE_PARENT,
                status, m.reply, m.created_at, self._school_days(m.for_date, end), m.leave_request_id))
        for r in attendance.leave_requests:
            if r.child_id not in child_ids or r.id in linked:
                continue
            child = self.system.children.get_or_none(r.child_id)
            result.append(LeaveApplication(
                r.id, r.child_id, child.class_id if child else None, r.from_date, r.to_date, r.reason,
                r.submitted_by or "-", LeaveApplication.SOURCE_TEACHER, LeaveStatus.APPROVED, "", r.created_at,
                self._school_days(r.from_date, r.to_date), r.id))
        # đơn chờ duyệt lên đầu, sau đó ngày nghỉ gần nhất trước
        return sorted(result, key=lambda a: (a.status is LeaveStatus.PENDING, a.from_date, a.created_at),
                      reverse=True)

    def leave_applications(self, child_id: str) -> list[LeaveApplication]:
        """Phụ huynh: mọi đơn xin nghỉ của con - đơn tự gửi (chờ duyệt / đã duyệt / từ chối) và đơn cô ghi giúp."""
        self._require(Permission.PARENT_PORTAL)
        return self._leave_applications({self._child_for_parent(child_id).id})

    def leave_applications_for_staff(self) -> list[LeaveApplication]:
        """Giáo viên / BGH: đơn xin nghỉ của các trẻ trong phạm vi được xem."""
        self._require(Permission.TAKE_ATTENDANCE)
        user = self._user
        children = self.system.children.all() if user is None else self.system.children_for(user)
        return self._leave_applications({c.id for c in children})

    def pending_leaves(self) -> list[Message]:
        """Đơn phụ huynh gửi đang chờ giáo viên duyệt (trong phạm vi lớp được xem), cũ nhất trước."""
        return sorted((self.messages.get(a.id) for a in self.leave_applications_for_staff()
                       if a.status is LeaveStatus.PENDING), key=lambda m: m.created_at)

    def parent_withdraw_leave(self, message_id: str) -> Message:
        """Phụ huynh rút đơn xin nghỉ đã gửi khi cô chưa duyệt (VD: gửi nhầm ngày, con khỏi ốm đi học lại)."""
        self._require(Permission.PARENT_PORTAL)
        message = self.messages.get(message_id)
        if message.kind is not MessageKind.LEAVE or not message.child_id:
            raise ValidationError(f"'{message.id}' không phải đơn xin nghỉ.")
        self._child_for_parent(message.child_id)
        if not message.needs_action:
            raise KindergartenError("Cô đã xử lý đơn này nên không rút được. Hãy nhắn cô nếu cần thay đổi.")
        self.messages.remove(message.id)
        self.system.audit("Phụ huynh rút đơn xin nghỉ", message.child_id, {"message": message.id})
        return message

    def review_leave(self, message_id: str, approve: bool, note: str = "") -> Message:
        """Giáo viên duyệt đơn phụ huynh gửi (thành đơn nghỉ có phép) hoặc từ chối (bắt buộc ghi lý do)."""
        self._require(Permission.TAKE_ATTENDANCE)
        message = self._message_for_staff(message_id)
        if message.kind is not MessageKind.LEAVE:
            raise ValidationError(f"Tin {message.id} không phải đơn xin nghỉ.")
        if not message.needs_action:
            raise KindergartenError(f"Đơn {message.id} đã được xử lý.")
        return self.complete(message.id, note) if approve else self.decline(message.id, note)

    def inbox(self, class_ids: set[str] | None = None, only_open: bool = False,
              on_date: date | None = None) -> list[Message]:
        """Hộp thư của giáo viên/BGH: tin của phụ huynh các lớp trong phạm vi, mới nhất trước."""
        result = []
        for message in self.messages:
            if class_ids is not None and message.class_id not in class_ids:
                continue
            if only_open and not message.needs_action:
                continue
            if on_date is not None and not (message.for_date <= on_date <= (message.to_date or message.for_date)) \
                    and message.created_at[:10] != on_date.isoformat():
                continue
            result.append(message)
        return sorted(result, key=lambda m: (m.needs_action, m.created_at), reverse=True)

    def messages_for_parent(self, child_id: str) -> list[Message]:
        child = self._child_for_parent(child_id)
        items = [m for m in self.messages
                 if m.child_id == child.id or (m.kind is MessageKind.ANNOUNCEMENT and m.class_id == child.class_id)]
        return sorted(items, key=lambda m: m.created_at, reverse=True)

    def medicine_today(self, class_ids: set[str] | None = None, on_date: date | None = None) -> list[Message]:
        d = on_date or date.today()
        return [m for m in self.inbox(class_ids) if m.kind is MessageKind.MEDICINE
                and m.for_date == d and m.status is not MessageStatus.DECLINED]

    # ================================================================== Bước 5: trả trẻ
    def pickup_status(self, class_id: str, on_date: Any = None) -> list[dict[str, Any]]:
        return [row for row in self.class_day(class_id, on_date)
                if row["record"] is not None and row["record"].is_present]

    # ================================================================== Bước 6: tổng hợp
    def class_summary(self, class_id: str, on_date: Any = None) -> dict[str, Any]:
        d = parse_date(on_date) if on_date else date.today()
        classroom = self.system.classes.get(class_id)
        rows = self.class_day(classroom.id, d)
        records = [r["record"] for r in rows if r["record"] is not None]
        present = [r for r in records if r.is_present]
        not_arrived = [r for r in rows if r["record"] is None]   # chưa đón = vắng (chưa chốt)
        logs = [r["log"] for r in rows if r["log"] is not None]
        messages = [m for m in self.messages if m.class_id == classroom.id and m.created_at[:10] == d.isoformat()]
        medicine = [m for m in messages if m.kind is MessageKind.MEDICINE] + \
            [m for m in self.messages if m.class_id == classroom.id and m.kind is MessageKind.MEDICINE
             and m.for_date == d and m.created_at[:10] != d.isoformat()]
        teacher = self.system.classes.homeroom_teacher(classroom.id)
        return {
            "class": classroom, "teacher": teacher.full_name if teacher else "-", "size": len(rows),
            "checked_in": sum(1 for r in records if r.checked_in), "taken": len(records),
            "present": len(present),
            "excused": sum(1 for r in records if r.status is AttendanceStatus.EXCUSED)
            + sum(1 for r in not_arrived if r["leave"] is not None),
            "unexcused": sum(1 for r in records if r.status is AttendanceStatus.UNEXCUSED)
            + sum(1 for r in not_arrived if r["leave"] is None),
            "finalized": len(records) == len(rows),
            "logs": len(logs), "logs_sent": sum(1 for log in logs if log.is_sent),
            "logs_seen": sum(1 for log in logs if log.parent_seen_at),
            "parent_replies": sum(1 for log in logs if log.parent_reply),
            "messages": len([m for m in messages if m.from_parent]),
            "open_messages": sum(1 for m in self.messages if m.class_id == classroom.id and m.needs_action),
            "medicine": len(medicine), "medicine_done": sum(1 for m in medicine if m.status is MessageStatus.DONE),
            "picked_up": sum(1 for r in present if r.picked_up),
            "not_picked_up": [self.system.children.get(r.child_id).full_name for r in present if not r.picked_up],
            "health_notes": [(self.system.children.get(log.child_id).full_name, log.health_note)
                             for log in logs if log.health_note],
            "absent_names": [(self.system.children.get(r.child_id).full_name, r.status.value, r.note)
                             for r in records if not r.is_present]
            + [(r["child"].full_name, "Nghỉ có phép" if r["leave"] else "Vắng", "chưa đến trường")
               for r in not_arrived],
        }

    def step_progress(self, class_ids: set[str] | None = None, on_date: Any = None,
                      now: datetime | None = None) -> list[dict[str, Any]]:
        """Tiến độ 6 bước vận hành trong ngày (cho màn hình 'Vận hành hôm nay')."""
        d = parse_date(on_date) if on_date else date.today()
        school_day = self.system.calendar.is_school_day(d)
        classes = [c for c in self.system.classes.all_sorted() if class_ids is None or c.id in class_ids]
        summaries = [self.class_summary(c.id, d) for c in classes] if school_day else []
        total = sum(s["size"] for s in summaries)
        present = sum(s["present"] for s in summaries)
        def tot(key: str) -> int:
            return sum(s[key] for s in summaries)
        values = {
            "checkin": (tot("checked_in"), total, f"Đã đón (có mặt) {tot('checked_in')}/{total} trẻ"),
            "attendance": (tot("taken"), total, f"Đã chốt {tot('taken')}/{total} - có mặt {present}, "
                                                f"vắng {total - present}"),
            "dailylog": (tot("logs_sent"), present, f"Đã gửi nhật ký {tot('logs_sent')}/{present} trẻ có mặt"),
            "contact": (tot("open_messages") == 0, 1, f"{tot('open_messages')} tin chờ xử lý, "
                                                       f"thuốc {tot('medicine_done')}/{tot('medicine')}"),
            "pickup": (tot("picked_up"), present, f"Đã trả {tot('picked_up')}/{present} trẻ"),
        }
        eod = self.system.reports.end_of_day_status(d, class_ids)
        values["report"] = (len(eod["sent"]), len(eod["classes"]),
                            f"Đã gửi BGH {len(eod['sent'])}/{len(eod['classes'])} lớp")
        result = []
        for step in DAILY_STEPS:
            done, needed, text = values[step.key]
            complete = bool(needed) and done >= needed
            phase = step.phase(now) if d == date.today() else ("Đã qua" if d < date.today() else "Sắp tới")
            result.append({"step": step, "phase": phase, "done": done, "needed": needed, "text": text,
                           "complete": complete if school_day else False})
        return result

    # ------------------------------------------------------------------ lưu trữ
    def load(self, logs: list[dict[str, Any]], messages: list[dict[str, Any]]) -> None:
        self.logs.load_list(logs, DailyLog.from_dict)
        self.messages.load_list(messages, Message.from_dict)
        self.rebuild_index()
