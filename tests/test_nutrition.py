"""Kiểm thử Meal/Menu (T25) và MenuManager - cảnh báo dị ứng (T26)."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from kindergarten.exceptions import DuplicateIdError, KindergartenError, ValidationError
from kindergarten.nutrition.meal import MealType


def next_monday() -> date:
    today = date.today()
    return today + timedelta(days=7 - today.weekday())


@pytest.fixture
def kitchen(system, make_child):
    classroom = system.classes.create_class("Mầm 1", "Mầm", 10)
    other_class = system.classes.create_class("Lá 1", "Lá", 10)
    ngoc, phuc = make_child("Lê Bảo Ngọc", 3, gender="Nữ"), make_child("Hồ Thiên Phúc", 5)
    system.classes.enroll(ngoc.id, classroom.id)
    system.classes.enroll(phuc.id, other_class.id)
    system.health.add_allergy(ngoc.id, "tôm", "Nặng")
    system.health.add_allergy(phuc.id, "đậu phộng", "Nặng")
    menus = system.menus
    meals = {
        "rice": menus.add_meal("Cơm trắng", 200, "gạo"),
        "shrimp": menus.add_meal("Tôm rim thịt", 210, "tôm, thịt heo"),
        "soup": menus.add_meal("Canh bí đỏ đậu phộng", 120, ["bí đỏ", "đậu phộng"]),
        "milk": menus.add_meal("Sữa tươi", 130, "sữa bò"),
    }
    return SimpleNamespace(classroom=classroom, ngoc=ngoc, phuc=phuc, meals=meals)


def test_meal_and_menu(system, kitchen):
    shrimp = kitchen.meals["shrimp"]
    assert shrimp.ingredients == ["tôm", "thịt heo"] and shrimp.contains("TOM")
    with pytest.raises(DuplicateIdError):
        system.menus.add_meal("cơm trắng", 100, "gạo")
    with pytest.raises(ValidationError):
        system.menus.add_meal("Món rỗng", 100, "")
    day = next_monday()
    system.menus.set_menu(day, MealType.LUNCH, [kitchen.meals["rice"].id, shrimp.id])
    system.menus.set_menu(day, "Bữa xế", [kitchen.meals["milk"].id])
    assert system.menus.daily_calories(day) == 200 + 210 + 130


def test_allergy_warnings(system, kitchen):
    day = next_monday()
    warnings = system.menus.plan_day(day, {MealType.LUNCH: [kitchen.meals["rice"].id, kitchen.meals["shrimp"].id,
                                                            kitchen.meals["soup"].id]})
    assert {(w.child.id, w.allergy.allergen) for w in warnings} == {(kitchen.ngoc.id, "tôm"),
                                                                    (kitchen.phuc.id, "đậu phộng")}
    only_class = system.menus.allergy_warnings(day, kitchen.classroom.id)
    assert [w.child.id for w in only_class] == [kitchen.ngoc.id]
    assert "Lê Bảo Ngọc" in str(only_class[0]) and "tôm" in str(only_class[0])


def test_plan_and_copy_week(system, kitchen):
    monday = next_monday()
    system.menus.plan_week(monday, {d: {MealType.LUNCH: [kitchen.meals["rice"].id]} for d in range(5)})
    assert all(menu is not None for _, menu in system.menus.week_menus(monday))
    assert system.menus.copy_week(monday, monday + timedelta(days=7)) == 5
    assert system.menus.menu_of(monday + timedelta(days=8)) is not None
    headers, rows = system.menus.week_table(monday)
    assert headers[2] == "Bữa sáng" and rows[0][3] == "Cơm trắng"
    with pytest.raises(KindergartenError):   # L13: món đã dùng không xóa được (giữ lịch sử) - chỉ ẩn
        system.menus.meals.remove(kitchen.meals["rice"].id)
    system.menus.set_meal_active(kitchen.meals["rice"].id, False)
    assert kitchen.meals["rice"] not in system.menus.meals_sorted()
    assert system.menus.daily_calories(monday) == 200   # thực đơn cũ giữ nguyên
    system.menus.meals.remove(kitchen.meals["milk"].id)   # món chưa dùng thì xóa được
