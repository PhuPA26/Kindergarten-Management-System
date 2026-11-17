"""Kiểm thử HealthRecord (T12), Vaccination, Allergy, HealthManager (T13)."""
from datetime import date, timedelta

import pytest

from kindergarten.exceptions import DuplicateIdError, ValidationError
from kindergarten.health.records import HealthRecord, NutritionStatus, ingredient_matches_allergen


def test_bmi_and_assessment(system, make_child):
    child = make_child("Phạm Khánh Linh", 4, gender="Nữ")
    normal = system.health.add_health_record(child.id, date.today(), 102, 16)
    assert normal.calc_bmi() == pytest.approx(15.4, abs=0.05)
    assert normal.assess() is NutritionStatus.NORMAL
    assert HealthRecord(child.id, date.today(), 105, 13, age_months=50).assess() is NutritionStatus.UNDERWEIGHT
    assert HealthRecord(child.id, date.today(), 100, 19, age_months=50).assess() is NutritionStatus.OVERWEIGHT
    with pytest.raises(ValidationError):
        system.health.add_health_record(child.id, date.today(), 300, 16)


def test_growth_history(system, make_child):
    child = make_child("Đỗ Hoàng Nam", 4)
    system.health.add_health_record(child.id, date.today() - timedelta(days=60), 100.0, 15.5)
    system.health.add_health_record(child.id, date.today() - timedelta(days=30), 101.2, 16.0)
    history = system.health.growth_history(child.id)
    assert len(history) == 2 and history[0]["height_change"] is None
    assert history[1]["height_change"] == pytest.approx(1.2)
    assert history[1]["weight_change"] == pytest.approx(0.5)
    with pytest.raises(DuplicateIdError):
        system.health.add_health_record(child.id, date.today() - timedelta(days=30), 101, 16)


def test_allergies(system, make_child):
    child = make_child("Lê Bảo Ngọc", 3, gender="Nữ")
    system.health.add_allergy(child.id, "Tôm", "Nặng", "Khó thở")
    with pytest.raises(DuplicateIdError):
        system.health.add_allergy(child.id, "tôm")
    assert [a.allergen for a in system.health.allergies_of(child.id)] == ["tôm"]
    conflicts = system.health.find_allergy_conflicts([child.id], ["gạo", "tôm sú"])
    assert len(conflicts) == 1 and conflicts[0].ingredient == "tôm sú"


def test_allergen_matching():
    assert ingredient_matches_allergen("tôm", "tôm sú")
    assert ingredient_matches_allergen("hải sản", "cua")
    assert ingredient_matches_allergen("đậu phộng", "lạc rang")
    assert ingredient_matches_allergen("sữa bò", "sữa chua")
    assert ingredient_matches_allergen("tom", "tôm")          # gõ không dấu
    assert not ingredient_matches_allergen("cá", "cà chua")   # giữ dấu: "cá" khác "cà"
    assert not ingredient_matches_allergen("trứng", "thịt heo")
