"""Báo cáo theo quy trình: bộ phận lập báo cáo đúng nghiệp vụ -> ghi chú -> gửi Ban giám hiệu;
Ban giám hiệu nhận, xem, duyệt hoặc yêu cầu bổ sung (có ý kiến) -> bộ phận cập nhật và gửi lại."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from ...auth.user import Permission
from ...exceptions import KindergartenError
from ...reports.submissions import ReportStatus
from ...utils import format_date, month_label, parse_date, parse_month, previous_month
from .base_tab import BaseTab
from .report_view import ReportView
from .widgets import COLORS, DataTable, Field, open_folder

P = Permission
STATUS_TAGS = {ReportStatus.DRAFT: "muted", ReportStatus.SENT: None, ReportStatus.APPROVED: "ok",
               ReportStatus.REVISE: "warn", ReportStatus.FINAL: "ok"}


# =============================================================================
class ReportSubmitTab(BaseTab):
    """Bộ phận (giáo viên, kế toán, nhân viên): lập báo cáo, ghi chú, gửi BGH, theo dõi phản hồi."""

    title = "Lập & gửi báo cáo"
    group = "Báo cáo"
    permission = P.SUBMIT_REPORTS

    def build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x")
        form = ttk.LabelFrame(top, text="1. Lập báo cáo", padding=8)
        form.pack(side="left", fill="y")
        ttk.Label(form, text="Loại báo cáo:").grid(row=0, column=0, sticky="w")
        self.m_cbo_type = ttk.Combobox(form, state="readonly", width=34)
        self.m_cbo_type.grid(row=0, column=1, sticky="w", pady=2)
        self.m_cbo_type.bind("<<ComboboxSelected>>", lambda _e: self._type_changed())
        self.m_lbl_period = ttk.Label(form, text="Ngày (dd/mm/yyyy):")
        self.m_lbl_period.grid(row=1, column=0, sticky="w")
        self.period_var = tk.StringVar()
        self.m_txt_period = ttk.Entry(form, textvariable=self.period_var, width=14)
        self.m_txt_period.grid(row=1, column=1, sticky="w", pady=2)
        self.m_lbl_class = ttk.Label(form, text="Lớp:")
        self.m_lbl_class.grid(row=2, column=0, sticky="w")
        self.m_cbo_class = ttk.Combobox(form, state="readonly", width=34)
        self.m_cbo_class.grid(row=2, column=1, sticky="w", pady=2)
        ttk.Button(form, text="Xem trước số liệu", command=self.preview).grid(row=3, column=0, columnspan=2,
                                                                                sticky="ew", pady=(6, 0))
        note_frame = ttk.LabelFrame(top, text="2. Ghi chú gửi Ban giám hiệu", padding=8)
        note_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.m_txt_note = tk.Text(note_frame, height=5, wrap="word")
        self.m_txt_note.pack(fill="both", expand=True)
        buttons = ttk.Frame(note_frame)
        buttons.pack(fill="x", pady=(6, 0))
        self.button(buttons, "3. Gửi Ban giám hiệu", self.send_new, P.SUBMIT_REPORTS, style="Accent.TButton")
        self.button(buttons, "Lưu nháp", self.save_draft, P.SUBMIT_REPORTS)
        # hàng nút đặt ở đáy TRƯỚC khi đặt các khung giãn được -> không bao giờ bị đẩy khuất khỏi cửa sổ
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Label(self, text="Báo cáo của tôi (nháp, đã gửi, phản hồi của Ban giám hiệu)",
                  style="Section.TLabel").pack(anchor="w", pady=(14, 4))
        self.m_fg_mine = DataTable(self, [("Mã", 60), ("Loại báo cáo", 220), ("Kỳ", 200), ("Trạng thái", 170),
                                     ("Gửi lúc", 120), ("Ý kiến BGH", 300)], height=5)
        self.m_fg_mine.pack(fill="both", expand=True)
        self.m_fg_mine.on_double_click(self.view_mine)
        self.button(actions, "Xem báo cáo", self.view_mine, style="Accent.TButton")
        self.button(actions, "Sửa ghi chú", self.open_mine)
        self.button(actions, "Cập nhật số liệu mới", self.refresh_data)
        self.button(actions, "Gửi / gửi lại BGH", self.send_existing)
        self.button(actions, "Xuất file", self.export)
        self.button(actions, "Xóa nháp", self.delete_draft)
        self.specs: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ chọn loại / tham số
    def refresh(self) -> None:
        self.specs = self.system.reports.available_types(self.user)
        labels = [s["label"] for s in self.specs]
        self.m_cbo_type["values"] = labels
        if self.m_cbo_type.get() not in labels:
            self.m_cbo_type.set(labels[0] if labels else "")
            self._type_changed()
        classes = self.system.classes_for(self.user)
        restricted = self.scope_class_ids() is not None
        options = (["(các lớp phụ trách)"] if restricted and len(classes) > 1 else []) + \
            ([] if restricted else ["(toàn trường)"]) + [f"{c.id} - {c.name}" for c in classes]
        self.m_cbo_class["values"] = options
        if self.m_cbo_class.get() not in options:
            self.m_cbo_class.set(options[0] if options else "")
        items = self.system.reports.mine()
        self.m_fg_mine.set_rows([[r.id, r.label, r.period_text, r.status.value, r.sent_at.replace("T", " ")[5:],
                             r.review_comment] for r in items], [r.id for r in items],
                           [STATUS_TAGS[r.status] for r in items])

    def _spec(self) -> dict[str, Any] | None:
        return next((s for s in self.specs if s["label"] == self.m_cbo_type.get()), None)

    def _type_changed(self) -> None:
        spec = self._spec()
        if spec is None:
            return
        today = date.today()
        if spec["period"] == "date":
            self.m_lbl_period.configure(text="Ngày (dd/mm/yyyy):")
            self.period_var.set(format_date(today))
            self.m_txt_period.state(["!disabled"])
        elif spec["period"] == "month":
            self.m_lbl_period.configure(text="Tháng (mm/yyyy):")
            self.period_var.set(month_label(*previous_month(today.month, today.year)) if spec["key"] != "attendance"
                                else month_label(today.month, today.year))
            self.m_txt_period.state(["!disabled"])
        else:
            self.m_lbl_period.configure(text="Kỳ:")
            self.period_var.set("đến hôm nay")
            self.m_txt_period.state(["disabled"])
        self.m_cbo_class.state(["!disabled"] if spec["scope"] else ["disabled"])

    def select_type(self, key: str) -> None:
        """Mở sẵn một loại báo cáo (VD: từ bước 6 ở màn hình Vận hành hôm nay)."""
        self.refresh()
        spec = next((s for s in self.specs if s["key"] == key), None)
        if spec is not None:
            self.m_cbo_type.set(spec["label"])
            self._type_changed()
            self.preview()

    def _params(self) -> tuple[str, dict[str, Any]]:
        spec = self._spec()
        if spec is None:
            raise KindergartenError("Bộ phận của bạn chưa có loại báo cáo nào.")
        params: dict[str, Any] = {}
        if spec["period"] == "date":
            params["on_date"] = parse_date(self.period_var.get(), "Ngày báo cáo")
        elif spec["period"] == "month":
            params["month"], params["year"] = parse_month(self.period_var.get())
        if spec["scope"] and self.m_cbo_class.get() and not self.m_cbo_class.get().startswith("("):
            params["class_id"] = self.m_cbo_class.get().split(" - ")[0]
        return spec["key"], params

    def preview(self) -> None:
        try:
            key, params = self._params()
            report, _saved = self.system.reports.build(key, **params)
            report.data   # tính số liệu ngay để báo lỗi tại đây
        except KindergartenError as exc:
            messagebox.showerror("Không lập được báo cáo", exc.message, parent=self)
            return
        self.open_report(f"Xem trước - {self.m_cbo_type.get()}", report=report,
                         conclusion=self.m_txt_note.get("1.0", "end").strip(), conclusion_title="Ghi chú gửi Ban giám hiệu")

    # ------------------------------------------------------------------ lập / gửi
    def _create(self):
        key, params = self._params()
        return self.system.reports.create(key, self.m_txt_note.get("1.0", "end").strip(), **params)

    def _show_created(self, item: Any, notice: str) -> None:
        if self.m_fg_mine.tree.exists(item.id):
            self.m_fg_mine.tree.selection_set(item.id)
        self.open_report(f"Báo cáo {item.id}", submission=item, notice=notice)

    def save_draft(self) -> None:
        item = self.guard(self._create)
        if item is not None:
            self.m_txt_note.delete("1.0", "end")
            self._show_created(item, f"Đã lưu nháp {item.id} - có thể gửi sau ở bảng 'Báo cáo của tôi'.")

    def send_new(self) -> None:
        try:
            key, params = self._params()
        except KindergartenError as exc:
            messagebox.showerror("Không lập được báo cáo", exc.message, parent=self)
            return
        if not self.confirm(f"Gửi '{self.m_cbo_type.get()}' cho Ban giám hiệu?\nSố liệu được chốt tại thời điểm gửi."):
            return

        def create_and_send():
            item = self.system.reports.create(key, self.m_txt_note.get("1.0", "end").strip(), **params)
            return self.system.reports.submit(item.id)

        item = self.guard(create_and_send)
        if item is not None:
            self.m_txt_note.delete("1.0", "end")
            self._show_created(item, f"Đã gửi {item.id} cho Ban giám hiệu.")

    def _selected(self):
        return self.selected(self.m_fg_mine, self.system.reports.get, "một báo cáo")

    def view_mine(self) -> None:
        item = self._selected()
        if item is not None:
            self.open_report(f"Báo cáo {item.id}", submission=item)

    def open_mine(self) -> None:
        item = self._selected()
        if item is None:
            return
        if not item.editable:
            self.open_report(f"Báo cáo {item.id}", submission=item)
            return
        self.form(f"Ghi chú báo cáo {item.id}",
                  [Field("note", f"{item.label} - {item.period_text}\n"
                                 + (f"BGH yêu cầu: {item.review_comment}\n" if item.review_comment else "")
                                 + "Ghi chú gửi BGH", "textarea", default=item.note or None, width=60,
                         required=False)],
                  lambda v: self.system.reports.set_note(item.id, v["note"]), success="Đã lưu ghi chú.")

    def refresh_data(self) -> None:
        item = self._selected()
        if item is not None:
            self.guard(self.system.reports.refresh_data, item.id, success="Đã cập nhật số liệu mới nhất.")

    def send_existing(self) -> None:
        item = self._selected()
        if item is not None and self.confirm(f"Gửi {item.id} ({item.label}) cho Ban giám hiệu?"):
            sent = self.guard(self.system.reports.submit, item.id)
            if sent is not None:
                self._show_created(sent, f"Đã gửi {sent.id} cho Ban giám hiệu.")

    def export(self) -> None:
        item = self._selected()
        if item is None:
            return
        try:
            path = self.system.reports.export(item.id, "txt", self.app.export_dir)
        except KindergartenError as exc:
            messagebox.showerror("Không xuất được", exc.message, parent=self)
            return
        if messagebox.askyesno("Đã xuất file", f"Đã lưu: {path}\n\nMở thư mục chứa file?", parent=self):
            open_folder(path.parent)

    def delete_draft(self) -> None:
        item = self._selected()
        if item is not None and self.confirm(f"Xóa bản nháp {item.id}?"):
            self.guard(self.system.reports.delete_draft, item.id, success="Đã xóa bản nháp.")


# =============================================================================
class ReportInboxTab(BaseTab):
    """Ban giám hiệu: hộp báo cáo các bộ phận gửi lên - xem, duyệt, yêu cầu bổ sung, xuất file."""

    title = "Báo cáo nhận được"
    group = "Báo cáo"
    permission = P.REVIEW_REPORTS

    def build(self) -> None:
        bar = self.bar()
        ttk.Label(bar, text="Hiển thị:").pack(side="left")
        self.m_cbo_filter = ttk.Combobox(bar, state="readonly", width=24,
                                   values=["Chờ xem", "Hôm nay", "Cần bổ sung", "Đã duyệt", "Tất cả"])
        self.m_cbo_filter.set("Chờ xem")
        self.m_cbo_filter.pack(side="left", padx=4)
        self.m_cbo_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.m_lbl_count = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_count.pack(side="left", padx=12)
        # Nút thao tác luôn nằm ngay dưới thanh lọc (không bị khung nội dung đẩy khuất)
        actions = self.bar(pady=(0, 6))
        self.button(actions, "✔ Duyệt báo cáo đang chọn", self.approve, P.REVIEW_REPORTS, style="Accent.TButton")
        self.button(actions, "Yêu cầu bổ sung", self.revise, P.REVIEW_REPORTS)
        self.button(actions, "Mở toàn bộ báo cáo", self.open_full)
        self.button(actions, "Xuất file", self.export)
        self.button(actions, "Dùng để lập báo cáo toàn trường", self.to_school_report, P.REVIEW_REPORTS,
                    side="right")
        self.m_fg_list = DataTable(self, [("Mã", 60), ("Gửi lúc", 115), ("Người gửi", 170), ("Bộ phận", 150),
                                      ("Loại báo cáo", 210), ("Kỳ", 180), ("Trạng thái", 160)], height=7)
        self.m_fg_list.pack(fill="x")
        self.m_fg_list.on_select(self.show_selected)
        self.m_fg_list.on_double_click(self.approve)
        ttk.Label(self, text="Nội dung báo cáo và ghi chú của người gửi", style="Section.TLabel").pack(
            anchor="w", pady=(6, 0))
        self.m_txt_detail = ReportView(self, height=8)
        self.m_txt_detail.configure(highlightthickness=1, highlightbackground=COLORS["border"])
        self.m_txt_detail.pack(fill="both", expand=True)

    def refresh(self) -> None:
        mode = self.m_cbo_filter.get()
        status = {"Chờ xem": ReportStatus.SENT, "Cần bổ sung": ReportStatus.REVISE,
                  "Đã duyệt": ReportStatus.APPROVED}.get(mode)
        items = self.system.reports.inbox(status, date.today() if mode == "Hôm nay" else None)
        self.m_fg_list.set_rows([[r.id, r.sent_at.replace("T", " ")[5:], r.author_name, r.author_role, r.label,
                              r.period_text, r.status.value] for r in items], [r.id for r in items],
                            [STATUS_TAGS[r.status] for r in items])
        waiting = len(self.system.reports.inbox(ReportStatus.SENT))
        self.m_lbl_count.configure(text=f"{waiting} báo cáo chờ xem")
        self.show_selected()

    def _selected(self):
        return self.selected(self.m_fg_list, self.system.reports.get, "một báo cáo")

    def to_school_report(self) -> None:
        if self.app.main is not None and self.app.main.show_tab("SchoolReportTab"):
            self.app.main.current.load_sources()

    def show_selected(self) -> None:
        report_id = self.m_fg_list.selected_id()
        item = self.system.reports.get_or_none(report_id) if report_id else None
        if item is None:
            self.m_txt_detail.show_message("Chọn một báo cáo trong bảng để xem nội dung và ghi chú của người gửi.")
        else:
            self.m_txt_detail.render_submission(item, self.system)

    def open_full(self) -> None:
        item = self._selected()
        if item is not None:
            self.open_report(f"Báo cáo {item.id}", submission=item)

    def approve(self) -> None:
        item = self._selected()
        if item is not None and item.status is not ReportStatus.SENT:
            messagebox.showinfo("Không cần duyệt", f"Báo cáo {item.id} đang ở trạng thái '{item.status.value}'.",
                                parent=self)
            return
        if item is not None:
            self.form(f"Duyệt báo cáo {item.id}", [Field("comment", "Ý kiến (không bắt buộc)", "textarea",
                                                          required=False, width=50)],
                      lambda v: self.system.reports.review(item.id, True, v["comment"]),
                      success="Đã duyệt - người gửi sẽ thấy trạng thái 'BGH đã duyệt'.", submit_text="Duyệt")

    def revise(self) -> None:
        item = self._selected()
        if item is not None:
            self.form(f"Yêu cầu bổ sung {item.id}", [Field("comment", "Cần bổ sung / sửa gì", "textarea", width=50)],
                      lambda v: self.system.reports.review(item.id, False, v["comment"]),
                      success="Đã gửi yêu cầu bổ sung cho người lập.", submit_text="Gửi yêu cầu")

    def export(self) -> None:
        item = self._selected()
        if item is None:
            return
        try:
            path = self.system.reports.export(item.id, "txt", self.app.export_dir)
        except KindergartenError as exc:
            messagebox.showerror("Không xuất được", exc.message, parent=self)
            return
        messagebox.showinfo("Đã xuất file", f"Đã lưu: {path}", parent=self)


# =============================================================================
class SchoolReportTab(BaseTab):
    """Ban giám hiệu lập báo cáo chung toàn trường DỰA TRÊN các báo cáo bộ phận đã gửi trong kỳ
    (chọn báo cáo nguồn, xem ghi chú của từng bộ phận) + số liệu chung + kết luận / chỉ đạo của BGH."""

    title = "Lập báo cáo toàn trường"
    group = "Báo cáo"
    permission = P.REVIEW_REPORTS

    def build(self) -> None:
        bar = self.bar()
        ttk.Label(bar, text="Loại:").pack(side="left")
        self.m_cbo_kind = ttk.Combobox(bar, state="readonly", width=34,
                                 values=["Báo cáo tổng hợp NGÀY toàn trường", "Báo cáo tổng hợp THÁNG toàn trường"])
        self.m_cbo_kind.set(self.m_cbo_kind["values"][0])
        self.m_cbo_kind.pack(side="left", padx=4)
        self.m_cbo_kind.bind("<<ComboboxSelected>>", lambda _e: self._kind_changed())
        self.m_lbl_period = ttk.Label(bar, text="Ngày:")
        self.m_lbl_period.pack(side="left", padx=(12, 0))
        self.period_var = tk.StringVar(value=format_date(date.today()))
        entry = ttk.Entry(bar, textvariable=self.period_var, width=12)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.load_sources())
        self.button(bar, "1. Tải báo cáo các bộ phận trong kỳ", self.load_sources, style="Accent.TButton")
        self.m_lbl_source_info = ttk.Label(bar, style="Muted.TLabel")
        self.m_lbl_source_info.pack(side="left", padx=8)
        actions = self.bar(pady=(0, 6))
        self.button(actions, "Xem báo cáo nguồn", self.view_source)
        self.button(actions, "2. Xem trước báo cáo toàn trường", self.preview)
        self.button(actions, "3. Hoàn tất & lưu hồ sơ", self.finalize, P.REVIEW_REPORTS, style="Accent.TButton")
        self.button(actions, "Lưu nháp", self.save_draft, P.REVIEW_REPORTS)
        self.button(actions, "Báo cáo toàn trường đã lập", self.history, side="right")
        note = ttk.Frame(self)
        note.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Label(note, text="Kết luận / chỉ đạo của Ban giám hiệu:", style="Section.TLabel").pack(anchor="w")
        self.m_txt_note = tk.Text(note, height=4, wrap="word")
        self.m_txt_note.pack(fill="x", pady=(4, 0))
        ttk.Label(self, text="Báo cáo bộ phận đưa vào tổng hợp (bỏ tích để loại ra):", style="Section.TLabel").pack(
            anchor="w", pady=(6, 4))
        self.m_fg_sources = DataTable(self, [("Mã", 60), ("Bộ phận", 140), ("Người gửi", 160), ("Loại", 200),
                                        ("Kỳ", 160), ("Trạng thái", 150), ("Ghi chú của người gửi", 330)],
                                 height=6, checkable=True)
        self.m_fg_sources.pack(fill="both", expand=True)
        self.m_fg_sources.on_double_click(self.view_source)
        self.loaded = False

    def _key(self) -> str:
        return "school_day" if "NGÀY" in self.m_cbo_kind.get() else "school_month"

    def _kind_changed(self) -> None:
        today = date.today()
        if self._key() == "school_day":
            self.m_lbl_period.configure(text="Ngày:")
            self.period_var.set(format_date(today))
        else:
            self.m_lbl_period.configure(text="Tháng:")
            self.period_var.set(month_label(today.month, today.year))
        self.load_sources()

    def _params(self) -> dict[str, Any]:
        if self._key() == "school_day":
            return {"on_date": parse_date(self.period_var.get(), "Ngày")}
        month, year = parse_month(self.period_var.get())
        return {"month": month, "year": year}

    def refresh(self) -> None:
        if not self.loaded:
            self.load_sources()

    def load_sources(self) -> None:
        from ...reports.reports import SchoolSummaryReport
        try:
            report = SchoolSummaryReport(self.system, **self._params())
        except KindergartenError as exc:
            messagebox.showerror("Kỳ không hợp lệ", exc.message, parent=self)
            return
        items = sorted(report.sources(), key=lambda r: (r.author_role, r.sent_at))
        self.m_fg_sources.set_rows([[r.id, r.author_role, r.author_name, r.label, r.period_text, r.status.value,
                                r.note or "-"] for r in items], [r.id for r in items],
                              [STATUS_TAGS[r.status] for r in items])
        self.m_fg_sources.set_checked([r.id for r in items])
        waiting = sum(1 for r in items if r.status is ReportStatus.SENT)
        self.m_lbl_source_info.configure(text=f"{len(items)} báo cáo trong kỳ" + (f" ({waiting} chưa duyệt)" if waiting else ""))
        self.loaded = True

    def _selected_ids(self) -> list[str]:
        return [i for i in self.m_fg_sources.all_ids() if i in self.m_fg_sources._checked]

    def view_source(self) -> None:
        item = self.selected(self.m_fg_sources, self.system.reports.get, "một báo cáo nguồn")
        if item is not None:
            self.open_report(f"Báo cáo {item.id}", submission=item)

    def preview(self) -> None:
        try:
            report, _p = self.system.reports.build(self._key(), report_ids=self._selected_ids(), **self._params())
            report.data
        except KindergartenError as exc:
            messagebox.showerror("Không lập được", exc.message, parent=self)
            return
        self.open_report(f"Xem trước - {self.m_cbo_kind.get()}", report=report,
                         conclusion=self.m_txt_note.get("1.0", "end").strip())

    def _create(self):
        return self.system.reports.create(self._key(), self.m_txt_note.get("1.0", "end").strip(),
                                          report_ids=self._selected_ids(), **self._params())

    def save_draft(self) -> None:
        item = self.guard(self._create)
        if item is not None:
            self.open_report(f"Báo cáo {item.id}", submission=item, notice=f"Đã lưu nháp {item.id}.")

    def finalize(self) -> None:
        if not self._selected_ids() and not self.confirm("Chưa chọn báo cáo bộ phận nào. Vẫn lập báo cáo toàn trường?"):
            return
        if not self.confirm(f"Hoàn tất '{self.m_cbo_kind.get()}' kỳ {self.period_var.get()} với "
                            f"{len(self._selected_ids())} báo cáo nguồn?\nSố liệu được chốt tại thời điểm này."):
            return

        def create_and_finalize():
            item = self._create()
            return self.system.reports.finalize(item.id)

        item = self.guard(create_and_finalize)
        if item is not None:
            self.m_txt_note.delete("1.0", "end")
            self.open_report(f"Báo cáo {item.id}", submission=item,
                             notice=f"Đã lập và lưu hồ sơ {item.id}. Có thể xuất file bằng nút phía trên.")

    def history(self) -> None:
        items = self.system.reports.school_reports()
        if not items:
            messagebox.showinfo("Chưa có", "Chưa lập báo cáo toàn trường nào.", parent=self)
            return
        self.open_report("Báo cáo toàn trường đã lập (10 bản gần nhất)", submissions=items[:10])
