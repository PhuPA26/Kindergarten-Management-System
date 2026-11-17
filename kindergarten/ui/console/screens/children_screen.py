"""Màn hình console: quản lý trẻ và phụ huynh (T09-T11)."""
from __future__ import annotations

from datetime import date

from ....auth.user import Permission
from ....exceptions import KindergartenError, ValidationError
from ....people.child import Child, PickupPerson
from ....people.parent import Parent
from ....utils import calculate_age, format_date, format_vnd, validate_name
from ..menu import Menu
from .base import Screen


class ChildrenScreen(Screen):
    title = "Trẻ & phụ huynh"

    def build_menu(self) -> Menu:
        """U11: tách hai nhóm Trẻ / Phụ huynh; thao tác xóa đặt cuối mỗi nhóm."""
        P = Permission
        return (self.new_menu()
                .add("Hồ sơ trẻ", self.children_menu().run, P.VIEW_CHILDREN, pause=False)
                .add("Phụ huynh", self.parents_menu().run, P.VIEW_CHILDREN, pause=False))

    def children_menu(self) -> Menu:
        P = Permission
        return (self.app.new_menu("Trẻ & phụ huynh › Hồ sơ trẻ")
                .add("Danh sách trẻ đang học", self.list_children, P.VIEW_CHILDREN)
                .add("Tìm kiếm trẻ (theo tên / lớp / độ tuổi)", self.search_children, P.VIEW_CHILDREN)
                .add("Xem hồ sơ chi tiết của trẻ", self.view_child, P.VIEW_CHILDREN)
                .add("Tiếp nhận trẻ mới", self.add_child, P.MANAGE_CHILDREN)
                .add("Sửa thông tin trẻ", self.edit_child, P.MANAGE_CHILDREN)
                .add("Quản lý người đón hộ", self.manage_pickups, P.MANAGE_CHILDREN)
                .add("Danh sách trẻ đã nghỉ / ra trường", self.list_inactive, P.VIEW_CHILDREN)
                .add("Cho trẻ thôi học / cho học lại", self.withdraw_child, P.MANAGE_CHILDREN)
                .add("Xóa hẳn hồ sơ nhập nhầm", self.delete_child, P.MANAGE_CHILDREN))

    def parents_menu(self) -> Menu:
        P = Permission
        return (self.app.new_menu("Trẻ & phụ huynh › Phụ huynh")
                .add("Danh sách phụ huynh", self.list_parents, P.VIEW_CHILDREN)
                .add("Tìm các con của một phụ huynh", self.children_of_parent, P.VIEW_CHILDREN)
                .add("Thêm phụ huynh", self.add_parent, P.MANAGE_CHILDREN)
                .add("Sửa thông tin phụ huynh", self.edit_parent, P.MANAGE_CHILDREN)
                .add("Liên kết / bỏ liên kết phụ huynh - trẻ", self.link_parent, P.MANAGE_CHILDREN)
                .add("Xóa phụ huynh", self.delete_parent, P.MANAGE_CHILDREN))

    # ================================================================== TRẺ
    def show_children(self, children: list[Child], title: str) -> None:
        rows = []
        for index, child in enumerate(children, 1):
            parents = self.system.parents.parents_of(child.id)
            rows.append([index, child.id, child.full_name, child.gender, format_date(child.dob), child.age_text,
                         self.class_name(child.class_id), ", ".join(p.full_name for p in parents) or "-"])
        self.io.table(["STT", "Mã", "Họ tên", "Giới tính", "Ngày sinh", "Tuổi", "Lớp", "Phụ huynh"], rows,
                      title=f"{title} ({len(children)} trẻ)")

    def list_children(self) -> None:
        self.show_children(self.visible_children(), "DANH SÁCH TRẺ")

    def search_children(self) -> None:
        manager = self.system.children
        mode = self.io.ask_choice("Tìm theo", [("name", "Họ tên / tên ở nhà"), ("class", "Lớp"),
                                               ("age", "Độ tuổi"), ("none", "Trẻ chưa xếp lớp")])
        if mode == "name":
            result = manager.search_by_name(self.io.ask_text("Từ khóa (có thể gõ không dấu)"))
        elif mode == "class":
            result = manager.find_by_class(self.select_class().id)
        elif mode == "age":
            low = self.io.ask_int("Từ tuổi", 1, 0, 7)
            high = self.io.ask_int("Đến tuổi", low, low, 7)
            result = manager.find_by_age_range(low, high)
        else:
            result = manager.find_unassigned()
        self.show_children(self.visible_children(result), "KẾT QUẢ TÌM KIẾM")

    def view_child(self) -> None:
        s = self.system
        child = self.select_child()
        self.io.key_values(child.profile(), title=f"\nHỒ SƠ TRẺ: {child.full_name.upper()}")
        parents = s.parents.parents_of(child.id)
        self.io.table(["Mã", "Họ tên", "Quan hệ", "SĐT", "Nghề nghiệp"],
                      [[p.id, p.full_name, p.relationship, p.phone, p.occupation or "-"] for p in parents],
                      title="Phụ huynh:")
        if self.auth.has_permission(Permission.MANAGE_HEALTH):   # L09: thông tin sức khỏe chỉ cho người có quyền
            allergies = s.health.allergies_of(child.id)
            self.io.write("Dị ứng: " + ("; ".join(f"{a.allergen} (mức {a.severity.value.lower()})"
                                                  for a in allergies) or "không có"))
            record = s.health.latest_record(child.id)
            if record:
                self.io.write(f"Cân đo gần nhất {format_date(record.measure_date)}: {record.height_cm} cm, "
                              f"{record.weight_kg} kg, BMI {record.bmi_text} -> {record.assess().value}")
        if self.auth.has_permission(Permission.MANAGE_FINANCE):
            self.io.write(f"Công nợ học phí: {format_vnd(s.invoices.debt_of_child(child.id))}")

    def _ask_services(self, current: list[str]) -> list[str]:
        services = list(self.system.settings.extra_services.items())
        if not services:
            return []
        self.io.write("Dịch vụ tự chọn:")
        for index, (name, price) in enumerate(services, 1):
            self.io.write(f"    {index}. {name} - {format_vnd(price)}/tháng")
        current_idx = [str(i) for i, (name, _) in enumerate(services, 1) if name in current]

        def parser(raw: str) -> list[str]:
            if raw == "-":
                return []
            result = []
            for part in raw.replace(",", " ").split():
                if not part.isdigit() or not 1 <= int(part) <= len(services):
                    raise ValidationError(f"'{part}' không phải số thứ tự dịch vụ hợp lệ.")
                result.append(services[int(part) - 1][0])
            return result

        default = current if current else None
        return self.io.ask("Đăng ký dịch vụ (STT cách nhau dấu phẩy, '-' = không đăng ký)", parser, default,
                           required=False, display_default=",".join(current_idx)) or []

    def _ask_parents_for_new_child(self) -> list[str]:
        parent_ids: list[str] = []
        while True:
            choice = self.io.ask_choice(f"Liên kết phụ huynh (đã chọn {len(parent_ids)})",
                                        [("done", "Xong / bỏ qua"), ("existing", "Chọn phụ huynh đã có"),
                                         ("new", "Thêm phụ huynh mới")], default="done")
            if choice == "done":
                return parent_ids
            if choice == "existing":
                parent = self.io.choose(self.system.parents.all_sorted(), self.parent_label, "Chọn phụ huynh")
            else:
                parent = self._create_parent()
            if parent is not None and parent.id not in parent_ids:
                parent_ids.append(parent.id)

    def _ask_class_for_age(self, age: int) -> str | None:
        options = [c for c in self.system.classes.all_sorted() if c.accepts_age(age) and not c.is_full]
        if not options:
            self.io.warning("Chưa có lớp phù hợp độ tuổi còn chỗ trống - trẻ được đưa vào danh sách chờ xếp lớp.")
            return None
        classroom = self.io.choose(options, self.class_label, "Xếp vào lớp (Enter = chờ xếp lớp sau)")
        return classroom.id if classroom else None

    def add_child(self) -> None:
        io = self.io
        io.info("Nhập thông tin trẻ (nhập ! để hủy):")
        data = {
            "full_name": io.ask_text("Họ tên trẻ", validator=validate_name),
            "dob": self.ask_dob(Child),
            "gender": io.ask_choice("Giới tính", [("Nam", "Nam"), ("Nữ", "Nữ")]),
            "nickname": io.ask_text("Tên ở nhà", required=False) or "",
            "address": io.ask_text("Địa chỉ", required=False) or "",
            "is_poor_household": io.ask_yes_no("Thuộc diện hộ nghèo", default=False),
        }
        data["extra_services"] = self._ask_services([])
        data["notes"] = io.ask_text("Ghi chú (sức khỏe, thói quen...)", required=False) or ""
        Child(**data)  # kiểm tra toàn bộ dữ liệu trước khi chọn lớp và phụ huynh
        # L23: hỏi lớp TRƯỚC khi tạo phụ huynh mới, hủy ở bước chọn lớp sẽ không để lại phụ huynh không có con
        class_id = self._ask_class_for_age(calculate_age(data["dob"]))
        parent_ids = self._ask_parents_for_new_child()
        child = self.system.enroll_new_child(parent_ids=parent_ids, class_id=class_id, **data)
        io.success(f"Đã tiếp nhận {child} - lớp: {self.class_name(child.class_id)}.")

    def edit_child(self) -> None:
        io = self.io
        child = self.select_child()
        io.info("Nhấn Enter để giữ nguyên giá trị hiện tại.")
        new_data = {
            "full_name": io.ask_text("Họ tên", child.full_name, validator=validate_name),
            "dob": self.ask_dob(Child, child.dob),
            "gender": io.ask_choice("Giới tính", [("Nam", "Nam"), ("Nữ", "Nữ")], default=child.gender),
            "nickname": io.ask_text("Tên ở nhà", child.nickname, required=False),
            "address": io.ask_text("Địa chỉ", child.address, required=False),
            "is_poor_household": io.ask_yes_no("Thuộc diện hộ nghèo", child.is_poor_household),
            "extra_services": self._ask_services(child.extra_services),
            "notes": io.ask_text("Ghi chú", child.notes, required=False),
        }
        changes = {k: v for k, v in new_data.items() if v is not None and v != getattr(child, k)}
        if not changes:
            io.info("Không có thay đổi.")
            return
        self.system.children.update(child.id, **changes)   # ràng buộc lớp - độ tuổi kiểm tra ở tầng nghiệp vụ (L11)
        io.success(f"Đã cập nhật hồ sơ {child}.")

    def list_inactive(self) -> None:
        children = self.system.children.find_inactive()
        rows = [[i, c.id, c.full_name, c.age_text, c.status, format_date(c.leave_date)]
                for i, c in enumerate(children, 1)]
        self.io.table(["STT", "Mã", "Họ tên", "Tuổi", "Trạng thái", "Từ ngày"], rows,
                      title=f"TRẺ ĐÃ NGHỈ / RA TRƯỜNG ({len(children)} trẻ)")

    def withdraw_child(self) -> None:
        """L14: cho thôi học/ra trường thay vì xóa - giữ lại lịch sử điểm danh, sức khỏe, học phí."""
        action = self.io.ask_choice("Thao tác", [("withdraw", "Cho trẻ thôi học / ra trường"),
                                                 ("readmit", "Cho trẻ đã nghỉ học lại")])
        if action == "readmit":
            child = self.select_child(self.system.children.find_inactive(), "Chọn trẻ học lại")
            self.system.classes.readmit(child.id)
            self.io.success(f"{child.full_name} đã trở lại trạng thái đang học - hãy xếp lớp cho trẻ.")
            return
        child = self.select_child()
        status = self.io.ask_choice("Trạng thái mới", [("Đã nghỉ", "Đã nghỉ học"), ("Ra trường", "Ra trường")])
        on_date = self.io.ask_date("Từ ngày", date.today())
        debt = self.system.invoices.debt_of_child(child.id)
        note = f" (còn nợ học phí {format_vnd(debt)})" if debt else ""
        if self.confirm(f"Chuyển {child.full_name} sang '{status}' từ {format_date(on_date)}{note}?"):
            self.system.withdraw_child(child.id, status, on_date)
            self.io.success(f"Đã cập nhật: {child.full_name} - {status}. Lịch sử của trẻ vẫn được giữ.")

    def delete_child(self) -> None:
        child = self.select_child(self.system.children.all_sorted(include_inactive=True))
        self.io.warning("Chỉ dùng khi hồ sơ nhập nhầm. Trẻ nghỉ học hãy dùng 'Cho trẻ thôi học' để giữ lịch sử.")
        if not self.confirm(f"Xóa HẲN hồ sơ {child}? (điểm danh, sức khỏe của trẻ cũng bị xóa, không hoàn tác)"):
            return
        self.system.children.remove(child.id)
        self.io.success(f"Đã xóa hồ sơ {child}.")

    def manage_pickups(self) -> None:
        io = self.io
        child = self.select_child()
        while True:
            persons = child.pickup_persons
            io.table(["STT", "Họ tên", "Quan hệ", "SĐT", "CCCD"],
                     [[i, p.full_name, p.relationship, p.phone, p.id_card or "-"] for i, p in enumerate(persons, 1)],
                     title=f"Người đón hộ của {child.full_name}:")
            action = io.ask_choice("Thao tác", [("done", "Xong"), ("add", "Thêm người đón hộ"),
                                                ("remove", "Xóa người đón hộ")], default="done")
            if action == "done":
                return
            if action == "add":
                person = PickupPerson(io.ask_text("Họ tên người đón", validator=validate_name),
                                      io.ask_text("Quan hệ với trẻ (VD: Bà ngoại)"), io.ask_phone("SĐT"),
                                      io.ask_text("Số CCCD", required=False) or "")
                child.add_pickup_person(person)
                io.success(f"Đã thêm {person.full_name}.")
            else:
                person = io.choose(persons, str, "Chọn người cần xóa", "Chưa có người đón hộ.")
                if person is not None:
                    child.remove_pickup_person(person.full_name)
                    io.success(f"Đã xóa {person.full_name}.")

    # ================================================================== PHỤ HUYNH
    def show_parents(self, parents: list[Parent], title: str) -> None:
        rows = []
        for index, parent in enumerate(parents, 1):
            children = self.system.parents.children_of(parent.id)
            rows.append([index, parent.id, parent.full_name, parent.relationship, parent.phone,
                         parent.occupation or "-", ", ".join(c.full_name for c in children) or "-"])
        self.io.table(["STT", "Mã", "Họ tên", "Quan hệ", "SĐT", "Nghề nghiệp", "Các con"], rows,
                      title=f"{title} ({len(parents)} người)")

    def list_parents(self) -> None:
        self.show_parents(self.visible_parents(), "DANH SÁCH PHỤ HUYNH")

    def _phone_checker(self, exclude: Parent | None = None):
        """L27/U06: báo ngay khi SĐT trùng; vợ chồng dùng chung số thì xác nhận để tiếp tục."""
        def check(phone: str) -> None:
            other = self.system.parents.find_by_phone(phone)
            if other is not None and other is not exclude:
                if not self.io.ask_yes_no(f"SĐT {phone} đang dùng cho {other}. Đây là người cùng hộ "
                                          "(dùng chung số)", default=False):
                    raise ValidationError(f"SĐT {phone} đã được dùng cho phụ huynh {other}.")
        return check

    def _create_parent(self) -> Parent:
        io = self.io
        io.info("Nhập thông tin phụ huynh:")
        parent = Parent(
            full_name=io.ask_text("Họ tên phụ huynh", validator=validate_name),
            dob=self.ask_dob(Parent),
            phone=io.ask_phone("Số điện thoại", check=self._phone_checker()),
            relationship=io.ask_choice("Quan hệ với trẻ", [(r, r) for r in Parent.RELATIONSHIPS]),
            occupation=io.ask_text("Nghề nghiệp", required=False) or "",
            email=io.ask_text("Email", required=False) or "",
            address=io.ask_text("Địa chỉ", required=False) or "",
        )
        self.system.parents.add(parent)
        io.success(f"Đã thêm phụ huynh {parent}.")
        return parent

    def add_parent(self) -> None:
        parent = self._create_parent()
        if self.io.ask_yes_no("Liên kết với trẻ ngay", default=True):
            child = self.select_child(self.system.children.all_sorted())
            self.system.parents.link(parent.id, child.id)
            self.io.success(f"Đã liên kết {parent.full_name} với {child.full_name}.")

    def edit_parent(self) -> None:
        io = self.io
        parent = self.select_parent()
        io.info("Nhấn Enter để giữ nguyên giá trị hiện tại.")
        new_data = {
            "full_name": io.ask_text("Họ tên", parent.full_name, validator=validate_name),
            "dob": self.ask_dob(Parent, parent.dob),
            "phone": io.ask_phone("Số điện thoại", parent.phone, check=self._phone_checker(parent)),
            "relationship": io.ask_choice("Quan hệ với trẻ", [(r, r) for r in Parent.RELATIONSHIPS],
                                          default=parent.relationship),
            "occupation": io.ask_text("Nghề nghiệp", parent.occupation, required=False),
            "email": io.ask_text("Email", parent.email, required=False),
            "address": io.ask_text("Địa chỉ", parent.address, required=False),
        }
        changes = {k: v for k, v in new_data.items() if v is not None and v != getattr(parent, k)}
        if not changes:
            io.info("Không có thay đổi.")
            return
        self.system.parents.update(parent.id, **changes)
        io.success(f"Đã cập nhật {parent}.")

    def delete_parent(self) -> None:
        parent = self.select_parent()
        if not self.confirm(f"Xóa phụ huynh {parent}? (liên kết với các con sẽ bị gỡ)"):
            return
        try:
            self.system.parents.remove(parent.id)
        except KindergartenError as exc:   # L27: trẻ sắp không còn người liên hệ -> hỏi xác nhận lần nữa
            if "không còn phụ huynh" not in exc.message or not self.confirm(f"{exc.message}\nVẫn xóa"):
                raise
            self.system.parents.remove(parent.id, force=True)
        self.io.success(f"Đã xóa {parent}.")

    def link_parent(self) -> None:
        parent = self.select_parent()
        action = self.io.ask_choice("Thao tác", [("link", "Liên kết với một trẻ"),
                                                 ("unlink", "Bỏ liên kết với một trẻ")])
        if action == "link":
            child = self.select_child(self.system.children.all_sorted())
            self.system.parents.link(parent.id, child.id)
            self.io.success(f"Đã liên kết {parent.full_name} - {child.full_name}.")
        else:
            child = self.select_child(self.system.parents.children_of(parent.id), "Chọn trẻ cần bỏ liên kết")
            try:
                self.system.parents.unlink(parent.id, child.id)
            except KindergartenError as exc:   # L27
                if "không còn phụ huynh" not in exc.message or not self.confirm(f"{exc.message}\nVẫn bỏ liên kết"):
                    raise
                self.system.parents.unlink(parent.id, child.id, force=True)
            self.io.success(f"Đã bỏ liên kết {parent.full_name} - {child.full_name}.")

    def children_of_parent(self) -> None:
        parent = self.select_parent()
        children = self.system.parents.children_of(parent.id)
        show_debt = self.auth.has_permission(Permission.MANAGE_FINANCE)
        rows = []
        for index, child in enumerate(children, 1):
            row = [index, child.id, child.full_name, child.age_text, self.class_name(child.class_id)]
            if show_debt:
                row.append(format_vnd(self.system.invoices.debt_of_child(child.id)))
            rows.append(row)
        headers = ["STT", "Mã", "Họ tên", "Tuổi", "Lớp"] + (["Công nợ"] if show_debt else [])
        self.io.table(headers, rows, title=f"Các con của {parent.full_name} ({len(children)} trẻ):")
