"""T15 - EmployeeManager: hồ sơ nhân sự, tìm kiếm, in bảng lương tháng.

L15: bảng lương gắn với kỳ - bỏ nhân sự chưa vào làm; kỳ đã "chốt lương" đọc từ bản chụp lưu trong payroll.json.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..auth.user import Permission
from ..core.base_manager import BaseManager
from ..core.person import Employee
from ..exceptions import DuplicateIdError, KindergartenError, ValidationError
from ..utils import format_table, format_vnd, month_bounds, month_label, normalize_text
from .employees import Staff, Teacher


def _period_key(month: int, year: int) -> str:
    return f"{year:04d}-{month:02d}"


class EmployeeManager(BaseManager[Employee]):
    entity_name = "nhân sự"

    def __init__(self) -> None:
        super().__init__()
        self._closed: dict[str, dict[str, Any]] = {}   # kỳ đã chốt: "2026-10" -> {"closed_at", "by", "rows"}

    def _check_unique_phone(self, employee: Employee) -> None:
        other = self.find_one(lambda e: e.phone == employee.phone and e is not employee)
        if other is not None:
            raise DuplicateIdError(f"SĐT {employee.phone} đã được dùng cho {other}.")

    def _validate_new(self, employee: Employee) -> None:
        self._check_unique_phone(employee)

    def _validate_update(self, employee: Employee) -> None:
        self._check_unique_phone(employee)
        employee.validate_dates()   # L11: sửa ngày sinh vẫn phải đủ 18 tuổi lúc vào làm

    # ------------------------------------------------------------------ truy vấn
    def all_sorted(self) -> list[Employee]:
        return self.sort(lambda e: (0 if isinstance(e, Teacher) else 1, e.id_sort_key))

    def teachers(self) -> list[Teacher]:
        return [e for e in self.sort("id") if isinstance(e, Teacher)]

    def staff_members(self) -> list[Staff]:
        return [e for e in self.sort("id") if isinstance(e, Staff)]

    def get_teacher(self, teacher_id: str) -> Teacher:
        employee = self.get(teacher_id)
        if not isinstance(employee, Teacher):
            raise ValidationError(f"{employee} không phải giáo viên.")
        return employee

    def get_staff(self, staff_id: str) -> Staff:
        employee = self.get(staff_id)
        if not isinstance(employee, Staff):
            raise ValidationError(f"{employee} không phải nhân viên (giáo viên không tính giờ làm thêm).")
        return employee

    def search_by_name(self, keyword: str) -> list[Employee]:
        return self.sort("sort_key", items=self.search(keyword, "full_name", "phone"))

    def find_by_position(self, keyword: str) -> list[Employee]:
        key = normalize_text(keyword)
        return self.sort("sort_key", items=self.find(
            lambda e: key in normalize_text(f"{e.position} {getattr(e, 'specialty', '')}")))

    # ------------------------------------------------------------------ lương
    def set_overtime(self, staff_id: str, month: int, year: int, hours: Any) -> Staff:
        self._authorize()
        if self.is_closed(month, year):
            raise KindergartenError(f"Bảng lương tháng {month_label(month, year)} đã chốt, không sửa giờ làm thêm.")
        staff = self.get_staff(staff_id)
        staff.set_overtime(month, year, hours)
        return staff

    def employees_in_period(self, month: int, year: int) -> list[Employee]:
        """Nhân sự đã vào làm tính đến cuối kỳ (L15)."""
        period_end = month_bounds(month, year)[1]
        return [e for e in self.all_sorted() if e.hire_date <= period_end]

    def payroll(self, month: int, year: int) -> list[dict[str, Any]]:
        """Bảng lương tháng: mỗi người gọi calculate_salary() theo đúng lớp của mình (đa hình).

        Kỳ đã chốt trả về bản chụp, không tính lại theo hệ số/phụ cấp hiện tại.
        """
        closed = self._closed.get(_period_key(month, year))
        if closed is not None:
            return [dict(row) for row in closed["rows"]]
        rows = []
        for employee in self.employees_in_period(month, year):
            position = employee.position
            if isinstance(employee, Teacher) and employee.specialty:
                position = f"{position} {employee.specialty}"
            rows.append({
                "employee_id": employee.id,
                "name": employee.full_name,
                "type": employee.role_name,
                "position": position,
                "salary": employee.calculate_salary(month, year),
                "note": employee.salary_note(month, year),
            })
        return rows

    def total_payroll(self, month: int, year: int, rows: list[dict[str, Any]] | None = None) -> int:
        return sum(row["salary"] for row in (rows if rows is not None else self.payroll(month, year)))

    def payroll_table(self, month: int, year: int, rows: list[dict[str, Any]] | None = None
                      ) -> tuple[list[str], list[list[Any]]]:
        rows = rows if rows is not None else self.payroll(month, year)
        headers = ["STT", "Mã", "Họ tên", "Loại", "Chức vụ", "Cách tính", "Thực lĩnh"]
        table = [[i, r["employee_id"], r["name"], r["type"], r["position"], r["note"], format_vnd(r["salary"])]
                 for i, r in enumerate(rows, 1)]
        return headers, table

    def payroll_text(self, month: int, year: int) -> str:
        rows = self.payroll(month, year)   # P05: tính một lần, dùng lại cho bảng và tổng
        headers, table = self.payroll_table(month, year, rows)
        status = " (ĐÃ CHỐT)" if self.is_closed(month, year) else ""
        text = format_table(headers, table, title=f"BẢNG LƯƠNG THÁNG {month_label(month, year)}{status}",
                            max_width=70)
        return f"{text}\nTổng quỹ lương: {format_vnd(self.total_payroll(month, year, rows))}"

    # ------------------------------------------------------------------ chốt lương (L15)
    def is_closed(self, month: int, year: int) -> bool:
        return _period_key(month, year) in self._closed

    def _authorize_payroll(self) -> None:
        """Chốt lương là việc của người có quyền xem bảng lương (kế toán, quản trị)."""
        if self._auth is not None and self._auth.current_user is not None:
            self._auth.check_permission(Permission.VIEW_PAYROLL)

    def close_payroll(self, month: int, year: int, by: str = "") -> list[dict[str, Any]]:
        self._authorize_payroll()
        if self.is_closed(month, year):
            raise KindergartenError(f"Bảng lương tháng {month_label(month, year)} đã chốt trước đó.")
        rows = self.payroll(month, year)
        self._closed[_period_key(month, year)] = {"closed_at": datetime.now().isoformat(timespec="seconds"),
                                                  "by": by, "rows": rows}
        return rows

    def reopen_payroll(self, month: int, year: int) -> None:
        self._authorize_payroll()
        if self._closed.pop(_period_key(month, year), None) is None:
            raise KindergartenError(f"Bảng lương tháng {month_label(month, year)} chưa chốt.")

    def closed_payrolls_to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in sorted(self._closed.items())}

    def load_closed_payrolls(self, data: dict[str, Any] | None) -> None:
        self._closed = dict(data or {})
