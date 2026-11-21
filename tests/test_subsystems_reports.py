"""Kiểm thử: phân hệ chỉ giữ chức năng đúng nhiệm vụ; đón trẻ đồng bộ điểm danh; quy trình gửi - duyệt báo cáo."""
from __future__ import annotations

from datetime import date

import pytest

from kindergarten.attendance.records import AttendanceStatus
from kindergarten.auth.user import Permission
from kindergarten.exceptions import KindergartenError, PermissionDeniedError, ValidationError
from kindergarten.reports.submissions import ReportStatus
from kindergarten.school_calendar import SchoolCalendar

school_day_only = pytest.mark.skipif(not SchoolCalendar().is_school_day(date.today()),
                                     reason="Đón trẻ / báo cáo cuối ngày chỉ có vào ngày học")


def login(system, username, password):
    system.auth.logout()
    return system.auth.login(username, password)


def screens_of(system, username, password) -> list[str]:
    """Các màn hình (GUI) mà phân hệ của tài khoản được mở."""
    from kindergarten.ui.gui.app import NAVIGATION
    login(system, username, password)
    return [cls.title for _group, classes in NAVIGATION for cls in classes
            if cls.permission is None or system.auth.has_permission(cls.permission)]


# ----------------------------------------------------------------------------- phân hệ con
def test_each_subsystem_only_has_its_own_screens(seeded):
    accountant = screens_of(seeded, "ketoan", "ketoan123")
    assert set(accountant) == {"Học phí", "Dịch vụ", "Nhân sự", "Lập & gửi báo cáo"}
    kitchen = screens_of(seeded, "nv.sau", "nhanvien123")
    assert set(kitchen) == {"Thực đơn", "Lập & gửi báo cáo"}
    guard = screens_of(seeded, "nv.hung", "nhanvien123")
    assert set(guard) == {"Đón - trả trẻ", "Lập & gửi báo cáo"}
    medic = screens_of(seeded, "nv.yen", "nhanvien123")
    assert set(medic) == {"Sức khỏe", "Lập & gửi báo cáo"}
    teacher = screens_of(seeded, "gv.nhung", "giaovien123")
    assert "Học phí" not in teacher and "Tổng quan" not in teacher and "Lớp học" not in teacher
    assert {"Vận hành hôm nay", "Đón - trả trẻ", "Điểm danh", "Ăn ngủ - sinh hoạt", "Trao đổi phụ huynh"} <= set(teacher)
    parent = screens_of(seeded, "ph.mai", "phuhuynh123")
    assert all(title in ("Hôm nay của con", "Nhật ký ăn ngủ", "Trao đổi với cô", "Đơn xin nghỉ", "Thực đơn tuần",
                         "Học phí & dịch vụ", "Sức khỏe & chuyên cần") for title in parent)
    admin = screens_of(seeded, "admin", "admin123")
    assert {"Báo cáo nhận được", "Lập báo cáo toàn trường"} <= set(admin) and "Lập & gửi báo cáo" not in admin


def test_business_layer_blocks_out_of_duty_actions(seeded):
    login(seeded, "ketoan", "ketoan123")
    with pytest.raises(PermissionDeniedError):
        seeded.menus.add_meal("Phở bò", 300, "bánh phở, thịt bò")
    login(seeded, "nv.sau", "nhanvien123")
    with pytest.raises(PermissionDeniedError):
        seeded.daily.check_in(seeded.children.find_one(full_name="Nguyễn Minh Khang").id, "Mẹ")
    seeded.menus.add_meal("Cháo cá hồi", 250, "gạo, cá hồi")   # bếp được quản lý món ăn


# ----------------------------------------------------------------------------- đón trẻ <-> điểm danh <-> trả trẻ
@school_day_only
def test_check_in_and_attendance_are_one_state(seeded):
    today = date.today()
    khang = seeded.children.find_one(full_name="Nguyễn Minh Khang")
    ngoc = seeded.children.find_one(full_name="Lê Bảo Ngọc")
    classroom = seeded.classes.get(khang.class_id)
    login(seeded, "gv.nhung", "giaovien123")
    # chưa đón -> vắng
    assert seeded.attendance.default_status(khang.id, today) == (AttendanceStatus.UNEXCUSED, "Chưa đến trường")
    # đón -> có mặt
    seeded.daily.check_in(khang.id, "Mẹ Trần Thị Mai")
    assert seeded.attendance.default_status(khang.id, today)[0] is AttendanceStatus.PRESENT
    # điểm danh 'có mặt' tại lớp cũng tính là đã đón
    seeded.attendance.mark(ngoc.id, today, "C")
    assert seeded.attendance.get_record(ngoc.id, today).checked_in and seeded.attendance.get_record(ngoc.id, today).arrived_at
    # chốt điểm danh: trẻ chưa đón -> vắng
    seeded.attendance.take_class_attendance(classroom.id, today)
    absent = [cid for cid in classroom.child_ids if not seeded.attendance.get_record(cid, today).is_present]
    assert absent and all(seeded.attendance.get_record(cid, today).status is not AttendanceStatus.PRESENT
                          for cid in absent)
    # trả trẻ: trẻ vắng không ở lớp -> không trả được; danh sách trả chỉ gồm trẻ có mặt
    with pytest.raises(KindergartenError):
        seeded.verify_pickup(absent[0], "Ai đó")
    assert {row["child"].id for row in seeded.daily.pickup_status(classroom.id)} == {khang.id, ngoc.id}
    # trẻ đến muộn sau khi đã chốt vắng vẫn đón được -> chuyển sang có mặt
    late = seeded.children.get(absent[0])
    seeded.daily.check_in(late.id, "Bố")
    assert seeded.attendance.get_record(late.id, today).is_present
    # hủy lượt đón nhầm -> trở về 'chưa đến'
    seeded.daily.undo_check_in(late.id)
    assert seeded.attendance.get_record(late.id, today) is None


# ----------------------------------------------------------------------------- báo cáo gửi BGH
@school_day_only
def test_report_submission_and_review_workflow(seeded):
    login(seeded, "gv.nhung", "giaovien123")
    assert {s["key"] for s in seeded.reports.available_types()} == {"end_of_day", "attendance", "pickup", "health"}
    other_class = seeded.classes.find_one(name="Lá Vành Khuyên")
    with pytest.raises(PermissionDeniedError):
        seeded.reports.create("end_of_day", class_id=other_class.id)
    with pytest.raises(PermissionDeniedError):
        seeded.reports.create("revenue")
    report = seeded.reports.create("end_of_day", note="Bé Khang ho nhẹ, đã báo phụ huynh")
    assert report.status is ReportStatus.DRAFT and "Mầm Sơn Ca" in report.period_text
    seeded.reports.submit(report.id)
    assert seeded.daily.step_progress()[5]["done"] == 1   # bước 6: 1 lớp đã gửi
    with pytest.raises(KindergartenError):
        seeded.reports.set_note(report.id, "sửa sau khi gửi")

    login(seeded, "ketoan", "ketoan123")
    assert {s["key"] for s in seeded.reports.available_types()} == {"revenue", "debt", "payroll"}
    finance = seeded.reports.create("debt", note="3 hộ quá hạn, đã nhắc")
    seeded.reports.submit(finance.id)
    with pytest.raises(PermissionDeniedError):
        seeded.reports.review(finance.id, True)

    login(seeded, "admin", "admin123")
    inbox = seeded.reports.inbox(ReportStatus.SENT)
    assert {r.id for r in inbox} == {report.id, finance.id}
    with pytest.raises(ValidationError):
        seeded.reports.review(report.id, False, "")      # yêu cầu bổ sung phải ghi rõ nội dung
    seeded.reports.review(report.id, False, "Bổ sung số trẻ chưa được đón")
    seeded.reports.review(finance.id, True, "Đồng ý")
    assert finance.status is ReportStatus.APPROVED
    with pytest.raises(PermissionDeniedError):
        seeded.reports.submit(report.id)                  # BGH không gửi báo cáo của người khác

    login(seeded, "gv.nhung", "giaovien123")
    assert report.status is ReportStatus.REVISE and report.review_comment
    seeded.reports.refresh_data(report.id)
    seeded.reports.set_note(report.id, "Đã bổ sung: còn 0 trẻ chưa đón")
    seeded.reports.submit(report.id)
    assert report.status is ReportStatus.SENT and [h["action"] for h in report.history][-1] == "Gửi lại"
    seeded.save()
    from kindergarten.system import KindergartenSystem
    again = KindergartenSystem(seeded.store.data_dir)
    again.load()
    assert again.reports.get(report.id).note.startswith("Đã bổ sung")

    login(seeded, "ph.mai", "phuhuynh123")
    assert seeded.reports.available_types() == []
    assert Permission.SUBMIT_REPORTS not in seeded.auth.current_user.permissions


@school_day_only
def test_admin_builds_school_report_from_received_reports(seeded):
    login(seeded, "gv.nhung", "giaovien123")
    class_report = seeded.reports.create("end_of_day", note="Lớp Mầm: 1 bé sốt nhẹ, đã báo phụ huynh")
    seeded.reports.submit(class_report.id)
    with pytest.raises(PermissionDeniedError):
        seeded.reports.create("school_day")          # giáo viên không lập báo cáo toàn trường
    login(seeded, "nv.sau", "nhanvien123")
    kitchen = seeded.reports.create("menu", note="Đã thay món tôm cho 2 bé dị ứng")
    seeded.reports.submit(kitchen.id)

    login(seeded, "admin", "admin123")
    seeded.reports.review(class_report.id, True)
    report, params = seeded.reports.build("school_day")
    data = report.data
    assert {row[0] for row in data.rows} >= {class_report.id}   # báo cáo cuối ngày gửi hôm nay
    assert any("1 bé sốt nhẹ" in str(row[-1]) for row in data.rows)   # kèm ghi chú của người gửi
    labels = [label for label, _value in data.summary]
    assert "Lớp đã gửi báo cáo cuối ngày" in labels and any(class_report.id in label for label in labels)
    # BGH chọn đúng các báo cáo nguồn muốn dùng
    school = seeded.reports.create("school_day", "Nhắc các lớp gửi báo cáo trước 17:30",
                                   report_ids=[class_report.id, kitchen.id])
    assert {row[0] for row in school.data["rows"]} == {class_report.id, kitchen.id}
    with pytest.raises(KindergartenError):
        seeded.reports.submit(school.id)              # báo cáo của BGH không 'gửi', mà hoàn tất lưu hồ sơ
    seeded.reports.finalize(school.id)
    assert school.status is ReportStatus.FINAL and school not in seeded.reports.inbox()
    assert seeded.reports.school_reports()[0].id == school.id
    month = seeded.reports.create("school_month", month=date.today().month, year=date.today().year)
    month_labels = [label for label, _v in month.data["summary"]]
    assert "Tỷ lệ chuyên cần toàn trường" in month_labels and "Quỹ lương tháng" in month_labels
