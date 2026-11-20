"""Hệ thống Phụ huynh: theo dõi một ngày của con, nhật ký ăn ngủ, trao đổi với cô (lời nhắn, dặn thuốc, xin nghỉ),
thực đơn, học phí và đăng ký dịch vụ, sức khỏe - phát triển."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from ...auth.user import Permission
from ...daily.records import MessageKind
from ...people.child import Child
from ...utils import format_date, format_percent, format_table, format_vnd, month_label, weekday_name
from .base_tab import BaseTab
from .report_view import ReportView
from .widgets import COLORS, DataTable, Field

P = Permission


def _hhmm(stamp: str) -> str:
    return stamp[11:16] if stamp and len(stamp) >= 16 else ""


class ParentTab(BaseTab):
    group = "Con của tôi"
    permission = P.PARENT_PORTAL

    def child_bar(self) -> ttk.Frame:
        bar = self.bar()
        ttk.Label(bar, text="Con:").pack(side="left")
        self.m_cbo_child = ttk.Combobox(bar, state="readonly", width=40)
        self.m_cbo_child.pack(side="left", padx=4)
        self.m_cbo_child.bind("<<ComboboxSelected>>", self._on_child)
        return bar

    def _on_child(self, _event: Any = None) -> None:
        self.app.parent_child_id = self.m_cbo_child.get().split(" - ")[0]
        self.refresh()

    def child(self) -> Child | None:
        """Trẻ đang xem (chọn chung cho mọi tab của phụ huynh)."""
        kids = self.system.children_for(self.user)
        options = [f"{c.id} - {c.full_name} ({self.class_name(c.class_id)})" for c in kids]
        self.m_cbo_child["values"] = options
        current = getattr(self.app, "parent_child_id", None)
        chosen = next((c for c in kids if c.id == current), kids[0] if kids else None)
        if chosen is not None:
            self.app.parent_child_id = chosen.id
            self.m_cbo_child.set(next(o for o in options if o.startswith(chosen.id + " ")))
        return chosen

    def send_message(self, kind: MessageKind) -> None:
        child = self.child()
        if child is None:
            return
        tomorrow = date.today() + timedelta(days=1)
        if kind is MessageKind.MEDICINE:
            fields = [Field("for_date", "Ngày uống", "date", default=date.today()),
                      Field("medicine", "Tên thuốc"), Field("dosage", "Liều lượng (VD: 5 ml, 1 gói)"),
                      Field("time_text", "Giờ uống (VD: sau ăn trưa)"),
                      Field("content", "Dặn thêm cô giáo", "textarea", required=False)]
            title = "Dặn cô cho con uống thuốc"
        elif kind is MessageKind.LEAVE:
            fields = [Field("for_date", "Nghỉ từ ngày", "date", default=tomorrow),
                      Field("to_date", "Đến ngày", "date", default=tomorrow),
                      Field("content", "Lý do xin nghỉ")]
            title = "Xin cho con nghỉ học"
        else:
            fields = [Field("content", "Nội dung lời nhắn", "textarea", width=50)]
            title = "Gửi lời nhắn cho cô"
        self.form(f"{title} - {child.full_name}", fields,
                  lambda v: self.system.daily.parent_send(child.id, kind, **v),
                  success=f"Đã gửi {kind.value.lower()} cho cô giáo lớp {self.class_name(child.class_id)}.")


# =============================================================================
class ParentTodayTab(ParentTab):
    title = "Hôm nay của con"
    # Nhật ký, trao đổi, thực đơn, sức khỏe là phần xem chi tiết của "Hôm nay của con" -> chức năng con
    sub_tabs = ("ParentDiaryTab", "ParentMessagesTab", "ParentMenuTab", "ParentHealthTab")

    def build(self) -> None:
        bar = self.child_bar()
        self.button(bar, "Làm mới", self.refresh, side="right")
        self.m_fra_sub = self.sub_function_bar("Xem thêm về con:")
        self.m_txt_content = ReportView(self, height=22)
        self.m_txt_content.configure(highlightthickness=1, highlightbackground=COLORS["border"])
        self.m_txt_content.pack(fill="both", expand=True)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Gửi lời nhắn cho cô", lambda: self.send_message(MessageKind.NOTE), style="Accent.TButton")
        self.button(actions, "Dặn uống thuốc", lambda: self.send_message(MessageKind.MEDICINE))
        self.button(actions, "Xin nghỉ học", lambda: self.send_message(MessageKind.LEAVE))
        self.button(actions, "Phản hồi nhật ký hôm nay", self.reply_today)

    def refresh(self) -> None:
        child = self.child()
        lines: list[str] = []
        if child is None:
            lines.append("Tài khoản chưa gắn với trẻ nào đang học. Vui lòng liên hệ nhà trường.")
        else:
            s, today = self.system, date.today()
            teacher = s.classes.homeroom_teacher(child.class_id) if child.class_id else None
            lines += [f"{child.full_name} - {child.age_text} - lớp {self.class_name(child.class_id)}",
                      f"Cô chủ nhiệm: {teacher.full_name + ' (' + teacher.phone + ')' if teacher else '-'}",
                      f"{weekday_name(today)} {format_date(today)}", ""]
            if not s.calendar.is_school_day(today):
                lines.append(f"Hôm nay trường nghỉ: {s.calendar.reason_not_school_day(today)}")
            else:
                record = s.attendance.get_record(child.id, today)
                leave = s.attendance.leave_for(child.id, today)
                lines.append("① ĐẾN TRƯỜNG: " + (
                    f"lúc {_hhmm(record.arrived_at)}, người đưa: {record.brought_by}, cô nhận: {record.received_by}"
                    if record and record.checked_in else
                    (record.status.value if record and not record.is_present else
                     ("Nghỉ có phép theo đơn" if leave else "Chưa đến trường"))))
                lines.append("② ĐIỂM DANH: " + (record.status.value + (f" ({record.note})" if record.note else "")
                                                if record else "Chưa điểm danh"))
                log = s.daily.log_of(child.id, today)
                if log and log.is_sent:
                    s.daily.parent_open_log(log.id)
                    lines.append("③ ĂN - NGỦ - SINH HOẠT (cô gửi lúc " + _hhmm(log.sent_at) + "):")
                    lines += ["   " + line for line in log.summary_text().splitlines()[1:]]
                else:
                    lines.append("③ ĂN - NGỦ - SINH HOẠT: cô sẽ cập nhật trong khoảng 10:30 - 14:00")
                lines.append("⑤ ĐÓN VỀ: " + (f"lúc {_hhmm(record.picked_up_at)}, người đón: {record.picked_up_by}"
                                            if record and record.picked_up else "Chưa đón"))
                menu = s.menus.menu_of(today)
                if menu:
                    meals = s.menus.meals_of(menu)
                    lines += ["", "THỰC ĐƠN HÔM NAY:"] + [f"   {t.value}: {', '.join(m.name for m in items) or '-'}"
                                                         for t, items in meals.items()]
                    warnings = [w for w in s.menus.allergy_warnings(today) if w.child.id == child.id]
                    lines += [f"   ⚠ {w.meal.name} có '{w.ingredient}' - con dị ứng {w.allergy.allergen}" for w in warnings]
            messages = [m for m in self.system.daily.messages_for_parent(child.id)
                        if m.created_at[:10] == date.today().isoformat() or m.needs_action]
            lines += ["", "④ TRAO ĐỔI VỚI CÔ HÔM NAY:"]
            lines += [f"   [{m.status.value}] {m.detail_text()}" + (f"\n      → Cô trả lời: {m.reply}" if m.reply else "")
                      for m in messages] or ["   Chưa có."]
        self.m_txt_content.render_plain("\n".join(lines), top="h2")

    def reply_today(self) -> None:
        child = self.child()
        log = self.system.daily.log_of(child.id, date.today()) if child else None
        if log is None or not log.is_sent:
            messagebox.showinfo("Chưa có nhật ký", "Cô chưa gửi nhật ký hôm nay.", parent=self)
            return
        self.form("Phản hồi / cập nhật tình hình của con",
                  [Field("text", "Nội dung (VD: tối qua bé ngủ muộn, nhờ cô để ý)", "textarea",
                         default=log.parent_reply or None, width=50)],
                  lambda v: self.system.daily.parent_reply_log(log.id, v["text"]), success="Đã gửi phản hồi cho cô.")


# =============================================================================
class ParentDiaryTab(ParentTab):
    title = "Nhật ký ăn ngủ"

    def build(self) -> None:
        self.child_bar()
        self.m_fg_list = DataTable(self, [("Ngày", 95), ("Ăn uống", 260), ("Giấc ngủ", 140), ("Tâm trạng", 90),
                                      ("Hoạt động / lời cô", 300), ("Phản hồi của tôi", 220)])
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.view)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Xem chi tiết", self.view)
        self.button(actions, "Phản hồi / cập nhật tình hình", self.reply, style="Accent.TButton")

    def refresh(self) -> None:
        child = self.child()
        logs = self.system.daily.logs_for_parent(child.id) if child else []
        self.m_fg_list.set_rows([[format_date(log.date), log.meals_text(), log.nap_text(), log.mood or "-",
                              " / ".join(x for x in (log.activities, log.teacher_note, log.health_note) if x),
                              log.parent_reply] for log in logs], [log.id for log in logs],
                            [None if log.parent_seen_at else "warn" for log in logs])

    def view(self) -> None:
        log_id = self.m_fg_list.selected_id()
        if log_id:
            log = self.system.daily.parent_open_log(log_id)
            self.app.save()
            self.show_text("Nhật ký ăn ngủ", log.summary_text())
            self.refresh()

    def reply(self) -> None:
        log_id = self.m_fg_list.selected_id()
        if not log_id:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một ngày trong bảng.", parent=self)
            return
        log = self.system.daily.logs.get(log_id)
        self.form(f"Phản hồi nhật ký ngày {format_date(log.date)}",
                  [Field("text", "Nội dung", "textarea", default=log.parent_reply or None, width=50)],
                  lambda v: self.system.daily.parent_reply_log(log.id, v["text"]), success="Đã gửi phản hồi cho cô.")


# =============================================================================
class ParentMessagesTab(ParentTab):
    title = "Trao đổi với cô"

    def build(self) -> None:
        self.child_bar()
        self.m_fg_list = DataTable(self, [("Gửi lúc", 110), ("Loại", 110), ("Nội dung", 360), ("Người gửi", 150),
                                      ("Trạng thái", 100), ("Cô trả lời", 260)])
        self.m_fg_list.pack(fill="both", expand=True)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Gửi lời nhắn", lambda: self.send_message(MessageKind.NOTE), style="Accent.TButton")
        self.button(actions, "Dặn uống thuốc", lambda: self.send_message(MessageKind.MEDICINE))
        self.button(actions, "Xin nghỉ học", lambda: self.send_message(MessageKind.LEAVE))

    def refresh(self) -> None:
        child = self.child()
        items = self.system.daily.messages_for_parent(child.id) if child else []
        self.m_fg_list.set_rows([[m.created_at.replace("T", " ")[5:], m.kind.value, m.detail_text(), m.sender,
                              m.status.value, m.reply] for m in items], [m.id for m in items],
                            ["ok" if m.status.value == "Đã thực hiện" else None for m in items])


# =============================================================================
class ParentMenuTab(ParentTab):
    title = "Thực đơn tuần"

    def build(self) -> None:
        bar = self.child_bar()
        self.offset = 0
        self.button(bar, "Tuần sau ▶", lambda: self._shift(1), side="right")
        self.button(bar, "Tuần này", lambda: self._shift(None), side="right")
        self.button(bar, "◀ Tuần trước", lambda: self._shift(-1), side="right")
        self.m_fg_list = DataTable(self, [("Thứ", 55), ("Ngày", 90), ("Bữa sáng", 170), ("Bữa trưa", 380),
                                      ("Bữa xế", 150), ("Năng lượng", 90, "e")], height=7)
        self.m_fg_list.pack(fill="x")
        self.m_lbl_notes = ttk.Label(self, style="Muted.TLabel", justify="left")
        self.m_lbl_notes.pack(anchor="w", pady=8)

    def _shift(self, step: int | None) -> None:
        self.offset = 0 if step is None else self.offset + step
        self.refresh()

    def refresh(self) -> None:
        child = self.child()
        start = date.today() - timedelta(days=date.today().weekday()) + timedelta(days=7 * self.offset)
        _headers, rows = self.system.menus.week_table(start)
        self.m_fg_list.set_rows(rows)
        notes = []
        if child is not None:
            warnings = [w for w in self.system.menus.week_allergy_warnings(start) if w.child.id == child.id]
            notes = [f"⚠ {format_date(w.menu_date)} {w.meal.name}: có '{w.ingredient}' - con dị ứng "
                     f"{w.allergy.allergen} (nhà trường sẽ thay món cho con)" for w in warnings]
        self.m_lbl_notes.configure(text="\n".join(notes) or "Thực đơn tuần này không có món chứa chất con bị dị ứng.")


# =============================================================================
class ParentFeesTab(ParentTab):
    title = "Học phí & dịch vụ"

    def build(self) -> None:
        self.child_bar()
        ttk.Label(self, text="Hóa đơn học phí", style="Section.TLabel").pack(anchor="w")
        self.m_fg_invoices = DataTable(self, [("Mã HĐ", 70), ("Kỳ", 80), ("Phải nộp", 110, "e"), ("Đã nộp", 110, "e"),
                                         ("Còn nợ", 110, "e"), ("Trạng thái", 200), ("Hạn nộp", 90)], height=6)
        self.m_fg_invoices.pack(fill="x")
        self.m_fg_invoices.on_double_click(self.detail)
        bar = self.bar(pady=(6, 10))
        self.button(bar, "Xem chi tiết hóa đơn", self.detail)
        self.m_lbl_debt = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_debt.pack(side="right")
        ttk.Label(self, text="Dịch vụ tự chọn của nhà trường", style="Section.TLabel").pack(anchor="w")
        self.m_fg_services = DataTable(self, [("Dịch vụ", 260), ("Giá / tháng", 120, "e"), ("Con đã đăng ký", 120, "center")],
                                  height=6)
        self.m_fg_services.pack(fill="x")
        bar = self.bar(pady=(6, 0))
        self.button(bar, "Đăng ký dịch vụ cho con", lambda: self.toggle(True), style="Accent.TButton")
        self.button(bar, "Hủy dịch vụ", lambda: self.toggle(False))
        ttk.Label(bar, text="Áp dụng từ hóa đơn tháng sau.", style="Muted.TLabel").pack(side="left", padx=12)

    def refresh(self) -> None:
        child = self.child()
        if child is None:
            return
        invoices = self.system.invoices.invoices_of_child(child.id)
        self.m_fg_invoices.set_rows([[i.id, i.period_label, format_vnd(i.total), format_vnd(i.paid_amount),
                                 format_vnd(i.balance), i.status_text(), format_date(i.due_date)] for i in invoices],
                               [i.id for i in invoices], ["warn" if i.is_overdue() else None for i in invoices])
        self.m_lbl_debt.configure(text=f"Tổng còn nợ: {format_vnd(sum(i.balance for i in invoices))}")
        catalog = self.system.service_catalog()
        self.m_fg_services.set_rows([[name, format_vnd(price), "✔" if name in child.extra_services else ""]
                                for name, price, _count in catalog], [name for name, _p, _c in catalog])

    def detail(self) -> None:
        invoice = self.selected(self.m_fg_invoices, self.system.invoices.get, "một hóa đơn")
        if invoice is not None:
            self.show_text(f"Hóa đơn {invoice.id}", invoice.detail_text())

    def toggle(self, register: bool) -> None:
        child = self.child()
        service = self.m_fg_services.selected_id()
        if child is None or not service:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một dịch vụ trong bảng.", parent=self)
            return
        price = self.system.settings.extra_services.get(service, 0)
        question = (f"Đăng ký '{service}' ({format_vnd(price)}/tháng) cho {child.full_name}?" if register
                    else f"Hủy dịch vụ '{service}' của {child.full_name}?")
        if self.confirm(question):
            self.guard(self.system.set_child_service, child.id, service, register,
                       success="Đã đăng ký dịch vụ - áp dụng từ hóa đơn tháng sau." if register else "Đã hủy dịch vụ.")


# =============================================================================
class ParentHealthTab(ParentTab):
    title = "Sức khỏe & chuyên cần"

    def build(self) -> None:
        self.child_bar()
        self.m_txt_content = ReportView(self)
        self.m_txt_content.configure(highlightthickness=1, highlightbackground=COLORS["border"])
        self.m_txt_content.pack(fill="both", expand=True)

    def refresh(self) -> None:
        child = self.child()
        parts: list[str] = []
        if child is not None:
            s = self.system
            rows = [[format_date(i["record"].measure_date), i["record"].height_cm, i["record"].weight_kg,
                     i["record"].bmi_text, i["status"].value] for i in s.health.growth_history(child.id)]
            parts.append(format_table(["Ngày đo", "Cao (cm)", "Nặng (kg)", "BMI", "Đánh giá"], rows,
                                      title=f"Quá trình phát triển - {child.full_name}"))
            allergies = s.health.allergies_of(child.id)
            parts.append("\nDị ứng: " + ("; ".join(f"{a.allergen} (mức {a.severity.value.lower()})" for a in allergies)
                                         or "không có"))
            today = date.today()
            stats = [x for x in s.attendance.monthly_stats(today.month, today.year, child.class_id)
                     if x["child_id"] == child.id]
            if stats:
                x = stats[0]
                parts.append(f"\nChuyên cần tháng {month_label(today.month, today.year)}: có mặt {x['present']}, "
                             f"nghỉ có phép {x['excused']}, nghỉ không phép {x['unexcused']} - tỷ lệ "
                             f"{format_percent(x['rate'])}")
        self.m_txt_content.render_plain("\n".join(parts), top="h2")
