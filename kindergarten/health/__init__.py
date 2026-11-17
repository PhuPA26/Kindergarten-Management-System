"""Sức khỏe: HealthRecord (T12), Allergy, HealthManager (T13)."""
from .health_manager import HealthManager
from .records import Allergy, AllergySeverity, HealthRecord, NutritionStatus, ingredient_matches_allergen

__all__ = ["HealthManager", "HealthRecord", "NutritionStatus", "Allergy", "AllergySeverity",
           "ingredient_matches_allergen"]
