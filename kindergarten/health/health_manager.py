"""T13 - HealthManager: tăng trưởng và dị ứng của từng trẻ (phần tiêm chủng đã bỏ theo yêu cầu).

HealthManager dùng 2 BaseManager[T] bên trong (thành phần - composition):
records (HealthRecord), allergies (Allergy).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable, TypeVar

from ..core.base_manager import BaseManager
from ..exceptions import DuplicateIdError, ValidationError
from ..people.child import Child
from ..people.managers import ChildManager
from ..utils import age_in_months, parse_date
from .records import Allergy, HealthRecord, NutritionStatus

T = TypeVar("T")


@dataclass
class AllergyConflict:
    child_id: str
    allergy: Allergy
    ingredient: str


class ChildIndexedManager(BaseManager[T]):
    """BaseManager có chỉ mục mã trẻ -> các bản ghi (P04: không quét toàn bộ cho từng trẻ)."""

    def __init__(self, entity_name: str) -> None:
        super().__init__(entity_name)
        self._by_child: dict[str, dict[str, T]] = defaultdict(dict)

    def _after_add(self, item: T) -> None:
        self._by_child[item.child_id][item.id] = item

    def _after_remove(self, item: T) -> None:
        self._by_child[item.child_id].pop(item.id, None)

    def _after_clear(self) -> None:
        self._by_child.clear()

    def of_child(self, child_id: str) -> list[T]:
        return list(self._by_child.get(self._key(child_id), {}).values())


class HealthManager:
    def __init__(self, child_manager: ChildManager) -> None:
        self.children = child_manager
        self.records: ChildIndexedManager[HealthRecord] = ChildIndexedManager("hồ sơ cân đo")
        self.allergies: ChildIndexedManager[Allergy] = ChildIndexedManager("thông tin dị ứng")
        self.child_guard: Callable[[Child], None] | None = None   # L08: giáo viên chỉ ghi cho trẻ lớp mình
        child_manager.on_remove(self._on_child_removed)

    def _guard(self, child: Child) -> None:
        if self.child_guard is not None:
            self.child_guard(child)

    def _on_child_removed(self, child: Child) -> None:
        for manager in (self.records, self.allergies):
            for item in manager.of_child(child.id):
                manager.remove(item.id)

    # ================================================================== Tăng trưởng (T12)
    def add_health_record(self, child_id: str, measure_date: Any, height_cm: Any, weight_kg: Any,
                          note: str = "") -> HealthRecord:
        child = self.children.get(child_id)
        self._guard(child)
        d = parse_date(measure_date, "Ngày đo")
        if d > date.today():
            raise ValidationError("Ngày đo không được ở tương lai.")
        if d < child.dob:
            raise ValidationError("Ngày đo không được trước ngày sinh của trẻ.")
        record = HealthRecord(child.id, d, height_cm, weight_kg, age_in_months(child.dob, d), note)
        if any(r.measure_date == d for r in self.records.of_child(child.id)):
            raise DuplicateIdError(f"{child.full_name} đã có số đo ngày {d:%d/%m/%Y}.")
        return self.records.add(record)

    def remove_health_record(self, record_id: str) -> HealthRecord:
        """U01: xóa số đo nhập nhầm."""
        record = self.records.get(record_id)
        self._guard(self.children.get(record.child_id))
        return self.records.remove(record.id)

    def records_of(self, child_id: str) -> list[HealthRecord]:
        key = self.children.get(child_id).id
        return sorted(self.records.of_child(key), key=lambda r: r.measure_date)

    def latest_record(self, child_id: str) -> HealthRecord | None:
        records = self.records_of(child_id)
        return records[-1] if records else None

    def growth_history(self, child_id: str) -> list[dict[str, Any]]:
        """Quá trình tăng trưởng: mỗi lần đo kèm mức thay đổi so với lần trước."""
        history, previous = [], None
        for record in self.records_of(child_id):
            history.append({
                "record": record,
                "bmi": record.calc_bmi(),
                "status": record.assess(),
                "height_change": None if previous is None else round(record.height_cm - previous.height_cm, 1),
                "weight_change": None if previous is None else round(record.weight_kg - previous.weight_kg, 1),
            })
            previous = record
        return history

    def children_needing_attention(self, child_ids: set[str] | None = None) -> list[tuple[Child, HealthRecord]]:
        """Trẻ đang học có kết quả cân đo gần nhất không bình thường (nhẹ cân, thừa cân, béo phì)."""
        result = []
        for child in self.children.all_sorted():
            if child_ids is not None and child.id not in child_ids:
                continue
            record = self.latest_record(child.id)
            if record is not None and record.assess() is not NutritionStatus.NORMAL:
                result.append((child, record))
        return result

    def nutrition_summary(self) -> dict[NutritionStatus, int]:
        summary = {status: 0 for status in NutritionStatus}
        for child in self.children.active():
            record = self.latest_record(child.id)
            if record is not None:
                summary[record.assess()] += 1
        return summary

    # ================================================================== Dị ứng (T13)
    def add_allergy(self, child_id: str, allergen: str, severity: Any = "Nhẹ", reaction: str = "") -> Allergy:
        child = self.children.get(child_id)
        self._guard(child)
        allergy = Allergy(child.id, allergen, severity, reaction)
        if any(a.allergen == allergy.allergen for a in self.allergies.of_child(child.id)):
            raise DuplicateIdError(f"{child.full_name} đã có thông tin dị ứng '{allergy.allergen}'.")
        return self.allergies.add(allergy)

    def remove_allergy(self, allergy_id: str) -> Allergy:
        allergy = self.allergies.get(allergy_id)
        self._guard(self.children.get(allergy.child_id))
        return self.allergies.remove(allergy.id)

    def allergies_of(self, child_id: str) -> list[Allergy]:
        key = self.children.get(child_id).id
        return sorted(self.allergies.of_child(key), key=lambda a: a.allergen)

    def children_with_allergies(self) -> list[tuple[Child, list[Allergy]]]:
        result = []
        for child in self.children.all_sorted():
            allergies = self.allergies.of_child(child.id)
            if allergies:
                result.append((child, sorted(allergies, key=lambda a: a.allergen)))
        return result

    def find_allergy_conflicts(self, child_ids: Iterable[str], ingredients: Iterable[str]) -> list[AllergyConflict]:
        """Đối chiếu thành phần món ăn với dị ứng của các trẻ (dùng cho thực đơn - T26)."""
        ingredient_list = list(ingredients)
        conflicts = []
        for child_id in child_ids:
            for allergy in self.allergies.of_child(child_id):
                for ingredient in ingredient_list:
                    if allergy.matches(ingredient):
                        conflicts.append(AllergyConflict(allergy.child_id, allergy, ingredient))
                        break
        return conflicts
