"""Các tab: Học phí, Thực đơn, Báo cáo, Hệ thống."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from ...auth.user import Permission, Role, User
from ...classroom.classroom import AgeGroup
from ...exceptions import KindergartenError, ValidationError
from ...finance.invoice import PAYMENT_METHODS, Invoice, InvoiceStatus
from ...hr.employees import Teacher
from ...nutrition.meal import MealType
from ...reports.reports import REPORT_TYPES, DebtReport, Report
from ...utils import (format_date, format_rate, format_table, format_vnd, month_bounds, month_label, parse_float,
                      parse_money, parse_month, previous_month, weekday_name)
from .base_tab import BaseTab
from .report_view import ReportView
from .widgets import COLORS, FONTS, DataTable, Field, FormDialog, open_folder, px

P = Permission


# =============================================================================
class FinanceTab(BaseTab):
    title = "Học phí"
    permission = P.MANAGE_FINANCE
    # Dịch vụ (bán trú, năng khiếu...) là khoản thu trên hóa đơn học phí: mở từ Học phí, có nút Quay lại
    sub_tabs = ("ServicesTab",)

    def build(self) -> None:
        self.m_fra_sub = self.sub_function_bar("Chức năng con:", pady=(0, 8))
        bar = self.bar()
        ttk.Label(bar, text="Tháng (mm/yyyy):").pack(side="left")
        today = date.today()
        self.month_var = tk.StringVar(value=month_label(*previous_month(today.month, today.year)))
        entry = ttk.Entry(bar, textvariable=self.month_var, width=10)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Trạng thái:").pack(side="left")
        self.m_cbo_status = ttk.Combobox(bar, state="readonly", width=22,
                                       values=["Tất cả"] + [s.value for s in InvoiceStatus] + ["Quá hạn"])
        self.m_cbo_status.set("Tất cả")
        self.m_cbo_status.pack(side="left", padx=(4, 12))
        self.m_cbo_status.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.button(bar, "Xem", self.refresh)
        self.m_fg_list = DataTable(self, [("Mã HĐ", 65), ("Trẻ", 170), ("Lớp", 120), ("Kỳ", 70, "center"),
                                      ("Phải nộp", 100, "e"), ("Đã nộp", 100, "e"), ("Còn nợ", 100, "e"),
                                      ("Trạng thái", 200), ("Hạn nộp", 85)])
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.detail)
        self.m_lbl_summary = ttk.Label(self, style="Muted.TLabel")
        self.m_lbl_summary.pack(anchor="w", pady=(4, 0))
        actions = self.bar(pady=(6, 0))
        self.button(actions, "Thu tiền", self.pay, style="Accent.TButton")
        self.button(actions, "Chi tiết", self.detail)
        self.button(actions, "Hủy phiếu thu nhầm", self.void_payment)
        self.button(actions, "Tính lại hóa đơn", self.recalculate)
        self.button(actions, "Xóa hóa đơn", self.delete)
        more = self.bar(pady=(6, 0))
        self.button(more, "Tạo hóa đơn cả trường", self.generate)
        self.button(more, "Tạo hóa đơn 1 trẻ", self.create_one)
        self.button(more, "Tra cứu công nợ", self.lookup)
        self.button(more, "Phụ huynh còn nợ", self.debtors)
        self.button(more, "Cấu hình học phí / lương", self.settings)

    def _month(self) -> tuple[int, int] | None:
        try:
            return parse_month(self.month_var.get())
        except KindergartenError as exc:
            messagebox.showerror("Tháng không hợp lệ", exc.message, parent=self)
            return None

    def refresh(self) -> None:
        period = self._month()
        if period is None:
            return
        invoices = self.system.invoices.invoices_of_month(*period)
        status = self.m_cbo_status.get()
        if status == "Quá hạn":
            invoices = [i for i in invoices if i.is_overdue()]
        elif status != "Tất cả":
            invoices = [i for i in invoices if i.status.value == status]
        rows, tags = [], []
        for i in invoices:
            rows.append([i.id, i.child_name, i.class_name, i.period_label, format_vnd(i.total),
                         format_vnd(i.paid_amount), format_vnd(i.balance), i.status_text(), format_date(i.due_date)])
            tags.append("warn" if i.is_overdue() else "ok" if i.status is InvoiceStatus.PAID
                        else "muted" if i.provisional else None)
        self.m_fg_list.set_rows(rows, [i.id for i in invoices], tags)
        provisional = sum(1 for i in invoices if i.provisional)
        self.m_lbl_summary.configure(text=f"{len(invoices)} hóa đơn | Phải nộp {format_vnd(sum(i.total for i in invoices))}"
                                    f" | Đã nộp {format_vnd(sum(i.paid_amount for i in invoices))}"
                                    f" | Còn nợ {format_vnd(sum(i.balance for i in invoices))}"
                                    + (f" | {provisional} hóa đơn tạm tính" if provisional else ""))

    def _selected_invoice(self) -> Invoice | None:
        return self.selected(self.m_fg_list, self.system.invoices.get, "một hóa đơn")

    def _unfinished_note(self, period: tuple[int, int]) -> str:
        if month_bounds(*period)[1] >= date.today():
            return ("\n\nLưu ý: tháng chưa kết thúc - hóa đơn là TẠM TÍNH (tiền ăn theo số ngày có mặt đến hôm nay). "
                    "Dùng 'Tính lại hóa đơn' khi hết tháng nếu chưa thu tiền.")
        return ""

    def generate(self) -> None:
        period = self._month()
        if period is None:
            return
        if not self.confirm(f"Tạo hóa đơn tháng {month_label(*period)} cho tất cả trẻ đang học?"
                            f"{self._unfinished_note(period)}"):
            return
        result = self.guard(self.system.invoices.generate_monthly_invoices, *period)
        if result is not None:
            created, skipped = result
            messagebox.showinfo("Hoàn tất", f"Đã tạo {len(created)} hóa đơn, tổng phải thu "
                                            f"{format_vnd(sum(i.total for i in created))}.\n"
                                            f"Bỏ qua {len(skipped)} trẻ đã có hóa đơn hoặc nhập học sau tháng này.",
                                parent=self)

    def create_one(self) -> None:
        period = self._month()
        if period is None:
            return
        children = [c for c in self.system.children.all_sorted() if c.class_id]
        fields = [Field("child_id", "Trẻ", "choice", self.child_options(children))]
        invoice = self.form(f"Tạo hóa đơn tháng {month_label(*period)}", fields,
                            lambda v: self.system.invoices.create_invoice(v["child_id"], *period))
        if invoice is not None:
            self.show_text(f"Hóa đơn {invoice.id}", invoice.detail_text() + self._unfinished_note(period))

    def detail(self) -> None:
        invoice = self._selected_invoice()
        if invoice is not None:
            self.show_text(f"Hóa đơn {invoice.id}", invoice.detail_text())

    def recalculate(self) -> None:
        """L03: tính lại hóa đơn tạm tính / chưa thu theo điểm danh và bảng giá hiện tại."""
        invoice = self._selected_invoice()
        if invoice is None:
            return
        old_total = invoice.total
        if self.guard(self.system.invoices.recalculate, invoice.id) is None:
            return
        self.system.audit("Tính lại hóa đơn", invoice.id, {"old": old_total, "new": invoice.total})
        self.show_text(f"Hóa đơn {invoice.id}", f"Đã tính lại: {format_vnd(old_total)} -> {format_vnd(invoice.total)}"
                                                f"\n\n{invoice.detail_text()}")

    def pay(self) -> None:
        invoice = self._selected_invoice()
        if invoice is None:
            return
        if invoice.balance <= 0:
            messagebox.showinfo("Đã thanh toán", f"Hóa đơn {invoice.id} đã thanh toán đủ.", parent=self)
            return
        fields = [Field("amount", f"Số tiền nộp (còn nợ {format_vnd(invoice.balance)})", "money",
                        default=invoice.balance),
                  Field("method", "Hình thức", "choice", [(m, m) for m in PAYMENT_METHODS], PAYMENT_METHODS[0]),
                  Field("pay_date", "Ngày nộp", "date", default=date.today()),
                  Field("note", "Ghi chú", required=False)]

        def submit(values: dict[str, Any]):
            amount = parse_money(values["amount"], "Số tiền nộp", allow_zero=False)
            # U08: bước xác nhận cuối trước khi ghi nhận
            if not messagebox.askyesno("Xác nhận thu tiền",
                                       f"Thu {format_vnd(amount)} ({values['method'].lower()}) cho hóa đơn {invoice.id}"
                                       f" - {invoice.child_name}, ngày {values['pay_date']}?",
                                       parent=self.focus_get() or self):
                raise KindergartenError("Chưa ghi nhận thanh toán - bạn có thể sửa lại thông tin.")
            return self.system.record_payment(invoice.id, amount, values["method"], values["pay_date"], values["note"])

        payment = self.form(f"Thu tiền hóa đơn {invoice.id} - {invoice.child_name}", fields, submit)
        if payment is not None:
            self.show_text(f"Phiếu thu {payment.id}", invoice.receipt_text(payment))

    def void_payment(self) -> None:
        """L16: hủy phiếu thu ghi nhầm - giữ dấu vết, bắt buộc nhập lý do."""
        invoice = self._selected_invoice()
        if invoice is None:
            return
        if not invoice.valid_payments:
            messagebox.showinfo("Không có phiếu thu", f"Hóa đơn {invoice.id} chưa có phiếu thu nào.", parent=self)
            return
        options = [(p.id, f"{p.id} - {format_date(p.pay_date)} - {format_vnd(p.amount)} ({p.method}, "
                          f"người thu {p.collected_by or '-'})") for p in invoice.valid_payments]
        fields = [Field("payment_id", "Phiếu thu cần hủy", "choice", options, options[-1][0], width=56),
                  Field("reason", "Lý do hủy")]
        self.form(f"Hủy phiếu thu - hóa đơn {invoice.id}", fields,
                  lambda v: self.system.void_payment(invoice.id, v["payment_id"], v["reason"]),
                  success=lambda p: f"Đã hủy phiếu thu {p.id}. Hóa đơn còn nợ {format_vnd(invoice.balance)}.",
                  submit_text="Hủy phiếu thu")

    def delete(self) -> None:
        invoice = self._selected_invoice()
        if invoice and self.confirm(f"Xóa hóa đơn {invoice.id} ({invoice.child_name}, tháng {invoice.period_label})?"):
            self.guard(self.system.invoices.remove, invoice.id, success="Đã xóa hóa đơn.")

    def lookup(self) -> None:
        keyword = self.form("Tra cứu công nợ", [Field("keyword", "Tên trẻ / tên hoặc SĐT phụ huynh / mã HĐ")],
                            lambda v: v["keyword"], submit_text="Tra cứu", save=False)
        if keyword:
            invoices = self.system.invoices.debt_lookup(keyword)
            rows = [[i.id, i.child_name, i.period_label, format_vnd(i.total), format_vnd(i.balance),
                     format_date(i.due_date), i.status_text()] for i in invoices]
            text = format_table(["Mã HĐ", "Trẻ", "Kỳ", "Phải nộp", "Còn nợ", "Hạn nộp", "Trạng thái"], rows,
                                title=f"CÔNG NỢ KHỚP '{keyword}'")
            self.show_text("Tra cứu công nợ", f"{text}\nTổng còn nợ: {format_vnd(sum(i.balance for i in invoices))}")

    def debtors(self) -> None:
        report = DebtReport(self.system)
        self.show_text(report.title, report.to_text(), report)

    def settings(self) -> None:
        """Học phí, miễn giảm, lương. Dịch vụ tự chọn quản lý ở mục 'Dịch vụ' (thêm/sửa/xóa, đăng ký cho trẻ)."""
        cfg = self.system.settings
        fields = [Field("monthly_tuition", "Học phí tháng - mức chung (đ)", "money", default=cfg.monthly_tuition),
                  Field("meal_rate_per_day", "Tiền ăn mỗi ngày (đ)", "money", default=cfg.meal_rate_per_day),
                  # L17: hiển thị đủ chữ số (12,5%) để không bị làm tròn khi chỉ bấm Lưu
                  Field("second_child_rate", "Giảm con thứ hai (%)", default=format_rate(cfg.second_child_rate)),
                  Field("poor_household_rate", "Giảm hộ nghèo (%)", default=format_rate(cfg.poor_household_rate)),
                  Field("due_days", "Hạn nộp (số ngày)", default=cfg.due_days)]
        fields += [Field(f"group_{g.name}", f"Học phí riêng khối {g.label} (trống = mức chung)", "money",
                         default=cfg.tuition_by_group.get(g.label), required=False) for g in AgeGroup]
        fields += [Field("base_salary_unit", "Lương cơ sở (đ)", "money", default=cfg.base_salary_unit),
                   Field("teacher_incentive_rate", "Ưu đãi nghề giáo viên (%)",
                         default=format_rate(cfg.teacher_incentive_rate)),
                   Field("homeroom_allowance", "Phụ cấp chủ nhiệm (đ)", "money", default=cfg.homeroom_allowance)]

        def rate(value: str, label: str) -> float:
            return parse_float(value, label, 0, 100) / 100

        def submit(values: dict[str, Any]) -> None:
            self.system.update_fee_settings(
                monthly_tuition=values["monthly_tuition"], meal_rate_per_day=values["meal_rate_per_day"],
                second_child_rate=rate(values["second_child_rate"], "Giảm con thứ hai"),
                poor_household_rate=rate(values["poor_household_rate"], "Giảm hộ nghèo"),
                due_days=values["due_days"], base_salary_unit=values["base_salary_unit"],
                teacher_incentive_rate=rate(values["teacher_incentive_rate"], "Ưu đãi nghề giáo viên"),
                homeroom_allowance=values["homeroom_allowance"],
                tuition_by_group={g.label: values[f"group_{g.name}"] for g in AgeGroup if values[f"group_{g.name}"]})

        self.form("Cấu hình học phí, miễn giảm và lương", fields, submit,
                  success="Đã lưu cấu hình. Học phí áp dụng cho hóa đơn tạo từ bây giờ; "
                          "lương áp dụng cho các kỳ chưa chốt.")


# =============================================================================
class MenuDayDialog(tk.Toplevel):
    """Lập thực đơn một ngày: chọn nhiều món cho từng bữa (chỉ hiện món đang dùng + món đã có trong ngày)."""

    def __init__(self, tab: "MenuTab", day: date) -> None:
        super().__init__(tab)
        self.tab, self.day = tab, day
        self.title(f"Thực đơn {weekday_name(day)} {format_date(day)}")
        self.transient(tab.winfo_toplevel())
        self.saved = False
        self.warnings: list = []
        menus = tab.system.menus
        menu = menus.menu_of(day)
        used = set(menu.all_meal_ids()) if menu else set()
        self.meals = [m for m in menus.meals_sorted(include_hidden=True) if m.active or m.id in used]   # L13
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        self.lists: dict[MealType, tk.Listbox] = {}
        self.initial: dict[MealType, list[str]] = {}
        for column, meal_type in enumerate(MealType):
            ttk.Label(body, text=meal_type.value, style="Section.TLabel").grid(row=0, column=column, sticky="w")
            listbox = tk.Listbox(body, selectmode="multiple", exportselection=False, height=16, width=30)
            current = menu.meals_of(meal_type) if menu else []
            self.initial[meal_type] = list(current)
            for index, meal in enumerate(self.meals):
                listbox.insert("end", f"{meal.name} ({meal.calories} kcal)" + ("" if meal.active else " [đã ẩn]"))
                if meal.id in current:
                    listbox.selection_set(index)
            listbox.grid(row=1, column=column, padx=(0, 8), sticky="nsew")
            self.lists[meal_type] = listbox
        buttons = ttk.Frame(body)
        buttons.grid(row=2, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Hủy", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Lưu thực đơn", style="Accent.TButton", command=self.save).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    def save(self) -> None:
        plan = {t: [self.meals[i].id for i in lb.curselection()] for t, lb in self.lists.items()}
        if all(sorted(plan[t]) == sorted(self.initial[t]) for t in plan):
            self.destroy()   # U09: không thay đổi -> không ghi
            return
        try:
            self.warnings = self.tab.system.menus.plan_day(self.day, plan)
        except KindergartenError as exc:
            messagebox.showerror("Không lưu được", exc.message, parent=self)
            return
        self.saved = True
        self.destroy()


class MealsDialog(tk.Toplevel):
    """Danh mục món ăn. Món đã dùng trong thực đơn không xóa được - chỉ ẩn (L13)."""

    def __init__(self, tab: "MenuTab") -> None:
        super().__init__(tab)
        self.tab = tab
        self.title("Danh mục món ăn")
        self.geometry(f"{px(820)}x{px(440)}")
        self.transient(tab.winfo_toplevel())
        self.m_fg_list = DataTable(self, [("Mã", 60), ("Tên món", 200), ("Kcal", 60, "e"), ("Thành phần", 360),
                                      ("Trạng thái", 80)])
        self.m_fg_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.m_fg_list.on_double_click(self.edit)
        bar = ttk.Frame(self, padding=(8, 0, 8, 8))
        bar.pack(fill="x")
        manage = tab.can(P.MANAGE_MENU)
        for text, command in (("Thêm món", self.add), ("Sửa", self.edit), ("Ẩn / hiện", self.toggle),
                              ("Xóa", self.delete)):
            button = ttk.Button(bar, text=text, command=command)
            button.pack(side="left", padx=(0, 6))
            if not manage:
                button.state(["disabled"])
        ttk.Button(bar, text="Đóng", command=self.destroy).pack(side="right")
        self.reload()

    def reload(self) -> None:
        meals = self.tab.system.menus.meals_sorted(include_hidden=True)
        self.m_fg_list.set_rows([[m.id, m.name, m.calories, m.ingredients_text, "Đang dùng" if m.active else "Đã ẩn"]
                             for m in meals], [m.id for m in meals], [None if m.active else "muted" for m in meals])

    def _fields(self, meal=None) -> list[Field]:
        return [Field("name", "Tên món", default=meal.name if meal else None),
                Field("calories", "Năng lượng (kcal/suất)", default=meal.calories if meal else None),
                Field("ingredients", "Thành phần (cách nhau dấu phẩy)", default=meal.ingredients_text if meal else None),
                Field("description", "Mô tả", default=meal.description if meal else None, required=False)]

    def _selected(self):
        return self.tab.selected(self.m_fg_list, self.tab.system.menus.meals.get, "một món")

    def add(self) -> None:
        self.tab.form("Thêm món ăn", self._fields(), lambda v: self.tab.system.menus.add_meal(**v))
        self.reload()

    def edit(self) -> None:
        meal = self._selected()
        if meal is None or not self.tab.can(P.MANAGE_MENU):
            return

        def submit(values: dict[str, Any]):
            ingredients = [i.strip() for i in values.pop("ingredients").split(",") if i.strip()]
            changes = self.tab.changed(meal, values)
            if ingredients != list(meal.ingredients):
                changes["ingredients"] = ingredients
            return self.tab.system.menus.meals.update(meal.id, **changes) if changes else meal

        self.tab.form(f"Sửa món {meal.name}", self._fields(meal), submit)
        self.reload()

    def toggle(self) -> None:
        meal = self._selected()
        if meal is not None:
            self.tab.guard(self.tab.system.menus.set_meal_active, meal.id, not meal.active)
            self.reload()

    def delete(self) -> None:
        meal = self._selected()
        if meal is None:
            return
        menus = self.tab.system.menus
        used = menus.days_using_meal(meal.id)
        if used:   # L13: giữ lịch sử ăn uống - đề nghị ẩn thay vì xóa
            if meal.active and messagebox.askyesno(
                    "Món đã được dùng", f"Món '{meal.name}' đã có trong thực đơn {len(used)} ngày nên không xóa được "
                                       "(để giữ lịch sử).\nẨn món khỏi danh sách chọn?", parent=self):
                self.tab.guard(menus.set_meal_active, meal.id, False)
            self.reload()
            return
        if messagebox.askyesno("Xác nhận", f"Xóa món {meal.name}?", parent=self):
            self.tab.guard(menus.meals.remove, meal.id)
            self.reload()


class MenuTab(BaseTab):
    title = "Thực đơn"
    permission = P.VIEW_MENU

    def build(self) -> None:
        self.week_start = date.today() - timedelta(days=date.today().weekday())
        bar = self.bar()
        self.button(bar, "◀ Tuần trước", lambda: self.shift(-7))
        self.button(bar, "Tuần này", lambda: self.shift(None))
        self.button(bar, "Tuần sau ▶", lambda: self.shift(7))
        self.m_lbl_week = ttk.Label(bar, style="Section.TLabel")
        self.m_lbl_week.pack(side="left", padx=12)
        self.m_fg_list = DataTable(self, [("Thứ", 55), ("Ngày", 90), ("Bữa sáng", 170), ("Bữa trưa", 420),
                                      ("Bữa xế", 150), ("Năng lượng", 90, "e")], height=6)
        self.m_fg_list.pack(fill="x")
        self.m_fg_list.on_double_click(self.plan_day)
        actions = self.bar(pady=(8, 4))
        self.button(actions, "Lập / sửa thực đơn ngày đang chọn", self.plan_day, P.MANAGE_MENU, style="Accent.TButton")
        self.button(actions, "Sao chép thực đơn tuần trước sang tuần đang xem", self.copy_previous, P.MANAGE_MENU)
        self.button(actions, "Danh mục món ăn", self.open_meals)
        self.m_txt_warnings = ReportView(self, height=10)
        self.m_txt_warnings.configure(highlightthickness=1, highlightbackground=COLORS["border"])
        self.m_txt_warnings.pack(fill="both", expand=True)

    def shift(self, days: int | None) -> None:
        today = date.today()
        self.week_start = today - timedelta(days=today.weekday()) if days is None \
            else self.week_start + timedelta(days=days)
        self.refresh()

    def refresh(self) -> None:
        menus = self.system.menus
        week = menus.week_menus(self.week_start)
        days = [d for d, _ in week]
        self.m_lbl_week.configure(text=f"Tuần {format_date(days[0])} - {format_date(days[-1])}")
        _headers, rows = menus.week_table(self.week_start)
        cal = self.system.calendar
        self.m_fg_list.set_rows(rows, [d.isoformat() for d in days],
                            ["muted" if not cal.is_school_day(d) or menu is None else None for d, menu in week])
        # L09: giáo viên chỉ thấy cảnh báo cho trẻ lớp mình
        warnings = menus.week_allergy_warnings(self.week_start, class_ids=self.scope_class_ids())
        text = "\n".join(str(w) for w in warnings) or "Không có món nào chứa chất gây dị ứng cho trẻ."
        self.m_txt_warnings.render_plain(text, title="Cảnh báo dị ứng trong tuần", top="h2")

    def plan_day(self) -> None:
        if not self.can(P.MANAGE_MENU):
            return
        day_id = self.m_fg_list.selected_id()
        if not day_id:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một ngày trong bảng.", parent=self)
            return
        day = date.fromisoformat(day_id)
        try:
            self.system.menus.check_menu_day(day)   # L20: không mở hộp thoại cho ngày nghỉ
        except KindergartenError as exc:
            messagebox.showwarning("Không phải ngày học", exc.message, parent=self)
            return
        dialog = MenuDayDialog(self, day)
        self.wait_window(dialog)
        if dialog.saved:
            self.app.save()
            self.refresh()
            scope = self.scope_class_ids()
            warnings = [w for w in dialog.warnings if scope is None or w.child.class_id in scope]
            if warnings:
                messagebox.showwarning("Cảnh báo dị ứng", "\n".join(str(w) for w in warnings), parent=self)

    def copy_previous(self) -> None:
        source = self.week_start - timedelta(days=7)
        overwritten = self.system.menus.overwritten_days(self.week_start)
        note = ""
        if overwritten:
            note = ("\n\nCÁC NGÀY SAU ĐÃ CÓ THỰC ĐƠN VÀ SẼ BỊ GHI ĐÈ: "
                    + ", ".join(format_date(d) for d in overwritten))
        if self.confirm(f"Sao chép thực đơn tuần {format_date(source)} sang tuần {format_date(self.week_start)}?"
                        f"{note}"):
            self.guard(self.system.menus.copy_week, source, self.week_start,
                       success=lambda n: f"Đã sao chép thực đơn {n} ngày (bỏ qua ngày nghỉ).")

    def open_meals(self) -> None:
        self.wait_window(MealsDialog(self))
        self.app.save()
        self.refresh()


# =============================================================================


# =============================================================================
class SystemTab(BaseTab):
    title = "Hệ thống"
    permission = P.MANAGE_USERS

    def build(self) -> None:
        ttk.Label(self, text="Tài khoản người dùng", style="Section.TLabel").pack(anchor="w")
        self.m_fg_list = DataTable(self, [("Mã", 60), ("Tên đăng nhập", 120), ("Họ tên", 220), ("Vai trò", 110),
                                      ("Mã NS", 70), ("Trạng thái", 90), ("Đăng nhập gần nhất", 150)])
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.edit_user)
        self.master_bar(self.create_user, self.edit_user, self.delete, extras=[
            ("Khóa / mở khóa", self.toggle), ("Đặt lại mật khẩu", self.reset_password),
            ("Nhật ký thao tác", self.audit_log)])
        approve = self.bar(pady=(6, 0))
        self.m_lbl_pending = ttk.Label(approve, style="Section.TLabel")
        self.m_lbl_pending.pack(side="left", padx=(0, 8))
        self.button(approve, "Duyệt tài khoản đăng ký", self.approve, style="Accent.TButton")
        self.button(approve, "Từ chối", self.reject)
        data = ttk.LabelFrame(self, text="Dữ liệu", padding=8)
        data.pack(fill="x", pady=(12, 0))
        self.button(data, "Lưu dữ liệu ngay", self.save_now, P.MANAGE_DATA)
        self.button(data, "Sao lưu dữ liệu", self.backup, P.MANAGE_DATA)
        self.button(data, "Khôi phục từ bản sao lưu", self.restore, P.MANAGE_DATA)
        self.button(data, "Mở thư mục sao lưu", self.open_backup_folder)
        if self.app.seed_func is not None:
            self.button(data, "Nạp lại dữ liệu mẫu", self.reseed, P.MANAGE_DATA)
        self.m_lbl_meta = ttk.Label(data, style="Muted.TLabel")
        self.m_lbl_meta.pack(side="right")
        view = ttk.LabelFrame(self, text="Hiển thị", padding=8)
        view.pack(fill="x", pady=(8, 0))
        ttk.Label(view, text="Cỡ chữ:").pack(side="left")
        self.m_cbo_font_size = ttk.Combobox(view, state="readonly", width=5, values=["9", "10", "11", "12", "14"])
        self.m_cbo_font_size.set(str(FONTS["size"]))
        self.m_cbo_font_size.pack(side="left", padx=4)
        self.m_cbo_font_size.bind("<<ComboboxSelected>>", lambda _e: self.app.set_font_size(int(self.m_cbo_font_size.get())))
        ttk.Label(view, text="(phím tắt Ctrl+1..9 để chuyển tab)", style="Muted.TLabel").pack(side="left", padx=12)

    def refresh(self) -> None:
        users = sorted(self.system.auth, key=lambda u: (not u.pending, u.role.value, u.username))
        self.m_fg_list.set_rows([[u.id, u.username, u.full_name, u.role.label, u.employee_id or u.parent_id or "-",
                              u.status_text, u.last_login.replace("T", " ") if u.last_login else "-"] for u in users],
                            [u.id for u in users],
                            ["warn" if u.pending else None if u.active else "muted" for u in users])
        pending = len(self.system.auth.pending_users())
        self.m_lbl_pending.configure(text=f"{pending} tài khoản chờ duyệt" if pending else "Không có tài khoản chờ duyệt")
        meta = self.system.store.read_meta()
        self.m_lbl_meta.configure(text=f"Lần lưu gần nhất: {meta.get('saved_at', '-').replace('T', ' ')}")

    def _selected_user(self) -> User | None:
        return self.selected(self.m_fg_list, self.system.auth.get, "một tài khoản")

    @staticmethod
    def _employee_options(employees) -> list[tuple[str, str]]:
        return [(e.id, f"{e.id} - {e.full_name} ({e.role_name})") for e in employees]

    def create_user(self) -> None:
        # U06: chỉ hiện nhân sự chưa có tài khoản; L08: tài khoản giáo viên bắt buộc liên kết hồ sơ giáo viên
        employees = [(None, "(không liên kết - bắt buộc với giáo viên)")] + \
            self._employee_options(self.system.employees_without_account())
        linked_parents = {u.parent_id for u in self.system.auth if u.parent_id}
        parents = [(None, "(không - chỉ dùng cho tài khoản phụ huynh)")] + \
            self.parent_options([p for p in self.system.parents.all_sorted() if p.id not in linked_parents])
        fields = [Field("username", "Tên đăng nhập"),
                  Field("role", "Vai trò", "choice", [(r, r.label) for r in Role]),
                  Field("employee_id", "Liên kết hồ sơ nhân sự", "choice", employees, None, required=False),
                  Field("parent_id", "Liên kết hồ sơ phụ huynh", "choice", parents, None, required=False),
                  Field("full_name", "Họ tên hiển thị", required=False),
                  Field("password", "Mật khẩu (≥ 6 ký tự)", "password"),
                  Field("confirm", "Nhập lại mật khẩu", "password")]

        def submit(values: dict[str, Any]) -> User:
            if values.pop("confirm") != values["password"]:
                raise ValidationError("Hai lần nhập mật khẩu không khớp.")
            return self.system.create_user(**values)

        self.form("Tạo tài khoản", fields, submit,
                  success=lambda u: f"Đã tạo tài khoản {u}. Người dùng sẽ phải đổi mật khẩu khi đăng nhập lần đầu."
                  if getattr(u, "must_change_password", False) else f"Đã tạo tài khoản {u}.")

    def edit_user(self) -> None:
        """U01: sửa họ tên, vai trò, liên kết nhân sự của tài khoản."""
        user = self._selected_user()
        if user is None:
            return
        options = self.system.employees_without_account()
        if user.employee_id and self.system.employees.exists(user.employee_id):
            options = [self.system.employees.get(user.employee_id)] + options
        fields = [Field("full_name", "Họ tên hiển thị", default=user.full_name),
                  Field("role", "Vai trò", "choice", [(r, r.label) for r in Role], user.role),
                  Field("employee_id", "Liên kết hồ sơ nhân sự", "choice",
                        [(None, "(không liên kết)")] + self._employee_options(options), user.employee_id,
                        required=False)]

        def submit(values: dict[str, Any]) -> User:
            linked = self.system.employees.get_or_none(values["employee_id"]) if values["employee_id"] else None
            if values["role"] is Role.TEACHER and not isinstance(linked, Teacher):   # L08
                raise ValidationError("Tài khoản giáo viên phải liên kết với một hồ sơ giáo viên.")
            changes = {k: v for k, v in values.items() if v != getattr(user, k)}
            if changes:
                self.system.auth.update(user.id, **changes)
                self.system.audit("Sửa tài khoản", user.username, {k: str(v) for k, v in changes.items()})
            return user

        self.form(f"Sửa tài khoản {user.username}", fields, submit, success="Đã cập nhật tài khoản.")

    def approve(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        if not user.pending:
            messagebox.showinfo("Không cần duyệt", f"Tài khoản {user.username} không ở trạng thái chờ duyệt.",
                                parent=self)
            return
        employee = self.system.employees.get_or_none(user.employee_id) if user.employee_id else None
        if self.confirm(f"Duyệt tài khoản {user.username} - {user.role.label}"
                        + (f"\nHồ sơ nhân sự: {employee.full_name} ({employee.position}, SĐT {employee.phone})"
                           if employee else "") + "?"):
            self.guard(self.system.approve_user, user.id, success=f"Đã duyệt - {user.username} đăng nhập được ngay.")

    def reject(self) -> None:
        user = self._selected_user()
        if user is not None and user.pending and self.confirm(f"Từ chối và xóa yêu cầu tài khoản {user.username}?"):
            self.guard(self.system.reject_user, user.id, success="Đã từ chối.")

    def toggle(self) -> None:
        user = self._selected_user()
        if user is not None:
            self.guard(self.system.set_user_active, user.id, not user.active,
                       success=lambda u: f"Tài khoản {u.username} đã được {'mở khóa' if u.active else 'khóa'}.")

    def reset_password(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        fields = [Field("password", "Mật khẩu mới", "password"), Field("confirm", "Nhập lại", "password")]

        def submit(values: dict[str, Any]) -> User:
            if values["password"] != values["confirm"]:
                raise ValidationError("Hai lần nhập mật khẩu không khớp.")
            return self.system.reset_password(user.id, values["password"])

        self.form(f"Đặt lại mật khẩu cho {user.username}", fields, submit,
                  success="Đã đặt lại mật khẩu (người dùng sẽ phải đổi ở lần đăng nhập tới).")

    def delete(self) -> None:
        user = self._selected_user()
        if user and self.confirm_delete("tài khoản", [
                ("Mã tài khoản", user.id), ("Tên đăng nhập", user.username), ("Họ tên", user.full_name),
                ("Vai trò", user.role.label), ("Trạng thái", user.status_text)]):
            if self.guard(self.system.auth.remove, user.id, success="Đã xóa tài khoản.") is not None:
                self.system.audit("Xóa tài khoản", user.username)

    def audit_log(self) -> None:
        """K06: ai đã làm gì, lúc nào."""
        entries = self.system.audit_log.read(200)
        rows = [[e.get("at", "").replace("T", " "), e.get("user", ""), e.get("action", ""), e.get("target", ""),
                 str(e.get("detail") or "")] for e in entries]
        self.show_text("Nhật ký thao tác", format_table(["Thời điểm", "Người dùng", "Hành động", "Đối tượng",
                                                         "Chi tiết"], rows,
                                                        title="NHẬT KÝ THAO TÁC (200 dòng mới nhất)", max_width=60))

    def save_now(self) -> None:
        self.guard(self.system.save, success=lambda path: f"Đã lưu dữ liệu vào {path}")

    def backup(self) -> None:
        self.guard(self.system.backup, success=lambda path: f"Đã sao lưu vào {path}")

    def open_backup_folder(self) -> None:
        folder = self.system.store.backup_dir.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        open_folder(folder)

    def restore(self) -> None:
        """P07: khôi phục từ bản sao lưu; hiện trạng được sao lưu trước, sau đó đăng nhập lại."""
        backups = self.system.store.list_backups()
        if not backups:
            messagebox.showinfo("Chưa có bản sao lưu", "Chưa có bản sao lưu nào.", parent=self)
            return
        name = self.form("Khôi phục dữ liệu",
                         [Field("name", "Bản sao lưu", "choice", [(b, b) for b in backups], backups[0], width=44)],
                         lambda v: v["name"], submit_text="Tiếp tục", save=False)
        if not name or not self.confirm(f"Khôi phục dữ liệu từ {name}?\nDữ liệu hiện tại sẽ được sao lưu trước khi "
                                        "thay, sau đó bạn cần đăng nhập lại."):
            return
        try:
            self.system.restore_backup(name)
        except KindergartenError as exc:
            messagebox.showerror("Không khôi phục được", exc.message, parent=self)
            return
        messagebox.showinfo("Đã khôi phục", f"Đã khôi phục từ {name}. Vui lòng đăng nhập lại.", parent=self)
        self.app.show_login(save=False)

    def reseed(self) -> None:
        if not self.confirm("Toàn bộ dữ liệu hiện tại sẽ được sao lưu rồi thay bằng dữ liệu mẫu. Tiếp tục?"):
            return
        try:
            backup = self.system.backup()
            self.app.seed_func(self.system)
            self.system.save()
        except KindergartenError as exc:
            messagebox.showerror("Lỗi", exc.message, parent=self)
            return
        messagebox.showinfo("Đã nạp dữ liệu mẫu", f"Dữ liệu cũ đã sao lưu tại:\n{backup}\n\nVui lòng đăng nhập lại.",
                            parent=self)
        self.app.show_login(save=False)
