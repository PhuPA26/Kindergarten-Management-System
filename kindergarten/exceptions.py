"""T01 - Hệ thống ngoại lệ nghiệp vụ.

Mọi lỗi nghiệp vụ đều kế thừa KindergartenError. Giao diện (console/Tkinter) chỉ cần
bắt KindergartenError để hiển thị thông báo rõ ràng thay vì để chương trình bị crash.
"""
from __future__ import annotations


class KindergartenError(Exception):
    """Lớp gốc cho mọi lỗi nghiệp vụ của hệ thống."""

    default_message = "Đã xảy ra lỗi nghiệp vụ."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)

    @property
    def message(self) -> str:
        return str(self.args[0]) if self.args else self.default_message


class ValidationError(KindergartenError, ValueError):
    """Dữ liệu nhập không hợp lệ (SĐT sai, ngày sai định dạng, số tiền âm...)."""

    default_message = "Dữ liệu không hợp lệ."


class DuplicateIdError(KindergartenError):
    """Thêm đối tượng có mã (hoặc khóa duy nhất) đã tồn tại."""

    default_message = "Mã đã tồn tại."


class NotFoundError(KindergartenError, LookupError):
    """Không tìm thấy đối tượng theo mã/khóa yêu cầu."""

    default_message = "Không tìm thấy dữ liệu."


class ClassFullError(KindergartenError):
    """Lớp học đã đủ sĩ số tối đa, không nhận thêm trẻ."""

    default_message = "Lớp đã đủ sĩ số."


class InvalidAgeError(ValidationError):
    """Độ tuổi không phù hợp (trẻ ngoài 1–6 tuổi, không hợp độ tuổi của lớp...)."""

    default_message = "Độ tuổi không phù hợp."


class PermissionDeniedError(KindergartenError):
    """Chưa đăng nhập hoặc vai trò hiện tại không có quyền dùng chức năng."""

    default_message = "Bạn không có quyền thực hiện chức năng này."


class AuthenticationError(KindergartenError):
    """Đăng nhập thất bại (sai tên đăng nhập/mật khẩu, tài khoản bị khóa)."""

    default_message = "Sai tên đăng nhập hoặc mật khẩu."


class ScheduleConflictError(KindergartenError):
    """Thời khóa biểu bị trùng tiết (cùng lớp hoặc cùng giáo viên)."""

    default_message = "Thời khóa biểu bị trùng tiết."


class PaymentError(KindergartenError):
    """Thanh toán không hợp lệ (vượt số tiền còn nợ, hóa đơn đã trả đủ...)."""

    default_message = "Thanh toán không hợp lệ."


class DataStoreError(KindergartenError):
    """Lỗi đọc/ghi file dữ liệu."""

    default_message = "Lỗi đọc/ghi dữ liệu."
