"""T21 - Fee (trừu tượng), MonthlyFee, MealFee, ExtraFee ghi đè calculate().

Mỗi loại phí tự tính theo cách riêng, ví dụ tiền ăn = số ngày đi học thực tế × đơn giá.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ..exceptions import ValidationError
from ..utils import format_vnd, parse_int, parse_money, require_text


class Fee(ABC):
    """Một khoản phí trong hóa đơn."""

    discountable: ClassVar[bool] = False   # khoản phí có được áp dụng miễn giảm không
    _types: ClassVar[dict[str, type["Fee"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        Fee._types[cls.__name__] = cls

    def __init__(self, name: str) -> None:
        self.name = require_text(name, "Tên khoản phí", 80)

    @abstractmethod
    def calculate(self) -> int:
        """Số tiền của khoản phí."""

    @abstractmethod
    def describe(self) -> str:
        """Diễn giải cách tính."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Dữ liệu để lưu file."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Fee":
        """Tạo đúng loại phí theo trường 'type' (đa hình khi đọc file)."""
        fee_type = Fee._types.get(str(data.get("type", "")))
        if fee_type is None:
            raise ValidationError(f"Loại phí '{data.get('type')}' không hợp lệ.")
        return fee_type._from_dict(data)

    @classmethod
    @abstractmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Fee":
        """Lớp con tự đọc dữ liệu của mình."""

    def __str__(self) -> str:
        return f"{self.name}: {format_vnd(self.calculate())} ({self.describe()})"


class MonthlyFee(Fee):
    """Học phí cố định theo tháng (được áp dụng miễn giảm)."""

    discountable = True

    def __init__(self, amount: Any, name: str = "Học phí tháng") -> None:
        super().__init__(name)
        self.amount = parse_money(amount, "Học phí")

    def calculate(self) -> int:
        return self.amount

    def describe(self) -> str:
        return "Cố định theo tháng"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "MonthlyFee", "name": self.name, "amount": self.amount}

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "MonthlyFee":
        return cls(data["amount"], data.get("name", "Học phí tháng"))


class MealFee(Fee):
    """Tiền ăn = số ngày đi học thực tế × đơn giá một ngày."""

    def __init__(self, days: Any, rate_per_day: Any, name: str = "Tiền ăn") -> None:
        super().__init__(name)
        self.days = parse_int(days, "Số ngày ăn", 0, 31)
        self.rate_per_day = parse_money(rate_per_day, "Tiền ăn/ngày")

    def calculate(self) -> int:
        return self.days * self.rate_per_day

    def describe(self) -> str:
        return f"{self.days} ngày × {format_vnd(self.rate_per_day)}"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "MealFee", "name": self.name, "days": self.days, "rate_per_day": self.rate_per_day}

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "MealFee":
        return cls(data["days"], data["rate_per_day"], data.get("name", "Tiền ăn"))


class ExtraFee(Fee):
    """Phí khác: năng khiếu, tiếng Anh, đồng phục... = đơn giá × số lượng."""

    def __init__(self, name: str, amount: Any, quantity: Any = 1) -> None:
        super().__init__(name)
        self.amount = parse_money(amount, "Đơn giá")
        self.quantity = parse_int(quantity, "Số lượng", 1, 100)

    def calculate(self) -> int:
        return self.amount * self.quantity

    def describe(self) -> str:
        return f"{self.quantity} × {format_vnd(self.amount)}" if self.quantity > 1 else "Dịch vụ tự chọn"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "ExtraFee", "name": self.name, "amount": self.amount, "quantity": self.quantity}

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "ExtraFee":
        return cls(data["name"], data["amount"], data.get("quantity", 1))
