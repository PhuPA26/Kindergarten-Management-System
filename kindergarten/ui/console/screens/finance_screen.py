"""Màn hình console: học phí, hóa đơn, thanh toán, công nợ, miễn giảm (T21-T24)."""
from __future__ import annotations

from datetime import date

from ....auth.user import Permission
from ....classroom.classroom import AgeGroup
from ....exceptions import KindergartenError
from ....finance.invoice import PAYMENT_METHODS, Invoice, InvoiceStatus
from ....reports.reports import DebtReport
from ....utils import (format_date, format_rate, format_vnd, month_bounds, month_label, parse_float,
                       previous_month, validate_not_future)
from ..menu import Menu
from .base import Screen


class FinanceScreen(Screen):
    title = "Học phí & công nợ"

    def build_menu(self) -> Menu:
        P = Permission.MANAGE_FINANCE
        return (self.new_menu()
                .add("Tạo hóa đơn hàng loạt theo tháng (cả trường)", self.generate, P)
                .add("Tạo hóa đơn cho một trẻ", self.create_one, P)
                .add("Danh sách hóa đơn theo tháng", self.list_month, P)
                .add("Xem chi tiết hóa đơn", self.detail, P)
                .add("Tính lại hóa đơn tạm tính / chưa thu", self.recalculate, P)
                .add("Ghi nhận thanh toán", self.pay, P)
                .add("Hủy phiếu thu ghi nhầm", self.void_payment, P)
                .add("Tra cứu công nợ (theo tên trẻ / phụ huynh / SĐT)", self.lookup, P)
                .add("Danh sách phụ huynh còn nợ", self.debtors, P)
                .add("Xem chế độ miễn giảm của trẻ", self.discounts, P)
                .add("Danh mục dịch vụ: thêm / sửa / xóa", self.service_catalog, Permission.MANAGE_SERVICES)
                .add("Đăng ký / hủy dịch vụ cho trẻ", self.child_services, Permission.MANAGE_SERVICES)
                .add("Cấu hình học phí, dịch vụ, miễn giảm, lương", self.settings, P)
                .add("Xóa hóa đơn (chưa thanh toán)", self.delete, P))

    def _invoice_label(self, invoice: Invoice) -> str:
        return (f"{invoice.id} - {invoice.child_name} - tháng {invoice.period_label} - "
                f"tổng {format_vnd(invoice.total)}, còn nợ {format_vnd(invoice.balance)}")

    def _select_invoice(self, invoices: list[Invoice], title: str = "Chọn hóa đơn") -> Invoice:
        return self._require(self.io.choose(invoices, self._invoice_label, title, "Không có hóa đơn phù hợp."))

    def _ask_billing_month(self) -> tuple[int, int]:
        today = date.today()
        return self.io.ask_month("Tháng thu học phí", default=previous_month(today.month, today.year))

    def _warn_unfinished(self, month: int, year: int) -> None:
        if month_bounds(month, year)[1] >= date.today():
            self.io.warning(f"Tháng {month_label(month, year)} chưa kết thúc: hóa đơn là TẠM TÍNH (tiền ăn theo số "
                            "ngày có mặt đến hôm nay); dùng 'Tính lại hóa đơn' khi hết tháng nếu chưa thu tiền.")

    # ------------------------------------------------------------------ lập hóa đơn
    def generate(self) -> None:
        month, year = self._ask_billing_month()
        self._warn_unfinished(month, year)
        created, skipped = self.system.invoices.generate_monthly_invoices(month, year)
        rows = [[i.id, i.child_name, i.class_name, format_vnd(i.subtotal), format_vnd(i.discount_amount),
                 format_vnd(i.total)] for i in created]
        self.io.table(["Mã HĐ", "Trẻ", "Lớp", "Cộng", "Miễn giảm", "Phải nộp"], rows,
                      title=f"ĐÃ TẠO {len(created)} HÓA ĐƠN THÁNG {month_label(month, year)}")
        if skipped:
            self.io.info(f"Bỏ qua {len(skipped)} trẻ đã có hóa đơn tháng này hoặc nhập học sau tháng này.")
        self.io.success(f"Tổng phải thu: {format_vnd(sum(i.total for i in created))}.")

    def create_one(self) -> None:
        child = self.select_child([c for c in self.system.children.all_sorted() if c.class_id])
        month, year = self._ask_billing_month()
        self._warn_unfinished(month, year)
        invoice = self.system.invoices.create_invoice(child.id, month, year)
        self.io.write(invoice.detail_text())
        self.io.success(f"Đã tạo hóa đơn {invoice.id}.")

    def list_month(self) -> None:
        month, year = self.ask_month(previous=True)   # U05: hóa đơn mặc định tháng trước
        status = self.io.ask_choice("Lọc theo trạng thái", [("all", "Tất cả")] + [(s, s.value) for s in InvoiceStatus]
                                    + [("overdue", "Quá hạn")], default="all")
        invoices = self.system.invoices.invoices_of_month(month, year)
        if status == "overdue":
            invoices = [i for i in invoices if i.is_overdue()]
        elif status != "all":
            invoices = [i for i in invoices if i.status is status]
        rows = [[i.id, i.child_name, i.class_name, format_vnd(i.total), format_vnd(i.paid_amount),
                 format_vnd(i.balance), i.status_text(), format_date(i.due_date)] for i in invoices]
        self.io.table(["Mã HĐ", "Trẻ", "Lớp", "Phải nộp", "Đã nộp", "Còn nợ", "Trạng thái", "Hạn nộp"], rows,
                      title=f"HÓA ĐƠN THÁNG {month_label(month, year)} ({len(invoices)} hóa đơn)")
        self.io.info(f"Tổng phải nộp: {format_vnd(sum(i.total for i in invoices))} | "
                     f"Đã nộp: {format_vnd(sum(i.paid_amount for i in invoices))} | "
                     f"Còn nợ: {format_vnd(sum(i.balance for i in invoices))}")

    def _invoice_of_month(self, title: str = "Chọn hóa đơn") -> Invoice:
        """U07: chọn tháng trước rồi mới chọn hóa đơn (không in mọi hóa đơn từ trước tới nay)."""
        month, year = self.ask_month("Tháng của hóa đơn", previous=True)
        return self._select_invoice(self.system.invoices.invoices_of_month(month, year), title)

    def detail(self) -> None:
        self.io.write(self._invoice_of_month().detail_text())

    def recalculate(self) -> None:
        """L03: tính lại tiền ăn/phí của hóa đơn chưa thu theo điểm danh và bảng giá hiện tại."""
        invoice = self._invoice_of_month("Chọn hóa đơn cần tính lại")
        old_total = invoice.total
        self.system.invoices.recalculate(invoice.id)
        self.system.audit("Tính lại hóa đơn", invoice.id, {"old": old_total, "new": invoice.total})
        self.io.write(invoice.detail_text())
        self.io.success(f"Đã tính lại: {format_vnd(old_total)} -> {format_vnd(invoice.total)}.")

    # ------------------------------------------------------------------ thanh toán
    def pay(self) -> None:
        io = self.io
        invoice = self._select_invoice(self.system.invoices.unpaid_invoices(), "Chọn hóa đơn cần thu")
        io.write(invoice.detail_text())
        amount = io.ask_money("Số tiền nộp", invoice.balance, allow_zero=False)
        method = io.ask_choice("Hình thức", [(m, m) for m in PAYMENT_METHODS], PAYMENT_METHODS[0])
        paid_on = io.ask_date("Ngày nộp", date.today(), check=lambda d: validate_not_future(d, "Ngày nộp"))
        note = io.ask_text("Ghi chú", required=False) or ""
        # U08: bước xác nhận cuối trước khi ghi nhận
        if not self.confirm(f"Thu {format_vnd(amount)} ({method.lower()}) cho hóa đơn {invoice.id} - "
                            f"{invoice.child_name}, ngày {format_date(paid_on)}. Xác nhận"):
            io.warning("Chưa ghi nhận thanh toán.")
            return
        payment = self.system.record_payment(invoice.id, amount, method, paid_on, note)
        io.write(invoice.receipt_text(payment))
        io.success(f"Đã lập phiếu thu {payment.id}. Hóa đơn {invoice.id}: {invoice.status.value}.")

    def void_payment(self) -> None:
        """L16: hủy phiếu thu ghi nhầm - giữ dấu vết, cần lý do."""
        invoices = [i for i in self.system.invoices if i.valid_payments]
        invoice = self._select_invoice(sorted(invoices, key=lambda i: (i.year, i.month, i.id_sort_key), reverse=True),
                                       "Chọn hóa đơn có phiếu thu nhầm")
        payment = self._require(self.io.choose(
            invoice.valid_payments, lambda p: f"{p.id} - {format_date(p.pay_date)} - {format_vnd(p.amount)} "
                                              f"({p.method}, người thu {p.collected_by or '-'})",
            "Chọn phiếu thu cần hủy"))
        reason = self.io.ask_text("Lý do hủy")
        if self.confirm(f"Hủy phiếu thu {payment.id} ({format_vnd(payment.amount)})"):
            self.system.void_payment(invoice.id, payment.id, reason)
            self.io.success(f"Đã hủy phiếu thu {payment.id}. Hóa đơn còn nợ {format_vnd(invoice.balance)}.")

    def lookup(self) -> None:
        keyword = self.io.ask_text("Từ khóa (tên trẻ, tên/SĐT phụ huynh, mã hóa đơn)")
        invoices = self.system.invoices.debt_lookup(keyword)
        rows = [[i.id, i.child_name, i.period_label, format_vnd(i.total), format_vnd(i.balance),
                 format_date(i.due_date), i.status_text()] for i in invoices]
        self.io.table(["Mã HĐ", "Trẻ", "Kỳ", "Phải nộp", "Còn nợ", "Hạn nộp", "Trạng thái"], rows,
                      title=f"CÔNG NỢ KHỚP '{keyword}'")
        self.io.info(f"Tổng còn nợ: {format_vnd(sum(i.balance for i in invoices))}")

    def debtors(self) -> None:
        report = DebtReport(self.system)
        self.io.write(report.to_text())
        self.export_report(report)

    def delete(self) -> None:
        invoices = [i for i in self.system.invoices.unpaid_invoices() if not i.valid_payments]
        invoice = self._select_invoice(invoices, "Chọn hóa đơn cần xóa")
        if self.confirm(f"Xóa hóa đơn {invoice.id} ({invoice.child_name}, tháng {invoice.period_label})?"):
            self.system.invoices.remove(invoice.id)
            self.io.success("Đã xóa hóa đơn.")

    def discounts(self) -> None:
        child = self.select_child(self.system.children.all_sorted())
        discounts = self.system.invoices.applicable_discounts(child.id)
        siblings = self.system.children.siblings_of(child.id, active_only=True)
        self.io.info(f"Anh/chị/em ruột đang học: {', '.join(s.full_name for s in siblings) or 'không có'}")
        if not discounts:
            self.io.info(f"{child.full_name} không thuộc diện miễn giảm.")
            return
        for discount in discounts:
            self.io.info(f"  - {discount.describe()} ({discount.reason})")
        self.io.info("Nếu thuộc nhiều diện, hệ thống áp dụng mức giảm cao nhất.")

    # ------------------------------------------------------------------ dịch vụ
    def service_catalog(self) -> None:
        io = self.io
        catalog = self.system.service_catalog()
        io.table(["Dịch vụ", "Giá / tháng", "Số trẻ đăng ký"], [[n, format_vnd(p), c] for n, p, c in catalog],
                 title="DANH MỤC DỊCH VỤ")
        action = io.ask_choice("Thao tác", [("add", "Thêm dịch vụ mới"), ("edit", "Sửa tên / giá"),
                                            ("remove", "Xóa dịch vụ"), ("done", "Xong")], "add")
        if action == "add":
            name = self.system.save_service(io.ask_text("Tên dịch vụ (VD: Bơi lội)"), io.ask_money("Giá mỗi tháng"))
            io.success(f"Đã thêm dịch vụ {name}.")
        elif action in ("edit", "remove"):
            name = self._require(io.choose([n for n, _p, _c in catalog], str, "Chọn dịch vụ"))
            if action == "edit":
                new = self.system.save_service(io.ask_text("Tên mới", name),
                                               io.ask_money("Giá mỗi tháng", self.system.settings.extra_services[name]),
                                               old_name=name)
                io.success(f"Đã cập nhật dịch vụ {new}.")
            elif self.confirm(f"Xóa dịch vụ {name} (gỡ đăng ký của {len(self.system.children_using_service(name))} trẻ)"):
                self.system.remove_service(name)
                io.success("Đã xóa dịch vụ.")

    def child_services(self) -> None:
        io = self.io
        child = self.select_child(self.system.children.all_sorted())
        catalog = self.system.service_catalog()
        name = self._require(io.choose(
            catalog, lambda x: f"{x[0]} - {format_vnd(x[1])}" + (" [ĐÃ ĐĂNG KÝ]" if x[0] in child.extra_services else ""),
            f"Dịch vụ của {child.full_name}", "Chưa có dịch vụ nào - hãy thêm ở 'Danh mục dịch vụ'."))[0]
        registered = name in child.extra_services
        self.system.set_child_service(child.id, name, not registered)
        io.success(f"Đã {'hủy' if registered else 'đăng ký'} dịch vụ {name} cho {child.full_name}.")

    # ------------------------------------------------------------------ cấu hình
    def settings(self) -> None:
        io, cfg = self.io, self.system.settings
        io.key_values([("Học phí tháng", format_vnd(cfg.monthly_tuition)),
                       ("Tiền ăn mỗi ngày", format_vnd(cfg.meal_rate_per_day)),
                       ("Giảm cho con thứ hai", f"{format_rate(cfg.second_child_rate)}%"),
                       ("Giảm cho hộ nghèo", f"{format_rate(cfg.poor_household_rate)}%"),
                       ("Hạn nộp", f"{cfg.due_days} ngày sau khi lập hóa đơn"),
                       ("Lương cơ sở", format_vnd(cfg.base_salary_unit)),
                       ("Ưu đãi nghề giáo viên", f"{format_rate(cfg.teacher_incentive_rate)}%"),
                       ("Phụ cấp chủ nhiệm", format_vnd(cfg.homeroom_allowance))]
                      + [(f"Học phí riêng khối {k}", format_vnd(v)) for k, v in cfg.tuition_by_group.items()]
                      + [(f"Dịch vụ: {name}", format_vnd(price)) for name, price in cfg.extra_services.items()],
                      title="CẤU HÌNH HIỆN TẠI:")
        if not io.ask_yes_no("Sửa cấu hình", default=False):
            return

        def rate(prompt: str, value: float) -> float:
            # L17: hiển thị và nhận đủ chữ số (12,5%), không làm tròn khi chỉ bấm Enter
            return io.ask(f"{prompt} (%)", lambda raw: parse_float(raw, prompt, 0, 100) / 100, value,
                          display_default=format_rate(value))

        changes = {
            "monthly_tuition": io.ask_money("Học phí tháng (mức chung)", cfg.monthly_tuition),
            "meal_rate_per_day": io.ask_money("Tiền ăn mỗi ngày", cfg.meal_rate_per_day),
            "second_child_rate": rate("Giảm cho con thứ hai", cfg.second_child_rate),
            "poor_household_rate": rate("Giảm cho hộ nghèo", cfg.poor_household_rate),
            "due_days": io.ask_int("Hạn nộp (số ngày)", cfg.due_days, 0, 60),
            "base_salary_unit": io.ask_money("Lương cơ sở", cfg.base_salary_unit, allow_zero=False),
            "teacher_incentive_rate": rate("Ưu đãi nghề giáo viên", cfg.teacher_incentive_rate),
            "homeroom_allowance": io.ask_money("Phụ cấp chủ nhiệm", cfg.homeroom_allowance),
        }
        groups = dict(cfg.tuition_by_group)
        if io.ask_yes_no("Đặt học phí riêng theo khối", default=False):
            for group in AgeGroup:
                value = io.ask_money(f"Học phí khối {group.label} (Enter = dùng mức chung)",
                                     groups.get(group.label), required=False)
                if value is None:
                    groups.pop(group.label, None)
                else:
                    groups[group.label] = value
        changes["tuition_by_group"] = groups
        services = dict(cfg.extra_services)
        while True:
            action = io.ask_choice("Dịch vụ tự chọn", [("done", "Xong"), ("set", "Thêm / sửa giá dịch vụ"),
                                                       ("remove", "Xóa dịch vụ")], default="done")
            if action == "done":
                break
            if action == "set":
                name = io.ask_text("Tên dịch vụ")
                existing = cfg.find_service(name) or next((s for s in services if s.lower() == name.lower()), None)
                key = existing or name
                services[key] = io.ask_money("Giá mỗi tháng", services.get(key))
            else:
                name = io.choose(list(services), str, "Chọn dịch vụ cần xóa", "Chưa có dịch vụ nào.")
                if name:
                    services.pop(name)
        changes["extra_services"] = services
        try:
            self.system.update_fee_settings(**changes)
        except KindergartenError as exc:   # L17: còn trẻ đăng ký dịch vụ bị xóa -> hỏi gỡ đăng ký hàng loạt
            if "đang đăng ký dịch vụ" not in exc.message or not self.confirm(f"{exc.message}\nGỡ đăng ký cho các trẻ này"):
                raise
            self.system.update_fee_settings(unregister_removed=True, **changes)
        io.success("Đã lưu cấu hình. Học phí áp dụng cho hóa đơn tạo từ bây giờ; lương áp dụng cho kỳ chưa chốt.")
