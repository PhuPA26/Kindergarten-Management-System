"""T23 - Invoice, Payment: hóa đơn theo tháng, ghi nhận thanh toán một phần hoặc đủ, có trạng thái.

Sau rà soát: hóa đơn tháng hiện tại là "tạm tính" và tính lại được khi chưa thu tiền (L03);
phiếu thu nhầm có thể hủy kèm lý do, không bị xóa (L16); không cho ngày nộp trước ngày lập.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from ..core.base_model import BaseModel
from ..exceptions import KindergartenError, NotFoundError, PaymentError, ValidationError
from ..utils import (format_date, format_key_values, format_table, format_vnd, in_month, month_label,
                     normalize_spaces, normalize_text, parse_date, parse_money, parse_month, require_text)
from .discount import Discount
from .fees import Fee, MealFee, MonthlyFee

PAYMENT_METHODS = ("Tiền mặt", "Chuyển khoản")


class InvoiceStatus(Enum):
    UNPAID = "Chưa thanh toán"
    PARTIAL = "Thanh toán một phần"
    PAID = "Đã thanh toán"


class Payment(BaseModel):
    """Một lần nộp tiền cho hóa đơn (phiếu thu)."""

    PREFIX = "PT"

    def __init__(self, invoice_id: str, amount: Any, pay_date: Any = None, method: str = "Tiền mặt",
                 note: str = "", collected_by: str = "", voided: bool = False, void_reason: str = "",
                 voided_by: str = "", voided_at: str = "", id: str | None = None) -> None:
        super().__init__(id)
        self.invoice_id = require_text(invoice_id, "Mã hóa đơn").upper()
        self.amount = parse_money(amount, "Số tiền thanh toán", allow_zero=False)
        self.pay_date = parse_date(pay_date) if pay_date is not None else date.today()
        if self.pay_date > date.today():
            raise ValidationError("Ngày thanh toán không được ở tương lai.")
        self.method = self._parse_method(method)
        self.note = normalize_spaces(note)
        self.collected_by = normalize_spaces(collected_by)
        self.voided = bool(voided)
        self.void_reason = normalize_spaces(void_reason)
        self.voided_by = normalize_spaces(voided_by)
        self.voided_at = normalize_spaces(voided_at)

    @staticmethod
    def _parse_method(value: Any) -> str:
        key = normalize_text(value)
        for method in PAYMENT_METHODS:
            if normalize_text(method) == key or key == str(PAYMENT_METHODS.index(method) + 1):
                return method
        raise ValidationError(f"Hình thức thanh toán '{value}' không hợp lệ ({', '.join(PAYMENT_METHODS)}).")

    @property
    def status_text(self) -> str:
        return f"ĐÃ HỦY ({self.void_reason})" if self.voided else "Hợp lệ"

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(invoice_id=self.invoice_id, amount=self.amount, pay_date=self.pay_date.isoformat(),
                    method=self.method, note=self.note, collected_by=self.collected_by, voided=self.voided,
                    void_reason=self.void_reason, voided_by=self.voided_by, voided_at=self.voided_at)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Payment":
        return cls(data["invoice_id"], data["amount"], data["pay_date"], data.get("method", "Tiền mặt"),
                   data.get("note", ""), data.get("collected_by", ""), data.get("voided", False),
                   data.get("void_reason", ""), data.get("voided_by", ""), data.get("voided_at", ""),
                   id=data["id"])


class Invoice(BaseModel):
    """Hóa đơn học phí tháng của một trẻ."""

    PREFIX = "HD"

    def __init__(self, child_id: str, month: int, year: int, fees: list[Fee] | None = None,
                 discount: Discount | None = None, payments: list[Payment] | None = None,
                 child_name: str = "", class_name: str = "", issue_date: Any = None, due_date: Any = None,
                 note: str = "", provisional: bool = False, id: str | None = None) -> None:
        super().__init__(id)
        self._child_id = require_text(child_id, "Mã trẻ").upper()
        self._month, self._year = parse_month((month, year))
        self.child_name = normalize_spaces(child_name) or self._child_id   # lưu bản chụp tên tại thời điểm lập
        self.class_name = normalize_spaces(class_name)
        self._fees: list[Fee] = list(fees or [])
        self.discount = discount
        self._payments: list[Payment] = list(payments or [])
        self.issue_date = parse_date(issue_date, "Ngày lập") if issue_date is not None else date.today()
        self.due_date = (parse_date(due_date, "Hạn nộp") if due_date is not None
                         else self.issue_date + timedelta(days=10))
        if self.due_date < self.issue_date:
            raise ValidationError("Hạn nộp phải sau ngày lập hóa đơn.")
        self.note = normalize_spaces(note)
        self.provisional = bool(provisional)   # L03: lập khi tháng chưa kết thúc -> tiền ăn còn tạm tính

    # ------------------------------------------------------------------ thông tin
    @property
    def child_id(self) -> str:
        return self._child_id

    @property
    def month(self) -> int:
        return self._month

    @property
    def year(self) -> int:
        return self._year

    @property
    def period_label(self) -> str:
        return month_label(self._month, self._year)

    @property
    def fees(self) -> list[Fee]:
        return list(self._fees)

    @property
    def payments(self) -> list[Payment]:
        return list(self._payments)

    @property
    def valid_payments(self) -> list[Payment]:
        return [p for p in self._payments if not p.voided]

    def add_fee(self, fee: Fee) -> None:
        if not isinstance(fee, Fee):
            raise ValidationError("Khoản phí không hợp lệ.")
        self._fees.append(fee)

    def replace_fees(self, fees: list[Fee], discount: Discount | None, provisional: bool) -> None:
        """L03: tính lại hóa đơn (chỉ khi chưa có thanh toán hợp lệ)."""
        if self.valid_payments:
            raise KindergartenError(f"Hóa đơn {self.id} đã có thanh toán: hãy hủy phiếu thu hoặc lập khoản "
                                    "điều chỉnh ở kỳ sau.")
        self._fees = list(fees)
        self.discount = discount
        self.provisional = provisional

    # ------------------------------------------------------------------ số tiền
    @property
    def subtotal(self) -> int:
        return sum(fee.calculate() for fee in self._fees)

    @property
    def discountable_amount(self) -> int:
        return sum(fee.calculate() for fee in self._fees if fee.discountable)

    @property
    def discount_amount(self) -> int:
        return self.discount.calculate(self.discountable_amount) if self.discount else 0

    @property
    def total(self) -> int:
        return self.subtotal - self.discount_amount

    @property
    def paid_amount(self) -> int:
        return sum(p.amount for p in self._payments if not p.voided)

    @property
    def balance(self) -> int:
        """Số tiền còn nợ."""
        return max(self.total - self.paid_amount, 0)

    def amount_of(self, fee_type: type[Fee]) -> int:
        return sum(f.calculate() for f in self._fees if isinstance(f, fee_type))

    @property
    def tuition_amount(self) -> int:
        return self.amount_of(MonthlyFee)

    @property
    def meal_amount(self) -> int:
        return self.amount_of(MealFee)

    @property
    def extra_amount(self) -> int:
        return self.subtotal - self.tuition_amount - self.meal_amount

    @property
    def status(self) -> InvoiceStatus:
        if self.paid_amount >= self.total:
            return InvoiceStatus.PAID
        return InvoiceStatus.PARTIAL if self.paid_amount > 0 else InvoiceStatus.UNPAID

    def is_overdue(self, today: date | None = None) -> bool:
        return self.balance > 0 and (today or date.today()) > self.due_date

    def status_text(self, today: date | None = None) -> str:
        text = self.status.value
        if self.provisional:
            text += " - tạm tính"
        return f"⚠ {text} (quá hạn)" if self.is_overdue(today) else text

    # ------------------------------------------------------------------ thanh toán
    def add_payment(self, amount: Any, pay_date: Any = None, method: str = "Tiền mặt", note: str = "",
                    collected_by: str = "") -> Payment:
        value = parse_money(amount, "Số tiền thanh toán", allow_zero=False)
        if self.balance <= 0:
            raise PaymentError(f"Hóa đơn {self.id} đã thanh toán đủ.")
        if value > self.balance:
            raise PaymentError(f"Số tiền {format_vnd(value)} vượt quá số còn nợ {format_vnd(self.balance)}.")
        payment = Payment(self.id, value, pay_date, method, note, collected_by)
        if payment.pay_date < self.issue_date:
            raise PaymentError(f"Ngày nộp {format_date(payment.pay_date)} trước ngày lập hóa đơn "
                               f"{format_date(self.issue_date)}.")
        payment.id  # cấp mã phiếu thu ngay
        self._payments.append(payment)
        return payment

    def find_payment(self, payment_id: str) -> Payment:
        key = str(payment_id).strip().upper()
        payment = next((p for p in self._payments if p.id == key), None)
        if payment is None:
            raise NotFoundError(f"Hóa đơn {self.id} không có phiếu thu '{payment_id}'.")
        return payment

    def void_payment(self, payment_id: str, reason: str, by: str = "") -> Payment:
        """L16: hủy phiếu thu ghi nhầm - giữ lại dấu vết (lý do, người hủy, thời điểm), không xóa."""
        payment = self.find_payment(payment_id)
        if payment.voided:
            raise PaymentError(f"Phiếu thu {payment.id} đã bị hủy trước đó.")
        payment.void_reason = require_text(reason, "Lý do hủy", 200)
        payment.voided = True
        payment.voided_by = normalize_spaces(by)
        payment.voided_at = datetime.now().isoformat(timespec="seconds")
        return payment

    def payments_in_month(self, month: int, year: int) -> list[Payment]:
        return [p for p in self._payments if not p.voided and in_month(p.pay_date, month, year)]

    # ------------------------------------------------------------------ hiển thị
    def detail_text(self, today: date | None = None) -> str:
        """Phiếu báo học phí chi tiết."""
        head = format_key_values([
            ("Mã hóa đơn", self.id),
            ("Trẻ", f"{self.child_name} ({self.child_id})"),
            ("Lớp", self.class_name or "-"),
            ("Kỳ thu", f"Tháng {self.period_label}" + (" (tạm tính - tháng chưa kết thúc)" if self.provisional else "")),
            ("Ngày lập / Hạn nộp", f"{format_date(self.issue_date)} / {format_date(self.due_date)}"),
            ("Trạng thái", self.status_text(today)),
        ], title=f"PHIẾU BÁO HỌC PHÍ THÁNG {self.period_label}")
        rows = [[i, fee.name, fee.describe(), format_vnd(fee.calculate())] for i, fee in enumerate(self._fees, 1)]
        table = format_table(["STT", "Khoản thu", "Cách tính", "Thành tiền"], rows)
        lines = [head, table, f"  Cộng                : {format_vnd(self.subtotal)}"]
        if self.discount:
            lines.append(f"  Miễn giảm           : -{format_vnd(self.discount_amount)} ({self.discount.describe()})")
        lines += [f"  TỔNG PHẢI NỘP       : {format_vnd(self.total)}",
                  f"  Đã nộp              : {format_vnd(self.paid_amount)}",
                  f"  CÒN NỢ              : {format_vnd(self.balance)}"]
        if self.note:
            lines.append(f"  Ghi chú             : {self.note}")
        if self._payments:
            pay_rows = [[p.id, format_date(p.pay_date), p.method, format_vnd(p.amount), p.collected_by or "-",
                         p.status_text] for p in self._payments]
            lines.append(format_table(["Phiếu thu", "Ngày nộp", "Hình thức", "Số tiền", "Người thu", "Tình trạng"],
                                      pay_rows, title="Lịch sử thanh toán:"))
        return "\n".join(lines)

    def receipt_text(self, payment: Payment) -> str:
        """U08: phiếu thu in ra sau khi ghi nhận thanh toán."""
        return format_key_values([
            ("Phiếu thu", payment.id), ("Hóa đơn", f"{self.id} - tháng {self.period_label}"),
            ("Trẻ", f"{self.child_name} ({self.child_id})"), ("Số tiền", format_vnd(payment.amount)),
            ("Hình thức", payment.method), ("Ngày nộp", format_date(payment.pay_date)),
            ("Người thu", payment.collected_by or "-"), ("Còn nợ sau khi nộp", format_vnd(self.balance)),
        ], title="PHIẾU THU HỌC PHÍ")

    # ------------------------------------------------------------------ lưu trữ
    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(child_id=self.child_id, month=self.month, year=self.year, child_name=self.child_name,
                    class_name=self.class_name, issue_date=self.issue_date.isoformat(),
                    due_date=self.due_date.isoformat(), note=self.note, provisional=self.provisional,
                    fees=[f.to_dict() for f in self._fees],
                    discount=self.discount.to_dict() if self.discount else None,
                    payments=[p.to_dict() for p in self._payments])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Invoice":
        discount = Discount.from_dict(data["discount"]) if data.get("discount") else None
        return cls(data["child_id"], data["month"], data["year"],
                   fees=[Fee.from_dict(f) for f in data.get("fees", [])], discount=discount,
                   payments=[Payment.from_dict(p) for p in data.get("payments", [])],
                   child_name=data.get("child_name", ""), class_name=data.get("class_name", ""),
                   issue_date=data.get("issue_date"), due_date=data.get("due_date"),
                   note=data.get("note", ""), provisional=data.get("provisional", False), id=data["id"])
