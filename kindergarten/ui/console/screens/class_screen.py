"""Màn hình console: lớp học, xếp lớp, chuyển lớp, giáo viên chủ nhiệm, thời khóa biểu (T16-T18)."""
from __future__ import annotations

from datetime import timedelta

from ....auth.user import Permission
from ....classroom.classroom import AgeGroup, Classroom
from ....utils import WEEKDAY_NAMES, format_date
from ..menu import Menu
from .base import Screen


class ClassScreen(Screen):
    title = "Lớp học & thời khóa biểu"

    def build_menu(self) -> Menu:
        P = Permission
        return (self.new_menu()
                .add("Danh sách lớp", self.list_classes, P.VIEW_CLASSES)
                .add("In danh sách trẻ của lớp", self.print_class, P.VIEW_CLASSES)
                .add("Tạo lớp mới", self.create_class, P.MANAGE_CLASSES)
                .add("Sửa thông tin lớp", self.edit_class, P.MANAGE_CLASSES)
                .add("Xóa lớp", self.delete_class, P.MANAGE_CLASSES)
                .add("Xếp lớp cho trẻ", self.enroll, P.MANAGE_CLASSES)
                .add("Chuyển lớp", self.transfer, P.MANAGE_CLASSES)
                .add("Rút trẻ khỏi lớp", self.unenroll, P.MANAGE_CLASSES)
                .add("Đổi giáo viên chủ nhiệm", self.change_teacher, P.MANAGE_CLASSES)
                .add("Xem thời khóa biểu của lớp", self.view_timetable, P.VIEW_CLASSES)
                .add("Xem lịch dạy của giáo viên", self.teacher_schedule, P.VIEW_CLASSES)
                .add("Thêm tiết học vào thời khóa biểu", self.add_slot, P.MANAGE_CLASSES)
                .add("Xóa tiết học", self.remove_slot, P.MANAGE_CLASSES)
                .add("Gỡ giáo viên chủ nhiệm khỏi lớp", self.remove_teacher, P.MANAGE_CLASSES)
                .add("Lịch năm học: ngày nghỉ lễ, học Thứ 7", self.calendar, P.MANAGE_CALENDAR)
                .add("Trẻ lệch độ tuổi lớp đang học", self.age_mismatches, P.VIEW_CLASSES)
                .add("Kết thúc năm học (lên lớp / ra trường)", self.end_year, P.MANAGE_CLASSES))

    def remove_teacher(self) -> None:
        """U01: hàm gỡ GVCN đã có ở tầng nghiệp vụ nhưng trước đây không giao diện nào gọi."""
        classroom = self.select_class(self._all_classes())
        teacher = self.system.classes.homeroom_teacher(classroom.id)
        if teacher is None:
            self.io.info(f"Lớp {classroom.name} chưa có giáo viên chủ nhiệm.")
            return
        if self.confirm(f"Gỡ {teacher.full_name} khỏi vị trí chủ nhiệm lớp {classroom.name}?"):
            self.system.classes.remove_homeroom_teacher(classroom.id)
            self.io.success("Đã gỡ giáo viên chủ nhiệm.")

    def calendar(self) -> None:
        """K03: quản lý lịch năm học dùng chung cho điểm danh, tiền ăn, thực đơn, dashboard."""
        cal = self.system.calendar
        self.io.info(f"Học Thứ 7: {'có' if cal.saturday_classes else 'không'}")
        self.io.table(["Ngày", "Thứ", "Tên ngày nghỉ"],
                      [[format_date(d), WEEKDAY_NAMES[d.weekday()], name] for d, name in cal.holidays.items()],
                      title="NGÀY NGHỈ LỄ")
        action = self.io.ask_choice("Thao tác", [("done", "Xong"), ("add", "Thêm ngày nghỉ (một ngày hoặc khoảng)"),
                                                 ("remove", "Xóa ngày nghỉ"), ("sat", "Bật/tắt học Thứ 7")],
                                    default="done")
        if action == "add":
            start = self.io.ask_date("Nghỉ từ ngày")
            end = self.io.ask_date("Đến ngày", start)
            name = self.io.ask_text("Tên ngày nghỉ (VD: Tết Nguyên đán)")
            days = self.system.add_holidays(start, end, name)
            self.io.success(f"Đã thêm {len(days)} ngày nghỉ.")
        elif action == "remove":
            day = self._require(self.io.choose(list(cal.holidays), format_date, "Chọn ngày cần bỏ",
                                               "Chưa có ngày nghỉ nào."))
            self.system.remove_holidays([day])
            self.io.success("Đã bỏ ngày nghỉ.")
        elif action == "sat":
            self.system.set_saturday_classes(not cal.saturday_classes)
            self.io.success(f"Học Thứ 7: {'có' if cal.saturday_classes else 'không'}.")

    def age_mismatches(self) -> None:
        rows = [[c.id, c.full_name, c.age_text, k.name, f"{k.min_age}-{k.max_age}"]
                for c, k in self.system.classes.age_mismatches()
                if self.scope_class_ids() is None or k.id in self.scope_class_ids()]
        self.io.table(["Mã", "Họ tên", "Tuổi", "Lớp", "Độ tuổi lớp"], rows, title="TRẺ LỆCH ĐỘ TUỔI LỚP")

    def end_year(self) -> None:
        """L14: chuyển cả lớp lên khối trên, lớp Lá ra trường (lịch sử vẫn giữ)."""
        self.io.warning("Mọi lớp sẽ lên khối trên; trẻ lớp Lá chuyển sang 'Ra trường'. Hệ thống tự sao lưu trước.")
        if not self.confirm("Thực hiện kết thúc năm học"):
            return
        backup = self.system.backup()
        result = self.system.classes.end_school_year()
        self.system.audit("Kết thúc năm học", "", result)
        self.io.success(f"Đã sao lưu ({backup.name}). Ra trường: {len(result['graduated'])} trẻ. "
                        f"Lên lớp: {'; '.join(result['promoted']) or 'không có'}.")
        self.io.info("Nên đổi tên lớp cho đúng khối mới trong 'Sửa thông tin lớp'.")

    def _all_classes(self) -> list[Classroom]:
        return self.system.classes.all_sorted()

    # ------------------------------------------------------------------ lớp học
    def list_classes(self) -> None:
        rows = []
        for classroom in self._all_classes():
            teacher = self.system.classes.homeroom_teacher(classroom.id)
            rows.append([classroom.id, classroom.name, classroom.age_group.label,
                         f"{classroom.min_age}-{classroom.max_age}", classroom.room or "-",
                         teacher.full_name if teacher else "-", f"{classroom.size}/{classroom.capacity}",
                         classroom.available_slots])
        self.io.table(["Mã", "Tên lớp", "Khối", "Độ tuổi", "Phòng", "GV chủ nhiệm", "Sĩ số", "Còn trống"], rows,
                      title="DANH SÁCH LỚP")

    def print_class(self) -> None:
        classroom = self.select_class()
        self.io.write(self.system.classes.class_list_text(classroom.id, self.system.parents.contact_of))

    def create_class(self) -> None:
        io = self.io
        name = io.ask_text("Tên lớp (VD: Mầm Sơn Ca)")
        group = io.ask_choice("Khối lớp", [(g, str(g)) for g in AgeGroup])
        capacity = io.ask_int("Sĩ số tối đa", 25, 1, Classroom.MAX_CAPACITY)
        room = io.ask_text("Phòng học", required=False) or ""
        teacher = io.choose(self.system.classes.free_teachers(), self.employee_label,
                            "Giáo viên chủ nhiệm (Enter = phân công sau)", "Không còn giáo viên nào chưa chủ nhiệm.")
        classroom = self.system.classes.create_class(name, group, capacity, room, teacher.id if teacher else None)
        io.success(f"Đã tạo lớp {classroom}.")

    def edit_class(self) -> None:
        io = self.io
        classroom = self.select_class(self._all_classes())
        io.info("Nhấn Enter để giữ nguyên giá trị hiện tại.")
        new_data = {
            "name": io.ask_text("Tên lớp", classroom.name),
            "age_group": io.ask_choice("Khối lớp", [(g, str(g)) for g in AgeGroup], classroom.age_group),
            "capacity": io.ask_int("Sĩ số tối đa", classroom.capacity, 1, Classroom.MAX_CAPACITY),
            "room": io.ask_text("Phòng học", classroom.room, required=False),
        }
        changes = {k: v for k, v in new_data.items() if v is not None and v != getattr(classroom, k)}
        if not changes:
            io.info("Không có thay đổi.")
            return
        self.system.classes.update(classroom.id, **changes)   # độ tuổi trẻ kiểm tra ở tầng nghiệp vụ (L11)
        io.success(f"Đã cập nhật lớp {classroom}.")

    def delete_class(self) -> None:
        classroom = self.select_class(self._all_classes())
        if self.confirm(f"Xóa lớp {classroom}? (thời khóa biểu của lớp cũng bị xóa)"):
            self.system.classes.remove(classroom.id)
            self.io.success(f"Đã xóa lớp {classroom.name}.")

    # ------------------------------------------------------------------ xếp lớp
    def _target_label(self, child, classroom: Classroom) -> str:
        notes = []
        if classroom.is_full:
            notes.append("ĐÃ ĐỦ SĨ SỐ")
        if not classroom.accepts_age(child.age):
            notes.append("không hợp độ tuổi")
        return self.class_label(classroom) + (f" [{', '.join(notes)}]" if notes else "")

    def enroll(self) -> None:
        child = self.select_child(self.system.children.find_unassigned(), "Chọn trẻ chưa xếp lớp")
        suggestions = self.system.classes.suggest_classes(child.id)
        if suggestions:
            self.io.info("Các lớp phù hợp độ tuổi và còn chỗ: " + ", ".join(c.name for c in suggestions))
        classroom = self.select_class(self._all_classes(), "Xếp vào lớp")
        self.system.classes.enroll(child.id, classroom.id)
        self.io.success(f"Đã xếp {child.full_name} vào lớp {classroom.name} ({classroom.size}/{classroom.capacity}).")

    def transfer(self) -> None:
        children = [c for c in self.system.children.all_sorted() if c.class_id]
        child = self.select_child(children, "Chọn trẻ cần chuyển lớp")
        targets = [c for c in self._all_classes() if c.id != child.class_id]
        classroom = self._require(self.io.choose(targets, lambda c: self._target_label(child, c), "Chuyển sang lớp",
                                                 "Không có lớp khác."))
        old = self.class_name(child.class_id)
        self.system.classes.transfer(child.id, classroom.id)
        self.io.success(f"Đã chuyển {child.full_name}: {old} -> {classroom.name}.")

    def unenroll(self) -> None:
        children = [c for c in self.system.children.all_sorted() if c.class_id]
        child = self.select_child(children, "Chọn trẻ cần rút khỏi lớp")
        if self.confirm(f"Rút {child.full_name} khỏi lớp {self.class_name(child.class_id)}?"):
            classroom = self.system.classes.unenroll(child.id)
            self.io.success(f"Đã rút {child.full_name} khỏi lớp {classroom.name}.")

    def change_teacher(self) -> None:
        classroom = self.select_class(self._all_classes())
        current = self.system.classes.homeroom_teacher(classroom.id)
        self.io.info(f"Giáo viên chủ nhiệm hiện tại: {current.full_name if current else 'chưa có'}")
        candidates = self.system.classes.free_teachers()
        teacher = self.select_teacher(candidates, "Chọn giáo viên chủ nhiệm mới (chỉ hiện GV chưa chủ nhiệm)")
        self.system.classes.change_homeroom_teacher(classroom.id, teacher.id)
        self.io.success(f"Lớp {classroom.name} nay do {teacher.full_name} chủ nhiệm.")

    # ------------------------------------------------------------------ thời khóa biểu
    def view_timetable(self) -> None:
        classroom = self.select_class()
        self.io.write(self.system.timetable.weekly_text(class_id=classroom.id))

    def teacher_schedule(self) -> None:
        teacher = self.select_teacher()
        self.io.write(self.system.timetable.weekly_text(teacher_id=teacher.id))

    def add_slot(self) -> None:
        io = self.io
        classroom = self.select_class(self._all_classes())
        weekday = io.ask_choice("Thứ", [(i, WEEKDAY_NAMES[i]) for i in range(6)])
        start = io.ask_time("Giờ bắt đầu")
        end = io.ask_time("Giờ kết thúc")
        activity = io.ask_text("Nội dung hoạt động (VD: Âm nhạc)")
        homeroom = self.system.classes.homeroom_teacher(classroom.id)
        teacher = io.choose(self.system.employees.teachers(), self.employee_label,
                            f"Giáo viên phụ trách (Enter = GVCN {homeroom.full_name if homeroom else 'không có'})")
        teacher = teacher or homeroom
        slot = self.system.timetable.add_slot(classroom.id, weekday, start, end, activity,
                                              teacher.id if teacher else None)
        io.success(f"Đã thêm tiết '{slot.activity}' {slot.time_label} cho lớp {classroom.name}.")

    def remove_slot(self) -> None:
        classroom = self.select_class(self._all_classes())
        slot = self._require(self.io.choose(self.system.timetable.of_class(classroom.id),
                                            lambda s: f"{s.id} - {s.time_label}: {s.activity}", "Chọn tiết cần xóa",
                                            "Lớp chưa có tiết nào."))
        if self.confirm(f"Xóa tiết '{slot.activity}' {slot.time_label}?"):
            self.system.timetable.remove(slot.id)
            self.io.success("Đã xóa tiết học.")
