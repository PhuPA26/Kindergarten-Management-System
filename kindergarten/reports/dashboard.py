"""T29 - Dashboard: màn hình tổng quan (tổng số trẻ, lớp, doanh thu tháng, tỷ lệ chuyên cần...).

Sau rà soát: ngày nghỉ không nhắc "chưa điểm danh" (L19); có thể giới hạn theo lớp cho giáo viên (L09);
render_text() nhận lại số liệu đã tính, không tính hai lần (P05); thêm nhắc trẻ lệch độ tuổi lớp (L14).
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from ..utils import format_date, format_key_values, format_percent, format_vnd, month_label

if TYPE_CHECKING:
    from ..system import KindergartenSystem


class Dashboard:
    def __init__(self, system: "KindergartenSystem", today: date | None = None,
                 class_ids: set[str] | None = None) -> None:
        self.system = system
        self.today = today or date.today()
        self.class_ids = class_ids   # None = toàn trường

    def collect(self, include_finance: bool = True) -> dict[str, Any]:
        s, today, scope = self.system, self.today, self.class_ids
        month, year = today.month, today.year
        classes = [c for c in s.classes.all_sorted() if scope is None or c.id in scope]
        children = [c for c in s.children.active() if scope is None or c.class_id in scope]
        child_ids = {c.id for c in children}
        enrolled = sum(c.size for c in classes)
        capacity = sum(c.capacity for c in classes)
        school_day = s.calendar.is_school_day(today)
        daily = s.attendance.daily_summary(today, scope) if school_day else []
        stats: dict[str, Any] = {
            "today": today,
            "month_label": month_label(month, year),
            "scope_label": "toàn trường" if scope is None else ", ".join(c.name for c in classes) or "(không có lớp)",
            "is_school_day": school_day,
            "day_note": "" if school_day else s.calendar.reason_not_school_day(today),
            "total_children": len(children),
            "enrolled": enrolled,
            "unassigned": len(children) - enrolled if scope is None else 0,
            "classes": len(classes),
            "capacity": capacity,
            "teachers": len(s.employees.teachers()),
            "staff": len(s.employees.staff_members()),
            "taken_today": sum(d["taken"] for d in daily),
            "present_today": sum(d["present"] for d in daily),
            "absent_today": sum(d["excused"] + d["unexcused"] for d in daily),
            "classes_not_taken": [d["class"].name for d in daily if d["size"] and d["taken"] < d["size"]],
            "attendance_rate_month": s.attendance.attendance_rate(month, year, class_ids=scope),
            "open_messages": len(s.daily.inbox(scope, only_open=True)),
            "medicine_today": s.daily.medicine_today(scope, today),
            "nutrition_alerts": s.health.children_needing_attention(child_ids),
            "allergy_warnings_today": s.menus.allergy_warnings(today, class_ids=scope),
            "birthdays": s.children.birthdays_in_month(month, child_ids),
            "age_mismatches": [(c, k) for c, k in s.classes.age_mismatches() if scope is None or k.id in scope],
        }
        if include_finance:
            revenue = s.invoices.revenue_summary(month, year)
            debtors = s.invoices.debtors(today)
            stats.update(
                revenue_month=revenue["cash_in_month"],
                billed_month=revenue["billed"],
                invoices_month=revenue["invoice_count"],
                total_debt=sum(d["debt"] for d in debtors),
                overdue_debt=sum(d["overdue"] for d in debtors),
                debtor_count=len(debtors),
            )
        return stats

    def render_text(self, include_finance: bool = True, stats: dict[str, Any] | None = None) -> str:
        st = stats if stats is not None else self.collect(include_finance)
        include_finance = include_finance and "revenue_month" in st
        lines = [f"TỔNG QUAN NGÀY {format_date(st['today'])} - {st['scope_label']}"]
        info = [("Tổng số trẻ đang học", f"{st['total_children']} (đã xếp lớp {st['enrolled']}"
                 + (f", chờ xếp lớp {st['unassigned']})" if self.class_ids is None else ")")),
                ("Số lớp", f"{st['classes']} lớp, chỉ tiêu {st['capacity']} chỗ, còn trống "
                           f"{max(st['capacity'] - st['enrolled'], 0)}")]
        if self.class_ids is None:
            info.append(("Nhân sự", f"{st['teachers']} giáo viên, {st['staff']} nhân viên"))
        lines.append(format_key_values(info, title="\n[ TRẺ - LỚP - NHÂN SỰ ]"))
        if st["is_school_day"]:
            attendance = [
                ("Điểm danh hôm nay", f"{st['taken_today']}/{st['enrolled']} trẻ (có mặt {st['present_today']}, "
                                      f"vắng {st['absent_today']})"),
                ("Lớp chưa điểm danh xong", ", ".join(st["classes_not_taken"]) or "không"),
            ]
        else:
            attendance = [("Hôm nay", f"Không phải ngày học - {st['day_note']}")]
        attendance.append((f"Tỷ lệ chuyên cần tháng {st['month_label']}", format_percent(st["attendance_rate_month"])))
        lines.append(format_key_values(attendance, title="\n[ CHUYÊN CẦN ]"))
        if include_finance:
            lines.append(format_key_values([
                (f"Thực thu trong tháng {st['month_label']}", format_vnd(st["revenue_month"])),
                (f"Hóa đơn tháng {st['month_label']}",
                 f"{st['invoices_month']} hóa đơn, phải thu {format_vnd(st['billed_month'])}"),
                ("Tổng công nợ", f"{format_vnd(st['total_debt'])} ({st['debtor_count']} hộ, quá hạn "
                                 f"{format_vnd(st['overdue_debt'])})"),
            ], title="\n[ HỌC PHÍ ]"))
        alerts = []
        if st["open_messages"]:
            alerts.append(f"{st['open_messages']} tin nhắn / dặn thuốc / xin nghỉ của phụ huynh chờ xử lý")
        pending_medicine = [m for m in st["medicine_today"] if m.status.value != "Đã thực hiện"]
        if pending_medicine:
            alerts.append(f"⚠ {len(pending_medicine)} lượt dặn uống thuốc hôm nay chưa thực hiện")
        if st["nutrition_alerts"]:
            names = ", ".join(f"{c.full_name} ({r.assess().value.lower()})" for c, r in st["nutrition_alerts"][:5])
            alerts.append(f"{len(st['nutrition_alerts'])} trẻ cần chú ý dinh dưỡng: {names}")
        if st["allergy_warnings_today"]:
            alerts.append(f"⚠ Thực đơn hôm nay có {len(st['allergy_warnings_today'])} cảnh báo dị ứng")
        if st["age_mismatches"]:
            alerts.append(f"{len(st['age_mismatches'])} trẻ đã lớn hơn độ tuổi lớp đang học (cần lên lớp/ra trường)")
        if st["birthdays"]:
            alerts.append("Sinh nhật tháng này: " + ", ".join(f"{c.full_name} ({c.dob:%d/%m})"
                                                               for c in st["birthdays"]))
        lines.append("\n[ CẢNH BÁO - NHẮC VIỆC ]")
        lines += [f"  - {a}" for a in alerts] or ["  Không có cảnh báo."]
        return "\n".join(lines)
