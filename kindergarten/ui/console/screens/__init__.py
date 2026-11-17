"""Các màn hình chức năng của giao diện console (mỗi nhóm nghiệp vụ một lớp Screen)."""
from .attendance_screen import AttendanceScreen
from .base import Screen
from .children_screen import ChildrenScreen
from .class_screen import ClassScreen
from .finance_screen import FinanceScreen
from .health_screen import HealthScreen
from .hr_screen import HRScreen
from .nutrition_screen import NutritionScreen
from .report_screen import ReportScreen
from .system_screen import SystemScreen

__all__ = ["Screen", "ChildrenScreen", "HealthScreen", "HRScreen", "ClassScreen", "AttendanceScreen",
           "FinanceScreen", "NutritionScreen", "ReportScreen", "SystemScreen"]
