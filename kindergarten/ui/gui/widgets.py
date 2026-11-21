"""Thành phần giao diện Tkinter dùng chung: bảng dữ liệu, hộp thoại nhập liệu, cửa sổ xem văn bản."""
from __future__ import annotations

import os
import re
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable, Sequence

from ...exceptions import KindergartenError, ValidationError
from ...reports.reports import Report
from ...utils import format_date, format_number, normalize_text, parse_money

FONTS = {"ui": "Segoe UI", "mono": "Consolas", "size": 10}   # được chọn lại khi khởi động (U19)
SCALE = {"factor": 1.0}   # tỷ lệ phóng của màn hình (Windows 150% -> 1.5), đo khi khởi động


def detect_scale(root: tk.Misc) -> float:
    """Tỷ lệ phóng màn hình so với 96 DPI. Mọi kích thước tính bằng điểm ảnh (cửa sổ, cột bảng, menu)
    được nhân với tỷ lệ này để giao diện không bị thu nhỏ trên màn hình đặt 125% / 150%."""
    try:
        factor = float(root.winfo_fpixels("1i")) / 96.0
    except tk.TclError:
        factor = 1.0
    SCALE["factor"] = max(1.0, min(round(factor, 2), 3.0))
    return SCALE["factor"]


def px(value: float) -> int:
    """Đổi kích thước thiết kế (ở 100%) sang điểm ảnh thật theo tỷ lệ màn hình."""
    return int(round(value * SCALE["factor"]))


def pick_font(preferred: Sequence[str], fallback: str = "TkDefaultFont") -> str:
    """U19: dùng phông dự phòng khi máy không có phông ưu tiên (VD: Segoe UI, Consolas)."""
    try:
        families = {f.lower() for f in tkfont.families()}
    except tk.TclError:
        return preferred[0]
    return next((name for name in preferred if name.lower() in families), fallback)


def configure_fonts() -> None:
    FONTS["ui"] = pick_font(["Segoe UI", "Arial", "Helvetica", "DejaVu Sans"])
    FONTS["mono"] = pick_font(["Consolas", "Cascadia Mono", "Courier New", "DejaVu Sans Mono"], "TkFixedFont")
    FONTS["icon"] = pick_font(["Segoe UI Symbol", "Segoe UI", "DejaVu Sans"], FONTS["ui"])


def ui_font(size_delta: int = 0, weight: str = "normal") -> tuple:
    return (FONTS["ui"], FONTS["size"] + size_delta, weight)


def mono_font() -> tuple:
    return (FONTS["mono"], FONTS["size"])


MONO_FONT = ("Consolas", 10)   # giữ để tương thích; nơi tạo widget dùng mono_font()
# Bảng màu giao diện (phong cách phần mềm mầm non hiện đại: nền xanh nhạt, thẻ trắng, menu xanh navy)
COLORS = {
    "primary": "#1f6fe5", "primary_dark": "#1556b8", "primary_light": "#7aaaf2",
    "primary_soft": "#eaf2ff", "primary_soft2": "#d5e5ff",
    "navy": "#10285a", "text": "#1d2939", "label": "#344054", "muted": "#667085", "muted_light": "#98a2b3",
    "bg": "#f1f5fb", "card": "#ffffff", "border": "#e3e9f2", "border_strong": "#cbd5e3", "head": "#f5f8fd",
    "select": "#dbe9ff", "stripe": "#f8fafe",
    "warn": "#d92d20", "ok": "#079455", "orange": "#f08c00", "pink": "#e2468f", "purple": "#7a5af8",
    "cyan": "#0aa2c0",
    # menu trái nền navy: mục đang chọn là viên xanh dương, thẻ phân hệ / tài khoản xanh navy sáng hơn
    "sidebar": "#10285a", "sidebar_hover": "#1a3a78", "sidebar_text": "#c9d5ee", "sidebar_group": "#7489b6",
    "sidebar_icon": "#9fb3da", "sidebar_card": "#183670", "sidebar_button": "#24498f",
}
ACCENTS = ["primary", "ok", "orange", "purple", "pink", "cyan"]


def tint(color: str, amount: float = 0.88) -> str:
    """Pha màu với trắng (amount = tỷ lệ trắng) - dùng làm nền nhạt cho chip / biểu tượng."""
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: int(c + (255 - c) * amount)   # noqa: E731
    return f"#{mix(r):02x}{mix(g):02x}{mix(b):02x}"


def icon_font(size_delta: int = 0) -> tuple:
    """Phông cho các ký hiệu biểu tượng (Segoe UI Symbol có sẵn trên Windows)."""
    return (FONTS.get("icon", FONTS["ui"]), FONTS["size"] + size_delta)


# =============================================================================
# Bảng dữ liệu
# =============================================================================
class DataTable(ttk.Frame):
    """Treeview có thanh cuộn, đặt cột nhanh, lấy mã dòng đang chọn."""

    CHECKED, UNCHECKED = "☑", "☐"

    def __init__(self, master: tk.Misc, columns: Sequence[tuple] = (), height: int = 8,
                 selectmode: str = "browse", checkable: bool = False) -> None:
        super().__init__(master)
        # checkable: thêm cột ô tích đầu bảng - bấm vào ô (hoặc phím Space) để chọn nhiều dòng, không cần Ctrl/Shift
        self.checkable = checkable
        self.row_click_check: Callable[[str], bool] | None = None   # bấm vào dòng cũng tích (nếu hàm trả True)
        # dòng nào được tích (None = mọi dòng). Dòng không được tích thì không có ô ☐ (VD trẻ vắng ở màn ăn ngủ)
        self.check_filter: Callable[[str], bool] | None = None
        self._checked: set[str] = set()
        self._check_listeners: list[Callable[[], Any]] = []
        self.tree = ttk.Treeview(self, show="headings", height=height, selectmode=selectmode)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        # cuộn ngang bằng touchpad / Shift + lăn chuột: mượt theo điểm ảnh (mặc định của Tk nhảy cả bước lớn)
        self.tree.bind("<Shift-MouseWheel>", self._on_horizontal_wheel)
        self.tree.tag_configure("odd", background=COLORS["stripe"])
        self.tree.tag_configure("warn", foreground=COLORS["warn"])
        self.tree.tag_configure("ok", foreground=COLORS["ok"])
        self.tree.tag_configure("muted", foreground=COLORS["muted"])
        if columns:
            self.set_columns(columns)
        if checkable:
            self.tree.bind("<Button-1>", self._on_click, add="+")
            self.tree.bind("<KeyPress-space>",
                           lambda _e: self.toggle(self.tree.selection()) if self.checkable else None)

    # ------------------------------------------------------------------ cuộn ngang mượt
    HSCROLL_PX_PER_NOTCH = 60   # một nấc lăn chuột (delta 120) = 60 điểm ảnh; touchpad gửi delta nhỏ -> dịch ít

    def _on_horizontal_wheel(self, event: tk.Event) -> str:
        """Tk 8.6 cuộn ngang bằng `xview scroll [expr {-%D/120}] units`: phép chia nguyên biến mỗi lần vuốt
        touchpad (delta nhỏ) thành cả một bước lớn hoặc 0 -> giật. Ở đây dịch đúng theo số điểm ảnh của delta."""
        first, last = self.tree.xview()
        visible = last - first
        if visible >= 1 or not event.delta:
            return "break"
        content_width = self.tree.winfo_width() / visible   # bề rộng toàn bộ các cột (điểm ảnh)
        shift = -event.delta / 120 * px(self.HSCROLL_PX_PER_NOTCH)
        self.tree.xview_moveto(max(0.0, min(1.0 - visible, first + shift / content_width)))
        return "break"

    # ------------------------------------------------------------------ ô tích chọn nhiều dòng
    def set_checkable(self, checkable: bool) -> None:
        """Bật / tắt cột ô tích khi đang chạy (VD: đón trẻ tích nhiều trẻ, trả trẻ thì từng trẻ một - không có ô tích).
        Bảng phải được tạo với checkable=True để có sẵn xử lý bấm chuột."""
        if checkable == self.checkable:
            return
        self.checkable = checkable
        self._checked.clear()
        self.tree.delete(*self.tree.get_children())
        self.set_columns(self._base_columns)
        self._notify()

    def _on_click(self, event: tk.Event) -> str | None:
        if not self.checkable:
            return None
        if self.tree.identify_region(event.x, event.y) == "heading" and self.tree.identify_column(event.x) == "#1":
            visible = [i for i in self.tree.get_children() if self.can_check(i)]
            self.set_checked([] if all(i in self._checked for i in visible) else visible)
            return "break"
        row = self.tree.identify_row(event.y)
        if self.tree.identify_column(event.x) == "#1":
            if row:
                self.toggle([row])
                return "break"
        elif row and self.tree.identify_region(event.x, event.y) == "cell" and self.row_click_check is not None \
                and self.row_click_check(row):
            self.toggle([row])   # bấm vào bất kỳ ô nào của dòng = tích / bỏ tích; dòng vẫn được chọn như thường
        return None

    def can_check(self, iid: str) -> bool:
        return self.check_filter is None or self.check_filter(iid)

    def _box(self, iid: str) -> str:
        if not self.can_check(iid):
            return ""
        return self.CHECKED if iid in self._checked else self.UNCHECKED

    def _paint(self, iid: str) -> None:
        if self.tree.exists(iid):
            self.tree.set(iid, "c0", self._box(iid))

    def toggle(self, ids: Sequence[str]) -> None:
        for iid in ids:
            if self.can_check(iid):
                self._checked.symmetric_difference_update({iid})
                self._paint(iid)
        self._notify()

    def set_checked(self, ids: Sequence[str]) -> None:
        self._checked = {i for i in ids if self.tree.exists(i) and self.can_check(i)}
        for iid in self.tree.get_children():
            self._paint(iid)
        self._notify()

    def checked_ids(self, *, fallback_to_selection: bool = True) -> list[str]:
        """Các dòng đang được tích (theo thứ tự hiển thị); chưa tích dòng nào thì lấy các dòng đang chọn."""
        ticked = [i for i in self.tree.get_children() if i in self._checked]
        return ticked or (list(self.tree.selection()) if fallback_to_selection else [])

    def on_check(self, callback: Callable[[], Any]) -> None:
        self._check_listeners.append(callback)

    def _notify(self) -> None:
        for callback in self._check_listeners:
            callback()

    def set_columns(self, columns: Sequence[tuple]) -> None:
        """columns: [(tiêu đề, độ rộng[, căn lề 'w'|'e'|'center'])]. Bấm tiêu đề cột để sắp xếp (U14)."""
        self._base_columns = list(columns)
        if self.checkable:
            columns = [(self.UNCHECKED, 34, "center")] + list(columns)
        ids = [f"c{i}" for i in range(len(columns))]
        self.tree["columns"] = ids
        self._titles = {cid: spec[0] for cid, spec in zip(ids, columns)}
        self._sort_state: tuple[str, bool] | None = None
        for cid, spec in zip(ids, columns):
            title, width = spec[0], px(spec[1])
            anchor = spec[2] if len(spec) > 2 else "w"
            command = (lambda: None) if (self.checkable and cid == "c0") else (lambda c=cid: self.sort_by(c))
            self.tree.heading(cid, text=title, anchor="center", command=command)
            self.tree.column(cid, width=width, minwidth=40, anchor=anchor, stretch=True)

    @staticmethod
    def _sort_value(text: str) -> tuple[int, Any]:
        """Số/tiền/% so theo giá trị, ngày dd/mm/yyyy theo thời gian, chữ theo thứ tự không dấu."""
        raw = str(text).replace("⚠", "").strip()
        digits = re.sub(r"[^\d,\-]", "", raw.replace(".", ""))
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw):
            d, m, y = raw.split("/")
            return 1, (int(y), int(m), int(d))
        if digits and re.fullmatch(r"-?[\d.,]+\s*(đ|%|kcal|năm|cm|kg)?", raw):
            try:
                return 0, float(digits.replace(",", "."))
            except ValueError:
                pass
        return 2, normalize_text(raw)

    def sort_by(self, cid: str) -> None:
        descending = bool(self._sort_state and self._sort_state[0] == cid and not self._sort_state[1])
        rows = [(self._sort_value(self.tree.set(iid, cid)), iid) for iid in self.tree.get_children()]
        rows.sort(reverse=descending)
        for index, (_value, iid) in enumerate(rows):
            self.tree.move(iid, "", index)
            tags = [t for t in self.tree.item(iid, "tags") if t != "odd"] + (["odd"] if index % 2 else [])
            self.tree.item(iid, tags=tags)
        self._sort_state = (cid, descending)
        for other, title in self._titles.items():
            arrow = (" ▼" if descending else " ▲") if other == cid else ""
            self.tree.heading(other, text=title + arrow)

    def set_rows(self, rows: Sequence[Sequence[Any]], ids: Sequence[str] | None = None,
                 tags: Sequence[str | None] | None = None) -> None:
        selected = set(self.tree.selection())
        first_visible = self.tree.yview()[0]   # U14: giữ vị trí cuộn khi làm mới
        self.tree.delete(*self.tree.get_children())
        if self.checkable:
            new_ids = {str(ids[i]) if ids else str(i) for i in range(len(rows))}
            # giữ ô đã tích qua các lần làm mới (bỏ dòng đã mất / không còn được tích)
            self._checked = {i for i in self._checked & new_ids if self.can_check(i)}
        for index, row in enumerate(rows):
            iid = str(ids[index]) if ids else str(index)
            if self.checkable:
                row = [self._box(iid)] + list(row)
            row_tags = ["odd"] if index % 2 else []
            if tags and tags[index]:
                row_tags.append(tags[index])
            self.tree.insert("", "end", iid=iid, values=["" if v is None else v for v in row], tags=row_tags)
        keep = [i for i in selected if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        if getattr(self, "_sort_state", None):
            cid, descending = self._sort_state
            self._sort_state = (cid, not descending)
            self.sort_by(cid)
        self.tree.yview_moveto(first_visible)

    def selected_id(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def selected_ids(self) -> list[str]:
        return list(self.tree.selection())

    def all_ids(self) -> list[str]:
        return list(self.tree.get_children())

    def on_double_click(self, callback: Callable[[], Any]) -> None:
        self.tree.bind("<Double-1>", lambda _e: callback())

    def on_select(self, callback: Callable[[], Any]) -> None:
        self.tree.bind("<<TreeviewSelect>>", lambda _e: callback())


# =============================================================================
# Hộp thoại nhập liệu
# =============================================================================
@dataclass
class Field:
    name: str
    label: str
    kind: str = "text"   # text | password | date | money | choice | multi | bool | textarea
    options: list[tuple[Any, str]] = field(default_factory=list)
    default: Any = None
    required: bool = True
    width: int = 34

    def __post_init__(self) -> None:
        if self.kind not in ("choice", "multi") and self.options:
            raise TypeError(f"Trường '{self.name}' kiểu {self.kind} không dùng options - hãy truyền default=...")


class FormDialog(tk.Toplevel):
    """Hộp thoại nhập dữ liệu. Lỗi nghiệp vụ khi lưu -> báo lỗi và giữ nguyên hộp thoại để sửa.

    U17: form dài chia hai cột; đóng (Esc/nút X/Hủy) khi đã nhập dở thì hỏi lại; ô tiền tự thêm dấu phân cách
    nghìn khi rời ô; lỗi thì đưa con trỏ tới ô liên quan.
    """

    TWO_COLUMN_AFTER = 8

    def __init__(self, master: tk.Misc, title: str, fields: list[Field],
                 on_submit: Callable[[dict[str, Any]], Any] | None = None, submit_text: str = "Thực hiện") -> None:
        super().__init__(master)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.on_submit = on_submit
        self.result: Any = None
        self.submitted = False
        self._vars: dict[str, tuple[Field, Any]] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self.configure(bg=COLORS["card"])
        # Form Detail (Hướng dẫn XD HTTTQL): tiêu đề form đầy đủ căn giữa; nút Thực hiện / Hủy bỏ
        header = tk.Frame(self, bg=COLORS["primary_soft"], padx=px(24), pady=px(12))
        header.pack(fill="x")
        tk.Label(header, text=title, font=ui_font(4, "bold"), fg=COLORS["navy"], bg=COLORS["primary_soft"]).pack()
        tk.Label(header, text="Các ô có dấu * là bắt buộc", font=ui_font(-1), fg=COLORS["muted"],
                 bg=COLORS["primary_soft"]).pack()
        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x")
        body = ttk.Frame(self, padding=(px(20), px(14), px(20), px(16)))
        body.pack(fill="both", expand=True)
        first_widget = None
        per_column = (len(fields) + 1) // 2 if len(fields) > self.TWO_COLUMN_AFTER else len(fields)
        for index, spec in enumerate(fields):
            row, block = index % per_column, index // per_column
            star = " *" if spec.required and spec.kind not in ("bool", "multi") else ""
            ttk.Label(body, text=spec.label + star, style="Field.TLabel").grid(
                row=row, column=block * 2, sticky="nw", padx=(px(24) if block else 0, px(12)), pady=px(6))
            widget = self._make_widget(body, spec)
            widget.grid(row=row, column=block * 2 + 1, sticky="we", pady=px(5))
            self._widgets[spec.name] = widget
            first_widget = first_widget or widget
        buttons = ttk.Frame(body)
        buttons.grid(row=per_column, column=0, columnspan=4, sticky="e", pady=(px(16), 0))
        ttk.Button(buttons, text="Hủy bỏ", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text=submit_text, style="Accent.TButton", command=self._submit).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.bind("<Return>", self._on_return)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.update_idletasks()
        self._center(master)
        self._initial = self._snapshot()
        self.grab_set()
        if first_widget is not None:
            first_widget.focus_set()

    def _center(self, master: tk.Misc) -> None:
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + max((top.winfo_width() - self.winfo_width()) // 2, 0)
        y = top.winfo_rooty() + max((top.winfo_height() - self.winfo_height()) // 3, 0)
        self.geometry(f"+{x}+{y}")

    @staticmethod
    def _default_text(spec: Field) -> str:
        value = spec.default
        if value is None:
            return ""
        if isinstance(value, date):
            return format_date(value)
        if spec.kind == "money" and isinstance(value, (int, float)):
            return f"{int(value):,}".replace(",", ".")
        if isinstance(value, float):
            return format_number(value, 2).rstrip("0").rstrip(",")
        return str(value)

    def _make_widget(self, parent: tk.Misc, spec: Field) -> tk.Widget:
        if spec.kind == "bool":
            var = tk.BooleanVar(value=bool(spec.default))
            widget = ttk.Checkbutton(parent, variable=var)
        elif spec.kind == "choice":
            labels = [label for _, label in spec.options]
            current = next((label for value, label in spec.options if value == spec.default), "")
            var = tk.StringVar(value=current)
            if len(labels) <= 3 and all(len(label) <= 24 for label in labels):
                # ít lựa chọn ngắn (VD giới tính Nam / Nữ) -> RadioButton như mẫu Form Detail của hướng dẫn
                widget = ttk.Frame(parent)
                for label in labels:
                    ttk.Radiobutton(widget, text=label, value=label, variable=var).pack(side="left",
                                                                                         padx=(0, px(18)))
            else:
                widget = ttk.Combobox(parent, textvariable=var, values=labels, state="readonly", width=spec.width)
        elif spec.kind == "multi":
            frame = ttk.Frame(parent)
            var = tk.Listbox(frame, selectmode="multiple", height=min(max(len(spec.options), 2), 7),
                             exportselection=False, width=spec.width)
            for index, (value, label) in enumerate(spec.options):
                var.insert("end", label)
                if spec.default and value in spec.default:
                    var.selection_set(index)
            scroll = ttk.Scrollbar(frame, orient="vertical", command=var.yview)
            var.configure(yscrollcommand=scroll.set)
            var.pack(side="left", fill="both", expand=True)
            scroll.pack(side="left", fill="y")
            widget = frame
        elif spec.kind == "textarea":
            var = tk.Text(parent, height=3, width=spec.width, wrap="word")
            var.insert("1.0", self._default_text(spec))
            widget = var
        else:
            var = tk.StringVar(value=self._default_text(spec))
            widget = ttk.Entry(parent, textvariable=var, width=spec.width, show="•" if spec.kind == "password" else "")
            if spec.kind == "money":
                widget.bind("<FocusOut>", lambda _e, v=var: self._format_money(v))
        self._vars[spec.name] = (spec, var)
        return widget

    @staticmethod
    def _format_money(var: tk.StringVar) -> None:
        try:
            var.set(f"{parse_money(var.get()):,}".replace(",", "."))
        except KindergartenError:
            pass   # để nguyên, lỗi sẽ báo khi bấm Lưu

    def _snapshot(self) -> list[Any]:
        state = []
        for spec, var in self._vars.values():
            if spec.kind == "multi":
                state.append(tuple(var.curselection()))
            elif spec.kind == "textarea":
                state.append(var.get("1.0", "end"))
            else:
                state.append(var.get())
        return state

    def cancel(self) -> None:
        if self._snapshot() != self._initial and not messagebox.askyesno(
                "Đóng biểu mẫu", "Bạn đã nhập dữ liệu nhưng chưa lưu. Đóng và bỏ các thay đổi?", parent=self):
            return
        self.destroy()

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, (spec, var) in self._vars.items():
            if spec.kind == "choice":
                label = var.get()
                value = next((v for v, lab in spec.options if lab == label), None)
                missing = label == ""
            elif spec.kind == "multi":
                value, missing = [spec.options[i][0] for i in var.curselection()], False
            elif spec.kind == "bool":
                value, missing = bool(var.get()), False
            elif spec.kind == "textarea":
                value = var.get("1.0", "end").strip()
                missing = value == ""
            else:
                value = var.get() if spec.kind == "password" else var.get().strip()
                missing = value == ""
            if missing and spec.required:
                self._focus(name)
                raise ValidationError(f"'{spec.label}' không được để trống.")
            result[name] = value
        return result

    def _focus(self, name: str) -> None:
        widget = self._widgets.get(name)
        if widget is not None:
            widget.focus_set()

    def _focus_from_message(self, message: str) -> None:
        """Đưa con trỏ tới ô có nhãn xuất hiện trong thông báo lỗi."""
        text = normalize_text(message)
        for name, (spec, _var) in self._vars.items():
            label = normalize_text(spec.label.split("(")[0])
            if label and label in text:
                self._focus(name)
                return

    def _on_return(self, event: tk.Event) -> None:
        if not isinstance(event.widget, tk.Text):
            self._submit()

    def _submit(self) -> None:
        try:
            values = self.values()
            self.result = self.on_submit(values) if self.on_submit else values
        except ValidationError as exc:
            self._focus_from_message(exc.message)
            messagebox.showerror("Dữ liệu chưa hợp lệ", exc.message, parent=self)
            return
        except KindergartenError as exc:   # từ chối nghiệp vụ (VD: không được đón trẻ) - không phải lỗi nhập
            messagebox.showwarning("Không thực hiện được", exc.message, parent=self)
            return
        self.submitted = True
        self.destroy()



class DeleteDialog(tk.Toplevel):
    """Form Detail khi XÓA (Hướng dẫn XD HTTTQL): hiện thông tin đối tượng (chỉ đọc) + dòng cảnh báo đỏ
    "Lưu ý: Bạn có muốn xóa đối tượng này không?" + nút Thực hiện / Hủy bỏ."""

    def __init__(self, master: tk.Misc, title: str, details: Sequence[tuple[str, Any]], note: str = "") -> None:
        super().__init__(master)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.confirmed = False
        self.configure(bg=COLORS["card"])
        header = tk.Frame(self, bg=COLORS["primary_soft"], padx=px(24), pady=px(12))
        header.pack(fill="x")
        tk.Label(header, text=title, font=ui_font(4, "bold"), fg=COLORS["navy"], bg=COLORS["primary_soft"]).pack()
        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x")
        body = ttk.Frame(self, padding=(px(24), px(14), px(24), px(16)))
        body.pack(fill="both", expand=True)
        for row, (label, value) in enumerate(details):
            ttk.Label(body, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", padx=(0, px(12)),
                                                                   pady=px(4))
            box = ttk.Entry(body, width=42)
            box.insert(0, "" if value is None else str(value))
            box.state(["readonly"])
            box.grid(row=row, column=1, sticky="we", pady=px(4))
        row = len(details)
        tk.Label(body, text="Lưu ý: Bạn có muốn xóa đối tượng này không?", font=ui_font(0, "bold"),
                 fg=COLORS["warn"], bg=COLORS["card"]).grid(row=row, column=0, columnspan=2, pady=(px(14), 0))
        if note:
            tk.Label(body, text=note, font=ui_font(-1), fg=COLORS["muted"], bg=COLORS["card"], wraplength=px(440),
                     justify="center").grid(row=row + 1, column=0, columnspan=2, pady=(px(4), 0))
        buttons = ttk.Frame(body)
        buttons.grid(row=row + 2, column=0, columnspan=2, pady=(px(16), 0))
        ttk.Button(buttons, text="Thực hiện", style="Danger.TButton", command=self._ok).pack(side="left",
                                                                                            padx=(0, px(8)))
        cancel = ttk.Button(buttons, text="Hủy bỏ", command=self.destroy)
        cancel.pack(side="left")
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        top = master.winfo_toplevel()
        self.geometry(f"+{top.winfo_rootx() + max((top.winfo_width() - self.winfo_width()) // 2, 0)}"
                      f"+{top.winfo_rooty() + max((top.winfo_height() - self.winfo_height()) // 3, 0)}")
        self.grab_set()
        cancel.focus_set()   # mặc định là Hủy bỏ - tránh bấm Enter xóa nhầm

    def _ok(self) -> None:
        self.confirmed = True
        self.destroy()


# =============================================================================
# Cửa sổ xem văn bản/báo cáo
# =============================================================================
class TextDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, title: str, text: str, report: Report | None = None,
                 export_dir: Path | None = None) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry(f"{px(980)}x{px(560)}")
        self.transient(master.winfo_toplevel())
        self.report = report
        self.export_dir = export_dir or Path("exports")
        from .report_view import ReportView   # nhập trong hàm để tránh vòng import
        area = ReportView(self)               # chữ bình thường, bảng thật - cùng kiểu với phần báo cáo
        area.pack(fill="both", expand=True)
        area.render_plain(text)
        buttons = ttk.Frame(self, padding=px(10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Đóng", command=self.destroy).pack(side="right")
        if report is not None:
            ttk.Button(buttons, text="Xuất CSV (Excel)", command=lambda: self._export("csv")).pack(side="right", padx=4)
            ttk.Button(buttons, text="Xuất Excel", command=lambda: self._export("xlsx")).pack(side="right", padx=4)
            ttk.Button(buttons, text="Xuất PDF", command=lambda: self._export("pdf")).pack(side="right", padx=4)
            ttk.Button(buttons, text="Xuất TXT", command=lambda: self._export("txt")).pack(side="right", padx=4)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _export(self, fmt: str) -> None:
        try:
            path = self.report.export(fmt=fmt, directory=self.export_dir)
        except KindergartenError as exc:
            messagebox.showerror("Lỗi", exc.message, parent=self)
            return
        if messagebox.askyesno("Đã xuất file", f"Đã lưu: {path}\n\nMở thư mục chứa file?", parent=self):
            open_folder(path.parent)


def open_folder(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
    except OSError:
        pass


STAT_ICONS = [("công nợ", "⚠"), ("thực thu", "₫"), ("có mặt", "✔"), ("nghỉ", "☾"), ("chuyên cần", "◷"),
              ("giáo viên", "✦"), ("trẻ", "☺"), ("lớp", "⌂")]


def stat_card(master: tk.Misc, value: str, caption: str, color: str | None = None,
              icon: str | None = None) -> tk.Frame:
    """Thẻ số liệu: chip biểu tượng màu bên trái, con số lớn và chú thích bên phải."""
    if color is None:   # tự xoay vòng màu theo vị trí thẻ để bảng tổng quan nhiều màu, dễ phân biệt
        color = COLORS[ACCENTS[len(master.winfo_children()) % len(ACCENTS)]]
    if icon is None:
        lowered = caption.lower()
        icon = next((sym for key, sym in STAT_ICONS if key in lowered), "●")
    card = tk.Frame(master, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["border"],
                    padx=px(14), pady=px(12))
    tk.Label(card, text=icon, font=icon_font(6), fg=color, bg=tint(color), width=3, pady=px(4)).pack(
        side="left", padx=(0, px(12)))
    texts = tk.Frame(card, bg=COLORS["card"])
    texts.pack(side="left", fill="x", expand=True)
    tk.Label(texts, text=value, font=ui_font(7, "bold"), fg=COLORS["navy"], bg=COLORS["card"]).pack(anchor="w")
    tk.Label(texts, text=caption, font=ui_font(-1), fg=COLORS["muted"], bg=COLORS["card"]).pack(anchor="w")
    tk.Frame(card, bg=color, width=px(4)).place(x=0, y=0, relheight=1)   # vạch màu nhấn bên trái
    return card
