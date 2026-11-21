"""Màn hình console: điểm danh, đơn xin nghỉ, chuyên cần, xác nhận người đón (T19-T20)."""
from __future__ import annotations

from datetime import date

from ....attendance.records import AttendanceStatus
from ....auth.user import Permission
from ....exceptions import KindergartenError
from ....utils import (format_date, format_percent, month_label, validate_not_future, weekday_name)
from ..menu import Menu
from .base import Screen

STATUS_OPTIONS = [(AttendanceStatus.PRESENT, "C - Có mặt"), (AttendanceStatus.EXCUSED, "P - Nghỉ có phép"),
                  (AttendanceStatus.UNEXCUSED, "K - Nghỉ không phép")]


class AttendanceScreen(Screen):
    title = "Điểm danh"

    def build_menu(self) -> Menu:
        P = Permission.TAKE_ATTENDANCE
        return (self.new_menu()
                .add("Điểm danh lớp theo ngày", self.take_attendance, P)
                .add("Sửa điểm danh của một trẻ", self.edit_one, P)
                .add("Duyệt đơn xin nghỉ phụ huynh gửi", self.review_leaves, P)
                .add("Ghi đơn xin nghỉ (phụ huynh báo qua điện thoại)", self.leave_request, P)
                .add("Danh sách đơn xin nghỉ", self.list_leaves, P)
                .add("Hủy đơn xin nghỉ nhập nhầm", self.cancel_leave, P)
                .add("Xem tình hình điểm danh theo ngày", self.view_day, P)
                .add("Sổ điểm danh tháng của lớp", self.month_grid, P)
                .add("Thống kê chuyên cần tháng", self.monthly_stats, P)
                .add("Xác nhận người đến đón trẻ", self.verify_pickup, P))

    def _ask_day(self, prompt: str = "Ngày điểm danh") -> date:
        """L04: hỏi lại ngay nếu là ngày tương lai, cuối tuần hoặc ngày nghỉ lễ."""
        def check(d: date) -> None:
            validate_not_future(d, prompt)
            self.system.calendar.ensure_school_day(d)

        today = date.today()
        default = today if self.system.calendar.is_school_day(today) else None
        return self.io.ask_date(prompt, default, check=check)

    def take_attendance(self) -> None:
        io, s = self.io, self.system
        classroom = self.select_class()
        day = self._ask_day()
        children = [c for c in s.classes.class_list(classroom.id) if c.enrollment_date <= day]
        if not children:
            raise KindergartenError(f"Lớp {classroom.name} chưa có trẻ.")
        if s.attendance.is_taken(classroom.id, day):
            io.info("Lớp đã được điểm danh ngày này - bạn đang sửa lại kết quả.")
        statuses = {c.id: s.attendance.default_status(c.id, day) for c in children}
        while True:
            rows = [[i, c.id, c.full_name, statuses[c.id][0].value, statuses[c.id][1] or ""]
                    for i, c in enumerate(children, 1)]
            io.table(["STT", "Mã", "Họ tên", "Trạng thái", "Ghi chú"], rows,
                     title=f"ĐIỂM DANH LỚP {classroom.name.upper()} - {weekday_name(day)} {format_date(day)}")
            indexes = io.ask_indexes("Nhập STT trẻ cần đổi trạng thái (VD: 2,5), Enter để LƯU", len(children),
                                     required=False)
            if not indexes:
                break
            status = io.ask_choice("Trạng thái", STATUS_OPTIONS)
            note = "" if status is AttendanceStatus.PRESENT else (io.ask_text("Lý do / ghi chú", required=False) or "")
            for index in indexes:
                statuses[children[index - 1].id] = (status, note)
        records = s.attendance.take_class_attendance(classroom.id, day, statuses)
        present = sum(1 for r in records if r.is_present)
        io.success(f"Đã lưu điểm danh lớp {classroom.name} ngày {format_date(day)}: "
                   f"có mặt {present}/{len(records)}.")

    def edit_one(self) -> None:
        children = [c for c in self.visible_children() if c.class_id]
        child = self.select_child(children)
        day = self._ask_day()
        current = self.system.attendance.get_record(child.id, day)
        if current:
            self.io.info(f"Hiện tại: {current.status.value} {current.note}")
        status = self.io.ask_choice("Trạng thái", STATUS_OPTIONS, current.status if current else None)
        note = self.io.ask_text("Ghi chú", current.note if current else None, required=False) or ""
        self.system.attendance.mark(child.id, day, status, note)
        self.io.success(f"Đã ghi {child.full_name}: {status.value} ngày {format_date(day)}.")

    def review_leaves(self) -> None:
        """Duyệt / từ chối đơn xin nghỉ phụ huynh tự tạo trên ứng dụng."""
        io, daily = self.io, self.system.daily
        message = self._require(io.choose(
            daily.pending_leaves(),
            lambda m: f"{m.id} - {self.system.children.get(m.child_id).full_name}: {m.period_text} - {m.content} "
                      f"({m.sender})",
            "Chọn đơn cần duyệt", "Không có đơn xin nghỉ nào của phụ huynh đang chờ duyệt."))
        approve = io.ask_choice("Quyết định", [(True, "Duyệt - tính nghỉ có phép"), (False, "Từ chối")], True)
        note = io.ask_text("Ghi chú cho phụ huynh" + ("" if approve else " (lý do từ chối)"),
                           required=not approve) or ""
        message = daily.review_leave(message.id, approve, note)
        io.success(f"Đã duyệt đơn {message.id}: {message.period_text} tính là nghỉ có phép." if approve
                   else f"Đã từ chối đơn {message.id}.")

    def leave_request(self) -> None:
        """Phụ huynh gọi điện báo nghỉ -> giáo viên ghi đơn giúp, có hiệu lực ngay (không cần duyệt)."""
        io = self.io
        child = self.select_child()
        start = io.ask_date("Nghỉ từ ngày", date.today())
        end = io.ask_date("Đến ngày", start)
        reason = io.ask_text("Lý do nghỉ")
        parents = self.system.parents.parents_of(child.id)
        default_sender = f"{parents[0].relationship} {parents[0].full_name}" if parents else None
        sender = io.ask_text("Người báo nghỉ", default_sender, required=False) or "Phụ huynh"
        request = self.system.attendance.record_leave_request(child.id, start, end, reason,
                                                              f"{sender} (qua điện thoại)")
        io.success(f"Đã ghi đơn {request.id} cho {child.full_name}: {request.period_text} "
                   f"({self.system.attendance.leave_school_days(request)} ngày học). "
                   "Các ngày này sẽ tính là nghỉ có phép.")

    def _visible_leaves(self) -> list:
        allowed = {c.id for c in self.visible_children()}
        return [r for r in self.system.attendance.leave_requests_of() if r.child_id in allowed]

    def list_leaves(self) -> None:
        rows = []
        for a in self.system.daily.leave_applications_for_staff():
            child = self.system.children.get(a.child_id)
            rows.append([a.id, child.full_name, self.class_name(a.class_id), a.period_text, a.school_days, a.reason,
                         a.created_by, "PH gửi" if a.source == a.SOURCE_PARENT else "Cô ghi giúp", a.status.value])
        self.io.table(["Mã đơn", "Trẻ", "Lớp", "Thời gian", "Ngày học", "Lý do", "Người gửi", "Hình thức",
                       "Trạng thái"], rows[:50], title="ĐƠN XIN NGHỈ (chờ duyệt trước, sau đó mới nhất; tối đa 50)")

    def cancel_leave(self) -> None:
        """L26: hủy đơn nhập nhầm; các ngày đơn đã chuyển 'có phép' được trả về 'không phép'."""
        request = self._require(self.io.choose(
            self._visible_leaves(),
            lambda r: f"{r.id} - {self.system.children.get(r.child_id).full_name}: {r.period_text} ({r.reason})",
            "Chọn đơn cần hủy", "Không có đơn xin nghỉ nào."))
        if self.confirm(f"Hủy đơn {request.id} ({request.period_text})?"):
            self.system.attendance.cancel_leave_request(request.id)
            self.system.audit("Hủy đơn xin nghỉ", request.id)
            self.io.success("Đã hủy đơn xin nghỉ.")

    def view_day(self) -> None:
        day = self.io.ask_date("Ngày", date.today())
        allowed = {c.id for c in self.system.classes_for(self.user)}
        summary = [d for d in self.system.attendance.daily_summary(day) if d["class"].id in allowed]
        rows = [[d["class"].name, d["size"], d["taken"], d["present"], d["excused"], d["unexcused"]] for d in summary]
        self.io.table(["Lớp", "Sĩ số", "Đã điểm danh", "Có mặt", "Có phép", "Không phép"], rows,
                      title=f"TÌNH HÌNH ĐIỂM DANH {weekday_name(day).upper()} {format_date(day)}")
        absent = []
        for d in summary:
            for record in self.system.attendance.records_of_class_on(d["class"].id, day):
                if not record.is_present:
                    child = self.system.children.get_or_none(record.child_id)
                    absent.append([d["class"].name, child.full_name if child else record.child_id,
                                   record.status.value, record.note or "-"])
        if absent:
            self.io.table(["Lớp", "Trẻ vắng", "Trạng thái", "Ghi chú"], absent, title="Danh sách vắng:")

    def month_grid(self) -> None:
        classroom = self.select_class()
        month, year = self.ask_month()
        headers, rows = self.system.attendance.monthly_grid(classroom.id, month, year)
        self.io.table(headers, rows, title=f"SỔ ĐIỂM DANH LỚP {classroom.name.upper()} THÁNG "
                                           f"{month_label(month, year)} (C: có mặt, P: có phép, K: không phép)",
                      max_width=24)

    def monthly_stats(self) -> None:
        classes = self.system.classes_for(self.user)
        scope = self.scope_class_ids()
        classroom = self.io.choose(classes, self.class_label, "Chọn lớp (Enter = tất cả lớp được phép)") \
            if len(classes) > 1 else classes[0] if classes else None
        month, year = self.ask_month()
        class_id = classroom.id if classroom else None
        stats = self.system.attendance.monthly_stats(month, year, class_id, scope)
        rows = [[s["child_id"], s["child_name"], s["class_name"], s["present"], s["excused"], s["unexcused"],
                 s["total"], format_percent(s["rate"])] for s in stats]
        label = classroom.name if classroom else ("TOÀN TRƯỜNG" if scope is None else "CÁC LỚP PHỤ TRÁCH")
        self.io.table(["Mã", "Họ tên", "Lớp", "Có mặt", "Có phép", "Không phép", "Tổng", "Tỷ lệ"], rows,
                      title=f"CHUYÊN CẦN THÁNG {month_label(month, year)} - {label}")
        rate = self.system.attendance.attendance_rate(month, year, class_id, scope)
        self.io.info(f"Tỷ lệ chuyên cần chung: {format_percent(rate)}")

    def verify_pickup(self) -> None:
        """L06/U04: chọn người đón từ danh sách (theo số thứ tự), không gõ tự do; chỉ giao khi trẻ có mặt."""
        io = self.io
        child = self.select_child()
        people = self.system.authorized_pickups(child.id)
        options = [(p[0], f"{p[0]} ({p[1]}) - SĐT {p[2]}") for p in people]
        options.append(("__other__", "Người KHÔNG có trong danh sách"))
        name = io.ask_choice(f"Người đến đón {child.full_name}", options)
        if name == "__other__":
            name = io.ask_text("Họ tên người đến đón (để ghi nhật ký)")
        result = self.system.verify_pickup(child.id, name)
        io.success(f"Hợp lệ - giao trẻ cho {result}.")
