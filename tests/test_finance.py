"""Kiểm thử Fee (T21), Discount (T22), Invoice/Payment (T23), InvoiceManager (T24)."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from kindergarten.exceptions import DuplicateIdError, KindergartenError, PaymentError
from kindergarten.finance.discount import Discount, DiscountPolicy
from kindergarten.finance.fees import ExtraFee, Fee, MealFee, MonthlyFee
from kindergarten.finance.invoice import Invoice, InvoiceStatus
from kindergarten.finance.settings import FeeSettings
from kindergarten.utils import previous_month, school_days


def test_fee_polymorphism():
    fees = [MonthlyFee(2_500_000), MealFee(20, 35_000), ExtraFee("Tiếng Anh", 400_000)]
    assert [f.calculate() for f in fees] == [2_500_000, 700_000, 400_000]
    assert [Fee.from_dict(f.to_dict()).calculate() for f in fees] == [2_500_000, 700_000, 400_000]
    assert fees[0].discountable and not fees[1].discountable
    assert "20 ngày" in fees[1].describe()


def test_discount_policy(make_child):
    policy = DiscountPolicy(FeeSettings(second_child_rate=0.2, poor_household_rate=0.5))
    older = make_child("Vũ Gia Bảo", 5)
    younger = make_child("Vũ Ngọc Hân", 3, gender="Nữ")
    assert policy.applicable_discounts(older, [younger]) == []
    assert [d.name for d in policy.applicable_discounts(younger, [older])] == ["Con thứ hai"]
    younger.is_poor_household = True
    best = policy.best_discount(younger, [older], 2_500_000)
    assert best.name == "Hộ nghèo" and best.calculate(2_500_000) == 1_250_000  # lấy mức giảm cao nhất
    assert Discount("Giảm cố định", amount=3_000_000).calculate(2_500_000) == 2_500_000


def test_invoice_payment_flow():
    invoice = Invoice("C001", 10, 2026, [MonthlyFee(2_000_000), MealFee(20, 30_000)],
                      Discount("Con thứ hai", rate=0.2), child_name="Bé An",
                      issue_date=date.today() - timedelta(days=20))
    assert (invoice.subtotal, invoice.discount_amount, invoice.total) == (2_600_000, 400_000, 2_200_000)
    assert invoice.status is InvoiceStatus.UNPAID and invoice.is_overdue()
    invoice.add_payment(1_000_000)
    assert invoice.status is InvoiceStatus.PARTIAL and invoice.balance == 1_200_000
    with pytest.raises(PaymentError):
        invoice.add_payment(2_000_000)  # vượt quá số còn nợ
    invoice.add_payment(1_200_000, method="Chuyển khoản")
    assert invoice.status is InvoiceStatus.PAID and invoice.balance == 0 and not invoice.is_overdue()
    with pytest.raises(PaymentError):
        invoice.add_payment(1_000)
    clone = Invoice.from_dict(invoice.to_dict())
    assert clone.total == invoice.total and clone.status is InvoiceStatus.PAID and len(clone.payments) == 2


@pytest.fixture
def school(system, make_child, make_parent):
    """Hai anh em ruột + một trẻ hộ nghèo, đã điểm danh 4 ngày của tháng trước."""
    senior = system.classes.create_class("Lá 1", "Lá", 10)
    junior = system.classes.create_class("Mầm 1", "Mầm", 10)
    older = make_child("Đỗ Ngọc Diệp", 5, gender="Nữ", extra_services=["Tiếng Anh"])
    younger = make_child("Đỗ Hoàng Nam", 3)
    poor = make_child("Trần Gia Huy", 5, is_poor_household=True)
    father = make_parent("Đỗ Quốc Việt", "0905000111", "Bố")
    for kid in (older, younger):
        system.parents.link(father.id, kid.id)
    for kid, room in ((older, senior), (younger, junior), (poor, senior)):
        system.classes.enroll(kid.id, room.id)
    month, year = previous_month(date.today().month, date.today().year)
    days = school_days(month, year)[:4]
    for day in days:
        for room in (senior, junior):   # trẻ đến lớp -> có mặt
            system.attendance.take_class_attendance(room.id, day, {cid: "C" for cid in room.child_ids})
    system.attendance.mark(older.id, days[0], "P")
    return SimpleNamespace(older=older, younger=younger, poor=poor, father=father, month=month, year=year)


def test_generate_monthly_invoices(system, school):
    created, skipped = system.invoices.generate_monthly_invoices(school.month, school.year)
    assert len(created) == 3 and skipped == []
    by_child = {i.child_id: i for i in created}
    older_invoice = by_child[school.older.id]
    assert older_invoice.meal_amount == 3 * system.settings.meal_rate_per_day  # nghỉ 1 ngày -> 3 ngày ăn
    assert older_invoice.extra_amount == system.settings.extra_services["Tiếng Anh"]
    assert older_invoice.discount is None
    assert by_child[school.younger.id].discount.name == "Con thứ hai"
    assert by_child[school.poor.id].discount.name == "Hộ nghèo"
    again, skipped = system.invoices.generate_monthly_invoices(school.month, school.year)
    assert again == [] and len(skipped) == 3
    with pytest.raises(DuplicateIdError):
        system.invoices.create_invoice(school.older.id, school.month, school.year)


def test_debt_tracking(system, school):
    created, _ = system.invoices.generate_monthly_invoices(school.month, school.year)
    by_child = {i.child_id: i for i in created}
    poor_invoice, older_invoice = by_child[school.poor.id], by_child[school.older.id]
    system.invoices.record_payment(poor_invoice.id, poor_invoice.total)
    system.invoices.record_payment(older_invoice.id, 500_000)
    debtors = system.invoices.debtors()
    assert len(debtors) == 1  # hai anh em gộp thành một hộ; hộ còn lại đã trả đủ
    family = debtors[0]
    assert family["parent_names"] == "Đỗ Quốc Việt" and len(family["children"]) == 2
    expected = older_invoice.balance + by_child[school.younger.id].balance
    assert family["debt"] == expected == system.invoices.debt_of_parent(school.father.id)
    found = {i.id for i in system.invoices.debt_lookup("0905000111")}
    assert found == {older_invoice.id, by_child[school.younger.id].id}
    summary = system.invoices.revenue_summary(school.month, school.year)
    assert summary["collected"] == poor_invoice.total + 500_000
    with pytest.raises(KindergartenError):
        system.children.remove(school.older.id)  # còn nợ học phí
    with pytest.raises(KindergartenError, match="lịch sử học phí"):
        system.children.remove(school.poor.id)  # đã trả đủ
    with pytest.raises(KindergartenError):
        system.invoices.remove(older_invoice.id)  # hóa đơn đã có thanh toán
