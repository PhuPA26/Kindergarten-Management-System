"""Quy trình báo cáo nội bộ: bộ phận lập báo cáo -> ghi chú -> gửi Ban giám hiệu -> BGH xem, duyệt hoặc
yêu cầu bổ sung -> bộ phận cập nhật số liệu, sửa ghi chú rồi gửi lại.

Số liệu được CHỐT tại thời điểm gửi (ảnh chụp), nên BGH xem đúng cái đã được gửi dù dữ liệu thay đổi sau đó.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..auth.user import Permission, Role
from ..core.base_manager import BaseManager
from ..core.base_model import BaseModel
from ..exceptions import KindergartenError, PermissionDeniedError, ValidationError
from ..utils import format_date, month_label, normalize_spaces, parse_date, parse_month
from .reports import REPORT_BY_KEY, REPORT_TYPES, Report, SnapshotReport, report_data_from_dict, report_data_to_dict

if TYPE_CHECKING:
    from ..system import KindergartenSystem


def _now() -> str:
    return datetime.now().isoformat(timespec="minutes")


class ReportStatus(Enum):
    DRAFT = "Nháp"
    SENT = "Đã gửi - chờ BGH xem"
    APPROVED = "BGH đã duyệt"
    REVISE = "BGH yêu cầu bổ sung"
    FINAL = "BGH đã lập - lưu hồ sơ"


class SubmittedReport(BaseModel):
    PREFIX = "BC"

    def __init__(self, type_key: str, params: dict[str, Any], data: dict[str, Any], author: str, author_name: str,
                 author_role: str, note: str = "", status: Any = ReportStatus.DRAFT, created_at: str = "",
                 sent_at: str = "", reviewed_by: str = "", reviewed_at: str = "", review_comment: str = "",
                 history: list[dict[str, str]] | None = None, id: str | None = None) -> None:
        super().__init__(id)
        if type_key not in REPORT_BY_KEY:
            raise ValidationError(f"Loại báo cáo '{type_key}' không hợp lệ.")
        self.type_key = type_key
        self.params = dict(params)
        self.data = dict(data)
        self.author = author
        self.author_name = author_name
        self.author_role = author_role
        self.note = note
        self.status = status if isinstance(status, ReportStatus) else ReportStatus(status)
        self.created_at = created_at or _now()
        self.sent_at = sent_at
        self.reviewed_by = reviewed_by
        self.reviewed_at = reviewed_at
        self.review_comment = review_comment
        self.history: list[dict[str, str]] = list(history or [])   # nhật ký: gửi, duyệt, yêu cầu bổ sung, gửi lại

    @property
    def note(self) -> str:
        return self._note

    @note.setter
    def note(self, value: Any) -> None:
        self._note = (str(value or "")).strip()[:2000]

    @property
    def label(self) -> str:
        return REPORT_BY_KEY[self.type_key]["label"]

    @property
    def period_text(self) -> str:
        p = self.params
        parts = []
        if p.get("on_date"):
            parts.append(format_date(parse_date(p["on_date"])))
        if p.get("month"):
            parts.append(f"tháng {month_label(p['month'], p['year'])}")
        if p.get("class_name"):
            parts.append(f"lớp {p['class_name']}")
        if p.get("report_ids") is not None:
            parts.append(f"{len(p['report_ids'])} báo cáo nguồn")
        return ", ".join(parts) or "-"

    @property
    def editable(self) -> bool:
        return self.status in (ReportStatus.DRAFT, ReportStatus.REVISE)

    def report(self, system: "KindergartenSystem") -> Report:
        return SnapshotReport(system, report_data_from_dict(self.data), REPORT_BY_KEY[self.type_key]["cls"].file_prefix)

    def full_text(self, system: "KindergartenSystem") -> str:
        lines = [f"[{self.id}] {self.label} - {self.period_text}",
                 f"Người lập: {self.author_name} ({self.author_role}) - trạng thái: {self.status.value}"]
        if self.sent_at:
            lines.append(f"Gửi lúc: {self.sent_at.replace('T', ' ')}")
        lines += ["", self.report(system).to_text(), "", "GHI CHÚ CỦA NGƯỜI LẬP:", f"  {self.note or '(không có)'}"]
        if self.review_comment:
            lines += ["", f"Ý KIẾN BAN GIÁM HIỆU ({self.reviewed_by}, {self.reviewed_at.replace('T', ' ')}):",
                      f"  {self.review_comment}"]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(type_key=self.type_key, params=self.params, data=self.data, author=self.author,
                    author_name=self.author_name, author_role=self.author_role, note=self.note,
                    status=self.status.value, created_at=self.created_at, sent_at=self.sent_at,
                    reviewed_by=self.reviewed_by, reviewed_at=self.reviewed_at, review_comment=self.review_comment,
                    history=self.history)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubmittedReport":
        keys = ("note", "status", "created_at", "sent_at", "reviewed_by", "reviewed_at", "review_comment", "history")
        return cls(data["type_key"], data.get("params", {}), data["data"], data["author"], data.get("author_name", ""),
                   data.get("author_role", ""), id=data["id"], **{k: data[k] for k in keys if k in data})


class ReportCenter(BaseManager[SubmittedReport]):
    entity_name = "báo cáo"

    def __init__(self, system: "KindergartenSystem") -> None:
        super().__init__()
        self.system = system

    # ------------------------------------------------------------------ quyền
    @property
    def _user(self):
        return self.system.auth.current_user

    def available_types(self, user=None) -> list[dict[str, Any]]:
        """Loại báo cáo người dùng được lập (đúng nghiệp vụ của bộ phận)."""
        user = user or self._user
        if user is None:
            return list(REPORT_TYPES)
        if not (user.has_permission(Permission.SUBMIT_REPORTS) or user.has_permission(Permission.REVIEW_REPORTS)):
            return []
        return [spec for spec in REPORT_TYPES if user.has_permission(spec["permission"])]

    def _check_type(self, type_key: str) -> dict[str, Any]:
        spec = REPORT_BY_KEY.get(type_key)
        if spec is None:
            raise ValidationError("Loại báo cáo không hợp lệ.")
        if self._user is not None and spec not in self.available_types():
            raise PermissionDeniedError(f"Bộ phận của bạn không lập '{spec['label']}'.")
        return spec

    def _own(self, report_id: str) -> SubmittedReport:
        report = self.get(report_id)
        if self._user is not None and report.author != self._user.username:
            raise PermissionDeniedError("Chỉ người lập mới sửa / gửi được báo cáo này.")
        return report

    # ------------------------------------------------------------------ lập báo cáo
    def build(self, type_key: str, on_date: Any = None, month: Any = None, year: Any = None,
              class_id: str | None = None, report_ids: list[str] | None = None) -> tuple[Report, dict[str, Any]]:
        """Tạo báo cáo theo tham số; giáo viên chỉ lập cho lớp mình. Báo cáo toàn trường của BGH
        lấy các báo cáo bộ phận đã nhận trong kỳ (hoặc đúng các báo cáo được chọn - report_ids)."""
        spec = self._check_type(type_key)
        kwargs: dict[str, Any] = {}
        params: dict[str, Any] = {}
        if spec.get("sources") and report_ids is not None:
            kwargs["report_ids"] = params["report_ids"] = list(report_ids)
        if spec["period"] == "date":
            d = parse_date(on_date) if on_date else date.today()
            kwargs["on_date"] = params["on_date"] = d.isoformat()
        elif spec["period"] == "month":
            m, y = parse_month((month, year)) if month else (date.today().month, date.today().year)
            kwargs["month"], kwargs["year"] = params["month"], params["year"] = m, y
        if spec["scope"]:
            scope = self.system.class_ids_for(self._user) if self._user is not None else None
            if class_id:
                classroom = self.system.classes.get(class_id)
                if scope is not None and classroom.id not in scope:
                    raise PermissionDeniedError("Giáo viên chỉ lập báo cáo cho lớp mình phụ trách.")
                kwargs["class_id"] = params["class_id"] = classroom.id
                params["class_name"] = classroom.name
            elif scope is not None:
                if not scope:
                    raise KindergartenError("Tài khoản chưa được phân công lớp nào.")
                kwargs["class_ids"] = scope
                params["class_name"] = ", ".join(self.system.classes.class_name(c) for c in sorted(scope))
        return spec["cls"](self.system, **kwargs), params

    def create(self, type_key: str, note: str = "", **params: Any) -> SubmittedReport:
        report, saved = self.build(type_key, **params)
        user = self._user
        item = SubmittedReport(type_key, saved, report_data_to_dict(report.data),
                               user.username if user else "he_thong", user.full_name if user else "Hệ thống",
                               user.portal.replace("Hệ thống ", "") if user else "", note)
        return self.add(item)

    def refresh_data(self, report_id: str) -> SubmittedReport:
        """Cập nhật lại số liệu (khi BGH yêu cầu bổ sung hoặc dữ liệu vừa được sửa)."""
        item = self._own(report_id)
        if not item.editable:
            raise KindergartenError("Báo cáo đã gửi, chờ BGH xem - không cập nhật được.")
        report, _params = self.build(item.type_key, item.params.get("on_date"), item.params.get("month"),
                                     item.params.get("year"), item.params.get("class_id"),
                                     item.params.get("report_ids"))
        item.data = report_data_to_dict(report.data)
        return item

    def set_note(self, report_id: str, note: str) -> SubmittedReport:
        item = self._own(report_id)
        if not item.editable:
            raise KindergartenError("Báo cáo đã gửi, chờ BGH xem - không sửa ghi chú được.")
        item.note = note
        return item

    def submit(self, report_id: str) -> SubmittedReport:
        if self._user is not None:
            self.system.auth.check_permission(Permission.SUBMIT_REPORTS)
        item = self._own(report_id)
        if not item.editable:
            raise KindergartenError("Báo cáo này đã được gửi.")
        if REPORT_BY_KEY[item.type_key].get("sources"):
            raise KindergartenError("Báo cáo toàn trường do BGH lập - dùng 'Hoàn tất & lưu hồ sơ'.")
        resend = item.status is ReportStatus.REVISE
        item.status = ReportStatus.SENT
        item.sent_at = _now()
        item.history.append({"at": item.sent_at, "by": item.author_name, "action": "Gửi lại" if resend else "Gửi"})
        self.system.audit("Gửi báo cáo", item.id, {"type": item.label, "period": item.period_text})
        return item

    def finalize(self, report_id: str) -> SubmittedReport:
        """BGH hoàn tất báo cáo toàn trường của mình: chốt số liệu, lưu hồ sơ (không gửi đi đâu)."""
        if self._user is not None:
            self.system.auth.check_permission(Permission.REVIEW_REPORTS)
        item = self._own(report_id)
        if not item.editable:
            raise KindergartenError("Báo cáo này đã hoàn tất.")
        item.status = ReportStatus.FINAL
        item.sent_at = _now()
        item.history.append({"at": item.sent_at, "by": item.author_name, "action": "Hoàn tất"})
        self.system.audit("Lập báo cáo toàn trường", item.id, {"type": item.label, "period": item.period_text})
        return item

    def school_reports(self) -> list[SubmittedReport]:
        return sorted((r for r in self if REPORT_BY_KEY[r.type_key].get("sources")), key=lambda r: r.created_at,
                      reverse=True)

    def delete_draft(self, report_id: str) -> None:
        item = self._own(report_id)
        if item.status is not ReportStatus.DRAFT:
            raise KindergartenError("Chỉ xóa được báo cáo nháp (chưa gửi).")
        self.remove(item.id)

    # ------------------------------------------------------------------ Ban giám hiệu
    def review(self, report_id: str, approve: bool, comment: str = "") -> SubmittedReport:
        if self._user is not None:
            self.system.auth.check_permission(Permission.REVIEW_REPORTS)
        item = self.get(report_id)
        if item.status is not ReportStatus.SENT:
            raise KindergartenError("Chỉ duyệt được báo cáo đang chờ BGH xem.")
        if not approve and not normalize_spaces(comment):
            raise ValidationError("Hãy ghi rõ cần bổ sung gì để người lập biết.")
        item.status = ReportStatus.APPROVED if approve else ReportStatus.REVISE
        item.review_comment = normalize_spaces(comment)
        item.reviewed_by = self._user.full_name if self._user else "Ban giám hiệu"
        item.reviewed_at = _now()
        item.history.append({"at": item.reviewed_at, "by": item.reviewed_by,
                             "action": "Duyệt" if approve else f"Yêu cầu bổ sung: {item.review_comment}"})
        self.system.audit("Duyệt báo cáo" if approve else "Yêu cầu bổ sung báo cáo", item.id)
        return item

    def inbox(self, status: ReportStatus | None = None, on_date: date | None = None) -> list[SubmittedReport]:
        """Báo cáo các bộ phận đã gửi BGH (không gồm nháp), mới nhất trước."""
        items = [r for r in self if r.status not in (ReportStatus.DRAFT, ReportStatus.FINAL)
                 and (status is None or r.status is status)
                 and (on_date is None or r.sent_at[:10] == on_date.isoformat())]
        return sorted(items, key=lambda r: (r.status is ReportStatus.SENT, r.sent_at), reverse=True)

    def mine(self, username: str | None = None) -> list[SubmittedReport]:
        name = username or (self._user.username if self._user else "")
        return sorted(self.find(author=name), key=lambda r: r.created_at, reverse=True)

    def end_of_day_status(self, on_date: date | None = None, class_ids: set[str] | None = None) -> dict[str, Any]:
        """Bước 6: lớp nào đã gửi báo cáo cuối ngày cho BGH."""
        d = (on_date or date.today()).isoformat()
        sent = {}
        for r in self:
            if r.type_key == "end_of_day" and r.status is not ReportStatus.DRAFT and r.params.get("on_date") == d:
                ids = [r.params["class_id"]] if r.params.get("class_id") else \
                    [c.id for c in self.system.classes_for(self.system.auth.find_by_username(r.author))]
                for class_id in ids:
                    sent[class_id] = r
        classes = [c for c in self.system.classes.all_sorted() if class_ids is None or c.id in class_ids]
        return {"classes": classes, "sent": sent}

    def export(self, report_id: str, fmt: str, directory: str | Path) -> Path:
        item = self.get(report_id)
        return item.report(self.system).export(fmt=fmt, directory=directory)
