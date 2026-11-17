"""T11 - ChildManager, ParentManager.

Thêm, sửa, xóa, tìm trẻ theo tên, lớp, độ tuổi; tìm các con của một phụ huynh.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from ..core.base_manager import BaseManager
from ..exceptions import DuplicateIdError, InvalidAgeError, KindergartenError, NotFoundError, ValidationError
from ..utils import normalize_phone, normalize_text
from .child import Child
from .parent import Parent

HOUSEHOLD_RELATIONS = ("Bố", "Mẹ")   # L12: anh chị em ruột = nối với nhau qua bố/mẹ


class ChildManager(BaseManager[Child]):
    entity_name = "trẻ"

    def __init__(self) -> None:
        super().__init__()
        self.class_lookup: Callable[[str], Any] | None = None      # gắn bởi KindergartenSystem
        self.parent_lookup: Callable[[str], Parent | None] | None = None

    # ------------------------------------------------------------------ L11: ràng buộc chéo khi sửa
    def _validate_update(self, child: Child) -> None:
        if child.enrollment_date < child.dob:
            raise ValidationError("Ngày nhập học không được trước ngày sinh.")
        classroom = self.class_lookup(child.class_id) if (self.class_lookup and child.class_id) else None
        if classroom is not None and not classroom.accepts_age(child.age):
            raise InvalidAgeError(f"Với ngày sinh mới, {child.full_name} ({child.age} tuổi) không còn hợp "
                                  f"độ tuổi lớp {classroom.name} ({classroom.min_age}-{classroom.max_age} tuổi).")

    # ------------------------------------------------------------------ danh sách (mặc định chỉ trẻ đang học - L14)
    def active(self) -> list[Child]:
        return [c for c in self._items.values() if c.is_active]

    def all_sorted(self, include_inactive: bool = False) -> list[Child]:
        return self.sort("sort_key", items=self._items.values() if include_inactive else self.active())

    def search_by_name(self, keyword: str, include_inactive: bool = False) -> list[Child]:
        found = self.search(keyword, "full_name", "nickname")
        return self.sort("sort_key", items=[c for c in found if include_inactive or c.is_active])

    def find_by_class(self, class_id: str | None) -> list[Child]:
        key = self._key(class_id) or None
        return self.sort("sort_key", items=self.find(lambda c: c.class_id == key and c.is_active))

    def find_unassigned(self) -> list[Child]:
        return self.find_by_class(None)

    def find_by_age(self, age: int) -> list[Child]:
        return self.sort("sort_key", items=self.find(lambda c: c.is_active and c.age == int(age)))

    def find_by_age_range(self, min_age: int, max_age: int) -> list[Child]:
        return self.sort("sort_key", items=self.find(
            lambda c: c.is_active and int(min_age) <= c.age <= int(max_age)))

    def find_by_parent(self, parent_id: str) -> list[Child]:
        key = self._key(parent_id)
        return self.sort("sort_key", items=self.find(lambda c: key in c.parent_ids))

    def find_inactive(self) -> list[Child]:
        return self.sort("sort_key", items=self.find(lambda c: not c.is_active))

    # ------------------------------------------------------------------ hộ gia đình, anh chị em (L12)
    def _household_parents(self, child: Child) -> list[str]:
        if self.parent_lookup is None:
            return child.parent_ids
        result = []
        for parent_id in child.parent_ids:
            parent = self.parent_lookup(parent_id)
            if parent is not None and parent.relationship in HOUSEHOLD_RELATIONS:
                result.append(parent.id)
        return result

    def household_of(self, child_id: str) -> set[str]:
        """Mã các trẻ cùng hộ: nối với nhau qua phụ huynh có quan hệ Bố/Mẹ (một định nghĩa duy nhất)."""
        start = self.get(child_id)
        members, queue = {start.id}, [start]
        parents_seen: set[str] = set()
        while queue:
            child = queue.pop()
            for parent_id in self._household_parents(child):
                if parent_id in parents_seen:
                    continue
                parents_seen.add(parent_id)
                for other in self._items.values():
                    if other.id not in members and parent_id in other.parent_ids:
                        members.add(other.id)
                        queue.append(other)
        return members

    def household_key(self, child_id: str) -> str:
        return min(self.household_of(child_id), key=lambda cid: (len(cid), cid))

    def siblings_of(self, child_id: str, active_only: bool = False, until: date | None = None) -> list[Child]:
        """Anh/chị/em ruột. active_only: chỉ tính trẻ còn đang học (có lớp, nhập học trước `until`)."""
        child = self.get(child_id)
        result = []
        for other_id in sorted(self.household_of(child.id) - {child.id}):
            other = self._items[other_id]
            if active_only and not (other.is_active and other.class_id is not None
                                    and (until is None or other.enrollment_date <= until)):
                continue
            result.append(other)
        return result

    def birthdays_in_month(self, month: int, child_ids: set[str] | None = None) -> list[Child]:
        return sorted((c for c in self.active() if c.dob.month == month
                       and (child_ids is None or c.id in child_ids)), key=lambda c: c.dob.day)

    def filter_children(self, keyword: str = "", class_id: str | None = None, min_age: int | None = None,
                        max_age: int | None = None, unassigned_only: bool = False) -> list[Child]:
        """Tìm kết hợp nhiều tiêu chí (dùng cho màn hình tìm kiếm)."""
        key = normalize_text(keyword)
        class_key = self._key(class_id) if class_id else None

        def match(c: Child) -> bool:
            if not c.is_active or (key and key not in f"{c.search_text} {c.id.lower()}"):
                return False
            if unassigned_only and c.class_id is not None:
                return False
            if class_key and c.class_id != class_key:
                return False
            if min_age is not None and c.age < min_age:
                return False
            return max_age is None or c.age <= max_age

        return self.sort("sort_key", items=self.find(match))


class ParentManager(BaseManager[Parent]):
    entity_name = "phụ huynh"

    def __init__(self, child_manager: ChildManager) -> None:
        super().__init__()
        self.children = child_manager
        self._by_phone: dict[str, Parent] = {}       # P04: chỉ mục SĐT
        child_manager.on_remove(self._on_child_removed)

    # ------------------------------------------------------------------ chỉ mục
    def _after_add(self, parent: Parent) -> None:
        self._by_phone.setdefault(parent.phone, parent)
        for child_id in parent.child_ids:  # giữ liên kết hai chiều
            child = self.children.get_or_none(child_id)
            if child is not None:
                child.add_parent_id(parent.id)

    def _after_update(self, parent: Parent, before: dict[str, Any]) -> None:
        self._rebuild_phone_index()

    def _after_remove(self, parent: Parent) -> None:
        self._rebuild_phone_index()

    def _after_clear(self) -> None:
        self._by_phone.clear()

    def _rebuild_phone_index(self) -> None:
        self._by_phone = {}
        for parent in self._items.values():
            self._by_phone.setdefault(parent.phone, parent)

    # ------------------------------------------------------------------ kiểm tra
    def _check_unique_phone(self, parent: Parent) -> None:
        """L27: cho phép vợ chồng dùng chung số (cùng có con chung, hoặc người mới chưa liên kết con -
        giao diện sẽ hỏi xác nhận); hai người đã thuộc hai hộ khác nhau thì chặn."""
        for other in self._items.values():
            if other is parent or other.phone != parent.phone:
                continue
            if not parent.child_ids or not other.child_ids or set(other.child_ids) & set(parent.child_ids):
                continue
            raise DuplicateIdError(f"SĐT {parent.phone} đã được dùng cho phụ huynh {other}.")

    def _validate_new(self, parent: Parent) -> None:
        self._check_unique_phone(parent)
        for child_id in parent.child_ids:
            self.children.get(child_id)

    def _validate_update(self, parent: Parent) -> None:
        self._check_unique_phone(parent)
        parent.check_gender_matches_relationship()

    def _studying_children_left_alone(self, parent: Parent, child_ids: list[str]) -> list[Child]:
        alone = []
        for child_id in child_ids:
            child = self.children.get_or_none(child_id)
            if child is not None and child.is_active and child.parent_ids == [parent.id]:
                alone.append(child)
        return alone

    def remove(self, item_id: Any, force: bool = False) -> Parent:
        """L27: chặn xóa người liên hệ cuối cùng của trẻ đang học, trừ khi xác nhận (force=True)."""
        parent = self.get(item_id)
        alone = self._studying_children_left_alone(parent, parent.child_ids)
        if alone and not force:
            raise KindergartenError(f"{', '.join(c.full_name for c in alone)} sẽ không còn phụ huynh nào để "
                                    "liên hệ/đón. Hãy thêm phụ huynh khác trước hoặc xác nhận vẫn xóa.")
        return super().remove(item_id)

    def _before_remove(self, parent: Parent) -> None:
        for child in self.children.find_by_parent(parent.id):
            child.remove_parent_id(parent.id)

    def _on_child_removed(self, child: Child) -> None:
        for parent in self._items.values():
            parent.remove_child_id(child.id)

    # ------------------------------------------------------------------ tìm kiếm
    def all_sorted(self) -> list[Parent]:
        return self.sort("sort_key")

    def search_by_name(self, keyword: str) -> list[Parent]:
        return self.sort("sort_key", items=self.search(keyword, "full_name", "phone"))

    def find_by_phone(self, phone: str) -> Parent | None:
        key = normalize_phone(phone)
        return self._by_phone.get(key) if key else None

    def parents_of_children(self, child_ids: set[str]) -> list[Parent]:
        """Phụ huynh của một nhóm trẻ (giáo viên chỉ xem phụ huynh trẻ lớp mình - L09)."""
        return self.sort("sort_key", items=[p for p in self._items.values() if set(p.child_ids) & child_ids])

    # ------------------------------------------------------------------ liên kết phụ huynh - trẻ
    def link(self, parent_id: str, child_id: str) -> None:
        self._authorize()
        parent, child = self.get(parent_id), self.children.get(child_id)
        parent.add_child_id(child.id)
        child.add_parent_id(parent.id)

    def unlink(self, parent_id: str, child_id: str, force: bool = False) -> None:
        self._authorize()
        parent, child = self.get(parent_id), self.children.get(child_id)
        if not parent.has_child(child.id):
            raise NotFoundError(f"{parent} không phải phụ huynh của {child}.")
        if self._studying_children_left_alone(parent, [child.id]) and not force:
            raise KindergartenError(f"{child.full_name} sẽ không còn phụ huynh nào. Hãy thêm phụ huynh khác "
                                    "trước hoặc xác nhận vẫn bỏ liên kết.")
        parent.remove_child_id(child.id)
        child.remove_parent_id(parent.id)

    def children_of(self, parent_id: str) -> list[Child]:
        """Danh sách các con (có hồ sơ tại trường) của một phụ huynh."""
        parent = self.get(parent_id)
        children = [self.children.get_or_none(cid) for cid in parent.child_ids]
        return [c for c in children if c is not None]

    def parents_of(self, child_id: str) -> list[Parent]:
        child = self.children.get(child_id)
        parents = [self.get_or_none(pid) for pid in child.parent_ids]
        return [p for p in parents if p is not None]

    def sync_links(self) -> None:
        """Đồng bộ liên kết hai chiều sau khi đọc file (bỏ mã không còn tồn tại)."""
        for parent in self._items.values():
            for child_id in parent.child_ids:
                child = self.children.get_or_none(child_id)
                if child is None:
                    parent.remove_child_id(child_id)
                else:
                    child.add_parent_id(parent.id)
        for child in self.children:
            for parent_id in child.parent_ids:
                parent = self.get_or_none(parent_id)
                if parent is None:
                    child.remove_parent_id(parent_id)
                else:
                    parent.add_child_id(child.id)

    def contact_of(self, child_id: str) -> str:
        """Chuỗi liên hệ ngắn gọn của phụ huynh (dùng trong bảng danh sách)."""
        parents = self.parents_of(child_id)
        return "; ".join(f"{p.relationship} {p.full_name} - {p.phone}" for p in parents) or "-"

    @staticmethod
    def describe_parents(parents: list[Parent]) -> str:
        return " & ".join(p.full_name for p in parents) if parents else "-"
