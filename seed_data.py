"""T31 - Nạp sẵn dữ liệu mẫu để demo: 20 trẻ, 27 phụ huynh, 5 giáo viên, 4 nhân viên, 3 lớp,
thời khóa biểu, 3 tháng điểm danh, hồ sơ sức khỏe, dị ứng, thực đơn, hóa đơn học phí, nhật ký ăn ngủ và
trao đổi phụ huynh của các ngày gần đây; tài khoản cho đủ 5 hệ thống (BGH, giáo viên, kế toán, nhân viên, phụ huynh).

Ngày tháng được tính tương đối theo ngày chạy nên dữ liệu luôn "mới".

Chạy riêng:  python seed_data.py            (ghi đè dữ liệu trong thư mục data/)
Hoặc:        python main.py --seed
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

from kindergarten.attendance.records import AttendanceStatus
from kindergarten.auth.user import User
from kindergarten.daily.records import MEAL_LEVELS, MEALS as DAY_MEALS, MOODS, NAP_LEVELS, MessageKind, MessageStatus
from kindergarten.auth.user import Role
from kindergarten.classroom.classroom import AgeGroup
from kindergarten.hr.employees import Staff, Teacher
from kindergarten.nutrition.meal import MealType
from kindergarten.people.child import Child, PickupPerson
from kindergarten.people.parent import Parent
from kindergarten.system import KindergartenSystem
from kindergarten.utils import add_months, age_in_months, month_bounds, previous_month, school_days

# (tên đăng nhập, mật khẩu, mô tả) - hiển thị gợi ý ở màn hình đăng nhập
DEMO_ACCOUNTS = [
    ("admin", "admin123", "Ban giám hiệu (Hiệu trưởng)"),
    ("ketoan", "ketoan123", "Kế toán"),
    ("gv.nhung", "giaovien123", "Giáo viên CN lớp Mầm Sơn Ca"),
    ("gv.ha", "giaovien123", "Giáo viên CN lớp Chồi Họa Mi"),
    ("gv.maianh", "giaovien123", "Giáo viên CN lớp Lá Vành Khuyên"),
    ("gv.tuan", "giaovien123", "Giáo viên bộ môn Âm nhạc"),
    ("gv.lan", "giaovien123", "Giáo viên bộ môn Tiếng Anh"),
    ("nv.sau", "nhanvien123", "Nhân viên cấp dưỡng"),
    ("nv.hung", "nhanvien123", "Nhân viên bảo vệ (đón/trả trẻ ở cổng)"),
    ("nv.yen", "nhanvien123", "Nhân viên y tế (cân đo, dị ứng)"),
    ("ph.mai", "phuhuynh123", "Phụ huynh: mẹ bé Minh Khang (Mầm Sơn Ca)"),
    ("ph.trang", "phuhuynh123", "Phụ huynh: mẹ bé Bảo Ngọc (Mầm Sơn Ca)"),
]

TEACHERS = [
    # họ tên, ngày sinh, SĐT, trình độ, hệ số, chuyên môn, ngày vào làm, giới tính
    ("Nguyễn Thị Hồng Nhung", "1986-04-12", "0912345601", "Đại học", 3.00, "", "2012-08-15", "Nữ"),
    ("Trần Thị Thu Hà", "1993-09-03", "0912345602", "Cao đẳng", 2.41, "", "2018-08-20", "Nữ"),
    ("Lê Thị Mai Anh", "1990-01-25", "0912345603", "Đại học", 2.67, "", "2016-09-01", "Nữ"),
    ("Phạm Minh Tuấn", "1994-06-18", "0912345604", "Đại học", 2.34, "Âm nhạc", "2020-08-10", "Nam"),
    ("Võ Thị Lan", "1996-11-30", "0912345605", "Đại học", 2.34, "Tiếng Anh", "2021-08-16", "Nữ"),
]

STAFF = [
    # họ tên, ngày sinh, SĐT, chức vụ, lương cơ bản, phụ cấp, ngày vào làm, giới tính
    ("Đỗ Văn Hùng", "1975-02-20", "0983456701", "Bảo vệ", 5_500_000, 300_000, "2015-03-01", "Nam"),
    ("Bùi Thị Sáu", "1980-06-11", "0983456702", "Cấp dưỡng", 6_000_000, 500_000, "2016-08-01", "Nữ"),
    ("Hoàng Thị Yến", "1992-10-05", "0983456703", "Nhân viên y tế", 7_000_000, 500_000, "2019-08-15", "Nữ"),
    ("Ngô Thị Kim Oanh", "1987-12-25", "0983456704", "Kế toán", 8_000_000, 700_000, "2017-07-01", "Nữ"),
]

CLASSES = [
    # tên lớp, khối, sĩ số tối đa, phòng, GVCN (chỉ số trong TEACHERS)
    ("Mầm Sơn Ca", AgeGroup.BEGINNER, 10, "P.101", 0),
    ("Chồi Họa Mi", AgeGroup.INTERMEDIATE, 10, "P.102", 1),
    ("Lá Vành Khuyên", AgeGroup.SENIOR, 7, "P.201", 2),
]

FAMILIES = [
    # bố (họ tên, nghề), mẹ (họ tên, nghề), hộ nghèo, địa chỉ
    (("Nguyễn Văn Hùng", "Kỹ sư xây dựng"), ("Trần Thị Mai", "Giáo viên"), False, "12 Lê Lợi, phường Bến Thành"),
    (("Lê Quang Minh", "Bác sĩ"), ("Phạm Thu Trang", "Dược sĩ"), False, "45 Hai Bà Trưng, phường Tân Định"),
    (("Trần Đức Thắng", "Lái xe"), None, True, "Hẻm 23 Nguyễn Trãi, phường Chợ Quán"),
    (None, ("Phạm Thị Hạnh", "Kinh doanh"), False, "8 Pasteur, phường Sài Gòn"),
    (("Hoàng Văn Long", "Kiến trúc sư"), ("Đinh Thị Ngọc", "Kế toán"), False, "102 Võ Văn Tần, phường Xuân Hòa"),
    (("Vũ Mạnh Cường", "Công an"), ("Nguyễn Thị Lan Hương", "Y tá"), False, "17 Trần Hưng Đạo, phường Cầu Ông Lãnh"),
    (("Đặng Văn Toàn", "Kỹ sư phần mềm"), ("Hà Thị Thu", "Nhân viên ngân hàng"), False, "56 Cách Mạng Tháng Tám"),
    (("Bùi Văn Sơn", "Thợ điện"), None, False, "9 Lý Tự Trọng, phường Sài Gòn"),
    (("Đỗ Quốc Việt", "Luật sư"), ("Lê Thị Thanh Tâm", "Giảng viên"), False, "33 Nam Kỳ Khởi Nghĩa"),
    (("Ngô Thanh Bình", "Kinh doanh"), None, False, "71 Điện Biên Phủ, phường Gia Định"),
    (("Dương Văn Lực", "Công nhân"), ("Tạ Thị Hằng", "Công nhân"), False, "Hẻm 5 Phan Xích Long"),
    (None, ("Lý Thị Hoa", "Thợ may"), False, "28 Nguyễn Thị Minh Khai"),
    (("Hồ Văn Tài", "Nhân viên văn phòng"), ("Quách Thị Yến", "Nội trợ"), False, "64 Lê Văn Sỹ"),
    (("Phan Văn Đức", "Lao động tự do"), None, True, "Hẻm 112 Bùi Viện"),
    (("Trịnh Văn Khải", "Kỹ thuật viên"), None, False, "15 Nguyễn Đình Chiểu"),
    (("Mai Văn Thành", "Doanh nhân"), ("Châu Thị Diễm", "Nhà thiết kế"), False, "201 Nguyễn Văn Trỗi"),
    (("Lâm Quốc Huy", "Phóng viên"), None, False, "40 Trương Định"),
    (("Cao Văn Dũng", "Nông dân"), None, False, "Ấp 3, xã Bình Chánh"),
]

CHILDREN = [
    # họ tên, giới tính, tuổi (năm, tháng), lớp (chỉ số CLASSES / None), gia đình, tên ở nhà, dịch vụ
    ("Nguyễn Minh Khang", "Nam", (3, 2), 0, 0, "Bin", []),
    ("Lê Bảo Ngọc", "Nữ", (3, 5), 0, 1, "Na", ["Năng khiếu (vẽ, múa)"]),
    ("Trần Gia Huy", "Nam", (3, 8), 0, 2, "Bo", []),
    ("Phạm Khánh Linh", "Nữ", (3, 10), 0, 3, "Mít", []),
    ("Hoàng Đức Anh", "Nam", (3, 4), 0, 4, "Su", ["Tiếng Anh"]),
    ("Vũ Ngọc Hân", "Nữ", (3, 7), 0, 5, "Bông", []),
    ("Đặng Tuấn Kiệt", "Nam", (4, 1), 1, 6, "Tôm", ["Tiếng Anh"]),
    ("Bùi Thảo Vy", "Nữ", (4, 3), 1, 7, "Thỏ", []),
    ("Đỗ Hoàng Nam", "Nam", (4, 6), 1, 8, "Cún", []),
    ("Ngô Phương Anh", "Nữ", (4, 9), 1, 9, "Kem", ["Năng khiếu (vẽ, múa)"]),
    ("Dương Minh Quân", "Nam", (4, 2), 1, 10, "Bắp", []),
    ("Lý An Nhiên", "Nữ", (4, 11), 1, 11, "Mây", ["Tiếng Anh", "Năng khiếu (vẽ, múa)"]),
    ("Hồ Thiên Phúc", "Nam", (5, 1), 2, 12, "Tin", []),
    ("Vũ Gia Bảo", "Nam", (5, 4), 2, 5, "Bi", ["Tiếng Anh"]),
    ("Đỗ Ngọc Diệp", "Nữ", (5, 8), 2, 8, "Xu", []),
    ("Phan Hải Đăng", "Nam", (5, 2), 2, 13, "Gấu", []),
    ("Trịnh Mai Chi", "Nữ", (5, 10), 2, 14, "Chíp", ["Năng khiếu (vẽ, múa)"]),
    ("Mai Đức Trí", "Nam", (5, 6), 2, 15, "Ken", ["Tiếng Anh"]),
    ("Lâm Bảo Trâm", "Nữ", (5, 3), 2, 16, "Sóc", []),
    ("Cao Minh Đạt", "Nam", (2, 6), None, 17, "Ốc", []),
]

# Hệ số cân nặng để tạo vài trường hợp cần chú ý dinh dưỡng (chỉ số trong CHILDREN)
WEIGHT_FACTORS = {3: 0.80, 15: 0.80, 6: 1.18, 17: 1.30}

PICKUP_PERSONS = {
    0: ("Nguyễn Văn Bảy", "Ông nội", "0977000111"),
    2: ("Trần Thị Tư", "Bà ngoại", "0977000222"),
    5: ("Vũ Thị Hoa", "Cô ruột", "0977000333"),
    12: ("Hồ Văn Lộc", "Ông nội", "0977000444"),
    16: ("Trịnh Thị Lan", "Bà nội", "0977000555"),
}

ALLERGIES = [
    # chỉ số trẻ, chất gây dị ứng, mức độ, biểu hiện
    (1, "tôm", "Nặng", "Nổi mẩn đỏ, khó thở"),
    (4, "trứng", "Nhẹ", "Ngứa nhẹ quanh miệng"),
    (7, "sữa bò", "Trung bình", "Đau bụng, tiêu chảy"),
    (12, "đậu phộng", "Nặng", "Sưng môi, nổi mề đay"),
    (16, "hải sản", "Trung bình", "Nổi mẩn ngứa"),
]

MEALS = {
    # tên món: (kcal, thành phần)
    "Cháo thịt bằm bí đỏ": (220, "gạo, thịt heo, bí đỏ, hành lá"),
    "Phở gà": (280, "bánh phở, thịt gà, hành lá"),
    "Bún riêu cua": (300, "bún, cua, cà chua, đậu hũ"),
    "Bánh mì trứng ốp la": (320, "bánh mì, trứng gà"),
    "Cháo tôm rau ngót": (230, "gạo, tôm, rau ngót"),
    "Xôi đậu xanh": (300, "gạo nếp, đậu xanh, dừa nạo"),
    "Mì xào thịt bò": (310, "mì, thịt bò, cải ngọt"),
    "Cơm trắng": (200, "gạo"),
    "Thịt kho trứng cút": (260, "thịt heo, trứng cút, nước dừa"),
    "Cá basa sốt cà chua": (190, "cá basa, cà chua"),
    "Tôm rim thịt": (210, "tôm, thịt heo"),
    "Gà kho gừng": (230, "thịt gà, gừng"),
    "Bò xào bông cải": (210, "thịt bò, bông cải xanh, cà rốt"),
    "Đậu hũ sốt cà chua": (150, "đậu hũ, cà chua"),
    "Canh bí đỏ đậu phộng": (120, "bí đỏ, đậu phộng"),
    "Canh rau ngót thịt bằm": (90, "rau ngót, thịt heo"),
    "Canh chua cá lóc": (130, "cá lóc, cà chua, thơm, giá đỗ"),
    "Canh cải thịt bằm": (80, "cải ngọt, thịt heo"),
    "Sữa tươi": (130, "sữa bò"),
    "Sữa chua": (100, "sữa chua"),
    "Bánh flan": (150, "trứng gà, sữa tươi, đường"),
    "Chè đậu xanh": (160, "đậu xanh, đường"),
    "Chuối": (90, "chuối"),
    "Dưa hấu": (60, "dưa hấu"),
    "Bánh bông lan": (180, "bột mì, trứng gà, đường"),
}

WEEK_A = [
    ("Cháo thịt bằm bí đỏ", ["Cơm trắng", "Tôm rim thịt", "Canh rau ngót thịt bằm"], ["Sữa tươi", "Chuối"]),
    ("Phở gà", ["Cơm trắng", "Thịt kho trứng cút", "Canh bí đỏ đậu phộng"], ["Sữa chua"]),
    ("Bánh mì trứng ốp la", ["Cơm trắng", "Cá basa sốt cà chua", "Canh cải thịt bằm"], ["Chè đậu xanh"]),
    ("Xôi đậu xanh", ["Cơm trắng", "Gà kho gừng", "Canh chua cá lóc"], ["Bánh flan"]),
    ("Bún riêu cua", ["Cơm trắng", "Bò xào bông cải", "Đậu hũ sốt cà chua"], ["Dưa hấu"]),
]
WEEK_B = [
    ("Cháo tôm rau ngót", ["Cơm trắng", "Gà kho gừng", "Canh cải thịt bằm"], ["Sữa tươi"]),
    ("Mì xào thịt bò", ["Cơm trắng", "Cá basa sốt cà chua", "Canh rau ngót thịt bằm"], ["Chuối"]),
    ("Phở gà", ["Cơm trắng", "Thịt kho trứng cút", "Canh bí đỏ đậu phộng"], ["Bánh bông lan"]),
    ("Cháo thịt bằm bí đỏ", ["Cơm trắng", "Bò xào bông cải", "Canh chua cá lóc"], ["Sữa chua"]),
    ("Bánh mì trứng ốp la", ["Cơm trắng", "Đậu hũ sốt cà chua", "Canh cải thịt bằm"], ["Dưa hấu"]),
]

LEARNING = ["Làm quen với Toán", "Khám phá khoa học", "Làm quen chữ cái", "Tạo hình", "Văn học - Kể chuyện"]
# (chỉ số lớp, thứ) -> (hoạt động, chỉ số giáo viên bộ môn)
SPECIAL_LESSONS = {
    (0, 0): ("Âm nhạc", 3), (1, 1): ("Âm nhạc", 3), (2, 2): ("Âm nhạc", 3),
    (0, 2): ("Tiếng Anh", 4), (1, 3): ("Tiếng Anh", 4), (2, 4): ("Tiếng Anh", 4),
}
SUBJECT_TOPICS = {
    "Âm nhạc": ["Dạy hát: Cả nhà thương nhau", "Vận động theo nhạc: Con cào cào", "Nghe hát: Ru con",
                "Trò chơi âm nhạc: Ai nhanh nhất", "Dạy hát: Cháu yêu bà", "Gõ đệm theo phách: Đàn gà con"],
    "Tiếng Anh": ["Colors: red, blue, yellow", "Animals: cat, dog, bird", "Numbers 1 - 5", "Greetings: Hello, Goodbye",
                  "Family: mom, dad, baby", "Fruits: apple, banana, orange"],
}
CHILD_COMMENTS = {
    "Nổi bật": ["Hát to, rõ lời, mạnh dạn biểu diễn trước lớp", "Nhớ từ mới nhanh, phát âm chuẩn",
                "Hăng hái xung phong, giúp bạn cùng làm"],
    "Cần hỗ trợ": ["Còn rụt rè, chưa dám hát cùng bạn", "Chưa tập trung, cần cô nhắc nhiều",
                   "Chưa nhớ từ mới, cần ôn thêm ở nhà"],
}
LEAVE_REASONS = ["Bé bị sốt", "Gia đình về quê", "Bé đi khám răng", "Bé bị ho, sổ mũi", "Gia đình có việc riêng"]


def _message(kind, content, parent, child, day, medicine="", dosage="", time_text="", class_id=None, sender=None):
    from kindergarten.daily.records import Message
    if kind is MessageKind.ANNOUNCEMENT:
        return Message(kind, content, sender, "Giáo viên", None, class_id, day)
    return Message(kind, content, f"{parent.relationship} {parent.full_name}", "Phụ huynh", child.id, child.class_id,
                   day, medicine, dosage, time_text, created_at=f"{day.isoformat()}T07:{random.randint(5, 50):02d}")


def _ideal_size(months: int) -> tuple[float, float]:
    """Chiều cao (cm), cân nặng (kg) trung bình gần đúng theo tháng tuổi."""
    return 87 + (months - 24) * 0.58, 12.2 + (months - 24) * 0.17


def seed(system: KindergartenSystem, verbose: bool = False) -> dict[str, int]:
    """Xóa dữ liệu hiện có trong bộ nhớ và nạp dữ liệu mẫu. Trả về số lượng từng loại dữ liệu."""
    rng = random.Random(2026)
    today = date.today()
    system.reset()

    # ---------------- Nhân sự
    teachers = [system.employees.add(Teacher(name, dob, phone, gender=gender, qualification=qual,
                                             salary_coefficient=coef, specialty=spec, hire_date=hired,
                                             address="TP. Hồ Chí Minh"))
                for name, dob, phone, qual, coef, spec, hired, gender in TEACHERS]
    staff = [system.employees.add(Staff(name, dob, phone, gender=gender, position=pos, base_salary=salary,
                                        allowance=allowance, hire_date=hired, address="TP. Hồ Chí Minh"))
             for name, dob, phone, pos, salary, allowance, hired, gender in STAFF]
    prev_m, prev_y = previous_month(today.month, today.year)
    staff[1].set_overtime(prev_m, prev_y, 12)
    staff[1].set_overtime(today.month, today.year, 6)
    staff[0].set_overtime(prev_m, prev_y, 8)

    # ---------------- Tài khoản
    system.create_user("admin", "admin123", Role.ADMIN, "Hiệu trưởng - Quản trị hệ thống")
    system.create_user("ketoan", "ketoan123", Role.ACCOUNTANT, employee_id=staff[3].id)
    for (username, password, _), teacher in zip(DEMO_ACCOUNTS[2:], teachers):
        system.create_user(username, password, Role.TEACHER, employee_id=teacher.id)

    # ---------------- Lớp học
    classes = [system.classes.create_class(name, group, capacity, room, teachers[t].id)
               for name, group, capacity, room, t in CLASSES]

    # ---------------- Phụ huynh
    family_parents: list[list[Parent]] = []
    for index, (father, mother, _poor, address) in enumerate(FAMILIES):
        members = []
        if father:
            members.append(system.parents.add(Parent(
                father[0], date(1984 + index % 9, index % 12 + 1, 5 + index), f"0905{index:02d}1234",
                address=address, occupation=father[1], relationship="Bố")))
        if mother:
            members.append(system.parents.add(Parent(
                mother[0], date(1987 + index % 8, (index + 5) % 12 + 1, 3 + index), f"0906{index:02d}5678",
                address=address, occupation=mother[1], relationship="Mẹ",
                email=f"phuhuynh{index + 1:02d}@example.com")))
        family_parents.append(members)

    # ---------------- Trẻ
    children: list[Child] = []
    for index, (name, gender, (years, months), class_index, family, nickname, services) in enumerate(CHILDREN):
        dob = add_months(today, -(years * 12 + months)) - timedelta(days=rng.randint(0, 20))
        enrolled_on = today - timedelta(days=7) if class_index is None else add_months(today, -8)
        child = Child(name, dob, gender, address=FAMILIES[family][3], nickname=nickname,
                      enrollment_date=max(enrolled_on, dob), is_poor_household=FAMILIES[family][2],
                      extra_services=services)
        if index in PICKUP_PERSONS:
            child.add_pickup_person(PickupPerson(*PICKUP_PERSONS[index]))
        system.children.add(child)
        for parent in family_parents[family]:
            system.parents.link(parent.id, child.id)
        if class_index is not None:
            system.classes.enroll(child.id, classes[class_index].id)
        children.append(child)

    # ---------------- Thời khóa biểu
    for c_index, classroom in enumerate(classes):
        homeroom = teachers[CLASSES[c_index][4]].id
        for day in range(5):
            system.timetable.add_slot(classroom.id, day, "07:30", "08:00", "Đón trẻ - Thể dục sáng", homeroom)
            system.timetable.add_slot(classroom.id, day, "08:00", "08:30", LEARNING[day], homeroom)
            activity, t_index = SPECIAL_LESSONS.get((c_index, day), ("Hoạt động góc", None))
            teacher_id = teachers[t_index].id if t_index is not None else homeroom
            system.timetable.add_slot(classroom.id, day, "09:00", "09:35", activity, teacher_id)
            system.timetable.add_slot(classroom.id, day, "15:00", "15:30", "Vận động - Trò chơi", homeroom)

    # ---------------- Sức khỏe: cân đo 3 tháng gần nhất
    for index, child in enumerate(children):
        factor = WEIGHT_FACTORS.get(index, rng.uniform(0.95, 1.05))
        for back in (3, 2, 1):
            measured = add_months(today, -back)
            if measured < child.dob:
                continue
            months = age_in_months(child.dob, measured)
            height, weight = _ideal_size(months)
            system.health.add_health_record(child.id, measured, round(height + rng.uniform(-2, 2), 1),
                                            round(weight * factor, 1), "Cân đo định kỳ")

    # ---------------- Dị ứng
    for index, allergen, severity, reaction in ALLERGIES:
        system.health.add_allergy(children[index].id, allergen, severity, reaction)

    # ---------------- Điểm danh 2 tháng trước + tháng này (đến hôm qua), có đơn xin nghỉ
    months = [previous_month(*previous_month(today.month, today.year)), (prev_m, prev_y),
              (today.month, today.year)]
    yesterday = today - timedelta(days=1)
    for month, year in months:
        for day in school_days(month, year, until=yesterday):
            for classroom in classes:
                absent = {}
                for child_id in classroom.child_ids:
                    roll = rng.random()
                    if roll < 0.03:
                        absent[child_id] = (AttendanceStatus.UNEXCUSED, "Không báo trước")
                    elif roll < 0.08 and system.attendance.leave_for(child_id, day) is None:
                        system.attendance.record_leave_request(child_id, day, day, rng.choice(LEAVE_REASONS),
                                                               "Phụ huynh báo qua điện thoại")
                # chưa đón = vắng: trẻ đến lớp được ghi rõ 'có mặt', trẻ có đơn để mặc định 'nghỉ có phép'
                statuses = {cid: absent.get(cid, AttendanceStatus.PRESENT) for cid in classroom.child_ids
                            if cid in absent or system.attendance.leave_for(cid, day) is None}
                system.attendance.take_class_attendance(classroom.id, day, statuses)
    # Đơn xin nghỉ cho hôm nay và ngày mai (khi điểm danh hôm nay sẽ tự gợi ý "nghỉ có phép")
    system.attendance.record_leave_request(children[9].id, today, today + timedelta(days=1),
                                           "Gia đình đi du lịch", "Mẹ bé gửi đơn")

    # ---------------- Tài khoản nhân viên và phụ huynh (hệ thống Nhân viên, hệ thống Phụ huynh)
    system.create_user("nv.sau", "nhanvien123", Role.STAFF, employee_id=staff[1].id)
    system.create_user("nv.hung", "nhanvien123", Role.STAFF, employee_id=staff[0].id)
    system.create_user("nv.yen", "nhanvien123", Role.STAFF, employee_id=staff[2].id)
    for username, family in (("ph.mai", 0), ("ph.trang", 1)):
        mother = family_parents[family][-1]
        system.auth.add(User(username=username, role=Role.PARENT, full_name=f"{mother.relationship} {mother.full_name}",
                             password="phuhuynh123", parent_id=mother.id, phone=mother.phone))

    # ---------------- Vận hành hằng ngày của 5 ngày học gần nhất: đón trẻ, nhật ký ăn ngủ, trả trẻ, trao đổi
    recent = [d for d in school_days(*previous_month(today.month, today.year)) + school_days(today.month, today.year)
              if d < today][-5:]
    activities = ["Vẽ tranh gia đình", "Hát múa bài Cháu yêu bà", "Chơi xếp hình", "Kể chuyện Tấm Cám",
                  "Trò chơi vận động ngoài trời", "Làm quen chữ cái a, ă, â"]
    for day in recent:
        for classroom in classes:
            teacher = teachers[CLASSES[classes.index(classroom)][4]]
            for child_id in classroom.child_ids:
                record = system.attendance.get_record(child_id, day)
                if record is None or not record.is_present:
                    continue
                parents = system.parents.parents_of(child_id)
                minute = rng.randint(0, 55)
                record.arrived_at = f"{day.isoformat()}T07:{minute:02d}"
                record.brought_by = f"{parents[0].relationship} {parents[0].full_name}" if parents else "Người nhà"
                record.received_by = teacher.full_name
                record.picked_up_by = record.brought_by
                record.picked_up_at = f"{day.isoformat()}T16:{rng.randint(10, 59):02d}"
                record.released_by = teacher.full_name
                log = system.daily.save_log(
                    child_id, day, meals={m: rng.choice(MEAL_LEVELS[:3]) for m in DAY_MEALS},
                    nap=rng.choice(NAP_LEVELS[:2]), nap_minutes=rng.choice([60, 90, 100, 120]),
                    mood=rng.choice(MOODS[:2]), activities=rng.choice(activities),
                    teacher_note="Bé ngoan, hợp tác với cô và các bạn." if rng.random() < 0.3 else "")
                log.updated_by = teacher.full_name
                log.sent_at = f"{day.isoformat()}T14:{rng.randint(0, 30):02d}"
                if rng.random() < 0.7:
                    log.parent_seen_at = f"{day.isoformat()}T18:{rng.randint(0, 59):02d}"
                    if rng.random() < 0.25:
                        log.parent_reply = rng.choice(["Cảm ơn cô ạ!", "Tối qua bé ngủ muộn, cô để ý giúp em nhé.",
                                                       "Ở nhà bé ăn ít rau, nhờ cô động viên bé ạ."])
                        log.parent_reply_at = f"{day.isoformat()}T19:{rng.randint(0, 59):02d}"
    # Trao đổi phụ huynh: tin cũ đã xử lý + tin hôm nay chờ giáo viên xử lý
    khang, ngoc = children[0], children[1]
    mai = family_parents[0][-1]
    if recent:
        old = system.daily.messages.add(
            _message(MessageKind.MEDICINE, "Bé hơi ho, nhờ cô cho uống sau ăn trưa.", mai, khang, recent[-1],
                     medicine="Siro ho Prospan", dosage="5 ml", time_text="Sau ăn trưa"))
        old.status, old.reply, old.replied_by = MessageStatus.DONE, "Cô đã cho bé uống lúc 11:45.", teachers[0].full_name
        old.done_at = f"{recent[-1].isoformat()}T11:45"
    system.daily.messages.add(_message(MessageKind.NOTE, "Chiều nay ông nội bé sẽ đón bé ạ.", mai, khang, today))
    system.daily.messages.add(_message(MessageKind.MEDICINE, "Bé đang uống kháng sinh, nhờ cô nhắc bé uống.",
                                       family_parents[1][-1], ngoc, today, medicine="Amoxicillin 250mg",
                                       dosage="1 gói", time_text="11:30 sau ăn trưa"))
    announcement = system.daily.messages.add(_message(
        MessageKind.ANNOUNCEMENT, "Thứ Sáu này lớp tổ chức sinh nhật tập thể, phụ huynh cho bé mặc đồ màu vàng ạ.",
        None, None, today, class_id=classes[0].id, sender=teachers[0].full_name))
    announcement.status = MessageStatus.DONE

    # ---------------- Thực đơn: tuần trước, tuần này, tuần sau
    meal_ids = {name: system.menus.add_meal(name, kcal, ingredients).id for name, (kcal, ingredients) in MEALS.items()}
    monday = today - timedelta(days=today.weekday())
    for week_start, plan in ((monday - timedelta(days=7), WEEK_B), (monday, WEEK_A), (monday + timedelta(days=7), WEEK_B)):
        for offset, (breakfast, lunch, snack) in enumerate(plan):
            day = week_start + timedelta(days=offset)
            system.menus.plan_day(day, {MealType.BREAKFAST: [meal_ids[breakfast]],
                                        MealType.LUNCH: [meal_ids[m] for m in lunch],
                                        MealType.SNACK: [meal_ids[m] for m in snack]})

    # ---------------- Học phí: hóa đơn 2 tháng trước (gần như đã thu đủ) và tháng trước (thu dở dang)
    two_m, two_y = months[0]
    issue_two = month_bounds(prev_m, prev_y)[0]           # lập hóa đơn vào ngày 1 tháng sau
    issue_prev = month_bounds(today.month, today.year)[0]
    created_two, _ = system.invoices.generate_monthly_invoices(two_m, two_y, issue_date=issue_two)
    for index, invoice in enumerate(created_two):
        pay_day = min(issue_two + timedelta(days=rng.randint(0, 9)), today)
        if index == 4:
            invoice.add_payment(invoice.total // 2, pay_day, "Tiền mặt", collected_by="ketoan")
        elif index != 9:
            invoice.add_payment(invoice.total, pay_day, rng.choice(["Tiền mặt", "Chuyển khoản"]),
                                collected_by="ketoan")
    created_prev, _ = system.invoices.generate_monthly_invoices(prev_m, prev_y, issue_date=issue_prev)
    for index, invoice in enumerate(created_prev):
        pay_day = min(issue_prev + timedelta(days=rng.randint(0, 8)), today)
        if index % 5 in (0, 1, 2):
            invoice.add_payment(invoice.total, pay_day, rng.choice(["Tiền mặt", "Chuyển khoản"]),
                                collected_by="ketoan")
        elif index % 5 == 3:
            invoice.add_payment(round(invoice.total * 0.5, -3), pay_day, "Chuyển khoản", collected_by="ketoan")

    # ---------------- Sổ tiết dạy bộ môn (GV Âm nhạc, Tiếng Anh): 3 tuần gần nhất, chừa vài tiết chưa ghi
    from kindergarten.teaching.lesson_log import LessonLog
    subject_slots = [s for s in system.timetable if s.teacher_id in (teachers[3].id, teachers[4].id)]
    for back in range(21, 0, -1):
        day = today - timedelta(days=back)
        if not system.calendar.is_school_day(day):
            continue
        for slot in (s for s in subject_slots if s.weekday == day.weekday()):
            if rng.random() < 0.15:   # quên ghi sổ -> báo cáo chuyên môn có tỷ lệ ghi sổ chưa đủ
                continue
            topics = SUBJECT_TOPICS[slot.activity]   # cùng một tuần, GV bộ môn dạy cùng một bài cho các lớp
            topic = topics[day.isocalendar()[1] % len(topics)]
            log = LessonLog(slot.class_id, slot.teacher_id, day, slot.activity, topic,
                            rng.choice(["Tốt", "Tốt", "Khá", "Trung bình"]), slot_id=slot.id,
                            time_text=slot.time_range, created_by=system.employees.get(slot.teacher_id).full_name,
                            updated_at=f"{day.isoformat()}T{slot.end.strftime('%H:%M')}")
            kids = system.classes.class_list(slot.class_id)
            notes = {}
            for kid in rng.sample(kids, k=min(2, len(kids))):
                level = rng.choice(["Nổi bật", "Nổi bật", "Cần hỗ trợ"])
                notes[kid.id] = {"level": level, "comment": rng.choice(CHILD_COMMENTS[level])}
            log.child_notes = notes
            system.lessons.add(log)

    counts = {
        "tài khoản": len(system.auth), "giáo viên": len(teachers), "nhân viên": len(staff),
        "lớp": len(system.classes), "trẻ": len(system.children), "phụ huynh": len(system.parents),
        "tiết học": len(system.timetable), "lần cân đo": len(system.health.records),
        "dị ứng": len(system.health.allergies),
        "điểm danh": len(system.attendance), "đơn xin nghỉ": len(system.attendance.leave_requests),
        "món ăn": len(system.menus.meals), "thực đơn ngày": len(system.menus), "hóa đơn": len(system.invoices),
        "nhật ký ăn ngủ": len(system.daily.logs), "tin nhắn": len(system.daily.messages),
        "tiết dạy bộ môn đã ghi sổ": len(system.lessons),
    }
    if verbose:
        print("Đã nạp dữ liệu mẫu: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return counts


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    from kindergarten.storage.sqlite_store import SQLiteDataStore
    data_dir = Path(__file__).resolve().parent / "data"
    system = KindergartenSystem(data_dir, store=SQLiteDataStore(data_dir))   # file CSDL data/ql_mam_non.db
    if system.store.has_data():   # L02: không ghi đè im lặng dữ liệu thật
        answer = input(f"{getattr(system.store, 'location', data_dir)} ĐÃ CÓ DỮ LIỆU. Thay bằng dữ liệu mẫu? "
                       "(dữ liệu cũ sẽ được sao lưu) [y/N]: ")
        if answer.strip().lower() not in ("y", "yes", "c", "co", "có"):
            print("Đã hủy - dữ liệu hiện có được giữ nguyên.")
            return
        print(f"Đã sao lưu dữ liệu cũ vào {system.store.backup('truoc_khi_nap_mau')}")
    seed(system, verbose=True)
    path = system.save()
    print(f"Đã lưu vào: {path}")
    print("Tài khoản demo: " + ", ".join(f"{u}/{p}" for u, p, _ in DEMO_ACCOUNTS))


if __name__ == "__main__":
    main()
