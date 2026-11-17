"""Màn hình console: nhân sự và bảng lương (T14-T15)."""
from __future__ import annotations

from datetime import date

from ....auth.user import Permission
from ....core.person import Employee
from ....exceptions import ValidationError
from ....hr.employees import Staff, Teacher
from ....reports.reports import PayrollReport
from ....utils import format_date, format_number, format_vnd, validate_name, validate_not_future
from ..menu import Menu
from .base import Screen


class HRScreen(Screen):
    title = "Nhân sự & bảng lương"

    def build_menu(self) -> Menu:
        P = Permission
        return (self.new_menu()
                .add("Danh sách nhân sự", self.list_employees, P.VIEW_EMPLOYEES)
                .add("Tìm kiếm nhân sự (tên / chức vụ)", self.search, P.VIEW_EMPLOYEES)
                .add("Xem hồ sơ nhân sự", self.view, P.VIEW_EMPLOYEES)
                .add("Thêm giáo viên", self.add_teacher, P.MANAGE_EMPLOYEES)
                .add("Thêm nhân viên", self.add_staff, P.MANAGE_EMPLOYEES)
                .add("Sửa thông tin nhân sự", self.edit, P.MANAGE_EMPLOYEES)
                .add("Xóa nhân sự", self.delete, P.MANAGE_EMPLOYEES)
                .add("Nhập giờ làm thêm của nhân viên", self.overtime, P.MANAGE_EMPLOYEES)
                .add("In bảng lương tháng", self.payroll, P.VIEW_PAYROLL)
                .add("Chốt / mở lại bảng lương tháng", self.close_payroll, P.VIEW_PAYROLL))

    def close_payroll(self) -> None:
        """L15: chốt lương lưu bản chụp, kỳ đã chốt không thay đổi theo hệ số/phụ cấp về sau."""
        month, year = self.ask_month("Tháng lương", previous=True)
        employees = self.system.employees
        if employees.is_closed(month, year):
            if self.confirm(f"Bảng lương tháng {month:02d}/{year} đã chốt. Mở lại để tính lại"):
                employees.reopen_payroll(month, year)
                self.system.audit("Mở lại bảng lương", f"{month:02d}/{year}")
                self.io.success("Đã mở lại bảng lương.")
            return
        self.io.write(employees.payroll_text(month, year))
        if self.confirm(f"Chốt bảng lương tháng {month:02d}/{year}"):
            employees.close_payroll(month, year, self.system.username)
            self.system.audit("Chốt bảng lương", f"{month:02d}/{year}")
            self.io.success("Đã chốt bảng lương.")

    def show(self, employees: list[Employee], title: str) -> None:
        rows = []
        for index, e in enumerate(employees, 1):
            position = e.position + (f" {e.specialty}" if isinstance(e, Teacher) and e.specialty else "")
            homeroom = self.class_name(e.homeroom_class_id) if isinstance(e, Teacher) and e.homeroom_class_id else "-"
            rows.append([index, e.id, e.full_name, e.role_name, position, e.phone, format_date(e.hire_date),
                         f"{e.years_of_service()} năm", homeroom])
        self.io.table(["STT", "Mã", "Họ tên", "Loại", "Chức vụ", "SĐT", "Vào làm", "Thâm niên", "Lớp CN"], rows,
                      title=f"{title} ({len(employees)} người)")

    def list_employees(self) -> None:
        self.show(self.system.employees.all_sorted(), "DANH SÁCH NHÂN SỰ")

    def search(self) -> None:
        mode = self.io.ask_choice("Tìm theo", [("name", "Họ tên / SĐT"), ("position", "Chức vụ / chuyên môn")])
        keyword = self.io.ask_text("Từ khóa")
        manager = self.system.employees
        result = manager.search_by_name(keyword) if mode == "name" else manager.find_by_position(keyword)
        self.show(result, "KẾT QUẢ TÌM KIẾM")

    def view(self) -> None:
        employee = self.select_employee()
        self.io.key_values(employee.profile(), title=f"\nHỒ SƠ NHÂN SỰ: {employee.full_name.upper()}")
        self.io.write("Cách tính lương tháng này: " + employee.salary_note())

    def _phone_checker(self, exclude: Employee | None = None):
        def check(phone: str) -> None:
            other = self.system.employees.find_one(lambda e: e.phone == phone and e is not exclude)
            if other is not None:
                raise ValidationError(f"SĐT {phone} đã được dùng cho {other}.")
        return check

    def _ask_common(self, employee: Employee | None = None) -> dict:
        io = self.io
        return {
            "full_name": io.ask_text("Họ tên", employee.full_name if employee else None, validator=validate_name),
            "dob": self.ask_dob(Teacher, employee.dob if employee else None),
            "phone": io.ask_phone("Số điện thoại", employee.phone if employee else None,
                                  check=self._phone_checker(employee)),
            "gender": io.ask_choice("Giới tính", [("Nam", "Nam"), ("Nữ", "Nữ")],
                                    default=employee.gender if employee else None),
            "address": io.ask_text("Địa chỉ", employee.address if employee else None, required=False),
            "hire_date": io.ask_date("Ngày vào làm", employee.hire_date if employee else date.today(),
                                     check=lambda d: validate_not_future(d, "Ngày vào làm")),
        }

    def add_teacher(self) -> None:
        io = self.io
        data = self._ask_common()
        data["address"] = data["address"] or ""
        data["qualification"] = io.ask_choice("Trình độ", [(q, q) for q in Teacher.QUALIFICATIONS], "Cao đẳng")
        data["salary_coefficient"] = io.ask_float("Hệ số lương", 2.10, 1.0, 10.0)
        data["specialty"] = io.ask_text("Chuyên môn (để trống nếu là GV đứng lớp)", required=False) or ""
        teacher = self.system.employees.add(Teacher(**data))
        io.success(f"Đã thêm giáo viên {teacher}. Lương dự kiến: {format_vnd(teacher.calculate_salary())}.")

    def add_staff(self) -> None:
        io = self.io
        data = self._ask_common()
        data["address"] = data["address"] or ""
        options = [(p, p) for p in Staff.POSITIONS] + [("", "Khác (tự nhập)")]
        data["position"] = io.ask_choice("Chức vụ", options) or io.ask_text("Chức vụ")
        data["base_salary"] = io.ask_money("Lương cơ bản", 5_000_000, allow_zero=False)
        data["allowance"] = io.ask_money("Phụ cấp", 0)
        staff = self.system.employees.add(Staff(**data))
        io.success(f"Đã thêm nhân viên {staff}. Lương dự kiến: {format_vnd(staff.calculate_salary())}.")

    def edit(self) -> None:
        io = self.io
        employee = self.select_employee()
        io.info("Nhấn Enter để giữ nguyên giá trị hiện tại.")
        data = self._ask_common(employee)
        if isinstance(employee, Teacher):
            data["qualification"] = io.ask_choice("Trình độ", [(q, q) for q in Teacher.QUALIFICATIONS],
                                                  employee.qualification)
            data["salary_coefficient"] = io.ask_float("Hệ số lương", employee.salary_coefficient, 1.0, 10.0)
            data["specialty"] = io.ask_text("Chuyên môn", employee.specialty, required=False)
        else:
            data["position"] = io.ask_text("Chức vụ", employee.position)
            data["base_salary"] = io.ask_money("Lương cơ bản", employee.base_salary, allow_zero=False)
            data["allowance"] = io.ask_money("Phụ cấp", employee.allowance)
        changes = {k: v for k, v in data.items() if v is not None and v != getattr(employee, k)}
        if not changes:
            io.info("Không có thay đổi.")
            return
        self.system.employees.update(employee.id, **changes)
        io.success(f"Đã cập nhật {employee}.")

    def delete(self) -> None:
        employee = self.select_employee()
        if self.confirm(f"Xóa nhân sự {employee}? (tài khoản liên kết sẽ bị khóa)"):
            self.system.employees.remove(employee.id)
            self.io.success(f"Đã xóa {employee}.")

    def overtime(self) -> None:
        staff = self.select_employee(self.system.employees.staff_members(), "Chọn nhân viên")
        month, year = self.ask_month()
        current = staff.overtime_hours(month, year)
        hours = self.io.ask_float("Số giờ làm thêm trong tháng", current, 0, 200)
        self.system.employees.set_overtime(staff.id, month, year, hours)
        self.io.success(f"Đã lưu {format_number(hours, 1)} giờ làm thêm cho {staff.full_name}. "
                        f"Lương tháng: {format_vnd(staff.calculate_salary(month, year))}.")

    def payroll(self) -> None:
        month, year = self.ask_month("Tháng tính lương")
        report = PayrollReport(self.system, month, year)
        self.io.write(report.to_text())
        self.export_report(report)
