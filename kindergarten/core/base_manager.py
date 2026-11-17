"""T03 - BaseManager[T]: bộ thêm/sửa/xóa/tìm/sắp xếp dùng chung cho mọi module."""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Generic, Iterable, Iterator, TypeVar

from ..exceptions import DuplicateIdError, NotFoundError, ValidationError
from ..utils import id_sort_key, normalize_text
from .base_model import BaseModel

T = TypeVar("T", bound=BaseModel)
Listener = Callable[[Any], None]


class BaseManager(Generic[T]):
    """Quản lý một tập đối tượng cùng kiểu, lưu trong dict theo mã.

    Chức năng chung: add, update, remove, get, find, search, sort.
    Lớp con tùy biến qua các "hook": _validate_new, _validate_update, _before_remove...
    Hỗ trợ đăng ký sự kiện xóa (mẫu Observer) để module khác tự cập nhật dữ liệu liên quan,
    VD: xóa trẻ -> lớp học tự bỏ trẻ khỏi danh sách, phụ huynh tự bỏ liên kết.

    Phân quyền ở tầng nghiệp vụ (L10): khi đã gắn AuthManager (bind_auth) và có người đăng nhập,
    mọi thao tác ghi (add/update/remove) đều kiểm tra `write_permission`.
    """

    entity_name: str = "đối tượng"
    write_permission: Any = None   # Permission cần có để ghi; None = không kiểm tra

    def __init__(self, entity_name: str | None = None, write_permission: Any = None) -> None:
        if entity_name:
            self.entity_name = entity_name
        if write_permission is not None:
            self.write_permission = write_permission
        self._items: dict[str, T] = {}
        self._before_remove_listeners: list[Listener] = []
        self._remove_listeners: list[Listener] = []
        self._auth: Any = None

    # ------------------------------------------------------------------ phân quyền
    def bind_auth(self, auth: Any) -> None:
        self._auth = auth

    def _authorize(self) -> None:
        """Có người đăng nhập thì bắt buộc đủ quyền; không có người đăng nhập = tác vụ hệ thống (nạp file, dữ liệu mẫu)."""
        if getattr(self._auth, "elevated", False):   # bước nghiệp vụ đã được kiểm tra quyền ở tầng trên
            return
        if self._auth is not None and self.write_permission is not None and self._auth.current_user is not None:
            self._auth.check_permission(self.write_permission)

    # ------------------------------------------------------------------ sự kiện
    def on_before_remove(self, callback: Listener) -> None:
        """Đăng ký hàm kiểm tra trước khi xóa (hàm raise lỗi để chặn việc xóa)."""
        self._before_remove_listeners.append(callback)

    def on_remove(self, callback: Listener) -> None:
        """Đăng ký hàm được gọi sau khi một đối tượng bị xóa."""
        self._remove_listeners.append(callback)

    # ------------------------------------------------------------------ hook cho lớp con
    def _validate_new(self, item: T) -> None:
        """Kiểm tra nghiệp vụ trước khi thêm (lớp con ghi đè)."""

    def _validate_update(self, item: T) -> None:
        """Kiểm tra nghiệp vụ sau khi sửa; lỗi sẽ khiến thay đổi bị hoàn tác."""

    def _before_remove(self, item: T) -> None:
        """Kiểm tra/dọn dẹp trước khi xóa (lớp con ghi đè)."""

    def _after_add(self, item: T) -> None:
        """Cập nhật chỉ mục phụ sau khi thêm."""

    def _after_update(self, item: T, before: dict[str, Any]) -> None:
        """Cập nhật chỉ mục phụ sau khi sửa (before = thuộc tính trước khi sửa)."""

    def _after_remove(self, item: T) -> None:
        """Cập nhật chỉ mục phụ sau khi xóa."""

    def _after_clear(self) -> None:
        """Cập nhật chỉ mục phụ sau khi xóa toàn bộ."""

    # ------------------------------------------------------------------ CRUD
    @staticmethod
    def _key(item_id: Any) -> str:
        return str(item_id if item_id is not None else "").strip().upper()

    def add(self, item: T) -> T:
        if not isinstance(item, BaseModel):
            raise TypeError("Chỉ thêm được đối tượng kế thừa BaseModel.")
        self._authorize()
        self._validate_new(item)          # kiểm tra nghiệp vụ TRƯỚC khi cấp mã (L22: không "nhảy số")
        if item.id in self._items:        # tới đây mới cấp mã
            raise DuplicateIdError(f"Mã '{item.id}' đã tồn tại trong danh sách {self.entity_name}.")
        self._items[item.id] = item
        self._after_add(item)
        return item

    def get(self, item_id: Any) -> T:
        item = self._items.get(self._key(item_id))
        if item is None:
            raise NotFoundError(f"Không tìm thấy {self.entity_name} có mã '{item_id}'.")
        return item

    def get_or_none(self, item_id: Any) -> T | None:
        return self._items.get(self._key(item_id))

    def exists(self, item_id: Any) -> bool:
        return self._key(item_id) in self._items

    @staticmethod
    def snapshot(item: BaseModel) -> dict[str, Any]:
        """Ảnh chụp thuộc tính (bản sao nông, sao chép thêm list/dict/set để hoàn tác an toàn)."""
        state = {}
        for key, value in vars(item).items():
            if isinstance(value, (list, dict, set)):
                value = value.copy()
            state[key] = value
        return state

    @staticmethod
    def restore(item: BaseModel, state: dict[str, Any]) -> None:
        """Khôi phục nguyên trạng từ ảnh chụp - không đi qua setter nên không thể thất bại (L05)."""
        vars(item).clear()
        vars(item).update(state)

    def update(self, item_id: Any, **changes: Any) -> T:
        """Sửa nhiều trường cùng lúc; nếu một trường sai thì hoàn tác toàn bộ (atomic)."""
        item = self.get(item_id)
        self._authorize()
        for field in changes:
            self._check_updatable(item, field)
        before = self.snapshot(item)
        try:
            for field, value in changes.items():
                setattr(item, field, value)
            self._validate_update(item)
        except Exception:
            self.restore(item, before)
            raise
        self._after_update(item, before)
        return item

    @staticmethod
    def _check_updatable(item: BaseModel, field: str) -> None:
        if field == "id" or field.startswith("_"):
            raise ValidationError(f"Không được sửa trường '{field}'.")
        attr = getattr(type(item), field, None)
        if isinstance(attr, property):
            if attr.fset is None:
                raise ValidationError(f"Trường '{field}' chỉ đọc, không sửa trực tiếp được.")
        elif not hasattr(item, field) or callable(getattr(item, field)):
            raise ValidationError(f"Trường '{field}' không tồn tại.")

    def remove(self, item_id: Any) -> T:
        item = self.get(item_id)
        self._authorize()
        for callback in list(self._before_remove_listeners):
            callback(item)  # module khác có thể chặn việc xóa
        self._before_remove(item)
        del self._items[item.id]
        self._after_remove(item)
        for callback in list(self._remove_listeners):
            callback(item)
        return item

    def clear(self) -> None:
        self._items.clear()
        self._after_clear()

    # ------------------------------------------------------------------ truy vấn
    def all(self) -> list[T]:
        return list(self._items.values())

    def find(self, predicate: Callable[[T], bool] | None = None, **criteria: Any) -> list[T]:
        """Tìm theo hàm điều kiện và/hoặc giá trị thuộc tính.

        VD: manager.find(lambda c: c.age >= 4, gender="Nữ")
        """
        result = []
        for item in self._items.values():
            if predicate is not None and not predicate(item):
                continue
            if all(getattr(item, key, None) == value for key, value in criteria.items()):
                result.append(item)
        return result

    def find_one(self, predicate: Callable[[T], bool] | None = None, **criteria: Any) -> T | None:
        for item in self._items.values():
            if predicate is not None and not predicate(item):
                continue
            if all(getattr(item, key, None) == value for key, value in criteria.items()):
                return item
        return None

    def search(self, keyword: Any, *fields: str) -> list[T]:
        """Tìm gần đúng (không dấu, không phân biệt hoa/thường) trên các trường chỉ định.

        Nếu đối tượng có sẵn `search_text` (đã chuẩn hóa khi gán giá trị - P08) thì dùng luôn.
        """
        key = normalize_text(keyword)
        if not key:
            return self.all()
        fields = fields or ("id",)
        result = []
        for item in self._items.values():
            cached = getattr(item, "search_text", None)
            if cached is not None and fields != ("id",):
                if key in cached:
                    result.append(item)
            elif any(key in normalize_text(getattr(item, f, "") or "") for f in fields):
                result.append(item)
        return result

    def sort(self, key: str | Callable[[T], Any] = "id", reverse: bool = False,
             items: Iterable[T] | None = None) -> list[T]:
        """Sắp xếp theo tên thuộc tính hoặc hàm khóa; chuỗi được so sánh không dấu, mã so theo số (L25)."""
        sequence = self.all() if items is None else list(items)
        if callable(key):
            key_func = key
        elif key == "id":
            key_func = lambda obj: id_sort_key(obj.id)  # noqa: E731
        else:
            attr = key

            def key_func(obj: T) -> Any:
                value = getattr(obj, attr)
                if isinstance(value, str):
                    return normalize_text(value)
                if isinstance(value, Enum):
                    return str(value.value)
                return value

        def safe_key(obj: T) -> tuple[bool, Any]:
            value = key_func(obj)
            return value is None, value if value is not None else 0

        return sorted(sequence, key=safe_key, reverse=reverse)

    def count(self, predicate: Callable[[T], bool] | None = None) -> int:
        if predicate is None:
            return len(self._items)
        return sum(1 for item in self._items.values() if predicate(item))

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        """Duyệt không sao chép (P04); nơi vừa duyệt vừa xóa phải dùng find()/all()."""
        return iter(self._items.values())

    def __contains__(self, item: object) -> bool:
        if isinstance(item, BaseModel):
            return item.has_id and item.id in self._items
        return self._key(item) in self._items

    # ------------------------------------------------------------------ lưu trữ
    def to_list(self) -> list[Any]:
        return [item.to_dict() for item in self._items.values()]

    def load_list(self, records: Iterable[Any], factory: Callable[[Any], T]) -> int:
        """Nạp lại toàn bộ dữ liệu khi đọc file (không chạy lại các kiểm tra nghiệp vụ)."""
        self.clear()
        for data in records:
            item = factory(data)
            if item.id in self._items:
                raise DuplicateIdError(f"Dữ liệu {self.entity_name} bị trùng mã '{item.id}'.")
            self._items[item.id] = item
            self._after_add(item)
        return len(self._items)
