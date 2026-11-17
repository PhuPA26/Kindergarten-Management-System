"""Tiện ích nhập/xuất cho giao diện console: nhập có kiểm tra (nhập sai thì hỏi lại), bảng, màu sắc."""
from __future__ import annotations

import getpass
import os
import sys
from datetime import date
from typing import Any, Callable, Iterable, Sequence, TypeVar

from ...exceptions import ValidationError
from ...utils import (format_date, format_key_values, format_table, format_time, format_vnd, month_label,
                      normalize_text, parse_bool, parse_date, parse_float, parse_int, parse_money, parse_month,
                      parse_time, text_contains, validate_phone)

T = TypeVar("T")


class CancelledInput(Exception):
    """Người dùng nhập '!' để hủy thao tác đang làm."""


class ConsoleIO:
    CANCEL_TOKEN = "!"
    CLEAR_TOKEN = "-"
    PAGE_SIZE = 20
    COLORS = {"red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m", "cyan": "\033[96m",
              "bold": "\033[1m", "reset": "\033[0m"}

    def __init__(self, input_func: Callable[[str], str] | None = None,
                 output_func: Callable[[str], Any] | None = None, use_color: bool | None = None) -> None:
        self._interactive = input_func is None
        self._input = input_func or input
        self._output = output_func or print
        if use_color is None:
            use_color = (self._interactive and output_func is None and sys.stdout.isatty()
                         and not os.environ.get("NO_COLOR"))
            if use_color and os.name == "nt":
                os.system("")  # bật chế độ hiển thị màu ANSI trên cửa sổ console Windows
        self.use_color = bool(use_color)

    # ================================================================== xuất
    def paint(self, text: str, color: str) -> str:
        if not self.use_color:
            return text
        return f"{self.COLORS[color]}{text}{self.COLORS['reset']}"

    def write(self, text: Any = "") -> None:
        self._output(str(text))

    def header(self, title: str) -> None:
        line = "=" * max(64, len(title) + 6)
        self.write("")
        self.write(self.paint(line, "cyan"))
        self.write(self.paint(f"   {title.upper()}", "bold"))
        self.write(self.paint(line, "cyan"))

    def success(self, message: str) -> None:
        self.write(self.paint(f"[OK] {message}", "green"))

    def error(self, message: str) -> None:
        self.write(self.paint(f"[LỖI] {message}", "red"))

    def warning(self, message: str) -> None:
        self.write(self.paint(f"[!] {message}", "yellow"))

    def info(self, message: str) -> None:
        self.write(message)

    def table(self, headers: Sequence[Any], rows: Iterable[Sequence[Any]], title: str | None = None,
              max_width: int = 42) -> None:
        self.write(format_table(headers, rows, title=title, max_width=max_width))

    def key_values(self, pairs: Iterable[tuple[str, Any]], title: str | None = None) -> None:
        self.write(format_key_values(pairs, title))

    # ================================================================== nhập cơ bản
    def input(self, prompt: str) -> str:
        try:
            raw = self._input(prompt)
        except StopIteration:  # hết dữ liệu nhập (khi chạy kiểm thử tự động)
            raise EOFError from None
        raw = (raw or "").replace("﻿", "").replace("​", "").strip()  # bỏ ký tự vô hình (BOM...)
        if raw == self.CANCEL_TOKEN:
            raise CancelledInput
        return raw

    def input_password(self, prompt: str = "Mật khẩu: ") -> str:
        try:
            if self._interactive and sys.stdin.isatty():
                return getpass.getpass(prompt)
            return (self._input(prompt) or "").replace("﻿", "")
        except StopIteration:
            raise EOFError from None

    def pause(self) -> None:
        try:
            self.input("Nhấn Enter để tiếp tục...")
        except CancelledInput:
            pass

    def ask(self, prompt: str, parser: Callable[[str], Any] | None = None, default: Any = None,
            required: bool = True, display_default: str | None = None) -> Any:
        """Hỏi đến khi nhập hợp lệ. Enter = giữ giá trị mặc định (nếu có)."""
        if default is not None:
            hint = f" [{display_default if display_default is not None else default}]"
        elif not required:
            hint = " (Enter để bỏ qua)"
        else:
            hint = ""
        while True:
            raw = self.input(f"{prompt}{hint}: ")
            if not raw:
                if default is not None:
                    return default
                if not required:
                    return None
                self.error("Không được để trống.")
                continue
            try:
                return parser(raw) if parser else raw
            except ValidationError as exc:
                self.error(exc.message)

    # ================================================================== nhập theo kiểu dữ liệu
    def ask_text(self, prompt: str, default: str | None = None, required: bool = True,
                 validator: Callable[[str], str] | None = None) -> str | None:
        """Nhập chuỗi. Với trường không bắt buộc, nhập '-' để xóa trắng giá trị hiện có."""

        def parser(raw: str) -> str:
            if not required and raw == self.CLEAR_TOKEN:
                return ""
            return validator(raw) if validator else raw

        if not required and default:
            prompt = f"{prompt} ('-' để xóa)"
        return self.ask(prompt, parser, default or None, required)

    def ask_int(self, prompt: str, default: int | None = None, min_value: int | None = None,
                max_value: int | None = None, required: bool = True) -> int | None:
        return self.ask(prompt, lambda raw: parse_int(raw, prompt, min_value, max_value), default, required)

    def ask_float(self, prompt: str, default: float | None = None, min_value: float | None = None,
                  max_value: float | None = None, required: bool = True) -> float | None:
        return self.ask(prompt, lambda raw: parse_float(raw, prompt, min_value, max_value), default, required)

    def ask_money(self, prompt: str, default: int | None = None, required: bool = True,
                  allow_zero: bool = True) -> int | None:
        return self.ask(prompt, lambda raw: parse_money(raw, prompt, allow_zero), default, required,
                        format_vnd(default) if default is not None else None)

    def ask_date(self, prompt: str, default: date | None = None, required: bool = True,
                 check: Callable[[date], Any] | None = None) -> date | None:
        def parser(raw: str) -> date:
            value = parse_date(raw, prompt)
            if check:
                check(value)
            return value

        return self.ask(f"{prompt} (dd/mm/yyyy)", parser, default, required,
                        format_date(default) if default else None)

    def ask_time(self, prompt: str, default: Any = None) -> Any:
        return self.ask(f"{prompt} (HH:MM)", lambda raw: parse_time(raw, prompt), default,
                        display_default=format_time(default) if default else None)

    def ask_month(self, prompt: str = "Tháng", default: tuple[int, int] | None = None) -> tuple[int, int]:
        return self.ask(f"{prompt} (mm/yyyy)", parse_month, default,
                        display_default=month_label(*default) if default else None)

    def ask_phone(self, prompt: str = "Số điện thoại", default: str | None = None, required: bool = True,
                  check: Callable[[str], Any] | None = None) -> str | None:
        def parser(raw: str) -> str:
            phone = validate_phone(raw, field=prompt)
            if check:
                check(phone)
            return phone

        return self.ask(prompt, parser, default or None, required)

    def ask_yes_no(self, prompt: str, default: bool = False) -> bool:
        return self.ask(f"{prompt} (c/k)", parse_bool, default, display_default="c" if default else "k")

    def ask_choice(self, prompt: str, options: Sequence[tuple[Any, str]], default: Any = None) -> Any:
        """Chọn một mục trong danh sách đánh số."""
        options = list(options)
        for index, (_, label) in enumerate(options, 1):
            self.write(f"    {index}. {label}")
        default_index = next((i for i, (value, _) in enumerate(options, 1) if value == default), None)

        def parser(raw: str) -> Any:
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1][0]
            key = normalize_text(raw)
            for value, label in options:
                if normalize_text(label) == key:
                    return value
            raise ValidationError(f"Hãy nhập số từ 1 đến {len(options)}.")

        if default_index is not None:
            return self.ask(prompt, parser, default, display_default=str(default_index))
        return self.ask(prompt, parser)

    def ask_indexes(self, prompt: str, count: int, required: bool = True) -> list[int] | None:
        """Nhập nhiều số thứ tự cách nhau dấu phẩy hoặc khoảng trắng, VD: 1, 3 5."""

        def parser(raw: str) -> list[int]:
            parts = raw.replace(",", " ").split()
            result = []
            for part in parts:
                if not part.isdigit() or not 1 <= int(part) <= count:
                    raise ValidationError(f"'{part}' không phải số thứ tự từ 1 đến {count}.")
                if int(part) not in result:
                    result.append(int(part))
            return result

        return self.ask(prompt, parser, required=required)

    def choose(self, items: Iterable[T], label: Callable[[T], str] = str, title: str = "Chọn",
               empty_message: str = "Không có dữ liệu để chọn.") -> T | None:
        """Chọn một đối tượng: nhập số thứ tự, mã (VD: C001) hoặc từ khóa để lọc. Enter = bỏ qua."""
        items = list(items)
        if not items:
            self.warning(empty_message)
            return None
        candidates = items
        page = 0
        while True:
            # U07: danh sách dài thì hiện theo trang PAGE_SIZE dòng, 'n'/'p' để chuyển trang
            pages = max((len(candidates) - 1) // self.PAGE_SIZE + 1, 1)
            page = min(page, pages - 1)
            start = page * self.PAGE_SIZE
            for index, item in enumerate(candidates[start:start + self.PAGE_SIZE], start + 1):
                self.write(f"  {index:>3}. {label(item)}")
            paging = ""
            if pages > 1:
                paging = f" [trang {page + 1}/{pages}: n = sau, p = trước]"
            raw = self.input(f"{title}{paging} (STT / mã / từ khóa, Enter = bỏ qua): ")
            if not raw:
                return None
            if pages > 1 and raw.lower() in ("n", "p"):
                page = (page + (1 if raw.lower() == "n" else -1)) % pages
                continue
            if raw.isdigit():
                number = int(raw)
                if 1 <= number <= len(candidates):
                    return candidates[number - 1]
                if len(raw) <= 3:  # số ngắn: STT sai; số dài (VD: SĐT) thì coi là từ khóa tìm kiếm
                    self.error("Số thứ tự không hợp lệ.")
                    continue
            exact = [item for item in items if str(getattr(item, "id", "")).upper() == raw.upper()]
            if exact:
                return exact[0]
            filtered = [item for item in items if text_contains(label(item), raw)]
            if len(filtered) == 1:
                return filtered[0]
            if not filtered:
                self.error(f"Không tìm thấy '{raw}', hãy thử lại.")
                candidates = items
                continue
            self.info(f"Có {len(filtered)} kết quả phù hợp:")
            candidates, page = filtered, 0
