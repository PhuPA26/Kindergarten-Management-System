"""Màn hình riêng của GIÁO VIÊN BỘ MÔN: lịch dạy trong ngày + sổ tiết dạy + nhận xét trẻ theo môn.

(GV chủ nhiệm dùng các màn hình Đón trả trẻ, Điểm danh, Ăn ngủ, Trao đổi phụ huynh... - GV bộ môn không có các
màn hình đó mà làm việc ở đây.)
"""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from typing import Any

from ...auth.user import Permission
from ...exceptions import KindergartenError
from ...reports.reports import SubjectTeachingReport
from ...teaching.lesson_log import CHILD_LEVELS, LESSON_RATINGS, LessonLog
from ...utils import format_date, month_label, parse_date, previous_month, weekday_name
from .base_tab import BaseTab
from .widgets import DataTable, Field, FormDialog, px

P = Permission


class LessonTab(BaseTab):
    title = "Sổ tiết dạy bộ môn"
    permission = P.TEACH_SUBJECT

    def build(self) -> None:
        lessons = self.system.lessons
        self.mine = lessons.my_teacher_id() if self.user is not None else None
        self.slots: dict[str, dict[str, Any]] = {}
        # ---- lịch dạy trong ngày (theo thời khóa biểu)
        bar = self.bar()
        ttk.Label(bar, text="Lịch dạy ngày", style="Section.TLabel").pack(side="left", padx=(0, px(10)))
        ttk.Button(bar, text="◀", width=3, command=lambda: self._shift(-1)).pack(side="left")
        self.day_var = tk.StringVar(value=format_date(date.today()))
        entry = ttk.Entry(bar, textvariable=self.day_var, width=12)
        entry.pack(side="left", padx=2)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="▶", width=3, command=lambda: self._shift(1)).pack(side="left")
        ttk.Button(bar, text="Hôm nay", command=self._today).pack(side="left", padx=(4, 12))
        if self.mine is None:   # Ban giám hiệu: xem lịch dạy của từng giáo viên bộ môn
            ttk.Label(bar, text="Giáo viên:").pack(side="left")
            self.m_cbo_teacher = ttk.Combobox(bar, state="readonly", width=30)
            self.m_cbo_teacher.pack(side="left", padx=4)
            self.m_cbo_teacher.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        else:
            self.m_cbo_teacher = None
        self.m_lbl_day = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_day.pack(side="left", padx=8)
        self.m_fg_schedule = DataTable(self, [("Giờ", 110), ("Lớp", 150), ("Môn / hoạt động", 170),
                                              ("Sổ tiết dạy", 320)], height=4)
        self.m_fg_schedule.pack(fill="x")
        self.m_fg_schedule.on_double_click(self.log_selected_slot)
        actions = self.bar(pady=(px(6), px(12)))
        self.button(actions, "✎  Ghi sổ tiết đã chọn", self.log_selected_slot, P.TEACH_SUBJECT,
                    style="Accent.TButton")
        ttk.Label(actions, text="Bấm đúp vào một tiết để ghi nội dung bài dạy và nhận xét trẻ.",
                  style="Muted.TLabel").pack(side="left", padx=8)

        # ---- sổ tiết dạy đã ghi
        box = self.filter_bar()
        ttk.Label(box, text="Tháng:").pack(side="left")
        self.m_cbo_month = ttk.Combobox(box, state="readonly", width=10, values=self._month_options())
        self.m_cbo_month.set(self._month_options()[0])
        self.m_cbo_month.pack(side="left", padx=(4, 12))
        self.m_cbo_month.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(box, text="Lớp:").pack(side="left")
        self.m_cbo_class = ttk.Combobox(box, state="readonly", width=24)
        self.m_cbo_class.pack(side="left", padx=4)
        self.m_cbo_class.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.m_lbl_count = ttk.Label(box, style="Muted.TLabel")
        self.m_lbl_count.pack(side="left", padx=12)
        self.m_fg_list = DataTable(self, [("Mã", 60), ("Ngày", 90), ("Giờ", 100), ("Lớp", 130), ("Môn", 100),
                                          ("Giáo viên", 150), ("Nội dung bài dạy", 260), ("Đánh giá", 90),
                                          ("Nhận xét trẻ", 90, "center")], height=8)
        self.m_fg_list.pack(fill="both", expand=True)
        self.m_fg_list.on_double_click(self.child_notes)
        self.master_bar(add=self.add_lesson, edit=self.edit_lesson, delete=self.delete_lesson,
                        permission=P.TEACH_SUBJECT,
                        extras=[("☺  Nhận xét trẻ", self.child_notes, P.TEACH_SUBJECT),
                                ("Xem chi tiết", self.view_lesson),
                                ("▤  Báo cáo chuyên môn tháng", self.month_report)])

    # ------------------------------------------------------------------ tiện ích
    @staticmethod
    def _month_options() -> list[str]:
        today = date.today()
        m, y = today.month, today.year
        out = []
        for _ in range(6):
            out.append(month_label(m, y))
            m, y = previous_month(m, y)
        return out

    def _month(self) -> tuple[int, int]:
        m, y = self.m_cbo_month.get().split("/")
        return int(m), int(y)

    def _day(self) -> date:
        try:
            return parse_date(self.day_var.get())
        except KindergartenError:
            return date.today()

    def _shift(self, step: int) -> None:
        day = self._day() + timedelta(days=step)
        if day <= date.today():
            self.day_var.set(format_date(day))
            self.refresh()

    def _today(self) -> None:
        self.day_var.set(format_date(date.today()))
        self.refresh()

    def _teacher_id(self) -> str | None:
        if self.mine is not None:
            return self.mine
        value = self.m_cbo_teacher.get() if self.m_cbo_teacher is not None else ""
        return value.split(" - ")[0] if value else None

    def _subject_teachers(self) -> list[Any]:
        return [t for t in self.system.employees.teachers()
                if self.system.teacher_duty_for_employee(t.id) == "bo_mon"]

    def _class_filter(self) -> str | None:
        value = self.m_cbo_class.get()
        return value.split(" - ")[0] if value and not value.startswith("(") else None

    # ------------------------------------------------------------------ hiển thị
    def refresh(self) -> None:
        lessons = self.system.lessons
        if self.m_cbo_teacher is not None:
            options = [f"{t.id} - {t.full_name}" + (f" ({t.specialty})" if t.specialty else "")
                       for t in self._subject_teachers()]
            self.m_cbo_teacher["values"] = options
            if self.m_cbo_teacher.get() not in options:
                self.m_cbo_teacher.set(options[0] if options else "")
        day = self._day()
        teacher_id = self._teacher_id()
        rows = lessons.schedule(day, teacher_id) if teacher_id else []
        self.slots = {row["slot"].id: row for row in rows}
        self.m_fg_schedule.set_rows(
            [[r["slot"].time_range, self.class_name(r["slot"].class_id), r["slot"].activity,
              f"✔ Đã ghi ({r['log'].id}) - {r['log'].content[:40]}" if r["log"] else "Chưa ghi sổ"] for r in rows],
            [r["slot"].id for r in rows], ["ok" if r["log"] else None for r in rows])
        if not self.system.calendar.is_school_day(day):
            info = self.system.calendar.reason_not_school_day(day)
        else:
            done = sum(1 for r in rows if r["log"])
            info = f"{weekday_name(day)}: {len(rows)} tiết, đã ghi sổ {done}" if rows else f"{weekday_name(day)}: không có tiết dạy"
        self.m_lbl_day.configure(text=info)

        classes = lessons.taught_classes(teacher_id) if teacher_id else self.system.classes.all_sorted()
        class_values = ["(Tất cả lớp)"] + [f"{c.id} - {c.name}" for c in classes]
        self.m_cbo_class["values"] = class_values
        if self.m_cbo_class.get() not in class_values:
            self.m_cbo_class.set(class_values[0])
        month, year = self._month()
        items = lessons.logs(teacher_id=teacher_id, class_id=self._class_filter(), month=month, year=year)
        teacher_name = lambda tid: (self.system.employees.get(tid).full_name  # noqa: E731
                                    if self.system.employees.exists(tid) else tid)
        self.m_fg_list.set_rows([[x.id, format_date(x.date), x.time_text or "-", self.class_name(x.class_id),
                                  x.subject, teacher_name(x.teacher_id), x.content, x.rating or "-",
                                  len(x.child_notes)] for x in items], [x.id for x in items])
        self.m_lbl_count.configure(text=f"{len(items)} tiết đã ghi trong tháng {month_label(month, year)}")

    # ------------------------------------------------------------------ ghi sổ
    def _lesson_fields(self, log: LessonLog | None = None, slot: Any = None, teacher_id: str | None = None
                       ) -> list[Field]:
        lessons = self.system.lessons
        teacher_id = log.teacher_id if log else teacher_id
        classes = lessons.taught_classes(teacher_id) if teacher_id else []
        subjects = lessons.subjects_of(teacher_id) if teacher_id else []
        subject_default = log.subject if log else (slot.activity if slot else (subjects[0] if subjects else ""))
        if subject_default and subject_default not in subjects:
            subjects.append(subject_default)
        fields = [Field("class_id", "Lớp", "choice", [(c.id, f"{c.id} - {c.name}") for c in classes],
                        log.class_id if log else (slot.class_id if slot else (classes[0].id if classes else None))),
                  Field("on_date", "Ngày dạy (dd/mm/yyyy)", "date",
                        default=format_date(log.date if log else self._day())),
                  Field("subject", "Môn / hoạt động", "choice", [(s, s) for s in subjects], subject_default),
                  Field("content", "Nội dung bài dạy", "textarea", default=log.content if log else ""),
                  Field("rating", "Đánh giá chung cả lớp", "choice", [("", "(chưa đánh giá)")] +
                        [(r, r) for r in LESSON_RATINGS], log.rating if log else "Tốt", required=False),
                  Field("note", "Ghi chú (đồ dùng, trẻ vắng...)", "textarea", default=log.note if log else "",
                        required=False)]
        return fields

    def log_selected_slot(self) -> None:
        slot_id = self.m_fg_schedule.selected_id()
        if not slot_id:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một tiết trong lịch dạy.", parent=self)
            return
        row = self.slots.get(slot_id)
        if row is None:
            return
        if row["log"] is not None:   # đã ghi -> sửa
            self._edit(row["log"])
            return
        slot = row["slot"]
        fields = self._lesson_fields(slot=slot, teacher_id=slot.teacher_id)
        result = self.form(f"Ghi sổ tiết {slot.activity} - {self.class_name(slot.class_id)}", fields,
                           lambda v: self.system.lessons.save_lesson(teacher_id=slot.teacher_id, slot=slot, **v))
        if result is not None and messagebox.askyesno(
                "Nhận xét trẻ", "Đã ghi sổ tiết dạy. Nhận xét trẻ trong tiết này luôn?", parent=self):
            self._open_child_notes(result)

    def add_lesson(self) -> None:
        teacher_id = self._teacher_id()
        if not teacher_id:
            messagebox.showwarning("Chưa chọn", "Hãy chọn giáo viên bộ môn trước.", parent=self)
            return
        self.form("Ghi sổ tiết dạy", self._lesson_fields(teacher_id=teacher_id),
                  lambda v: self.system.lessons.save_lesson(teacher_id=teacher_id, **v),
                  success=lambda x: f"Đã ghi sổ tiết {x.subject} lớp {self.class_name(x.class_id)} "
                                    f"ngày {format_date(x.date)}.")

    def _selected_log(self) -> LessonLog | None:
        return self.selected(self.m_fg_list, self.system.lessons.get, "một tiết dạy trong sổ")

    def edit_lesson(self) -> None:
        log = self._selected_log()
        if log is not None:
            self._edit(log)

    def _edit(self, log: LessonLog) -> None:
        self.form(f"Sửa sổ tiết dạy {log.id}", self._lesson_fields(log),
                  lambda v: self.system.lessons.save_lesson(teacher_id=log.teacher_id, log_id=log.id, **v),
                  success="Đã cập nhật sổ tiết dạy.")

    def delete_lesson(self) -> None:
        log = self._selected_log()
        if log is None:
            return
        if self.confirm_delete("tiết dạy", [("Mã", log.id), ("Ngày", format_date(log.date)),
                                            ("Lớp", self.class_name(log.class_id)), ("Môn", log.subject),
                                            ("Nội dung", log.content)],
                               "Nhận xét trẻ trong tiết này cũng bị xóa."):
            self.guard(self.system.lessons.delete_lesson, log.id)

    # ------------------------------------------------------------------ nhận xét trẻ
    def child_notes(self) -> None:
        log = self._selected_log()
        if log is not None:
            self._open_child_notes(log)

    def _open_child_notes(self, log: LessonLog) -> None:
        dialog = ChildNotesDialog(self, log)
        self.wait_window(dialog)
        if dialog.changed:
            self.app.save()
        self.refresh()

    def view_lesson(self) -> None:
        log = self._selected_log()
        if log is None:
            return
        teacher = self.system.employees.get_or_none(log.teacher_id)
        lines = [f"Tiết {log.subject} - lớp {self.class_name(log.class_id)}",
                 f"Ngày dạy: {weekday_name(log.date)} {format_date(log.date)}" + (f", {log.time_text}" if log.time_text else ""),
                 f"Giáo viên: {teacher.full_name if teacher else log.teacher_id}",
                 f"Nội dung bài dạy: {log.content}",
                 f"Đánh giá chung: {log.rating or 'chưa đánh giá'}"]
        if log.note:
            lines.append(f"Ghi chú: {log.note}")
        notes = log.child_notes
        lines += ["", f"Nhận xét trẻ ({len(notes)} trẻ)"]
        for child_id, note in sorted(notes.items()):
            child = self.system.children.get_or_none(child_id)
            lines.append(f"  • {child.full_name if child else child_id}: {log.child_note_text(child_id)}")
        if not notes:
            lines.append("  Chưa nhận xét trẻ nào.")
        lines.append(f"\nNgười ghi: {log.created_by or '-'} - cập nhật lúc {log.updated_at.replace('T', ' ')}")
        self.show_text(f"Sổ tiết dạy {log.id}", "\n".join(lines))

    def month_report(self) -> None:
        month, year = self._month()
        scope = self.scope_class_ids()
        class_id = self._class_filter()
        report = SubjectTeachingReport(self.system, month, year, class_id=class_id,
                                       class_ids=None if class_id else scope)
        self.open_report(f"Báo cáo chuyên môn bộ môn tháng {month_label(month, year)}", report=report,
                         notice="Muốn gửi Ban giám hiệu: vào 'Lập & gửi báo cáo', chọn "
                                "'Báo cáo chuyên môn bộ môn tháng'." if self.mine else "")


class ChildNotesDialog(tk.Toplevel):
    """Nhận xét từng trẻ trong một tiết dạy: chọn trẻ -> chọn mức (Nổi bật / Đạt / Cần hỗ trợ) + ghi nhận xét."""

    def __init__(self, tab: LessonTab, log: LessonLog) -> None:
        super().__init__(tab)
        self.tab, self.log, self.changed = tab, log, False
        system = tab.system
        self.title(f"Nhận xét trẻ - {log.subject} lớp {system.classes.class_name(log.class_id)} "
                   f"ngày {format_date(log.date)}")
        self.transient(tab.winfo_toplevel())
        self.geometry(f"{px(760)}x{px(520)}")
        body = ttk.Frame(self, padding=px(14))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Tiết {log.subject}: {log.content}", style="Section.TLabel",
                  wraplength=px(720)).pack(anchor="w")
        ttk.Label(body, text="Bấm đúp vào một trẻ để nhận xét. Chỉ cần nhận xét trẻ nổi bật hoặc cần hỗ trợ thêm.",
                  style="Muted.TLabel").pack(anchor="w", pady=(px(2), px(8)))
        self.m_fg_children = DataTable(body, [("Mã", 60), ("Họ tên", 190), ("Mức", 100), ("Nhận xét", 320)],
                                       height=12)
        self.m_fg_children.pack(fill="both", expand=True)
        self.m_fg_children.on_double_click(self.edit_note)
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(px(10), 0))
        ttk.Button(bar, text="Đóng", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Xóa nhận xét", command=self.clear_note).pack(side="right", padx=6)
        ttk.Button(bar, text="✎  Nhận xét trẻ đã chọn", style="Accent.TButton",
                   command=self.edit_note).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())
        self.load()
        self.grab_set()

    def load(self) -> None:
        system = self.tab.system
        kids = system.classes.class_list(self.log.class_id)
        notes = self.log.child_notes
        self.m_fg_children.set_rows(
            [[c.id, c.full_name, notes.get(c.id, {}).get("level", "") or "-", notes.get(c.id, {}).get("comment", "")]
             for c in kids], [c.id for c in kids],
            ["ok" if c.id in notes else None for c in kids])

    def _child(self):
        child_id = self.m_fg_children.selected_id()
        if not child_id:
            messagebox.showwarning("Chưa chọn", "Hãy chọn một trẻ trong danh sách.", parent=self)
            return None
        return self.tab.system.children.get(child_id)

    def edit_note(self) -> None:
        child = self._child()
        if child is None:
            return
        current = self.log.child_notes.get(child.id, {})
        fields = [Field("level", "Mức đánh giá", "choice", [(lv, lv) for lv in CHILD_LEVELS],
                        current.get("level") or "Đạt"),
                  Field("comment", "Nhận xét", "textarea", default=current.get("comment", ""), required=False)]
        dialog = FormDialog(self, f"Nhận xét {child.full_name}", fields,
                            lambda v: self.tab.system.lessons.set_child_note(self.log.id, child.id, **v))
        self.wait_window(dialog)
        if dialog.submitted:
            self.changed = True
            self.load()

    def clear_note(self) -> None:
        child = self._child()
        if child is None or child.id not in self.log.child_notes:
            return
        try:
            self.tab.system.lessons.set_child_note(self.log.id, child.id)
        except KindergartenError as exc:
            messagebox.showerror("Không thực hiện được", exc.message, parent=self)
            return
        self.changed = True
        self.load()
