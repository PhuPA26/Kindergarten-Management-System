"""Màn hình console: sức khỏe - cân đo tăng trưởng, dị ứng (T12-T13)."""
from __future__ import annotations

from datetime import date

from ....auth.user import Permission
from ....health.records import AllergySeverity
from ....utils import format_date, format_number, validate_not_future
from ..menu import Menu
from .base import Screen

class HealthScreen(Screen):
    title = "Sức khỏe - dị ứng"

    def build_menu(self) -> Menu:
        P = Permission.MANAGE_HEALTH
        return (self.new_menu()
                .add("Nhập kết quả cân đo", self.add_record, P)
                .add("Xem quá trình tăng trưởng của trẻ", self.growth, P)
                .add("Danh sách trẻ cần chú ý dinh dưỡng", self.attention, P)
                .add("Thêm thông tin dị ứng", self.add_allergy, P)
                .add("Danh sách trẻ bị dị ứng", self.allergy_list, P)
                .add("Xóa số đo nhập nhầm", self.remove_record, P)
                .add("Xóa thông tin dị ứng", self.remove_allergy, P))

    def remove_record(self) -> None:
        """U01: sửa sai kết quả cân đo."""
        child = self.select_child()
        record = self._require(self.io.choose(
            self.system.health.records_of(child.id),
            lambda r: f"{r.id} - {format_date(r.measure_date)}: {r.height_cm} cm, {r.weight_kg} kg",
            "Chọn lần đo cần xóa", "Trẻ chưa có số đo nào."))
        if self.confirm(f"Xóa số đo ngày {format_date(record.measure_date)} của {child.full_name}?"):
            self.system.health.remove_health_record(record.id)
            self.io.success("Đã xóa số đo.")

    def _visible_ids(self) -> set[str]:
        return {c.id for c in self.visible_children()}

    def _child_name(self, child_id: str) -> str:
        child = self.system.children.get_or_none(child_id)
        return child.full_name if child else child_id

    # ------------------------------------------------------------------ tăng trưởng
    def add_record(self) -> None:
        io = self.io
        child = self.select_child()
        measured = io.ask_date("Ngày đo", date.today(), check=lambda d: validate_not_future(d, "Ngày đo"))
        height = io.ask_float("Chiều cao (cm)", min_value=40, max_value=150)
        weight = io.ask_float("Cân nặng (kg)", min_value=3, max_value=60)
        note = io.ask_text("Ghi chú", required=False) or ""
        record = self.system.health.add_health_record(child.id, measured, height, weight, note)
        io.success(f"Đã lưu số đo của {child.full_name}: BMI {record.bmi_text} -> {record.assess().value}.")

    def growth(self) -> None:
        child = self.select_child()
        rows = []
        for item in self.system.health.growth_history(child.id):
            record = item["record"]
            change_h = "" if item["height_change"] is None else f"{item['height_change']:+.1f}"
            change_w = "" if item["weight_change"] is None else f"{item['weight_change']:+.1f}"
            rows.append([format_date(record.measure_date), record.age_months, record.height_cm, record.weight_kg,
                         format_number(item["bmi"]), item["status"].value, change_h, change_w])
        self.io.table(["Ngày đo", "Tháng tuổi", "Cao (cm)", "Nặng (kg)", "BMI", "Đánh giá", "+Cao", "+Nặng"],
                      rows, title=f"QUÁ TRÌNH TĂNG TRƯỞNG - {child.full_name.upper()}")

    def attention(self) -> None:
        allowed = self._visible_ids()
        rows = []
        for child, record in self.system.health.children_needing_attention():
            if child.id in allowed:
                rows.append([child.id, child.full_name, self.class_name(child.class_id),
                             format_date(record.measure_date), record.height_cm, record.weight_kg,
                             record.bmi_text, record.assess().value])
        self.io.table(["Mã", "Họ tên", "Lớp", "Ngày đo", "Cao", "Nặng", "BMI", "Đánh giá"], rows,
                      title="TRẺ CẦN CHÚ Ý DINH DƯỠNG (theo lần cân đo gần nhất)")

    # ------------------------------------------------------------------ dị ứng
    def add_allergy(self) -> None:
        io = self.io
        child = self.select_child()
        allergen = io.ask_text("Chất gây dị ứng (VD: tôm, sữa bò, đậu phộng, hải sản)")
        severity = io.ask_choice("Mức độ", [(s, s.value) for s in AllergySeverity], default=AllergySeverity.MILD)
        reaction = io.ask_text("Biểu hiện khi dị ứng", required=False) or ""
        self.system.health.add_allergy(child.id, allergen, severity, reaction)
        io.success(f"Đã ghi nhận {child.full_name} dị ứng '{allergen}'. Thực đơn sẽ tự cảnh báo món có chất này.")

    def remove_allergy(self) -> None:
        allowed = self._visible_ids()
        items = [a for a in self.system.health.allergies.sort("child_id") if a.child_id in allowed]
        allergy = self._require(self.io.choose(
            items, lambda a: f"{a.id} - {self._child_name(a.child_id)}: {a.allergen} ({a.severity.value})",
            "Chọn thông tin dị ứng", "Chưa có thông tin dị ứng nào."))
        if self.confirm(f"Xóa dị ứng '{allergy.allergen}' của {self._child_name(allergy.child_id)}?"):
            self.system.health.remove_allergy(allergy.id)
            self.io.success("Đã xóa.")

    def allergy_list(self) -> None:
        allowed = self._visible_ids()
        rows = []
        for child, allergies in self.system.health.children_with_allergies():
            if child.id not in allowed:
                continue
            for allergy in allergies:
                rows.append([child.id, child.full_name, self.class_name(child.class_id), allergy.allergen,
                             allergy.severity.value, allergy.reaction or "-"])
        self.io.table(["Mã trẻ", "Họ tên", "Lớp", "Chất gây dị ứng", "Mức độ", "Biểu hiện"], rows,
                      title="DANH SÁCH TRẺ BỊ DỊ ỨNG")
