"""Lớp cơ sở cho các màn hình console: tạo menu, chọn đối tượng, xuất báo cáo."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, Iterable

from ....auth.user import User
from ....classroom.classroom import Classroom
from ....core.person import Employee
from ....exceptions import InvalidAgeError, ValidationError
from ....hr.employees import Teacher
from ....people.child import Child
from ....people.parent import Parent
from ....reports.reports import Report
from ....utils import calculate_age, format_date, parse_date, previous_month
from ..console_io import CancelledInput
from ..menu import Menu

if TYPE_CHECKING:
    from ..main_menu import MainMenu


class Screen:
    title = "Chức năng"

    def __init__(self, app: "MainMenu") -> None:
        self.app = app
        self.system = app.system
        self.io = app.io

    @property
    def auth(self):
        return self.system.auth

    @property
    def user(self) -> User | None:
        return self.system.auth.current_user

    def build_menu(self) -> Menu:
        raise NotImplementedError

    def run(self) -> None:
        self.build_menu().run()

    def new_menu(self) -> Menu:
        return self.app.new_menu(self.title)

    # ------------------------------------------------------------------ nhãn hiển thị
    def class_name(self, class_id: str | None) -> str:
        return self.system.classes.class_name(class_id)

    def child_label(self, child: Child) -> str:
        return f"{child.id} - {child.full_name} ({child.age_text}, {self.class_name(child.class_id)})"

    @staticmethod
    def parent_label(parent: Parent) -> str:
        return f"{parent.id} - {parent.full_name} ({parent.relationship}, {parent.phone})"

    @staticmethod
    def class_label(classroom: Classroom) -> str:
        return f"{classroom.id} - {classroom.display_name} - sĩ số {classroom.size}/{classroom.capacity}"

    @staticmethod
    def employee_label(employee: Employee) -> str:
        extra = f" {employee.specialty}" if isinstance(employee, Teacher) and employee.specialty else ""
        return f"{employee.id} - {employee.full_name} ({employee.position}{extra})"

    # ------------------------------------------------------------------ chọn đối tượng
    @staticmethod
    def _require(value: Any) -> Any:
        if value is None:
            raise CancelledInput
        return value

    def visible_children(self, children: Iterable[Child] | None = None) -> list[Child]:
        """Trẻ mà người dùng hiện tại được làm việc (giáo viên chủ nhiệm: trẻ lớp mình)."""
        allowed = self.system.children_for(self.user)
        if children is None:
            return allowed
        allowed_ids = {c.id for c in allowed}
        return [c for c in children if c.id in allowed_ids]

    def select_child(self, children: Iterable[Child] | None = None, title: str = "Chọn trẻ") -> Child:
        items = self.visible_children() if children is None else list(children)
        return self._require(self.io.choose(items, self.child_label, title, "Không có trẻ nào phù hợp."))

    def visible_parents(self) -> list[Parent]:
        """L09: giáo viên chỉ thấy phụ huynh của trẻ lớp mình."""
        if self.system.class_ids_for(self.user) is None:
            return self.system.parents.all_sorted()
        return self.system.parents.parents_of_children({c.id for c in self.visible_children()})

    def scope_class_ids(self) -> set[str] | None:
        """Phạm vi lớp của người dùng (None = toàn trường)."""
        return self.system.class_ids_for(self.user)

    def select_parent(self, parents: Iterable[Parent] | None = None, title: str = "Chọn phụ huynh") -> Parent:
        items = self.visible_parents() if parents is None else list(parents)
        return self._require(self.io.choose(items, self.parent_label, title, "Chưa có phụ huynh nào."))

    def select_class(self, classes: Iterable[Classroom] | None = None, title: str = "Chọn lớp") -> Classroom:
        items = self.system.classes_for(self.user) if classes is None else list(classes)
        return self._require(self.io.choose(items, self.class_label, title, "Chưa có lớp nào phù hợp."))

    def select_employee(self, employees: Iterable[Employee] | None = None, title: str = "Chọn nhân sự") -> Employee:
        items = self.system.employees.all_sorted() if employees is None else list(employees)
        return self._require(self.io.choose(items, self.employee_label, title, "Chưa có nhân sự nào."))

    def select_teacher(self, teachers: Iterable[Teacher] | None = None, title: str = "Chọn giáo viên") -> Teacher:
        items = self.system.employees.teachers() if teachers is None else list(teachers)
        return self._require(self.io.choose(items, self.employee_label, title, "Chưa có giáo viên nào."))

    # ------------------------------------------------------------------ nhập dữ liệu hay dùng
    def ask_month(self, prompt: str = "Tháng", previous: bool = False) -> tuple[int, int]:
        """U05: báo cáo và hóa đơn mặc định tháng trước (previous=True); việc hằng ngày mặc định tháng này."""
        today = date.today()
        default = previous_month(today.month, today.year) if previous else (today.month, today.year)
        return self.io.ask_month(prompt, default=default)

    def confirm(self, prompt: str) -> bool:
        return self.io.ask_yes_no(prompt, default=False)

    @staticmethod
    def parse_dob_for(model: type, raw: Any) -> date:
        """Kiểm tra ngày sinh ngay khi nhập: không ở tương lai, tuổi nằm trong khoảng cho phép."""
        d = parse_date(raw, "Ngày sinh")
        if d > date.today():
            raise ValidationError("Ngày sinh không được ở tương lai.")
        age = calculate_age(d)
        low, high = getattr(model, "MIN_AGE", None), getattr(model, "MAX_AGE", None)
        if (low is not None and age < low) or (high is not None and age > high):
            rule = f"từ {low} đến {high} tuổi" if high is not None else f"từ {low} tuổi trở lên"
            raise InvalidAgeError(f"Tuổi theo ngày sinh là {age}, yêu cầu {rule}.")
        return d

    def ask_dob(self, model: type, default: date | None = None) -> date:
        return self.io.ask("Ngày sinh (dd/mm/yyyy)", lambda raw: self.parse_dob_for(model, raw), default,
                           display_default=format_date(default) if default else None)

    def export_report(self, report: Report) -> None:
        fmt = self.io.ask_choice("Xuất báo cáo ra file?", [("no", "Không xuất"), ("txt", "File văn bản .txt"),
                                                            ("csv", "File .csv (mở bằng Excel)"),
                                                            ("xlsx", "File Excel .xlsx"),
                                                            ("pdf", "File PDF")], default="no")
        if fmt != "no":
            path = report.export(fmt=fmt, directory=self.app.export_dir)
            self.io.success(f"Đã xuất báo cáo: {path}")
