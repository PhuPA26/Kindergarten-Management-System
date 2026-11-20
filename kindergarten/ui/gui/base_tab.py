"""Lớp cơ sở cho các tab của giao diện Tkinter."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any, Callable, Iterable

from ...auth.user import Permission
from ...classroom.classroom import Classroom
from ...exceptions import KindergartenError
from ...hr.employees import Teacher
from ...people.child import Child
from ...people.parent import Parent
from ...reports.reports import Report
from ...utils import parse_date, parse_float, parse_money
from .report_view import ReportDrawer
from .widgets import DataTable, DeleteDialog, Field, FormDialog, TextDialog, px

if TYPE_CHECKING:
    from .app import KindergartenApp


class BaseTab(ttk.Frame):
    title = "Tab"
    permission: Permission | None = None
    # Chức năng con (tên lớp tab): nếu phân hệ có màn hình này thì các chức năng con không có mục riêng trên menu
    # trái, chỉ mở từ màn hình này và có nút "Quay lại".
    sub_tabs: tuple[str, ...] = ()

    def __init__(self, master: tk.Misc, app: "KindergartenApp") -> None:
        super().__init__(master, padding=(px(18), px(14)))
        self.app = app
        self.system = app.system
        self.build()

    # ------------------------------------------------------------------ tiện ích
    @property
    def user(self):
        return self.system.auth.current_user

    def can(self, permission: Permission | None) -> bool:
        return permission is None or self.system.auth.has_permission(permission)

    def build(self) -> None:
        raise NotImplementedError

    def refresh(self) -> None:
        """Nạp lại dữ liệu hiển thị (gọi khi mở tab hoặc sau mỗi thao tác)."""

    def bar(self, master: tk.Misc | None = None, pady: tuple[int, int] = (0, 6)) -> ttk.Frame:
        frame = ttk.Frame(master or self)
        frame.pack(fill="x", pady=pady)
        return frame

    def sub_function_bar(self, label: str, master: tk.Misc | None = None,
                         pady: tuple[int, int] = (2, 8)) -> ttk.Frame:
        """Hàng nút mở các chức năng con (sub_tabs). Nút được tạo khi màn hình mở lần đầu (fill_sub_functions) -
        lúc đó mới biết phân hệ đang đăng nhập có những màn hình nào."""
        self._sub_bar = self.bar(master, pady)
        self._sub_label = label
        return self._sub_bar

    def fill_sub_functions(self, tabs: dict[str, "BaseTab"]) -> None:
        bar = getattr(self, "_sub_bar", None)
        if bar is None or bar.winfo_children():
            return
        present = [name for name in self.sub_tabs if name in tabs]
        if not present:
            bar.pack_forget()
            return
        ttk.Label(bar, text=self._sub_label, style="Section.TLabel").pack(side="left", padx=(0, px(8)))
        for name in present:
            ttk.Button(bar, text=tabs[name].title, cursor="hand2",
                       command=lambda n=name: self.app.show_tab(n)).pack(side="left", padx=(0, px(6)))

    def button(self, bar: tk.Misc, text: str, command: Callable[[], Any], permission: Permission | None = None,
               side: str = "left", style: str = "TButton") -> ttk.Button:
        btn = ttk.Button(bar, text=text, command=command, style=style)
        if not self.can(permission):
            btn.state(["disabled"])
        btn.pack(side=side, padx=(0, 6))
        return btn

    # ------------------------------------------------------------------ form Master (Hướng dẫn XD HTTTQL)
    def filter_bar(self, master: tk.Misc | None = None) -> ttk.Frame:
        """Khung "Bộ lọc" phía trên lưới dữ liệu của form danh mục."""
        box = ttk.LabelFrame(master or self, text="Bộ lọc", padding=(px(12), px(6), px(12), px(8)))
        box.pack(fill="x", pady=(0, px(10)))
        inner = ttk.Frame(box)
        inner.pack(fill="x")
        return inner

    def master_bar(self, add: Callable[[], Any] | None = None, edit: Callable[[], Any] | None = None,
                   delete: Callable[[], Any] | None = None, permission: Permission | None = None,
                   extras: Iterable[tuple] = (), master: tk.Misc | None = None, exit_button: bool = True
                   ) -> ttk.Frame:
        """Hàng nút của form danh mục theo mẫu Master: [Thoát] bên trái ... [Thêm] [Sửa] [Xóa] bên phải.
        extras: (chữ, lệnh[, quyền]) - các chức năng riêng của danh mục, đặt sau nút Thoát."""
        bar = self.bar(master, pady=(px(10), 0))
        if exit_button:
            ttk.Button(bar, text="⟵  Thoát", command=self.exit_form).pack(side="left", padx=(0, px(14)))
        for spec in extras:
            self.button(bar, spec[0], spec[1], spec[2] if len(spec) > 2 else None)
        for text, command, style in (("Xóa", delete, "TButton"), ("Sửa", edit, "TButton"),
                                     ("Thêm", add, "Accent.TButton")):
            if command is not None:
                btn = self.button(bar, text, command, permission, side="right", style=style)
                btn.configure(width=8)
        return bar

    def exit_form(self) -> None:
        """Nút Thoát của form: về màn hình chính của phân hệ."""
        main = getattr(self.app, "main", None)
        if main is not None:
            main.go_home()

    def confirm_delete(self, what: str, details: list[tuple[str, Any]], note: str = "") -> bool:
        """Form Detail khi xóa: thông tin đối tượng + cảnh báo đỏ + Thực hiện / Hủy bỏ."""
        dialog = DeleteDialog(self, f"Xóa {what}", details, note)
        self.wait_window(dialog)
        return dialog.confirmed

    def guard(self, func: Callable[..., Any], *args: Any, success: Any = None, **kwargs: Any) -> Any:
        """Chạy thao tác nghiệp vụ: lỗi -> báo lỗi; thành công -> lưu dữ liệu, làm mới, báo thành công."""
        try:
            result = func(*args, **kwargs)
        except KindergartenError as exc:
            messagebox.showerror("Không thực hiện được", exc.message, parent=self)
            return None
        self.app.save()
        self.refresh()
        if success:
            messagebox.showinfo("Thành công", success(result) if callable(success) else success, parent=self)
        return result

    def form(self, title: str, fields: list[Field], on_submit: Callable[[dict[str, Any]], Any],
             success: Any = None, submit_text: str = "Thực hiện", save: bool = True) -> Any:
        """save=False cho hộp thoại chỉ để xem/hỏi tham số (P01: không ghi đĩa, không làm mới)."""
        dialog = FormDialog(self, title, fields, on_submit, submit_text)
        self.wait_window(dialog)
        if not dialog.submitted:
            return None
        if save:
            self.app.save()
            self.refresh()
        if success:
            text = success(dialog.result) if callable(success) else success
            messagebox.showinfo("Thành công", text, parent=self)
        return dialog.result

    @staticmethod
    def changed(obj: Any, values: dict[str, Any]) -> dict[str, Any]:
        """L05: chỉ lấy trường thật sự thay đổi; chuẩn hóa ngày/số/tiền trước khi so sánh
        (tránh việc gửi lại ngày sinh dạng chuỗi làm hồ sơ trẻ quá tuổi không sửa được)."""
        out = {}
        for key, value in values.items():
            current = getattr(obj, key)
            candidate = value
            try:
                if isinstance(current, date) and isinstance(value, str) and value:
                    candidate = parse_date(value)
                elif isinstance(current, bool) or current is None:
                    candidate = value
                elif isinstance(current, int) and isinstance(value, str) and value:
                    candidate = parse_money(value)
                elif isinstance(current, float) and isinstance(value, str) and value:
                    candidate = parse_float(value)
            except KindergartenError:
                candidate = value   # để setter báo lỗi đúng chỗ
            if candidate != current:
                out[key] = value
        return out

    def show_text(self, title: str, text: str, report: Report | None = None) -> None:
        if report is not None:   # báo cáo: mở khung dạng văn bản tự nhiên thay cho bảng ký tự
            self.open_report(title, report=report)
            return
        # hồ sơ, hóa đơn, danh sách...: cùng khung và cùng kiểu chữ bình thường như phần báo cáo
        host = self.app.main.right if getattr(self.app, "main", None) is not None else None
        if host is None:
            TextDialog(self, title, text, None, self.app.export_dir)
            return
        drawer = ReportDrawer.open(host, title, export_dir=self.app.export_dir)
        drawer.view.render_plain(text)

    def open_report(self, title: str, report: Report | None = None, submission: Any = None,
                    submissions: list[Any] | None = None, conclusion: str = "", notice: str = "",
                    conclusion_title: str = "Kết luận / chỉ đạo của Ban giám hiệu") -> ReportDrawer:
        """Hiện toàn bộ báo cáo phủ kín màn hình (trừ menu trái), đóng bằng nút ✕ / Esc."""
        host = self.app.main.right if getattr(self.app, "main", None) is not None else self
        export = report if report is not None else (submission.report(self.system) if submission else None)
        drawer = ReportDrawer.open(host, title, report=export, export_dir=self.app.export_dir, notice=notice)
        if submission is not None:
            drawer.view.render_submission(submission, self.system)
        elif submissions is not None:
            drawer.view.render_submissions(submissions, self.system)
        elif report is not None:
            drawer.view.render_report(report, conclusion, conclusion_title)
        return drawer

    def confirm(self, message: str) -> bool:
        return messagebox.askyesno("Xác nhận", message, parent=self)

    def selected(self, table: DataTable, getter: Callable[[str], Any], what: str = "một dòng") -> Any:
        item_id = table.selected_id()
        if not item_id:
            messagebox.showwarning("Chưa chọn", f"Hãy chọn {what} trong bảng trước.", parent=self)
            return None
        return getter(item_id)

    # ------------------------------------------------------------------ danh sách lựa chọn
    def class_name(self, class_id: str | None) -> str:
        return self.system.classes.class_name(class_id)

    def child_options(self, children: Iterable[Child] | None = None) -> list[tuple[str, str]]:
        items = self.system.children_for(self.user) if children is None else children
        return [(c.id, f"{c.id} - {c.full_name} ({self.class_name(c.class_id)})") for c in items]

    def scope_class_ids(self) -> set[str] | None:
        """Phạm vi lớp của người dùng (None = toàn trường) - L08/L09."""
        return self.system.class_ids_for(self.user)

    def visible_parents(self) -> list[Parent]:
        """L09: giáo viên chỉ thấy phụ huynh của trẻ lớp mình."""
        if self.scope_class_ids() is None:
            return self.system.parents.all_sorted()
        return self.system.parents.parents_of_children({c.id for c in self.system.children_for(self.user)})

    def parent_options(self, parents: Iterable[Parent] | None = None) -> list[tuple[str, str]]:
        items = self.visible_parents() if parents is None else parents
        return [(p.id, f"{p.id} - {p.full_name} ({p.relationship}, {p.phone})") for p in items]

    def class_options(self, classes: Iterable[Classroom] | None = None) -> list[tuple[str, str]]:
        items = self.system.classes_for(self.user) if classes is None else classes
        return [(c.id, f"{c.id} - {c.display_name} ({c.size}/{c.capacity})") for c in items]

    def teacher_options(self, teachers: Iterable[Teacher] | None = None) -> list[tuple[str, str]]:
        items = self.system.employees.teachers() if teachers is None else teachers
        return [(t.id, f"{t.id} - {t.full_name}" + (f" ({t.specialty})" if t.specialty else "")) for t in items]
