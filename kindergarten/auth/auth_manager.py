"""T07 - AuthManager: đăng nhập, đăng xuất, đổi mật khẩu, check_permission()."""
from __future__ import annotations

import contextlib
import functools
from datetime import datetime, timedelta
from typing import Any, Callable, TypeVar

from ..core.base_manager import BaseManager
from ..exceptions import (AuthenticationError, DuplicateIdError, KindergartenError,
                          PermissionDeniedError, ValidationError)
from ..utils import normalize_spaces
from .user import TEACHER_DUTIES, Permission, Role, User

F = TypeVar("F", bound=Callable[..., Any])


class AuthManager(BaseManager[User]):
    entity_name = "tài khoản"
    DEFAULT_ADMIN = ("admin", "admin123")
    MAX_FAILURES = 5
    LOCK_MINUTES = 5

    def __init__(self) -> None:
        super().__init__()
        self.current_user: User | None = None
        self.elevated = False
        self._failures: dict[str, tuple[int, datetime | None]] = {}
        # Hệ thống gắn hàm xác định loại giáo viên (chủ nhiệm / bộ môn) theo hồ sơ nhân sự - xem KindergartenSystem
        self.teacher_duty_of: Callable[[User], str] | None = None

    # ------------------------------------------------------------------ kiểm tra dữ liệu
    def _validate_new(self, user: User) -> None:
        if self.find_by_username(user.username):
            raise DuplicateIdError(f"Tên đăng nhập '{user.username}' đã tồn tại.")

    def _validate_update(self, user: User) -> None:
        if any(u is not user and u.username == user.username for u in self):
            raise DuplicateIdError(f"Tên đăng nhập '{user.username}' đã tồn tại.")
        if self._active_admin_count() == 0:
            raise KindergartenError("Phải còn ít nhất một tài khoản Quản trị viên đang hoạt động.")

    def _before_remove(self, user: User) -> None:
        if user is self.current_user:
            raise KindergartenError("Không thể xóa tài khoản đang đăng nhập.")
        if user.role is Role.ADMIN and user.active and self._active_admin_count(exclude=user) == 0:
            raise KindergartenError("Phải còn ít nhất một tài khoản Quản trị viên đang hoạt động.")

    def _active_admin_count(self, exclude: User | None = None) -> int:
        return sum(1 for u in self if u is not exclude and u.active and u.role is Role.ADMIN)

    # ------------------------------------------------------------------ quản lý tài khoản
    def create_user(self, username: str, password: str, role: Any, full_name: str = "",
                    employee_id: str | None = None) -> User:
        return self.add(User(username=username, role=role, full_name=full_name,
                             password=password, employee_id=employee_id))

    def find_by_username(self, username: Any) -> User | None:
        name = normalize_spaces(username).lower()
        return self.find_one(lambda u: u.username == name)

    def ensure_default_admin(self) -> User | None:
        """Tạo tài khoản admin mặc định nếu hệ thống chưa có quản trị viên nào."""
        if any(u.role is Role.ADMIN for u in self):
            return None
        username, password = self.DEFAULT_ADMIN
        user = self.create_user(username, password, Role.ADMIN, "Quản trị hệ thống")
        user.must_change_password = True   # L24: bắt buộc đổi mật khẩu mặc định ở lần đăng nhập đầu
        return user

    def reset_password(self, user_id: str, new_password: str) -> User:
        self.check_permission(Permission.MANAGE_USERS)
        user = self.get(user_id)
        user.set_password(new_password)
        user.must_change_password = True   # L24: người dùng phải tự đặt mật khẩu mới
        self._failures.pop(user.username, None)
        return user

    def set_active(self, user_id: str, active: bool) -> User:
        self.check_permission(Permission.MANAGE_USERS)
        user = self.get(user_id)
        if not active:
            if user is self.current_user:
                raise KindergartenError("Không thể khóa tài khoản đang đăng nhập.")
            if user.role is Role.ADMIN and self._active_admin_count(exclude=user) == 0:
                raise KindergartenError("Phải còn ít nhất một tài khoản Quản trị viên đang hoạt động.")
        user.active = bool(active)
        return user

    @contextlib.contextmanager
    def elevated_scope(self):
        """Cho một bước nghiệp vụ đã kiểm tra quyền riêng (VD: nhân viên đón trẻ -> tự ghi điểm danh có mặt)
        ghi vào manager khác mà không bị chặn bởi quyền ghi của manager đó."""
        previous, self.elevated = self.elevated, True
        try:
            yield
        finally:
            self.elevated = previous

    def pending_users(self) -> list[User]:
        return self.sort("created_at", items=self.find(pending=True))

    def approve(self, user_id: str) -> User:
        """Ban giám hiệu duyệt tài khoản nhân sự tự đăng ký."""
        self.check_permission(Permission.MANAGE_USERS)
        user = self.get(user_id)
        if not user.pending:
            raise KindergartenError(f"Tài khoản {user.username} không ở trạng thái chờ duyệt.")
        user.pending = False
        user.active = True
        return user

    def find_by_parent(self, parent_id: str) -> User | None:
        key = normalize_spaces(parent_id).upper()
        return self.find_one(lambda u: u.parent_id == key)

    # ------------------------------------------------------------------ đăng nhập
    def login(self, username: str, password: str) -> User:
        """L24: đếm lần sai theo tài khoản, sai MAX_FAILURES lần thì khóa tạm LOCK_MINUTES phút
        (dùng chung cho cả console và Tkinter)."""
        name = normalize_spaces(username).lower()
        count, locked_until = self._failures.get(name, (0, None))
        now = datetime.now()
        if locked_until is not None and now < locked_until:
            minutes = max(1, int((locked_until - now).total_seconds() // 60) + 1)
            raise AuthenticationError(f"Tài khoản tạm khóa do nhập sai nhiều lần, thử lại sau {minutes} phút.")
        user = self.find_by_username(name)
        if user is None or not user.check_password(password):
            count += 1
            if count >= self.MAX_FAILURES:
                self._failures[name] = (0, now + timedelta(minutes=self.LOCK_MINUTES))
                raise AuthenticationError(f"Sai quá {self.MAX_FAILURES} lần, tài khoản tạm khóa "
                                          f"{self.LOCK_MINUTES} phút.")
            self._failures[name] = (count, None)
            raise AuthenticationError(f"Sai tên đăng nhập hoặc mật khẩu (còn {self.MAX_FAILURES - count} lần thử).")
        if user.pending:
            raise AuthenticationError("Tài khoản đang chờ Ban giám hiệu duyệt. Vui lòng thử lại sau khi được duyệt.")
        if not user.active:
            raise AuthenticationError("Tài khoản đã bị khóa, vui lòng liên hệ quản trị viên.")
        self._failures.pop(name, None)
        user.last_login = now.isoformat(timespec="seconds")
        self.current_user = user
        return user

    def uses_password(self, username: str, password: str) -> bool:
        """Tài khoản còn dùng đúng mật khẩu này không (chỉ hiện gợi ý tài khoản mẫu khi còn đúng - L24)."""
        user = self.find_by_username(username)
        return user is not None and user.active and user.check_password(password)

    def logout(self) -> None:
        self.current_user = None

    @property
    def is_logged_in(self) -> bool:
        return self.current_user is not None

    def change_password(self, old_password: str, new_password: str) -> None:
        user = self._require_login()
        if not user.check_password(old_password):
            raise AuthenticationError("Mật khẩu hiện tại không đúng.")
        if old_password == new_password:
            raise ValidationError("Mật khẩu mới phải khác mật khẩu hiện tại.")
        user.set_password(new_password)
        user.must_change_password = False

    # ------------------------------------------------------------------ phân quyền
    def teacher_duty(self, user: User | None) -> str:
        """'chu_nhiem' / 'bo_mon' cho tài khoản giáo viên (tính theo hồ sơ hiện tại), '' cho vai trò khác."""
        if user is None or user.role is not Role.TEACHER or self.teacher_duty_of is None:
            return ""
        return self.teacher_duty_of(user)

    def permissions_of(self, user: User | None) -> frozenset[Permission]:
        """Quyền thực tế: quyền của vai trò + quyền theo loại giáo viên (chủ nhiệm / bộ môn)."""
        if user is None:
            return frozenset()
        permissions = user.permissions
        duty = self.teacher_duty(user)
        if permissions and duty in TEACHER_DUTIES:
            permissions = permissions | TEACHER_DUTIES[duty][1]
        return permissions

    def role_label(self, user: User | None) -> str:
        duty = self.teacher_duty(user)
        if duty in TEACHER_DUTIES:
            return TEACHER_DUTIES[duty][0]
        return user.role.label if user is not None else ""

    def portal_of(self, user: User) -> str:
        duty = self.teacher_duty(user)
        if duty in TEACHER_DUTIES:
            return f"{user.role.portal} - {'Chủ nhiệm' if duty == 'chu_nhiem' else 'Bộ môn'}"
        return user.portal

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions_of(self.current_user)

    def check_permission(self, permission: Permission) -> None:
        """Ném PermissionDeniedError nếu chưa đăng nhập hoặc vai trò không có quyền."""
        user = self._require_login()
        if permission not in self.permissions_of(user):
            raise PermissionDeniedError(
                f"Vai trò '{self.role_label(user)}' không có quyền: {permission.value.lower()}.")

    def _require_login(self) -> User:
        if self.current_user is None:
            raise PermissionDeniedError("Bạn cần đăng nhập để sử dụng chức năng này.")
        return self.current_user


def require_permission(permission: Permission) -> Callable[[F], F]:
    """Decorator: kiểm tra quyền trước khi chạy phương thức (đối tượng cần có thuộc tính `auth`)."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            self.auth.check_permission(permission)
            return func(self, *args, **kwargs)

        wrapper.required_permission = permission  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
