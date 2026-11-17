"""T27 - Report (trừu tượng) và EnrollmentReport, AttendanceReport, RevenueReport, DebtReport ghi đè generate().
T28 - export() ra file .txt hoặc .csv.
"""
from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..auth.user import Permission
from ..exceptions import DataStoreError, ValidationError
from ..utils import (format_date, format_key_values, format_percent, format_table, format_vnd, month_label,
                     normalize_text, parse_month, weekday_name)

if TYPE_CHECKING:  # tránh import vòng
    from ..system import KindergartenSystem


@dataclass
class ReportData:
    title: str
    headers: list[str]
    rows: list[list[Any]]
    formats: list[str | None] = field(default_factory=list)   # "money" | "percent" | None cho từng cột
    summary: list[tuple[str, str]] = field(default_factory=list)
    subtitle: str = ""
    generated_at: datetime = field(default_factory=datetime.now)

    def column_format(self, index: int) -> str | None:
        return self.formats[index] if index < len(self.formats) else None


def _display(value: Any, fmt: str | None) -> str:
    if value is None:
        return "-"
    if fmt == "money":
        return format_vnd(value)
    if fmt == "percent":
        return format_percent(value)
    return str(value)


def _raw(value: Any, fmt: str | None) -> Any:
    if value is None:
        return ""
    if fmt == "percent":
        return round(value, 1)
    return value


class Report(ABC):
    """Lớp cha của mọi báo cáo: lớp con chỉ cần ghi đè generate() (đa hình)."""

    title: ClassVar[str] = "Báo cáo"
    file_prefix: ClassVar[str] = "bao_cao"
    column_width: ClassVar[int] = 50

    def __init__(self, system: "KindergartenSystem") -> None:
        self.system = system
        self._data: ReportData | None = None

    @abstractmethod
    def generate(self) -> ReportData:
        """Tổng hợp số liệu của báo cáo."""

    @property
    def data(self) -> ReportData:
        if self._data is None:
            self._data = self.generate()
        return self._data

    def refresh(self) -> ReportData:
        self._data = None
        return self.data

    def to_text(self) -> str:
        data = self.data
        rows = [[_display(v, data.column_format(i)) for i, v in enumerate(row)] for row in data.rows]
        lines = [data.title.upper()]
        if data.subtitle:
            lines.append(data.subtitle)
        lines.append(f"Ngày lập: {data.generated_at:%d/%m/%Y %H:%M}")
        lines.append(format_table(data.headers, rows, max_width=self.column_width))
        if data.summary:
            lines.append(format_key_values(data.summary, title="TỔNG HỢP:"))
        return "\n".join(lines)

    # ------------------------------------------------------------------ T28 - xuất file
    def export(self, path: str | Path | None = None, fmt: str | None = None,
               directory: str | Path = "exports") -> Path:
        """Xuất báo cáo ra .txt hoặc .csv (CSV mã hóa UTF-8 có BOM để Excel đọc đúng tiếng Việt)."""
        if path is not None:
            target = Path(path)
            fmt = (fmt or target.suffix.lstrip(".") or "txt").lower()
            if not target.suffix:
                target = target.with_suffix(f".{fmt}")
        else:
            fmt = (fmt or "txt").lower()
            target = Path(directory) / f"{self.file_prefix}_{datetime.now():%Y%m%d_%H%M%S}.{fmt}"
        if fmt not in ("txt", "csv"):
            raise ValidationError("Chỉ hỗ trợ xuất báo cáo ra file .txt hoặc .csv.")
        self.refresh()   # U16: luôn xuất số liệu mới nhất, không dùng bản tạo từ trước
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "txt":
                target.write_text(self.to_text() + "\n", encoding="utf-8")
            else:
                self._export_csv(target)
        except OSError as exc:   # L21: lỗi ghi file (đang mở trong Excel, ổ đầy...) thành thông báo dễ hiểu
            raise DataStoreError(f"Không ghi được file báo cáo '{target}': {exc.strerror or exc}") from exc
        return target

    def _export_csv(self, target: Path) -> None:
        data = self.data
        with open(target, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow([data.title])
            if data.subtitle:
                writer.writerow([data.subtitle])
            writer.writerow([f"Ngày lập: {data.generated_at:%d/%m/%Y %H:%M}"])
            writer.writerow([])
            writer.writerow(data.headers)
            for row in data.rows:
                writer.writerow([_raw(v, data.column_format(i)) for i, v in enumerate(row)])
            if data.summary:
                writer.writerow([])
                writer.writerows([[label, value] for label, value in data.summary])


class EnrollmentReport(Report):
    """Báo cáo sĩ số theo lớp."""

    title = "Báo cáo sĩ số"
    file_prefix = "bao_cao_si_so"

    def generate(self) -> ReportData:
        classes = self.system.classes
        rows = []
        for classroom in classes.all_sorted():
            teacher = classes.homeroom_teacher(classroom.id)
            kids = classes.class_list(classroom.id)
            boys = sum(1 for k in kids if k.gender == "Nam")
            rows.append([classroom.id, classroom.name, classroom.age_group.label,
                         f"{classroom.min_age}-{classroom.max_age}", teacher.full_name if teacher else "-",
                         classroom.size, classroom.capacity, boys, classroom.size - boys, classroom.fill_rate])
        total_children = len(self.system.children.active())   # L14: chỉ tính trẻ đang học
        enrolled = sum(c.size for c in classes)
        capacity = sum(c.capacity for c in classes)
        summary = [
            ("Tổng số lớp", str(len(classes))),
            ("Tổng số trẻ có hồ sơ", str(total_children)),
            ("Đã xếp lớp", str(enrolled)),
            ("Chờ xếp lớp", str(total_children - enrolled)),
            ("Tổng chỉ tiêu / còn trống", f"{capacity} / {capacity - enrolled}"),
            ("Tỷ lệ lấp đầy chung", format_percent(enrolled / capacity * 100 if capacity else None)),
        ]
        return ReportData(self.title, ["Mã", "Tên lớp", "Khối", "Độ tuổi", "GV chủ nhiệm", "Sĩ số", "Tối đa",
                                       "Nam", "Nữ", "Lấp đầy"], rows,
                          formats=[None] * 9 + ["percent"], summary=summary,
                          subtitle=f"Tính đến ngày {format_date(date.today())}")


class AttendanceReport(Report):
    """Báo cáo chuyên cần tháng (toàn trường hoặc một lớp)."""

    title = "Báo cáo chuyên cần"
    file_prefix = "bao_cao_chuyen_can"
    LOW_RATE = 80.0

    def __init__(self, system: "KindergartenSystem", month: int, year: int, class_id: str | None = None,
                 class_ids: set[str] | None = None) -> None:
        super().__init__(system)
        self.month, self.year = parse_month((month, year))
        self.class_id = class_id
        self.class_ids = class_ids   # phạm vi của giáo viên (L09); None = toàn trường

    def generate(self) -> ReportData:
        attendance = self.system.attendance
        stats = attendance.monthly_stats(self.month, self.year, self.class_id, self.class_ids)
        rows = [[s["child_id"], s["child_name"], s["class_name"], s["present"], s["excused"], s["unexcused"],
                 s["total"], s["rate"]] for s in stats]
        overall = attendance.attendance_rate(self.month, self.year, self.class_id, self.class_ids)
        summary = [("Kỳ báo cáo", f"Tháng {month_label(self.month, self.year)}"),
                   ("Số trẻ", str(len(stats))),
                   ("Tổng lượt điểm danh", str(sum(s["total"] for s in stats))),
                   ("Tỷ lệ chuyên cần chung", format_percent(overall))]
        if not self.class_id:
            for classroom in self.system.classes.all_sorted():
                if self.class_ids is not None and classroom.id not in self.class_ids:
                    continue
                rate = attendance.attendance_rate(self.month, self.year, classroom.id)
                summary.append((f"  - Lớp {classroom.name}", format_percent(rate)))
        low = [s["child_name"] for s in stats if s["rate"] is not None and s["rate"] < self.LOW_RATE]
        summary.append((f"Trẻ chuyên cần dưới {self.LOW_RATE:.0f}%", ", ".join(low) or "Không có"))
        if self.class_id:
            scope = f"Lớp {self.system.classes.get(self.class_id).name}"
        elif self.class_ids is not None:
            scope = "Các lớp: " + (", ".join(self.system.classes.class_name(c) for c in sorted(self.class_ids)) or "-")
        else:
            scope = "Toàn trường"
        return ReportData(self.title, ["Mã", "Họ tên", "Lớp", "Có mặt", "Có phép", "Không phép", "Tổng ngày",
                                       "Tỷ lệ"], rows, formats=[None] * 7 + ["percent"], summary=summary,
                          subtitle=f"{scope} - tháng {month_label(self.month, self.year)}")


class RevenueReport(Report):
    """Báo cáo doanh thu học phí tháng theo lớp."""

    title = "Báo cáo doanh thu"
    file_prefix = "bao_cao_doanh_thu"

    def __init__(self, system: "KindergartenSystem", month: int, year: int) -> None:
        super().__init__(system)
        self.month, self.year = parse_month((month, year))

    def generate(self) -> ReportData:
        invoices = self.system.invoices.invoices_of_month(self.month, self.year)
        groups: dict[str, list] = {}
        for invoice in invoices:
            groups.setdefault(invoice.class_name or "Khác", []).append(invoice)
        rows = []
        for class_name in sorted(groups, key=normalize_text):
            items = groups[class_name]
            rows.append([class_name, len(items), sum(i.tuition_amount for i in items),
                         sum(i.meal_amount for i in items), sum(i.extra_amount for i in items),
                         sum(i.discount_amount for i in items), sum(i.total for i in items),
                         sum(i.paid_amount for i in items), sum(i.balance for i in items)])
        summary_data = self.system.invoices.revenue_summary(self.month, self.year)
        if rows:
            rows.append(["TỔNG CỘNG", summary_data["invoice_count"], summary_data["tuition"], summary_data["meal"],
                         summary_data["extra"], summary_data["discount"], summary_data["billed"],
                         summary_data["collected"], summary_data["outstanding"]])
        billed = summary_data["billed"]
        payroll = self.system.employees.total_payroll(self.month, self.year)
        summary = [
            ("Kỳ báo cáo", f"Tháng {month_label(self.month, self.year)}"),
            ("Tổng phải thu", format_vnd(billed)),
            ("Đã thu", format_vnd(summary_data["collected"])),
            ("Tỷ lệ thu", format_percent(summary_data["collected"] / billed * 100 if billed else None)),
            ("Còn phải thu", format_vnd(summary_data["outstanding"])),
            ("Tiền thực thu trong tháng (mọi kỳ)", format_vnd(summary_data["cash_in_month"])),
            ("Quỹ lương tháng", format_vnd(payroll)),
            ("Chênh lệch phải thu - quỹ lương", format_vnd(billed - payroll)),
        ]
        return ReportData(self.title, ["Lớp", "Số HĐ", "Học phí", "Tiền ăn", "Phí khác", "Miễn giảm",
                                       "Phải thu", "Đã thu", "Còn nợ"], rows,
                          formats=[None, None] + ["money"] * 7, summary=summary,
                          subtitle=f"Học phí tháng {month_label(self.month, self.year)}")


class DebtReport(Report):
    """Báo cáo công nợ: danh sách hộ phụ huynh còn nợ."""

    title = "Báo cáo công nợ"
    file_prefix = "bao_cao_cong_no"

    def __init__(self, system: "KindergartenSystem", as_of: date | None = None) -> None:
        super().__init__(system)
        self.as_of = as_of or date.today()

    def generate(self) -> ReportData:
        debtors = self.system.invoices.debtors(self.as_of)
        rows = [[i, d["parent_names"], d["phone"], ", ".join(d["children"]), len(d["invoices"]), d["periods"],
                 d["debt"], d["overdue"]] for i, d in enumerate(debtors, 1)]
        total = sum(d["debt"] for d in debtors)
        overdue = sum(d["overdue"] for d in debtors)
        summary = [("Số hộ còn nợ", str(len(debtors))),
                   ("Tổng công nợ", format_vnd(total)),
                   ("Trong đó quá hạn", format_vnd(overdue))]
        return ReportData(self.title, ["STT", "Phụ huynh", "SĐT", "Trẻ", "Số HĐ", "Kỳ nợ", "Còn nợ", "Quá hạn"],
                          rows, formats=[None] * 6 + ["money", "money"], summary=summary,
                          subtitle=f"Tính đến ngày {format_date(self.as_of)}")


class PayrollReport(Report):
    """Bảng lương tháng (bổ sung cho T15): mỗi nhân sự tự tính lương theo lớp của mình."""

    title = "Bảng lương tháng"
    file_prefix = "bang_luong"
    column_width = 110

    def __init__(self, system: "KindergartenSystem", month: int, year: int) -> None:
        super().__init__(system)
        self.month, self.year = parse_month((month, year))

    def generate(self) -> ReportData:
        employees = self.system.employees
        payroll = employees.payroll(self.month, self.year)                 # P05: tính một lần
        headers, rows = employees.payroll_table(self.month, self.year, payroll)
        for row, item in zip(rows, payroll):
            row[-1] = item["salary"]  # giữ số nguyên để xuất CSV tính toán được
        total = sum(item["salary"] for item in payroll)
        teachers = sum(item["salary"] for item in payroll if item["type"] == "Giáo viên")
        summary = [("Số nhân sự", str(len(rows))),
                   ("Lương khối giáo viên", format_vnd(teachers)),
                   ("Lương khối nhân viên", format_vnd(total - teachers)),
                   ("Tổng quỹ lương", format_vnd(total)),
                   ("Trạng thái kỳ lương", "Đã chốt" if employees.is_closed(self.month, self.year) else "Chưa chốt")]
        return ReportData(self.title, headers, rows, formats=[None] * 6 + ["money"], summary=summary,
                          subtitle=f"Tháng {month_label(self.month, self.year)}")


class EndOfDayReport(Report):
    """Bước 6 - báo cáo cuối ngày cho Ban giám hiệu: tổng hợp tự động từ đón trẻ, điểm danh, nhật ký ăn ngủ,
    trao đổi phụ huynh và trả trẻ của từng lớp (không cần giáo viên tổng hợp thủ công)."""

    title = "Báo cáo cuối ngày"
    file_prefix = "bao_cao_cuoi_ngay"
    column_width = 40

    def __init__(self, system: "KindergartenSystem", on_date: Any = None, class_ids: set[str] | None = None,
                 class_id: str | None = None) -> None:
        super().__init__(system)
        from ..utils import parse_date
        self.on_date = parse_date(on_date) if on_date else date.today()
        self.class_ids = {class_id} if class_id else class_ids

    def generate(self) -> ReportData:
        s, d = self.system, self.on_date
        classes = [c for c in s.classes.all_sorted() if self.class_ids is None or c.id in self.class_ids]
        if not s.calendar.is_school_day(d):
            return ReportData(self.title, ["Ghi chú"], [[s.calendar.reason_not_school_day(d)]],
                              subtitle=f"Ngày {format_date(d)}")
        summaries = [s.daily.class_summary(c.id, d) for c in classes]
        rows = [[x["class"].name, x["teacher"], x["size"], x["checked_in"], x["present"],
                 x["excused"] + x["unexcused"], f"{x['logs_sent']}/{x['present']}",
                 f"{x['medicine_done']}/{x['medicine']}", x["open_messages"], f"{x['picked_up']}/{x['present']}"]
                for x in summaries]
        total = lambda key: sum(x[key] for x in summaries)  # noqa: E731
        summary = [("Sĩ số / đã đón đầu ngày", f"{total('size')} / {total('checked_in')}"),
                   ("Có mặt / vắng có phép / vắng không phép",
                    f"{total('present')} / {total('excused')} / {total('unexcused')}"),
                   ("Nhật ký ăn ngủ đã gửi phụ huynh", f"{total('logs_sent')}/{total('present')} trẻ, phụ huynh đã xem "
                                                       f"{total('logs_seen')}, phản hồi {total('parent_replies')}"),
                   ("Dặn uống thuốc đã thực hiện", f"{total('medicine_done')}/{total('medicine')}"),
                   ("Tin phụ huynh trong ngày / còn chờ xử lý", f"{total('messages')} / {total('open_messages')}"),
                   ("Đã trả trẻ", f"{total('picked_up')}/{total('present')}")]
        not_picked = [f"{name} ({x['class'].name})" for x in summaries for name in x["not_picked_up"]]
        summary.append(("Trẻ CHƯA được đón về", ", ".join(not_picked) or "Không có"))
        absent = [f"{name} ({x['class'].name}, {status.lower()}{': ' + note if note else ''})"
                  for x in summaries for name, status, note in x["absent_names"]]
        summary.append(("Trẻ vắng", "; ".join(absent) or "Không có"))
        health = [f"{name}: {note}" for x in summaries for name, note in x["health_notes"]]
        summary.append(("Ghi chú sức khỏe trong ngày", "; ".join(health) or "Không có"))
        return ReportData(self.title, ["Lớp", "GV chủ nhiệm", "Sĩ số", "Đã đón", "Có mặt", "Vắng", "Nhật ký gửi",
                                       "Thuốc", "Tin chờ", "Đã trả"], rows, summary=summary,
                          subtitle=f"{weekday_name(d)} {format_date(d)}")


class MenuWeekReport(Report):
    """Báo cáo bếp: thực đơn tuần, năng lượng từng ngày và các món cần thay cho trẻ dị ứng."""

    title = "Báo cáo bếp - thực đơn tuần"
    file_prefix = "bao_cao_bep"
    column_width = 45

    def __init__(self, system: "KindergartenSystem", on_date: Any = None) -> None:
        super().__init__(system)
        from ..utils import parse_date
        self.on_date = parse_date(on_date) if on_date else date.today()

    def generate(self) -> ReportData:
        menus = self.system.menus
        headers, rows = menus.week_table(self.on_date)
        warnings = menus.week_allergy_warnings(self.on_date)
        days = [d for d, m in menus.week_menus(self.on_date)]
        planned = sum(1 for _d, m in menus.week_menus(self.on_date) if m is not None)
        summary = [("Số ngày đã có thực đơn", f"{planned}/{len(days)}"),
                   ("Món cần thay cho trẻ dị ứng", str(len(warnings)))]
        summary += [(f"  {format_date(w.menu_date)} {w.meal.name}", f"{w.child.full_name} ({w.class_name}) dị ứng "
                     f"{w.allergy.allergen}") for w in warnings]
        return ReportData(self.title, headers, rows, summary=summary,
                          subtitle=f"Tuần {format_date(days[0])} - {format_date(days[-1])}")


class PickupDayReport(Report):
    """Báo cáo đón - trả trẻ trong ngày (bảo vệ / giáo viên): giờ đến, người đưa, giờ về, người đón."""

    title = "Báo cáo đón - trả trẻ"
    file_prefix = "bao_cao_don_tra"
    column_width = 40

    def __init__(self, system: "KindergartenSystem", on_date: Any = None, class_id: str | None = None,
                 class_ids: set[str] | None = None) -> None:
        super().__init__(system)
        from ..utils import parse_date
        self.on_date = parse_date(on_date) if on_date else date.today()
        self.class_ids = {class_id} if class_id else class_ids

    def generate(self) -> ReportData:
        s, d = self.system, self.on_date
        rows = []
        arrived = picked = 0
        for classroom in s.classes.all_sorted():
            if self.class_ids is not None and classroom.id not in self.class_ids:
                continue
            for row in s.daily.class_day(classroom.id, d):
                record = row["record"]
                if record is not None and record.is_present:
                    arrived += 1
                    picked += record.picked_up
                    rows.append([classroom.name, row["child"].full_name, record.arrived_at[11:16] or "-",
                                 record.brought_by or "-", record.picked_up_at[11:16] or "CHƯA ĐÓN",
                                 record.picked_up_by or "-"])
                else:
                    status = record.status.value if record else ("Nghỉ có phép" if row["leave"] else "Vắng")
                    rows.append([classroom.name, row["child"].full_name, status, "", "", ""])
        summary = [("Số trẻ đến trường", str(arrived)), ("Đã trả", f"{picked}/{arrived}")]
        return ReportData(self.title, ["Lớp", "Trẻ", "Giờ đến", "Người đưa", "Giờ về", "Người đón"], rows,
                          summary=summary, subtitle=f"{weekday_name(d)} {format_date(d)}")


class HealthReport(Report):
    """Báo cáo y tế: trẻ cần chú ý dinh dưỡng, danh sách dị ứng, ghi chú sức khỏe trong tháng."""

    title = "Báo cáo y tế - sức khỏe trẻ"
    file_prefix = "bao_cao_y_te"

    def __init__(self, system: "KindergartenSystem", class_id: str | None = None,
                 class_ids: set[str] | None = None) -> None:
        super().__init__(system)
        self.class_ids = {class_id} if class_id else class_ids

    def generate(self) -> ReportData:
        s = self.system
        child_ids = None if self.class_ids is None else \
            {c.id for c in s.children.all_sorted() if c.class_id in self.class_ids}
        rows = []
        for child, record in s.health.children_needing_attention(child_ids):
            rows.append([child.full_name, s.classes.class_name(child.class_id), format_date(record.measure_date),
                         record.height_cm, record.weight_kg, record.bmi_text, record.assess().value])
        allergies = [(c, a) for c, items in s.health.children_with_allergies() for a in items
                     if child_ids is None or c.id in child_ids]
        summary = [("Trẻ cần chú ý dinh dưỡng", str(len(rows))), ("Trẻ có dị ứng", str(len({c.id for c, _ in allergies})))]
        summary += [(f"  {c.full_name}", f"dị ứng {a.allergen} (mức {a.severity.value.lower()})") for c, a in allergies]
        return ReportData(self.title, ["Trẻ", "Lớp", "Ngày đo", "Cao", "Nặng", "BMI", "Đánh giá"], rows,
                          summary=summary, subtitle=f"Tính đến ngày {format_date(date.today())}")


class SchoolSummaryReport(Report):
    """Ban giám hiệu: báo cáo tổng hợp TOÀN TRƯỜNG dựa trên các báo cáo bộ phận đã gửi trong kỳ
    (kèm ghi chú của người gửi) và số liệu chung của trường."""

    title = "Báo cáo tổng hợp toàn trường"
    file_prefix = "bao_cao_toan_truong"
    column_width = 45

    def __init__(self, system: "KindergartenSystem", on_date: Any = None, month: int | None = None,
                 year: int | None = None, report_ids: list[str] | None = None) -> None:
        super().__init__(system)
        from ..utils import parse_date
        self.on_date = parse_date(on_date) if on_date else None
        self.month, self.year = parse_month((month, year)) if month else (None, None)
        if self.on_date is None and self.month is None:
            self.on_date = date.today()
        self.report_ids = list(report_ids) if report_ids is not None else None

    def in_period(self, item: Any) -> bool:
        """Báo cáo bộ phận có thuộc kỳ tổng hợp không (theo kỳ của báo cáo, hoặc ngày gửi)."""
        from ..utils import parse_date
        p = item.params
        if self.on_date is not None:
            return p.get("on_date") == self.on_date.isoformat() or (not p.get("on_date") and not p.get("month")
                                                                     and item.sent_at[:10] == self.on_date.isoformat())
        if p.get("month"):
            return (p["month"], p["year"]) == (self.month, self.year)
        day = parse_date(p["on_date"]) if p.get("on_date") else parse_date(item.sent_at[:10])
        return (day.month, day.year) == (self.month, self.year)

    def sources(self) -> list[Any]:
        received = [r for r in self.system.reports.inbox() if r.type_key not in ("school_day", "school_month")]
        if self.report_ids is not None:
            return [r for r in received if r.id in self.report_ids]
        return [r for r in received if self.in_period(r)]

    def generate(self) -> ReportData:
        s = self.system
        sources = sorted(self.sources(), key=lambda r: (r.author_role, r.sent_at))
        rows = [[r.id, r.author_role, r.author_name, r.label, r.period_text, r.status.value, r.note or "-"]
                for r in sources]
        summary: list[tuple[str, str]] = []
        active = len(s.children.active())
        if self.on_date is not None:
            d = self.on_date
            period = f"{weekday_name(d)} {format_date(d)}"
            if s.calendar.is_school_day(d):
                classes = [s.daily.class_summary(c.id, d) for c in s.classes.all_sorted()]
                total = lambda key: sum(x[key] for x in classes)  # noqa: E731
                eod = s.reports.end_of_day_status(d)
                missing = [c.name for c in eod["classes"] if c.id not in eod["sent"]]
                summary += [("Sĩ số đang học", str(active)),
                            ("Có mặt / vắng có phép / vắng không phép",
                             f"{total('present')} / {total('excused')} / {total('unexcused')}"),
                            ("Nhật ký ăn ngủ đã gửi phụ huynh", f"{total('logs_sent')}/{total('present')} trẻ"),
                            ("Dặn uống thuốc đã thực hiện", f"{total('medicine_done')}/{total('medicine')}"),
                            ("Tin phụ huynh còn chờ xử lý", str(total("open_messages"))),
                            ("Đã trả trẻ", f"{total('picked_up')}/{total('present')}"),
                            ("Lớp đã gửi báo cáo cuối ngày", f"{len(eod['sent'])}/{len(eod['classes'])}"
                             + (f" (chưa gửi: {', '.join(missing)})" if missing else ""))]
            else:
                summary.append(("Ngày", s.calendar.reason_not_school_day(d)))
        else:
            m, y = self.month, self.year
            period = f"tháng {month_label(m, y)}"
            revenue = s.invoices.revenue_summary(m, y)
            debtors = s.invoices.debtors()
            summary += [("Sĩ số đang học", str(active)),
                        ("Tỷ lệ chuyên cần toàn trường", format_percent(s.attendance.attendance_rate(m, y))),
                        ("Học phí phải thu / đã thu", f"{format_vnd(revenue['billed'])} / "
                                                      f"{format_vnd(revenue['collected'])}"),
                        ("Tổng công nợ hiện tại", f"{format_vnd(sum(x['debt'] for x in debtors))} "
                                                  f"({len(debtors)} hộ)"),
                        ("Quỹ lương tháng", format_vnd(s.employees.total_payroll(m, y)))]
        approved = sum(1 for r in sources if r.status.name == "APPROVED")
        summary.append(("Báo cáo bộ phận đưa vào tổng hợp", f"{len(sources)} (đã duyệt {approved}, "
                                                            f"chờ xem {sum(1 for r in sources if r.status.name == 'SENT')})"))
        for r in sources:   # trích phần tổng hợp của từng báo cáo nguồn
            for label, value in r.data.get("summary", [])[:3]:
                summary.append((f"  [{r.id} {r.author_role}] {label}", str(value)))
        return ReportData(self.title, ["Mã BC", "Bộ phận", "Người gửi", "Loại báo cáo", "Kỳ", "Trạng thái",
                                       "Ghi chú của người gửi"], rows, summary=summary, subtitle=f"Kỳ: {period}")


class SnapshotReport(Report):
    """Báo cáo đã gửi: dùng nguyên số liệu chốt lúc gửi (không tính lại), để xem / xuất file."""

    def __init__(self, system: "KindergartenSystem", data: ReportData, file_prefix: str = "bao_cao") -> None:
        super().__init__(system)
        self._snapshot = data
        self.file_prefix = file_prefix   # type: ignore[misc]
        self.title = data.title          # type: ignore[misc]

    def generate(self) -> ReportData:
        return self._snapshot


def report_data_to_dict(data: ReportData) -> dict[str, Any]:
    return {"title": data.title, "headers": data.headers, "rows": data.rows, "formats": data.formats,
            "summary": [list(item) for item in data.summary], "subtitle": data.subtitle,
            "generated_at": data.generated_at.isoformat(timespec="seconds")}


def report_data_from_dict(raw: dict[str, Any]) -> ReportData:
    return ReportData(raw["title"], list(raw["headers"]), [list(r) for r in raw["rows"]], list(raw.get("formats", [])),
                      [tuple(item) for item in raw.get("summary", [])], raw.get("subtitle", ""),
                      datetime.fromisoformat(raw["generated_at"]) if raw.get("generated_at") else datetime.now())


# Danh mục báo cáo theo nghiệp vụ: mỗi bộ phận chỉ thấy loại báo cáo của mình (permission = quyền nghiệp vụ cần có).
# period: "date" (theo ngày), "month" (theo tháng), "none".  scope: True = báo cáo theo lớp (giáo viên chỉ lớp mình).
REPORT_TYPES: list[dict[str, Any]] = [
    {"key": "school_day", "label": "Báo cáo tổng hợp NGÀY toàn trường", "cls": SchoolSummaryReport,
     "period": "date", "scope": False, "permission": Permission.REVIEW_REPORTS, "sources": True},
    {"key": "school_month", "label": "Báo cáo tổng hợp THÁNG toàn trường", "cls": SchoolSummaryReport,
     "period": "month", "scope": False, "permission": Permission.REVIEW_REPORTS, "sources": True},
    {"key": "end_of_day", "label": "Báo cáo cuối ngày của lớp", "cls": EndOfDayReport, "period": "date",
     "scope": True, "permission": Permission.DAILY_LOG},
    {"key": "attendance", "label": "Báo cáo chuyên cần tháng", "cls": AttendanceReport, "period": "month",
     "scope": True, "permission": Permission.TAKE_ATTENDANCE},
    {"key": "pickup", "label": "Báo cáo đón - trả trẻ trong ngày", "cls": PickupDayReport, "period": "date",
     "scope": True, "permission": Permission.CHECK_IN_OUT},
    {"key": "health", "label": "Báo cáo y tế - sức khỏe trẻ", "cls": HealthReport, "period": "none",
     "scope": True, "permission": Permission.MANAGE_HEALTH},
    {"key": "menu", "label": "Báo cáo bếp - thực đơn tuần", "cls": MenuWeekReport, "period": "date",
     "scope": False, "permission": Permission.MANAGE_MENU},
    {"key": "revenue", "label": "Báo cáo doanh thu tháng", "cls": RevenueReport, "period": "month",
     "scope": False, "permission": Permission.MANAGE_FINANCE},
    {"key": "debt", "label": "Báo cáo công nợ", "cls": DebtReport, "period": "none",
     "scope": False, "permission": Permission.MANAGE_FINANCE},
    {"key": "payroll", "label": "Bảng lương tháng", "cls": PayrollReport, "period": "month",
     "scope": False, "permission": Permission.VIEW_PAYROLL},
    {"key": "enrollment", "label": "Báo cáo sĩ số toàn trường", "cls": EnrollmentReport, "period": "none",
     "scope": False, "permission": Permission.MANAGE_CLASSES},
]
REPORT_BY_KEY = {spec["key"]: spec for spec in REPORT_TYPES}
