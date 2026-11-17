"""Màn hình console: tài khoản, đổi mật khẩu, lưu/sao lưu/nạp dữ liệu (T06, T07, T30)."""
from __future__ import annotations

from ....auth.user import Permission, Role, User
from ....exceptions import ValidationError
from ..menu import Menu
from .base import Screen


class SystemScreen(Screen):
    title = "Tài khoản & hệ thống"

    def build_menu(self) -> Menu:
        P = Permission
        menu = (self.new_menu()
                .add("Đổi mật khẩu", self.change_password)
                .add("Danh sách tài khoản", self.list_users, P.MANAGE_USERS)
                .add("Duyệt tài khoản nhân sự tự đăng ký", self.approve, P.MANAGE_USERS)
                .add("Tạo tài khoản", self.create_user, P.MANAGE_USERS)
                .add("Sửa tài khoản (họ tên, vai trò, liên kết nhân sự)", self.edit_user, P.MANAGE_USERS)
                .add("Khóa / mở khóa tài khoản", self.toggle_user, P.MANAGE_USERS)
                .add("Đặt lại mật khẩu cho tài khoản", self.reset_password, P.MANAGE_USERS)
                .add("Nhật ký thao tác", self.audit_log, P.MANAGE_USERS)
                .add("Lưu dữ liệu ngay", self.save, P.MANAGE_DATA)
                .add("Sao lưu dữ liệu", self.backup, P.MANAGE_DATA)
                .add("Khôi phục từ bản sao lưu", self.restore, P.MANAGE_DATA)
                .add("Xóa tài khoản", self.delete_user, P.MANAGE_USERS))
        if self.app.seed_func is not None:
            menu.add("Nạp lại dữ liệu mẫu (XÓA dữ liệu hiện tại)", self.reseed, P.MANAGE_DATA)
        return menu

    def _ask_password(self, prompt: str) -> str:
        password = self.io.input_password(f"{prompt}: ")
        User.validate_password(password)
        confirm = self.io.input_password("Nhập lại mật khẩu: ")
        if confirm != password:
            raise ValidationError("Hai lần nhập mật khẩu không khớp.")
        return password

    def change_password(self) -> None:
        old = self.io.input_password("Mật khẩu hiện tại: ")
        new = self._ask_password("Mật khẩu mới (ít nhất 6 ký tự)")
        self.auth.change_password(old, new)
        self.system.audit("Đổi mật khẩu", self.system.username)
        self.io.success("Đã đổi mật khẩu.")

    def _user_label(self, user: User) -> str:
        return f"{user.id} - {user.username} ({user.full_name}, {user.role.label}, {user.status_text.lower()})"

    def approve(self) -> None:
        pending = self.auth.pending_users()
        user = self._require(self.io.choose(pending, self._user_label, "Tài khoản chờ duyệt",
                                            "Không có tài khoản nào chờ duyệt."))
        employee = self.system.employees.get_or_none(user.employee_id) if user.employee_id else None
        if employee:
            self.io.info(f"Hồ sơ nhân sự: {employee.full_name} - {employee.position} - SĐT {employee.phone}")
        action = self.io.ask_choice("Quyết định", [("ok", "Duyệt"), ("no", "Từ chối"), ("skip", "Để sau")], "ok")
        if action == "ok":
            self.system.approve_user(user.id)
            self.io.success(f"Đã duyệt - {user.username} đăng nhập được ngay.")
        elif action == "no":
            self.system.reject_user(user.id)
            self.io.success("Đã từ chối.")

    def _select_user(self, title: str = "Chọn tài khoản") -> User:
        return self._require(self.io.choose(self.auth.sort("username"), self._user_label, title))

    def list_users(self) -> None:
        rows = []
        for user in self.auth.sort("username"):
            last = user.last_login.replace("T", " ") if user.last_login else "-"
            rows.append([user.id, user.username, user.full_name, user.role.label,
                         user.employee_id or user.parent_id or "-", user.status_text, last])
        self.io.table(["Mã", "Tên đăng nhập", "Họ tên", "Vai trò", "Mã NS", "Trạng thái", "Đăng nhập gần nhất"],
                      rows, title="DANH SÁCH TÀI KHOẢN")

    def _check_username(self, raw: str) -> str:
        """U06: báo trùng tên đăng nhập ngay khi nhập, không đợi tới sau khi gõ mật khẩu."""
        probe = raw.strip().lower()
        if self.auth.find_by_username(probe):
            raise ValidationError(f"Tên đăng nhập '{probe}' đã tồn tại.")
        if not User._USERNAME_PATTERN.match(probe):
            raise ValidationError("Tên đăng nhập dài 3–30 ký tự, chỉ gồm chữ thường không dấu, số, dấu chấm "
                                  "hoặc gạch dưới.")
        return probe

    def create_user(self) -> None:
        io = self.io
        username = io.ask("Tên đăng nhập (chữ thường không dấu, số, dấu chấm)", self._check_username)
        role = io.ask_choice("Vai trò", [(r, r.label) for r in Role])
        employee_id = parent_id = None
        if role is Role.PARENT:   # tài khoản phụ huynh phải gắn hồ sơ phụ huynh
            linked = {u.parent_id for u in self.auth if u.parent_id}
            parent_id = self.select_parent([p for p in self.system.parents.all_sorted() if p.id not in linked],
                                           "Liên kết với hồ sơ phụ huynh (bắt buộc)").id
        elif role is Role.TEACHER:   # L08: bắt buộc liên kết; U06: chỉ hiện giáo viên chưa có tài khoản
            teacher = self.select_teacher(self.system.employees_without_account(teachers_only=True),
                                          "Liên kết với hồ sơ giáo viên (bắt buộc)")
            employee_id = teacher.id
        elif io.ask_yes_no("Liên kết với hồ sơ nhân sự", default=False):
            employee_id = self.select_employee(self.system.employees_without_account()).id
        full_name = io.ask_text("Họ tên hiển thị", required=False) or ""
        password = self._ask_password("Mật khẩu (ít nhất 6 ký tự)")
        user = self.system.create_user(username, password, role, full_name, employee_id, parent_id)
        io.success(f"Đã tạo tài khoản {user}.")

    def edit_user(self) -> None:
        """U01: sửa họ tên, vai trò, liên kết nhân sự của tài khoản."""
        io = self.io
        user = self._select_user()
        changes = {"full_name": io.ask_text("Họ tên hiển thị", user.full_name),
                   "role": io.ask_choice("Vai trò", [(r, r.label) for r in Role], user.role)}
        if changes["role"] is Role.TEACHER:
            options = self.system.employees_without_account(teachers_only=True)
            current = self.system.teacher_of(user)
            if current is not None:
                options = [current] + options
            changes["employee_id"] = self.select_teacher(options, "Hồ sơ giáo viên liên kết").id
        changes = {k: v for k, v in changes.items() if v != getattr(user, k)}
        if not changes:
            io.info("Không có thay đổi.")
            return
        self.auth.update(user.id, **changes)
        self.system.audit("Sửa tài khoản", user.username, {k: str(v) for k, v in changes.items()})
        io.success(f"Đã cập nhật tài khoản {user}.")

    def toggle_user(self) -> None:
        user = self._select_user()
        self.system.set_user_active(user.id, not user.active)
        self.io.success(f"Tài khoản {user.username} đã được {'mở khóa' if user.active else 'khóa'}.")

    def reset_password(self) -> None:
        user = self._select_user()
        password = self._ask_password(f"Mật khẩu mới cho {user.username}")
        self.system.reset_password(user.id, password)
        self.io.success(f"Đã đặt lại mật khẩu cho {user.username} (người dùng sẽ phải đổi ở lần đăng nhập tới).")

    def delete_user(self) -> None:
        user = self._select_user()
        if self.confirm(f"Xóa tài khoản {user.username}?"):
            self.auth.remove(user.id)
            self.io.success("Đã xóa tài khoản.")

    def audit_log(self) -> None:
        """K06: ai đã làm gì, lúc nào."""
        entries = self.system.audit_log.read(100)
        rows = [[e.get("at", "").replace("T", " "), e.get("user", ""), e.get("action", ""), e.get("target", ""),
                 str(e.get("detail") or "")] for e in entries]
        self.io.table(["Thời điểm", "Người dùng", "Hành động", "Đối tượng", "Chi tiết"], rows,
                      title="NHẬT KÝ THAO TÁC (100 dòng mới nhất)", max_width=50)

    def save(self) -> None:
        path = self.system.save()
        self.io.success(f"Đã lưu dữ liệu vào {path}")

    def backup(self) -> None:
        path = self.system.backup()
        self.io.success(f"Đã sao lưu dữ liệu vào {path}")

    def restore(self) -> None:
        """P07: khôi phục từ bản sao lưu; hiện trạng được sao lưu trước, sau đó phải đăng nhập lại."""
        backups = self.system.store.list_backups()
        name = self._require(self.io.choose(backups, str, "Chọn bản sao lưu", "Chưa có bản sao lưu nào."))
        if not self.confirm(f"Khôi phục dữ liệu từ {name}? Dữ liệu hiện tại sẽ được sao lưu trước khi thay"):
            return
        self.system.restore_backup(name)
        self.io.success(f"Đã khôi phục từ {name}. Vui lòng đăng nhập lại.")
        self.app.request_logout()

    def reseed(self) -> None:
        if not self.confirm("Toàn bộ dữ liệu hiện tại sẽ bị thay bằng dữ liệu mẫu. Tiếp tục"):
            return
        backup = self.system.backup()
        self.io.info(f"Đã sao lưu dữ liệu cũ vào {backup}")
        counts = self.app.seed_func(self.system)
        self.system.save()
        self.io.success("Đã nạp dữ liệu mẫu: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        self.io.warning("Vui lòng đăng nhập lại.")
        self.app.request_logout()
