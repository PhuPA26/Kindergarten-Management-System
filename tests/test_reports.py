"""Kiểm thử Report và các báo cáo (T27), export .txt/.csv (T28), Dashboard (T29)."""
import csv
import io
from datetime import date

import pytest

from kindergarten.exceptions import ValidationError
from kindergarten.reports.reports import (AttendanceReport, DebtReport, EnrollmentReport, PayrollReport,
                                          RevenueReport)
from kindergarten.utils import previous_month


def test_reports_generate_from_seed(seeded):
    month, year = previous_month(date.today().month, date.today().year)
    enrollment = EnrollmentReport(seeded).data
    assert len(enrollment.rows) == 3 and ("Tổng số trẻ có hồ sơ", "20") in enrollment.summary
    assert len(AttendanceReport(seeded, month, year).data.rows) == 19
    revenue = RevenueReport(seeded, month, year).data
    assert revenue.rows[-1][0] == "TỔNG CỘNG" and revenue.rows[-1][1] == 19
    debt = DebtReport(seeded).data
    assert debt.rows and all(row[6] > 0 for row in debt.rows)
    assert len(PayrollReport(seeded, month, year).data.rows) == 9
    assert "BÁO CÁO DOANH THU" in RevenueReport(seeded, month, year).to_text()


def test_export_txt_and_csv(seeded, tmp_path):
    report = EnrollmentReport(seeded)
    txt = report.export(tmp_path / "si_so.txt")
    csv_path = report.export(tmp_path / "si_so", fmt="csv")
    assert txt.read_text(encoding="utf-8").startswith("BÁO CÁO SĨ SỐ")
    raw = csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM để Excel hiển thị đúng tiếng Việt
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert "Tên lớp" in rows[4]
    with pytest.raises(ValidationError):
        report.export(tmp_path / "bao_cao.pdf")
    default_path = report.export(directory=tmp_path / "exports")
    assert default_path.suffix == ".txt" and default_path.parent.name == "exports"


def test_dashboard(seeded):
    stats = seeded.dashboard().collect()
    assert (stats["total_children"], stats["classes"], stats["teachers"]) == (20, 3, 5)
    rate = stats["attendance_rate_month"]
    assert rate is None or 0 <= rate <= 100
    assert stats["total_debt"] > 0 and stats["open_messages"] >= 1   # tin phụ huynh hôm nay chờ xử lý
    text = seeded.dashboard().render_text(include_finance=False)
    assert "TỔNG QUAN" in text and "HỌC PHÍ" not in text
