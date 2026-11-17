"""Menu console dùng chung: chỉ hiển thị chức năng mà vai trò đăng nhập được phép dùng."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ...auth.auth_manager import AuthManager
from ...auth.user import Permission
from ...exceptions import KindergartenError
from .console_io import CancelledInput, ConsoleIO


@dataclass
class MenuItem:
    label: str
    action: Callable[[], Any]
    permission: Permission | None = None
    pause: bool = True


class Menu:
    def __init__(self, title: str, io: ConsoleIO, auth: AuthManager, *, exit_label: str = "Quay lại",
                 after_action: Callable[[], Any] | None = None, header: Callable[[], str] | None = None,
                 error_log: Callable[[BaseException], Any] | None = None,
                 exit_when: Callable[[], bool] | None = None) -> None:
        self.title = title
        self.io = io
        self.auth = auth
        self.exit_label = exit_label
        self.after_action = after_action
        self.header = header
        self.error_log = error_log
        self.exit_when = exit_when
        self.items: list[MenuItem] = []

    def add(self, label: str, action: Callable[[], Any], permission: Permission | None = None,
            pause: bool = True) -> "Menu":
        self.items.append(MenuItem(label, action, permission, pause))
        return self

    def visible_items(self) -> list[MenuItem]:
        return [item for item in self.items
                if item.permission is None or self.auth.has_permission(item.permission)]

    def _should_exit(self) -> bool:
        return bool(self.exit_when and self.exit_when())

    def run(self) -> None:
        while not self._should_exit():
            items = self.visible_items()
            self.io.header(self.title)
            if self.header:
                self.io.write(self.header())
            for index, item in enumerate(items, 1):
                self.io.write(f"  {index:>2}. {item.label}")
            self.io.write(f"   0. {self.exit_label}")
            try:
                choice = self.io.input("Chọn chức năng: ")
            except CancelledInput:
                return
            if choice == "0":
                return
            if not choice:
                continue
            if not choice.isdigit() or not 1 <= int(choice) <= len(items):
                self.io.error("Lựa chọn không hợp lệ.")
                continue
            self.execute(items[int(choice) - 1])

    def execute(self, item: MenuItem) -> None:
        """Chạy một chức năng: kiểm tra quyền, bắt lỗi nghiệp vụ để chương trình không bị dừng.

        L23: chỉ tự lưu khi thao tác kết thúc bình thường (hủy giữa chừng hay lỗi thì không ghi xuống đĩa).
        """
        succeeded = False
        try:
            if item.permission is not None:
                self.auth.check_permission(item.permission)
            item.action()
            succeeded = True
        except CancelledInput:
            self.io.warning("Đã hủy thao tác.")
        except KindergartenError as exc:
            self.io.error(exc.message)
        except KeyboardInterrupt:
            self.io.warning("Đã hủy thao tác.")
        except EOFError:
            raise
        except Exception as exc:  # lỗi lập trình ngoài dự kiến: ghi log, không làm dừng chương trình
            self.io.error(f"Lỗi không mong muốn: {exc!r}. Chi tiết đã ghi vào file log.")
            if self.error_log:
                self.error_log(exc)
        if succeeded and self.after_action:
            try:
                self.after_action()
            except KindergartenError as exc:
                self.io.error(exc.message)
        if item.pause and not self._should_exit():
            self.io.pause()
