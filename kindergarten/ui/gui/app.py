"""T34 - Ứng dụng Tkinter: màn hình đăng nhập và cửa sổ chính gồm các tab theo quyền của vai trò."""
from __future__ import annotations

import os
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable

from ... import APP_NAME, __version__
from ...applog import log_exception
from ...exceptions import AuthenticationError, KindergartenError, ValidationError
from ...system import KindergartenSystem
from .base_tab import BaseTab
from ...auth.user import Role
from .tabs_daily import CalendarTab, CheckInOutTab, DailyLogTab, OperationsTab, ParentContactTab, ServicesTab
from .tabs_office import FinanceTab, MenuTab, SystemTab
from .tabs_reports import ReportInboxTab, ReportSubmitTab, SchoolReportTab
from .tabs_parent import (ParentDiaryTab, ParentFeesTab, ParentHealthTab, ParentMenuTab, ParentMessagesTab,
                          ParentTodayTab)
from .tabs_people import ChildrenTab, DashboardTab, HealthTab, ParentsTab
from .tabs_school import AttendanceTab, ClassesTab, EmployeesTab, TimetableTab
from .tabs_teaching import LessonTab
from .report_view import close_drawer
from .theme import HeroPanel, Sidebar, apply_theme, avatar, demo_values, sidebar_link
from .widgets import COLORS, FONTS, Field, FormDialog, configure_fonts, detect_scale, px, ui_font

# Biểu tượng của từng màn hình trên menu trái (ký tự Unicode - có sẵn trong phông Segoe UI Symbol)
TAB_ICONS = {
    "ParentTodayTab": "☀", "ParentDiaryTab": "✎", "ParentMessagesTab": "✉", "ParentMenuTab": "♨",
    "ParentFeesTab": "₫", "ParentHealthTab": "♥",
    "OperationsTab": "⚡", "LessonTab": "♪", "CheckInOutTab": "⇄", "AttendanceTab": "✔", "DailyLogTab": "☾",
    "ParentContactTab": "✆",
    "ChildrenTab": "☺", "ParentsTab": "☻", "HealthTab": "✚", "ClassesTab": "⌂", "TimetableTab": "◷",
    "MenuTab": "♨", "FinanceTab": "₫", "ServicesTab": "★", "EmployeesTab": "✦",
    "ReportSubmitTab": "➤", "ReportInboxTab": "✉", "SchoolReportTab": "▤",
    "DashboardTab": "◉", "CalendarTab": "☷", "SystemTab": "⚙",
}
RESOURCE_DIR = Path(__file__).resolve().parents[3] / "Resource"   # biểu tượng, tài nguyên giao diện
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]

# Sơ đồ phân cấp chức năng (Hướng dẫn XD HTTTQL): 5 chức năng đỉnh - 3 chức năng chung (F1.1 Quản trị hệ thống,
# F1.2 Quản lý thông tin danh mục, F1.5 Báo cáo thống kê) + 2 chức năng nghiệp vụ riêng (F1.3, F1.4).
# Mỗi chức năng lá là một form. Mỗi vai trò chỉ thấy form mình có quyền -> mỗi vai trò một hệ thống con.
NAVIGATION: list[tuple[str, list[type[BaseTab]]]] = [
    ("F1.1 Quản trị hệ thống", [SystemTab]),
    ("F1.2 Quản lý danh mục", [ChildrenTab, ParentsTab, EmployeesTab, ClassesTab, ServicesTab, CalendarTab]),
    ("F1.3 Nghiệp vụ chăm sóc - giáo dục", [OperationsTab, LessonTab, CheckInOutTab, AttendanceTab, DailyLogTab,
                                           ParentContactTab, HealthTab, TimetableTab, MenuTab,
                                           ParentTodayTab, ParentDiaryTab, ParentMessagesTab, ParentMenuTab,
                                           ParentHealthTab]),
    ("F1.4 Nghiệp vụ tài chính", [FinanceTab, ParentFeesTab]),
    ("F1.5 Báo cáo thống kê", [DashboardTab, ReportSubmitTab, ReportInboxTab, SchoolReportTab]),
]
TAB_CLASSES: list[type[BaseTab]] = [cls for _group, classes in NAVIGATION for cls in classes]

# Tên form theo quy ước của hướng dẫn: frm + số thứ tự + _ + loại (ht / dm / nv / bc) + _ + tên
LOGIN_FORM = "frm000_dang_nhap"
_FORM_SLUGS = {
    "SystemTab": "ht_he_thong",
    "ChildrenTab": "dm_tre", "ParentsTab": "dm_phu_huynh", "EmployeesTab": "dm_nhan_su", "ClassesTab": "dm_lop_hoc",
    "ServicesTab": "dm_dich_vu", "CalendarTab": "dm_lich_nam_hoc",
    "OperationsTab": "nv_van_hanh_hom_nay", "LessonTab": "nv_so_tiet_day_bo_mon", "CheckInOutTab": "nv_don_tra_tre", "AttendanceTab": "nv_diem_danh",
    "DailyLogTab": "nv_an_ngu_sinh_hoat", "ParentContactTab": "nv_trao_doi_phu_huynh", "HealthTab": "nv_suc_khoe",
    "TimetableTab": "nv_thoi_khoa_bieu", "MenuTab": "nv_thuc_don", "ParentTodayTab": "nv_hom_nay_cua_con",
    "ParentDiaryTab": "nv_nhat_ky_cua_con", "ParentMessagesTab": "nv_trao_doi_voi_co",
    "ParentMenuTab": "nv_thuc_don_tuan", "ParentHealthTab": "nv_suc_khoe_cua_con",
    "FinanceTab": "nv_hoc_phi", "ParentFeesTab": "nv_hoc_phi_cua_con",
    "DashboardTab": "bc_tong_quan", "ReportSubmitTab": "bc_lap_gui_bao_cao", "ReportInboxTab": "bc_bao_cao_nhan_duoc",
    "SchoolReportTab": "bc_bao_cao_toan_truong",
}
FORM_CODES: dict[str, str] = {cls.__name__: f"frm{i:03d}_{_FORM_SLUGS[cls.__name__]}"
                              for i, cls in enumerate(TAB_CLASSES, 1)}
# Menu trái: gom form theo CÔNG VIỆC với tên nhóm ngắn (dễ tìm hơn tên chức năng F1.x dài).
# Mỗi phân hệ chỉ thấy nhóm / mục mình có quyền; nhóm rỗng tự ẩn.
SIDEBAR_GROUPS: list[tuple[str, list[str]]] = [
    ("Trang chính", ["DashboardTab", "OperationsTab", "LessonTab", "ParentTodayTab"]),
    ("Công việc hằng ngày", ["CheckInOutTab", "AttendanceTab", "DailyLogTab", "ParentContactTab", "HealthTab",
                             "MenuTab", "ParentDiaryTab", "ParentMessagesTab", "ParentMenuTab", "ParentHealthTab"]),
    ("Hồ sơ & lớp học", ["ChildrenTab", "ParentsTab", "ClassesTab", "TimetableTab", "EmployeesTab"]),
    ("Học phí", ["FinanceTab", "ServicesTab", "ParentFeesTab"]),
    ("Báo cáo", ["ReportSubmitTab", "ReportInboxTab", "SchoolReportTab"]),
    ("Hệ thống", ["CalendarTab", "SystemTab"]),
]
# Màn hình chính của từng phân hệ (nút Thoát của form quay về đây)
HOME_TABS = ["DashboardTab", "OperationsTab", "LessonTab", "ParentTodayTab", "FinanceTab"]


class LoginFrame(ttk.Frame):
    """Màn hình đăng nhập hai cột: bên trái giới thiệu hệ thống, bên phải biểu mẫu đăng nhập."""

    def __init__(self, master: tk.Misc, app: "KindergartenApp") -> None:
        super().__init__(master, style="App.TFrame")
        self.app = app
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2, minsize=px(480))
        self.rowconfigure(0, weight=1)
        HeroPanel(self, APP_NAME, __version__).grid(row=0, column=0, sticky="nsew")
        panel = ttk.Frame(self, style="Card.TFrame")
        panel.grid(row=0, column=1, sticky="nsew")
        form = ttk.Frame(panel, style="Card.TFrame", padding=(px(8), 0))
        form.place(relx=0.5, rely=0.47, anchor="center", width=px(400))
        form.columnconfigure(0, weight=1)

        badge = tk.Label(form, text="  ●  ĐĂNG NHẬP HỆ THỐNG  ", font="AppSmallBold", fg=COLORS["primary"],
                         bg=COLORS["primary_soft"], pady=px(4))
        badge.grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="Chào mừng trở lại!", style="LoginTitle.TLabel").grid(row=1, column=0, sticky="w",
                                                                                  pady=(px(14), px(2)))
        ttk.Label(form, text="Đăng nhập để vào đúng phân hệ của bạn.", style="LoginSub.TLabel").grid(
            row=2, column=0, sticky="w", pady=(0, px(22)))

        self.username = tk.StringVar()
        self.password = tk.StringVar()
        ttk.Label(form, text="Tên đăng nhập", style="FieldBold.TLabel").grid(row=3, column=0, sticky="w")
        user_entry = self.m_txt_username = ttk.Entry(form, textvariable=self.username, style="Login.TEntry",
                                                     font=ui_font(1))
        user_entry.grid(row=4, column=0, sticky="ew", pady=(px(4), px(14)))
        ttk.Label(form, text="Mật khẩu", style="FieldBold.TLabel").grid(row=5, column=0, sticky="w")
        self.m_txt_password = ttk.Entry(form, textvariable=self.password, show="•", style="Login.TEntry",
                                        font=ui_font(1))
        self.m_txt_password.grid(row=6, column=0, sticky="ew", pady=(px(4), px(6)))
        self.show_password = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Hiện mật khẩu", variable=self.show_password,
                        command=lambda: self.m_txt_password.configure(show="" if self.show_password.get() else "•")
                        ).grid(row=7, column=0, sticky="w")
        # Enter ở ô tên đăng nhập: chưa gõ mật khẩu thì chỉ chuyển xuống ô mật khẩu (không báo sai)
        user_entry.bind("<Return>", lambda _e: self._username_return())
        self.m_txt_password.bind("<Return>", lambda _e: self.login())
        self.m_lbl_message = ttk.Label(form, style="CardWarn.TLabel", wraplength=px(380))
        self.m_lbl_message.grid(row=8, column=0, sticky="w", pady=(px(6), 0))
        ttk.Button(form, text="Đăng nhập  →", style="Big.Accent.TButton", command=self.login, cursor="hand2").grid(
            row=9, column=0, sticky="ew", pady=(px(8), 0))

        register = ttk.Frame(form, style="Card.TFrame")
        register.grid(row=10, column=0, pady=(px(12), 0))
        ttk.Label(register, text="Chưa có tài khoản?", style="CardMuted.TLabel").pack(side="left")
        ttk.Button(register, text="Đăng ký ngay", style="Link.TButton", command=self.register, cursor="hand2").pack(
            side="left")

        # L24: chỉ gợi ý tài khoản mẫu còn đang dùng đúng mật khẩu mẫu - chọn là tự điền
        auth = app.system.auth
        self.demo = [(u, p, d) for u, p, d in app.demo_accounts if auth.uses_password(u, p)]
        if self.demo:
            box = tk.Frame(form, bg=COLORS["primary_soft"], padx=px(14), pady=px(12))
            box.grid(row=11, column=0, sticky="ew", pady=(px(22), 0))
            tk.Label(box, text="✦  Dùng thử nhanh", font="AppSmallBold", fg=COLORS["navy"],
                     bg=COLORS["primary_soft"]).pack(anchor="w")
            tk.Label(box, text="Chọn một tài khoản mẫu - hệ thống tự điền tên đăng nhập và mật khẩu.",
                     font="AppSmall", fg=COLORS["muted"], bg=COLORS["primary_soft"], wraplength=px(340),
                     justify="left").pack(anchor="w", pady=(px(2), px(8)))
            self.m_cbo_demo = ttk.Combobox(box, state="readonly", values=demo_values(self.demo),
                                         style="Login.TCombobox")
            self.m_cbo_demo.set("Chọn tài khoản dùng thử…")
            self.m_cbo_demo.pack(fill="x")
            self.m_cbo_demo.bind("<<ComboboxSelected>>", self._fill_demo)
        ttk.Label(form, text="Ban giám hiệu  •  Giáo viên  •  Kế toán  •  Nhân viên  •  Phụ huynh",
                  style="CardMuted.TLabel", font="AppSmall").grid(row=12, column=0, pady=(px(18), 0))
        user_entry.focus_set()

    def _fill_demo(self, _event: Any = None) -> None:
        index = self.m_cbo_demo.current()
        if 0 <= index < len(self.demo):
            username, password, _desc = self.demo[index]
            self.username.set(username)
            self.password.set(password)
            self.m_lbl_message.configure(text="")
            self.m_txt_password.focus_set()

    def _username_return(self) -> None:
        if self.password.get():
            self.login()
        else:
            self.m_lbl_message.configure(text="")
            self.m_txt_password.focus_set()

    def login(self) -> None:
        # Ô nào còn trống thì đưa con trỏ tới ô đó - chưa tính là đăng nhập sai (không cộng lần sai)
        if not self.username.get().strip():
            self.m_lbl_message.configure(text="Hãy nhập tên đăng nhập.")
            self.m_txt_username.focus_set()
            return
        if not self.password.get():
            self.m_lbl_message.configure(text="Hãy nhập mật khẩu.")
            self.m_txt_password.focus_set()
            return
        try:
            user = self.app.system.auth.login(self.username.get(), self.password.get())
        except AuthenticationError as exc:
            self.m_lbl_message.configure(text=exc.message)
            self.password.set("")
            self.m_txt_password.focus_set()
            return
        self.app.on_login(user)

    def register(self) -> None:
        """Tự đăng ký: phụ huynh (xác minh bằng SĐT + mã và ngày sinh của con -> dùng ngay);
        giáo viên / kế toán / nhân viên (xác minh bằng mã nhân sự + SĐT -> chờ Ban giám hiệu duyệt)."""
        kind = FormDialog(self, "Đăng ký tài khoản", [Field("kind", "Bạn là", "choice", [
            ("parent", "Phụ huynh có con đang học tại trường"),
            ("staff", "Giáo viên / Kế toán / Nhân viên của trường")], "parent", width=44)], submit_text="Tiếp tục")
        self.wait_window(kind)
        if not kind.submitted:
            return
        common = [Field("username", "Tên đăng nhập (chữ thường không dấu)"),
                  Field("password", "Mật khẩu (ít nhất 6 ký tự)", "password"),
                  Field("confirm", "Nhập lại mật khẩu", "password")]
        system = self.app.system
        if kind.result["kind"] == "parent":
            fields = common + [Field("phone", "SĐT phụ huynh đã khai với trường"),
                               Field("child_id", "Mã của con (VD: C001 - xem trên hóa đơn / hỏi cô)"),
                               Field("child_dob", "Ngày sinh của con (dd/mm/yyyy)", "date")]

            def submit(values: dict[str, Any]):
                if values.pop("confirm") != values["password"]:
                    raise ValidationError("Hai lần nhập mật khẩu không khớp.")
                return system.register_parent(**values)

            done = "Đăng ký thành công! Bạn có thể đăng nhập ngay để theo dõi con."
        else:
            fields = common + [Field("role", "Loại tài khoản", "choice",
                                     [(r, r.label) for r in (Role.TEACHER, Role.ACCOUNTANT, Role.STAFF)], Role.TEACHER),
                               Field("employee_id", "Mã nhân sự (VD: T001, NV002 - hỏi văn phòng)"),
                               Field("phone", "SĐT trong hồ sơ nhân sự")]

            def submit(values: dict[str, Any]):
                if values.pop("confirm") != values["password"]:
                    raise ValidationError("Hai lần nhập mật khẩu không khớp.")
                return system.register_staff(**values)

            done = "Đã gửi đăng ký. Tài khoản sẽ dùng được sau khi Ban giám hiệu duyệt."
        dialog = FormDialog(self, "Đăng ký tài khoản", fields, submit, "Đăng ký")
        self.wait_window(dialog)
        if dialog.submitted:
            self.app.save()
            self.username.set(dialog.result.username)
            self.password.set("")
            self.m_lbl_message.configure(text="")
            messagebox.showinfo("Đăng ký", done, parent=self)


def password_fields(with_old: bool = True) -> list[Field]:
    fields = [Field("old", "Mật khẩu hiện tại", "password")] if with_old else []
    return fields + [Field("new", "Mật khẩu mới (≥ 6 ký tự)", "password"),
                     Field("confirm", "Nhập lại mật khẩu mới", "password")]


class MainFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, app: "KindergartenApp") -> None:
        super().__init__(master, style="App.TFrame")
        self.app = app
        system = app.system
        user = system.auth.current_user
        c = COLORS
        # ---- menu trái (navy) theo nhóm công việc của phân hệ
        self.sidebar = Sidebar(self, "Mầm Non", system.auth.portal_of(user), self.select_tab)
        self.sidebar.pack(side="left", fill="y")
        footer = self.sidebar.footer   # thẻ tài khoản bo góc ở chân menu
        card_bg = c["sidebar_card"]
        who = tk.Frame(footer, bg=card_bg)
        who.pack(fill="x")
        avatar(who, user.full_name, 38, color=c["orange"], bg=card_bg).pack(side="left")
        names = tk.Frame(who, bg=card_bg)
        names.pack(side="left", fill="x", expand=True, padx=(px(10), 0))
        tk.Label(names, text=user.full_name, font="AppNavBold", fg="white", bg=card_bg, anchor="w",
                 wraplength=px(160), justify="left").pack(fill="x")
        role = system.auth.role_label(user)
        teacher = system.teacher_of(user)
        if teacher is not None and teacher.homeroom_class_id:
            role += f" • {system.classes.class_name(teacher.homeroom_class_id)}"
        elif teacher is not None and teacher.specialty:
            role += f" • {teacher.specialty}"
        tk.Label(names, text=role, font="AppSmall", fg=c["sidebar_text"], bg=card_bg, anchor="w",
                 wraplength=px(160), justify="left").pack(fill="x")
        links = tk.Frame(footer, bg=card_bg)
        links.pack(fill="x", pady=(px(10), 0))
        links.columnconfigure((0, 1), weight=1, uniform="links")
        sidebar_link(links, "✎  Đổi mật khẩu", self.change_password).grid(row=0, column=0, sticky="ew")
        sidebar_link(links, "↩  Đăng xuất", app.logout, color="#ffb4a8").grid(row=0, column=1, sticky="ew",
                                                                               padx=(px(6), 0))

        # ---- vùng phải: thanh tiêu đề + nội dung
        right = self.right = ttk.Frame(self, style="App.TFrame")   # mọi thứ trừ menu trái (khung báo cáo phủ lên đây)
        right.pack(side="left", fill="both", expand=True)
        topbar = tk.Frame(right, bg=c["card"], padx=px(24), pady=px(12))
        topbar.pack(fill="x")
        tk.Frame(right, bg=c["border"], height=1).pack(fill="x")
        titles = tk.Frame(topbar, bg=c["card"])
        titles.pack(side="left")
        self.m_lbl_crumb = tk.Label(titles, font="AppSmall", fg=c["muted"], bg=c["card"])
        self.m_lbl_crumb.pack(anchor="w")
        self.m_lbl_page_title = tk.Label(titles, font="AppPageTitle", fg=c["navy"], bg=c["card"])
        self.m_lbl_page_title.pack(anchor="w")
        ttk.Button(topbar, text="✓  Lưu dữ liệu", style="Accent.TButton", cursor="hand2",
                   command=lambda: app.save(notify=True)).pack(side="right")
        today = date.today()
        tk.Label(topbar, text=f"◷  {WEEKDAYS[today.weekday()]}, {today:%d/%m/%Y}", font="AppSmallBold",
                 fg=c["primary"], bg=c["primary_soft"], padx=px(12), pady=px(6)).pack(side="right", padx=px(12))
        self.m_lbl_sync = tk.Label(topbar, font="AppSmall", bg=c["card"], fg=c["muted"], text="")
        self.m_lbl_sync.pack(side="right", padx=(0, px(4)))

        # Dòng trạng thái như mẫu form nghiệp vụ của hướng dẫn: người sử dụng - ngày giờ - phiên bản - dữ liệu
        location = str(getattr(system.store, "location", system.store.data_dir))
        if len(location) > 55:
            location = "…" + location[-50:]
        self._status_tail = f"Phiên bản {__version__}   •   Dữ liệu: {location}"
        self.m_lbl_status = ttk.Label(right, style="Status.TLabel", padding=(px(24), 0, px(24), px(8)))
        self.m_lbl_status.pack(side="bottom", fill="x")
        self._tick_clock()
        wrap = ttk.Frame(right, style="App.TFrame", padding=(px(20), px(16), px(20), px(10)))
        wrap.pack(fill="both", expand=True)
        self.content = tk.Frame(wrap, bg=c["card"], highlightthickness=1, highlightbackground=c["border"])
        self.content.pack(fill="both", expand=True)

        self.tabs: list[BaseTab] = []
        self.groups: list[str] = []
        self.current: BaseTab | None = None
        for group, classes in NAVIGATION:   # thứ tự form, mã form, thanh menu: theo sơ đồ chức năng F1.x
            for tab_class in classes:
                if tab_class.permission is None or system.auth.has_permission(tab_class.permission):
                    self.tabs.append(tab_class(self.content, app))
                    self.groups.append(group)
        # menu trái: nhóm theo công việc, tên ngắn gọn (mã F1.x vẫn hiện ở đường dẫn trên tiêu đề form)
        index_of = {type(tab).__name__: i for i, tab in enumerate(self.tabs)}
        for group, names in SIDEBAR_GROUPS:
            present = [n for n in names if n in index_of]
            if not present:
                continue
            self.sidebar.add_group(group)
            for name in present:
                i = index_of[name]
                self.sidebar.add_item(i, TAB_ICONS.get(name, "•"), self.tabs[i].title)
        self.sidebar.finish()
        self._build_menu()
        if self.tabs:
            self.go_home()

    # ------------------------------------------------------------------ thanh menu (control Menu của hướng dẫn)
    def _build_menu(self) -> None:
        root = self.winfo_toplevel()
        font = ("Segoe UI", 10)
        menubar = tk.Menu(root, font=font)
        system_menu = tk.Menu(menubar, tearoff=False, font=font)
        system_menu.add_command(label="Đổi mật khẩu", command=self.change_password)
        system_menu.add_command(label="Lưu dữ liệu", accelerator="Ctrl+S",
                                command=lambda: self.app.save(notify=True))
        system_menu.add_separator()
        system_menu.add_command(label="Đăng xuất", command=self.app.logout)
        system_menu.add_command(label="Thoát chương trình", command=self.app.on_close)
        menubar.add_cascade(label="Hệ thống", menu=system_menu)
        groups: dict[str, tk.Menu] = {}
        for index, (tab, group) in enumerate(zip(self.tabs, self.groups)):
            if group not in groups:
                groups[group] = tk.Menu(menubar, tearoff=False, font=font)
                menubar.add_cascade(label=group.split(" ", 1)[1], menu=groups[group])   # bỏ mã F1.x cho gọn
            code = FORM_CODES.get(type(tab).__name__, "")
            groups[group].add_command(label=f"{tab.title}", accelerator=f"Ctrl+{index + 1}" if index < 9 else code,
                                      command=lambda i=index: self.select_tab(i))
        help_menu = tk.Menu(menubar, tearoff=False, font=font)
        help_menu.add_command(label="Sơ đồ chức năng của phân hệ", command=self.show_function_map)
        help_menu.add_command(label="Giới thiệu", command=lambda: messagebox.showinfo(
            "Giới thiệu", f"{APP_NAME}\nPhiên bản {__version__}", parent=self))
        menubar.add_cascade(label="Trợ giúp", menu=help_menu)
        root.configure(menu=menubar)

    def show_function_map(self) -> None:
        """Cây chức năng (F1.x -> form) của phân hệ đang đăng nhập."""
        lines, last = [], None
        for tab, group in zip(self.tabs, self.groups):
            if group != last:
                lines.append(("\n" if last else "") + group)
                last = group
            lines.append(f"    • {tab.title}  ({FORM_CODES.get(type(tab).__name__, '')})")
        messagebox.showinfo("Sơ đồ chức năng", "\n".join(lines), parent=self)

    def _tick_clock(self) -> None:
        from datetime import datetime
        if not self.winfo_exists():
            return
        user = self.app.system.auth.current_user
        now = datetime.now()
        who = f"Người sử dụng: {user.username} ({self.app.system.auth.role_label(user)})" if user else ""
        self.m_lbl_status.configure(text=f"{who}   •   {WEEKDAYS[now.weekday()]} {now:%d/%m/%Y %H:%M:%S}   •   "
                                   f"{self._status_tail}")
        self.after(1000, self._tick_clock)

    def go_home(self) -> None:
        """Màn hình chính của phân hệ (nút Thoát trên các form quay về đây)."""
        names = [type(t).__name__ for t in self.tabs]
        home = next((names.index(n) for n in HOME_TABS if n in names), 0)
        self.select_tab(home)

    def select_tab(self, index: int) -> None:
        if 0 <= index < len(self.tabs):
            self._show(index)

    def show_tab(self, class_name: str) -> bool:
        for index, tab in enumerate(self.tabs):
            if type(tab).__name__ == class_name:
                self.select_tab(index)
                return True
        return False

    def _show(self, index: int) -> None:
        tab = self.tabs[index]
        if tab is self.current:
            return
        if self.current is not None:
            if hasattr(self.current, "confirm_discard") and not self.current.confirm_discard():
                return
            self.current.pack_forget()
        close_drawer(self.right)   # đổi màn hình thì đóng khung báo cáo đang mở
        tab.pack(fill="both", expand=True)
        self.current = tab
        self.sidebar.set_active(index)
        self.m_lbl_page_title.configure(text=tab.title)
        code = FORM_CODES.get(type(tab).__name__, "")
        self.m_lbl_crumb.configure(text=f"{self.app.system.auth.current_user.portal}   ›   {self.groups[index]}   ›   {code}")
        self.winfo_toplevel().title(f"{APP_NAME} - {tab.title} [{code}]")
        try:
            tab.refresh()
        except KindergartenError as exc:
            messagebox.showerror("Lỗi", exc.message, parent=self)

    def after_sync(self, writer: str = "") -> None:
        """Sau khi tải lại dữ liệu người khác vừa lưu: làm mới màn hình đang mở và báo nhẹ trên thanh tiêu đề."""
        from datetime import datetime
        who = writer.split(" @ ")[0] if writer else "cửa sổ chương trình khác"
        self.m_lbl_sync.configure(text=f"↻ Đã cập nhật thay đổi của {who} lúc {datetime.now():%H:%M:%S}",
                                  fg=COLORS["ok"])
        if self.current is not None:
            try:
                self.current.refresh()
            except KindergartenError:
                pass

    def _on_tab_changed(self, _event: Any = None) -> None:   # tương thích với mã cũ
        if self.current is not None:
            self.current.refresh()

    def unsaved_tabs(self) -> list[BaseTab]:
        return [t for t in self.tabs if getattr(t, "has_unsaved", lambda: False)()]

    def change_password(self, forced: bool = False) -> bool:
        auth = self.app.system.auth

        def submit(values: dict[str, Any]) -> None:
            if values["new"] != values["confirm"]:
                raise ValidationError("Hai lần nhập mật khẩu mới không khớp.")
            if values["new"] == values["old"]:
                raise ValidationError("Mật khẩu mới phải khác mật khẩu hiện tại.")
            auth.change_password(values["old"], values["new"])

        title = "Bắt buộc đổi mật khẩu" if forced else "Đổi mật khẩu"
        dialog = FormDialog(self, title, password_fields(), submit)
        self.wait_window(dialog)
        if dialog.submitted:
            self.app.system.audit("Đổi mật khẩu", self.app.system.username)
            self.app.save()
            messagebox.showinfo("Thành công", "Đã đổi mật khẩu.", parent=self)
        return dialog.submitted


class KindergartenApp:
    def __init__(self, system: KindergartenSystem, seed_func: Callable[[KindergartenSystem], Any] | None = None,
                 demo_accounts: list[tuple[str, str, str]] | None = None, root: tk.Tk | None = None) -> None:
        self.system = system
        self.seed_func = seed_func
        self.demo_accounts = demo_accounts or []
        self.export_dir = Path(system.store.data_dir).resolve().parent / "exports"
        self.log_dir = Path(system.store.data_dir).resolve().parent / "logs"
        self.root = root or tk.Tk()
        self.root.title(f"{APP_NAME} - phiên bản {__version__}")
        icon = RESOURCE_DIR / "Icons" / "app.png"   # Solution Folder "Resource" (Hướng dẫn XD HTTTQL)
        if icon.exists():
            try:
                self._icon = tk.PhotoImage(file=str(icon))
                self.root.iconphoto(True, self._icon)
            except tk.TclError:
                pass
        detect_scale(self.root)   # màn hình 125% / 150%: phóng kích thước theo tỷ lệ, không bị thu nhỏ
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = min(px(1366), screen_w - 40), min(px(820), screen_h - 80)
        self.root.geometry(f"{width}x{height}+{max((screen_w - width) // 2, 0)}+{max((screen_h - height) // 3, 0)}")
        self.root.minsize(min(px(1000), screen_w - 40), min(px(620), screen_h - 80))
        if os.name == "nt":
            try:
                self.root.state("zoomed")   # mở toàn màn hình (vẫn thu nhỏ / kéo lại được)
            except tk.TclError:
                pass
        configure_fonts()   # U19: phông dự phòng khi máy không có Segoe UI / Consolas
        self._setup_style()
        self.container = ttk.Frame(self.root, style="App.TFrame")
        self.container.pack(fill="both", expand=True)
        self.main: MainFrame | None = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.report_callback_exception = self._report_error
        for number in range(1, 10):
            self.root.bind_all(f"<Control-Key-{number}>", lambda _e, i=number - 1: self._select_tab(i))
        self.root.bind_all("<Control-s>", lambda _e: self.save(notify=True) if self.main else None)
        self._first_run()
        self.show_login()
        self.root.after(self.SYNC_INTERVAL_MS, self._sync_tick)

    # ------------------------------------------------------------------ giao diện chung
    def _setup_style(self) -> None:
        """Bộ giao diện chung (theme.py): nền xanh nhạt, thẻ trắng, nút xanh dương, bảng thoáng."""
        apply_theme(self.root)

    def set_font_size(self, size: int) -> None:
        """U19: đổi cỡ chữ toàn ứng dụng (áp dụng ngay cho widget ttk; bảng/khung chữ mới mở dùng cỡ mới)."""
        FONTS["size"] = max(8, min(int(size), 18))
        self._setup_style()

    def _report_error(self, exc_type: type, exc: BaseException, tb: Any) -> None:
        if isinstance(exc, KindergartenError):
            messagebox.showerror("Lỗi", exc.message, parent=self.root)
            return
        exc.__traceback__ = tb
        log = log_exception(self.log_dir, exc)   # U19: dùng chung logger xoay vòng với bản console
        messagebox.showerror("Lỗi không mong muốn", f"{exc!r}\nChi tiết đã ghi vào {log}", parent=self.root)

    def _select_tab(self, index: int) -> None:
        if self.main is not None:
            self.main.select_tab(index)

    def show_tab(self, class_name: str | None) -> None:
        if self.main is not None and class_name and not self.main.show_tab(class_name):
            messagebox.showinfo("Không có quyền", "Phân hệ của bạn không có màn hình này.", parent=self.root)

    def _clear(self) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()
        self.main = None
        self.root.configure(menu="")   # màn hình đăng nhập không có thanh menu
        self.root.title(f"{APP_NAME} - phiên bản {__version__} [{LOGIN_FORM}]")

    def _first_run(self) -> None:
        if len(self.system.auth) > 0:
            return
        if self.seed_func is not None and messagebox.askyesno(
                "Lần chạy đầu tiên", "Chưa có dữ liệu. Nạp dữ liệu mẫu (20 trẻ, 3 lớp, 5 giáo viên...) để dùng thử?"):
            self.seed_func(self.system)
        else:
            self.system.auth.ensure_default_admin()
            messagebox.showinfo("Tài khoản quản trị", "Đã tạo tài khoản admin / admin123.\n"
                                                      "Bạn sẽ phải đổi mật khẩu ở lần đăng nhập đầu tiên.")
        self.save()

    # ------------------------------------------------------------------ điều hướng
    def show_login(self, save: bool = False) -> None:
        if save:
            self.save()
        self._clear()
        self.system.auth.logout()
        LoginFrame(self.container, self).pack(fill="both", expand=True)

    def on_login(self, user: Any) -> None:
        self._clear()
        self.main = MainFrame(self.container, self)
        self.main.pack(fill="both", expand=True)
        if getattr(user, "must_change_password", False):   # L24: mật khẩu mặc định / vừa được đặt lại
            messagebox.showwarning("Đổi mật khẩu", "Tài khoản đang dùng mật khẩu mặc định hoặc vừa được đặt lại.\n"
                                                   "Bạn phải đổi mật khẩu trước khi tiếp tục.", parent=self.root)
            if not self.main.change_password(forced=True):
                self.show_login()
                return

    def _confirm_unsaved(self) -> bool:
        """U15: còn điểm danh chưa lưu thì hỏi trước khi thoát."""
        if self.main is None:
            return True
        return all(tab.confirm_discard() for tab in self.main.unsaved_tabs())

    def unsaved_items(self) -> list[str]:
        """Liệt kê những gì chưa được lưu: màn hình đang sửa dở + thay đổi trong bộ nhớ chưa ghi vào CSDL."""
        items: list[str] = []
        if self.main is not None:
            for tab in self.main.unsaved_tabs():
                label = getattr(tab, "unsaved_label", None)
                items.append(label() if callable(label) else f"Màn hình {tab.title} đang sửa dở")
        pending = getattr(self.system.store, "pending_changes", None)
        if callable(pending):
            try:
                count = pending(self.system)
            except Exception:   # noqa: BLE001 - không kiểm tra được thì coi như không có
                count = 0
            if count:
                items.append(f"{count} thay đổi dữ liệu chưa ghi vào CSDL")
        return items

    def logout(self) -> None:
        """Đăng xuất: hỏi có lưu dữ liệu chưa được lưu không (Có = lưu, Không = bỏ thay đổi, Hủy = ở lại)."""
        items = self.unsaved_items()
        if not items:
            if messagebox.askyesno("Đăng xuất", "Mọi dữ liệu đã được lưu.\nBạn có chắc muốn đăng xuất?",
                                   parent=self.root):
                self.show_login()
            return
        listing = "\n".join(f"  •  {item}" for item in items)
        answer = messagebox.askyesnocancel(
            "Đăng xuất - còn dữ liệu chưa lưu",
            f"Còn dữ liệu chưa được lưu:\n{listing}\n\nBạn có muốn lưu trước khi đăng xuất không?\n\n"
            "Có = lưu rồi đăng xuất\nKhông = bỏ các thay đổi và đăng xuất\nHủy = ở lại làm tiếp",
            icon="warning", parent=self.root)
        if answer is None:
            return
        tabs = self.main.unsaved_tabs() if self.main is not None else []
        if answer:
            for tab in tabs:
                save_tab = getattr(tab, "save_unsaved", None)
                if callable(save_tab) and not save_tab():
                    return   # lưu lỗi -> ở lại để người dùng xử lý
            if not self.save():
                return
        else:
            for tab in tabs:
                discard = getattr(tab, "discard_unsaved", None)
                if callable(discard):
                    discard()
            self._discard_memory()
        self.show_login()

    def _discard_memory(self) -> None:
        """Bỏ các thay đổi chưa lưu trong bộ nhớ: nạp lại dữ liệu đang có trong CSDL."""
        try:
            self.system.load()
        except KindergartenError as exc:
            messagebox.showerror("Không tải lại được dữ liệu", exc.message, parent=self.root)

    def save(self, notify: bool = False) -> bool:
        store = self.system.store
        try:
            path = self.system.save()
        except KindergartenError as exc:
            if getattr(store, "needs_reload", False):   # cửa sổ khác vừa thêm dữ liệu trùng mã
                messagebox.showwarning("Dữ liệu vừa được cập nhật ở cửa sổ khác", exc.message, parent=self.root)
                self.sync_from_db()
                return False
            messagebox.showerror("Không lưu được dữ liệu", f"{exc.message}\n\nDữ liệu vẫn còn trong bộ nhớ - hãy "
                                 "kiểm tra kết nối CSDL rồi bấm 'Lưu dữ liệu' lại.", parent=self.root)
            return False
        if getattr(store, "needs_reload", False):   # đã lưu phần của mình; cửa sổ khác cũng vừa lưu -> lấy phần đó
            self.sync_from_db()
        if notify:
            messagebox.showinfo("Đã lưu", f"Đã lưu dữ liệu vào {path}", parent=self.root)
        return True

    # ------------------------------------------------------------------ nhiều cửa sổ cùng một file CSDL
    SYNC_INTERVAL_MS = 4000

    def _sync_tick(self) -> None:
        """Mỗi vài giây kiểm tra cửa sổ chương trình khác (cùng file CSDL) có lưu thay đổi không; có thì tải lại khi đang rảnh tay."""
        try:
            store = self.system.store
            busy = self.root.grab_current() is not None or (self.main is not None and self.main.unsaved_tabs())
            if not busy and hasattr(store, "has_remote_changes") and store.has_remote_changes():
                self.sync_from_db()
        except Exception:   # noqa: BLE001 - mất mạng tạm thời: bỏ qua lần này, thử lại lần sau
            pass
        finally:
            self.root.after(self.SYNC_INTERVAL_MS, self._sync_tick)

    def sync_from_db(self) -> None:
        """Tải lại dữ liệu mới nhất mà vẫn giữ người đang đăng nhập và màn hình đang mở."""
        writer = getattr(self.system.store, "last_writer", "")
        try:
            still_valid = self.system.reload_keep_session()
        except KindergartenError as exc:
            messagebox.showerror("Không tải lại được dữ liệu", exc.message, parent=self.root)
            return
        if self.main is None:
            return
        if not still_valid:
            messagebox.showwarning("Tài khoản bị thay đổi", "Tài khoản của bạn vừa bị khóa hoặc xóa ở cửa sổ chương trình khác. "
                                   "Vui lòng đăng nhập lại.", parent=self.root)
            self.show_login()
            return
        self.main.after_sync(writer)

    def on_close(self) -> None:
        if not self._confirm_unsaved():
            return
        while not self.save():   # L21: lưu lỗi thì cho thử lại hoặc chủ động thoát không lưu
            answer = messagebox.askretrycancel("Chưa lưu được", "Thử lưu lại?\n(Hủy = thoát KHÔNG lưu - mất các "
                                                                "thay đổi kể từ lần lưu gần nhất)", parent=self.root)
            if not answer:
                if messagebox.askyesno("Thoát không lưu", "Chắc chắn thoát mà không lưu?", parent=self.root):
                    break
                return
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui(system: KindergartenSystem, seed_func: Callable[[KindergartenSystem], Any] | None = None,
            demo_accounts: list[tuple[str, str, str]] | None = None) -> None:
    try:  # chữ sắc nét trên màn hình độ phân giải cao (Windows)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    KindergartenApp(system, seed_func, demo_accounts).run()
