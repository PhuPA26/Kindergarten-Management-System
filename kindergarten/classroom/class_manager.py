"""T17 - ClassManager: xếp lớp, chuyển lớp, đổi giáo viên chủ nhiệm, in danh sách lớp."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..core.base_manager import BaseManager
from ..core.person import Employee
from ..exceptions import DuplicateIdError, InvalidAgeError, KindergartenError
from ..hr.employee_manager import EmployeeManager
from ..hr.employees import Teacher
from ..people.child import Child
from ..people.managers import ChildManager
from ..utils import format_date, format_key_values, format_table, normalize_text
from .classroom import AgeGroup, Classroom


class ClassManager(BaseManager[Classroom]):
    entity_name = "lớp học"

    def __init__(self, child_manager: ChildManager, employee_manager: EmployeeManager) -> None:
        super().__init__()
        self.children = child_manager
        self.employees = employee_manager
        child_manager.on_remove(self._on_child_removed)
        employee_manager.on_before_remove(self._check_employee_removable)

    # ------------------------------------------------------------------ hook / sự kiện
    def _validate_new(self, classroom: Classroom) -> None:
        self._check_unique_name(classroom)

    def _validate_update(self, classroom: Classroom) -> None:
        self._check_unique_name(classroom)
        # L11: đổi khối lớp không được làm trẻ đang học lệch độ tuổi (trước đây chỉ giao diện chặn)
        wrong = [c.full_name for c in self.class_list(classroom.id) if not classroom.accepts_age(c.age)]
        if wrong:
            raise InvalidAgeError(f"Không đổi được khối lớp vì các trẻ sau không hợp độ tuổi "
                                  f"{classroom.min_age}-{classroom.max_age}: {', '.join(wrong)}.")

    def age_mismatches(self) -> list[tuple[Child, Classroom]]:
        """Trẻ đã lớn hơn độ tuổi của lớp đang học (L14) - nhắc việc lên lớp/ra trường."""
        result = []
        for classroom in self.all_sorted():
            for child in self.class_list(classroom.id):
                if not classroom.accepts_age(child.age):
                    result.append((child, classroom))
        return result

    def _check_unique_name(self, classroom: Classroom) -> None:
        key = normalize_text(classroom.name)
        if any(c is not classroom and normalize_text(c.name) == key for c in self):
            raise DuplicateIdError(f"Đã có lớp tên '{classroom.name}'.")

    def _before_remove(self, classroom: Classroom) -> None:
        if classroom.size:
            raise KindergartenError(f"Lớp {classroom.name} còn {classroom.size} trẻ. "
                                    "Hãy chuyển trẻ sang lớp khác trước khi xóa lớp.")
        teacher = self.homeroom_teacher(classroom.id)
        classroom.unassign_teacher(teacher)

    def _on_child_removed(self, child: Child) -> None:
        for classroom in self:
            classroom.drop_child_id(child.id)

    def _check_employee_removable(self, employee: Employee) -> None:
        if isinstance(employee, Teacher) and employee.homeroom_class_id:
            classroom = self.get_or_none(employee.homeroom_class_id)
            if classroom is not None:
                raise KindergartenError(f"{employee.full_name} đang chủ nhiệm lớp {classroom.name}. "
                                        "Hãy đổi giáo viên chủ nhiệm trước khi xóa.")

    # ------------------------------------------------------------------ tạo lớp
    def all_sorted(self) -> list[Classroom]:
        order = {"NURSERY": 0, "BEGINNER": 1, "INTERMEDIATE": 2, "SENIOR": 3}
        return self.sort(lambda c: (order[c.age_group.name], normalize_text(c.name)))

    def create_class(self, name: str, age_group: Any, capacity: Any = 25, room: str = "",
                     teacher_id: str | None = None) -> Classroom:
        teacher = self._available_teacher(teacher_id, None) if teacher_id else None
        classroom = self.add(Classroom(name, age_group, capacity, room))
        if teacher is not None:
            classroom.assign_teacher(teacher)
        return classroom

    def class_name(self, class_id: str | None) -> str:
        classroom = self.get_or_none(class_id) if class_id else None
        return classroom.name if classroom else "Chưa xếp lớp"

    # ------------------------------------------------------------------ xếp lớp, chuyển lớp
    def class_of(self, child_id: str) -> Classroom | None:
        child = self.children.get(child_id)
        return self.get_or_none(child.class_id) if child.class_id else None

    def enroll(self, child_id: str, class_id: str) -> Classroom:
        """Xếp lớp cho trẻ chưa có lớp."""
        self._authorize()
        child, classroom = self.children.get(child_id), self.get(class_id)
        if not child.is_active:
            raise KindergartenError(f"{child.full_name} đã {child.status.lower()}, không xếp lớp được.")
        current = self.class_of(child.id)
        if current is not None:
            raise KindergartenError(f"{child.full_name} đang học lớp {current.name}, "
                                    "hãy dùng chức năng chuyển lớp.")
        classroom.add_child(child)
        return classroom

    def transfer(self, child_id: str, new_class_id: str) -> Classroom:
        """Chuyển lớp: kiểm tra lớp mới trước, chỉ khi hợp lệ mới rút trẻ khỏi lớp cũ."""
        self._authorize()
        child, new_class = self.children.get(child_id), self.get(new_class_id)
        old_class = self.class_of(child.id)
        if old_class is new_class:
            raise KindergartenError(f"{child.full_name} đã ở lớp {new_class.name}.")
        new_class.check_can_accept(child)
        if old_class is not None:
            old_class.remove_child(child)
        new_class.add_child(child)
        return new_class

    def unenroll(self, child_id: str) -> Classroom:
        self._authorize()
        child = self.children.get(child_id)
        classroom = self.class_of(child.id)
        if classroom is None:
            raise KindergartenError(f"{child.full_name} chưa được xếp lớp.")
        classroom.remove_child(child)
        return classroom

    # ------------------------------------------------------------------ vòng đời trẻ (L14)
    def withdraw(self, child_id: str, status: str = "Đã nghỉ", on_date: Any = None) -> Child:
        """Cho trẻ thôi học / ra trường: rút khỏi lớp nhưng GIỮ toàn bộ lịch sử (điểm danh, sức khỏe, hóa đơn)."""
        self._authorize()
        child = self.children.get(child_id)
        if not child.is_active:
            raise KindergartenError(f"{child.full_name} đã ở trạng thái '{child.status}'.")
        classroom = self.class_of(child.id)
        if classroom is not None:
            classroom.remove_child(child)
        child.status = status
        child.leave_date = on_date or date.today()
        return child

    def readmit(self, child_id: str) -> Child:
        """Cho trẻ đã nghỉ học lại (sau đó xếp lớp như bình thường)."""
        self._authorize()
        child = self.children.get(child_id)
        if child.is_active:
            raise KindergartenError(f"{child.full_name} đang học.")
        child.status, child.leave_date = "Đang học", None
        return child

    def end_school_year(self, on_date: Any = None) -> dict[str, list[str]]:
        """Kết thúc năm học: lớp Lá ra trường, các lớp khác lên khối trên (giữ nguyên trẻ và giáo viên)."""
        self._authorize()
        order = list(AgeGroup)
        graduated, promoted = [], []
        for classroom in self.all_sorted():
            if classroom.age_group is AgeGroup.SENIOR:
                for child in self.class_list(classroom.id):
                    self.withdraw(child.id, "Ra trường", on_date)
                    graduated.append(child.full_name)
            else:
                classroom.age_group = order[order.index(classroom.age_group) + 1]
                promoted.append(f"{classroom.name} -> khối {classroom.age_group.label}")
        return {"graduated": graduated, "promoted": promoted}

    def suggest_classes(self, child_id: str) -> list[Classroom]:
        """Các lớp còn chỗ và phù hợp độ tuổi của trẻ."""
        child = self.children.get(child_id)
        return [c for c in self.all_sorted() if not c.is_full and c.accepts_age(child.age)
                and not c.has_child(child.id)]

    # ------------------------------------------------------------------ giáo viên chủ nhiệm
    def homeroom_teacher(self, class_id: str) -> Teacher | None:
        classroom = self.get(class_id)
        if not classroom.teacher_id:
            return None
        employee = self.employees.get_or_none(classroom.teacher_id)
        return employee if isinstance(employee, Teacher) else None

    def _available_teacher(self, teacher_id: str, class_id: str | None) -> Teacher:
        teacher = self.employees.get_teacher(teacher_id)
        if teacher.homeroom_class_id and teacher.homeroom_class_id != (class_id or "").upper():
            other = self.get_or_none(teacher.homeroom_class_id)
            if other is not None:
                raise KindergartenError(f"{teacher.full_name} đang chủ nhiệm lớp {other.name}.")
        return teacher

    def change_homeroom_teacher(self, class_id: str, teacher_id: str) -> Classroom:
        self._authorize()
        classroom = self.get(class_id)
        teacher = self._available_teacher(teacher_id, classroom.id)
        old_teacher = self.homeroom_teacher(classroom.id)
        if old_teacher is not None and old_teacher is not teacher:
            old_teacher.homeroom_class_id = None
        classroom.assign_teacher(teacher)
        return classroom

    def remove_homeroom_teacher(self, class_id: str) -> Classroom:
        self._authorize()
        classroom = self.get(class_id)
        classroom.unassign_teacher(self.homeroom_teacher(classroom.id))
        return classroom

    def free_teachers(self) -> list[Teacher]:
        """Giáo viên chưa chủ nhiệm lớp nào."""
        return [t for t in self.employees.teachers()
                if not t.homeroom_class_id or self.get_or_none(t.homeroom_class_id) is None]

    # ------------------------------------------------------------------ danh sách lớp
    def class_list(self, class_id: str) -> list[Child]:
        classroom = self.get(class_id)
        children = [self.children.get_or_none(cid) for cid in classroom.child_ids]
        return self.children.sort("sort_key", items=[c for c in children if c is not None])

    def class_list_text(self, class_id: str, parent_lookup: Any = None) -> str:
        """In danh sách lớp. `parent_lookup(child_id) -> str` để hiển thị liên hệ phụ huynh."""
        classroom = self.get(class_id)
        teacher = self.homeroom_teacher(classroom.id)
        info = format_key_values([
            ("Lớp", f"{classroom.name} ({classroom.id})"),
            ("Khối", str(classroom.age_group)),
            ("Phòng", classroom.room or "-"),
            ("GV chủ nhiệm", teacher.full_name if teacher else "Chưa phân công"),
            ("Sĩ số", f"{classroom.size}/{classroom.capacity}"),
        ], title=f"DANH SÁCH LỚP {classroom.name.upper()}")
        headers = ["STT", "Mã", "Họ tên", "Giới tính", "Ngày sinh", "Tuổi"]
        if parent_lookup:
            headers.append("Phụ huynh")
        rows = []
        for index, child in enumerate(self.class_list(classroom.id), 1):
            row = [index, child.id, child.full_name, child.gender, format_date(child.dob), child.age_text]
            if parent_lookup:
                row.append(parent_lookup(child.id))
            rows.append(row)
        return f"{info}\n{format_table(headers, rows, max_width=60)}"

    def sync_links(self) -> None:
        """Đồng bộ lớp - trẻ - giáo viên sau khi đọc file."""
        for child in self.children:
            classroom = self.get_or_none(child.class_id) if child.class_id else None
            if classroom is None or not classroom.has_child(child.id):
                child.class_id = None
        for classroom in self:
            for child_id in classroom.child_ids:
                child = self.children.get_or_none(child_id)
                if child is None:
                    classroom.drop_child_id(child_id)
                else:
                    child.class_id = classroom.id
            if classroom.teacher_id:
                teacher = self.employees.get_or_none(classroom.teacher_id)
                if isinstance(teacher, Teacher):
                    teacher.homeroom_class_id = classroom.id
                else:
                    classroom.unassign_teacher()
        for teacher in self.employees.teachers():
            classroom = self.get_or_none(teacher.homeroom_class_id) if teacher.homeroom_class_id else None
            if classroom is None or classroom.teacher_id != teacher.id:
                teacher.homeroom_class_id = None
