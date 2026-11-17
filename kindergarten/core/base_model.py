"""T02 - BaseModel: lớp trừu tượng gốc của mọi đối tượng nghiệp vụ."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar

from ..exceptions import ValidationError

M = TypeVar("M", bound="BaseModel")
_ID_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")


class BaseModel(ABC):
    """Lớp gốc trừu tượng.

    * Mã tự sinh: mỗi lớp con khai báo PREFIX; mã có dạng PREFIX + số thứ tự 3 chữ số
      (C001, T001, PH001...). Bộ đếm dùng chung theo tiền tố.
    * Mã được cấp ở lần truy cập đầu tiên (thường là lúc thêm vào Manager), nhờ đó dữ liệu
      nhập sai bị từ chối ngay trong __init__ sẽ không làm "nhảy số".
    * to_dict()/from_dict(): chuyển qua lại dạng dict để lưu file JSON (T30).
    """

    PREFIX: ClassVar[str] = "ID"
    ID_DIGITS: ClassVar[int] = 3
    _counters: ClassVar[dict[str, int]] = {}
    _registry: ClassVar[dict[str, type["BaseModel"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        BaseModel._registry[cls.__name__] = cls  # phục vụ from_dict đa hình

    def __init__(self, id: str | None = None) -> None:  # noqa: A002 - giữ tên 'id' cho dễ đọc
        self._id: str | None = None
        if id is not None and str(id).strip():
            self._id = str(id).strip().upper()
            BaseModel.register_id(self._id)

    # ------------------------------------------------------------------ mã
    @property
    def id(self) -> str:
        if self._id is None:
            self._id = type(self).next_id()
        return self._id

    @property
    def has_id(self) -> bool:
        return self._id is not None

    @classmethod
    def next_id(cls) -> str:
        number = BaseModel._counters.get(cls.PREFIX, 0) + 1
        BaseModel._counters[cls.PREFIX] = number
        return f"{cls.PREFIX}{number:0{cls.ID_DIGITS}d}"

    @staticmethod
    def register_id(obj_id: str) -> None:
        """Ghi nhận mã đã có (VD khi đọc từ file) để lần sinh mã sau không bị trùng."""
        match = _ID_PATTERN.match(obj_id.upper())
        if match:
            prefix, number = match.group(1), int(match.group(2))
            if number > BaseModel._counters.get(prefix, 0):
                BaseModel._counters[prefix] = number

    @staticmethod
    def reset_counters() -> None:
        BaseModel._counters.clear()

    @staticmethod
    def counters() -> dict[str, int]:
        """Bộ đếm hiện tại - được lưu cùng dữ liệu để mã đã dùng không bao giờ bị cấp lại (L01)."""
        return dict(BaseModel._counters)

    @staticmethod
    def restore_counters(saved: dict[str, Any]) -> None:
        """Khôi phục bộ đếm đã lưu; chỉ tăng, không bao giờ cho bộ đếm lùi."""
        for prefix, number in (saved or {}).items():
            try:
                value = int(number)
            except (TypeError, ValueError):
                continue
            if value > BaseModel._counters.get(str(prefix), 0):
                BaseModel._counters[str(prefix)] = value

    @property
    def id_sort_key(self) -> tuple[str, int, str]:
        from ..utils import id_sort_key
        return id_sort_key(self.id)

    # ------------------------------------------------------------------ chuyển đổi
    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Chuyển đối tượng thành dict chỉ gồm kiểu dữ liệu JSON."""

    @classmethod
    @abstractmethod
    def from_dict(cls: type[M], data: dict[str, Any]) -> M:
        """Tạo lại đối tượng từ dict do to_dict() sinh ra."""

    def _base_dict(self) -> dict[str, Any]:
        return {"type": type(self).__name__, "id": self.id}

    @staticmethod
    def class_for(type_name: str) -> type["BaseModel"]:
        try:
            return BaseModel._registry[type_name]
        except KeyError:
            raise ValidationError(f"Không nhận ra kiểu dữ liệu '{type_name}'.") from None

    # ------------------------------------------------------------------ hiển thị
    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._id or '(chưa cấp mã)'}>"

    def __str__(self) -> str:
        return self.id
