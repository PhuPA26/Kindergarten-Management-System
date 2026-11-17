"""Nền tảng dùng chung: BaseModel (T02), BaseManager[T] (T03), Person/Employee (T04)."""
from .base_model import BaseModel
from .base_manager import BaseManager
from .person import GENDERS, Employee, Person, parse_gender

__all__ = ["BaseModel", "BaseManager", "Person", "Employee", "GENDERS", "parse_gender"]
