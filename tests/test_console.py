"""Kiểm thử MainMenu console (T08) chạy từ đầu đến cuối bằng dữ liệu nhập giả lập (T32)."""
from datetime import date

import pytest

from kindergarten.attendance.records import AttendanceStatus
from kindergarten.ui.console.console_io import ConsoleIO
from kindergarten.ui.console.main_menu import MainMenu
from seed_data import DEMO_ACCOUNTS


def run_console(system, inputs, **kwargs):
    output: list[str] = []
    answers = iter(inputs)
    io = ConsoleIO(input_func=lambda prompt: next(answers), output_func=output.append, use_color=False)
    MainMenu(system, io, demo_accounts=DEMO_ACCOUNTS, **kwargs).run()
    return "\n".join(output)


def test_admin_login_dashboard_and_exit(seeded):
    out = run_console(seeded, ["admin", "admin123", "2", "", "0", "k"])   # 1 = Vận hành, 2 = Dashboard
    assert "Xin chào" in out and "TỔNG QUAN NGÀY" in out and "Học phí & công nợ" in out
    assert "Tạm biệt" in out


def test_teacher_menu_only_shows_allowed_functions(seeded):
    out = run_console(seeded, ["gv.nhung", "giaovien123", "0", "k"])
    assert "Điểm danh" in out and "lớp chủ nhiệm: Mầm Sơn Ca" in out
    assert "Học phí & công nợ" not in out and "Nhân sự & bảng lương" not in out


def test_wrong_password_loop_and_lockout(seeded):
    """U10/L24: sai mật khẩu không thoát chương trình; đếm lần thử theo tài khoản, quá 5 lần thì khóa tạm."""
    out = run_console(seeded, ["admin", "x", "admin", "y", "admin", "admin123", "0", "k"])
    assert out.count("Sai tên đăng nhập hoặc mật khẩu") == 2 and "còn 3 lần thử" in out and "Xin chào" in out
    out = run_console(seeded, ["ketoan", "1", "ketoan", "2", "ketoan", "3", "ketoan", "4", "ketoan", "5",
                               "ketoan", "ketoan123", ""])
    assert "tạm khóa" in out and "Xin chào" not in out


def test_teacher_takes_attendance_via_console(seeded):
    if not seeded.calendar.is_school_day(date.today()):
        pytest.skip("Hôm nay không phải ngày học (L04: không cho điểm danh ngày nghỉ)")
    # Menu giáo viên: 1 Vận hành, 2 Trẻ, 3 Sức khỏe, 4 Lớp học, 5 Điểm danh... (không có Dashboard toàn trường)
    inputs = ["gv.nhung", "giaovien123", "5", "1", "1", "", "2", "3", "Không báo", "", "", "0", "0", "k"]
    out = run_console(seeded, inputs)
    assert "Đã lưu điểm danh lớp Mầm Sơn Ca" in out
    classroom = seeded.classes.find_one(name="Mầm Sơn Ca")
    kids = seeded.classes.class_list(classroom.id)
    record = seeded.attendance.get_record(kids[1].id, date.today())
    assert record.status is AttendanceStatus.UNEXCUSED and record.note == "Không báo"
    assert all(seeded.attendance.get_record(k.id, date.today()) for k in kids)


def test_first_run_creates_default_admin_and_forces_password_change(system):
    """L24: tài khoản admin mặc định phải đổi mật khẩu trước khi vào menu."""
    out = run_console(system, ["admin", "admin123", "matkhau1", "khac", "matkhau1", "matkhau1", "0", ""])
    assert "admin / admin123" in out and "Xin chào" in out
    assert "Hai lần nhập không khớp" in out and "Đã đổi mật khẩu" in out
    assert system.store.has_data()
    assert system.auth.uses_password("admin", "matkhau1") and not system.auth.uses_password("admin", "admin123")
    out = run_console(system, ["admin", "admin123", "", ])
    assert "admin / admin123" not in out   # không còn gợi ý mật khẩu mẫu đã đổi
