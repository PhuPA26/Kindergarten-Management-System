"""T06 - Vai trò (Role), quyền (Permission) và tài khoản người dùng (User).

Hệ thống có 5 loại tài khoản, mỗi loại mở một hệ thống con riêng sau khi đăng nhập:
Ban giám hiệu (quản trị - quyền cao nhất), Giáo viên, Kế toán, Nhân viên, Phụ huynh.
Mật khẩu không lưu dạng rõ mà lưu chuỗi băm PBKDF2-SHA256 (hashlib) kèm salt ngẫu nhiên.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from ..core.base_model import BaseModel
from ..exceptions import ValidationError
from ..utils import normalize_spaces, normalize_text


class Role(Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    ACCOUNTANT = "accountant"
    STAFF = "staff"
    PARENT = "parent"

    @property
    def label(self) -> str:
        return _ROLE_LABELS[self]

    @property
    def portal(self) -> str:
        """Tên hệ thống con (cổng) mở ra sau khi đăng nhập."""
        return _ROLE_PORTALS[self]

    @property
    def is_internal(self) -> bool:
        """Nhân sự của trường (khác phụ huynh)."""
        return self is not Role.PARENT

    @classmethod
    def parse(cls, value: Any) -> "Role":
        if isinstance(value, cls):
            return value
        text = normalize_text(value)
        aliases = {
            "1": cls.ADMIN, "admin": cls.ADMIN, "quan tri": cls.ADMIN, "quan tri vien": cls.ADMIN,
            "bgh": cls.ADMIN, "ban giam hieu": cls.ADMIN, "ban giam hieu (quan tri)": cls.ADMIN,
            "2": cls.TEACHER, "teacher": cls.TEACHER, "giao vien": cls.TEACHER, "gv": cls.TEACHER,
            "3": cls.ACCOUNTANT, "accountant": cls.ACCOUNTANT, "ke toan": cls.ACCOUNTANT,
            "4": cls.STAFF, "staff": cls.STAFF, "nhan vien": cls.STAFF, "nv": cls.STAFF,
            "5": cls.PARENT, "parent": cls.PARENT, "phu huynh": cls.PARENT, "ph": cls.PARENT,
        }
        if text in aliases:
            return aliases[text]
        raise ValidationError(f"Vai trò '{value}' không hợp lệ (Ban giám hiệu/Giáo viên/Kế toán/Nhân viên/Phụ huynh).")


_ROLE_LABELS = {Role.ADMIN: "Ban giám hiệu (Quản trị)", Role.TEACHER: "Giáo viên", Role.ACCOUNTANT: "Kế toán",
                Role.STAFF: "Nhân viên", Role.PARENT: "Phụ huynh"}
_ROLE_PORTALS = {Role.ADMIN: "Hệ thống Ban giám hiệu", Role.TEACHER: "Hệ thống Giáo viên",
                 Role.ACCOUNTANT: "Hệ thống Kế toán", Role.STAFF: "Hệ thống Nhân viên",
                 Role.PARENT: "Hệ thống Phụ huynh"}


class Permission(Enum):
    MANAGE_USERS = "Quản lý tài khoản, duyệt tài khoản đăng ký"
    MANAGE_DATA = "Lưu, sao lưu, nạp dữ liệu"
    VIEW_DASHBOARD = "Xem tổng quan của trường"
    VIEW_CHILDREN = "Xem hồ sơ trẻ và phụ huynh"
    MANAGE_CHILDREN = "Thêm/sửa/xóa hồ sơ trẻ và phụ huynh"
    MANAGE_HEALTH = "Quản lý sức khỏe (cân đo, dị ứng)"
    VIEW_EMPLOYEES = "Xem hồ sơ nhân sự"
    MANAGE_EMPLOYEES = "Thêm/sửa/xóa nhân sự"
    VIEW_PAYROLL = "Xem bảng lương"
    VIEW_CLASSES = "Xem lớp học, thời khóa biểu"
    MANAGE_CLASSES = "Quản lý lớp học, xếp lớp, thời khóa biểu"
    MANAGE_CALENDAR = "Quản lý lịch năm học, ngày nghỉ lễ"
    TAKE_ATTENDANCE = "Điểm danh, ghi đơn xin nghỉ"
    CHECK_IN_OUT = "Đón trẻ đầu ngày, trả trẻ cuối ngày"
    DAILY_LOG = "Cập nhật ăn, ngủ, sinh hoạt của trẻ"
    PARENT_CONTACT = "Trao đổi với phụ huynh (lời nhắn, dặn thuốc, xin nghỉ, thông báo)"
    VIEW_OPERATIONS = "Theo dõi vận hành trong ngày, báo cáo cuối ngày"
    MANAGE_FINANCE = "Quản lý học phí, hóa đơn, thanh toán"
    MANAGE_SERVICES = "Quản lý danh mục dịch vụ, đăng ký dịch vụ cho trẻ"
    VIEW_MENU = "Xem thực đơn"
    MANAGE_MENU = "Lập thực đơn, quản lý món ăn"
    VIEW_FINANCE_REPORTS = "Xem báo cáo doanh thu, công nợ"
    SUBMIT_REPORTS = "Lập báo cáo, ghi chú và gửi Ban giám hiệu"
    REVIEW_REPORTS = "Nhận, xem, duyệt / yêu cầu bổ sung báo cáo"
    PARENT_PORTAL = "Theo dõi con, nhắn giáo viên, dặn thuốc, xin nghỉ, đăng ký dịch vụ"
    TEACH_SUBJECT = "Ghi sổ tiết dạy bộ môn, nhận xét trẻ theo môn học"


# Mỗi phân hệ CHỈ giữ chức năng đúng nhiệm vụ của mình (không còn "thấy hết nhưng bị khóa nút").
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    # Ban giám hiệu: quyền cao nhất - mọi chức năng nội bộ, nhận và duyệt báo cáo của các bộ phận
    Role.ADMIN: frozenset(p for p in Permission if p not in (Permission.PARENT_PORTAL, Permission.SUBMIT_REPORTS)),
    # Giáo viên (phần chung): xem lớp mình phụ trách, thời khóa biểu, hồ sơ trẻ, gửi báo cáo.
    # Phần còn lại tùy loại giáo viên - xem TEACHER_DUTIES.
    Role.TEACHER: frozenset({Permission.VIEW_CHILDREN, Permission.VIEW_CLASSES, Permission.SUBMIT_REPORTS}),
    # Kế toán: chỉ tiền - học phí, thu chi, công nợ, dịch vụ, bảng lương, báo cáo tài chính
    Role.ACCOUNTANT: frozenset({
        Permission.MANAGE_FINANCE, Permission.MANAGE_SERVICES, Permission.VIEW_FINANCE_REPORTS,
        Permission.VIEW_EMPLOYEES, Permission.VIEW_PAYROLL, Permission.SUBMIT_REPORTS,
    }),
    # Nhân viên: quyền theo công việc cụ thể (xem STAFF_DUTIES) + gửi báo cáo công việc
    Role.STAFF: frozenset({Permission.SUBMIT_REPORTS}),
    Role.PARENT: frozenset({Permission.PARENT_PORTAL}),
}

# Công việc của nhân viên -> (tên hiển thị, quyền thêm). Lấy theo chức vụ trong hồ sơ nhân sự.
STAFF_DUTIES: dict[str, tuple[str, frozenset[Permission]]] = {
    "bep": ("Bếp - cấp dưỡng", frozenset({Permission.VIEW_MENU, Permission.MANAGE_MENU})),
    "bao_ve": ("Bảo vệ - đón trả trẻ ở cổng", frozenset({Permission.CHECK_IN_OUT})),
    "y_te": ("Y tế - sức khỏe trẻ", frozenset({Permission.MANAGE_HEALTH})),
    "": ("Nhân viên", frozenset()),
}

# Hai loại giáo viên -> (tên hiển thị, quyền thêm). Xác định theo hồ sơ: có lớp chủ nhiệm = GV chủ nhiệm.
TEACHER_DUTIES: dict[str, tuple[str, frozenset[Permission]]] = {
    # GV chủ nhiệm: chăm sóc - nuôi dưỡng trẻ LỚP MÌNH cả ngày, trao đổi với phụ huynh, báo cáo lớp
    "chu_nhiem": ("Giáo viên chủ nhiệm", frozenset({
        Permission.VIEW_OPERATIONS, Permission.CHECK_IN_OUT, Permission.TAKE_ATTENDANCE, Permission.DAILY_LOG,
        Permission.PARENT_CONTACT, Permission.MANAGE_HEALTH, Permission.VIEW_MENU})),
    # GV bộ môn (Âm nhạc, Tiếng Anh...): dạy theo tiết ở nhiều lớp - ghi sổ tiết dạy, nhận xét trẻ theo môn,
    # báo cáo chuyên môn. KHÔNG đón trả, điểm danh, ăn ngủ, sức khỏe, dặn thuốc (việc của GV chủ nhiệm).
    "bo_mon": ("Giáo viên bộ môn", frozenset({Permission.TEACH_SUBJECT})),
}


def duty_from_position(position: str) -> str:
    text = normalize_text(position)
    if "cap duong" in text or "bep" in text or "nau" in text:
        return "bep"
    if "bao ve" in text:
        return "bao_ve"
    if "y te" in text or "y ta" in text:
        return "y_te"
    return ""

class User(BaseModel):
    """Tài khoản đăng nhập hệ thống."""

    PREFIX = "TK"
    HASH_ALGORITHM: ClassVar[str] = "pbkdf2_sha256"
    HASH_ITERATIONS: ClassVar[int] = 120_000
    MIN_PASSWORD_LENGTH: ClassVar[int] = 6
    _USERNAME_PATTERN = re.compile(r"^[a-z0-9_.]{3,30}$")

    def __init__(self, username: str, role: Any, full_name: str = "", password: str | None = None,
                 password_hash: str = "", employee_id: str | None = None, active: bool = True,
                 created_at: str | None = None, last_login: str | None = None,
                 must_change_password: bool = False, parent_id: str | None = None, pending: bool = False,
                 phone: str = "", duty: str = "", id: str | None = None) -> None:
        super().__init__(id)
        self.username = username
        self.role = role
        self.full_name = full_name
        self.employee_id = employee_id
        self.parent_id = (normalize_spaces(parent_id).upper() or None) if parent_id else None   # tài khoản phụ huynh
        self.pending = bool(pending)   # tự đăng ký, chờ Ban giám hiệu duyệt
        self.duty = duty if duty in STAFF_DUTIES else ""   # công việc của nhân viên (bếp, bảo vệ, y tế)
        self.phone = normalize_spaces(phone)
        self.active = bool(active)
        self.must_change_password = bool(must_change_password)   # L24
        self.created_at = created_at or datetime.now().isoformat(timespec="seconds")
        self.last_login = last_login
        self._password_hash = password_hash
        if password is not None:
            self.set_password(password)
        elif not password_hash:
            raise ValidationError("Tài khoản phải có mật khẩu.")

    # ------------------------------------------------------------------ thuộc tính
    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: Any) -> None:
        text = normalize_spaces(value).lower()
        if not self._USERNAME_PATTERN.match(text):
            raise ValidationError("Tên đăng nhập dài 3–30 ký tự, chỉ gồm chữ thường không dấu, "
                                  "số, dấu chấm hoặc gạch dưới.")
        self._username = text

    @property
    def role(self) -> Role:
        return self._role

    @role.setter
    def role(self, value: Any) -> None:
        self._role = Role.parse(value)

    @property
    def full_name(self) -> str:
        return self._full_name

    @full_name.setter
    def full_name(self, value: Any) -> None:
        self._full_name = normalize_spaces(value) or self._username

    @property
    def employee_id(self) -> str | None:
        return self._employee_id

    @employee_id.setter
    def employee_id(self, value: Any) -> None:
        text = normalize_spaces(value).upper() if value else ""
        self._employee_id = text or None

    @property
    def password_hash(self) -> str:
        return self._password_hash

    # ------------------------------------------------------------------ mật khẩu
    @classmethod
    def hash_password(cls, password: str, salt: str | None = None, iterations: int | None = None) -> str:
        salt = salt or secrets.token_hex(16)
        iterations = iterations or cls.HASH_ITERATIONS
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
        return f"{cls.HASH_ALGORITHM}${iterations}${salt}${digest.hex()}"

    @classmethod
    def validate_password(cls, password: Any) -> str:
        if not isinstance(password, str) or len(password) < cls.MIN_PASSWORD_LENGTH:
            raise ValidationError(f"Mật khẩu phải có ít nhất {cls.MIN_PASSWORD_LENGTH} ký tự.")
        if password.strip() != password:
            raise ValidationError("Mật khẩu không được bắt đầu hoặc kết thúc bằng khoảng trắng.")
        return password

    def set_password(self, password: str) -> None:
        self._password_hash = self.hash_password(self.validate_password(password))

    def check_password(self, password: Any) -> bool:
        try:
            algorithm, iterations, salt, _digest = self._password_hash.split("$")
            candidate = self.hash_password(str(password), salt, int(iterations))
        except (ValueError, TypeError):
            return False
        if algorithm != self.HASH_ALGORITHM:
            return False
        return hmac.compare_digest(candidate, self._password_hash)

    # ------------------------------------------------------------------ phân quyền
    @property
    def permissions(self) -> frozenset[Permission]:
        if not self.active or self.pending:
            return frozenset()
        if self.role is Role.STAFF:
            return ROLE_PERMISSIONS[Role.STAFF] | STAFF_DUTIES[self.duty][1]
        return ROLE_PERMISSIONS[self.role]

    @property
    def portal(self) -> str:
        """Tên hệ thống con hiển thị sau khi đăng nhập (nhân viên ghi rõ công việc)."""
        if self.role is Role.STAFF and self.duty:
            return f"{self.role.portal} - {STAFF_DUTIES[self.duty][0]}"
        return self.role.portal

    @property
    def status_text(self) -> str:
        if self.pending:
            return "Chờ duyệt"
        return "Hoạt động" if self.active else "Đã khóa"

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    # ------------------------------------------------------------------ lưu trữ
    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(username=self.username, full_name=self.full_name, role=self.role.value,
                    password_hash=self.password_hash, employee_id=self.employee_id,
                    active=self.active, created_at=self.created_at, last_login=self.last_login,
                    must_change_password=self.must_change_password, parent_id=self.parent_id,
                    pending=self.pending, phone=self.phone, duty=self.duty)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        return cls(username=data["username"], role=data["role"], full_name=data.get("full_name", ""),
                   password_hash=data["password_hash"], employee_id=data.get("employee_id"),
                   active=data.get("active", True), created_at=data.get("created_at"),
                   last_login=data.get("last_login"),
                   must_change_password=data.get("must_change_password", False),
                   parent_id=data.get("parent_id"), pending=data.get("pending", False), phone=data.get("phone", ""),
                   duty=data.get("duty", ""),
                   id=data["id"])

    def __str__(self) -> str:
        return f"{self.username} ({self.role.label})"
