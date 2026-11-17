"""T26 - MenuManager: lập thực đơn tuần, cảnh báo món chứa chất mà trẻ trong lớp bị dị ứng (nối với T13)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from ..classroom.class_manager import ClassManager
from ..core.base_manager import BaseManager
from ..exceptions import DuplicateIdError, KindergartenError, ValidationError
from ..health.health_manager import HealthManager
from ..health.records import Allergy
from ..people.child import Child
from ..people.managers import ChildManager
from ..school_calendar import SchoolCalendar
from ..utils import format_date, format_table, monday_of, normalize_text, parse_date, weekday_name
from .meal import Meal, MealType, Menu


@dataclass
class AllergyWarning:
    menu_date: date
    meal_type: MealType
    meal: Meal
    child: Child
    allergy: Allergy
    ingredient: str
    class_name: str = ""

    def __str__(self) -> str:
        return (f"[!] {weekday_name(self.menu_date)} {format_date(self.menu_date)} - {self.meal_type.value}: "
                f"món '{self.meal.name}' có '{self.ingredient}' -> {self.child.full_name}"
                f"{f' ({self.class_name})' if self.class_name else ''} dị ứng {self.allergy.allergen} "
                f"(mức {self.allergy.severity.value.lower()})")


class MealManager(BaseManager[Meal]):
    """L13: kiểm tra trùng tên cả khi thêm lẫn khi sửa; không xóa món đã dùng trong thực đơn (chỉ ẩn)."""

    entity_name = "món ăn"

    def __init__(self) -> None:
        super().__init__()
        self.usage_lookup: Callable[[str], list[date]] | None = None

    def _check_unique_name(self, meal: Meal) -> None:
        key = normalize_text(meal.name)
        if any(m is not meal and normalize_text(m.name) == key for m in self._items.values()):
            raise DuplicateIdError(f"Đã có món '{meal.name}'.")

    def _validate_new(self, meal: Meal) -> None:
        self._check_unique_name(meal)

    def _validate_update(self, meal: Meal) -> None:
        self._check_unique_name(meal)

    def _before_remove(self, meal: Meal) -> None:
        used = self.usage_lookup(meal.id) if self.usage_lookup else []
        if used:
            raise KindergartenError(f"Món '{meal.name}' đã có trong thực đơn {len(used)} ngày (gần nhất "
                                    f"{format_date(max(used))}); không xóa để giữ lịch sử ăn uống. "
                                    "Hãy dùng chức năng ẩn món.")


class MenuManager(BaseManager[Menu]):
    entity_name = "thực đơn"

    def __init__(self, health_manager: HealthManager, child_manager: ChildManager,
                 class_manager: ClassManager, calendar: SchoolCalendar | None = None) -> None:
        super().__init__()
        self.health = health_manager
        self.children = child_manager
        self.classes = class_manager
        self.calendar = calendar or SchoolCalendar()
        self.meals = MealManager()
        self.meals.usage_lookup = self.days_using_meal
        self._by_date: dict[date, Menu] = {}   # P04: chỉ mục ngày -> thực đơn

    # ------------------------------------------------------------------ chỉ mục
    def _validate_new(self, menu: Menu) -> None:
        if menu.date in self._by_date:
            raise DuplicateIdError(f"Đã có thực đơn ngày {format_date(menu.date)}.")

    def _after_add(self, menu: Menu) -> None:
        self._by_date[menu.date] = menu

    def _after_remove(self, menu: Menu) -> None:
        self._by_date.pop(menu.date, None)

    def _after_clear(self) -> None:
        self._by_date.clear()

    def days_using_meal(self, meal_id: str) -> list[date]:
        key = self._key(meal_id)
        return [m.date for m in self._items.values() if key in m.all_meal_ids()]

    # ------------------------------------------------------------------ món ăn
    def add_meal(self, name: str, calories: Any, ingredients: Any, description: str = "") -> Meal:
        return self.meals.add(Meal(name, calories, ingredients, description))

    def set_meal_active(self, meal_id: str, active: bool) -> Meal:
        """Ẩn/hiện món trong danh sách chọn (món đã dùng không xóa được - L13)."""
        return self.meals.update(meal_id, active=bool(active))

    def meals_sorted(self, include_hidden: bool = False) -> list[Meal]:
        return self.meals.sort("name", items=[m for m in self.meals if include_hidden or m.active])

    def search_meals(self, keyword: str) -> list[Meal]:
        return self.meals.sort("name", items=self.meals.search(keyword, "name", "ingredients_text"))

    # ------------------------------------------------------------------ thực đơn
    def menu_of(self, on_date: Any) -> Menu | None:
        return self._by_date.get(parse_date(on_date))

    def check_menu_day(self, on_date: Any) -> date:
        """L20: thực đơn chỉ lập cho ngày học theo lịch (cùng định nghĩa với điểm danh)."""
        d = parse_date(on_date, "Ngày thực đơn")
        if not self.calendar.is_school_day(d):
            raise ValidationError(self.calendar.reason_not_school_day(d) + " Không lập thực đơn.")
        return d

    def set_menu(self, on_date: Any, meal_type: Any, meal_ids: list[str]) -> Menu | None:
        """Đặt các món cho một bữa trong ngày (chỉ ghi - P05). Bữa rỗng hết thì xóa luôn thực đơn ngày (L20)."""
        d = self.check_menu_day(on_date)
        self._authorize()
        ids = [self.meals.get(meal_id).id for meal_id in meal_ids]
        menu = self.menu_of(d)
        if menu is None:
            if not ids:
                return None
            menu = self.add(Menu(d))
        menu.set_meals(meal_type, ids)
        if menu.is_empty:
            self.remove(menu.id)
            return None
        return menu

    def plan_day(self, on_date: Any, plan: dict[Any, list[str]]) -> list[AllergyWarning]:
        d = self.check_menu_day(on_date)
        for meal_type, meal_ids in plan.items():
            self.set_menu(d, meal_type, meal_ids)
        return self.allergy_warnings(d)   # tính cảnh báo MỘT lần sau khi ghi xong

    def plan_week(self, any_date: Any, plan: dict[int, dict[Any, list[str]]]) -> list[AllergyWarning]:
        """Lập thực đơn tuần. `plan` = {thứ (0=Thứ 2..5=Thứ 7): {bữa: [mã món]}}."""
        start = monday_of(parse_date(any_date))
        for weekday, day_plan in plan.items():
            if not 0 <= int(weekday) <= 5:
                raise ValidationError("Thứ trong tuần không hợp lệ.")
            for meal_type, meal_ids in day_plan.items():
                self.set_menu(start + timedelta(days=int(weekday)), meal_type, meal_ids)
        return self.week_allergy_warnings(start)

    def copy_week(self, from_date: Any, to_date: Any) -> int:
        """Sao chép thực đơn tuần chứa `from_date` sang tuần chứa `to_date` (GHI ĐÈ các ngày trùng)."""
        source, target = monday_of(parse_date(from_date)), monday_of(parse_date(to_date))
        if source == target:
            raise ValidationError("Tuần nguồn và tuần đích trùng nhau.")
        copied = 0
        for offset in range(6):
            menu = self.menu_of(source + timedelta(days=offset))
            day = target + timedelta(days=offset)
            if menu is None or menu.is_empty or not self.calendar.is_school_day(day):
                continue
            for meal_type, ids in menu.items.items():
                self.set_menu(day, meal_type, ids)
            copied += 1
        if copied == 0:
            raise ValidationError(f"Tuần {format_date(source)} chưa có thực đơn để sao chép.")
        return copied

    def overwritten_days(self, to_date: Any) -> list[date]:
        """Các ngày ở tuần đích đã có thực đơn (sẽ bị ghi đè khi sao chép)."""
        return [d for d, menu in self.week_menus(to_date) if menu is not None]

    def meals_of(self, menu: Menu) -> dict[MealType, list[Meal]]:
        return {meal_type: [m for m in (self.meals.get_or_none(i) for i in ids) if m]
                for meal_type, ids in menu.items.items()}

    def daily_calories(self, on_date: Any) -> int:
        menu = self.menu_of(on_date)
        if menu is None:
            return 0
        return sum(m.calories for meals in self.meals_of(menu).values() for m in meals)

    def week_menus(self, any_date: Any) -> list[tuple[date, Menu | None]]:
        """Các ngày của tuần theo lịch (Thứ 2-6, thêm Thứ 7 nếu trường học Thứ 7) - L20."""
        return [(d, self.menu_of(d)) for d in self.calendar.week_days(parse_date(any_date))]

    # ------------------------------------------------------------------ cảnh báo dị ứng (T13 + T26)
    def _target_children(self, class_id: str | None, class_ids: set[str] | None = None) -> list[Child]:
        if class_id:
            return self.classes.class_list(class_id)
        return [c for c in self.children.all_sorted() if c.class_id and (class_ids is None or c.class_id in class_ids)]

    def allergy_warnings(self, on_date: Any, class_id: str | None = None,
                         class_ids: set[str] | None = None) -> list[AllergyWarning]:
        d = parse_date(on_date)
        menu = self.menu_of(d)
        if menu is None:
            return []
        child_ids = [c.id for c in self._target_children(class_id, class_ids)]
        warnings = []
        for meal_type, meals in self.meals_of(menu).items():
            for meal in meals:
                for conflict in self.health.find_allergy_conflicts(child_ids, meal.ingredients):
                    child = self.children.get(conflict.child_id)
                    warnings.append(AllergyWarning(d, meal_type, meal, child, conflict.allergy,
                                                   conflict.ingredient, self.classes.class_name(child.class_id)))
        return warnings

    def week_allergy_warnings(self, any_date: Any, class_id: str | None = None,
                              class_ids: set[str] | None = None) -> list[AllergyWarning]:
        warnings = []
        for d, menu in self.week_menus(any_date):
            if menu is not None:
                warnings.extend(self.allergy_warnings(d, class_id, class_ids))
        return warnings

    def week_table(self, any_date: Any) -> tuple[list[str], list[list[Any]]]:
        headers = ["Thứ", "Ngày", *[t.value for t in MealType], "Năng lượng"]
        rows = []
        for d, menu in self.week_menus(any_date):
            holiday = self.calendar.holiday_name(d)
            if menu is None:
                rows.append([weekday_name(d), format_date(d), holiday or "-", "-", "-", "-"])
                continue
            meals = self.meals_of(menu)
            rows.append([weekday_name(d), format_date(d),
                         *[", ".join(m.name for m in meals[t]) or "-" for t in MealType],
                         f"{self.daily_calories(d)} kcal"])
        return headers, rows

    def week_text(self, any_date: Any) -> str:
        start = monday_of(parse_date(any_date))
        headers, rows = self.week_table(start)
        return format_table(headers, rows, title=f"THỰC ĐƠN TUẦN TỪ {format_date(start)}", max_width=45)
