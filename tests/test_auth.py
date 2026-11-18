"""Kiểm thử Role/User (T06) và AuthManager (T07)."""
import pytest

from kindergarten.auth.auth_manager import AuthManager, require_permission
from kindergarten.auth.user import ROLE_PERMISSIONS, TEACHER_DUTIES, Permission, Role, User
from kindergarten.exceptions import (AuthenticationError, DuplicateIdError, KindergartenError,
                                     PermissionDeniedError, ValidationError)


@pytest.fixture
def auth():
    manager = AuthManager()
    manager.create_user("admin", "admin123", Role.ADMIN)
    manager.create_user("ketoan", "ketoan123", Role.ACCOUNTANT)
    manager.create_user("gv.hoa", "giaovien123", Role.TEACHER)
    return manager


def test_five_roles_with_different_permissions():
    """5 phân hệ: Ban giám hiệu (cao nhất), Giáo viên, Kế toán, Nhân viên, Phụ huynh."""
    assert {r.label for r in Role} == {"Ban giám hiệu (Quản trị)", "Giáo viên", "Kế toán", "Nhân viên", "Phụ huynh"}
    assert ROLE_PERMISSIONS[Role.ADMIN] == frozenset(Permission) - {Permission.PARENT_PORTAL,
                                                                     Permission.SUBMIT_REPORTS}
    assert ROLE_PERMISSIONS[Role.PARENT] == {Permission.PARENT_PORTAL}
    # mỗi phân hệ chỉ giữ chức năng đúng nhiệm vụ
    assert ROLE_PERMISSIONS[Role.ACCOUNTANT] == {Permission.MANAGE_FINANCE, Permission.MANAGE_SERVICES,
                                                 Permission.VIEW_FINANCE_REPORTS, Permission.VIEW_EMPLOYEES,
                                                 Permission.VIEW_PAYROLL, Permission.SUBMIT_REPORTS}
    assert ROLE_PERMISSIONS[Role.STAFF] == {Permission.SUBMIT_REPORTS}   # còn lại theo công việc (bếp, bảo vệ, y tế)
    kitchen = User("nv.bep", Role.STAFF, password="abcdef", duty="bep")
    guard = User("nv.baove", Role.STAFF, password="abcdef", duty="bao_ve")
    assert kitchen.has_permission(Permission.MANAGE_MENU) and not kitchen.has_permission(Permission.CHECK_IN_OUT)
    assert guard.has_permission(Permission.CHECK_IN_OUT) and not guard.has_permission(Permission.VIEW_MENU)
    assert "Bếp" in kitchen.portal
    # giáo viên: phần chung + phần riêng theo loại (chủ nhiệm / bộ môn)
    homeroom, subject = TEACHER_DUTIES["chu_nhiem"][1], TEACHER_DUTIES["bo_mon"][1]
    assert {Permission.DAILY_LOG, Permission.TAKE_ATTENDANCE, Permission.CHECK_IN_OUT} <= homeroom
    assert Permission.TEACH_SUBJECT not in homeroom
    assert subject == {Permission.TEACH_SUBJECT}
    assert Permission.DAILY_LOG not in ROLE_PERMISSIONS[Role.TEACHER] | subject
    assert Permission.MANAGE_FINANCE in ROLE_PERMISSIONS[Role.ACCOUNTANT]
    assert Permission.MANAGE_FINANCE not in ROLE_PERMISSIONS[Role.TEACHER] | homeroom | subject
    assert Role.parse("Giáo viên") is Role.TEACHER


def test_password_is_hashed_with_salt(auth):
    user = auth.find_by_username("admin")
    assert "admin123" not in user.password_hash
    assert user.password_hash.startswith("pbkdf2_sha256$")
    other = User("admin2", Role.ADMIN, password="admin123")
    assert other.password_hash != user.password_hash  # salt ngẫu nhiên khác nhau
    assert user.check_password("admin123") and not user.check_password("sai")


def test_login_logout(auth):
    with pytest.raises(AuthenticationError):
        auth.login("admin", "sai-mat-khau")
    with pytest.raises(AuthenticationError):
        auth.login("khong.ton.tai", "admin123")
    user = auth.login("ADMIN", "admin123")
    assert auth.current_user is user and user.last_login
    auth.logout()
    assert not auth.is_logged_in


def test_change_password(auth):
    auth.login("gv.hoa", "giaovien123")
    with pytest.raises(AuthenticationError):
        auth.change_password("sai", "matkhaumoi")
    with pytest.raises(ValidationError):
        auth.change_password("giaovien123", "123")
    auth.change_password("giaovien123", "matkhaumoi")
    auth.logout()
    assert auth.login("gv.hoa", "matkhaumoi").username == "gv.hoa"


def test_check_permission_by_role(auth):
    with pytest.raises(PermissionDeniedError):
        auth.check_permission(Permission.VIEW_CHILDREN)  # chưa đăng nhập
    auth.login("gv.hoa", "giaovien123")
    auth.check_permission(Permission.VIEW_CHILDREN)
    with pytest.raises(PermissionDeniedError):
        auth.check_permission(Permission.MANAGE_FINANCE)
    with pytest.raises(PermissionDeniedError):   # chưa biết là GV chủ nhiệm hay bộ môn -> chỉ có quyền chung
        auth.check_permission(Permission.TAKE_ATTENDANCE)
    auth.teacher_duty_of = lambda _user: "chu_nhiem"
    auth.check_permission(Permission.TAKE_ATTENDANCE)
    assert not auth.has_permission(Permission.TEACH_SUBJECT)
    auth.teacher_duty_of = lambda _user: "bo_mon"
    assert auth.has_permission(Permission.TEACH_SUBJECT) and not auth.has_permission(Permission.TAKE_ATTENDANCE)
    auth.logout()
    auth.login("ketoan", "ketoan123")
    auth.check_permission(Permission.MANAGE_FINANCE)
    assert not auth.has_permission(Permission.MANAGE_USERS)


def test_require_permission_decorator(auth):
    class Service:
        def __init__(self, manager):
            self.auth = manager

        @require_permission(Permission.MANAGE_USERS)
        def secret(self):
            return "ok"

    service = Service(auth)
    auth.login("ketoan", "ketoan123")
    with pytest.raises(PermissionDeniedError):
        service.secret()
    auth.logout()
    auth.login("admin", "admin123")
    assert service.secret() == "ok"


def test_account_rules(auth):
    with pytest.raises(DuplicateIdError):
        auth.create_user("Admin", "abcdef", Role.TEACHER)
    with pytest.raises(ValidationError):
        auth.create_user("tên có dấu", "abcdef", Role.TEACHER)
    auth.login("admin", "admin123")
    teacher = auth.find_by_username("gv.hoa")
    auth.set_active(teacher.id, False)
    auth.logout()
    with pytest.raises(AuthenticationError):
        auth.login("gv.hoa", "giaovien123")
    auth.login("admin", "admin123")
    with pytest.raises(KindergartenError):
        auth.remove(auth.current_user.id)  # không thể tự xóa tài khoản đang đăng nhập
