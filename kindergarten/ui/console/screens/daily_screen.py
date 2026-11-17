"""Màn hình console: vận hành hằng ngày theo 6 bước (đón trẻ, điểm danh, ăn ngủ, trao đổi phụ huynh,
trả trẻ, báo cáo cuối ngày)."""
from __future__ import annotations

from datetime import date

from ....auth.user import Permission
from ....daily.records import MEAL_LEVELS, MEALS, MOODS, NAP_LEVELS, MessageKind
from ....exceptions import KindergartenError
from ....reports.reports import EndOfDayReport
from ....utils import format_date, weekday_name
from ..menu import Menu
from .base import Screen

P = Permission


def _hhmm(stamp: str) -> str:
    return stamp[11:16] if stamp and len(stamp) >= 16 else ""


class DailyScreen(Screen):
    title = "Vận hành hằng ngày"

    def build_menu(self) -> Menu:
        return (self.new_menu()
                .add("Tiến độ 6 bước hôm nay", self.progress, P.VIEW_OPERATIONS)
                .add("① Đón trẻ đầu ngày (07:00-08:00)", self.check_in, P.CHECK_IN_OUT)
                .add("③ Cập nhật ăn - ngủ - sinh hoạt của trẻ", self.update_log, P.DAILY_LOG)
                .add("③ Điền nhanh ăn ngủ mặc định cho cả lớp", self.fill_defaults, P.DAILY_LOG)
                .add("③ Gửi nhật ký trong ngày cho phụ huynh", self.send_logs, P.DAILY_LOG)
                .add("④ Hộp thư phụ huynh: xem, trả lời, đã cho uống thuốc, duyệt xin nghỉ", self.inbox,
                     P.PARENT_CONTACT)
                .add("④ Nhắn riêng phụ huynh / gửi thông báo cho lớp", self.send_to_parents, P.PARENT_CONTACT)
                .add("⑤ Trả trẻ cuối ngày (16:00-17:00)", self.pick_up, P.CHECK_IN_OUT)
                .add("⑥ Báo cáo cuối ngày: lập, ghi chú, gửi BGH", self.end_of_day, P.DAILY_LOG)
                .add("⑥ Lớp nào đã gửi báo cáo cuối ngày", self.end_of_day_status, P.REVIEW_REPORTS))

    def _school_today(self) -> date:
        today = date.today()
        if not self.system.calendar.is_school_day(today):
            raise KindergartenError(self.system.calendar.reason_not_school_day(today) + " Không có vận hành lớp.")
        return today

    # ------------------------------------------------------------------ tiến độ
    def progress(self) -> None:
        today = date.today()
        rows = [[item["step"].number, item["step"].title, item["step"].time_text,
                 "✔ Hoàn thành" if item["complete"] else item["phase"], item["text"]]
                for item in self.system.daily.step_progress(self.scope_class_ids())]
        self.io.table(["Bước", "Công việc", "Thời gian", "Trạng thái", "Tiến độ"], rows,
                      title=f"VẬN HÀNH {weekday_name(today).upper()} {format_date(today)}")

    # ------------------------------------------------------------------ bước 1, 5
    def _people(self, child_id: str) -> list[tuple[str, str]]:
        return [(p[0], f"{p[0]} ({p[1]}) - {p[2]}") for p in self.system.authorized_pickups(child_id)] + \
            [("__other__", "Người khác (tự nhập tên)")]

    def check_in(self) -> None:
        io, s = self.io, self.system
        today = self._school_today()
        classroom = self.select_class()
        while True:
            waiting = [row["child"] for row in s.daily.class_day(classroom.id, today)
                       if not (row["record"] and (row["record"].checked_in or not row["record"].is_present))]
            if not waiting:
                io.success("Tất cả trẻ của lớp đã được đón / có lý do vắng.")
                return
            child = io.choose(waiting, self.child_label, f"Trẻ vừa đến (còn {len(waiting)} trẻ chưa đến, Enter = xong)")
            if child is None:
                return
            person = io.ask_choice("Người đưa trẻ", self._people(child.id))
            if person == "__other__":
                person = io.ask_text("Họ tên người đưa")
            note = io.ask_text("Lưu ý sức khỏe khi đón (Enter nếu không có)", required=False) or ""
            record = s.daily.check_in(child.id, person, note)
            self.app._save_quietly()
            io.success(f"Đã đón {child.full_name} lúc {_hhmm(record.arrived_at)}.")

    def pick_up(self) -> None:
        io, s = self.io, self.system
        today = self._school_today()
        classroom = self.select_class()
        rows = [row for row in s.daily.pickup_status(classroom.id, today) if not row["record"].picked_up]
        child = self._require(io.choose([row["child"] for row in rows], self.child_label,
                                        "Trẻ được đón về", "Lớp không còn trẻ nào chờ đón."))
        name = io.ask_choice(f"Người đến đón {child.full_name}", self._people(child.id))
        if name == "__other__":
            name = io.ask_text("Họ tên người đến đón (để ghi nhật ký)")
        result = s.verify_pickup(child.id, name)
        io.success(f"Hợp lệ - đã giao {child.full_name} cho {result}.")

    # ------------------------------------------------------------------ bước 3
    def _ask_level(self, prompt: str, options: tuple[str, ...], default: str) -> str:
        return self.io.ask_choice(prompt, [(o, o) for o in options], default)

    def update_log(self) -> None:
        io, s = self.io, self.system
        today = self._school_today()
        classroom = self.select_class()
        present = [row for row in s.daily.class_day(classroom.id, today)
                   if row["record"] is not None and row["record"].is_present]
        if not present:
            raise KindergartenError("Lớp chưa có trẻ nào có mặt hôm nay (hãy đón trẻ / điểm danh trước).")
        child = self._require(io.choose([r["child"] for r in present],
                                        lambda c: self.child_label(c) + (" ✔" if s.daily.log_of(c.id, today) else ""),
                                        "Chọn trẻ cần cập nhật (✔ = đã có nhật ký)"))
        log = s.daily.log_of(child.id, today)
        meals = {meal: self._ask_level(meal, MEAL_LEVELS, (log.meals if log else {}).get(meal, "Ăn hết"))
                 for meal in MEALS}
        nap = self._ask_level("Giấc ngủ trưa", NAP_LEVELS, log.nap if log and log.nap else "Ngủ ngon")
        minutes = io.ask_int("Ngủ bao lâu (phút)", log.nap_minutes if log else 120, 0, 240)
        mood = self._ask_level("Tâm trạng", MOODS, log.mood if log and log.mood else "Vui vẻ")
        activities = io.ask_text("Hoạt động trong ngày", log.activities if log else None, required=False) or ""
        health = io.ask_text("Sức khỏe (sốt, ho...)", log.health_note if log else None, required=False) or ""
        note = io.ask_text("Lời nhắn của cô gửi phụ huynh", log.teacher_note if log else None, required=False) or ""
        s.daily.save_log(child.id, today, meals=meals, nap=nap, nap_minutes=minutes, mood=mood, activities=activities,
                         health_note=health, teacher_note=note)
        io.success(f"Đã cập nhật nhật ký của {child.full_name}. Nhớ 'Gửi nhật ký cho phụ huynh' khi xong cả lớp.")

    def fill_defaults(self) -> None:
        today = self._school_today()
        classroom = self.select_class()
        count = self.system.daily.fill_class_defaults(classroom.id, today)
        self.io.success(f"Đã điền mặc định (ăn hết, ngủ ngon, vui vẻ) cho {count} trẻ.")

    def send_logs(self) -> None:
        today = self._school_today()
        classroom = self.select_class()
        if self.confirm(f"Gửi nhật ký hôm nay của lớp {classroom.name} cho phụ huynh từng trẻ"):
            count = self.system.daily.send_logs(classroom.id, today)
            self.io.success(f"Đã gửi nhật ký của {count} trẻ cho phụ huynh.")

    # ------------------------------------------------------------------ bước 4
    def _message_label(self, m) -> str:
        child = self.system.children.get_or_none(m.child_id) if m.child_id else None
        who = child.full_name if child else f"lớp {self.class_name(m.class_id)}"
        return f"[{m.status.value}] {m.created_at[5:16].replace('T', ' ')} {who}: {m.detail_text()} ({m.sender})"

    def inbox(self) -> None:
        io, daily = self.io, self.system.daily
        items = daily.inbox(self.scope_class_ids(), only_open=True)
        message = self._require(io.choose(items, self._message_label, "Tin phụ huynh chờ xử lý",
                                          "Không có tin nào chờ xử lý."))
        daily.mark_seen(message.id)
        actions = [("reply", "Trả lời"), ("done", {MessageKind.MEDICINE: "Đã cho trẻ uống thuốc",
                                                    MessageKind.LEAVE: "Duyệt đơn xin nghỉ"}.get(message.kind,
                                                                                                "Đã xử lý")),
                   ("decline", "Từ chối (ghi lý do)")]
        action = io.ask_choice("Thao tác", actions)
        if action == "reply":
            daily.reply(message.id, io.ask_text("Nội dung trả lời"), io.ask_yes_no("Đánh dấu đã xử lý", default=False))
        elif action == "done":
            daily.complete(message.id, io.ask_text("Ghi chú cho phụ huynh", required=False) or "")
        else:
            daily.decline(message.id, io.ask_text("Lý do"))
        io.success("Đã cập nhật - phụ huynh sẽ thấy ngay trong hệ thống của mình.")

    def send_to_parents(self) -> None:
        io, daily = self.io, self.system.daily
        if io.ask_choice("Gửi cho", [("one", "Phụ huynh một trẻ"), ("class", "Phụ huynh cả lớp (thông báo)")]) == "one":
            child = self.select_child()
            daily.teacher_send(child.id, io.ask_text("Nội dung"))
        else:
            classroom = self.select_class()
            daily.teacher_send(None, io.ask_text("Nội dung thông báo"), classroom.id, announcement=True)
        io.success("Đã gửi.")

    # ------------------------------------------------------------------ bước 6
    def end_of_day(self) -> None:
        """Giáo viên xem báo cáo cuối ngày của lớp, thêm ghi chú rồi gửi Ban giám hiệu."""
        report = EndOfDayReport(self.system, date.today(), self.scope_class_ids())
        self.io.write(report.to_text())
        note = self.io.ask_text("Ghi chú gửi Ban giám hiệu (Enter nếu không có)", required=False) or ""
        if self.confirm("Gửi báo cáo cuối ngày cho Ban giám hiệu"):
            item = self.system.reports.create("end_of_day", note)
            self.system.reports.submit(item.id)
            self.io.success(f"Đã gửi {item.id} cho Ban giám hiệu.")

    def end_of_day_status(self) -> None:
        status = self.system.reports.end_of_day_status(date.today())
        rows = []
        for classroom in status["classes"]:
            item = status["sent"].get(classroom.id)
            rows.append([classroom.name, item.status.value if item else "CHƯA GỬI",
                         item.sent_at[11:16] if item else "", item.note if item else ""])
        self.io.table(["Lớp", "Báo cáo cuối ngày", "Gửi lúc", "Ghi chú của giáo viên"], rows,
                      title=f"BÁO CÁO CUỐI NGÀY {format_date(date.today())}", max_width=50)
