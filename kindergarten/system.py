"""KindergartenSystem - ghép tất cả các manager thành một hệ thống (mẫu Facade).

Các manager nhận phụ thuộc qua constructor (Dependency Injection) và đăng ký sự kiện xóa
lẫn nhau để dữ liệu luôn nhất quán (xóa trẻ -> lớp, phụ huynh, sức khỏe, điểm danh tự cập nhật).

Sau rà soát:
- L10/K01: mọi manager được gắn AuthManager + quyền ghi; có người đăng nhập thì thao tác ghi bị kiểm tra
  quyền ở tầng nghiệp vụ, nên console và Tkinter không thể lệch nhau.
- L08: phạm vi của giáo viên = lớp chủ nhiệm + các lớp có tiết dạy; thiếu thông tin thì trả về rỗng.
- L06: xác nhận người đón bắt buộc trẻ có mặt, so đúng họ tên có dấu, ghi giờ đón và nhật ký.
- K06: nhật ký thao tác audit.jsonl.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from .applog import AuditLog
from .attendance.attendance_manager import AttendanceManager
from .auth.auth_manager import AuthManager
from .auth.user import Permission, Role, User, duty_from_position
from .classroom.class_manager import ClassManager
from .classroom.classroom import Classroom
from .classroom.timetable import Timetable
from .core.base_model import BaseModel
from .core.person import Employee
from .exceptions import (DuplicateIdError, KindergartenError, NotFoundError, PermissionDeniedError,
                         ValidationError)
from .finance.invoice import Payment
from .finance.invoice_manager import InvoiceManager
from .finance.settings import FeeSettings
from .health.health_manager import HealthManager
from .hr.employee_manager import EmployeeManager
from .hr.employees import Teacher
from .nutrition.menu_manager import MenuManager
from .people.child import Child, PickupPerson
from .people.managers import ChildManager, ParentManager
from .daily.daily_manager import DailyManager
from .teaching.lesson_log import LessonLogManager
from .reports.dashboard import Dashboard
from .reports.submissions import ReportCenter
from .school_calendar import SchoolCalendar
from .storage.datastore import DataStore
from .utils import format_date, normalize_phone, normalize_spaces, parse_date


class KindergartenSystem:
    def __init__(self, data_dir: str | Path = "data", settings: FeeSettings | None = None, store: Any = None) -> None:
        """store: nơi lưu dữ liệu - SQLiteDataStore (chương trình chính) hoặc DataStore JSON (kiểm thử, ngoại tuyến)."""
        self.store = store if store is not None else DataStore(data_dir)
        if getattr(self.store, "backend", "json") == "sqlite":
            from .storage.sqlite_store import SQLiteAuditLog
            self.audit_log = SQLiteAuditLog(self.store)
        else:
            self.audit_log = AuditLog(Path(data_dir) / "audit.jsonl")
        self._build(settings or FeeSettings())

    def _build(self, settings: FeeSettings) -> None:
        self.settings = settings
        self.calendar = SchoolCalendar()
        self.auth = AuthManager()
        self.children = ChildManager()
        self.parents = ParentManager(self.children)
        self.employees = EmployeeManager()
        self.health = HealthManager(self.children)
        self.classes = ClassManager(self.children, self.employees)
        self.timetable = Timetable(self.classes, self.employees)
        self.attendance = AttendanceManager(self.children, self.classes, self.calendar)
        self.invoices = InvoiceManager(self.children, self.parents, self.classes, self.attendance, self.settings)
        self.menus = MenuManager(self.health, self.children, self.classes, self.calendar)
        self.daily = DailyManager(self)   # vận hành hằng ngày: đón trẻ, ăn ngủ, trao đổi phụ huynh, trả trẻ
        self.reports = ReportCenter(self)   # báo cáo các bộ phận gửi Ban giám hiệu
        # liên kết tra cứu chéo (L11, L12)
        self.children.class_lookup = self.classes.get_or_none
        self.children.parent_lookup = self.parents.get_or_none
        # phạm vi giáo viên ở tầng nghiệp vụ (L08)
        self.attendance.class_guard = self.ensure_class_access
        self.health.child_guard = self.ensure_child_access
        self.employees.on_remove(self._on_employee_removed)
        self.auth.teacher_duty_of = self.teacher_duty   # GV chủ nhiệm / GV bộ môn có quyền khác nhau
        self.lessons = LessonLogManager(self)   # sổ tiết dạy bộ môn (việc riêng của GV bộ môn)
        self._bind_permissions()
        self.apply_salary_settings()

    def _bind_permissions(self) -> None:
        P = Permission
        mapping = [
            (self.auth, P.MANAGE_USERS), (self.children, P.MANAGE_CHILDREN), (self.parents, P.MANAGE_CHILDREN),
            (self.employees, P.MANAGE_EMPLOYEES), (self.health.records, P.MANAGE_HEALTH),
            (self.health.allergies, P.MANAGE_HEALTH), (self.daily.logs, P.DAILY_LOG),
            (self.classes, P.MANAGE_CLASSES), (self.timetable, P.MANAGE_CLASSES),
            (self.attendance, P.TAKE_ATTENDANCE), (self.attendance.leave_requests, P.TAKE_ATTENDANCE),
            (self.invoices, P.MANAGE_FINANCE), (self.menus, P.MANAGE_MENU), (self.menus.meals, P.MANAGE_MENU),
            (self.lessons, P.TEACH_SUBJECT),
        ]
        for manager, permission in mapping:
            manager.write_permission = permission
            manager.bind_auth(self.auth)
        for manager, label in ((self.children, "trẻ"), (self.parents, "phụ huynh"), (self.employees, "nhân sự"),
                               (self.classes, "lớp"), (self.invoices, "hóa đơn"), (self.auth, "tài khoản")):
            manager.on_remove(lambda item, label=label: self.audit(f"Xóa {label}", str(item)))

    def apply_salary_settings(self) -> None:
        """K07: tham số lương lấy từ cấu hình."""
        Teacher.configure(self.settings.base_salary_unit, self.settings.teacher_incentive_rate,
                          self.settings.homeroom_allowance)

    def reset(self, settings: FeeSettings | None = None) -> None:
        """Xóa toàn bộ dữ liệu trong bộ nhớ (dùng trước khi nạp file hoặc nạp dữ liệu mẫu)."""
        BaseModel.reset_counters()
        self._build(settings or FeeSettings())

    def after_load(self) -> None:
        self.attendance.calendar = self.calendar
        self.menus.calendar = self.calendar
        self.daily.rebuild_index()
        for user in self.auth:   # dữ liệu cũ: tài khoản nhân viên nhận công việc theo chức vụ trong hồ sơ
            if user.role is Role.STAFF and not user.duty and user.employee_id:
                employee = self.employees.get_or_none(user.employee_id)
                if employee is not None:
                    user.duty = duty_from_position(employee.position)
        self.parents.sync_links()
        self.classes.sync_links()
        self.apply_salary_settings()

    # ------------------------------------------------------------------ lưu trữ (T30)
    def save(self) -> Path:
        return self.store.save_all(self)

    def load(self) -> bool:
        return self.store.load_all(self)

    def reload_keep_session(self) -> bool:
        """Làm việc nhóm: tải lại dữ liệu mới nhất từ CSDL (người khác vừa lưu) mà vẫn giữ người đang đăng nhập.
        Trả về False nếu tài khoản đang dùng đã bị người khác khóa / xóa (phải đăng nhập lại)."""
        user = self.auth.current_user
        elevated = getattr(self.auth, "elevated", False)
        self.store.load_all(self)
        if user is None:
            return True
        again = self.auth.find_by_username(user.username)
        if again is None or not again.active:
            return False
        self.auth.current_user = again
        self.auth.elevated = elevated
        return True

    def backup(self) -> Path:
        self.save()
        path = self.store.backup()
        self.audit("Sao lưu dữ liệu", path.name)
        return path

    def restore_backup(self, name: str) -> Path:
        """P07: khôi phục từ bản sao lưu (hiện trạng được tự sao lưu trước)."""
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.MANAGE_DATA)
        user = self.username
        path = self.store.restore(name, self)
        self.audit("Khôi phục dữ liệu", name, {"by": user})
        return path

    # ------------------------------------------------------------------ nhật ký (K06)
    @property
    def username(self) -> str:
        return self.auth.current_user.username if self.auth.current_user else ""

    def audit(self, action: str, target: str = "", detail: Any = None) -> None:
        self.audit_log.write(self.username, action, target, detail)

    # ------------------------------------------------------------------ nghiệp vụ liên module
    def enroll_new_child(self, parent_ids: list[str] | None = None, class_id: str | None = None,
                         **child_data: Any) -> Child:
        """Tiếp nhận trẻ mới: kiểm tra hết trước, ghi sau; lỗi ở bước sau thì gỡ phần đã ghi (L23)."""
        parents = [self.parents.get(pid) for pid in parent_ids or []]
        classroom = self.classes.get(class_id) if class_id else None
        child = Child(**child_data)
        if classroom is not None:
            classroom.check_can_accept(child)
        self.children.add(child)
        try:
            for parent in parents:
                self.parents.link(parent.id, child.id)
            if classroom is not None:
                self.classes.enroll(child.id, classroom.id)
        except Exception:
            for parent in parents:
                parent.remove_child_id(child.id)
            if child.class_id and self.classes.exists(child.class_id):
                self.classes.get(child.class_id).drop_child_id(child.id)
            self.children.remove(child.id)
            raise
        self.audit("Tiếp nhận trẻ", str(child), {"class": class_id, "parents": parent_ids or []})
        return child

    def withdraw_child(self, child_id: str, status: str = "Đã nghỉ", on_date: Any = None) -> Child:
        """L14: cho thôi học / ra trường thay vì xóa cứng hồ sơ."""
        child = self.classes.withdraw(child_id, status, on_date)
        self.audit(f"Trẻ {status.lower()}", str(child))
        return child

    def create_user(self, username: str, password: str, role: Any, full_name: str = "",
                    employee_id: str | None = None, parent_id: str | None = None) -> User:
        """Tạo tài khoản; tài khoản giáo viên BẮT BUỘC liên kết hồ sơ giáo viên (L08),
        tài khoản phụ huynh BẮT BUỘC liên kết hồ sơ phụ huynh."""
        role = Role.parse(role)
        if role is Role.PARENT:
            if self.auth.current_user is not None:
                self.auth.check_permission(Permission.MANAGE_USERS)
            parent = self.parents.get(parent_id) if parent_id else None
            if parent is None:
                raise ValidationError("Tài khoản phụ huynh phải liên kết với một hồ sơ phụ huynh.")
            if self.auth.find_by_parent(parent.id):
                raise DuplicateIdError(f"Phụ huynh {parent.full_name} đã có tài khoản.")
            user = self.auth.add(User(username=username, role=Role.PARENT, password=password,
                                      full_name=full_name or f"{parent.relationship} {parent.full_name}",
                                      parent_id=parent.id, phone=parent.phone))
            self.audit("Tạo tài khoản", str(user))
            return user
        if role is Role.STAFF and employee_id and isinstance(self.employees.get(employee_id), Teacher):
            raise ValidationError("Giáo viên dùng loại tài khoản Giáo viên.")
        if role is Role.TEACHER and not employee_id:
            raise ValidationError("Tài khoản giáo viên phải liên kết với một hồ sơ giáo viên.")
        if employee_id:
            employee = self.employees.get(employee_id)
            if role is Role.TEACHER and not isinstance(employee, Teacher):
                raise ValidationError("Tài khoản giáo viên phải liên kết với hồ sơ giáo viên.")
            if any(u.employee_id == employee.id for u in self.auth):
                raise DuplicateIdError(f"{employee} đã có tài khoản.")
            full_name = full_name or employee.full_name
            employee_id = employee.id
        user = self.auth.create_user(username, password, role, full_name, employee_id)
        if role is Role.STAFF and employee_id:   # quyền nhân viên theo công việc trong hồ sơ (bếp, bảo vệ, y tế)
            user.duty = duty_from_position(self.employees.get(employee_id).position)
        self.audit("Tạo tài khoản", str(user))
        return user

    # ------------------------------------------------------------------ tự đăng ký tài khoản
    def register_parent(self, username: str, password: str, phone: str, child_id: str, child_dob: Any) -> User:
        """Phụ huynh tự đăng ký: SĐT phải có trong hồ sơ phụ huynh và khớp mã + ngày sinh của con.
        Đúng thông tin thì tài khoản dùng được ngay."""
        parent = self.parents.find_by_phone(phone)
        child = self.children.get_or_none(normalize_spaces(child_id).upper())
        try:
            dob = parse_date(child_dob, "Ngày sinh của con")
        except ValidationError:
            dob = None
        if parent is None or child is None or not parent.has_child(child.id) or child.dob != dob:
            raise ValidationError("Thông tin không khớp hồ sơ của trường (SĐT phụ huynh, mã trẻ, ngày sinh của trẻ). "
                                  "Hãy liên hệ giáo viên chủ nhiệm để cập nhật hồ sơ.")
        if self.auth.find_by_parent(parent.id):
            raise DuplicateIdError(f"Phụ huynh {parent.full_name} đã có tài khoản. Nếu quên mật khẩu, "
                                   "hãy nhờ Ban giám hiệu đặt lại.")
        user = User(username=username, role=Role.PARENT, full_name=f"{parent.relationship} {parent.full_name}",
                    password=password, parent_id=parent.id, phone=parent.phone)
        self.auth.add(user)
        self.audit("Phụ huynh tự đăng ký", user.username, {"parent": parent.id})
        return user

    def register_staff(self, username: str, password: str, employee_id: str, phone: str, role: Any) -> User:
        """Nhân sự tự đăng ký bằng mã nhân sự + SĐT trong hồ sơ; tài khoản chờ Ban giám hiệu duyệt."""
        role = Role.parse(role)
        if role in (Role.ADMIN, Role.PARENT):
            raise ValidationError("Chỉ đăng ký được tài khoản Giáo viên, Kế toán hoặc Nhân viên.")
        employee = self.employees.get_or_none(normalize_spaces(employee_id).upper())
        if employee is None or employee.phone != normalize_phone(phone):
            raise ValidationError("Mã nhân sự hoặc số điện thoại không khớp hồ sơ nhân sự của trường.")
        if role is Role.TEACHER and not isinstance(employee, Teacher):
            raise ValidationError(f"{employee.full_name} không phải giáo viên.")
        if role is not Role.TEACHER and isinstance(employee, Teacher):
            raise ValidationError(f"{employee.full_name} là giáo viên - hãy chọn loại tài khoản Giáo viên.")
        if any(u.employee_id == employee.id for u in self.auth):
            raise DuplicateIdError(f"{employee.full_name} đã có tài khoản.")
        user = User(username=username, role=role, full_name=employee.full_name, password=password,
                    employee_id=employee.id, active=False, pending=True, phone=employee.phone,
                    duty=duty_from_position(employee.position) if role is Role.STAFF else "")
        self.auth.add(user)
        self.audit("Nhân sự đăng ký tài khoản (chờ duyệt)", user.username, {"employee": employee.id})
        return user

    def approve_user(self, user_id: str) -> User:
        user = self.auth.approve(user_id)
        self.audit("Duyệt tài khoản", user.username)
        return user

    def reject_user(self, user_id: str) -> None:
        self.auth.check_permission(Permission.MANAGE_USERS)
        user = self.auth.get(user_id)
        if not user.pending:
            raise KindergartenError("Chỉ từ chối được tài khoản đang chờ duyệt.")
        self.auth.remove(user.id)
        self.audit("Từ chối tài khoản", user.username)

    def employees_without_account(self, teachers_only: bool = False) -> list[Employee]:
        """U06: chỉ hiện nhân sự chưa có tài khoản khi tạo tài khoản."""
        linked = {u.employee_id for u in self.auth if u.employee_id}
        return [e for e in self.employees.all_sorted()
                if e.id not in linked and (not teachers_only or isinstance(e, Teacher))]

    def reset_password(self, user_id: str, new_password: str) -> User:
        user = self.auth.reset_password(user_id, new_password)
        self.audit("Đặt lại mật khẩu", user.username)
        return user

    def set_user_active(self, user_id: str, active: bool) -> User:
        user = self.auth.set_active(user_id, active)
        self.audit("Mở khóa tài khoản" if active else "Khóa tài khoản", user.username)
        return user

    def _on_employee_removed(self, employee: Employee) -> None:
        for user in self.auth.find(employee_id=employee.id):
            user.employee_id = None
            if user is not self.auth.current_user:
                user.active = False

    # ------------------------------------------------------------------ học phí
    def record_payment(self, invoice_id: str, amount: Any, method: str = "Tiền mặt", pay_date: Any = None,
                       note: str = "") -> Payment:
        payment = self.invoices.record_payment(invoice_id, amount, method, pay_date, note, self.username)
        self.audit("Thu tiền", invoice_id, {"payment": payment.id, "amount": payment.amount, "method": method})
        return payment

    def void_payment(self, invoice_id: str, payment_id: str, reason: str) -> Payment:
        payment = self.invoices.void_payment(invoice_id, payment_id, reason, self.username)
        self.audit("Hủy phiếu thu", invoice_id, {"payment": payment.id, "amount": payment.amount, "reason": reason})
        return payment

    # ------------------------------------------------------------------ dịch vụ tự chọn
    def service_catalog(self) -> list[tuple[str, int, int]]:
        """(tên dịch vụ, giá/tháng, số trẻ đang đăng ký)."""
        return [(name, price, len(self.children_using_service(name)))
                for name, price in sorted(self.settings.extra_services.items())]

    def save_service(self, name: str, price: Any, old_name: str | None = None) -> str:
        """Thêm dịch vụ mới hoặc sửa tên/giá dịch vụ; đổi tên thì các trẻ đã đăng ký vẫn giữ đăng ký."""
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.MANAGE_SERVICES)
        services = dict(self.settings.extra_services)
        clean = normalize_spaces(name)
        if not clean:
            raise ValidationError("Tên dịch vụ không được để trống.")
        old = self.settings.find_service(old_name) if old_name else None
        if old_name and old is None:
            raise KindergartenError(f"Không có dịch vụ '{old_name}'.")
        existing = self.settings.find_service(clean)
        if existing and existing != old:
            raise DuplicateIdError(f"Đã có dịch vụ '{existing}'.")
        if old:
            services.pop(old)
        services[clean] = price
        self.settings.update(extra_services=services)
        if old and old != clean:
            for child in self.children:
                if old in child.extra_services:
                    child.extra_services = [clean if s == old else s for s in child.extra_services]
        self.audit("Sửa dịch vụ" if old else "Thêm dịch vụ", clean, {"price": self.settings.extra_services[clean]})
        return clean

    def remove_service(self, name: str) -> list[Child]:
        """Xóa dịch vụ khỏi danh mục và gỡ đăng ký của các trẻ (hóa đơn đã lập không đổi)."""
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.MANAGE_SERVICES)
        key = self.settings.find_service(name)
        if key is None:
            raise KindergartenError(f"Không có dịch vụ '{name}'.")
        users = self.children_using_service(key)
        services = dict(self.settings.extra_services)
        services.pop(key)
        self.settings.update(extra_services=services)
        for child in users:
            child.extra_services = [s for s in child.extra_services if s != key]
        self.audit("Xóa dịch vụ", key, {"children": len(users)})
        return users

    def set_child_service(self, child_id: str, service: str, registered: bool) -> Child:
        """Đăng ký / hủy dịch vụ cho trẻ. Kế toán, BGH: mọi trẻ; phụ huynh: chỉ con mình. Áp dụng từ hóa đơn sau."""
        user = self.auth.current_user
        child = self.children.get(child_id)
        if user is not None:
            if user.role is Role.PARENT:
                self.auth.check_permission(Permission.PARENT_PORTAL)
                self.ensure_child_access(child)
            else:
                self.auth.check_permission(Permission.MANAGE_SERVICES)
        key = self.settings.find_service(service)
        if key is None:
            raise KindergartenError(f"Dịch vụ '{service}' không có trong danh mục của trường.")
        current = child.extra_services
        if registered and key not in current:
            child.extra_services = current + [key]
        elif not registered and key in current:
            child.extra_services = [s for s in current if s != key]
        else:
            state = "đã" if registered else "chưa"
            raise KindergartenError(f"{child.full_name} {state} đăng ký dịch vụ {key}.")
        self.audit("Đăng ký dịch vụ" if registered else "Hủy dịch vụ", str(child), {"service": key})
        return child

    # ------------------------------------------------------------------ lịch năm học (ngày nghỉ lễ)
    def _check_calendar_permission(self) -> None:
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.MANAGE_CALENDAR)

    def add_holidays(self, start: Any, end: Any, name: str) -> list[date]:
        """Thêm một ngày hoặc một khoảng ngày nghỉ (VD: Tết Nguyên đán 5 ngày)."""
        self._check_calendar_permission()
        first = parse_date(start, "Nghỉ từ ngày")
        last = parse_date(end, "Đến ngày") if end else first
        if last < first:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")
        if (last - first).days > 60:
            raise ValidationError("Mỗi lần chỉ thêm tối đa 60 ngày nghỉ.")
        if not normalize_spaces(name):
            raise ValidationError("Hãy nhập tên ngày nghỉ (VD: Tết Nguyên đán).")
        days = []
        current = first
        while current <= last:
            days.append(self.calendar.add_holiday(current, name))
            current = date.fromordinal(current.toordinal() + 1)
        self.audit("Thêm ngày nghỉ", normalize_spaces(name), {"from": first.isoformat(), "to": last.isoformat()})
        return days

    def remove_holidays(self, days: list[Any]) -> int:
        self._check_calendar_permission()
        for day in days:
            self.calendar.remove_holiday(day)
        self.audit("Bỏ ngày nghỉ", ", ".join(str(d) for d in days))
        return len(days)

    def set_saturday_classes(self, enabled: bool) -> None:
        self._check_calendar_permission()
        self.calendar.saturday_classes = bool(enabled)
        self.audit("Đổi lịch học Thứ 7", "có" if enabled else "không")

    def children_using_service(self, service: str) -> list[Child]:
        key = self.settings.find_service(service) or service
        return [c for c in self.children.active() if any(s == key for s in c.extra_services)]

    def update_fee_settings(self, unregister_removed: bool = False, **changes: Any) -> None:
        """L17: xóa dịch vụ còn trẻ đăng ký thì phải xác nhận gỡ đăng ký hàng loạt."""
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.MANAGE_FINANCE)
        new_services = changes.get("extra_services")
        affected: dict[str, list[Child]] = {}
        if new_services is not None:
            keep = {normalize_spaces(name) for name in new_services}
            for service in self.settings.extra_services:
                if service not in keep:
                    users = self.children_using_service(service)
                    if users:
                        affected[service] = users
        if affected and not unregister_removed:
            detail = "; ".join(f"{s}: {', '.join(c.full_name for c in kids)}" for s, kids in affected.items())
            raise KindergartenError(f"Còn trẻ đang đăng ký dịch vụ sắp xóa ({detail}). Hãy xác nhận gỡ đăng ký.")
        self.settings.update(**changes)
        for service, kids in affected.items():
            for child in kids:
                child.extra_services = [s for s in child.extra_services if s != service]
        self.apply_salary_settings()
        self.audit("Sửa cấu hình học phí", "", {k: str(v) for k, v in changes.items()})

    # ------------------------------------------------------------------ phạm vi theo người dùng (L08)
    def teacher_of(self, user: User | None) -> Teacher | None:
        if user is None or not user.employee_id:
            return None
        employee = self.employees.get_or_none(user.employee_id)
        return employee if isinstance(employee, Teacher) else None

    def teacher_duty(self, user: User | None) -> str:
        """Loại giáo viên theo hồ sơ hiện tại: đang chủ nhiệm một lớp = 'chu_nhiem', còn lại = 'bo_mon'.
        Tài khoản chưa gắn hồ sơ giáo viên -> '' (không thêm quyền nào)."""
        teacher = self.teacher_of(user)
        return self.teacher_duty_for_employee(teacher.id) if teacher is not None else ""

    def teacher_duty_for_employee(self, employee_id: str | None) -> str:
        teacher = self.employees.get_or_none(employee_id) if employee_id else None
        if not isinstance(teacher, Teacher):
            return ""
        if teacher.homeroom_class_id and self.classes.get_or_none(teacher.homeroom_class_id) is not None:
            return "chu_nhiem"
        return "bo_mon"

    def is_restricted(self, user: User | None) -> bool:
        """Giáo viên / phụ huynh luôn bị giới hạn theo lớp / con."""
        return user is None or user.role in (Role.TEACHER, Role.PARENT)

    def parent_of(self, user: User | None):
        """Hồ sơ phụ huynh gắn với tài khoản phụ huynh."""
        if user is None or user.role is not Role.PARENT or not user.parent_id:
            return None
        return self.parents.get_or_none(user.parent_id)

    def classes_for(self, user: User | None) -> list[Classroom]:
        """Lớp người dùng được làm việc. Giáo viên: lớp chủ nhiệm + lớp có tiết dạy; thiếu thông tin -> rỗng.
        Phụ huynh: lớp của các con."""
        if user is None:
            return []
        if user.role is Role.PARENT:
            ids = {c.class_id for c in self.children_for(user) if c.class_id}
            return [c for c in self.classes.all_sorted() if c.id in ids]
        if user.role is not Role.TEACHER:
            return self.classes.all_sorted()
        teacher = self.teacher_of(user)
        if teacher is None:
            return []                                            # không đoán, không mở rộng quyền
        ids = {slot.class_id for slot in self.timetable.find(teacher_id=teacher.id)}
        if teacher.homeroom_class_id:
            ids.add(teacher.homeroom_class_id)
        return [c for c in self.classes.all_sorted() if c.id in ids]

    def class_ids_for(self, user: User | None) -> set[str] | None:
        """None = không giới hạn (toàn trường)."""
        if user is not None and user.role not in (Role.TEACHER, Role.PARENT):
            return None
        return {c.id for c in self.classes_for(user)}

    def children_for(self, user: User | None) -> list[Child]:
        if user is not None and user.role is Role.PARENT:   # phụ huynh chỉ thấy con mình
            parent = self.parent_of(user)
            return [c for c in self.parents.children_of(parent.id) if c.is_active] if parent else []
        allowed = self.class_ids_for(user)
        children = self.children.all_sorted()
        return children if allowed is None else [c for c in children if c.class_id in allowed]

    def ensure_class_access(self, class_id: str) -> None:
        user = self.auth.current_user
        if user is None or user.role is not Role.TEACHER:
            return
        if class_id not in (self.class_ids_for(user) or set()):
            raise PermissionDeniedError(f"Giáo viên chỉ làm việc với lớp mình phụ trách "
                                        f"(không có quyền với lớp {self.classes.class_name(class_id)}).")

    def ensure_child_access(self, child: Child) -> None:
        user = self.auth.current_user
        if user is not None and user.role is Role.PARENT:
            if child.id not in {c.id for c in self.children_for(user)}:
                raise PermissionDeniedError("Phụ huynh chỉ xem thông tin của con mình.")
            return
        if user is None or user.role is not Role.TEACHER:
            return
        if child.class_id not in (self.class_ids_for(user) or set()):
            raise PermissionDeniedError(f"Giáo viên chỉ làm việc với trẻ lớp mình phụ trách ({child.full_name}).")

    # ------------------------------------------------------------------ đón trẻ (L06)
    def authorized_pickups(self, child_id: str) -> list[tuple[str, str, str]]:
        """Danh sách người được đón trẻ: (họ tên, quan hệ, SĐT) gồm phụ huynh và người đón hộ."""
        child = self.children.get(child_id)
        people = [(p.full_name, p.relationship, p.phone) for p in self.parents.parents_of(child.id)]
        people += [(p.full_name, p.relationship, p.phone) for p in child.pickup_persons]
        return people

    def save_pickup_person(self, child_id: str, person: PickupPerson, old_name: str | None = None) -> list[Child]:
        """Thêm (old_name=None) hoặc sửa một người đón hộ của trẻ.

        Một người có thể được ủy quyền đón nhiều trẻ (VD ông nội đón cả hai anh em). CSDL lưu MỖI NGƯỜI MỘT DÒNG
        trong MN_DM_NGUOI_DON_HO (đạt BCNF: số CCCD xác định họ tên, SĐT), quan hệ với từng trẻ nằm ở
        MN_DM_TRE_NGUOI_DON_HO. Vì vậy:
        - số CCCD đã ghi cho người đón khác họ tên ở trẻ khác -> từ chối (nhập nhầm CCCD hoặc họ tên);
        - sửa họ tên / SĐT / CCCD của một người -> cập nhật cho mọi trẻ người đó đang đón (quan hệ với từng trẻ
          giữ nguyên). Trả về các trẻ khác được cập nhật theo."""
        child = self.children.get(child_id)
        self.ensure_child_access(child)
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.MANAGE_CHILDREN)
        old = child.find_pickup_person(old_name) if old_name is not None else None
        if old_name is not None and old is None:
            raise NotFoundError(f"Không có '{old_name}' trong danh sách người đón hộ của {child.full_name}.")
        targets: list[tuple[Child, PickupPerson]] = []   # cùng người đó ở các trẻ khác
        for other in self.children:
            if other is child:
                continue
            for p in other.pickup_persons:
                same_card = bool(person.id_card) and p.id_card == person.id_card
                if old is not None and p.identity == old.identity:
                    targets.append((other, p))
                elif same_card:
                    if p.full_name != person.full_name:
                        raise ValidationError(f"Số CCCD {person.id_card} đã ghi cho người đón hộ '{p.full_name}' "
                                              f"của trẻ {other.full_name}. Kiểm tra lại họ tên hoặc số CCCD.")
                    targets.append((other, p))
        saved = {c.id: c.pickup_persons for c in [child] + [o for o, _p in targets]}
        try:
            if old is None:
                child.add_pickup_person(person)
            else:
                child.replace_pickup_person(old.full_name, person)
            for other, p in targets:
                other.replace_pickup_person(p.full_name, PickupPerson(person.full_name, p.relationship, person.phone,
                                                                      person.id_card))
        except KindergartenError:
            for c in [child] + [o for o, _p in targets]:   # lỗi giữa chừng: trả lại như cũ cho mọi trẻ
                c.restore_pickup_persons(saved[c.id])
            raise
        synced = list({o.id: o for o, _p in targets}.values())
        self.audit("Sửa người đón hộ" if old else "Thêm người đón hộ", str(child),
                   {"person": person.full_name, "synced": [c.id for c in synced]})
        return synced

    def verify_pickup(self, child_id: str, person_name: str, on_date: Any = None) -> str:
        """Xác nhận người đến đón; chỉ hợp lệ khi trẻ đã được điểm danh CÓ MẶT và người đón có trong danh sách
        (so đúng họ tên có dấu). Mọi lần chấp nhận/từ chối đều ghi nhật ký."""
        child = self.children.get(child_id)
        self.ensure_child_access(child)
        if self.auth.current_user is not None:
            self.auth.check_permission(Permission.CHECK_IN_OUT)
        d = parse_date(on_date) if on_date is not None else date.today()
        record = self.attendance.get_record(child.id, d)
        if record is None or not record.is_present:
            self.audit("Từ chối giao trẻ", str(child), {"person": person_name, "reason": "chưa điểm danh có mặt"})
            raise KindergartenError(f"{child.full_name} chưa được điểm danh có mặt ngày {format_date(d)}. "
                                    "Kiểm tra lại trước khi giao trẻ.")
        key = normalize_spaces(person_name).casefold()
        match = next((p for p in self.authorized_pickups(child.id) if p[0].casefold() == key), None)
        if match is None:
            self.audit("Từ chối giao trẻ", str(child), {"person": person_name, "reason": "không có trong danh sách"})
            raise PermissionDeniedError(f"'{person_name}' KHÔNG có trong danh sách được phép đón "
                                        f"{child.full_name}. Không giao trẻ, hãy liên hệ phụ huynh!")
        if record.picked_up:
            self.audit("Từ chối giao trẻ", str(child), {"person": person_name, "reason": "đã giao trẻ"})
            raise KindergartenError(f"{child.full_name} đã được giao cho {record.picked_up_by}.")
        record.picked_up_by = f"{match[0]} ({match[1]})"
        record.picked_up_at = datetime.now().isoformat(timespec="minutes")
        record.released_by = self.username
        self.audit("Giao trẻ", str(child), {"person": record.picked_up_by, "at": record.picked_up_at})
        return f"{match[0]} ({match[1]} - {match[2]})"

    # ------------------------------------------------------------------ tổng quan
    def dashboard(self, today: date | None = None, user: User | None = None) -> Dashboard:
        """Dashboard theo phạm vi người dùng (giáo viên chỉ thấy số liệu lớp mình - L09)."""
        return Dashboard(self, today, self.class_ids_for(user) if user is not None else None)
