"""Kiểm thử hồi quy cho các lỗi trong 'Báo cáo rà soát hệ thống' (mục 8: L01-L27, P01, P03).

Mỗi test ghi rõ mã lỗi; test thất bại nghĩa là lỗi cũ đã quay lại.
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pytest

from kindergarten.auth.user import Role
from kindergarten.exceptions import (AuthenticationError, DataStoreError, InvalidAgeError, KindergartenError,
                                     ValidationError)
from kindergarten.health.records import ingredient_matches_allergen
from kindergarten.hr.employees import Teacher
from kindergarten.people.child import Child
from kindergarten.people.parent import Parent
from kindergarten.system import KindergartenSystem
from kindergarten.utils import add_months, format_rate, parse_money, previous_month


def last_weekday(before: date | None = None, offset: int = 0) -> date:
    """Ngày Thứ 2-6 gần nhất (không sau `before`), lùi thêm `offset` ngày làm việc."""
    day = before or date.today()
    found = -1
    while True:
        if day.weekday() < 5:
            found += 1
            if found == offset:
                return day
        day -= timedelta(days=1)


def last_saturday() -> date:
    today = date.today()
    return today - timedelta(days=(today.weekday() - 5) % 7)


@pytest.fixture
def klass(system):
    return system.classes.create_class("Lá 1", "Lá", 20)


# ----------------------------------------------------------------------------- L01
def test_l01_id_counter_survives_deleting_highest_id(system, make_child, tmp_path):
    a, b, c = make_child("Trẻ Một"), make_child("Trẻ Hai"), make_child("Trẻ Ba")
    assert c.id == "C003"
    system.children.remove(c.id)
    system.save()
    reloaded = KindergartenSystem(system.store.data_dir)
    reloaded.load()
    new = reloaded.children.add(Child("Trẻ Bốn", a.dob, "Nam"))
    assert new.id == "C004"   # không cấp lại mã C003 của hồ sơ đã xóa


# ----------------------------------------------------------------------------- L02
def test_l02_missing_users_file_is_an_error_not_an_empty_school(system, make_child):
    make_child()
    system.auth.ensure_default_admin()
    system.save()
    (system.store.data_dir / "users.json").unlink()
    with pytest.raises(DataStoreError):
        KindergartenSystem(system.store.data_dir).load()


def test_l02_seed_requires_confirmation_and_backs_up(system, make_child):
    import main
    make_child()
    system.auth.ensure_default_admin()
    system.save()
    assert main.prepare_reseed(system, ask=lambda _p: "n") is False
    assert system.store.list_backups() == []
    assert main.prepare_reseed(system, ask=lambda _p: "y") is True
    assert len(system.store.list_backups()) == 1


def test_l02_first_save_of_day_and_big_shrink_make_backups(system, make_child):
    for name in ("An", "Bình", "Chi", "Dũng", "Giang", "Hà"):
        make_child(f"Trẻ {name}")
    system.auth.ensure_default_admin()
    system.save()
    first = len(system.store.list_backups())
    for child in list(system.children):
        system.children.remove(child.id)
    system.save()
    assert len(system.store.list_backups()) > first   # dữ liệu giảm mạnh -> tự sao lưu trước khi ghi


# ----------------------------------------------------------------------------- L03
def test_l03_future_month_blocked_and_current_month_provisional(system, make_child, klass):
    child = make_child("Lê Minh Châu", 5)
    system.classes.enroll(child.id, klass.id)
    today = date.today()
    future = add_months(today, 1)
    with pytest.raises(KindergartenError):
        system.invoices.create_invoice(child.id, future.month, future.year)
    invoice = system.invoices.create_invoice(child.id, today.month, today.year)
    assert invoice.provisional and "tạm tính" in invoice.status_text()
    meals_before = invoice.total
    day = last_weekday()
    if day.month == today.month and day >= child.enrollment_date:
        system.attendance.mark(child.id, day, "Có mặt")
        system.invoices.recalculate(invoice.id)
        assert invoice.total == meals_before + system.settings.meal_rate_per_day


# ----------------------------------------------------------------------------- L04
def test_l04_weekend_holiday_and_pre_enrollment_rejected(system, make_child, klass):
    child = make_child("Phan Gia Huy", 5, enrollment_date=date.today() - timedelta(days=3))
    system.classes.enroll(child.id, klass.id)
    with pytest.raises(ValidationError):
        system.attendance.mark(child.id, last_saturday(), "Có mặt")
    with pytest.raises(ValidationError):
        system.attendance.mark(child.id, last_weekday(date.today() - timedelta(days=10)), "Có mặt")
    holiday = last_weekday()
    system.calendar.add_holiday(holiday, "Nghỉ bù")
    with pytest.raises(ValidationError):
        system.attendance.mark(child.id, holiday, "Có mặt")
    system.calendar.saturday_classes = True
    if last_saturday() >= child.enrollment_date:
        assert system.attendance.mark(child.id, last_saturday(), "Có mặt").is_present


# ----------------------------------------------------------------------------- L05
def test_l05_child_older_than_six_can_still_be_edited(system):
    old = system.children.add(Child("Nguyễn Hữu Tài", add_months(date.today(), -(6 * 12 + 9)), "Nam",
                                    check_age=False))
    system.children.update(old.id, nickname="Tèo", dob=old.dob)   # gửi lại đúng ngày sinh cũ: không lỗi
    assert old.nickname == "Tèo"


def test_l05_failed_update_rolls_back_everything(system, make_child):
    child = make_child("Đỗ Thu Trang", 4, gender="Nữ")
    with pytest.raises(KindergartenError):
        system.children.update(child.id, nickname="Bống", dob="01/01/2010")
    assert child.nickname == "" and child.full_name == "Đỗ Thu Trang"


# ----------------------------------------------------------------------------- L07
@pytest.mark.parametrize("allergen, ingredient, expected", [
    ("tôm", "tôm sú", True),
    ("hải sản", "tôm rim", True),
    ("tôm", "hải sản tổng hợp", True),       # món ghi tên nhóm, trẻ dị ứng một thành viên
    ("sữa bò", "bò kho", False),             # không còn khớp ngược tùy tiện
    ("đậu phộng", "lạc rang", True),
    ("cá", "ca cao", False),                 # không bỏ dấu khi dị ứng gõ có dấu
    ("tom", "tôm hấp", True),                # dị ứng gõ không dấu thì so không dấu
    ("trứng", "trứng cút", True),
    ("mè", "muối vừng", True),
])
def test_l07_allergen_matching(allergen, ingredient, expected):
    assert ingredient_matches_allergen(allergen, ingredient) is expected


# ----------------------------------------------------------------------------- L08
def test_l08_teacher_scope_never_guesses(system, make_teacher, klass):
    other = system.classes.create_class("Mầm 1", "Mầm", 20)
    with pytest.raises(ValidationError):
        system.create_user("gv.moi", "matkhau1", Role.TEACHER)
    user = system.auth.create_user("gv.cu", "matkhau1", Role.TEACHER)   # tài khoản cũ chưa liên kết
    assert system.classes_for(user) == [] and system.children_for(user) == []
    music = make_teacher("Trần Văn Nhạc", "0912000111", specialty="Âm nhạc")
    linked = system.create_user("gv.nhac", "matkhau1", Role.TEACHER, employee_id=music.id)
    system.timetable.add_slot(other.id, 1, "09:00", "09:30", "Âm nhạc", music.id)
    assert [c.id for c in system.classes_for(linked)] == [other.id]
    assert klass not in system.classes_for(linked)


# ----------------------------------------------------------------------------- L11
def test_l11_dates_and_ages_checked_on_update(system, make_teacher, make_child, klass):
    with pytest.raises(KindergartenError):
        Teacher("Lê Thị Trẻ", "2010-01-01", "0912000222", hire_date="2024-01-01")
    teacher = make_teacher("Lê Thị Hoa", "0912000333")
    with pytest.raises(KindergartenError):
        system.employees.update(teacher.id, hire_date="2000-01-01")   # mới 9 tuổi
    child = make_child("Vũ An Nhiên", 5, gender="Nữ")
    system.classes.enroll(child.id, klass.id)
    with pytest.raises(InvalidAgeError):
        system.classes.update(klass.id, age_group="Mầm")
    with pytest.raises(KindergartenError):
        system.children.update(child.id, enrollment_date=child.dob - timedelta(days=1))


# ----------------------------------------------------------------------------- L12
def test_l12_half_siblings_share_household_for_discount_and_debt(system, make_child, make_parent, klass):
    a, b = make_child("Ngô Gia Bảo", 5), make_child("Trịnh Gia Hân", 5, gender="Nữ")
    for child in (a, b):
        system.classes.enroll(child.id, klass.id)
    mother = make_parent("Ngô Thị Mai", "0906111000", "Mẹ")
    system.parents.link(mother.id, a.id)
    system.parents.link(mother.id, b.id)
    assert system.children.siblings_of(a.id, active_only=True) == [b]
    month, year = previous_month(date.today().month, date.today().year)
    for child in (a, b):
        system.invoices.create_invoice(child.id, month, year)
    debtors = system.invoices.debtors()
    assert len(debtors) == 1 and sorted(debtors[0]["children"]) == sorted([a.full_name, b.full_name])


# ----------------------------------------------------------------------------- L14
def test_l14_withdraw_keeps_history_and_readmit(system, make_child, klass):
    child = make_child("Mai Anh Thư", 5, gender="Nữ")
    system.classes.enroll(child.id, klass.id)
    system.withdraw_child(child.id, "Đã nghỉ")
    assert not child.is_active and child.class_id is None and klass.size == 0
    assert child in system.children.find_inactive() and child not in system.children.all_sorted()
    system.classes.readmit(child.id)
    assert child.is_active


# ----------------------------------------------------------------------------- L15
def test_l15_closed_payroll_does_not_change(system, make_teacher):
    teacher = make_teacher("Phạm Thu Hà", "0912000444", hire_date="2015-01-01")
    month, year = previous_month(date.today().month, date.today().year)
    rows = system.employees.close_payroll(month, year)
    before = system.employees.total_payroll(month, year)
    system.employees.update(teacher.id, salary_coefficient=4.5)
    assert system.employees.total_payroll(month, year) == before == rows[0]["salary"]
    late = make_teacher("Người Vào Sau", "0912000555", hire_date=date.today())
    if (year, month) < (date.today().year, date.today().month):
        assert late.id not in [r["employee_id"] for r in system.employees.payroll(month, year)]
    system.employees.reopen_payroll(month, year)
    assert system.employees.total_payroll(month, year) > before


# ----------------------------------------------------------------------------- L16
def test_l16_void_payment_keeps_trace(system, make_child, klass):
    child = make_child("Đinh Bảo Long", 5)
    system.classes.enroll(child.id, klass.id)
    month, year = previous_month(date.today().month, date.today().year)
    invoice = system.invoices.create_invoice(child.id, month, year, issue_date=date.today())
    payment = system.record_payment(invoice.id, invoice.total, pay_date=date.today())
    assert invoice.balance == 0
    with pytest.raises(KindergartenError):
        system.invoices.remove(invoice.id)
    system.void_payment(invoice.id, payment.id, "Ghi nhầm hóa đơn")
    assert invoice.balance == invoice.total and payment.voided and payment.void_reason == "Ghi nhầm hóa đơn"
    assert payment in invoice.payments
    with pytest.raises(KindergartenError, match="lịch sử phiếu thu"):
        system.invoices.remove(invoice.id)


# ----------------------------------------------------------------------------- L17
def test_l17_rates_and_services(system):
    assert format_rate(0.125) == "12,5"
    with pytest.raises(KindergartenError):
        system.settings.update(extra_services={"Năng khiếu vẽ": 100_000, "năng  khiếu VẼ": 120_000})
    system.update_fee_settings(second_child_rate=0.125)
    assert system.settings.second_child_rate == 0.125


# ----------------------------------------------------------------------------- L18
@pytest.mark.parametrize("text", ["2.5", "2500.50", "1,5", "12.34.5"])
def test_l18_ambiguous_money_rejected(text):
    with pytest.raises(ValidationError):
        parse_money(text)


@pytest.mark.parametrize("text, value", [("2.500.000", 2_500_000), ("2,500,000", 2_500_000), ("2500000", 2_500_000),
                                         ("2,5tr", 2_500_000), ("300k", 300_000), ("1.5 triệu", 1_500_000)])
def test_l18_money_formats_accepted(text, value):
    assert parse_money(text) == value


# ----------------------------------------------------------------------------- L19
def test_l19_dashboard_on_non_school_day(system, klass):
    stats = system.dashboard(today=last_saturday()).collect()
    assert not stats["is_school_day"] and stats["classes_not_taken"] == [] and "cuối tuần" in stats["day_note"]


# ----------------------------------------------------------------------------- L22
def test_l22_invalid_add_does_not_consume_id(system, make_parent):
    first = make_parent("Hoàng Văn Nam", "0905999001", "Bố")
    with pytest.raises(KindergartenError):
        make_parent("Hoàng Văn Bắc", "0905999002", "Bố", child_ids=["C999"])
    second = make_parent("Hoàng Văn Đông", "0905999003", "Bố")
    assert int(second.id[2:]) == int(first.id[2:]) + 1


# ----------------------------------------------------------------------------- L24
def test_l24_lockout_and_forced_password_change(system):
    system.auth.ensure_default_admin()
    admin = system.auth.find_by_username("admin")
    assert admin.must_change_password
    for _ in range(system.auth.MAX_FAILURES):
        with pytest.raises(AuthenticationError):
            system.auth.login("admin", "sai")
    with pytest.raises(AuthenticationError, match="tạm khóa"):
        system.auth.login("admin", "admin123")
    system.auth._failures.clear()
    system.auth.login("admin", "admin123")
    system.auth.change_password("admin123", "matkhaumoi")
    assert not admin.must_change_password and not system.auth.uses_password("admin", "admin123")


# ----------------------------------------------------------------------------- L26
def test_l26_cancel_leave_request_reverts_days(system, make_child, klass):
    child = make_child("Lý Gia Phong", 5)
    system.classes.enroll(child.id, klass.id)
    day = last_weekday(offset=1)
    system.attendance.mark(child.id, day, "Nghỉ không phép", "Không báo")
    request = system.attendance.record_leave_request(child.id, day, day, "Ốm")
    assert system.attendance.get_record(child.id, day).status.value == "Nghỉ có phép"
    system.attendance.cancel_leave_request(request.id)
    assert system.attendance.get_record(child.id, day).status.value == "Nghỉ không phép"


# ----------------------------------------------------------------------------- L27
def test_l27_parent_gender_must_match_relationship():
    with pytest.raises(ValidationError):
        Parent("Nguyễn Văn Hùng", "1985-01-01", "0905123123", gender="Nam", relationship="Mẹ")


# ----------------------------------------------------------------------------- P01
def test_p01_second_save_writes_nothing(system, make_child):
    make_child()
    system.auth.ensure_default_admin()
    system.save()
    before = {p.name: p.stat().st_mtime_ns for p in system.store.data_dir.glob("*.json") if p.name != "meta.json"}
    time.sleep(0.05)
    system.save()
    after = {p.name: p.stat().st_mtime_ns for p in system.store.data_dir.glob("*.json") if p.name != "meta.json"}
    assert before == after
    data = json.loads((system.store.data_dir / "meta.json").read_text(encoding="utf-8"))
    assert data["counters"]["C"] >= 1


# ----------------------------------------------------------------------------- P03
def test_p03_monthly_attendance_and_invoices_are_fast(seeded):
    month, year = previous_month(date.today().month, date.today().year)
    start = time.perf_counter()
    for _ in range(50):
        seeded.attendance.present_days_map(month, year)
        seeded.attendance.monthly_stats(month, year)
    assert time.perf_counter() - start < 5
