"""Các tab vận hành hằng ngày: Vận hành hôm nay (6 bước + báo cáo cuối ngày), Đón - trả trẻ, Ăn ngủ - sinh hoạt,
Trao đổi phụ huynh; cùng các tab danh mục Dịch vụ và Lịch năm học."""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from ...auth.user import Permission
from ...daily.daily_manager import DAILY_STEPS
from ...daily.records import MEAL_LEVELS, MEALS, MOODS, NAP_LEVELS, MessageKind, MessageStatus
from ...exceptions import KindergartenError
from ...reports.reports import EndOfDayReport
from ...utils import WEEKDAY_NAMES, format_date, format_vnd, parse_date, validate_not_future, weekday_name
from .base_tab import BaseTab
from .report_view import ReportView
from .widgets import COLORS, DataTable, Field, mono_font, px, ui_font

P = Permission
STEP_COLORS = ["#2563eb", "#059669", "#d97706", "#ea580c", "#7c3aed", "#0284c7"]


def _hhmm(stamp: str) -> str:
    return stamp[11:16] if stamp and len(stamp) >= 16 else ""


class ClassDayMixin:
    """Thanh chọn lớp + ngày dùng chung cho các tab vận hành."""

    def _class_day_bar(self: Any, allow_date: bool = True) -> ttk.Frame:
        bar = self.bar()
        ttk.Label(bar, text="Lớp:").pack(side="left")
        self.m_cbo_class = ttk.Combobox(bar, state="readonly", width=28)
        self.m_cbo_class.pack(side="left", padx=(4, 12))
        self.m_cbo_class.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.day_var = tk.StringVar(value=format_date(date.today()))
        if allow_date:
            ttk.Label(bar, text="Ngày:").pack(side="left")
            entry = ttk.Entry(bar, textvariable=self.day_var, width=12)
            entry.pack(side="left", padx=4)
            entry.bind("<Return>", lambda _e: self.refresh())
            ttk.Button(bar, text="Hôm nay", command=self._today).pack(side="left", padx=(0, 12))
        self.m_lbl_info = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_info.pack(side="left", padx=8)
        return bar

    def _today(self: Any) -> None:
        self.day_var.set(format_date(date.today()))
        self.refresh()

    def _load_classes(self: Any) -> None:
        options = [f"{c.id} - {c.name}" for c in self.system.classes_for(self.user)]
        self.m_cbo_class["values"] = options
        if self.m_cbo_class.get() not in options:
            self.m_cbo_class.set(options[0] if options else "")

    def _class_id(self: Any) -> str | None:
        return self.m_cbo_class.get().split(" - ")[0] if self.m_cbo_class.get() else None

    def _day(self: Any) -> date | None:
        try:
            return validate_not_future(self.day_var.get(), "Ngày")
        except KindergartenError as exc:
            self.m_lbl_info.configure(text=exc.message)
            return None


# =============================================================================
class OperationsTab(BaseTab):
    """Vận hành hôm nay: 6 bước trong ngày và báo cáo cuối ngày tự tổng hợp."""

    title = "Vận hành hôm nay"
    group = "Vận hành hằng ngày"
    permission = P.VIEW_OPERATIONS
    STEP_TABS = {"checkin": "CheckInOutTab", "attendance": "AttendanceTab", "dailylog": "DailyLogTab",
                 "contact": "ParentContactTab", "pickup": "CheckInOutTab", "report": "__report__"}

    def build(self) -> None:
        bar = self.bar()
        self.m_lbl_heading = ttk.Label(bar, style="Title.TLabel")
        self.m_lbl_heading.pack(side="left")
        self.button(bar, "Làm mới", self.refresh, side="right")
        self.cards_frame = ttk.Frame(self)
        self.cards_frame.pack(fill="x", pady=(4, 8))
        for column in range(len(DAILY_STEPS)):
            self.cards_frame.columnconfigure(column, weight=1, uniform="step")
        self.cards: list[dict[str, Any]] = []
        for index, step in enumerate(DAILY_STEPS):
            color = STEP_COLORS[index]
            card = tk.Frame(self.cards_frame, bg=COLORS["card"], highlightthickness=2, highlightbackground="#dbe3f0")
            card.grid(row=0, column=index, sticky="nsew", padx=4)
            tk.Label(card, text=f" {step.number} ", font=ui_font(4, "bold"), fg="white", bg=color).pack(pady=(8, 2))
            tk.Label(card, text=step.title, font=ui_font(1, "bold"), bg=COLORS["card"]).pack()
            tk.Label(card, text=step.time_text, font=ui_font(-1, "bold"), fg=color, bg=COLORS["card"]).pack()
            phase = tk.Label(card, font=ui_font(-1), bg=COLORS["card"])
            phase.pack()
            progress = tk.Label(card, font=ui_font(-1), fg=COLORS["muted"], bg=COLORS["card"], wraplength=px(150),
                                justify="center")
            progress.pack(padx=6, pady=(2, 4))
            target = self.STEP_TABS[step.key]
            button = ttk.Button(card, text="Mở", command=lambda t=target: self.open_step(t))
            button.pack(pady=(0, 8))
            self.cards.append({"frame": card, "phase": phase, "progress": progress, "color": color})
        actions = self.bar(pady=(4, 4))
        self.m_lbl_report_title = ttk.Label(actions, style="Section.TLabel")
        self.m_lbl_report_title.pack(side="left")
        self.m_btn_report = ttk.Button(actions, style="Accent.TButton", command=self.report_action)
        self.m_btn_report.pack(side="right")
        self.reviewer = self.can(P.REVIEW_REPORTS)
        if self.reviewer:   # Ban giám hiệu: lớp nào đã gửi / chưa gửi báo cáo cuối ngày
            self.m_fg_report = DataTable(self, [("Lớp", 160), ("GV chủ nhiệm", 200), ("Báo cáo cuối ngày", 160),
                                                 ("Gửi lúc", 90), ("Ghi chú của giáo viên", 420)], height=6)
            self.m_fg_report.pack(fill="both", expand=True)
        else:               # Giáo viên: xem trước báo cáo cuối ngày của lớp mình rồi gửi BGH
            self.m_txt_report = ReportView(self, height=14)
            self.m_txt_report.configure(highlightthickness=1, highlightbackground=COLORS["border"])
            self.m_txt_report.pack(fill="both", expand=True)

    def refresh(self) -> None:
        today = date.today()
        now = datetime.now()
        scope = self.scope_class_ids()
        school_day = self.system.calendar.is_school_day(today)
        note = "" if school_day else f" - {self.system.calendar.reason_not_school_day(today)}"
        self.m_lbl_heading.configure(text=f"{weekday_name(today)} {format_date(today)}  •  {now:%H:%M}{note}")
        for card, item in zip(self.cards, self.system.daily.step_progress(scope)):
            phase = item["phase"]
            done = item["complete"]
            card["phase"].configure(text=("✔ Hoàn thành" if done else phase),
                                    fg=COLORS["ok"] if done else (card["color"] if phase == "Đang diễn ra"
                                                                  else COLORS["muted"]))
            card["progress"].configure(text=item["text"] if school_day else "Không phải ngày học")
            card["frame"].configure(highlightbackground=card["color"] if phase == "Đang diễn ra" else "#dbe3f0")
        status = self.system.reports.end_of_day_status(today, scope)
        if self.reviewer:
            self.m_lbl_report_title.configure(text=f"⑥ Báo cáo cuối ngày các lớp gửi Ban giám hiệu: "
                                             f"{len(status['sent'])}/{len(status['classes'])} lớp")
            self.m_btn_report.configure(text="Mở hộp báo cáo nhận được")
            rows, tags = [], []
            for classroom in status["classes"]:
                item = status["sent"].get(classroom.id)
                teacher = self.system.classes.homeroom_teacher(classroom.id)
                rows.append([classroom.name, teacher.full_name if teacher else "-",
                             item.status.value if item else "CHƯA GỬI", item.sent_at[11:16] if item else "",
                             item.note if item else ""])
                tags.append("ok" if item else "warn" if now.hour >= 17 else None)
            self.m_fg_report.set_rows(rows, [c.id for c in status["classes"]], tags)
        else:
            sent = bool(status["sent"]) and len(status["sent"]) >= len(status["classes"])
            self.m_lbl_report_title.configure(text="⑥ Báo cáo cuối ngày của lớp - " +
                                             ("ĐÃ GỬI Ban giám hiệu" if sent else "chưa gửi Ban giám hiệu"))
            self.m_btn_report.configure(text="Lập & gửi báo cáo cuối ngày (thêm ghi chú)")
            self.m_txt_report.render_report(EndOfDayReport(self.system, today, scope))

    def open_step(self, target: str) -> None:
        if target == "__report__":
            self.report_action()
        else:
            self.app.show_tab(target)

    def report_action(self) -> None:
        if self.can(P.REVIEW_REPORTS):
            self.app.show_tab("ReportInboxTab")
        elif self.app.main is not None and self.app.main.show_tab("ReportSubmitTab"):
            self.app.main.current.select_type("end_of_day")


# =============================================================================
class CheckInOutTab(ClassDayMixin, BaseTab):
    """Bước 1 (đón trẻ đầu ngày) và bước 5 (trả trẻ cuối ngày).

    Đồng bộ với điểm danh: CHƯA ĐÓN = VẮNG; đón trẻ = CÓ MẶT. Khi trả trẻ, chỉ những trẻ có mặt mới ở lớp nên chỉ
    những trẻ đó được trả; trẻ vắng hiện mờ và không thao tác được.
    """

    title = "Đón - trả trẻ"
    group = "Vận hành hằng ngày"
    permission = P.CHECK_IN_OUT

    def build(self) -> None:
        self._class_day_bar(allow_date=False)
        mode_bar = self.bar()
        self.mode = tk.StringVar(value="in" if datetime.now().hour < 12 else "out")
        ttk.Radiobutton(mode_bar, text="① Đón trẻ đầu ngày (07:00 - 08:00)", value="in", variable=self.mode,
                        command=self._mode_changed).pack(side="left")
        ttk.Radiobutton(mode_bar, text="⑤ Trả trẻ cuối ngày (16:00 - 17:00)", value="out", variable=self.mode,
                        command=self._mode_changed).pack(side="left", padx=16)
        self.m_lbl_hint = ttk.Label(mode_bar, style="Muted.TLabel")
        self.m_lbl_hint.pack(side="right")
        self.m_fg_list = DataTable(self, [("STT", 45, "center"), ("Mã", 60), ("Họ tên", 180), ("Trạng thái", 210),
                                      ("Người đưa / đón", 220), ("Ghi chú", 280)], checkable=True)
        self.m_fg_list.pack(fill="both", expand=True)
        # Đón trẻ: bấm vào dòng của trẻ chưa có mặt là tích luôn (không cần nhắm đúng ô ☐)
        self.m_fg_list.row_click_check = lambda child_id: self.mode.get() == "in" and child_id not in self.present
        self.m_fg_list.on_double_click(lambda: self.pick_up() if self.mode.get() == "out" else None)
        self.m_fg_list.on_check(self._update_count)
        actions = self.bar(pady=(8, 0))
        self.m_btn_quick = self.button(actions, "Đón các trẻ đã tích", self.quick_check_in, P.CHECK_IN_OUT,
                                        style="Accent.TButton")
        self.m_btn_primary = self.button(actions, "Trả trẻ (xác nhận người đón)", self.pick_up, P.CHECK_IN_OUT,
                                          style="Accent.TButton")
        self.m_btn_select = self.button(actions, "Tích tất cả trẻ chưa đến", self.select_waiting, P.CHECK_IN_OUT)
        self.m_btn_undo = self.button(actions, "Hủy lượt đón nhầm", self.undo, P.CHECK_IN_OUT)
        self.m_lbl_summary = ttk.Label(actions, style="Muted.TLabel")
        self.m_lbl_summary.pack(side="right")
        self.waiting: list[str] = []
        self.present: list[str] = []

    def _mode_changed(self) -> None:
        self.m_fg_list.set_checked([])
        self.refresh()

    def _update_count(self) -> None:
        count = len([i for i in self.m_fg_list.checked_ids() if i in self.m_fg_list._checked])
        self.m_btn_quick.configure(text=f"Đón các trẻ đã tích ({count})")

    def refresh(self) -> None:
        self._load_classes()
        class_id = self._class_id()
        today = date.today()
        checking_in = self.mode.get() == "in"
        # mỗi chế độ chỉ hiện nút của nó: đón -> đón các trẻ đã tích; trả -> trả trẻ (xác nhận người đón)
        for button in (self.m_btn_quick, self.m_btn_primary, self.m_btn_select, self.m_btn_undo):
            button.pack_forget()
        shown = (self.m_btn_quick, self.m_btn_select, self.m_btn_undo) if checking_in else (self.m_btn_primary,)
        for button in shown:
            button.pack(side="left", padx=(0, 6), before=self.m_lbl_summary)
        self.m_lbl_hint.configure(text="Bấm vào dòng của trẻ để tích chọn (bấm ☐ ở tiêu đề = chọn / bỏ tất cả)"
                                  if checking_in else "Chọn trẻ rồi bấm 'Trả trẻ' (hoặc nháy đúp vào dòng)")
        if not checking_in:
            self.m_fg_list.set_checked([])
        self._update_count()
        if not class_id:
            self.m_fg_list.set_rows([])
            return
        if not self.system.calendar.is_school_day(today):
            self.m_lbl_info.configure(text=self.system.calendar.reason_not_school_day(today) + " Không đón trẻ.")
            self.m_fg_list.set_rows([])
            return
        self.m_lbl_info.configure(text=f"{weekday_name(today)} {format_date(today)}")
        rows, ids, tags = [], [], []
        self.waiting, self.present = [], []
        picked = 0
        for index, row in enumerate(self.system.daily.class_day(class_id, today), 1):
            child, record, leave = row["child"], row["record"], row["leave"]
            present = record is not None and record.is_present
            note = record.note if record and record.note != self.system.attendance.NOT_ARRIVED else ""
            if present:
                self.present.append(child.id)
                picked += record.picked_up
            elif leave is None and (record is None or record.note == self.system.attendance.NOT_ARRIVED):
                self.waiting.append(child.id)
            if leave is not None and not present:
                note = f"Có đơn xin nghỉ: {leave.reason}"
            if present and checking_in:
                status, who, tag = f"Có mặt - đến lúc {_hhmm(record.arrived_at) or '?'}", record.brought_by, "ok"
            elif present:
                if record.picked_up:
                    status, who, tag = f"Đã về lúc {_hhmm(record.picked_up_at)}", record.picked_up_by, "ok"
                else:
                    status, who, tag = "Đang ở lớp - chờ đón", "", "warn" if datetime.now().hour >= 17 else None
            else:
                absent = "Nghỉ có phép" if leave or (record and record.status.name == "EXCUSED") else "Vắng"
                status = f"{absent} - chưa đến trường" if checking_in and record is None else absent
                if not checking_in:
                    status += " (không ở lớp)"
                who, tag = "", "muted" if (not checking_in or leave) else None
            rows.append([index, child.id, child.full_name, status, who, note])
            ids.append(child.id)
            tags.append(tag)
        self.m_fg_list.set_rows(rows, ids, tags)
        total = len(rows)
        self.m_lbl_summary.configure(text=f"Có mặt {len(self.present)}/{total}  •  chưa đến {len(self.waiting)}  •  "
                                    f"đã trả {picked}/{len(self.present)}")
        self._update_count()

    def _people(self, child_id: str) -> list[tuple[str, str]]:
        people = self.system.authorized_pickups(child_id)
        return [(p[0], f"{p[0]} ({p[1]}) - {p[2]}") for p in people] + [("__other__", "Người khác (ghi tên bên dưới)")]

    def select_waiting(self) -> None:
        self.m_fg_list.set_checked(self.waiting)

    def quick_check_in(self) -> None:
        ids = [i for i in self.m_fg_list.checked_ids() if i not in self.present]
        if not ids:
            messagebox.showwarning("Chưa chọn", "Hãy bấm vào dòng của các trẻ đã đến để tích chọn "
                                                "(hoặc bấm 'Tích tất cả trẻ chưa đến').", parent=self)
            return
        done, errors = 0, []
        for child_id in ids:
            parents = self.system.parents.parents_of(child_id)
            who = f"{parents[0].relationship} {parents[0].full_name}" if parents else "Phụ huynh"
            try:
                self.system.daily.check_in(child_id, who)
                done += 1
            except KindergartenError as exc:
                errors.append(exc.message)
        self.app.save()
        self.m_fg_list.set_checked([])
        self.refresh()
        message = f"Đã đón {done} trẻ - các trẻ chuyển sang 'có mặt'."
        if errors:
            message += "\n\nKhông đón được:\n- " + "\n- ".join(errors)
        messagebox.showinfo("Đón trẻ", message, parent=self)

    def undo(self) -> None:
        child = self.selected(self.m_fg_list, self.system.children.get, "một trẻ")
        if child and self.confirm(f"Hủy lượt đón của {child.full_name}? Trẻ trở về trạng thái 'chưa đến' (vắng)."):
            self.guard(self.system.daily.undo_check_in, child.id, success="Đã hủy lượt đón.")

    def pick_up(self) -> None:
        child = self.selected(self.m_fg_list, self.system.children.get, "một trẻ")
        if child is None:
            return
        if child.id not in self.present:   # trẻ vắng không ở lớp -> không có gì để trả
            messagebox.showwarning("Trẻ không ở lớp", f"{child.full_name} vắng hôm nay nên không có lượt trả trẻ.",
                                   parent=self)
            return
        options = self._people(child.id)
        fields = [Field("person", "Người đến đón", "choice", options, width=48),
                  Field("other_name", "Họ tên (nếu không có trong danh sách)", required=False)]

        def submit(values: dict[str, Any]) -> str:
            name = values["person"]
            if name == "__other__":
                name = values["other_name"]
                if not name:
                    raise KindergartenError("Hãy nhập họ tên người đến đón để ghi nhật ký.")
            return self.system.verify_pickup(child.id, name)

        result = self.form(f"Trả trẻ: {child.full_name}", fields, submit, submit_text="Kiểm tra & trả trẻ")
        if result:
            messagebox.showinfo("Hợp lệ", f"Đã giao {child.full_name} cho: {result}", parent=self)


# =============================================================================
class DailyLogTab(ClassDayMixin, BaseTab):
    """Bước 3: giáo viên cập nhật ăn, ngủ, sinh hoạt; gửi cho phụ huynh của từng trẻ."""

    title = "Ăn ngủ - sinh hoạt"
    group = "Vận hành hằng ngày"
    permission = P.DAILY_LOG

    def build(self) -> None:
        self._class_day_bar()
        self.m_fg_list = DataTable(self, [("Mã", 55), ("Họ tên", 160), ("Bữa sáng", 80), ("Bữa trưa", 80),
                                      ("Bữa xế", 80), ("Giấc ngủ", 120), ("Tâm trạng", 85), ("Hoạt động / ghi chú", 230),
                                      ("Gửi PH", 60, "center"), ("PH xem / phản hồi", 200)], checkable=True)
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.edit)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Cập nhật trẻ đang chọn", self.edit, P.DAILY_LOG, style="Accent.TButton")
        self.button(actions, "Điền nhanh (ăn hết, ngủ ngon) cho trẻ chưa có", self.fill_defaults, P.DAILY_LOG)
        self.button(actions, "Gửi nhật ký cho phụ huynh", self.send, P.DAILY_LOG)
        self.button(actions, "Xem chi tiết", self.view)

    def refresh(self) -> None:
        self._load_classes()
        class_id, day = self._class_id(), self._day()
        if not class_id or day is None:
            self.m_fg_list.set_rows([])
            return
        if not self.system.calendar.is_school_day(day):
            self.m_lbl_info.configure(text=self.system.calendar.reason_not_school_day(day))
            self.m_fg_list.set_rows([])
            return
        rows, ids, tags = [], [], []
        sent = total = 0
        for row in self.system.daily.class_day(class_id, day):
            child, record, log = row["child"], row["record"], row["log"]
            if record is None or not record.is_present:
                rows.append([child.id, child.full_name, "", "", "", "", "",
                             record.status.value if record else "Chưa đón / điểm danh", "", ""])
                tags.append("muted")
            else:
                total += 1
                meals = log.meals if log else {}
                if log and log.is_sent:
                    sent += 1
                feedback = ""
                if log and log.parent_reply:
                    feedback = f"💬 {log.parent_reply}"
                elif log and log.parent_seen_at:
                    feedback = f"Đã xem {_hhmm(log.parent_seen_at)}"
                rows.append([child.id, child.full_name, *[meals.get(m, "") for m in MEALS],
                             log.nap_text() if log else "", log.mood if log else "",
                             " / ".join(x for x in (log.activities, log.teacher_note, log.health_note) if x) if log else "",
                             "✔" if log and log.is_sent else "", feedback])
                tags.append(None if log else "warn")
            ids.append(child.id)
        self.m_fg_list.set_rows(rows, ids, tags)
        self.m_lbl_info.configure(text=f"{weekday_name(day)} {format_date(day)} - đã gửi {sent}/{total} trẻ có mặt")

    def edit(self) -> None:
        ids = self.m_fg_list.checked_ids()
        day = self._day()
        if not ids or day is None:
            messagebox.showwarning("Chưa chọn", "Hãy tích ô ☐ đầu dòng một hoặc nhiều trẻ (cùng mức ăn ngủ).",
                                   parent=self)
            return
        first = self.system.daily.log_of(ids[0], day)
        meals = first.meals if first else {}
        level = [(v, v) for v in MEAL_LEVELS]
        fields = [Field(f"meal{i}", meal, "choice", level, meals.get(meal, "Ăn hết")) for i, meal in enumerate(MEALS)]
        fields += [Field("nap", "Giấc ngủ trưa", "choice", [(v, v) for v in NAP_LEVELS],
                         first.nap if first and first.nap else "Ngủ ngon"),
                   Field("nap_minutes", "Ngủ bao lâu (phút)", default=first.nap_minutes if first else 120,
                         required=False),
                   Field("mood", "Tâm trạng", "choice", [(v, v) for v in MOODS], first.mood if first and first.mood
                         else "Vui vẻ"),
                   Field("activities", "Hoạt động trong ngày", default=first.activities if first else None,
                         required=False),
                   Field("health_note", "Sức khỏe (sốt, ho, vết thương...)", default=first.health_note if first
                         else None, required=False),
                   Field("teacher_note", "Lời nhắn của cô gửi phụ huynh", "textarea",
                         default=first.teacher_note if first else None, required=False)]

        def submit(values: dict[str, Any]) -> int:
            meal_values = {meal: values.pop(f"meal{i}") for i, meal in enumerate(MEALS)}
            for child_id in ids:
                self.system.daily.save_log(child_id, day, meals=meal_values, **values)
            return len(ids)

        names = ", ".join(self.system.children.get(i).full_name for i in ids[:3]) + ("..." if len(ids) > 3 else "")
        self.form(f"Ăn ngủ ngày {format_date(day)}: {names}", fields, submit,
                  success=lambda n: f"Đã cập nhật {n} trẻ. Bấm 'Gửi nhật ký cho phụ huynh' khi xong.")

    def fill_defaults(self) -> None:
        class_id, day = self._class_id(), self._day()
        if class_id and day:
            self.guard(self.system.daily.fill_class_defaults, class_id, day,
                       success=lambda n: f"Đã điền mặc định cho {n} trẻ - hãy sửa các trẻ khác thường.")

    def send(self) -> None:
        class_id, day = self._class_id(), self._day()
        if class_id and day and self.confirm(f"Gửi nhật ký ngày {format_date(day)} cho phụ huynh của từng trẻ?"):
            self.guard(self.system.daily.send_logs, class_id, day,
                       success=lambda n: f"Đã gửi nhật ký của {n} trẻ cho phụ huynh.")

    def view(self) -> None:
        child_id, day = self.m_fg_list.selected_id(), self._day()
        log = self.system.daily.log_of(child_id, day) if child_id and day else None
        if log is None:
            messagebox.showinfo("Chưa có", "Trẻ này chưa có nhật ký trong ngày.", parent=self)
            return
        child = self.system.children.get(child_id)
        status = f"\n\nĐã gửi phụ huynh lúc {_hhmm(log.sent_at)}" if log.is_sent else "\n\n(Chưa gửi phụ huynh)"
        self.show_text(f"Nhật ký {child.full_name}", f"Nhật ký của {child.full_name}\n{log.summary_text()}{status}"
                       f"\nCập nhật bởi {log.updated_by} lúc {_hhmm(log.updated_at)}")


# =============================================================================
class ParentContactTab(BaseTab):
    """Bước 4: trao đổi hai chiều - phụ huynh nhắn / dặn thuốc / xin nghỉ; giáo viên trả lời, thông báo lớp."""

    title = "Trao đổi phụ huynh"
    group = "Vận hành hằng ngày"
    permission = P.PARENT_CONTACT

    def build(self) -> None:
        bar = self.bar()
        ttk.Label(bar, text="Hiển thị:").pack(side="left")
        self.m_cbo_filter = ttk.Combobox(bar, state="readonly", width=20, values=["Chờ xử lý", "Hôm nay", "Tất cả"])
        self.m_cbo_filter.set("Chờ xử lý")
        self.m_cbo_filter.pack(side="left", padx=4)
        self.m_cbo_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.m_lbl_count = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_count.pack(side="left", padx=12)
        self.m_fg_list = DataTable(self, [("Gửi lúc", 110), ("Loại", 110), ("Trẻ", 150), ("Lớp", 110), ("Nội dung", 330),
                                      ("Người gửi", 150), ("Trạng thái", 100), ("Trả lời", 220)])
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.open)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Xem & trả lời", self.open, style="Accent.TButton")
        self.button(actions, "Đã thực hiện / Duyệt xin nghỉ", self.complete)
        self.button(actions, "Từ chối", self.decline)
        self.button(actions, "Nhắn riêng phụ huynh", self.message_parent)
        self.button(actions, "Gửi thông báo cho lớp", self.announce)

    def refresh(self) -> None:
        mode = self.m_cbo_filter.get()
        scope = self.scope_class_ids()
        items = self.system.daily.inbox(scope, only_open=mode == "Chờ xử lý",
                                        on_date=date.today() if mode == "Hôm nay" else None)
        rows, tags = [], []
        for m in items:
            child = self.system.children.get_or_none(m.child_id) if m.child_id else None
            rows.append([m.created_at.replace("T", " ")[5:], m.kind.value, child.full_name if child else "(cả lớp)",
                         self.class_name(m.class_id), m.detail_text(), m.sender, m.status.value, m.reply or ""])
            tags.append("warn" if m.needs_action and m.kind is MessageKind.MEDICINE else
                        None if m.needs_action else "muted")
        self.m_fg_list.set_rows(rows, [m.id for m in items], tags)
        waiting = len(self.system.daily.inbox(scope, only_open=True))
        self.m_lbl_count.configure(text=f"{waiting} tin chờ xử lý")

    def _selected(self):
        return self.selected(self.m_fg_list, self.system.daily.messages.get, "một tin nhắn")

    def open(self) -> None:
        message = self._selected()
        if message is None:
            return
        if message.from_parent:
            self.system.daily.mark_seen(message.id)
        fields = [Field("reply", f"{message.kind.value} của {message.sender}:\n{message.detail_text()[:200]}\n\nTrả lời",
                        "textarea", default=message.reply or None, width=60)]
        if message.needs_action:
            fields.append(Field("done", "Đánh dấu đã thực hiện / duyệt", "bool",
                                default=message.kind is not MessageKind.LEAVE))
        self.form("Trao đổi với phụ huynh", fields,
                  lambda v: self.system.daily.reply(message.id, v["reply"], v.get("done", False)),
                  success="Đã gửi trả lời cho phụ huynh.")

    def complete(self) -> None:
        message = self._selected()
        if message is None:
            return
        label = {MessageKind.MEDICINE: "Đã cho trẻ uống thuốc?", MessageKind.LEAVE: "Duyệt đơn xin nghỉ "
                 f"{message.period_text}? Các ngày này sẽ tính 'nghỉ có phép'."}.get(message.kind, "Đánh dấu đã xử lý?")
        if self.confirm(label):
            self.guard(self.system.daily.complete, message.id, success="Đã cập nhật - phụ huynh sẽ thấy trạng thái mới.")

    def decline(self) -> None:
        message = self._selected()
        if message is not None:
            self.form("Từ chối", [Field("reason", "Lý do (gửi cho phụ huynh)")],
                      lambda v: self.system.daily.decline(message.id, v["reason"]), success="Đã gửi lý do.")

    def message_parent(self) -> None:
        children = self.system.children_for(self.user)
        fields = [Field("child_id", "Phụ huynh của trẻ", "choice", self.child_options(children)),
                  Field("content", "Nội dung", "textarea", width=50)]
        self.form("Nhắn riêng phụ huynh", fields,
                  lambda v: self.system.daily.teacher_send(v["child_id"], v["content"]), success="Đã gửi tin nhắn.")

    def announce(self) -> None:
        fields = [Field("class_id", "Lớp", "choice", self.class_options()),
                  Field("content", "Nội dung thông báo", "textarea", width=50)]
        self.form("Thông báo cho phụ huynh cả lớp", fields,
                  lambda v: self.system.daily.teacher_send(None, v["content"], v["class_id"], announcement=True),
                  success="Đã gửi thông báo cho phụ huynh cả lớp.")


# =============================================================================
class ServicesTab(BaseTab):
    """Danh mục dịch vụ tự chọn (thêm được dịch vụ mới) và đăng ký dịch vụ cho trẻ."""

    title = "Dịch vụ"
    group = "Tài chính"
    permission = P.MANAGE_SERVICES

    def build(self) -> None:
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        ttk.Label(left, text="Danh mục dịch vụ", style="Section.TLabel").pack(anchor="w")
        self.m_fg_services = DataTable(left, [("Tên dịch vụ", 200), ("Giá / tháng", 110, "e"), ("Số trẻ", 60, "center")])
        self.m_fg_services.pack(fill="both", expand=True)
        self.m_fg_services.on_select(self.refresh_children)
        self.master_bar(self.add, self.edit, self.delete, P.MANAGE_SERVICES, master=left)
        self.m_lbl_child_title = ttk.Label(right, text="Trẻ đăng ký", style="Section.TLabel")
        self.m_lbl_child_title.pack(anchor="w")
        self.m_fg_children = DataTable(right, [("Mã", 60), ("Họ tên", 180), ("Lớp", 140), ("Dịch vụ đang dùng", 260)],
                                        selectmode="extended")
        self.m_fg_children.pack(fill="both", expand=True)
        bar = self.bar(right, pady=(6, 0))
        self.button(bar, "Đăng ký thêm trẻ", self.register, P.MANAGE_SERVICES, style="Accent.TButton")
        self.button(bar, "Hủy đăng ký trẻ đã chọn", self.unregister, P.MANAGE_SERVICES)
        ttk.Label(right, text="Thay đổi áp dụng từ hóa đơn lập sau thời điểm đăng ký.", style="Muted.TLabel").pack(
            anchor="w", pady=(4, 0))

    def refresh(self) -> None:
        catalog = self.system.service_catalog()
        self.m_fg_services.set_rows([[name, format_vnd(price), count] for name, price, count in catalog],
                               [name for name, _p, _c in catalog])
        if self.m_fg_services.selected_id() is None and catalog:
            self.m_fg_services.tree.selection_set(catalog[0][0])
        self.refresh_children()

    def _service(self) -> str | None:
        return self.m_fg_services.selected_id()

    def refresh_children(self) -> None:
        service = self._service()
        kids = self.system.children_using_service(service) if service else []
        self.m_lbl_child_title.configure(text=f"Trẻ đăng ký: {service or '-'} ({len(kids)} trẻ)")
        self.m_fg_children.set_rows([[c.id, c.full_name, self.class_name(c.class_id), ", ".join(c.extra_services)]
                                      for c in kids], [c.id for c in kids])

    def _fields(self, name: str | None = None) -> list[Field]:
        price = self.system.settings.extra_services.get(name) if name else None
        return [Field("name", "Tên dịch vụ (VD: Bơi lội, Võ thuật)", default=name),
                Field("price", "Giá mỗi tháng (đ)", "money", default=price)]

    def add(self) -> None:
        self.form("Thêm dịch vụ", self._fields(), lambda v: self.system.save_service(v["name"], v["price"]),
                  success=lambda n: f"Đã thêm dịch vụ '{n}'. Phụ huynh và kế toán đã có thể đăng ký cho trẻ.")

    def edit(self) -> None:
        service = self._service()
        if service:
            self.form(f"Sửa dịch vụ {service}", self._fields(service),
                      lambda v: self.system.save_service(v["name"], v["price"], old_name=service),
                      success="Đã cập nhật dịch vụ (áp dụng cho hóa đơn lập từ bây giờ).")

    def delete(self) -> None:
        service = self._service()
        if not service:
            return
        users = self.system.children_using_service(service)
        warning = f"{len(users)} trẻ đang đăng ký sẽ được gỡ đăng ký. " if users else ""
        if self.confirm_delete("dịch vụ", [
                ("Tên dịch vụ", service), ("Giá / tháng", format_vnd(self.system.settings.extra_services[service])),
                ("Số trẻ đang đăng ký", len(users))], note=f"{warning}Hóa đơn đã lập không thay đổi."):
            self.guard(self.system.remove_service, service, success="Đã xóa dịch vụ.")

    def register(self) -> None:
        service = self._service()
        if not service:
            messagebox.showwarning("Chưa chọn", "Hãy chọn dịch vụ ở bảng bên trái.", parent=self)
            return
        candidates = [c for c in self.system.children.all_sorted() if service not in c.extra_services]
        fields = [Field("child_ids", "Chọn trẻ đăng ký", "multi", self.child_options(candidates), [], width=50)]

        def submit(values: dict[str, Any]) -> int:
            if not values["child_ids"]:
                raise KindergartenError("Hãy chọn ít nhất một trẻ.")
            for child_id in values["child_ids"]:
                self.system.set_child_service(child_id, service, True)
            return len(values["child_ids"])

        self.form(f"Đăng ký dịch vụ {service}", fields, submit, success=lambda n: f"Đã đăng ký cho {n} trẻ.")

    def unregister(self) -> None:
        service, ids = self._service(), self.m_fg_children.selected_ids()
        if service and ids and self.confirm(f"Hủy dịch vụ '{service}' cho {len(ids)} trẻ đã chọn?"):
            for child_id in ids:
                self.guard(self.system.set_child_service, child_id, service, False)


# =============================================================================
class CalendarTab(BaseTab):
    """Lịch năm học: ngày nghỉ lễ, học Thứ 7 - dùng chung cho đón trẻ, điểm danh, tiền ăn, thực đơn."""

    title = "Lịch năm học"
    group = "Quản trị"
    permission = P.MANAGE_CALENDAR
    FIXED_HOLIDAYS = [((1, 1), "Tết Dương lịch"), ((4, 30), "Ngày Giải phóng miền Nam"),
                      ((5, 1), "Ngày Quốc tế Lao động"), ((9, 2), "Quốc khánh"), ((9, 1), "Nghỉ Quốc khánh")]

    def build(self) -> None:
        bar = self.bar()
        self.saturday = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Trường có học Thứ 7", variable=self.saturday,
                        command=self.toggle_saturday).pack(side="left")
        self.m_lbl_summary = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_summary.pack(side="left", padx=16)
        self.m_fg_list = DataTable(self, [("Ngày", 100), ("Thứ", 80), ("Tên ngày nghỉ", 320)], selectmode="extended")
        self.m_fg_list.pack(fill="both", expand=True)
        actions = self.bar(pady=(8, 0))
        self.button(actions, "Thêm ngày nghỉ", self.add, P.MANAGE_CALENDAR, style="Accent.TButton")
        self.button(actions, "Thêm ngày lễ cố định của một năm", self.add_fixed, P.MANAGE_CALENDAR)
        self.button(actions, "Bỏ các ngày đã chọn", self.remove, P.MANAGE_CALENDAR)

    def refresh(self) -> None:
        cal = self.system.calendar
        self.saturday.set(cal.saturday_classes)
        items = list(cal.holidays.items())
        self.m_fg_list.set_rows([[format_date(d), WEEKDAY_NAMES[d.weekday()], name] for d, name in items],
                            [d.isoformat() for d, _ in items],
                            ["muted" if d < date.today() else None for d, _ in items])
        upcoming = [d for d, _ in items if d >= date.today()]
        self.m_lbl_summary.configure(text=f"{len(items)} ngày nghỉ, sắp tới: "
                                    + (f"{format_date(upcoming[0])} ({cal.holiday_name(upcoming[0])})"
                                       if upcoming else "không có"))

    def toggle_saturday(self) -> None:
        self.guard(self.system.set_saturday_classes, self.saturday.get())

    def add(self) -> None:
        fields = [Field("start", "Nghỉ từ ngày", "date", default=date.today()),
                  Field("end", "Đến ngày (để trống = nghỉ 1 ngày)", "date", required=False),
                  Field("name", "Tên ngày nghỉ (VD: Tết Nguyên đán)")]
        self.form("Thêm ngày nghỉ", fields, lambda v: self.system.add_holidays(v["start"], v["end"] or None, v["name"]),
                  success=lambda days: f"Đã thêm {len(days)} ngày nghỉ. Các ngày này không điểm danh, không tính tiền ăn.")

    def add_fixed(self) -> None:
        fields = [Field("year", "Năm", default=date.today().year)]

        def submit(values: dict[str, Any]) -> int:
            try:
                year = int(values["year"])
            except ValueError as exc:
                raise KindergartenError("Năm không hợp lệ.") from exc
            count = 0
            for (month, day), name in self.FIXED_HOLIDAYS:
                count += len(self.system.add_holidays(date(year, month, day), None, name))
            return count

        self.form("Ngày lễ cố định (Tết Dương lịch, 30/4, 1/5, Quốc khánh)", fields, submit,
                  success=lambda n: f"Đã thêm {n} ngày lễ. Tết Âm lịch thay đổi theo năm - thêm bằng 'Thêm ngày nghỉ'.")

    def remove(self) -> None:
        ids = self.m_fg_list.selected_ids()
        if not ids:
            messagebox.showwarning("Chưa chọn", "Hãy chọn ngày cần bỏ.", parent=self)
            return
        if self.confirm(f"Bỏ {len(ids)} ngày nghỉ đã chọn?"):
            self.guard(self.system.remove_holidays, [parse_date(i) for i in ids], success="Đã bỏ ngày nghỉ.")
