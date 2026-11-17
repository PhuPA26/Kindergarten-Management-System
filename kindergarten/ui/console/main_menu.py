"""T08 - MainMenu (console): đăng nhập, menu chính hiển thị theo vai trò đăng nhập."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ... import APP_NAME, __version__
from ...applog import log_exception
from ...auth.user import Permission, Role, User
from ...exceptions import AuthenticationError, KindergartenError, ValidationError
from ...system import KindergartenSystem
from .console_io import CancelledInput, ConsoleIO
from .menu import Menu
from .screens import (AttendanceScreen, ChildrenScreen, ClassScreen, FinanceScreen, HealthScreen, HRScreen,
                      NutritionScreen, ReportScreen, SystemScreen)
from .screens.daily_screen import DailyScreen
from .screens.parent_screen import ParentScreen

SeedFunc = Callable[[KindergartenSystem], dict[str, int]]


class MainMenu:
    def __init__(self, system: KindergartenSystem, io: ConsoleIO | None = None, *, autosave: bool = True,
                 seed_func: SeedFunc | None = None, demo_accounts: list[tuple[str, str, str]] | None = None) -> None:
        self.system = system
        self.io = io or ConsoleIO()
        self.autosave = autosave
        self.seed_func = seed_func
        self.demo_accounts = demo_accounts or []
        base = Path(system.store.data_dir).resolve().parent
        self.export_dir = base / "exports"
        self.log_path = base / "logs" / "error.log"
        self._logout_requested = False

    # ------------------------------------------------------------------ tiện ích cho các màn hình
    def new_menu(self, title: str, exit_label: str = "Quay lại") -> Menu:
        return Menu(title, self.io, self.system.auth, exit_label=exit_label, after_action=self._after_action,
                    header=self._user_line, error_log=self._log_error, exit_when=lambda: self._logout_requested)

    def request_logout(self) -> None:
        self._logout_requested = True

    def _after_action(self) -> None:
        if self.autosave and self.system.auth.is_logged_in:
            self.system.save()

    def _user_line(self) -> str:
        user = self.system.auth.current_user
        if user is None:
            return ""
        line = f"Người dùng: {user.full_name} ({user.username}) - {user.role.label}"
        teacher = self.system.teacher_of(user)
        if teacher is not None and teacher.homeroom_class_id:
            line += f" - lớp chủ nhiệm: {self.system.classes.class_name(teacher.homeroom_class_id)}"
        return line

    def _log_error(self, exc: BaseException) -> None:
        try:
            log_exception(self.log_path.parent, exc)   # có thời điểm, tự xoay vòng file (P07, U19)
        except OSError:
            pass

    # ------------------------------------------------------------------ khởi động
    def _banner(self) -> None:
        self.io.header(f"{APP_NAME} - phiên bản {__version__}")
        self.io.info("Mẹo: nhập ! để hủy thao tác đang nhập; Enter để giữ giá trị mặc định trong [ ].")

    def initialize_if_empty(self) -> None:
        """Lần chạy đầu tiên (chưa có dữ liệu): hỏi có nạp dữ liệu mẫu không."""
        if len(self.system.auth) > 0:
            return
        if self.seed_func is not None and self.io.ask_yes_no(
                "Chưa có dữ liệu. Nạp dữ liệu mẫu (20 trẻ, 3 lớp, 5 giáo viên...) để dùng thử", default=True):
            counts = self.seed_func(self.system)
            self.io.success("Đã nạp dữ liệu mẫu: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        else:
            self.system.auth.ensure_default_admin()
            self.io.warning("Đã tạo tài khoản quản trị mặc định admin / admin123 - "
                            "bạn sẽ phải đổi mật khẩu ở lần đăng nhập đầu.")
        self.system.save()

    def _demo_hint(self) -> None:
        """L24: chỉ gợi ý tài khoản mẫu còn đúng mật khẩu mẫu (dữ liệu thật/đã đổi mật khẩu thì không hiện)."""
        auth = self.system.auth
        existing = [(u, p, d) for u, p, d in self.demo_accounts if auth.uses_password(u, p)]
        if existing:
            self.io.info("Tài khoản dùng thử (dữ liệu mẫu):")
            for username, password, description in existing:
                self.io.info(f"   {username:<10} / {password:<12} - {description}")

    def _login(self) -> User | None:
        """U10: sai mật khẩu không làm thoát chương trình; khóa tạm do AuthManager quyết định (L24)."""
        auth = self.system.auth
        self._demo_hint()
        while True:
            self.io.header("Đăng nhập")
            try:
                username = self.io.input("Tên đăng nhập (Enter để thoát, gõ dk để đăng ký tài khoản): ")
            except CancelledInput:
                return None
            if not username:
                return None
            if username.strip().lower() in ("dk", "dang ky", "đăng ký"):
                try:
                    self._register()
                except CancelledInput:
                    self.io.warning("Đã hủy đăng ký.")
                except KindergartenError as exc:
                    self.io.error(exc.message)
                continue
            password = self.io.input_password("Mật khẩu: ")
            try:
                user = auth.login(username, password)
            except AuthenticationError as exc:
                self.io.error(exc.message)
                continue
            self.io.success(f"Xin chào {user.full_name} - vai trò {user.role.label}!")
            if user.must_change_password and not self._force_password_change(password):
                auth.logout()
                self.io.warning("Chưa đổi mật khẩu nên chưa thể sử dụng hệ thống.")
                continue
            return user

    def _register(self) -> None:
        """Tự đăng ký: phụ huynh dùng được ngay; giáo viên / kế toán / nhân viên chờ Ban giám hiệu duyệt."""
        io = self.io
        io.header("Đăng ký tài khoản")
        kind = io.ask_choice("Bạn là", [("parent", "Phụ huynh có con đang học tại trường"),
                                        ("staff", "Giáo viên / Kế toán / Nhân viên của trường")])
        username = io.ask_text("Tên đăng nhập (chữ thường không dấu, số, dấu chấm)")
        password = io.input_password("Mật khẩu (ít nhất 6 ký tự): ")
        User.validate_password(password)
        if io.input_password("Nhập lại mật khẩu: ") != password:
            raise ValidationError("Hai lần nhập mật khẩu không khớp.")
        if kind == "parent":
            phone = io.ask_text("SĐT phụ huynh đã khai với trường")
            child_id = io.ask_text("Mã của con (VD: C001)")
            dob = io.ask_date("Ngày sinh của con")
            user = self.system.register_parent(username, password, phone, child_id, dob)
            io.success(f"Đăng ký thành công tài khoản {user.username}. Bạn có thể đăng nhập ngay.")
        else:
            role = io.ask_choice("Loại tài khoản", [(r, r.label) for r in (Role.TEACHER, Role.ACCOUNTANT, Role.STAFF)])
            employee_id = io.ask_text("Mã nhân sự (VD: T001, NV002)")
            phone = io.ask_text("SĐT trong hồ sơ nhân sự")
            user = self.system.register_staff(username, password, employee_id, phone, role)
            io.success(f"Đã gửi đăng ký {user.username}. Tài khoản dùng được sau khi Ban giám hiệu duyệt.")
        self._save_quietly()

    def _force_password_change(self, current_password: str) -> bool:
        """L24: tài khoản mặc định / vừa được đặt lại mật khẩu phải đổi mật khẩu trước khi dùng."""
        self.io.warning("Bạn đang dùng mật khẩu mặc định hoặc mật khẩu vừa được đặt lại - hãy đặt mật khẩu mới.")
        while True:
            try:
                new = self.io.input_password("Mật khẩu mới (ít nhất 6 ký tự, ! để hủy): ")
                if new == ConsoleIO.CANCEL_TOKEN:
                    return False
                confirm = self.io.input_password("Nhập lại mật khẩu mới: ")
                if new != confirm:
                    raise ValidationError("Hai lần nhập không khớp.")
                self.system.auth.change_password(current_password, new)
            except KindergartenError as exc:
                self.io.error(exc.message)
                continue
            self.io.success("Đã đổi mật khẩu.")
            self._save_quietly()
            return True

    # ------------------------------------------------------------------ menu chính theo vai trò
    def build_main_menu(self) -> Menu:
        user = self.system.auth.current_user
        portal = user.portal.upper() if user else ""
        P = Permission
        if user is not None and user.role is Role.PARENT:   # hệ thống phụ huynh: menu riêng
            menu = ParentScreen(self).add_items(self.new_menu(portal, exit_label="Đăng xuất"))
            return menu.add("Đổi mật khẩu", SystemScreen(self).change_password)
        reports = ReportScreen(self)
        return (self.new_menu(portal, exit_label="Đăng xuất")
                .add("Vận hành hằng ngày (đón trẻ, ăn ngủ, phụ huynh, trả trẻ)", DailyScreen(self).run,
                     P.VIEW_OPERATIONS, pause=False)
                .add("Tổng quan (Dashboard)", reports.show_dashboard, P.VIEW_DASHBOARD)
                .add("Trẻ & phụ huynh", ChildrenScreen(self).run, P.VIEW_CHILDREN, pause=False)
                .add("Sức khỏe - dị ứng", HealthScreen(self).run, P.MANAGE_HEALTH, pause=False)
                .add("Nhân sự & bảng lương", HRScreen(self).run, P.VIEW_EMPLOYEES, pause=False)
                .add("Lớp học & thời khóa biểu", ClassScreen(self).run, P.VIEW_CLASSES, pause=False)
                .add("Điểm danh", AttendanceScreen(self).run, P.TAKE_ATTENDANCE, pause=False)
                .add("Học phí & công nợ", FinanceScreen(self).run, P.MANAGE_FINANCE, pause=False)
                .add("Thực đơn & dinh dưỡng", NutritionScreen(self).run, P.VIEW_MENU, pause=False)
                .add("Báo cáo (lập, gửi BGH / nhận, duyệt)", reports.run, pause=False)
                .add("Tài khoản & hệ thống", SystemScreen(self).run, pause=False))

    def run(self) -> None:
        self._banner()
        try:
            self.initialize_if_empty()
            while True:
                if self._login() is None:
                    break
                self._logout_requested = False
                self.build_main_menu().run()
                forced = self._logout_requested  # VD: vừa nạp lại dữ liệu mẫu -> bắt buộc đăng nhập lại
                if self.system.auth.is_logged_in:
                    self.system.auth.logout()
                    self.io.success("Đã đăng xuất.")
                self._save_quietly()
                if not forced and not self.io.ask_yes_no("Đăng nhập tài khoản khác", default=False):
                    break
        except (EOFError, KeyboardInterrupt, CancelledInput):
            self.io.write("")
        finally:
            # U10: chỉ báo "Đã lưu" khi lưu thành công
            if self._save_quietly():
                self.io.info("Đã lưu dữ liệu. Tạm biệt!")
            else:
                self.io.info("Tạm biệt!")

    def _save_quietly(self) -> bool:
        if not self.autosave:
            return False
        try:
            self.system.save()
        except KindergartenError as exc:
            self.io.error(exc.message)
            return False
        return True
