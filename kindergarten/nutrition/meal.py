"""T25 - Meal (tên, calo, thành phần) và Menu (thực đơn theo ngày)."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from ..core.base_model import BaseModel
from ..exceptions import ValidationError
from ..health.records import ingredient_matches_allergen
from ..utils import normalize_spaces, normalize_text, parse_date, parse_int, require_text


class MealType(Enum):
    BREAKFAST = "Bữa sáng"
    LUNCH = "Bữa trưa"
    SNACK = "Bữa xế"

    @classmethod
    def parse(cls, value: Any) -> "MealType":
        if isinstance(value, cls):
            return value
        text = normalize_text(value)
        for index, item in enumerate(cls, 1):
            if text in (item.name.lower(), normalize_text(item.value), str(index),
                        normalize_text(item.value).replace("bua ", "")):
                return item
        raise ValidationError(f"Bữa ăn '{value}' không hợp lệ (Bữa sáng/Bữa trưa/Bữa xế).")


class Meal(BaseModel):
    """Món ăn."""

    PREFIX = "MA"

    def __init__(self, name: str, calories: Any, ingredients: Any, description: str = "",
                 active: bool = True, id: str | None = None) -> None:
        super().__init__(id)
        self.active = bool(active)   # L13: món đã dùng không xóa mà ẩn khỏi danh sách chọn
        self.name = name
        self.calories = calories
        self.ingredients = ingredients
        self.description = description

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: Any) -> None:
        self._name = require_text(value, "Tên món", 80)

    @property
    def calories(self) -> int:
        return self._calories

    @calories.setter
    def calories(self, value: Any) -> None:
        self._calories = parse_int(value, "Năng lượng (kcal)", 0, 2000)

    @property
    def ingredients(self) -> list[str]:
        return list(self._ingredients)

    @ingredients.setter
    def ingredients(self, value: Any) -> None:
        items = value.split(",") if isinstance(value, str) else list(value or [])
        result: list[str] = []
        for item in items:
            text = normalize_spaces(item).lower()
            if text and text not in result:
                result.append(text)
        if not result:
            raise ValidationError("Món ăn phải có ít nhất một thành phần.")
        self._ingredients = result

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: Any) -> None:
        self._description = normalize_spaces(value)

    @property
    def ingredients_text(self) -> str:
        return ", ".join(self._ingredients)

    def contains(self, ingredient: str) -> bool:
        key = normalize_text(ingredient)
        return any(key in normalize_text(i) for i in self._ingredients)

    def allergen_hits(self, allergen: str) -> list[str]:
        """Các thành phần của món khớp với chất gây dị ứng."""
        return [i for i in self._ingredients if ingredient_matches_allergen(allergen, i)]

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(name=self.name, calories=self.calories, ingredients=self.ingredients,
                    description=self.description, active=self.active)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Meal":
        return cls(data["name"], data["calories"], data["ingredients"], data.get("description", ""),
                   data.get("active", True), id=data["id"])

    def __str__(self) -> str:
        return f"{self.name} ({self.calories} kcal)"


class Menu(BaseModel):
    """Thực đơn của một ngày: mỗi bữa gồm danh sách mã món ăn."""

    PREFIX = "TD"

    def __init__(self, menu_date: Any, items: dict[Any, list[str]] | None = None, note: str = "",
                 id: str | None = None) -> None:
        super().__init__(id)
        self._date = parse_date(menu_date, "Ngày thực đơn")
        self._items: dict[MealType, list[str]] = {meal_type: [] for meal_type in MealType}
        for meal_type, meal_ids in (items or {}).items():
            self.set_meals(meal_type, meal_ids)
        self.note = normalize_spaces(note)

    @property
    def date(self) -> date:
        return self._date

    @property
    def items(self) -> dict[MealType, list[str]]:
        return {k: list(v) for k, v in self._items.items()}

    def set_meals(self, meal_type: Any, meal_ids: list[str]) -> None:
        ids: list[str] = []
        for meal_id in meal_ids:
            key = str(meal_id).strip().upper()
            if key and key not in ids:
                ids.append(key)
        self._items[MealType.parse(meal_type)] = ids

    def meals_of(self, meal_type: Any) -> list[str]:
        return list(self._items[MealType.parse(meal_type)])

    def all_meal_ids(self) -> list[str]:
        return [meal_id for ids in self._items.values() for meal_id in ids]

    def remove_meal(self, meal_id: str) -> None:
        key = str(meal_id).strip().upper()
        for ids in self._items.values():
            if key in ids:
                ids.remove(key)

    @property
    def is_empty(self) -> bool:
        return not self.all_meal_ids()

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(date=self.date.isoformat(), note=self.note,
                    items={meal_type.name: ids for meal_type, ids in self._items.items()})
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Menu":
        items = {MealType[name]: ids for name, ids in data.get("items", {}).items()}
        return cls(data["date"], items, data.get("note", ""), id=data["id"])
