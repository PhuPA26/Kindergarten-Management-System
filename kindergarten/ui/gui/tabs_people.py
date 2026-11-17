"""Các tab: Tổng quan, Trẻ, Phụ huynh, Sức khỏe."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from ...auth.user import Permission
from ...health.records import AllergySeverity, NutritionStatus
from ...people.child import Child, PickupPerson
from ...people.parent import Parent
from ...utils import (format_date, format_key_values, format_number, format_percent, format_table, format_vnd,
                      normalize_text, parse_float)
from ...exceptions import KindergartenError
from .base_tab import BaseTab
from .report_view import ReportView
from .widgets import COLORS, DataTable, Field, px, stat_card

P = Permission


# =============================================================================
class DashboardTab(BaseTab):
    title = "Tổng quan"
    permission = P.VIEW_DASHBOARD

    def build(self) -> None:
        bar = self.bar()
        ttk.Label(bar, text="Tổng quan hoạt động của trường", style="Title.TLabel").pack(side="left")
        self.button(bar, "Làm mới", self.refresh, side="right")
        self.cards = ttk.Frame(self)
        self.cards.pack(fill="x", pady=(0, 10))
        self.text = ReportView(self, height=18)
        self.text.configure(highlightthickness=1, highlightbackground=COLORS["border"])
        self.text.pack(fill="both", expand=True)

    def refresh(self) -> None:
        finance = self.can(P.VIEW_FINANCE_REPORTS)
        dashboard = self.system.dashboard(user=self.user)   # L09: giáo viên chỉ thấy số liệu lớp mình
        st = dashboard.collect(finance)                       # P05: tính một lần, dùng cho cả thẻ và văn bản
        for widget in self.cards.winfo_children():
            widget.destroy()
        today_card = (f"{st['present_today']}/{st['enrolled']}", "Có mặt hôm nay") if st["is_school_day"] \
            else ("Nghỉ", "Hôm nay không phải ngày học")
        cards: list[tuple] = [
            (str(st["total_children"]), f"Trẻ ({st['enrolled']} đã xếp lớp)"),
            (str(st["classes"]), f"Lớp học (chỉ tiêu {st['capacity']})"),
            (f"{st['teachers']} / {st['staff']}", "Giáo viên / nhân viên"),
            today_card,
            (format_percent(st["attendance_rate_month"]), f"Chuyên cần tháng {st['month_label']}"),
        ]
        if finance:
            cards += [(format_vnd(st["revenue_month"]), "Thực thu trong tháng", COLORS["ok"]),
                      (format_vnd(st["total_debt"]), f"Công nợ ({st['debtor_count']} hộ)", COLORS["warn"])]
        per_row = 4
        for index, spec in enumerate(cards):
            row, column = divmod(index, per_row)
            stat_card(self.cards, *spec).grid(row=row, column=column, padx=(0, 8), pady=(0, 8), sticky="nsew")
        for column in range(per_row):
            self.cards.columnconfigure(column, weight=1, uniform="cards")
        self.text.render_plain(dashboard.render_text(finance, stats=st), top="h2")


# =============================================================================
class PickupDialog(tk.Toplevel):
    """Quản lý danh sách người đón hộ của một trẻ."""

    def __init__(self, tab: BaseTab, child: Child) -> None:
        super().__init__(tab)
        self.tab, self.child = tab, child
        self.title(f"Người đón hộ - {child.full_name}")
        self.transient(tab.winfo_toplevel())
        self.geometry(f"{px(640)}x{px(320)}")
        self.table = DataTable(self, [("Họ tên", 170), ("Quan hệ", 110), ("SĐT", 110), ("CCCD", 120)], height=8)
        self.table.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self, padding=(8, 0, 8, 8))
        bar.pack(fill="x")
        ttk.Button(bar, text="Thêm", command=self.add).pack(side="left")
        ttk.Button(bar, text="Xóa", command=self.remove).pack(side="left", padx=6)
        ttk.Button(bar, text="Đóng", command=self.destroy).pack(side="right")
        self.reload()
        self.grab_set()

    def reload(self) -> None:
        persons = self.child.pickup_persons
        self.table.set_rows([[p.full_name, p.relationship, p.phone, p.id_card or "-"] for p in persons],
                            [p.full_name for p in persons])

    def add(self) -> None:
        fields = [Field("full_name", "Họ tên"), Field("relationship", "Quan hệ với trẻ (VD: Bà ngoại)"),
                  Field("phone", "Số điện thoại"), Field("id_card", "Số CCCD", required=False)]
        self.tab.form("Thêm người đón hộ", fields, lambda v: self.child.add_pickup_person(PickupPerson(**v)))
        self.reload()

    def remove(self) -> None:
        name = self.table.selected_id()
        if name and messagebox.askyesno("Xác nhận", f"Xóa {name} khỏi danh sách người đón hộ?", parent=self):
            self.tab.guard(self.child.remove_pickup_person, name)
            self.reload()


class ChildrenTab(BaseTab):
    title = "Trẻ"
    permission = P.VIEW_CHILDREN

    def build(self) -> None:
        bar = self.filter_bar()
        ttk.Label(bar, text="Tìm:").pack(side="left")
        self.keyword = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.keyword, width=24)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<KeyRelease>", self._on_key)
        self._pending: str | None = None
        ttk.Label(bar, text="Lớp:").pack(side="left")
        self.class_filter = ttk.Combobox(bar, state="readonly", width=26)
        self.class_filter.pack(side="left", padx=(4, 12))
        self.class_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(bar, text="Tuổi:").pack(side="left")
        self.age_filter = ttk.Combobox(bar, state="readonly", width=8, values=["Tất cả", "1", "2", "3", "4", "5", "6"])
        self.age_filter.set("Tất cả")
        self.age_filter.pack(side="left", padx=(4, 12))
        self.age_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.table = DataTable(self, [("Mã", 60), ("Họ tên", 170), ("Giới tính", 70, "center"), ("Ngày sinh", 90),
                                      ("Tuổi", 110), ("Lớp", 130), ("Phụ huynh", 260), ("Dị ứng", 120)])
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.view_detail)
        self.count = ttk.Label(bar, style="Muted.TLabel")
        self.count.pack(side="right")
        self.master_bar(self.add_child, self.edit_child, self.delete_child, P.MANAGE_CHILDREN, extras=[
            ("Hồ sơ chi tiết", self.view_detail), ("Người đón hộ", self.manage_pickups, P.MANAGE_CHILDREN),
            ("Liên kết phụ huynh", self.link_parent, P.MANAGE_CHILDREN),
            ("Thôi học / Học lại", self.withdraw_child, P.MANAGE_CHILDREN)])

    def _on_key(self, _event: Any) -> None:
        """P08: trì hoãn tìm kiếm 250 ms sau phím gõ cuối thay vì vẽ lại bảng ở mỗi phím."""
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(250, self.refresh)

    def refresh(self) -> None:
        self._pending = None
        restricted = self.scope_class_ids() is not None
        options = ["Tất cả"] + ([] if restricted else ["Chưa xếp lớp", "Đã nghỉ / ra trường"]) \
            + [f"{c.id} - {c.name}" for c in self.system.classes_for(self.user)]
        current = self.class_filter.get() or "Tất cả"
        self.class_filter["values"] = options
        self.class_filter.set(current if current in options else "Tất cả")
        key, selection, age = normalize_text(self.keyword.get()), self.class_filter.get(), self.age_filter.get()
        if selection == "Đã nghỉ / ra trường":
            children = self.system.children.find_inactive()
        else:
            children = self.system.children_for(self.user)
        show_health = self.can(P.MANAGE_HEALTH)   # L09: kế toán không xem thông tin sức khỏe

        def keep(c: Child) -> bool:
            if key and key not in f"{c.search_text} {c.id.lower()}":   # P08: khóa tìm kiếm tính sẵn
                return False
            if selection == "Chưa xếp lớp" and c.class_id:
                return False
            if selection not in ("Tất cả", "Chưa xếp lớp", "Đã nghỉ / ra trường") \
                    and c.class_id != selection.split(" - ")[0]:
                return False
            return age == "Tất cả" or c.age == int(age)

        shown = [c for c in children if keep(c)]
        rows, tags = [], []
        for c in shown:
            parents = self.system.parents.parents_of(c.id)
            allergies = self.system.health.allergies_of(c.id) if show_health else []
            class_text = self.class_name(c.class_id) if c.is_active else c.status
            rows.append([c.id, c.full_name, c.gender, format_date(c.dob), c.age_text, class_text,
                         "; ".join(f"{p.relationship} {p.full_name}" for p in parents) or "-",
                         ("⚠ " + ", ".join(a.allergen for a in allergies)) if allergies else ""])
            tags.append("warn" if allergies else (None if c.is_active else "muted"))
        self.table.set_rows(rows, [c.id for c in shown], tags)
        self.count.configure(text=f"{len(shown)}/{len(children)} trẻ")

    def _selected_child(self) -> Child | None:
        return self.selected(self.table, self.system.children.get, "một trẻ")

    def _fields(self, child: Child | None = None) -> list[Field]:
        services = list(self.system.settings.extra_services)
        fields = [
            Field("full_name", "Họ tên", default=child.full_name if child else None),
            Field("dob", "Ngày sinh (dd/mm/yyyy)", "date", default=child.dob if child else None),
            Field("gender", "Giới tính", "choice", [("Nam", "Nam"), ("Nữ", "Nữ")], child.gender if child else None),
            Field("nickname", "Tên ở nhà", default=child.nickname if child else None, required=False),
            Field("address", "Địa chỉ", default=child.address if child else None, required=False),
            Field("is_poor_household", "Diện hộ nghèo", "bool", default=child.is_poor_household if child else False),
            Field("extra_services", "Dịch vụ đăng ký", "multi", [(s, s) for s in services],
                  default=child.extra_services if child else [], required=False),
            Field("notes", "Ghi chú", "textarea", default=child.notes if child else None, required=False),
        ]
        if child is None:
            fields += [
                Field("class_id", "Xếp vào lớp", "choice",
                      [(None, "(chờ xếp lớp)")] + self.class_options(self.system.classes.all_sorted()), None,
                      required=False),
                # U02: chọn được nhiều phụ huynh như bản console
                Field("parent_ids", "Phụ huynh (chọn một hoặc nhiều)", "multi", self.parent_options(), [],
                      required=False),
            ]
        return fields

    def add_child(self) -> None:
        def submit(values: dict[str, Any]) -> Child:
            parent_ids, class_id = values.pop("parent_ids"), values.pop("class_id")
            return self.system.enroll_new_child(parent_ids=parent_ids, class_id=class_id, **values)

        self.form("Tiếp nhận trẻ mới", self._fields(), submit,
                  success=lambda c: f"Đã tiếp nhận {c} - lớp: {self.class_name(c.class_id)}.")

    def edit_child(self) -> None:
        child = self._selected_child()
        if child is None:
            return

        def submit(values: dict[str, Any]) -> Child:
            changes = self.changed(child, values)   # L05: không gửi lại ngày sinh khi không đổi
            if changes:
                self.system.children.update(child.id, **changes)
            return child

        self.form(f"Sửa thông tin {child.full_name}", self._fields(child), submit, success="Đã cập nhật hồ sơ trẻ.")

    def withdraw_child(self) -> None:
        """L14: cho thôi học / ra trường (giữ lịch sử) hoặc cho học lại."""
        child = self._selected_child()
        if child is None:
            return
        if not child.is_active:
            if self.confirm(f"{child.full_name} đang ở trạng thái '{child.status}'. Cho trẻ học lại?"):
                self.guard(self.system.classes.readmit, child.id, success="Trẻ đã học lại - hãy xếp lớp cho trẻ.")
            return
        fields = [Field("status", "Trạng thái mới", "choice", [("Đã nghỉ", "Đã nghỉ học"), ("Ra trường", "Ra trường")],
                        "Đã nghỉ"),
                  Field("on_date", "Từ ngày", "date", default=date.today())]
        self.form(f"Cho {child.full_name} thôi học", fields,
                  lambda v: self.system.withdraw_child(child.id, v["status"], v["on_date"]),
                  success="Đã cập nhật trạng thái. Lịch sử điểm danh, sức khỏe, học phí của trẻ vẫn được giữ.")

    def delete_child(self) -> None:
        child = self._selected_child()
        if child and self.confirm_delete("hồ sơ trẻ", [
                ("Mã trẻ", child.id), ("Họ tên", child.full_name), ("Ngày sinh", format_date(child.dob)),
                ("Giới tính", child.gender), ("Lớp", self.class_name(child.class_id)),
                ("Phụ huynh", ", ".join(p.full_name for p in self.system.parents.parents_of(child.id)) or "-")],
                note="Chỉ dùng cho hồ sơ nhập nhầm - trẻ nghỉ học hãy dùng 'Thôi học / Học lại' để giữ lịch sử. "
                     "Dữ liệu sức khỏe, điểm danh của trẻ cũng bị xóa."):
            self.guard(self.system.children.remove, child.id, success=f"Đã xóa hồ sơ {child}.")

    def view_detail(self) -> None:
        child = self._selected_child()
        if child is None:
            return
        s = self.system
        parts = [format_key_values(child.profile(), title=f"Hồ sơ trẻ: {child.full_name}")]
        parents = s.parents.parents_of(child.id)
        parts.append(format_table(["Mã", "Họ tên", "Quan hệ", "SĐT", "Nghề nghiệp"],
                                  [[p.id, p.full_name, p.relationship, p.phone, p.occupation or "-"] for p in parents],
                                  title="\nPhụ huynh:"))
        if self.can(P.MANAGE_HEALTH):   # L09: thông tin sức khỏe chỉ cho vai trò có quyền
            allergies = s.health.allergies_of(child.id)
            parts.append("\nDị ứng: " + ("; ".join(f"{a.allergen} (mức {a.severity.value.lower()}) - "
                                                    f"{a.reaction or ''}" for a in allergies) or "không có"))
            record = s.health.latest_record(child.id)
            if record:
                parts.append(f"Cân đo gần nhất {format_date(record.measure_date)}: {record.height_cm} cm, "
                             f"{record.weight_kg} kg, BMI {record.bmi_text} -> {record.assess().value}")
        if self.can(P.MANAGE_FINANCE):
            parts.append(f"\nCông nợ học phí: {format_vnd(s.invoices.debt_of_child(child.id))}")
        self.show_text(f"Hồ sơ {child.full_name}", "\n".join(parts))

    def manage_pickups(self) -> None:
        child = self._selected_child()
        if child is not None:
            self.wait_window(PickupDialog(self, child))
            self.app.save()
            self.refresh()

    def link_parent(self) -> None:
        child = self._selected_child()
        if child is None:
            return
        fields = [Field("parent_id", "Phụ huynh", "choice", self.parent_options()),
                  Field("action", "Thao tác", "choice", [("link", "Liên kết"), ("unlink", "Bỏ liên kết")], "link")]

        def submit(values: dict[str, Any]) -> None:
            parents = self.system.parents
            if values["action"] == "link":
                parents.link(values["parent_id"], child.id)
                return
            parent = parents.get(values["parent_id"])
            force = False
            if parent.has_child(child.id) and parents._studying_children_left_alone(parent, [child.id]):
                # L27: hỏi lại trước khi để trẻ đang học không còn phụ huynh nào
                if not self.confirm(f"{child.full_name} sẽ không còn phụ huynh nào để liên hệ/đón. Vẫn bỏ liên kết?"):
                    raise KindergartenError("Đã hủy bỏ liên kết.")
                force = True
            parents.unlink(parent.id, child.id, force=force)

        self.form(f"Phụ huynh của {child.full_name}", fields, submit, success="Đã cập nhật liên kết phụ huynh.")


# =============================================================================
class ParentsTab(BaseTab):
    title = "Phụ huynh"
    permission = P.VIEW_CHILDREN

    def build(self) -> None:
        bar = self.filter_bar()
        ttk.Label(bar, text="Tìm tên / SĐT:").pack(side="left")
        self.keyword = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.keyword, width=28)
        entry.pack(side="left", padx=4)
        entry.bind("<KeyRelease>", self._on_key)
        self._pending: str | None = None
        self.table = DataTable(self, [("Mã", 60), ("Họ tên", 170), ("Quan hệ", 80), ("SĐT", 100), ("Nghề nghiệp", 130),
                                      ("Email", 170), ("Các con", 260)])
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.view_children)
        self.master_bar(self.add_parent, self.edit_parent, self.delete_parent, P.MANAGE_CHILDREN,
                        extras=[("Xem các con", self.view_children)])

    def _on_key(self, _event: Any) -> None:
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(250, self.refresh)

    def refresh(self) -> None:
        self._pending = None
        key = normalize_text(self.keyword.get())
        digits = "".join(ch for ch in key if ch.isdigit())
        parents = [p for p in self.visible_parents()   # L09: giáo viên chỉ thấy phụ huynh lớp mình
                   if not key or key in p.search_text or (digits and digits in p.phone)]
        rows = [[p.id, p.full_name, p.relationship, p.phone, p.occupation or "-", p.email or "-",
                 ", ".join(c.full_name for c in self.system.parents.children_of(p.id)) or "-"] for p in parents]
        self.table.set_rows(rows, [p.id for p in parents])

    def _fields(self, parent: Parent | None = None) -> list[Field]:
        fields = [
            Field("full_name", "Họ tên", default=parent.full_name if parent else None),
            Field("dob", "Ngày sinh (dd/mm/yyyy)", "date", default=parent.dob if parent else None),
            Field("phone", "Số điện thoại", default=parent.phone if parent else None),
            Field("relationship", "Quan hệ với trẻ", "choice", [(r, r) for r in Parent.RELATIONSHIPS],
                  parent.relationship if parent else None),
            Field("occupation", "Nghề nghiệp", default=parent.occupation if parent else None, required=False),
            Field("email", "Email", default=parent.email if parent else None, required=False),
            Field("address", "Địa chỉ", default=parent.address if parent else None, required=False),
        ]
        if parent is None:
            fields.append(Field("child_id", "Liên kết với trẻ", "choice",
                                [(None, "(chưa liên kết)")] + self.child_options(self.system.children.all_sorted()),
                                None, required=False))
        return fields

    def _confirm_shared_phone(self, phone: str, exclude: Parent | None = None) -> None:
        """L27: SĐT trùng với phụ huynh khác -> hỏi có phải cùng một hộ (vợ chồng dùng chung số) không."""
        other = self.system.parents.find_by_phone(phone)
        if other is not None and other is not exclude and not self.confirm(
                f"SĐT {other.phone} đang được dùng cho {other}.\nĐây là người cùng hộ (dùng chung số) phải không?"):
            raise KindergartenError("Hãy nhập số điện thoại khác.")

    def add_parent(self) -> None:
        def submit(values: dict[str, Any]) -> Parent:
            child_id = values.pop("child_id")
            self._confirm_shared_phone(values["phone"])
            parent = Parent(**values, child_ids=[child_id] if child_id else [])
            parent = self.system.parents.add(parent)
            if child_id:
                self.system.parents.link(parent.id, child_id)
            return parent

        self.form("Thêm phụ huynh", self._fields(), submit, success=lambda p: f"Đã thêm phụ huynh {p}.")

    def edit_parent(self) -> None:
        parent = self.selected(self.table, self.system.parents.get, "một phụ huynh")
        if parent is None:
            return

        def submit(values: dict[str, Any]) -> Parent:
            changes = self.changed(parent, values)   # L05
            if "phone" in changes:
                self._confirm_shared_phone(changes["phone"], exclude=parent)
            if changes:
                self.system.parents.update(parent.id, **changes)
            return parent

        self.form(f"Sửa {parent.full_name}", self._fields(parent), submit, success="Đã cập nhật phụ huynh.")

    def delete_parent(self) -> None:
        parent = self.selected(self.table, self.system.parents.get, "một phụ huynh")
        if not parent or not self.confirm_delete("phụ huynh", [
                ("Mã phụ huynh", parent.id), ("Họ tên", parent.full_name), ("Quan hệ", parent.relationship),
                ("Số điện thoại", parent.phone),
                ("Các con", ", ".join(c.full_name for c in self.system.parents.children_of(parent.id)) or "-")],
                note="Liên kết với các con sẽ bị gỡ."):
            return
        alone = self.system.parents._studying_children_left_alone(parent, parent.child_ids)
        force = False
        if alone:   # L27
            if not self.confirm(f"{', '.join(c.full_name for c in alone)} sẽ không còn phụ huynh nào để liên hệ/đón.\n"
                                "Vẫn xóa?"):
                return
            force = True
        self.guard(self.system.parents.remove, parent.id, force=force, success="Đã xóa phụ huynh.")

    def view_children(self) -> None:
        parent = self.selected(self.table, self.system.parents.get, "một phụ huynh")
        if parent is None:
            return
        children = self.system.parents.children_of(parent.id)
        show_debt = self.can(P.MANAGE_FINANCE)   # L09: công nợ chỉ cho kế toán / quản trị
        rows = [[c.id, c.full_name, c.age_text, self.class_name(c.class_id) if c.is_active else c.status]
                + ([format_vnd(self.system.invoices.debt_of_child(c.id))] if show_debt else []) for c in children]
        headers = ["Mã", "Họ tên", "Tuổi", "Lớp"] + (["Công nợ"] if show_debt else [])
        text = format_table(headers, rows,
                            title=f"Các con của {parent.full_name} ({len(children)} trẻ)")
        self.show_text("Các con của phụ huynh", text)


# =============================================================================
class HealthTab(BaseTab):
    title = "Sức khỏe"
    permission = P.MANAGE_HEALTH

    def build(self) -> None:
        notebook = self.notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        # P05: chỉ nạp lại tab con đang xem
        notebook.bind("<<NotebookTabChanged>>", lambda _e: self.refresh())
        growth, allergy = (ttk.Frame(notebook, padding=6) for _ in range(2))
        notebook.add(growth, text="Tăng trưởng - dinh dưỡng")
        notebook.add(allergy, text="Dị ứng")
        # ---- tăng trưởng
        self.growth_table = DataTable(growth, [("Mã", 60), ("Họ tên", 170), ("Lớp", 130), ("Ngày đo", 90),
                                               ("Cao (cm)", 70, "e"), ("Nặng (kg)", 70, "e"), ("BMI", 60, "e"),
                                               ("Đánh giá", 100)])
        self.growth_table.pack(fill="both", expand=True)
        self.growth_table.on_double_click(self.history)
        bar = self.bar(growth, pady=(6, 0))
        self.button(bar, "Nhập kết quả cân đo", self.add_record, style="Accent.TButton")
        self.button(bar, "Lịch sử tăng trưởng", self.history)
        self.button(bar, "Xóa một lần đo", self.delete_record)
        # ---- dị ứng
        self.allergy_table = DataTable(allergy, [("Mã", 60), ("Trẻ", 170), ("Lớp", 130), ("Chất gây dị ứng", 150),
                                                 ("Mức độ", 90), ("Biểu hiện", 260)])
        self.allergy_table.pack(fill="both", expand=True)
        bar = self.bar(allergy, pady=(6, 0))
        self.button(bar, "Thêm thông tin dị ứng", self.add_allergy, style="Accent.TButton")
        self.button(bar, "Xóa", self.delete_allergy)

    def _visible_ids(self) -> set[str]:
        return {c.id for c in self.system.children_for(self.user)}

    def refresh(self) -> None:
        h, visible = self.system.health, self.system.children_for(self.user)
        allowed = {c.id for c in visible}
        try:
            current = self.notebook.index("current")
        except tk.TclError:
            current = 0
        if current == 1:
            self._refresh_allergies(allowed)
        else:
            self._refresh_growth(visible)

    def _refresh_growth(self, visible: list[Child]) -> None:
        h = self.system.health
        rows, tags = [], []
        for child in visible:
            record = h.latest_record(child.id)
            if record is None:
                rows.append([child.id, child.full_name, self.class_name(child.class_id), "-", "", "", "", "Chưa đo"])
                tags.append("muted")
                continue
            status = record.assess()
            rows.append([child.id, child.full_name, self.class_name(child.class_id), format_date(record.measure_date),
                         record.height_cm, record.weight_kg, record.bmi_text, status.value])
            tags.append(None if status is NutritionStatus.NORMAL else "warn")
        self.growth_table.set_rows(rows, [c.id for c in visible], tags)

    def _refresh_allergies(self, allowed: set[str]) -> None:
        h = self.system.health
        allergies = [a for a in h.allergies.sort("child_id") if a.child_id in allowed]
        self.allergy_table.set_rows(
            [[a.id, self._child_name(a.child_id), self.class_name(self._child_class(a.child_id)), a.allergen,
              a.severity.value, a.reaction or "-"] for a in allergies],
            [a.id for a in allergies], ["warn" if a.severity is AllergySeverity.SEVERE else None for a in allergies])

    def _child_name(self, child_id: str) -> str:
        child = self.system.children.get_or_none(child_id)
        return child.full_name if child else child_id

    def _child_class(self, child_id: str) -> str | None:
        child = self.system.children.get_or_none(child_id)
        return child.class_id if child else None

    def add_record(self) -> None:
        fields = [Field("child_id", "Trẻ", "choice", self.child_options(), self.growth_table.selected_id()),
                  Field("measure_date", "Ngày đo", "date", default=date.today()),
                  Field("height_cm", "Chiều cao (cm)"), Field("weight_kg", "Cân nặng (kg)"),
                  Field("note", "Ghi chú", required=False)]
        self.form("Nhập kết quả cân đo", fields, lambda v: self.system.health.add_health_record(**v),
                  success=lambda r: f"BMI {r.bmi_text} -> {r.assess().value}.")

    def history(self) -> None:
        child = self.selected(self.growth_table, self.system.children.get, "một trẻ")
        if child is None:
            return
        rows = []
        for item in self.system.health.growth_history(child.id):
            record = item["record"]
            rows.append([format_date(record.measure_date), record.age_months, record.height_cm, record.weight_kg,
                         format_number(item["bmi"]), item["status"].value,
                         "" if item["height_change"] is None else f"{item['height_change']:+.1f}",
                         "" if item["weight_change"] is None else f"{item['weight_change']:+.1f}"])
        self.show_text("Quá trình tăng trưởng", format_table(
            ["Ngày đo", "Tháng tuổi", "Cao (cm)", "Nặng (kg)", "BMI", "Đánh giá", "+Cao", "+Nặng"], rows,
            title=f"Quá trình tăng trưởng - {child.full_name}"))

    def delete_record(self) -> None:
        """U01: xóa lần cân đo nhập nhầm."""
        child = self.selected(self.growth_table, self.system.children.get, "một trẻ")
        if child is None:
            return
        records = self.system.health.records_of(child.id)
        if not records:
            messagebox.showinfo("Không có dữ liệu", f"{child.full_name} chưa có lần cân đo nào.", parent=self)
            return
        options = [(r.id, f"{format_date(r.measure_date)}: {r.height_cm} cm, {r.weight_kg} kg") for r in records]
        self.form(f"Xóa lần đo của {child.full_name}",
                  [Field("record_id", "Lần đo", "choice", options, records[-1].id)],
                  lambda v: self.system.health.remove_health_record(v["record_id"]),
                  success="Đã xóa lần đo.", submit_text="Xóa")

    def add_allergy(self) -> None:
        fields = [Field("child_id", "Trẻ", "choice", self.child_options()),
                  Field("allergen", "Chất gây dị ứng (VD: tôm, sữa bò)"),
                  Field("severity", "Mức độ", "choice", [(s, s.value) for s in AllergySeverity], AllergySeverity.MILD),
                  Field("reaction", "Biểu hiện", required=False)]
        self.form("Thêm thông tin dị ứng", fields, lambda v: self.system.health.add_allergy(**v),
                  success="Đã lưu. Thực đơn sẽ tự cảnh báo món có chất này.")

    def delete_allergy(self) -> None:
        allergy = self.selected(self.allergy_table, self.system.health.allergies.get, "một dòng dị ứng")
        if allergy and self.confirm(f"Xóa dị ứng '{allergy.allergen}' của {self._child_name(allergy.child_id)}?"):
            self.guard(self.system.health.remove_allergy, allergy.id)
