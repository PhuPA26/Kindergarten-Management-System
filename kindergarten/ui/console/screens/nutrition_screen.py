"""Màn hình console: món ăn, thực đơn tuần, cảnh báo dị ứng (T25-T26)."""
from __future__ import annotations

from datetime import date, timedelta

from ....auth.user import Permission, Role
from ....exceptions import ValidationError
from ....nutrition.meal import Meal, MealType
from ....utils import format_date, monday_of, weekday_name
from ..menu import Menu
from .base import Screen


class NutritionScreen(Screen):
    title = "Thực đơn & dinh dưỡng"

    def build_menu(self) -> Menu:
        P = Permission
        return (self.new_menu()
                .add("Xem thực đơn tuần", self.view_week, P.VIEW_MENU)
                .add("Cảnh báo dị ứng theo thực đơn tuần", self.week_warnings, P.VIEW_MENU)
                .add("Danh sách món ăn", self.list_meals, P.VIEW_MENU)
                .add("Thêm món ăn", self.add_meal, P.MANAGE_MENU)
                .add("Sửa món ăn", self.edit_meal, P.MANAGE_MENU)
                .add("Lập / sửa thực đơn một ngày", self.plan_day, P.MANAGE_MENU)
                .add("Sao chép thực đơn từ tuần khác", self.copy_week, P.MANAGE_MENU)
                .add("Ẩn / hiện món ăn", self.toggle_meal, P.MANAGE_MENU)
                .add("Xóa món ăn chưa từng dùng", self.delete_meal, P.MANAGE_MENU))

    def _show_warnings(self, warnings: list) -> None:
        if not warnings:
            self.io.success("Không có món nào chứa chất gây dị ứng cho trẻ.")
            return
        self.io.warning(f"Có {len(warnings)} cảnh báo dị ứng:")
        for warning in warnings:
            self.io.write(self.io.paint(f"  {warning}", "yellow"))

    def view_week(self) -> None:
        day = self.io.ask_date("Xem tuần chứa ngày", date.today())
        self.io.write(self.system.menus.week_text(day))

    def week_warnings(self) -> None:
        day = self.io.ask_date("Kiểm tra tuần chứa ngày", date.today())
        scope = self.scope_class_ids()
        class_id = None
        if scope is None:   # giáo viên tự động chỉ xem lớp mình phụ trách (không còn phép đoán theo số lớp)
            classroom = self.io.choose(self.system.classes.all_sorted(), self.class_label,
                                       "Chọn lớp (Enter = toàn trường)")
            class_id = classroom.id if classroom else None
        self._show_warnings(self.system.menus.week_allergy_warnings(day, class_id, scope))

    def list_meals(self) -> None:
        rows = [[m.id, m.name, m.calories, m.ingredients_text, "đang dùng" if m.active else "ĐÃ ẨN"]
                for m in self.system.menus.meals_sorted(include_hidden=True)]
        self.io.table(["Mã", "Tên món", "Kcal", "Thành phần", "Trạng thái"], rows, title="DANH SÁCH MÓN ĂN",
                      max_width=50)

    def add_meal(self) -> None:
        io = self.io
        meal = self.system.menus.add_meal(io.ask_text("Tên món"), io.ask_int("Năng lượng (kcal/suất)", None, 0, 2000),
                                          io.ask_text("Thành phần (cách nhau dấu phẩy)"),
                                          io.ask_text("Mô tả", required=False) or "")
        io.success(f"Đã thêm món {meal}.")

    def _select_meal(self, title: str = "Chọn món", include_hidden: bool = False) -> Meal:
        return self._require(self.io.choose(self.system.menus.meals_sorted(include_hidden),
                                            lambda m: f"{m.id} - {m.name} ({m.ingredients_text})"
                                                      + ("" if m.active else " [đã ẩn]"), title,
                                            "Chưa có món ăn nào."))

    def edit_meal(self) -> None:
        io = self.io
        meal = self._select_meal(include_hidden=True)
        new_data = {"name": io.ask_text("Tên món", meal.name),
                    "calories": io.ask_int("Năng lượng (kcal)", meal.calories, 0, 2000),
                    "ingredients": io.ask_text("Thành phần", meal.ingredients_text),
                    "description": io.ask_text("Mô tả", meal.description, required=False)}
        if isinstance(new_data["ingredients"], str):
            new_data["ingredients"] = [i.strip().lower() for i in new_data["ingredients"].split(",") if i.strip()]
        changes = {k: v for k, v in new_data.items() if v is not None and v != getattr(meal, k)}
        if changes:
            self.system.menus.meals.update(meal.id, **changes)   # trùng tên được kiểm tra cả khi sửa (L13)
            io.success(f"Đã cập nhật món {meal}.")
        else:
            io.info("Không có thay đổi.")

    def toggle_meal(self) -> None:
        meal = self._select_meal("Chọn món cần ẩn / hiện", include_hidden=True)
        self.system.menus.set_meal_active(meal.id, not meal.active)
        self.io.success(f"Món {meal.name} đã được {'hiện lại' if meal.active else 'ẩn khỏi danh sách chọn'}.")

    def delete_meal(self) -> None:
        """L13: món đã có trong thực đơn không xóa được (giữ lịch sử ăn uống) - chỉ ẩn."""
        meal = self._select_meal("Chọn món cần xóa", include_hidden=True)
        used = self.system.menus.days_using_meal(meal.id)
        if used:
            if self.confirm(f"Món {meal.name} đã dùng trong {len(used)} ngày thực đơn nên không xóa được. Ẩn món"):
                self.system.menus.set_meal_active(meal.id, False)
                self.io.success("Đã ẩn món.")
            return
        if self.confirm(f"Xóa món {meal.name}?"):
            self.system.menus.meals.remove(meal.id)
            self.io.success("Đã xóa món ăn.")

    def plan_day(self) -> None:
        io, menus = self.io, self.system.menus
        # U06: kiểm tra ngày học ngay khi nhập ngày, trước khi phải chọn món
        day = io.ask_date("Ngày lập thực đơn", date.today(), check=menus.check_menu_day)
        meals = menus.meals_sorted()
        if not meals:
            raise ValidationError("Chưa có món ăn nào, hãy thêm món ăn trước.")
        io.table(["STT", "Món", "Kcal", "Thành phần"],
                 [[i, m.name, m.calories, m.ingredients_text] for i, m in enumerate(meals, 1)],
                 title="DANH MỤC MÓN ĂN", max_width=50)
        menu = menus.menu_of(day)
        plan: dict[MealType, list[str]] = {}
        for meal_type in MealType:
            current = menu.meals_of(meal_type) if menu else []
            names = ", ".join(menus.meals.get(i).name for i in current if menus.meals.exists(i)) or "(trống)"
            io.info(f"{meal_type.value} hiện tại: {names}")
            # U09: '-' để xóa trống bữa, Enter để giữ nguyên
            raw = io.ask(f"Chọn món cho {meal_type.value.lower()} (STT cách nhau dấu phẩy, '-' = để trống)",
                         lambda text: [] if text == "-" else self._parse_indexes(text, len(meals)), required=False)
            if raw is not None:
                plan[meal_type] = [meals[i - 1].id for i in raw]
        if not plan:
            io.info("Không có thay đổi.")
            return
        warnings = menus.plan_day(day, plan)
        io.success(f"Thực đơn {weekday_name(day)} {format_date(day)}: {menus.daily_calories(day)} kcal.")
        self._show_warnings(warnings)

    @staticmethod
    def _parse_indexes(text: str, count: int) -> list[int]:
        result = []
        for part in text.replace(",", " ").split():
            if not part.isdigit() or not 1 <= int(part) <= count:
                raise ValidationError(f"'{part}' không phải số thứ tự từ 1 đến {count}.")
            result.append(int(part))
        return result

    def copy_week(self) -> None:
        io, menus = self.io, self.system.menus
        this_monday = monday_of(date.today())
        source = io.ask_date("Sao chép từ tuần chứa ngày", this_monday - timedelta(days=7))
        target = io.ask_date("Sang tuần chứa ngày", this_monday + timedelta(days=7))
        overwritten = menus.overwritten_days(target)
        if overwritten and not self.confirm("Tuần đích đã có thực đơn các ngày "
                                            f"{', '.join(format_date(d) for d in overwritten)} - sẽ bị GHI ĐÈ. Tiếp tục"):
            return
        copied = menus.copy_week(source, target)
        io.success(f"Đã sao chép {copied} ngày sang tuần bắt đầu {format_date(monday_of(target))}.")
        self._show_warnings(menus.week_allergy_warnings(target))
