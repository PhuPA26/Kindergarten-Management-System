"""Màn hình console - Hệ thống Phụ huynh: theo dõi con, nhật ký ăn ngủ, nhắn cô, dặn thuốc, xin nghỉ,
thực đơn, học phí, đăng ký dịch vụ, sức khỏe - chuyên cần."""
from __future__ import annotations

from datetime import date, timedelta

from ....daily.records import MessageKind
from ....exceptions import KindergartenError
from ....people.child import Child
from ....utils import format_date, format_percent, format_vnd, month_label, weekday_name
from ..menu import Menu
from .base import Screen


def _hhmm(stamp: str) -> str:
    return stamp[11:16] if stamp and len(stamp) >= 16 else ""


class ParentScreen(Screen):
    title = "Hệ thống Phụ huynh"

    def add_items(self, menu: Menu) -> Menu:
        return (menu
                .add("Hôm nay của con", self.today)
                .add("Nhật ký ăn ngủ các ngày (xem, phản hồi cô)", self.diary)
                .add("Gửi lời nhắn cho cô", lambda: self.send(MessageKind.NOTE))
                .add("Dặn cô cho con uống thuốc", lambda: self.send(MessageKind.MEDICINE))
                .add("Xin cho con nghỉ học", lambda: self.send(MessageKind.LEAVE))
                .add("Tin nhắn và thông báo của cô", self.messages)
                .add("Thực đơn tuần này", self.menu_week)
                .add("Học phí của con", self.fees)
                .add("Đăng ký / hủy dịch vụ cho con", self.services)
                .add("Sức khỏe và chuyên cần", self.health))

    def build_menu(self) -> Menu:
        return self.add_items(self.new_menu())

    def _child(self) -> Child:
        kids = self.system.children_for(self.user)
        if not kids:
            raise KindergartenError("Tài khoản chưa gắn với trẻ nào đang học. Vui lòng liên hệ nhà trường.")
        if len(kids) == 1:
            return kids[0]
        return self.select_child(kids, "Chọn con")

    def today(self) -> None:
        s, child, today = self.system, self._child(), date.today()
        teacher = s.classes.homeroom_teacher(child.class_id) if child.class_id else None
        io = self.io
        io.header(f"{child.full_name} - lớp {self.class_name(child.class_id)} - {weekday_name(today)} "
                  f"{format_date(today)}")
        io.info(f"Cô chủ nhiệm: {teacher.full_name} ({teacher.phone})" if teacher else "Chưa có cô chủ nhiệm")
        if not s.calendar.is_school_day(today):
            io.info(f"Hôm nay trường nghỉ: {s.calendar.reason_not_school_day(today)}")
        else:
            record = s.attendance.get_record(child.id, today)
            leave = s.attendance.leave_for(child.id, today)
            io.write("① Đến trường: " + (f"lúc {_hhmm(record.arrived_at)}, người đưa {record.brought_by}"
                                        if record and record.checked_in else
                                        "nghỉ có phép theo đơn" if leave else "chưa đến"))
            io.write("② Điểm danh: " + (record.status.value if record else "chưa điểm danh"))
            log = s.daily.log_of(child.id, today)
            if log and log.is_sent:
                s.daily.parent_open_log(log.id)
                io.write("③ " + log.summary_text().replace("\n", "\n   "))
            else:
                io.write("③ Ăn ngủ: cô sẽ cập nhật trong khoảng 10:30 - 14:00")
            io.write("⑤ Đón về: " + (f"lúc {_hhmm(record.picked_up_at)} - {record.picked_up_by}"
                                    if record and record.picked_up else "chưa đón"))
        for m in s.daily.messages_for_parent(child.id)[:5]:
            io.write(f"④ [{m.status.value}] {m.detail_text()}" + (f" -> Cô trả lời: {m.reply}" if m.reply else ""))

    def diary(self) -> None:
        io, child = self.io, self._child()
        logs = self.system.daily.logs_for_parent(child.id)
        log = self._require(io.choose(logs, lambda l: f"{format_date(l.date)}: {l.meals_text()} | {l.nap_text()}"
                                      + (" | đã phản hồi" if l.parent_reply else ""),
                                      "Chọn ngày để xem", "Cô chưa gửi nhật ký nào."))
        log = self.system.daily.parent_open_log(log.id)
        io.write(log.summary_text())
        if io.ask_yes_no("Phản hồi / cập nhật tình hình của con cho cô", default=False):
            self.system.daily.parent_reply_log(log.id, io.ask_text("Nội dung"))
            io.success("Đã gửi phản hồi cho cô.")

    def send(self, kind: MessageKind) -> None:
        io, child = self.io, self._child()
        values: dict = {}
        if kind is MessageKind.MEDICINE:
            values["for_date"] = io.ask_date("Ngày uống", date.today())
            values["medicine"] = io.ask_text("Tên thuốc")
            values["dosage"] = io.ask_text("Liều lượng (VD: 5 ml)")
            values["time_text"] = io.ask_text("Giờ uống (VD: sau ăn trưa)")
            values["content"] = io.ask_text("Dặn thêm", required=False) or ""
        elif kind is MessageKind.LEAVE:
            start = io.ask_date("Nghỉ từ ngày", date.today() + timedelta(days=1))
            values["for_date"], values["to_date"] = start, io.ask_date("Đến ngày", start)
            values["content"] = io.ask_text("Lý do xin nghỉ")
        else:
            values["content"] = io.ask_text("Nội dung lời nhắn")
        self.system.daily.parent_send(child.id, kind, **values)
        io.success(f"Đã gửi {kind.value.lower()} cho cô giáo lớp {self.class_name(child.class_id)}.")

    def messages(self) -> None:
        child = self._child()
        rows = [[m.created_at.replace("T", " ")[5:], m.kind.value, m.detail_text(), m.sender, m.status.value,
                 m.reply or "-"] for m in self.system.daily.messages_for_parent(child.id)]
        self.io.table(["Gửi lúc", "Loại", "Nội dung", "Người gửi", "Trạng thái", "Cô trả lời"], rows,
                      title=f"TRAO ĐỔI VỚI CÔ - {child.full_name.upper()}", max_width=40)

    def menu_week(self) -> None:
        child = self._child()
        self.io.write(self.system.menus.week_text(date.today()))
        for w in self.system.menus.week_allergy_warnings(date.today()):
            if w.child.id == child.id:
                self.io.warning(f"{format_date(w.menu_date)} {w.meal.name} có '{w.ingredient}' - con dị ứng "
                                f"{w.allergy.allergen} (nhà trường sẽ thay món)")

    def fees(self) -> None:
        child = self._child()
        invoices = self.system.invoices.invoices_of_child(child.id)
        self.io.table(["Mã HĐ", "Kỳ", "Phải nộp", "Đã nộp", "Còn nợ", "Trạng thái", "Hạn nộp"],
                      [[i.id, i.period_label, format_vnd(i.total), format_vnd(i.paid_amount), format_vnd(i.balance),
                        i.status_text(), format_date(i.due_date)] for i in invoices],
                      title=f"HỌC PHÍ - {child.full_name.upper()}")
        self.io.info(f"Tổng còn nợ: {format_vnd(sum(i.balance for i in invoices))}")

    def services(self) -> None:
        io, child = self.io, self._child()
        catalog = self.system.service_catalog()
        name = self._require(io.choose(
            catalog, lambda x: f"{x[0]} - {format_vnd(x[1])}/tháng"
            + (" [ĐÃ ĐĂNG KÝ]" if x[0] in child.extra_services else ""), "Chọn dịch vụ",
            "Nhà trường chưa có dịch vụ nào."))[0]
        registered = name in child.extra_services
        if self.confirm(f"{'Hủy' if registered else 'Đăng ký'} dịch vụ {name} cho {child.full_name}"):
            self.system.set_child_service(child.id, name, not registered)
            io.success("Đã cập nhật - áp dụng từ hóa đơn tháng sau.")

    def health(self) -> None:
        s, child, today = self.system, self._child(), date.today()
        rows = [[format_date(i["record"].measure_date), i["record"].height_cm, i["record"].weight_kg,
                 i["record"].bmi_text, i["status"].value] for i in s.health.growth_history(child.id)]
        self.io.table(["Ngày đo", "Cao (cm)", "Nặng (kg)", "BMI", "Đánh giá"], rows,
                      title=f"PHÁT TRIỂN - {child.full_name.upper()}")
        allergies = s.health.allergies_of(child.id)
        self.io.info("Dị ứng: " + ("; ".join(a.allergen for a in allergies) or "không có"))
        stats = [x for x in s.attendance.monthly_stats(today.month, today.year, child.class_id)
                 if x["child_id"] == child.id]
        if stats:
            x = stats[0]
            self.io.info(f"Chuyên cần tháng {month_label(today.month, today.year)}: có mặt {x['present']}, "
                         f"có phép {x['excused']}, không phép {x['unexcused']} ({format_percent(x['rate'])})")
