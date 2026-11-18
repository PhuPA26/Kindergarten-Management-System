"""Giao diện hiện đại cho bản Tkinter: bộ style ttk dùng chung và các thành phần bố cục
(menu bên trái, ảnh đại diện chữ cái, khung giới thiệu ở màn hình đăng nhập).

Phong cách: nền xanh rất nhạt, thẻ nội dung trắng viền mảnh, nút chính màu xanh dương,
menu trái xanh navy có biểu tượng, chip màu cho số liệu.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Any, Callable, Sequence

from .widgets import COLORS, FONTS, icon_font, px, tint, ui_font


# =============================================================================
# Style ttk
# =============================================================================
_NAMED_FONTS: dict[str, tkfont.Font] = {}   # giữ tham chiếu: đối tượng Font bị thu hồi thì Tk xóa luôn phông


def _named_font(name: str, size_delta: int = 0, weight: str = "normal") -> None:
    """Tạo / cập nhật phông có tên - đổi cỡ chữ (U19) thì mọi nơi dùng phông này đổi theo."""
    options = {"family": FONTS["ui"], "size": FONTS["size"] + size_delta, "weight": weight}
    font = _NAMED_FONTS.get(name)
    if font is not None:
        try:
            font.configure(**options)
            return
        except tk.TclError:   # cửa sổ Tk cũ đã đóng (mở lại ứng dụng trong cùng tiến trình) -> tạo lại phông
            pass
    try:
        font = tkfont.nametofont(name)
        font.configure(**options)
    except tk.TclError:
        font = tkfont.Font(name=name, **options)
    _NAMED_FONTS[name] = font


def apply_theme(root: tk.Misc) -> ttk.Style:
    c = COLORS
    style = ttk.Style(root)
    if "clam" in style.theme_names():   # clam cho phép đổi màu nút, ô nhập, bảng (vista thì không)
        style.theme_use("clam")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=FONTS["ui"], size=FONTS["size"])
        except tk.TclError:
            pass
    try:
        tkfont.nametofont("TkFixedFont").configure(family=FONTS["mono"], size=FONTS["size"])
    except tk.TclError:
        pass
    for name, delta, weight in (("AppNav", 0, "normal"), ("AppNavBold", 0, "bold"), ("AppGroup", -2, "bold"),
                                ("AppPageTitle", 6, "bold"), ("AppSmall", -1, "normal"),
                                ("AppSmallBold", -1, "bold"), ("AppBrand", 2, "bold")):
        _named_font(name, delta, weight)
    line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(bg=c["bg"])

    style.configure(".", background=c["card"], foreground=c["text"], bordercolor=c["border"],
                    lightcolor=c["card"], darkcolor=c["card"], troughcolor=c["bg"], focuscolor=c["primary_light"],
                    selectbackground=c["select"], selectforeground=c["text"], insertcolor=c["primary"],
                    font="TkDefaultFont")
    # ---- khung & nhãn
    style.configure("TFrame", background=c["card"])
    style.configure("App.TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["card"], relief="flat", borderwidth=0)
    style.configure("TLabel", background=c["card"], foreground=c["text"])
    style.configure("Title.TLabel", font=ui_font(5, "bold"), foreground=c["navy"])
    style.configure("Section.TLabel", font=ui_font(1, "bold"), foreground=c["navy"])
    style.configure("Muted.TLabel", foreground=c["muted"])
    style.configure("Field.TLabel", foreground=c["label"])
    style.configure("Status.TLabel", background=c["bg"], foreground=c["muted"], font="AppSmall")
    style.configure("Card.TLabel", background=c["card"])
    style.configure("CardTitle.TLabel", background=c["card"], foreground=c["navy"], font=ui_font(5, "bold"))
    style.configure("CardMuted.TLabel", background=c["card"], foreground=c["muted"])
    style.configure("CardWarn.TLabel", background=c["card"], foreground=c["warn"])
    style.configure("Header.TFrame", background=c["card"])
    style.configure("HeaderTitle.TLabel", background=c["card"], foreground=c["navy"], font=ui_font(4, "bold"))
    style.configure("HeaderInfo.TLabel", background=c["card"], foreground=c["muted"])
    style.configure("LoginTitle.TLabel", foreground=c["navy"], font=ui_font(10, "bold"))
    style.configure("LoginSub.TLabel", foreground=c["muted"], font=ui_font(1))
    style.configure("FieldBold.TLabel", foreground=c["label"], font="AppSmallBold")
    style.configure("TSeparator", background=c["border"])

    # ---- nút
    pad = (px(14), px(6))
    style.configure("TButton", background=c["card"], foreground=c["label"], bordercolor=c["border_strong"],
                    lightcolor=c["card"], darkcolor=c["card"], relief="raised", padding=pad, anchor="center",
                    focusthickness=0)
    style.map("TButton",
              background=[("disabled", c["bg"]), ("pressed", c["primary_soft2"]), ("active", c["primary_soft"])],
              lightcolor=[("disabled", c["bg"]), ("pressed", c["primary_soft2"]), ("active", c["primary_soft"])],
              darkcolor=[("disabled", c["bg"]), ("pressed", c["primary_soft2"]), ("active", c["primary_soft"])],
              foreground=[("disabled", c["muted_light"]), ("active", c["primary_dark"])],
              bordercolor=[("disabled", c["border"]), ("focus", c["primary"]), ("active", c["primary_light"])])
    style.configure("Accent.TButton", background=c["primary"], foreground="white", bordercolor=c["primary"],
                    lightcolor=c["primary"], darkcolor=c["primary"], font=ui_font(0, "bold"))
    style.map("Accent.TButton",
              background=[("disabled", c["primary_soft2"]), ("pressed", c["navy"]), ("active", c["primary_dark"])],
              lightcolor=[("disabled", c["primary_soft2"]), ("pressed", c["navy"]), ("active", c["primary_dark"])],
              darkcolor=[("disabled", c["primary_soft2"]), ("pressed", c["navy"]), ("active", c["primary_dark"])],
              foreground=[("disabled", "white"), ("active", "white")],
              bordercolor=[("disabled", c["primary_soft2"]), ("active", c["primary_dark"]), ("focus", c["navy"])])
    style.configure("Danger.TButton", background=c["warn"], foreground="white", bordercolor=c["warn"],
                    lightcolor=c["warn"], darkcolor=c["warn"], font=ui_font(0, "bold"))
    style.map("Danger.TButton", background=[("active", "#b42318")], lightcolor=[("active", "#b42318")],
              darkcolor=[("active", "#b42318")], foreground=[("active", "white")],
              bordercolor=[("active", "#b42318"), ("focus", c["navy"])])
    style.configure("Big.Accent.TButton", padding=(px(16), px(10)), font=ui_font(1, "bold"))
    style.configure("Big.TButton", padding=(px(16), px(9)), font=ui_font(0, "bold"))
    style.configure("Link.TButton", background=c["card"], foreground=c["primary"], bordercolor=c["card"],
                    relief="flat", padding=(px(4), px(2)), font=ui_font(0, "bold"))
    style.map("Link.TButton", background=[("active", c["card"])], lightcolor=[("active", c["card"])],
              darkcolor=[("active", c["card"])], bordercolor=[("active", c["card"]), ("focus", c["card"])],
              foreground=[("active", c["primary_dark"])])

    # ---- ô nhập
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(widget, fieldbackground="white", foreground=c["text"], bordercolor=c["border_strong"],
                        lightcolor="white", darkcolor="white", background="white", arrowcolor=c["primary"],
                        padding=(px(8), px(5)), insertcolor=c["primary"], arrowsize=px(13))
        style.map(widget, bordercolor=[("focus", c["primary"]), ("hover", c["primary_light"])],
                  lightcolor=[("focus", c["primary_soft2"])],
                  fieldbackground=[("disabled", c["bg"]), ("readonly", c["head"])],
                  foreground=[("disabled", c["muted"])],
                  background=[("active", c["primary_soft"]), ("pressed", c["primary_soft2"])])
    style.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", c["bg"])],
              selectbackground=[("readonly", "white")], selectforeground=[("readonly", c["text"])],
              bordercolor=[("focus", c["primary"]), ("hover", c["primary_light"])],
              lightcolor=[("focus", c["primary_soft2"])], background=[("active", c["primary_soft"])])
    style.configure("Login.TEntry", padding=(px(10), px(8)))
    style.configure("Login.TCombobox", padding=(px(10), px(7)))

    # ---- ô tích / chọn
    for widget in ("TCheckbutton", "TRadiobutton"):
        style.configure(widget, background=c["card"], foreground=c["text"], indicatorbackground="white",
                        indicatorforeground="white", upperbordercolor=c["border_strong"],
                        lowerbordercolor=c["border_strong"], focuscolor=c["card"], indicatormargin=(0, 0, px(6), 0),
                        indicatorsize=px(16))
        style.map(widget, background=[("active", c["card"])],
                  indicatorbackground=[("selected", c["primary"]), ("active", c["primary_soft"])],
                  upperbordercolor=[("selected", c["primary"])], lowerbordercolor=[("selected", c["primary"])])
    # nút tròn: nền trắng + chấm xanh ở giữa khi được chọn (nền xanh kín bị vẽ thành vòng rỗng, khó nhận ra)
    style.map("TRadiobutton", background=[("active", c["card"])],
              indicatorbackground=[("active", c["primary_soft"]), ("selected", "white")],
              indicatorforeground=[("selected", c["primary"])],
              upperbordercolor=[("selected", c["primary"])], lowerbordercolor=[("selected", c["primary"])])

    # ---- bảng dữ liệu
    style.configure("Treeview", background="white", fieldbackground="white", foreground=c["text"],
                    bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                    rowheight=line + px(12), borderwidth=1)
    style.map("Treeview", background=[("selected", c["select"])], foreground=[("selected", c["navy"])])
    style.configure("Treeview.Heading", background=c["head"], foreground=c["label"], font=ui_font(0, "bold"),
                    relief="flat", bordercolor=c["border"], lightcolor=c["head"], darkcolor=c["head"],
                    padding=(px(8), px(7)))
    style.map("Treeview.Heading", background=[("active", c["primary_soft"])],
              lightcolor=[("active", c["primary_soft"])], darkcolor=[("active", c["primary_soft"])],
              foreground=[("active", c["primary_dark"])])

    # ---- thanh cuộn mảnh
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background="#d3dbe8", troughcolor=c["card"], bordercolor=c["card"],
                        lightcolor="#d3dbe8", darkcolor="#d3dbe8", arrowcolor=c["muted"], gripcount=0,
                        arrowsize=px(12))
        style.map(f"{orient}.TScrollbar", background=[("active", "#b3c0d4")],
                  lightcolor=[("active", "#b3c0d4")], darkcolor=[("active", "#b3c0d4")])

    # ---- notebook, labelframe, thanh tiến độ
    style.configure("TNotebook", background=c["card"], bordercolor=c["border"], lightcolor=c["card"],
                    darkcolor=c["card"], tabmargins=(0, px(4), 0, 0))
    style.configure("TNotebook.Tab", background=c["bg"], foreground=c["muted"], bordercolor=c["border"],
                    lightcolor=c["bg"], darkcolor=c["bg"], padding=(px(18), px(7)), font=ui_font(0, "bold"))
    style.map("TNotebook.Tab", background=[("selected", c["card"]), ("active", c["primary_soft"])],
              lightcolor=[("selected", c["card"])], foreground=[("selected", c["primary"]),
                                                                 ("active", c["primary_dark"])])
    style.configure("TLabelframe", background=c["card"], bordercolor=c["border"], lightcolor=c["card"],
                    darkcolor=c["card"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=c["card"], foreground=c["navy"], font=ui_font(0, "bold"))
    style.configure("TProgressbar", background=c["primary"], troughcolor=c["bg"], bordercolor=c["border"],
                    lightcolor=c["primary"], darkcolor=c["primary"])

    # ---- widget tk cổ điển (Text, Listbox, hộp thoại) dùng cùng bảng màu
    options = {
        "*Text.background": "white", "*Text.foreground": c["text"], "*Text.relief": "flat",
        "*Text.borderWidth": 0, "*Text.highlightThickness": 1, "*Text.highlightBackground": c["border"],
        "*Text.highlightColor": c["primary_light"], "*Text.selectBackground": c["select"],
        "*Text.selectForeground": c["text"], "*Text.insertBackground": c["primary"],
        "*Text.padX": px(10), "*Text.padY": px(8),
        "*Listbox.background": "white", "*Listbox.foreground": c["text"], "*Listbox.relief": "flat",
        "*Listbox.borderWidth": 0, "*Listbox.highlightThickness": 1, "*Listbox.highlightBackground": c["border"],
        "*Listbox.highlightColor": c["primary_light"], "*Listbox.selectBackground": c["primary"],
        "*Listbox.selectForeground": "white", "*Listbox.activeStyle": "none",
        "*TCombobox*Listbox.background": "white", "*TCombobox*Listbox.selectBackground": c["primary"],
        "*TCombobox*Listbox.selectForeground": "white", "*TCombobox*Listbox.highlightThickness": 0,
        "*Toplevel.background": c["card"],
    }
    for key, value in options.items():
        root.option_add(key, value)
    return style


# =============================================================================
# Thành phần vẽ
# =============================================================================
def round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float, **kw: Any) -> int:
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
              x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kw)


def initials(name: str) -> str:
    words = [w for w in str(name).split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def avatar(master: tk.Misc, name: str, size: int = 36, color: str | None = None, bg: str | None = None) -> tk.Canvas:
    """Ảnh đại diện tròn bằng chữ cái đầu (VD: Nguyễn Thị Nhung -> NN)."""
    color = color or COLORS["primary"]
    bg = bg or master.cget("bg")
    size = px(size)
    canvas = tk.Canvas(master, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
    canvas.create_oval(1, 1, size - 1, size - 1, fill=color, outline="")
    canvas.create_text(size / 2, size / 2, text=initials(name), fill="white",
                       font=(FONTS["ui"], max(FONTS["size"] - 1, 8), "bold"))
    return canvas


# =============================================================================
# Menu bên trái
# =============================================================================
class RoundPanel(tk.Canvas):
    """Khung bo góc tự giãn theo nội dung: vẽ hình chữ nhật bo tròn, đặt `inner` (Frame) lên trên.
    set_fill() đổi màu nền cả khung lẫn các widget bên trong (dùng cho mục menu đang chọn / di chuột)."""

    def __init__(self, master: tk.Misc, fill: str, radius: int = 12, padx: int = 12, pady: int = 10,
                 outline: str = "") -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, height=1)
        self.fill, self.radius, self.padx, self.pady, self.outline = fill, px(radius), px(padx), px(pady), outline
        self.inner = tk.Frame(self, bg=fill)
        self._window = self.create_window(self.padx, self.pady, window=self.inner, anchor="nw")
        self._shape: int | None = None
        self.inner.bind("<Configure>", lambda _e: self._layout())
        self.bind("<Configure>", lambda _e: self._layout())

    def _layout(self) -> None:
        width = self.winfo_width()
        height = self.inner.winfo_reqheight() + 2 * self.pady
        if int(self.cget("height")) != height:
            self.configure(height=height)
        if width > 1:
            self.itemconfigure(self._window, width=max(width - 2 * self.padx, 1))
        if self._shape is not None:
            self.delete(self._shape)
        self._shape = round_rect(self, 1, 1, max(width, 2) - 1, height - 1, self.radius, fill=self.fill,
                                 outline=self.outline or self.fill)
        self.tag_lower(self._shape)

    def set_fill(self, color: str, widgets: list[tk.Misc] | None = None) -> None:
        self.fill = color
        if self._shape is not None:
            self.itemconfigure(self._shape, fill=color, outline=self.outline or color)
        for widget in [self.inner] + list(widgets or []):
            widget.configure(bg=color)


def school_year(today: Any = None) -> str:
    """Năm học hiện tại (bắt đầu tháng 9): VD 18/11/2026 -> 'Năm học 2026 - 2027'."""
    from datetime import date
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"Năm học {start} - {start + 1}"


class Sidebar(tk.Frame):
    """Menu điều hướng nền navy, gọn kiểu ứng dụng hiện đại:
    - trên cùng: logo + thẻ phân hệ đang đăng nhập (bo góc);
    - giữa: các nhóm có tên NGẮN (Trang chính, Công việc hằng ngày, Hồ sơ & lớp học...), bấm tên nhóm để
      thu gọn / mở ra; mục chỉ có biểu tượng + tên (phím tắt Ctrl+N vẫn có trong thanh menu), mục đang mở là
      viên xanh dương bo góc;
    - chân: thẻ tài khoản (bo góc) với nút Đổi mật khẩu / Đăng xuất."""

    WIDTH = 270
    COLLAPSE_OVER = 8   # phân hệ nhiều mục hơn số này: chỉ mở sẵn nhóm đang dùng, các nhóm khác thu gọn

    def __init__(self, master: tk.Misc, title: str, subtitle: str, on_select: Callable[[int], Any],
                 caption: str = "") -> None:
        c = COLORS
        super().__init__(master, bg=c["sidebar"], width=px(self.WIDTH))
        self.pack_propagate(False)
        self.on_select = on_select
        self.items: dict[int, dict[str, Any]] = {}
        self.groups: dict[str, dict[str, Any]] = {}
        self._current_group: str | None = None
        self.active: int | None = None
        # logo + tên hệ thống
        brand = tk.Frame(self, bg=c["sidebar"], padx=px(18))
        brand.pack(fill="x", pady=(px(16), px(12)))
        logo = tk.Canvas(brand, width=px(36), height=px(36), bg=c["sidebar"], highlightthickness=0)
        round_rect(logo, 0, 0, px(36), px(36), px(10), fill=c["primary"], outline="")
        for i, color in enumerate((c["orange"], "#3ccf91", c["pink"])):   # ba chấm màu vui mắt
            x = px(9) + i * px(9)
            logo.create_oval(x - px(3), px(25) - px(3), x + px(3), px(25) + px(3), fill=color, outline="")
        logo.create_text(px(18), px(13), text="MN", fill="white", font=(FONTS["ui"], FONTS["size"] - 1, "bold"))
        logo.pack(side="left")
        names = tk.Frame(brand, bg=c["sidebar"])
        names.pack(side="left", padx=(px(10), 0))
        tk.Label(names, text=title, font="AppBrand", fg="white", bg=c["sidebar"]).pack(anchor="w")
        tk.Label(names, text="HỆ THỐNG QUẢN LÝ MẦM NON", font="AppGroup", fg=c["sidebar_group"],
                 bg=c["sidebar"]).pack(anchor="w")
        # thẻ phân hệ đang đăng nhập
        card = RoundPanel(self, c["sidebar_card"], radius=12, padx=12, pady=9)
        card.pack(fill="x", padx=px(14), pady=(0, px(8)))
        tk.Label(card.inner, text="⌂", font=icon_font(5), fg=c["primary_light"], bg=c["sidebar_card"]).pack(
            side="left", padx=(0, px(10)))
        texts = tk.Frame(card.inner, bg=c["sidebar_card"])
        texts.pack(side="left", fill="x", expand=True)
        tk.Label(texts, text=subtitle.replace("Hệ thống ", "", 1), font="AppNavBold", fg="white",
                 bg=c["sidebar_card"], anchor="w", justify="left", wraplength=px(180)).pack(fill="x")
        tk.Label(texts, text=caption or school_year(), font="AppSmall", fg=c["sidebar_text"], bg=c["sidebar_card"],
                 anchor="w").pack(fill="x")
        # chân: thẻ tài khoản - app.py đặt nội dung vào self.footer
        self.footer_card = RoundPanel(self, c["sidebar_card"], radius=14, padx=12, pady=12)
        self.footer_card.pack(side="bottom", fill="x", padx=px(14), pady=(px(6), px(14)))
        self.footer = self.footer_card.inner
        # vùng menu cuộn được
        self.canvas = tk.Canvas(self, bg=c["sidebar"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=c["sidebar"])
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_wheel(self, event: tk.Event) -> None:
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ------------------------------------------------------------------ nhóm (thu gọn được)
    def add_group(self, text: str) -> None:
        c = COLORS
        header = tk.Frame(self.inner, bg=c["sidebar"], cursor="hand2")
        header.pack(fill="x", padx=px(24), pady=(px(12), px(4)))
        label = tk.Label(header, text=text.upper(), font="AppGroup", fg=c["sidebar_group"], bg=c["sidebar"],
                         anchor="w", cursor="hand2")
        label.pack(side="left")
        arrow = tk.Label(header, text="▾", font="AppSmall", fg=c["sidebar_group"], bg=c["sidebar"], cursor="hand2")
        arrow.pack(side="right")
        body = tk.Frame(self.inner, bg=c["sidebar"])
        body.pack(fill="x")
        self.groups[text] = {"header": header, "label": label, "arrow": arrow, "body": body, "open": True,
                             "items": []}
        for widget in (header, label, arrow):
            widget.bind("<Button-1>", lambda _e, g=text: self.toggle_group(g))
            widget.bind("<Enter>", lambda _e, w=(label, arrow): [x.configure(fg=c["sidebar_text"]) for x in w])
            widget.bind("<Leave>", lambda _e, w=(label, arrow): [x.configure(fg=c["sidebar_group"]) for x in w])
        self._current_group = text

    def toggle_group(self, name: str, open_: bool | None = None) -> None:
        group = self.groups.get(name)
        if group is None:
            return
        group["open"] = (not group["open"]) if open_ is None else open_
        if group["open"]:
            group["body"].pack(fill="x", after=group["header"])
        else:
            group["body"].pack_forget()
        group["arrow"].configure(text="▾" if group["open"] else "▸")
        count = len(group["items"])
        group["label"].configure(text=group["label"].cget("text").split("  (")[0] +
                                 ("" if group["open"] else f"  ({count})"))

    def finish(self) -> None:
        """Gọi sau khi thêm hết các mục: phân hệ nhiều mục thì thu gọn sẵn các nhóm (nhóm đang dùng sẽ tự mở)."""
        if len(self.items) > self.COLLAPSE_OVER:
            for name in self.groups:
                self.toggle_group(name, False)

    # ------------------------------------------------------------------ mục
    def add_item(self, index: int, icon: str, text: str, shortcut: str = "") -> None:
        """shortcut giữ để tương thích - không hiện trên menu cho gọn (đã có trong thanh menu)."""
        c = COLORS
        parent = self.groups[self._current_group]["body"] if self._current_group else self.inner
        pill = RoundPanel(parent, c["sidebar"], radius=10, padx=12, pady=8)
        pill.pack(fill="x", padx=px(12), pady=1)
        row = pill.inner
        icon_label = tk.Label(row, text=icon, font=icon_font(2), fg=c["sidebar_icon"], bg=c["sidebar"], width=2)
        icon_label.pack(side="left")
        text_label = tk.Label(row, text=text, font="AppNav", fg=c["sidebar_text"], bg=c["sidebar"], anchor="w")
        text_label.pack(side="left", fill="x", expand=True, padx=(px(10), 0))
        widgets = [icon_label, text_label]
        self.items[index] = {"pill": pill, "widgets": widgets, "icon": icon_label, "text": text_label,
                             "frame": pill, "group": self._current_group}
        if self._current_group:
            self.groups[self._current_group]["items"].append(index)
        for widget in [pill, row] + widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _e, i=index: self.on_select(i))
            widget.bind("<Enter>", lambda _e, i=index: self._paint(i, hover=True))
            widget.bind("<Leave>", lambda _e, i=index: self._paint(i))

    def _paint(self, index: int, hover: bool = False) -> None:
        item = self.items.get(index)
        if item is None:
            return
        c = COLORS
        if index == self.active:   # viên xanh dương, chữ trắng đậm
            bg, fg, icon_fg, font = c["primary"], "white", "white", "AppNavBold"
        elif hover:
            bg, fg, icon_fg, font = c["sidebar_hover"], "white", "white", "AppNav"
        else:
            bg, fg, icon_fg, font = c["sidebar"], c["sidebar_text"], c["sidebar_icon"], "AppNav"
        item["pill"].set_fill(bg, item["widgets"])
        item["icon"].configure(fg=icon_fg)
        item["text"].configure(fg=fg, font=font)

    def set_active(self, index: int | None) -> None:
        previous, self.active = self.active, index
        if previous is not None:
            self._paint(previous)
        if index is not None:
            group = self.items.get(index, {}).get("group")
            if group and not self.groups[group]["open"]:
                self.toggle_group(group, True)
            self._paint(index)
            self.see(index)

    def see(self, index: int) -> None:
        item = self.items.get(index)
        if item is None:
            return
        self.update_idletasks()
        view = self.canvas.winfo_height()
        total = self.inner.winfo_height()
        if view <= 1 or total <= view:   # chưa hiển thị / menu vừa khung: không cần cuộn
            if view > 1:
                self.canvas.yview_moveto(0)
            else:   # cửa sổ chưa vẽ xong - thử lại khi đã có kích thước
                self.after(50, lambda: self.see(index))
            return
        frame = item["frame"]
        y = frame.winfo_rooty() - self.inner.winfo_rooty()
        top = y - px(44)   # chừa chỗ cho tên nhóm phía trên
        bottom = y + frame.winfo_height() + px(8)
        view_top, view_bottom = (f * total for f in self.canvas.yview())
        if top < view_top:
            self.canvas.yview_moveto(max(top, 0) / total)
        elif bottom > view_bottom:
            self.canvas.yview_moveto((bottom - view) / total)


def sidebar_link(master: tk.Misc, text: str, command: Callable[[], Any], color: str | None = None) -> RoundPanel:
    """Nút bo góc trong thẻ tài khoản ở chân menu (Đổi mật khẩu, Đăng xuất)."""
    c = COLORS
    color = color or c["sidebar_text"]
    button = RoundPanel(master, c["sidebar_button"], radius=10, padx=4, pady=6)
    label = tk.Label(button.inner, text=text, font="AppSmallBold", fg=color, bg=c["sidebar_button"], cursor="hand2")
    label.pack()
    for widget in (button, button.inner, label):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _e: command())
        widget.bind("<Enter>", lambda _e: (button.set_fill(c["primary"], [label]), label.configure(fg="white")))
        widget.bind("<Leave>", lambda _e: (button.set_fill(c["sidebar_button"], [label]), label.configure(fg=color)))
    return button


# =============================================================================
# Khung giới thiệu bên trái màn hình đăng nhập
# =============================================================================
FEATURES = [("Điểm danh - đón trả", "ok"), ("Nhật ký ăn ngủ", "orange"), ("Học phí - dịch vụ", "purple"),
            ("Thực đơn - dinh dưỡng", "pink"), ("Kết nối phụ huynh", "cyan"), ("Báo cáo Ban giám hiệu", "primary")]
ROLES = [("Ban giám hiệu", "⌂", "primary"), ("Giáo viên", "✎", "ok"), ("Kế toán", "₫", "purple"),
         ("Nhân viên", "✦", "orange"), ("Phụ huynh", "♥", "pink")]


class HeroPanel(tk.Canvas):
    """Nền chuyển màu xanh, tiêu đề lớn, chip tính năng và thẻ các phân hệ - vẽ lại khi đổi kích thước."""

    def __init__(self, master: tk.Misc, title: str, version: str) -> None:
        super().__init__(master, highlightthickness=0, bd=0, bg=COLORS["primary"])
        self.title, self.version = title, version
        self.bind("<Configure>", lambda _e: self.draw())

    @staticmethod
    def _blend(a: str, b: str, t: float) -> str:
        a, b = a.lstrip("#"), b.lstrip("#")
        ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
        cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
        return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(ca, cb))

    def draw(self) -> None:
        c = COLORS
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        steps = 64
        for i in range(steps):   # nền chuyển màu từ xanh sáng sang navy
            y0, y1 = h * i / steps, h * (i + 1) / steps + 1
            self.create_rectangle(0, y0, w, y1, outline="", fill=self._blend("#2f86ff", "#163f9e", i / steps))
        # hình trang trí
        self.create_oval(w - px(260), -px(160), w + px(160), px(260), outline="", fill="#3b8eff")
        self.create_oval(w - px(170), -px(70), w + px(70), px(170), outline="", fill="#56a0ff")
        self.create_oval(-px(140), h - px(220), px(200), h + px(120), outline="", fill="#1d4fb8")
        self.create_oval(w - px(90), h - px(90), w - px(54), h - px(54), outline="", fill="#ffc64d")
        self.create_oval(w - px(46), h * 0.5, w - px(28), h * 0.5 + px(18), outline="", fill="#ff8fc1")

        left = max(px(56), int(w * 0.09))
        y = max(px(48), int(h * 0.12))
        # chip nhỏ phía trên
        chip_font = (FONTS["ui"], FONTS["size"] - 2, "bold")
        chip = "HỆ THỐNG QUẢN LÝ NHÀ TRẺ - MẪU GIÁO"
        chip_w = tkfont.Font(font=chip_font).measure(chip) + px(40)
        round_rect(self, left, y, left + chip_w, y + px(30), px(15), fill="#4a97ff", outline="")
        self.create_oval(left + px(12), y + px(11), left + px(20), y + px(19), fill="#7cf0b4", outline="")
        self.create_text(left + px(28), y + px(15), text=chip, anchor="w", fill="white", font=chip_font)
        y += px(54)
        # tiêu đề lớn
        big = (FONTS["ui"], FONTS["size"] + 18, "bold")
        self.create_text(left, y, text="Quản lý trường mầm non", anchor="nw", fill="white", font=big)
        y += tkfont.Font(font=big).metrics("linespace") + px(2)
        self.create_text(left, y, text="thông minh & gần gũi", anchor="nw", fill="#ffd56b", font=big)
        y += tkfont.Font(font=big).metrics("linespace") + px(14)
        sub = (FONTS["ui"], FONTS["size"] + 2)
        text_id = self.create_text(left, y, anchor="nw", fill="#dce9ff", font=sub, width=max(w - left * 2, px(200)),
                                   text="Kết nối Nhà trường - Giáo viên - Phụ huynh trên một nền tảng: điểm danh, "
                                        "nhật ký ăn ngủ, học phí, thực đơn, sức khỏe và báo cáo - minh bạch, "
                                        "tiết kiệm thời gian mỗi ngày.")
        y = self.bbox(text_id)[3] + px(26)
        # chip tính năng
        feat_font = (FONTS["ui"], FONTS["size"], "bold")
        measure = tkfont.Font(font=feat_font).measure
        x = left
        for text, key in FEATURES:
            chip_w = measure(text) + px(46)
            if x + chip_w > w - px(30):
                x, y = left, y + px(48)
            round_rect(self, x, y, x + chip_w, y + px(36), px(18), fill="white", outline="")
            self.create_oval(x + px(14), y + px(13), x + px(24), y + px(23), fill=c[key], outline="")
            self.create_text(x + px(32), y + px(18), text=text, anchor="w", fill=c["navy"], font=feat_font)
            x += chip_w + px(10)
        y += px(70)
        # thẻ các phân hệ
        if y + px(110) < h - px(40):
            self.create_text(left, y, anchor="nw", fill="white", font=(FONTS["ui"], FONTS["size"] + 1, "bold"),
                             text="Mỗi vai trò một phân hệ riêng")
            y += px(34)
            card_w = min(px(124), (w - left * 2 - px(12) * 4) / 5)
            for i, (name, icon, key) in enumerate(ROLES):
                x0 = left + i * (card_w + px(12))
                round_rect(self, x0, y, x0 + card_w, y + px(92), px(16), fill="#ffffff", outline="")
                self.create_oval(x0 + card_w / 2 - px(19), y + px(12), x0 + card_w / 2 + px(19), y + px(50),
                                 fill=tint(c[key], 0.85), outline="")
                self.create_text(x0 + card_w / 2, y + px(31), text=icon, fill=c[key],
                                 font=(FONTS.get("icon", FONTS["ui"]), FONTS["size"] + 4))
                self.create_text(x0 + card_w / 2, y + px(70), text=name, fill=c["navy"],
                                 font=(FONTS["ui"], FONTS["size"] - 1, "bold"))
        self.create_text(left, h - px(28), anchor="w", fill="#a9c6ff", font=(FONTS["ui"], FONTS["size"] - 1),
                         text=f"{self.title}  •  phiên bản {self.version}")


def demo_values(accounts: Sequence[tuple[str, str, str]]) -> list[str]:
    return [f"{u}  —  {d}" for u, _p, d in accounts]
