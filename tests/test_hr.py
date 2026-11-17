"""Kiểm thử Teacher/Staff tính lương đa hình (T14) và EmployeeManager (T15)."""
from datetime import date, timedelta

import pytest

from kindergarten.exceptions import DuplicateIdError, KindergartenError, ValidationError
from kindergarten.hr.employees import BASE_SALARY_UNIT, Staff, Teacher


def test_teacher_salary(system):
    teacher = system.employees.add(Teacher("Nguyễn Thị Hồng", "1990-03-12", "0912000001", salary_coefficient=2.10,
                                           hire_date=date.today() - timedelta(days=365)))
    basic = round(BASE_SALARY_UNIT * 2.10)
    assert teacher.calculate_salary() == basic + round(basic * 0.35)  # chưa đủ 5 năm, chưa chủ nhiệm
    system.classes.create_class("Mầm 1", "Mầm", 10, teacher_id=teacher.id)
    assert teacher.calculate_salary() == basic + round(basic * 0.35) + Teacher.HOMEROOM_ALLOWANCE
    senior = Teacher("Lê Thị Mai", "1980-01-01", "0912000002", salary_coefficient=3.0, hire_date="2010-01-01")
    basic3 = round(BASE_SALARY_UNIT * 3.0)
    years = senior.years_of_service()
    assert senior.calculate_salary() == basic3 + round(basic3 * 0.35) + round(basic3 * years / 100)


def test_staff_salary_with_overtime():
    staff = Staff("Bùi Thị Sáu", "1980-06-11", "0983000001", position="Cấp dưỡng", base_salary=6_240_000,
                  allowance=500_000)
    assert staff.calculate_salary(10, 2026) == 6_740_000
    staff.set_overtime(10, 2026, 10)
    # 6.240.000 / 208 giờ = 30.000 đ/giờ × 150% × 10 giờ = 450.000 đ
    assert staff.calculate_salary(10, 2026) == 6_740_000 + 450_000
    assert staff.calculate_salary(9, 2026) == 6_740_000


def test_payroll_uses_each_class_formula(system):
    teacher = system.employees.add(Teacher("Trần Thu Hà", "1993-09-03", "0912000003"))
    staff = system.employees.add(Staff("Đỗ Văn Hùng", "1975-02-20", "0983000002", position="Bảo vệ",
                                       base_salary=5_500_000, allowance=300_000))
    rows = system.employees.payroll(11, 2026)
    assert [r["type"] for r in rows] == ["Giáo viên", "Nhân viên"]
    assert system.employees.total_payroll(11, 2026) == (teacher.calculate_salary(11, 2026)
                                                        + staff.calculate_salary(11, 2026))
    assert "BẢNG LƯƠNG THÁNG 11/2026" in system.employees.payroll_text(11, 2026)


def test_employee_search_and_rules(system):
    music = system.employees.add(Teacher("Phạm Minh Tuấn", "1994-06-18", "0912000004", specialty="Âm nhạc"))
    guard = system.employees.add(Staff("Đỗ Văn Hùng", "1975-02-20", "0983000005", position="Bảo vệ"))
    assert system.employees.search_by_name("tuan") == [music]
    assert system.employees.find_by_position("âm nhạc") == [music]
    assert system.employees.teachers() == [music] and system.employees.staff_members() == [guard]
    with pytest.raises(DuplicateIdError):
        system.employees.add(Staff("Người Trùng Số", "1980-01-01", "0912000004"))
    with pytest.raises(ValidationError):
        system.employees.set_overtime(music.id, 11, 2026, 5)  # giáo viên không tính giờ làm thêm
    system.classes.create_class("Chồi 1", "Chồi", 10, teacher_id=music.id)
    with pytest.raises(KindergartenError):
        system.employees.remove(music.id)  # đang chủ nhiệm lớp
