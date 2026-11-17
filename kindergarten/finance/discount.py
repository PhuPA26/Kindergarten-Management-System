"""T22 - Discount: miễn giảm học phí (con thứ hai, hộ nghèo)."""
from __future__ import annotations

from typing import Any, Iterable

from ..people.child import Child
from ..utils import format_rate, format_vnd, parse_float, parse_money, require_text, round_money
from .settings import FeeSettings


class Discount:
    """Một chế độ miễn giảm: theo tỷ lệ (%) và/hoặc số tiền cố định, áp dụng trên các khoản 'discountable'."""

    def __init__(self, name: str, rate: Any = 0.0, amount: Any = 0, reason: str = "") -> None:
        self.name = require_text(name, "Tên chế độ miễn giảm", 80)
        self.rate = parse_float(rate, "Tỷ lệ giảm", 0, 1)
        self.amount = parse_money(amount, "Số tiền giảm")
        self.reason = reason

    def calculate(self, base_amount: int) -> int:
        """Số tiền được giảm (không vượt quá số tiền gốc)."""
        return min(int(base_amount), round_money(base_amount * self.rate) + self.amount)

    def describe(self) -> str:
        parts = []
        if self.rate:
            parts.append(f"giảm {format_rate(self.rate)}% học phí")
        if self.amount:
            parts.append(f"giảm {format_vnd(self.amount)}")
        return f"{self.name}: " + (", ".join(parts) or "không giảm")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "rate": self.rate, "amount": self.amount, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Discount":
        return cls(data["name"], data.get("rate", 0), data.get("amount", 0), data.get("reason", ""))

    def __str__(self) -> str:
        return self.describe()


class DiscountPolicy:
    """Chính sách miễn giảm của trường.

    - Hộ nghèo: giảm `poor_household_rate` học phí.
    - Con thứ hai trở đi (có anh/chị ruột đang học tại trường): giảm `second_child_rate` học phí.
    - Nếu thuộc nhiều diện: áp dụng mức giảm cao nhất (không cộng dồn).
    """

    def __init__(self, settings: FeeSettings) -> None:
        self.settings = settings

    @staticmethod
    def is_second_child(child: Child, siblings: Iterable[Child]) -> bool:
        """Có anh/chị (sinh trước) đang học tại trường thì là con thứ hai trở đi."""
        return any((s.dob, s.id) < (child.dob, child.id) for s in siblings if s is not child)

    def applicable_discounts(self, child: Child, siblings: Iterable[Child]) -> list[Discount]:
        discounts = []
        if child.is_poor_household and self.settings.poor_household_rate > 0:
            discounts.append(Discount("Hộ nghèo", rate=self.settings.poor_household_rate,
                                      reason="Trẻ thuộc diện hộ nghèo"))
        if self.settings.second_child_rate > 0 and self.is_second_child(child, list(siblings)):
            discounts.append(Discount("Con thứ hai", rate=self.settings.second_child_rate,
                                      reason="Có anh/chị ruột đang học tại trường"))
        return discounts

    def best_discount(self, child: Child, siblings: Iterable[Child], base_amount: int) -> Discount | None:
        discounts = self.applicable_discounts(child, siblings)
        if not discounts:
            return None
        return max(discounts, key=lambda d: d.calculate(base_amount))
