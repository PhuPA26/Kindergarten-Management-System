"""Màn hình console: báo cáo theo quy trình - bộ phận lập báo cáo, ghi chú, gửi Ban giám hiệu;
Ban giám hiệu xem, duyệt / yêu cầu bổ sung. Dashboard tổng quan dành cho Ban giám hiệu."""
from __future__ import annotations

from datetime import date
from typing import Any

from ....auth.user import Permission
from ....reports.submissions import ReportStatus, SubmittedReport
from ..menu import Menu
from .base import Screen

P = Permission


class ReportScreen(Screen):
    title = "Báo cáo"

    def build_menu(self) -> Menu:
        return (self.new_menu()
                .add("Lập báo cáo mới và gửi Ban giám hiệu", self.create, P.SUBMIT_REPORTS)
                .add("Báo cáo của tôi: xem, sửa ghi chú, cập nhật số liệu, gửi lại", self.my_reports,
                     P.SUBMIT_REPORTS)
                .add("Hộp báo cáo nhận được: xem, duyệt, yêu cầu bổ sung", self.inbox, P.REVIEW_REPORTS)
                .add("Lập báo cáo tổng hợp toàn trường từ các báo cáo đã nhận", self.school_report,
                     P.REVIEW_REPORTS)
                .add("Xem báo cáo toàn trường đã lập", self.school_history, P.REVIEW_REPORTS))

    def show_dashboard(self) -> None:
        include_finance = self.auth.has_permission(Permission.VIEW_FINANCE_REPORTS)
        self.io.header("Tổng quan")
        self.io.write(self.system.dashboard(user=self.user).render_text(include_finance))   # L09: theo phạm vi

    def _label(self, item: SubmittedReport) -> str:
        return f"{item.id} - {item.label} ({item.period_text}) - {item.status.value}"

    # ------------------------------------------------------------------ bộ phận
    def _ask_params(self, spec: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if spec["period"] == "date":
            params["on_date"] = self.io.ask_date("Ngày báo cáo", date.today())
        elif spec["period"] == "month":
            params["month"], params["year"] = self.ask_month("Tháng báo cáo", previous=spec["key"] != "attendance")
        if spec["scope"]:
            classes = self.system.classes_for(self.user)
            if len(classes) > 1:
                classroom = self.io.choose(classes, self.class_label, "Chọn lớp (Enter = tất cả lớp của bạn)")
                if classroom is not None:
                    params["class_id"] = classroom.id
        return params

    def create(self) -> None:
        io, reports = self.io, self.system.reports
        specs = reports.available_types()
        spec = self._require(io.choose(specs, lambda s: s["label"], "Loại báo cáo của bộ phận",
                                       "Bộ phận của bạn chưa có loại báo cáo nào."))
        params = self._ask_params(spec)
        report, _saved = reports.build(spec["key"], **params)
        io.write(report.to_text())
        note = io.ask_text("Ghi chú gửi Ban giám hiệu (Enter nếu không có)", required=False) or ""
        item = reports.create(spec["key"], note, **params)
        if self.confirm("Gửi Ban giám hiệu ngay (chọn Không để lưu nháp)"):
            reports.submit(item.id)
            io.success(f"Đã gửi {item.id} cho Ban giám hiệu.")
        else:
            io.success(f"Đã lưu nháp {item.id}.")

    def my_reports(self) -> None:
        io, reports = self.io, self.system.reports
        item = self._require(io.choose(reports.mine(), self._label, "Báo cáo của tôi", "Bạn chưa lập báo cáo nào."))
        io.write(item.full_text(self.system))
        if not item.editable:
            return
        action = io.ask_choice("Thao tác", [("send", "Gửi / gửi lại Ban giám hiệu"), ("note", "Sửa ghi chú"),
                                            ("data", "Cập nhật số liệu mới nhất"), ("done", "Xong")], "send")
        if action == "note":
            reports.set_note(item.id, io.ask_text("Ghi chú", item.note or None, required=False) or "")
            io.success("Đã lưu ghi chú.")
        elif action == "data":
            reports.refresh_data(item.id)
            io.success("Đã cập nhật số liệu.")
        elif action == "send":
            reports.submit(item.id)
            io.success("Đã gửi Ban giám hiệu.")

    # ------------------------------------------------------------------ Ban giám hiệu
    def school_report(self) -> None:
        """BGH chọn kỳ -> hệ thống gom các báo cáo bộ phận đã gửi trong kỳ -> bỏ bớt nếu cần -> kết luận -> lưu."""
        from ....reports.reports import SchoolSummaryReport
        io, reports = self.io, self.system.reports
        kind = io.ask_choice("Loại báo cáo", [("school_day", "Tổng hợp NGÀY toàn trường"),
                                              ("school_month", "Tổng hợp THÁNG toàn trường")], "school_day")
        params: dict[str, Any] = {}
        if kind == "school_day":
            params["on_date"] = io.ask_date("Ngày", date.today())
        else:
            params["month"], params["year"] = self.ask_month("Tháng")
        sources = SchoolSummaryReport(self.system, **params).sources()
        io.table(["STT", "Mã", "Bộ phận", "Người gửi", "Loại", "Trạng thái", "Ghi chú"],
                 [[i, r.id, r.author_role, r.author_name, r.label, r.status.value, r.note or "-"]
                  for i, r in enumerate(sources, 1)], title="BÁO CÁO BỘ PHẬN TRONG KỲ", max_width=40)
        chosen = sources
        if sources:
            drop = io.ask_indexes("STT báo cáo cần LOẠI khỏi tổng hợp (Enter = dùng tất cả)", len(sources),
                                  required=False)
            chosen = [r for i, r in enumerate(sources, 1) if i not in (drop or [])]
        report, _p = reports.build(kind, report_ids=[r.id for r in chosen], **params)
        io.write(report.to_text())
        note = io.ask_text("Kết luận / chỉ đạo của Ban giám hiệu", required=False) or ""
        item = reports.create(kind, note, report_ids=[r.id for r in chosen], **params)
        if self.confirm("Hoàn tất và lưu hồ sơ (chọn Không để lưu nháp)"):
            reports.finalize(item.id)
            io.success(f"Đã lập báo cáo toàn trường {item.id}.")
            self.export_report(item.report(self.system))
        else:
            io.success(f"Đã lưu nháp {item.id}.")

    def school_history(self) -> None:
        item = self._require(self.io.choose(self.system.reports.school_reports(), self._label,
                                            "Báo cáo toàn trường", "Chưa lập báo cáo toàn trường nào."))
        self.io.write(item.full_text(self.system))
        if item.editable and self.confirm("Hoàn tất và lưu hồ sơ bản nháp này"):
            self.system.reports.refresh_data(item.id)
            self.system.reports.finalize(item.id)
            self.io.success("Đã hoàn tất.")

    def inbox(self) -> None:
        io, reports = self.io, self.system.reports
        waiting = reports.inbox(ReportStatus.SENT)
        items = waiting or reports.inbox()
        title = "Báo cáo chờ xem" if waiting else "Báo cáo đã nhận (không có báo cáo chờ xem)"
        item = self._require(io.choose(items, lambda r: f"{self._label(r)} - {r.author_name} ({r.author_role})",
                                       title, "Chưa có báo cáo nào được gửi."))
        io.write(item.full_text(self.system))
        if item.status is not ReportStatus.SENT:
            self.export_report(item.report(self.system))
            return
        action = io.ask_choice("Quyết định", [("ok", "Duyệt"), ("revise", "Yêu cầu bổ sung"), ("later", "Để sau")],
                               "ok")
        if action == "ok":
            reports.review(item.id, True, io.ask_text("Ý kiến (không bắt buộc)", required=False) or "")
            io.success("Đã duyệt.")
        elif action == "revise":
            reports.review(item.id, False, io.ask_text("Cần bổ sung / sửa gì"))
            io.success("Đã gửi yêu cầu bổ sung cho người lập.")
        else:
            io.info("Báo cáo vẫn ở trạng thái chờ xem.")
