"""T20 - AttendanceManager: điểm danh cả lớp theo ngày, ghi đơn xin nghỉ, thống kê chuyên cần tháng."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Callable

from ..classroom.class_manager import ClassManager
from ..core.base_manager import BaseManager
from ..exceptions import KindergartenError, NotFoundError, ValidationError
from ..people.child import Child
from ..people.managers import ChildManager
from ..school_calendar import SchoolCalendar
from ..utils import format_date, month_bounds, parse_date, validate_not_future
from .records import AttendanceRecord, AttendanceStatus, LeaveRequest


class AttendanceManager(BaseManager[AttendanceRecord]):
    entity_name = "bản ghi điểm danh"

    def __init__(self, child_manager: ChildManager, class_manager: ClassManager,
                 calendar: SchoolCalendar | None = None) -> None:
        super().__init__()
        self.children = child_manager
        self.classes = class_manager
        self.calendar = calendar or SchoolCalendar()
        self.leave_requests: BaseManager[LeaveRequest] = BaseManager("đơn xin nghỉ")
        self.class_guard: Callable[[str], None] | None = None   # L08: giáo viên chỉ điểm danh lớp mình
        self._by_key: dict[tuple[str, date], AttendanceRecord] = {}
        self._by_month: dict[tuple[int, int], dict[str, AttendanceRecord]] = defaultdict(dict)   # P03
        child_manager.on_remove(self._on_child_removed)

    # ------------------------------------------------------------------ chỉ mục (trẻ, ngày) và (năm, tháng)
    def _validate_new(self, record: AttendanceRecord) -> None:
        if (record.child_id, record.date) in self._by_key:
            raise ValidationError(f"Trẻ {record.child_id} đã được điểm danh ngày {record.date:%d/%m/%Y}.")

    def _after_add(self, record: AttendanceRecord) -> None:
        self._by_key[(record.child_id, record.date)] = record
        self._by_month[(record.date.year, record.date.month)][record.id] = record

    def _after_remove(self, record: AttendanceRecord) -> None:
        self._by_key.pop((record.child_id, record.date), None)
        self._by_month[(record.date.year, record.date.month)].pop(record.id, None)

    def _after_clear(self) -> None:
        self._by_key.clear()
        self._by_month.clear()

    def _on_child_removed(self, child: Child) -> None:
        for record in self.find(child_id=child.id):
            self.remove(record.id)
        for request in self.leave_requests.find(child_id=child.id):
            self.leave_requests.remove(request.id)

    def _guard(self, class_id: str | None) -> None:
        if self.class_guard is not None and class_id:
            self.class_guard(class_id)

    # ------------------------------------------------------------------ đơn xin nghỉ
    def leave_for(self, child_id: str, on_date: date) -> LeaveRequest | None:
        key = self._key(child_id)
        return next((r for r in self.leave_requests if r.child_id == key and r.covers(on_date)), None)

    def leave_requests_of(self, child_id: str | None = None) -> list[LeaveRequest]:
        items = self.leave_requests.find(child_id=self._key(child_id)) if child_id else self.leave_requests.all()
        return sorted(items, key=lambda r: (r.from_date, r.id_sort_key), reverse=True)

    def leave_school_days(self, request: LeaveRequest) -> int:
        """Số ngày học (theo lịch năm học) nằm trong đơn."""
        days = range(request.from_date.toordinal(), request.to_date.toordinal() + 1)
        return sum(1 for o in days if self.calendar.is_school_day(date.fromordinal(o)))

    def record_leave_request(self, child_id: str, from_date: Any, to_date: Any, reason: str,
                             submitted_by: str = "") -> LeaveRequest:
        """Ghi đơn xin nghỉ; các ngày đã điểm danh 'nghỉ không phép' được chuyển thành 'có phép'."""
        child = self.children.get(child_id)
        self._guard(child.class_id)
        request = LeaveRequest(child.id, from_date, to_date, reason, submitted_by)
        for other in self.leave_requests.find(child_id=child.id):
            if other.overlaps(request):
                raise ValidationError(f"{child.full_name} đã có đơn {other.id} ({other.period_text}) "
                                      "trùng khoảng thời gian này.")
        self.leave_requests.add(request)
        for record in self.find(lambda r: r.child_id == child.id and request.covers(r.date)):
            if record.status is AttendanceStatus.UNEXCUSED:
                record.status = AttendanceStatus.EXCUSED
                record.note = f"Theo đơn {request.id}: {request.reason}"
                request.converted_dates.append(record.date)
        return request

    def cancel_leave_request(self, request_id: str) -> LeaveRequest:
        """L26: hủy đơn nhập nhầm; các ngày đơn đã đổi sang 'có phép' được trả lại 'không phép'."""
        request = self.leave_requests.get(request_id)
        child = self.children.get_or_none(request.child_id)
        self._guard(child.class_id if child else None)
        for d in request.converted_dates:
            record = self._by_key.get((request.child_id, d))
            if record is not None and record.status is AttendanceStatus.EXCUSED:
                record.status = AttendanceStatus.UNEXCUSED
                record.note = f"Hủy đơn {request.id}"
        return self.leave_requests.remove(request.id)

    # ------------------------------------------------------------------ điểm danh
    def get_record(self, child_id: str, on_date: Any) -> AttendanceRecord | None:
        return self._by_key.get((self._key(child_id), parse_date(on_date)))

    def default_status(self, child_id: str, on_date: Any) -> tuple[AttendanceStatus, str]:
        """Trạng thái của trẻ trong ngày, đồng bộ với bước đón trẻ:
        đã đón (có bản ghi có mặt) -> 'có mặt'; có đơn xin nghỉ -> 'nghỉ có phép'; CHƯA ĐÓN -> vắng."""
        d = parse_date(on_date)
        existing = self.get_record(child_id, d)
        if existing is not None:
            return existing.status, existing.note
        leave = self.leave_for(child_id, d)
        if leave is not None:
            return AttendanceStatus.EXCUSED, f"Theo đơn {leave.id}: {leave.reason}"
        return AttendanceStatus.UNEXCUSED, self.NOT_ARRIVED

    NOT_ARRIVED = "Chưa đến trường"

    def remove_record(self, child_id: str, on_date: Any) -> None:
        """Xóa kết quả của trẻ trong ngày (VD: hủy lượt đón nhầm) -> trở về 'chưa đến'."""
        record = self.get_record(child_id, on_date)
        if record is not None:
            self._guard(record.class_id)
            self.remove(record.id)

    def check_day(self, child: Child, d: date) -> None:
        """L04: một định nghĩa 'ngày đi học' duy nhất + không điểm danh trước ngày nhập học."""
        validate_not_future(d, "Ngày điểm danh")
        self.calendar.ensure_school_day(d)
        if d < child.enrollment_date:
            raise ValidationError(f"{child.full_name} nhập học ngày {format_date(child.enrollment_date)}, "
                                  f"chưa thể điểm danh ngày {format_date(d)}.")

    def mark(self, child_id: str, on_date: Any, status: Any, note: str | None = None,
             class_id: str | None = None) -> AttendanceRecord:
        """Ghi/cập nhật điểm danh một trẻ trong một ngày (mỗi trẻ chỉ 1 bản ghi/ngày).

        `note=None` giữ nguyên ghi chú cũ (L26).
        """
        child = self.children.get(child_id)
        d = parse_date(on_date, "Ngày điểm danh")
        status = AttendanceStatus.parse(status)
        record = self._by_key.get((child.id, d))
        class_key = self._key(class_id) or (record.class_id if record else None) or child.class_id
        if not class_key:
            raise KindergartenError(f"{child.full_name} chưa được xếp lớp nên chưa thể điểm danh.")
        self._guard(class_key)
        self.check_day(child, d)
        if record is not None:
            self._authorize()
            record.status = status
            if note is not None:
                record.note = note
        else:
            record = self.add(AttendanceRecord(child.id, class_key, d, status, note or ""))
        if record.is_present and not record.arrived_at and d == date.today():
            # đồng bộ: điểm danh 'có mặt' tại lớp cũng là đã đón trẻ đầu ngày
            record.arrived_at = datetime.now().isoformat(timespec="minutes")
            record.brought_by = record.brought_by or "Ghi nhận khi điểm danh"
        return record

    def take_class_attendance(self, class_id: str, on_date: Any,
                              statuses: dict[str, Any] | None = None) -> list[AttendanceRecord]:
        """Điểm danh cả lớp. `statuses` = {mã trẻ: trạng thái | (trạng thái, ghi chú)}.

        Trẻ không có trong `statuses`: giữ nguyên kết quả đã có (L26); chưa có thì 'nghỉ có phép' nếu có đơn,
        ngược lại 'có mặt'. Toàn bộ dữ liệu được kiểm tra trước, chỉ ghi khi tất cả hợp lệ (L23).
        """
        classroom = self.classes.get(class_id)
        self._guard(classroom.id)
        self._authorize()
        d = parse_date(on_date, "Ngày điểm danh")
        statuses = {self._key(k): v for k, v in (statuses or {}).items()}
        unknown = set(statuses) - set(classroom.child_ids)
        if unknown:
            raise ValidationError(f"Các mã trẻ không thuộc lớp {classroom.name}: {', '.join(sorted(unknown))}.")
        if not classroom.child_ids:
            raise KindergartenError(f"Lớp {classroom.name} chưa có trẻ.")
        validate_not_future(d, "Ngày điểm danh")
        self.calendar.ensure_school_day(d)
        plan: list[tuple[str, AttendanceStatus, str | None]] = []
        for child_id in classroom.child_ids:
            child = self.children.get(child_id)
            if d < child.enrollment_date:
                continue   # trẻ nhập học sau ngày này: bỏ qua thay vì làm hỏng cả lớp
            value = statuses.get(child_id)
            if value is None:
                if (child_id, d) in self._by_key:
                    continue
                status, note = self.default_status(child_id, d)
            elif isinstance(value, tuple):
                status, note = AttendanceStatus.parse(value[0]), value[1]
            else:
                status, note = AttendanceStatus.parse(value), None
            plan.append((child_id, status, note))
        for child_id, status, note in plan:
            self.mark(child_id, d, status, note, class_id=classroom.id)
        return [self._by_key[(cid, d)] for cid in classroom.child_ids if (cid, d) in self._by_key]

    def is_taken(self, class_id: str, on_date: Any) -> bool:
        classroom = self.classes.get(class_id)
        d = parse_date(on_date)
        return bool(classroom.child_ids) and all((cid, d) in self._by_key for cid in classroom.child_ids)

    def records_of_class_on(self, class_id: str, on_date: Any) -> list[AttendanceRecord]:
        """Dùng chỉ mục (trẻ, ngày) thay vì quét toàn bộ (P03)."""
        classroom = self.classes.get_or_none(class_id)
        d = parse_date(on_date)
        if classroom is None:
            return []
        records = (self._by_key.get((cid, d)) for cid in classroom.child_ids)
        return [r for r in records if r is not None and r.class_id == classroom.id]

    # ------------------------------------------------------------------ thống kê
    def records_in_month(self, month: int, year: int, child_id: str | None = None,
                         class_id: str | None = None) -> list[AttendanceRecord]:
        child_key = self._key(child_id) if child_id else None
        class_key = self._key(class_id) if class_id else None
        records = self._by_month.get((year, month), {}).values()
        return sorted((r for r in records if (child_key is None or r.child_id == child_key)
                       and (class_key is None or r.class_id == class_key)),
                      key=lambda r: (r.date, r.child_id))

    def present_days_map(self, month: int, year: int) -> Counter:
        """Số ngày có mặt của mọi trẻ trong tháng - một lượt duyệt cho cả trường (P03)."""
        return Counter(r.child_id for r in self._by_month.get((year, month), {}).values() if r.is_present)

    def present_days(self, child_id: str, month: int, year: int) -> int:
        """Số ngày đi học thực tế trong tháng (dùng tính tiền ăn - T21)."""
        return self.present_days_map(month, year).get(self._key(child_id), 0)

    def monthly_stats(self, month: int, year: int, class_id: str | None = None,
                      class_ids: set[str] | None = None) -> list[dict[str, Any]]:
        """Thống kê chuyên cần từng trẻ trong tháng (có thể giới hạn theo một hoặc nhiều lớp)."""
        counters: dict[str, Counter] = {}
        class_of: dict[str, str] = {}
        for record in self.records_in_month(month, year, class_id=class_id):
            if class_ids is not None and record.class_id not in class_ids:
                continue
            counters.setdefault(record.child_id, Counter())[record.status] += 1
            class_of[record.child_id] = record.class_id
        if class_id:  # hiển thị cả trẻ trong lớp chưa có bản ghi nào
            for child_id in self.classes.get(class_id).child_ids:
                counters.setdefault(child_id, Counter())
                class_of.setdefault(child_id, self._key(class_id))
        rows = []
        for child_id, counter in counters.items():
            child = self.children.get_or_none(child_id)
            total = sum(counter.values())
            present = counter[AttendanceStatus.PRESENT]
            rows.append({
                "child_id": child_id,
                "child_name": child.full_name if child else child_id,
                "sort_key": child.sort_key if child else ("", child_id),
                "class_id": class_of.get(child_id),
                "class_name": self.classes.class_name(class_of.get(child_id)),
                "present": present,
                "excused": counter[AttendanceStatus.EXCUSED],
                "unexcused": counter[AttendanceStatus.UNEXCUSED],
                "total": total,
                "rate": present / total * 100 if total else None,
            })
        return sorted(rows, key=lambda r: (r["class_name"], r["sort_key"]))

    def attendance_rate(self, month: int, year: int, class_id: str | None = None,
                        class_ids: set[str] | None = None) -> float | None:
        records = [r for r in self.records_in_month(month, year, class_id=class_id)
                   if class_ids is None or r.class_id in class_ids]
        if not records:
            return None
        return sum(1 for r in records if r.is_present) / len(records) * 100

    def daily_summary(self, on_date: Any, class_ids: set[str] | None = None) -> list[dict[str, Any]]:
        """Tình hình điểm danh từng lớp trong một ngày."""
        d = parse_date(on_date)
        summary = []
        for classroom in self.classes.all_sorted():
            if class_ids is not None and classroom.id not in class_ids:
                continue
            records = [self._by_key.get((cid, d)) for cid in classroom.child_ids]
            done = [r for r in records if r is not None]
            summary.append({
                "class": classroom,
                "size": classroom.size,
                "taken": len(done),
                "present": sum(1 for r in done if r.status is AttendanceStatus.PRESENT),
                "excused": sum(1 for r in done if r.status is AttendanceStatus.EXCUSED),
                "unexcused": sum(1 for r in done if r.status is AttendanceStatus.UNEXCUSED),
            })
        return summary

    def monthly_grid(self, class_id: str, month: int, year: int, until: date | None = None
                     ) -> tuple[list[str], list[list[Any]]]:
        """Sổ điểm danh tháng: mỗi hàng là một trẻ, mỗi cột là một ngày học theo lịch (C/P/K)."""
        classroom = self.classes.get(class_id)
        last = min(month_bounds(month, year)[1], until or date.today())
        days = self.calendar.school_days(month, year, until=last)
        headers = ["Mã", "Họ tên"] + [f"{d.day:02d}" for d in days] + ["C", "P", "K"]
        rows = []
        child_ids = set(classroom.child_ids) | {r.child_id for r in self.records_in_month(month, year, class_id=class_id)}
        children = self.children.sort("sort_key", items=[c for c in map(self.children.get_or_none, child_ids) if c])
        for child in children:
            marks, counter = [], Counter()
            for d in days:
                record = self._by_key.get((child.id, d))
                if record is None or record.class_id != classroom.id:
                    marks.append(".")
                else:
                    marks.append(record.status.short)
                    counter[record.status] += 1
            rows.append([child.id, child.full_name, *marks, counter[AttendanceStatus.PRESENT],
                         counter[AttendanceStatus.EXCUSED], counter[AttendanceStatus.UNEXCUSED]])
        return headers, rows

    def find_leave(self, request_id: str) -> LeaveRequest:
        request = self.leave_requests.get_or_none(request_id)
        if request is None:
            raise NotFoundError(f"Không tìm thấy đơn xin nghỉ '{request_id}'.")
        return request
