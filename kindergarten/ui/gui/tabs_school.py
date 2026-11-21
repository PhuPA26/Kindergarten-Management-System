"""Các tab: Nhân sự, Lớp học, Thời khóa biểu, Điểm danh."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from ...attendance.records import AttendanceStatus
from ...auth.user import Permission
from ...classroom.classroom import AgeGroup, Classroom
from ...core.person import Employee
from ...exceptions import KindergartenError
from ...hr.employees import Staff, Teacher
from ...reports.reports import AttendanceReport, PayrollReport
from ...utils import (WEEKDAY_NAMES, format_date, format_key_values, format_table, format_vnd, month_label,
                      normalize_text, parse_date, parse_month, previous_month, validate_not_future, weekday_name)
from .base_tab import BaseTab
from .widgets import DataTable, Field, FormDialog

P = Permission


def _month_text(month: int, year: int) -> str:
    return month_label(month, year)


# =============================================================================
class EmployeesTab(BaseTab):
    title = "Nhân sự"
    permission = P.VIEW_EMPLOYEES

    def build(self) -> None:
        bar = self.filter_bar()
        ttk.Label(bar, text="Tìm tên / chức vụ:").pack(side="left")
        self.keyword = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.keyword, width=26)
        entry.pack(side="left", padx=4)
        entry.bind("<KeyRelease>", lambda _e: self.refresh())
        self.m_fg_list = DataTable(self, [("Mã", 60), ("Họ tên", 170), ("Loại", 80), ("Chức vụ", 150), ("SĐT", 100),
                                      ("Vào làm", 90), ("Thâm niên", 75, "e"), ("Lớp CN", 120),
                                      ("Lương tháng này", 120, "e")])
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.view)
        self.master_bar(self.add_employee, self.edit, self.delete, P.MANAGE_EMPLOYEES, extras=[
            ("Hồ sơ", self.view), ("Giờ làm thêm", self.overtime, P.MANAGE_EMPLOYEES),
            ("Bảng lương tháng", self.payroll, P.VIEW_PAYROLL),
            ("Chốt / mở lại lương", self.close_payroll, P.VIEW_PAYROLL)])

    def add_employee(self) -> None:
        kind = self.form("Thêm nhân sự", [Field("kind", "Loại nhân sự", "choice",
                                               [("teacher", "Giáo viên"), ("staff", "Nhân viên")], "teacher")],
                         lambda v: v["kind"], submit_text="Tiếp tục", save=False)
        if kind == "teacher":
            self.add_teacher()
        elif kind == "staff":
            self.add_staff()

    def refresh(self) -> None:
        key = normalize_text(self.keyword.get())
        show_salary = self.can(P.VIEW_PAYROLL)
        employees = [e for e in self.system.employees.all_sorted()
                     if not key or key in normalize_text(f"{e.full_name} {e.position} {getattr(e, 'specialty', '')}")]
        rows = []
        for e in employees:
            position = e.position + (f" {e.specialty}" if isinstance(e, Teacher) and e.specialty else "")
            homeroom = self.class_name(e.homeroom_class_id) if isinstance(e, Teacher) and e.homeroom_class_id else "-"
            rows.append([e.id, e.full_name, e.role_name, position, e.phone, format_date(e.hire_date),
                         f"{e.years_of_service()} năm", homeroom,
                         format_vnd(e.calculate_salary()) if show_salary else "-"])
        self.m_fg_list.set_rows(rows, [e.id for e in employees])

    def _selected(self) -> Employee | None:
        return self.selected(self.m_fg_list, self.system.employees.get, "một nhân sự")

    def _common_fields(self, e: Employee | None) -> list[Field]:
        return [
            Field("full_name", "Họ tên", default=e.full_name if e else None),
            Field("dob", "Ngày sinh (dd/mm/yyyy)", "date", default=e.dob if e else None),
            Field("phone", "Số điện thoại", default=e.phone if e else None),
            Field("gender", "Giới tính", "choice", [("Nam", "Nam"), ("Nữ", "Nữ")], e.gender if e else None),
            Field("address", "Địa chỉ", default=e.address if e else None, required=False),
            Field("hire_date", "Ngày vào làm", "date", default=e.hire_date if e else date.today()),
        ]

    def _teacher_fields(self, t: Teacher | None = None) -> list[Field]:
        return self._common_fields(t) + [
            Field("qualification", "Trình độ", "choice", [(q, q) for q in Teacher.QUALIFICATIONS],
                  t.qualification if t else "Cao đẳng"),
            Field("salary_coefficient", "Hệ số lương", default=t.salary_coefficient if t else 2.10),
            Field("specialty", "Chuyên môn (trống = GV đứng lớp)", default=t.specialty if t else None, required=False),
        ]

    def _staff_fields(self, s: Staff | None = None) -> list[Field]:
        return self._common_fields(s) + [
            Field("position", "Chức vụ", default=s.position if s else "Cấp dưỡng"),
            Field("base_salary", "Lương cơ bản (đ)", "money", default=s.base_salary if s else 5_000_000),
            Field("allowance", "Phụ cấp (đ)", "money", default=s.allowance if s else 0, required=False),
        ]

    def add_teacher(self) -> None:
        self.form("Thêm giáo viên", self._teacher_fields(), lambda v: self.system.employees.add(Teacher(**v)),
                  success=lambda t: f"Đã thêm {t}. Lương dự kiến {format_vnd(t.calculate_salary())}.")

    def add_staff(self) -> None:
        def submit(values: dict[str, Any]) -> Staff:
            values["allowance"] = values["allowance"] or 0
            return self.system.employees.add(Staff(**values))

        self.form("Thêm nhân viên", self._staff_fields(), submit,
                  success=lambda s: f"Đã thêm {s}. Lương dự kiến {format_vnd(s.calculate_salary())}.")

    def edit(self) -> None:
        employee = self._selected()
        if employee is None:
            return
        fields = self._teacher_fields(employee) if isinstance(employee, Teacher) else self._staff_fields(employee)

        def submit(values: dict[str, Any]) -> Employee:
            changes = self.changed(employee, values)   # L05
            if changes:
                self.system.employees.update(employee.id, **changes)
            return employee

        self.form(f"Sửa {employee.full_name}", fields, submit, success="Đã cập nhật hồ sơ nhân sự.")

    def delete(self) -> None:
        employee = self._selected()
        if employee and self.confirm_delete("nhân sự", [
                ("Mã nhân sự", employee.id), ("Họ tên", employee.full_name), ("Chức vụ", employee.position),
                ("Số điện thoại", employee.phone)], note="Tài khoản đăng nhập liên kết (nếu có) sẽ bị khóa."):
            self.guard(self.system.employees.remove, employee.id, success="Đã xóa nhân sự.")

    def view(self) -> None:
        employee = self._selected()
        if employee is not None:
            text = format_key_values(employee.profile(), title=f"Hồ sơ nhân sự: {employee.full_name}")
            text += "\n\nCách tính lương tháng này:\n  " + employee.salary_note().replace(" + ", "\n  + ")
            self.show_text("Hồ sơ nhân sự", text)

    def overtime(self) -> None:
        employee = self._selected()
        if employee is None:
            return
        if not isinstance(employee, Staff):
            messagebox.showwarning("Không áp dụng", "Giờ làm thêm chỉ áp dụng cho nhân viên.", parent=self)
            return
        today = date.today()
        fields = [Field("month", "Tháng (mm/yyyy)", default=_month_text(today.month, today.year)),
                  Field("hours", "Số giờ làm thêm", default=employee.overtime_hours())]

        def submit(values: dict[str, Any]) -> Staff:
            month, year = parse_month(values["month"])
            return self.system.employees.set_overtime(employee.id, month, year, values["hours"])

        self.form(f"Giờ làm thêm - {employee.full_name}", fields, submit, success="Đã lưu giờ làm thêm.")

    def payroll(self) -> None:
        month, year = previous_month(date.today().month, date.today().year)   # U05: mặc định tháng vừa kết thúc
        dialog_fields = [Field("month", "Tháng (mm/yyyy)", default=_month_text(month, year))]

        def submit(values: dict[str, Any]) -> PayrollReport:
            month, year = parse_month(values["month"])
            return PayrollReport(self.system, month, year)

        report = self.form("Bảng lương tháng", dialog_fields, submit, submit_text="Xem", save=False)
        if report is not None:
            self.show_text(report.title, report.to_text(), report)

    def close_payroll(self) -> None:
        """L15: chốt lương lưu bản chụp; kỳ đã chốt không đổi theo hệ số / phụ cấp về sau."""
        month, year = previous_month(date.today().month, date.today().year)
        result = self.form("Chốt / mở lại bảng lương",
                           [Field("month", "Tháng (mm/yyyy)", default=_month_text(month, year))],
                           lambda v: parse_month(v["month"]), submit_text="Tiếp tục", save=False)
        if not result:
            return
        month, year = result
        employees, label = self.system.employees, f"{month:02d}/{year}"
        if employees.is_closed(month, year):
            if self.confirm(f"Bảng lương tháng {label} đã chốt. Mở lại để tính lại?"):
                self.guard(employees.reopen_payroll, month, year, success="Đã mở lại bảng lương.")
                self.system.audit("Mở lại bảng lương", label)
            return
        total = employees.total_payroll(month, year)
        if self.confirm(f"Chốt bảng lương tháng {label}?\nTổng quỹ lương: {format_vnd(total)}.\n"
                        "Sau khi chốt, thay đổi hệ số / phụ cấp không làm đổi bảng lương tháng này."):
            self.guard(employees.close_payroll, month, year, self.system.username, success="Đã chốt bảng lương.")
            self.system.audit("Chốt bảng lương", label)


# =============================================================================
class ClassesTab(BaseTab):
    title = "Lớp học"
    permission = P.MANAGE_CLASSES
    # Lịch năm học (ngày học / nghỉ) và thời khóa biểu của các lớp: mở từ Lớp học, có nút Quay lại.
    # K03: lịch năm học vẫn dùng chung cho điểm danh, tiền ăn, thực đơn, dashboard - chỉ đổi chỗ mở trên menu.
    sub_tabs = ("CalendarTab", "TimetableTab")

    def build(self) -> None:
        self.m_fra_sub = self.sub_function_bar("Chức năng con:", pady=(0, 8))
        self.m_lbl_notice = ttk.Label(self, style="Muted.TLabel")
        self.m_lbl_notice.pack(anchor="w")
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        ttk.Label(left, text="Danh sách lớp", style="Section.TLabel").pack(anchor="w")
        self.m_fg_classes = DataTable(left, [("Mã", 55), ("Tên lớp", 140), ("Khối", 70), ("Độ tuổi", 60, "center"),
                                            ("Phòng", 60), ("GV chủ nhiệm", 160), ("Sĩ số", 60, "center")])
        self.m_fg_classes.pack(fill="both", expand=True)
        self.m_fg_classes.on_select(self.refresh_children)
        self.m_lbl_children = ttk.Label(right, text="Trẻ trong lớp", style="Section.TLabel")
        self.m_lbl_children.pack(anchor="w")
        self.m_fg_children = DataTable(right, [("Mã", 55), ("Họ tên", 160), ("Giới tính", 65, "center"),
                                             ("Tuổi", 100)])
        self.m_fg_children.pack(fill="both", expand=True)
        self.master_bar(self.create_class, self.edit_class, self.delete_class, P.MANAGE_CLASSES, extras=[
            ("Xếp lớp", self.enroll, P.MANAGE_CLASSES), ("Chuyển lớp", self.transfer, P.MANAGE_CLASSES),
            ("Rút khỏi lớp", self.unenroll, P.MANAGE_CLASSES), ("In danh sách lớp", self.print_list)])
        more = self.bar(pady=(6, 0))
        self.button(more, "Đổi GV chủ nhiệm", self.change_teacher, P.MANAGE_CLASSES)
        self.button(more, "Gỡ GV chủ nhiệm", self.remove_teacher, P.MANAGE_CLASSES)
        self.button(more, "Trẻ lệch độ tuổi", self.age_mismatches)
        self.button(more, "Kết thúc năm học", self.end_year, P.MANAGE_CLASSES)

    def refresh(self) -> None:
        classes = self.system.classes_for(self.user)   # L08: giáo viên chỉ thấy lớp mình phụ trách
        mismatches = len(self._mismatches())
        self.m_lbl_notice.configure(text=f"⚠ {mismatches} trẻ đang lệch độ tuổi so với lớp - bấm 'Trẻ lệch độ tuổi'."
                              if mismatches else "")
        rows, tags = [], []
        for c in classes:
            teacher = self.system.classes.homeroom_teacher(c.id)
            rows.append([c.id, c.name, c.age_group.label, f"{c.min_age}-{c.max_age}", c.room or "-",
                         teacher.full_name if teacher else "(chưa phân công)", f"{c.size}/{c.capacity}"])
            tags.append("warn" if c.is_full else None)
        self.m_fg_classes.set_rows(rows, [c.id for c in classes], tags)
        self.refresh_children()

    def refresh_children(self) -> None:
        class_id = self.m_fg_classes.selected_id()
        children = self.system.classes.class_list(class_id) if class_id and self.system.classes.exists(class_id) else []
        self.m_lbl_children.configure(text=f"Trẻ trong lớp ({len(children)})")
        self.m_fg_children.set_rows([[c.id, c.full_name, c.gender, c.age_text] for c in children],
                                  [c.id for c in children])

    def _selected_class(self) -> Classroom | None:
        return self.selected(self.m_fg_classes, self.system.classes.get, "một lớp")

    def _class_fields(self, c: Classroom | None = None) -> list[Field]:
        fields = [Field("name", "Tên lớp", default=c.name if c else None),
                  Field("age_group", "Khối lớp", "choice", [(g, str(g)) for g in AgeGroup], c.age_group if c else None),
                  Field("capacity", "Sĩ số tối đa", default=c.capacity if c else 25),
                  Field("room", "Phòng học", default=c.room if c else None, required=False)]
        if c is None:
            fields.append(Field("teacher_id", "Giáo viên chủ nhiệm", "choice",
                                [(None, "(phân công sau)")] + self.teacher_options(self.system.classes.free_teachers()),
                                None, required=False))
        return fields

    def create_class(self) -> None:
        self.form("Tạo lớp mới", self._class_fields(), lambda v: self.system.classes.create_class(**v),
                  success=lambda c: f"Đã tạo lớp {c}.")

    def edit_class(self) -> None:
        classroom = self._selected_class()
        if classroom is None:
            return

        def submit(values: dict[str, Any]) -> Classroom:
            # L11: độ tuổi của trẻ trong lớp được kiểm tra ở tầng nghiệp vụ (ClassManager._validate_update)
            changes = self.changed(classroom, values)
            if changes:
                self.system.classes.update(classroom.id, **changes)
            return classroom

        self.form(f"Sửa lớp {classroom.name}", self._class_fields(classroom), submit, success="Đã cập nhật lớp.")

    def delete_class(self) -> None:
        classroom = self._selected_class()
        teacher = self.system.classes.homeroom_teacher(classroom.id) if classroom else None
        if classroom and self.confirm_delete("lớp học", [
                ("Mã lớp", classroom.id), ("Tên lớp", classroom.name), ("Phòng", classroom.room or "-"),
                ("GV chủ nhiệm", teacher.full_name if teacher else "-"), ("Sĩ số", classroom.size)],
                note="Thời khóa biểu của lớp cũng bị xóa."):
            self.guard(self.system.classes.remove, classroom.id, success="Đã xóa lớp.")

    def enroll(self) -> None:
        classroom = self._selected_class()
        if classroom is None:
            return
        unassigned = self.system.children.find_unassigned()
        if not unassigned:
            messagebox.showinfo("Thông báo", "Không có trẻ nào đang chờ xếp lớp.", parent=self)
            return
        fields = [Field("child_id", "Trẻ chờ xếp lớp", "choice", self.child_options(unassigned))]
        self.form(f"Xếp trẻ vào lớp {classroom.name}", fields,
                  lambda v: self.system.classes.enroll(v["child_id"], classroom.id), success="Đã xếp lớp.")

    def transfer(self) -> None:
        child = self.selected(self.m_fg_children, self.system.children.get, "một trẻ ở bảng bên phải")
        if child is None:
            return
        targets = [c for c in self.system.classes.all_sorted() if c.id != child.class_id]
        fields = [Field("class_id", "Chuyển sang lớp", "choice", self.class_options(targets))]
        self.form(f"Chuyển lớp cho {child.full_name}", fields,
                  lambda v: self.system.classes.transfer(child.id, v["class_id"]),
                  success=lambda c: f"Đã chuyển {child.full_name} sang lớp {c.name}.")

    def unenroll(self) -> None:
        child = self.selected(self.m_fg_children, self.system.children.get, "một trẻ ở bảng bên phải")
        if child and self.confirm(f"Rút {child.full_name} khỏi lớp {self.class_name(child.class_id)}?"):
            self.guard(self.system.classes.unenroll, child.id, success="Đã rút trẻ khỏi lớp.")

    def change_teacher(self) -> None:
        classroom = self._selected_class()
        if classroom is None:
            return
        fields = [Field("teacher_id", "Giáo viên chủ nhiệm mới", "choice",
                        self.teacher_options(self.system.classes.free_teachers()))]
        self.form(f"Đổi GV chủ nhiệm lớp {classroom.name}", fields,
                  lambda v: self.system.classes.change_homeroom_teacher(classroom.id, v["teacher_id"]),
                  success="Đã đổi giáo viên chủ nhiệm.")

    def remove_teacher(self) -> None:
        """U01: gỡ GVCN khỏi lớp."""
        classroom = self._selected_class()
        if classroom is None:
            return
        teacher = self.system.classes.homeroom_teacher(classroom.id)
        if teacher is None:
            messagebox.showinfo("Thông báo", f"Lớp {classroom.name} chưa có giáo viên chủ nhiệm.", parent=self)
            return
        if self.confirm(f"Gỡ {teacher.full_name} khỏi vị trí chủ nhiệm lớp {classroom.name}?"):
            self.guard(self.system.classes.remove_homeroom_teacher, classroom.id, success="Đã gỡ giáo viên chủ nhiệm.")

    def _mismatches(self) -> list:
        scope = self.scope_class_ids()
        return [(c, k) for c, k in self.system.classes.age_mismatches() if scope is None or k.id in scope]

    def age_mismatches(self) -> None:
        rows = [[c.id, c.full_name, c.age_text, k.name, f"{k.min_age}-{k.max_age}"] for c, k in self._mismatches()]
        self.show_text("Trẻ lệch độ tuổi", format_table(["Mã", "Họ tên", "Tuổi", "Lớp", "Độ tuổi lớp"], rows,
                                                         title="TRẺ LỆCH ĐỘ TUỔI LỚP ĐANG HỌC"))

    def end_year(self) -> None:
        """L14: các lớp lên khối trên, trẻ lớp Lá ra trường (lịch sử vẫn giữ)."""
        if not self.confirm("KẾT THÚC NĂM HỌC?\nMọi lớp sẽ lên khối trên; trẻ lớp Lá chuyển sang 'Ra trường'.\n"
                            "Hệ thống tự sao lưu dữ liệu trước khi thực hiện."):
            return
        try:
            backup = self.system.backup()
            result = self.system.classes.end_school_year()
        except KindergartenError as exc:
            messagebox.showerror("Không thực hiện được", exc.message, parent=self)
            return
        self.system.audit("Kết thúc năm học", "", result)
        self.app.save()
        self.refresh()
        messagebox.showinfo("Đã kết thúc năm học",
                            f"Đã sao lưu ({backup.name}).\nRa trường: {len(result['graduated'])} trẻ.\n"
                            f"Lên lớp: {'; '.join(result['promoted']) or 'không có'}.\n\n"
                            "Nên đổi tên lớp cho đúng khối mới bằng 'Sửa lớp'.", parent=self)

    def print_list(self) -> None:
        classroom = self._selected_class()
        if classroom is not None:
            self.show_text(f"Danh sách lớp {classroom.name}",
                           self.system.classes.class_list_text(classroom.id, self.system.parents.contact_of))


# =============================================================================
class TimetableTab(BaseTab):
    title = "Thời khóa biểu"
    permission = P.VIEW_CLASSES

    def build(self) -> None:
        bar = self.bar()
        ttk.Label(bar, text="Xem theo:").pack(side="left")
        self.m_cbo_mode = ttk.Combobox(bar, state="readonly", width=12, values=["Lớp", "Giáo viên"])
        self.m_cbo_mode.set("Lớp")
        self.m_cbo_mode.pack(side="left", padx=4)
        self.m_cbo_mode.bind("<<ComboboxSelected>>", self._on_mode_change)
        self.m_cbo_target = ttk.Combobox(bar, state="readonly", width=40)
        self.m_cbo_target.pack(side="left", padx=4)
        self.m_cbo_target.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.m_fg_grid = DataTable(self, height=7)
        self.m_fg_grid.pack(fill="both", expand=True)
        ttk.Label(self, text="Chi tiết các tiết", style="Section.TLabel").pack(anchor="w", pady=(8, 0))
        self.m_fg_slots = DataTable(self, [("Mã", 60), ("Thứ", 70), ("Giờ", 100), ("Hoạt động", 200), ("Lớp", 140),
                                           ("Giáo viên", 170)], height=8)
        self.m_fg_slots.pack(fill="both", expand=True)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Thêm tiết học", self.add_slot, P.MANAGE_CLASSES, style="Accent.TButton")
        self.button(actions, "Xóa tiết học", self.remove_slot, P.MANAGE_CLASSES)

    def _target_options(self) -> list[str]:
        if self.m_cbo_mode.get() == "Lớp":
            return [f"{c.id} - {c.name}" for c in self.system.classes_for(self.user)]
        return [f"{t.id} - {t.full_name}" for t in self.system.employees.teachers()]

    def _on_mode_change(self, _event: Any = None) -> None:
        self.m_cbo_target.set("")
        self.refresh()

    def refresh(self) -> None:
        options = self._target_options()
        self.m_cbo_target["values"] = options
        if self.m_cbo_target.get() not in options:
            self.m_cbo_target.set(options[0] if options else "")
        target_id = self.m_cbo_target.get().split(" - ")[0] if self.m_cbo_target.get() else None
        if not target_id:
            self.m_fg_grid.set_columns([("Giờ", 100)])
            self.m_fg_grid.set_rows([])
            self.m_fg_slots.set_rows([])
            return
        tt = self.system.timetable
        try:
            if self.m_cbo_mode.get() == "Lớp":
                headers, rows = tt.weekly_grid(class_id=target_id)
                slots = tt.of_class(target_id)
            else:
                headers, rows = tt.weekly_grid(teacher_id=target_id)
                slots = tt.of_teacher(target_id)
        except KindergartenError:
            headers, rows, slots = ["Giờ"], [], []
        self.m_fg_grid.set_columns([(headers[0], 90)] + [(h, 170) for h in headers[1:]])
        self.m_fg_grid.set_rows(rows)
        teacher_name = lambda tid: (self.system.employees.get(tid).full_name  # noqa: E731
                                    if tid and self.system.employees.exists(tid) else "-")
        self.m_fg_slots.set_rows([[s.id, WEEKDAY_NAMES[s.weekday], s.time_range, s.activity,
                                   self.class_name(s.class_id), teacher_name(s.teacher_id)] for s in slots],
                                 [s.id for s in slots])

    def add_slot(self) -> None:
        current = self.m_cbo_target.get().split(" - ")[0] if self.m_cbo_mode.get() == "Lớp" and self.m_cbo_target.get() else None
        fields = [Field("class_id", "Lớp", "choice", self.class_options(self.system.classes.all_sorted()), current),
                  Field("weekday", "Thứ", "choice", [(i, WEEKDAY_NAMES[i]) for i in range(6)], 0),
                  Field("start", "Giờ bắt đầu (HH:MM)", default="08:00"),
                  Field("end", "Giờ kết thúc (HH:MM)", default="08:30"),
                  Field("activity", "Nội dung hoạt động"),
                  Field("teacher_id", "Giáo viên phụ trách", "choice",
                        [(None, "(GV chủ nhiệm của lớp)")] + self.teacher_options(), None, required=False)]

        def submit(values: dict[str, Any]):
            if not values["teacher_id"]:
                teacher = self.system.classes.homeroom_teacher(values["class_id"])
                values["teacher_id"] = teacher.id if teacher else None
            return self.system.timetable.add_slot(**values)

        self.form("Thêm tiết học", fields, submit, success=lambda s: f"Đã thêm '{s.activity}' {s.time_label}.")

    def remove_slot(self) -> None:
        slot = self.selected(self.m_fg_slots, self.system.timetable.get, "một tiết học ở bảng chi tiết")
        if slot and self.confirm(f"Xóa tiết '{slot.activity}' {slot.time_label}?"):
            self.guard(self.system.timetable.remove, slot.id)


# =============================================================================
class AttendanceTab(BaseTab):
    title = "Điểm danh"
    permission = P.TAKE_ATTENDANCE
    CYCLE = (AttendanceStatus.PRESENT, AttendanceStatus.EXCUSED, AttendanceStatus.UNEXCUSED)

    def build(self) -> None:
        self.statuses: dict[str, tuple[AttendanceStatus, str]] = {}
        self.dirty = False
        self.loaded: tuple[str, date] | None = None
        self._shown: tuple[str, str] = ("", "")
        bar = self.bar()
        ttk.Label(bar, text="Lớp:").pack(side="left")
        self.m_cbo_class = ttk.Combobox(bar, state="readonly", width=30)
        self.m_cbo_class.pack(side="left", padx=(4, 12))
        self.m_cbo_class.bind("<<ComboboxSelected>>", lambda _e: self._switch())
        ttk.Label(bar, text="Ngày:").pack(side="left")
        # U12: chuyển ngày bằng nút, tự tải danh sách khi đổi lớp / ngày (không cần bấm "Tải danh sách")
        ttk.Button(bar, text="◀", width=3, command=lambda: self._shift(-1)).pack(side="left", padx=(4, 0))
        self.day_var = tk.StringVar(value=format_date(self._default_day()))
        entry = ttk.Entry(bar, textvariable=self.day_var, width=12)
        entry.pack(side="left", padx=2)
        entry.bind("<Return>", lambda _e: self._switch())
        entry.bind("<FocusOut>", lambda _e: self._switch())
        ttk.Button(bar, text="▶", width=3, command=lambda: self._shift(1)).pack(side="left")
        ttk.Button(bar, text="Hôm nay", command=self._today).pack(side="left", padx=(4, 12))
        self.m_lbl_info = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_info.pack(side="left", padx=8)
        self.m_fg_list = DataTable(self, [("STT", 45, "center"), ("Mã", 60), ("Họ tên", 190), ("Trạng thái", 130),
                                      ("Ghi chú", 300)], checkable=True)
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.cycle_status)
        for key, status in (("c", AttendanceStatus.PRESENT), ("p", AttendanceStatus.EXCUSED),
                            ("k", AttendanceStatus.UNEXCUSED)):
            self.m_fg_list.tree.bind(f"<KeyPress-{key}>", lambda _e, s=status: self.set_status(s))
        marks = self.bar(pady=(8, 0))
        ttk.Label(marks, text="Trẻ đang chọn (phím C/P/K, nháy đúp để đổi vòng):").pack(side="left", padx=(0, 6))
        self.button(marks, "Có mặt", lambda: self.set_status(AttendanceStatus.PRESENT))
        self.button(marks, "Nghỉ có phép", lambda: self.set_status(AttendanceStatus.EXCUSED))
        self.button(marks, "Nghỉ không phép", lambda: self.set_status(AttendanceStatus.UNEXCUSED))
        self.m_btn_save = self.button(marks, "LƯU ĐIỂM DANH", self.save_attendance, style="Accent.TButton",
                                       side="right")
        more = self.bar(pady=(6, 0))
        self.button(more, "Ghi đơn xin nghỉ", self.leave_request)
        self.button(more, "Danh sách đơn xin nghỉ", self.list_leaves)
        self.button(more, "Hủy đơn nhập nhầm", self.cancel_leave)
        self.button(more, "Thống kê chuyên cần tháng", self.monthly_stats)
        self.button(more, "Sổ điểm danh tháng", self.month_grid)
        self.button(more, "Xác nhận người đón trẻ", self.verify_pickup, style="Accent.TButton")

    # ------------------------------------------------------------------ chọn lớp / ngày
    def _default_day(self) -> date:
        """Hôm nay nếu là ngày học, ngược lại ngày học gần nhất trước đó (tối đa lùi 14 ngày)."""
        day = date.today()
        for _ in range(14):
            if self.system.calendar.is_school_day(day):
                return day
            day -= timedelta(days=1)
        return date.today()

    def _today(self) -> None:
        self.day_var.set(format_date(date.today()))
        self._switch()

    def _shift(self, step: int) -> None:
        """◀ ▶: nhảy tới ngày học kế trước / kế sau (bỏ qua cuối tuần, ngày lễ)."""
        try:
            day = parse_date(self.day_var.get(), "Ngày")
        except KindergartenError:
            day = date.today()
        for _ in range(30):
            day += timedelta(days=step)
            if self.system.calendar.is_school_day(day):
                break
        if day > date.today():
            return
        self.day_var.set(format_date(day))
        self._switch()

    def has_unsaved(self) -> bool:
        return self.dirty

    def unsaved_label(self) -> str:
        if self.loaded is None:
            return "Điểm danh chưa lưu"
        return f"Điểm danh lớp {self.class_name(self.loaded[0])} ngày {format_date(self.loaded[1])}"

    def save_unsaved(self) -> bool:
        return self.save_attendance(show_message=False)

    def discard_unsaved(self) -> None:
        self.dirty = False

    def confirm_discard(self) -> bool:
        """U15: còn điểm danh chưa lưu -> hỏi Lưu / Bỏ / Hủy. Trả về False nếu người dùng chọn Hủy."""
        if not self.dirty or self.loaded is None:
            return True
        answer = messagebox.askyesnocancel(
            "Điểm danh chưa lưu",
            f"Điểm danh lớp {self.class_name(self.loaded[0])} ngày {format_date(self.loaded[1])} chưa được lưu.\n"
            "Lưu trước khi chuyển?\n(Có = lưu, Không = bỏ thay đổi, Hủy = ở lại)", parent=self)
        if answer is None:
            return False
        if answer:
            return self.save_attendance(show_message=False)
        self.dirty = False
        return True

    def _switch(self) -> None:
        current = (self.m_cbo_class.get(), self.day_var.get().strip())
        if current == self._shown:
            return
        if not self.confirm_discard():
            self.m_cbo_class.set(self._shown[0])   # quay lại lựa chọn cũ
            self.day_var.set(self._shown[1])
            return
        self.load_list(quiet=False)

    def refresh(self) -> None:
        options = [f"{c.id} - {c.name}" for c in self.system.classes_for(self.user)]
        self.m_cbo_class["values"] = options
        if self.m_cbo_class.get() not in options:
            self.m_cbo_class.set(options[0] if options else "")
        if not self.dirty:
            self.load_list(quiet=True)

    def _clear(self, message: str) -> None:
        self.loaded = None
        self.statuses = {}
        self.dirty = False
        self.m_fg_list.set_rows([])
        self.m_lbl_info.configure(text=message)
        self.m_btn_save.state(["disabled"])

    def load_list(self, quiet: bool = False) -> None:
        self._shown = (self.m_cbo_class.get(), self.day_var.get().strip())
        class_id = self.m_cbo_class.get().split(" - ")[0] if self.m_cbo_class.get() else None
        if not class_id:
            self._clear("Bạn chưa được phân công lớp nào.")
            return
        try:
            day = validate_not_future(self.day_var.get(), "Ngày điểm danh")
        except KindergartenError as exc:
            self._clear(exc.message)
            if not quiet:
                messagebox.showerror("Ngày không hợp lệ", exc.message, parent=self)
            return
        if not self.system.calendar.is_school_day(day):   # L04: dùng chung một định nghĩa ngày học
            self._clear(self.system.calendar.reason_not_school_day(day) + " Không điểm danh.")
            return
        children = [c for c in self.system.classes.class_list(class_id) if c.enrollment_date <= day]
        self.statuses = {c.id: self.system.attendance.default_status(c.id, day) for c in children}
        self.loaded = (class_id, day)
        self.dirty = False
        if self.can(P.TAKE_ATTENDANCE):
            self.m_btn_save.state(["!disabled"])
        taken = self.system.attendance.is_taken(class_id, day)
        self.m_lbl_info.configure(text=f"{weekday_name(day)} {format_date(day)} - "
                                 + ("ĐÃ điểm danh (đang xem/sửa)" if taken else "chưa điểm danh"))
        self._render()

    def _render(self) -> None:
        if self.loaded is None:
            return
        children = [c for c in self.system.classes.class_list(self.loaded[0]) if c.id in self.statuses]
        rows, tags = [], []
        present = 0
        for index, child in enumerate(children, 1):
            status, note = self.statuses[child.id]
            present += status is AttendanceStatus.PRESENT
            rows.append([index, child.id, child.full_name, status.value, note])
            tags.append({AttendanceStatus.UNEXCUSED: "warn", AttendanceStatus.EXCUSED: "muted"}.get(status))
        self.m_fg_list.set_rows(rows, [c.id for c in children], tags)
        base = self.m_lbl_info.cget("text").split("  |  ")[0]
        self.m_lbl_info.configure(text=f"{base}  |  có mặt {present}/{len(children)}"
                                       + ("  •  CHƯA LƯU" if self.dirty else ""))

    def set_status(self, status: AttendanceStatus, ask_note: bool = True) -> None:
        ids = [i for i in self.m_fg_list.checked_ids() if i in self.statuses]
        if not ids:
            messagebox.showwarning("Chưa chọn", "Hãy tích ô ☐ đầu dòng một hoặc nhiều trẻ.", parent=self)
            return
        note = ""
        if status is not AttendanceStatus.PRESENT and ask_note:
            note = simpledialog.askstring("Lý do", "Lý do / ghi chú (có thể để trống):", parent=self) or ""
        for child_id in ids:
            self.statuses[child_id] = (status, note)
        self.dirty = True
        self.m_fg_list.set_checked([])
        self._render()

    def cycle_status(self) -> None:
        """U12: nháy đúp đổi vòng Có mặt -> Có phép -> Không phép."""
        child_id = self.m_fg_list.selected_id()
        if child_id not in self.statuses:
            return
        status, note = self.statuses[child_id]
        following = self.CYCLE[(self.CYCLE.index(status) + 1) % len(self.CYCLE)]
        self.statuses[child_id] = (following, "" if following is AttendanceStatus.PRESENT else note)
        self.dirty = True
        self._render()

    def save_attendance(self, show_message: bool = True) -> bool:
        if self.loaded is None:
            messagebox.showwarning("Chưa có danh sách", "Hãy chọn lớp và một ngày học.", parent=self)
            return False
        class_id, day = self.loaded
        try:
            records = self.system.attendance.take_class_attendance(class_id, day, dict(self.statuses))
        except KindergartenError as exc:
            messagebox.showerror("Không lưu được", exc.message, parent=self)
            return False
        self.dirty = False
        self.app.save()
        self.load_list(quiet=True)
        if show_message:
            present = sum(1 for r in records if r.is_present)
            messagebox.showinfo("Đã lưu", f"Đã lưu điểm danh {format_date(day)}: có mặt {present}/{len(records)}.",
                                parent=self)
        return True

    # ------------------------------------------------------------------ đơn xin nghỉ
    def leave_request(self) -> None:
        fields = [Field("child_id", "Trẻ", "choice", self.child_options(), self.m_fg_list.selected_id()),
                  Field("from_date", "Nghỉ từ ngày", "date", default=date.today()),
                  Field("to_date", "Đến ngày", "date", default=date.today()),
                  Field("reason", "Lý do"), Field("submitted_by", "Người gửi đơn", required=False)]
        attendance = self.system.attendance
        self.form("Ghi đơn xin nghỉ", fields, lambda v: attendance.record_leave_request(**v),
                  success=lambda r: f"Đã ghi đơn {r.id} ({r.period_text}, {attendance.leave_school_days(r)} ngày học).")

    def _visible_leaves(self) -> list:
        allowed = {c.id for c in self.system.children_for(self.user)}
        return [r for r in self.system.attendance.leave_requests_of() if r.child_id in allowed]

    def list_leaves(self) -> None:
        rows = []
        for r in self._visible_leaves():
            child = self.system.children.get_or_none(r.child_id)
            rows.append([r.id, child.full_name if child else r.child_id,
                         self.class_name(child.class_id) if child else "-", r.period_text,
                         self.system.attendance.leave_school_days(r), r.reason, r.submitted_by or "-"])
        self.show_text("Đơn xin nghỉ", format_table(["Mã đơn", "Trẻ", "Lớp", "Thời gian", "Ngày học", "Lý do",
                                                     "Người gửi"], rows, title="ĐƠN XIN NGHỈ (mới nhất trước)"))

    def cancel_leave(self) -> None:
        """L26: hủy đơn nhập nhầm; các ngày đơn đã chuyển 'có phép' được trả về 'không phép'."""
        leaves = self._visible_leaves()
        if not leaves:
            messagebox.showinfo("Không có đơn", "Không có đơn xin nghỉ nào.", parent=self)
            return
        names = {c.id: c.full_name for c in self.system.children_for(self.user)}
        options = [(r.id, f"{r.id} - {names.get(r.child_id, r.child_id)}: {r.period_text} ({r.reason})")
                   for r in leaves]

        def submit(values: dict[str, Any]):
            request = self.system.attendance.cancel_leave_request(values["request_id"])
            self.system.audit("Hủy đơn xin nghỉ", request.id)
            return request

        self.form("Hủy đơn xin nghỉ", [Field("request_id", "Đơn cần hủy", "choice", options, width=60)], submit,
                  success=lambda r: f"Đã hủy đơn {r.id}.", submit_text="Hủy đơn")
        if not self.dirty:
            self.load_list(quiet=True)

    # ------------------------------------------------------------------ thống kê
    def _ask_month(self, title: str):
        today = date.today()
        options = self.class_options()
        default = options[0][0] if len(options) == 1 else None
        extra = [] if len(options) == 1 else [(None, "(tất cả lớp được phép xem)")]
        fields = [Field("month", "Tháng (mm/yyyy)", default=month_label(today.month, today.year)),
                  Field("class_id", "Lớp", "choice", extra + options, default, required=False)]
        return self.form(title, fields, lambda v: (*parse_month(v["month"]), v.get("class_id")), submit_text="Xem",
                         save=False)

    def monthly_stats(self) -> None:
        result = self._ask_month("Thống kê chuyên cần")
        if result:
            month, year, class_id = result
            report = AttendanceReport(self.system, month, year, class_id, class_ids=self.scope_class_ids())
            self.show_text(report.title, report.to_text(), report)

    def month_grid(self) -> None:
        options = self.class_options()
        today = date.today()
        current = self.loaded[0] if self.loaded else (options[0][0] if options else None)
        fields = [Field("class_id", "Lớp", "choice", options, current),
                  Field("month", "Tháng (mm/yyyy)", default=month_label(today.month, today.year))]
        result = self.form("Sổ điểm danh tháng", fields,
                           lambda v: (v["class_id"], *parse_month(v["month"])), submit_text="Xem", save=False)
        if result:
            class_id, month, year = result
            headers, rows = self.system.attendance.monthly_grid(class_id, month, year)
            self.show_text("Sổ điểm danh", format_table(
                headers, rows, title=f"Sổ điểm danh lớp {self.class_name(class_id)} - tháng "
                                     f"{month_label(month, year)} (C = có mặt, P = có phép, K = không phép)",
                max_width=24))

    # ------------------------------------------------------------------ đón trẻ
    def verify_pickup(self) -> None:
        """L06/U04: chọn người đón từ danh sách đăng ký thay vì gõ tự do; chỉ giao khi trẻ đã điểm danh có mặt."""
        selected = self.m_fg_list.selected_id()
        if selected is None:
            result = self.form("Xác nhận người đón trẻ", [Field("child_id", "Trẻ", "choice", self.child_options())],
                               lambda v: v["child_id"], submit_text="Tiếp tục", save=False)
            if not result:
                return
            selected = result
        child = self.system.children.get(selected)
        people = self.system.authorized_pickups(child.id)
        options = [(p[0], f"{p[0]} ({p[1]}) - SĐT {p[2]}") for p in people]
        options.append(("__other__", "Người KHÔNG có trong danh sách"))
        fields = [Field("person", "Người đến đón", "choice", options, width=48),
                  Field("other_name", "Họ tên (nếu không có trong danh sách)", required=False)]

        def submit(values: dict[str, Any]) -> str:
            name = values["person"]
            if name == "__other__":
                name = values["other_name"]
                if not name:
                    raise KindergartenError("Hãy nhập họ tên người đến đón để ghi nhật ký.")
            return self.system.verify_pickup(child.id, name)

        result = self.form(f"Người đón {child.full_name}", fields, submit, submit_text="Kiểm tra")
        if result:
            messagebox.showinfo("Hợp lệ", f"Được phép giao {child.full_name} cho: {result}", parent=self)
