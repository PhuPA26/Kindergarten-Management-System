"""T24 - InvoiceManager: tạo hóa đơn hàng loạt cho cả trường, tra cứu công nợ, danh sách phụ huynh còn nợ.

Sau rà soát:
- L03: không lập hóa đơn cho tháng chưa diễn ra; tháng hiện tại là "tạm tính", tính lại được khi chưa thu.
- L12: anh chị em xác định theo hộ (bố/mẹ chung), chỉ tính anh/chị còn đang học; công nợ gộp theo cùng định nghĩa hộ.
- L16: hủy phiếu thu ghi nhầm.  L17: báo dịch vụ đã đăng ký nhưng không còn trong bảng giá.
- P03/P04: số ngày có mặt tính một lần cho cả trường; chỉ mục (trẻ, năm, tháng) -> hóa đơn.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from ..attendance.attendance_manager import AttendanceManager
from ..classroom.class_manager import ClassManager
from ..core.base_manager import BaseManager
from ..exceptions import DuplicateIdError, KindergartenError
from ..people.child import Child
from ..people.managers import ChildManager, ParentManager
from ..utils import format_vnd, id_sort_key, in_month, month_bounds, month_label, normalize_text, parse_date, parse_month
from .discount import Discount, DiscountPolicy
from .fees import ExtraFee, Fee, MealFee, MonthlyFee
from .invoice import Invoice, InvoiceStatus, Payment
from .settings import FeeSettings


class InvoiceManager(BaseManager[Invoice]):
    entity_name = "hóa đơn"

    def __init__(self, child_manager: ChildManager, parent_manager: ParentManager, class_manager: ClassManager,
                 attendance_manager: AttendanceManager, settings: FeeSettings | None = None) -> None:
        super().__init__()
        self.children = child_manager
        self.parents = parent_manager
        self.classes = class_manager
        self.attendance = attendance_manager
        self.settings = settings or FeeSettings()
        self._by_period: dict[tuple[str, int, int], Invoice] = {}
        child_manager.on_before_remove(self._check_child_financial_history)

    @property
    def policy(self) -> DiscountPolicy:
        return DiscountPolicy(self.settings)

    # ------------------------------------------------------------------ hook / chỉ mục
    def _validate_new(self, invoice: Invoice) -> None:
        existing = self.find_invoice(invoice.child_id, invoice.month, invoice.year)
        if existing is not None:
            raise DuplicateIdError(f"{invoice.child_name} đã có hóa đơn tháng {invoice.period_label} ({existing.id}).")

    def _after_add(self, invoice: Invoice) -> None:
        self._by_period[(invoice.child_id, invoice.year, invoice.month)] = invoice

    def _after_remove(self, invoice: Invoice) -> None:
        self._by_period.pop((invoice.child_id, invoice.year, invoice.month), None)

    def _after_clear(self) -> None:
        self._by_period.clear()

    def _before_remove(self, invoice: Invoice) -> None:
        if invoice.payments:
            raise KindergartenError(f"Hóa đơn {invoice.id} đã có lịch sử phiếu thu, không thể xóa.")

    def _check_child_financial_history(self, child: Child) -> None:
        if self.invoices_of_child(child.id):
            raise KindergartenError(f"{child.full_name} đã có lịch sử học phí. "
                                    "Hãy dùng chức năng Thôi học để giữ hồ sơ.")

    # ------------------------------------------------------------------ lập hóa đơn
    def find_invoice(self, child_id: str, month: int, year: int) -> Invoice | None:
        return self._by_period.get((self._key(child_id), int(year), int(month)))

    def unknown_services(self, child: Child) -> list[str]:
        """L17: dịch vụ trẻ đăng ký nhưng không còn trong bảng giá."""
        return [s for s in child.extra_services if self.settings.find_service(s) is None]

    def build_fees(self, child: Child, month: int, year: int, present_days: int | None = None) -> list[Fee]:
        """Các khoản phí của trẻ trong tháng (đa hình: mỗi khoản tự tính tiền)."""
        if present_days is None:
            present_days = self.attendance.present_days(child.id, month, year)
        classroom = self.classes.get_or_none(child.class_id) if child.class_id else None
        tuition = self.settings.tuition_for(classroom.age_group.label if classroom else None)
        fees: list[Fee] = [MonthlyFee(tuition), MealFee(present_days, self.settings.meal_rate_per_day)]
        for service in child.extra_services:
            name = self.settings.find_service(service)
            if name is not None:
                fees.append(ExtraFee(name, self.settings.extra_services[name]))
        return fees

    def applicable_discounts(self, child_id: str, month: int | None = None, year: int | None = None) -> list[Discount]:
        child = self.children.get(child_id)
        until = month_bounds(month, year)[1] if month and year else None
        return self.policy.applicable_discounts(child, self.children.siblings_of(child.id, True, until))

    def _discount_for(self, child: Child, month: int, year: int, fees: list[Fee]) -> Discount | None:
        base = sum(f.calculate() for f in fees if f.discountable)
        siblings = self.children.siblings_of(child.id, active_only=True, until=month_bounds(month, year)[1])
        return self.policy.best_discount(child, siblings, base)

    @staticmethod
    def _check_period(month: int, year: int, today: date) -> bool:
        """L03: chặn tháng chưa diễn ra; trả về True nếu là tháng hiện tại (tạm tính)."""
        if (year, month) > (today.year, today.month):
            raise KindergartenError(f"Tháng {month_label(month, year)} chưa diễn ra, chưa thể lập hóa đơn.")
        return (year, month) == (today.year, today.month)

    def create_invoice(self, child_id: str, month: int, year: int, issue_date: Any = None,
                       present_days: int | None = None) -> Invoice:
        child = self.children.get(child_id)
        month, year = parse_month((month, year))
        today = date.today()
        provisional = self._check_period(month, year, today)
        if self.find_invoice(child.id, month, year):
            raise DuplicateIdError(f"{child.full_name} đã có hóa đơn tháng {month_label(month, year)}.")
        if child.enrollment_date > month_bounds(month, year)[1]:
            raise KindergartenError(f"{child.full_name} nhập học sau tháng {month_label(month, year)}.")
        issued = parse_date(issue_date) if issue_date is not None else today
        fees = self.build_fees(child, month, year, present_days)
        missing = self.unknown_services(child)
        invoice = Invoice(child.id, month, year, fees, self._discount_for(child, month, year, fees),
                          child_name=child.full_name, class_name=self.classes.class_name(child.class_id),
                          issue_date=issued, due_date=issued + timedelta(days=self.settings.due_days),
                          note=f"Dịch vụ không còn trong bảng giá (chưa tính): {', '.join(missing)}" if missing else "",
                          provisional=provisional)
        return self.add(invoice)

    def recalculate(self, invoice_id: str) -> Invoice:
        """L03: tính lại tiền ăn/phí theo điểm danh và bảng giá hiện tại (chỉ khi chưa có thanh toán)."""
        self._authorize()
        invoice = self.get(invoice_id)
        child = self.children.get(invoice.child_id)
        fees = self.build_fees(child, invoice.month, invoice.year)
        provisional = (invoice.year, invoice.month) >= (date.today().year, date.today().month)
        invoice.replace_fees(fees, self._discount_for(child, invoice.month, invoice.year, fees), provisional)
        return invoice

    def generate_monthly_invoices(self, month: int, year: int, class_id: str | None = None,
                                  issue_date: Any = None) -> tuple[list[Invoice], list[Child]]:
        """Tạo hóa đơn hàng loạt cho mọi trẻ đang học (bỏ qua trẻ đã có hóa đơn tháng đó)."""
        month, year = parse_month((month, year))
        self._check_period(month, year, date.today())
        month_end = month_bounds(month, year)[1]
        class_key = self._key(class_id) if class_id else None
        present: Counter = self.attendance.present_days_map(month, year)   # P03: một lượt cho cả trường
        created, skipped = [], []
        for child in self.children.sort("id", items=self.children.active()):
            if not child.class_id or (class_key and child.class_id != class_key):
                continue
            if child.enrollment_date > month_end or self.find_invoice(child.id, month, year):
                skipped.append(child)
                continue
            created.append(self.create_invoice(child.id, month, year, issue_date, present.get(child.id, 0)))
        return created, skipped

    # ------------------------------------------------------------------ thanh toán
    def record_payment(self, invoice_id: str, amount: Any, method: str = "Tiền mặt", pay_date: Any = None,
                       note: str = "", collected_by: str = "") -> Payment:
        self._authorize()
        return self.get(invoice_id).add_payment(amount, pay_date, method, note, collected_by)

    def void_payment(self, invoice_id: str, payment_id: str, reason: str, by: str = "") -> Payment:
        """L16: hủy phiếu thu ghi nhầm (giữ dấu vết, không xóa)."""
        self._authorize()
        return self.get(invoice_id).void_payment(payment_id, reason, by)

    # ------------------------------------------------------------------ tra cứu
    def invoices_of_child(self, child_id: str) -> list[Invoice]:
        key = self._key(child_id)
        return sorted(self.find(lambda i: i.child_id == key), key=lambda i: (i.year, i.month), reverse=True)

    def invoices_of_month(self, month: int, year: int, status: InvoiceStatus | None = None) -> list[Invoice]:
        items = self.find(lambda i: i.month == month and i.year == year and (status is None or i.status is status))
        return sorted(items, key=lambda i: (normalize_text(i.class_name), normalize_text(i.child_name)))

    def unpaid_invoices(self) -> list[Invoice]:
        return sorted(self.find(lambda i: i.balance > 0), key=lambda i: (i.year, i.month, i.id_sort_key))

    def debt_of_child(self, child_id: str) -> int:
        key = self._key(child_id)
        return sum(i.balance for i in self._items.values() if i.child_id == key)

    def debt_of_parent(self, parent_id: str) -> int:
        return sum(self.debt_of_child(c.id) for c in self.parents.children_of(parent_id))

    def total_debt(self) -> int:
        return sum(i.balance for i in self._items.values())

    def debt_lookup(self, keyword: str) -> list[Invoice]:
        """Tra cứu công nợ theo tên trẻ, tên/SĐT phụ huynh hoặc mã hóa đơn."""
        key = normalize_text(keyword)
        result = []
        for invoice in self.unpaid_invoices():
            child = self.children.get_or_none(invoice.child_id)
            parents = self.parents.parents_of(child.id) if child else []
            haystack = " ".join([invoice.id, invoice.child_id, invoice.child_name,
                                 *[f"{p.full_name} {p.phone}" for p in parents]])
            if key in normalize_text(haystack):
                result.append(invoice)
        return result

    def debtors(self, today: date | None = None) -> list[dict[str, Any]]:
        """Danh sách hộ còn nợ - anh chị em ruột gộp một hộ theo đúng định nghĩa dùng khi tính giảm (L12)."""
        today = today or date.today()
        groups: dict[str, dict[str, Any]] = {}
        for invoice in self.unpaid_invoices():
            child = self.children.get_or_none(invoice.child_id)
            if child is not None:
                members = self.children.household_of(child.id)
                key = min(members, key=id_sort_key)
                parent_ids: list[str] = []
                for member_id in sorted(members, key=id_sort_key):
                    for pid in self.children.get(member_id).parent_ids:
                        if pid not in parent_ids:
                            parent_ids.append(pid)
            else:
                key, parent_ids = f"child:{invoice.child_id}", []
            group = groups.get(key)
            if group is None:
                parents = [p for p in (self.parents.get_or_none(pid) for pid in parent_ids) if p]
                group = groups[key] = {
                    "parents": parents,
                    "parent_names": " & ".join(p.full_name for p in parents) or "(chưa có phụ huynh)",
                    "phone": parents[0].phone if parents else "-",
                    "children": [], "invoices": [], "debt": 0, "overdue": 0,
                }
            if invoice.child_name not in group["children"]:
                group["children"].append(invoice.child_name)
            group["invoices"].append(invoice)
            group["debt"] += invoice.balance
            if invoice.is_overdue(today):
                group["overdue"] += invoice.balance
        rows = list(groups.values())
        for row in rows:
            row["periods"] = ", ".join(sorted({i.period_label for i in row["invoices"]},
                                              key=lambda p: (p[3:], p[:2])))
        return sorted(rows, key=lambda r: r["debt"], reverse=True)

    def revenue_summary(self, month: int, year: int) -> dict[str, int]:
        """Doanh thu tháng: phải thu (theo hóa đơn kỳ đó), đã thu, còn nợ, tiền thực thu trong tháng."""
        invoices = self.invoices_of_month(month, year)
        return {
            "invoice_count": len(invoices),
            "tuition": sum(i.tuition_amount for i in invoices),
            "meal": sum(i.meal_amount for i in invoices),
            "extra": sum(i.extra_amount for i in invoices),
            "discount": sum(i.discount_amount for i in invoices),
            "billed": sum(i.total for i in invoices),
            "collected": sum(i.paid_amount for i in invoices),
            "outstanding": sum(i.balance for i in invoices),
            "cash_in_month": sum(p.amount for i in self._items.values() for p in i.payments_in_month(month, year)),
        }
