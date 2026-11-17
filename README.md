# Hệ thống thông tin quản lý Nhà trẻ - Mẫu giáo (OOP Python)

Chương trình quản lý một trường mầm non được xây dựng theo đúng **34 task** trong file
`Danh sách task code - HTTTQL Nhà trẻ mẫu giáo (OOP Python).xlsx` (bản đã đánh dấu hoàn thành nằm trong `docs/`).

Chức năng chính: **5 phân hệ** theo tài khoản đăng nhập (Ban giám hiệu, Giáo viên, Kế toán, Nhân viên, Phụ huynh),
tự đăng ký tài khoản, **vận hành hằng ngày 6 bước** (đón trẻ → điểm danh → cập nhật ăn ngủ → tương tác phụ huynh →
trả trẻ → báo cáo cuối ngày), hồ sơ trẻ và phụ huynh, sức khỏe – dị ứng, nhân sự và bảng lương, lớp học – thời khóa biểu,
học phí – miễn giảm – công nợ, danh mục dịch vụ tự chọn, lịch nghỉ lễ, thực đơn có cảnh báo dị ứng, báo cáo xuất file.
Có 2 giao diện: **menu console** và **cửa sổ Tkinter**.

---

## 1. Yêu cầu

- Python **3.10 trở lên** (đã chạy thử với Python 3.11 trên Windows 11).
- CSDL **SQLite** (có sẵn trong Python - không cần cài máy chủ CSDL). Toàn bộ dữ liệu nằm trong file
  `data/ql_mam_non.db`; xem / sửa bảng bằng **DB Browser for SQLite** (<https://sqlitebrowser.org>).
- `pip install -r requirements.txt` (chỉ có `pytest` để chạy kiểm thử). Môi trường `env/` của dự án đã cài sẵn.

### Lần chạy đầu
1. Chạy chương trình (`python main.py --gui` hoặc F5 trong Visual Studio).
2. Chương trình tự tạo file `data/ql_mam_non.db` với 40 bảng (thiết kế: `docs/CSDL/thiet_ke_csdl.md`, câu lệnh:
   `docs/CSDL/01_tao_csdl.sql`). Nếu `data/` có các file JSON cũ, dữ liệu được tự chuyển sang; nếu không, chương trình
   hỏi có nạp dữ liệu mẫu không.
3. **Làm nhóm 2 người**: xem `docs/CSDL/HUONG_DAN_LAM_VIEC_NHOM.md` (mỗi người một file `.db`, trao đổi file khi cần).

## 2. Cách chạy

Mở Command Prompt / PowerShell tại thư mục dự án:

```bash
cd /d D:\HTTTQL_NhaTreMauGiao
```

| Lệnh | Tác dụng |
|---|---|
| `python main.py` | Giao diện **console** (menu theo vai trò đăng nhập) |
| `python main.py --gui` | Giao diện **cửa sổ Tkinter** |
| `python main.py --seed` | Nạp lại **dữ liệu mẫu** rồi chạy - nếu đã có dữ liệu thì **hỏi xác nhận và tự sao lưu** trước |
| `python main.py --seed --yes` | Như trên, không hỏi (dùng trong script) |
| `python seed_data.py` | Chỉ nạp dữ liệu mẫu vào `data/ql_mam_non.db` (cũng hỏi xác nhận + sao lưu) |
| `python main.py --gui --db D:\...\ql_mam_non.db` | Mở một file CSDL khác (VD file bạn cùng nhóm gửi) |
| `python main.py --json` | Chạy bằng file JSON trong `data/` (chế độ cũ, dùng cho kiểm thử) |
| `python -m pytest` | Chạy **116 test** tự động |

Hoặc nhấp đúp các file: `chay_console.bat`, `chay_giao_dien.bat`, `chay_kiem_thu.bat`.

**Lần chạy đầu tiên** (chưa có thư mục `data/`), chương trình hỏi có nạp dữ liệu mẫu không:
20 trẻ, 27 phụ huynh, 5 giáo viên, 4 nhân viên, 3 lớp, thời khóa biểu, 3 tháng điểm danh, cân đo, dị ứng,
thực đơn 3 tuần, hóa đơn 2 tháng, nhật ký ăn ngủ 5 ngày gần nhất, vài tin nhắn/dặn thuốc của phụ huynh hôm nay.
Ngày tháng trong dữ liệu mẫu tính theo **ngày chạy** nên luôn "mới".
Nếu chọn không, hệ thống tạo sẵn tài khoản `admin / admin123` và **bắt buộc đổi mật khẩu** ở lần đăng nhập đầu.

Trong console: nhập `!` để hủy thao tác đang nhập; nhấn Enter để giữ giá trị mặc định hiển thị trong `[ ]`;
khi chọn trẻ/lớp có thể gõ số thứ tự, mã (VD `C001`) hoặc từ khóa không dấu (VD `nguyen`).

## 3. Tài khoản dùng thử (dữ liệu mẫu)

| Tên đăng nhập | Mật khẩu | Phân hệ mở ra sau khi đăng nhập |
|---|---|---|
| `admin` | `admin123` | **Ban giám hiệu** (quyền cao nhất) |
| `ketoan` | `ketoan123` | **Kế toán** |
| `gv.nhung` | `giaovien123` | **Giáo viên** chủ nhiệm lớp Mầm Sơn Ca |
| `gv.ha`, `gv.maianh` | `giaovien123` | Giáo viên chủ nhiệm lớp Chồi Họa Mi, Lá Vành Khuyên |
| `gv.tuan`, `gv.lan` | `giaovien123` | Giáo viên Âm nhạc, Tiếng Anh |
| `nv.sau` | `nhanvien123` | **Nhân viên** cấp dưỡng (thực đơn, món ăn) |
| `nv.hung` | `nhanvien123` | Nhân viên bảo vệ (đón / trả trẻ ở cổng) |
| `nv.yen` | `nhanvien123` | Nhân viên y tế (cân đo, dị ứng) |
| `ph.mai` | `phuhuynh123` | **Phụ huynh**: mẹ bé Nguyễn Minh Khang (lớp Mầm Sơn Ca) |
| `ph.trang` | `phuhuynh123` | Phụ huynh: mẹ bé Lê Bảo Ngọc (lớp Mầm Sơn Ca) |

**Đăng ký tài khoản** (nút *Chưa có tài khoản? Đăng ký* trên màn hình đăng nhập; console gõ `dk` ở ô tên đăng nhập):
- *Phụ huynh*: nhập SĐT đã khai với trường + mã của con (VD `C003`) + ngày sinh của con → dùng được ngay.
- *Giáo viên / Kế toán / Nhân viên*: nhập mã nhân sự (VD `T001`, `NV003`) + SĐT trong hồ sơ → tài khoản ở trạng thái
  **chờ duyệt**, Ban giám hiệu duyệt ở mục *Hệ thống* (GUI) hoặc *Tài khoản & hệ thống → Duyệt tài khoản* (console).

Màn hình đăng nhập chỉ gợi ý những tài khoản **còn dùng đúng mật khẩu mẫu**. Sai mật khẩu 5 lần liên tiếp thì tài khoản
bị khóa tạm 5 phút; tài khoản vừa được quản trị viên đặt lại mật khẩu phải đổi mật khẩu khi đăng nhập.

## 4. Phân quyền theo vai trò

Đăng nhập xong, hệ thống **tự nhận diện tài khoản thuộc phân hệ nào** và mở đúng phân hệ đó (tiêu đề cửa sổ ghi
"Hệ thống Ban giám hiệu", "Hệ thống Giáo viên"...). Trong GUI, menu bên trái chia nhóm *Vận hành hằng ngày*,
*Trẻ - lớp học*, *Bếp - dinh dưỡng*, *Tài chính - nhân sự*, *Quản trị*; phụ huynh chỉ có nhóm *Con của tôi*.

Mỗi phân hệ **chỉ có các màn hình đúng nhiệm vụ** (không hiện chức năng của bộ phận khác):

| Phân hệ | Màn hình có trong phân hệ |
|---|---|
| **Ban giám hiệu** (quyền cao nhất) | Tất cả: vận hành hôm nay, hồ sơ, lớp học, tài chính, thực đơn, **Báo cáo nhận được** (duyệt / yêu cầu bổ sung), tổng quan, lịch năm học, tài khoản & dữ liệu |
| **Giáo viên** (chỉ lớp mình) | Vận hành hôm nay, Đón - trả trẻ, Điểm danh, Ăn ngủ - sinh hoạt, Trao đổi phụ huynh, Trẻ, Phụ huynh, Sức khỏe, Thời khóa biểu, Thực đơn (xem), Lập & gửi báo cáo |
| **Kế toán** | Học phí, Dịch vụ, Nhân sự - bảng lương, Lập & gửi báo cáo (doanh thu, công nợ, bảng lương) |
| **Nhân viên - Bếp** | Thực đơn & món ăn, Lập & gửi báo cáo bếp |
| **Nhân viên - Bảo vệ** | Đón - trả trẻ ở cổng, Lập & gửi báo cáo đón trả |
| **Nhân viên - Y tế** | Sức khỏe (cân đo, dị ứng), Lập & gửi báo cáo y tế |
| **Phụ huynh** (chỉ con mình) | Hôm nay của con, Nhật ký ăn ngủ, Trao đổi với cô, Thực đơn tuần, Học phí & dịch vụ, Sức khỏe & chuyên cần |

Công việc của nhân viên (bếp / bảo vệ / y tế) lấy theo **chức vụ trong hồ sơ nhân sự**, nên tài khoản nhân viên
mở đúng phân hệ con (VD "Hệ thống Nhân viên - Bếp - cấp dưỡng").

Menu (console) và các màn hình (Tkinter) chỉ hiện chức năng của vai trò đang đăng nhập. Quyền còn được kiểm tra ngay trong
**tầng nghiệp vụ** (`BaseManager.write_permission`), nên gọi trực tiếp manager cũng không vượt quyền được.
Tài khoản giáo viên **bắt buộc liên kết hồ sơ giáo viên** và chỉ làm việc với lớp chủ nhiệm + lớp có tiết dạy
(chưa liên kết thì không thấy lớp nào); kế toán không xem thông tin sức khỏe, giáo viên không xem công nợ.

## 5. Cấu trúc thư mục

```
HTTTQL_NhaTreMauGiao/
├── main.py                  T32 - điểm khởi động (console / --gui / --seed)
├── seed_data.py             T31 - dữ liệu mẫu
├── kindergarten/            gói mã nguồn chính
│   ├── exceptions.py        T01 - các lỗi nghiệp vụ
│   ├── utils.py             T05 - kiểm tra SĐT/ngày/tiền, định dạng VNĐ, bảng văn bản
│   ├── system.py            KindergartenSystem: ghép các manager (Facade)
│   ├── core/                T02-T04 - BaseModel, BaseManager[T], Person, Employee
│   ├── auth/                T06-T07 - Role, Permission, User, AuthManager
│   ├── people/              T09-T11 - Parent, Child, ChildManager, ParentManager
│   ├── health/              T12-T13 - HealthRecord, Vaccination, Allergy, HealthManager
│   ├── hr/                  T14-T15 - Teacher, Staff, EmployeeManager
│   ├── classroom/           T16-T18 - Classroom, ClassManager, TimeSlot, Timetable
│   ├── attendance/          T19-T20 - AttendanceStatus, AttendanceRecord, LeaveRequest, AttendanceManager
│   ├── finance/             T21-T24 - Fee..., Discount, Invoice, Payment, InvoiceManager, FeeSettings
│   ├── nutrition/           T25-T26 - Meal, Menu, MenuManager
│   ├── reports/             T27-T29 - Report và các báo cáo, export(), Dashboard
│   ├── storage/             T30 - schema.py (40 bảng), SQLiteDataStore (sqlite_store.py), DataStore (datastore.py, JSON cũ)
│   ├── school_calendar.py   Lịch năm học: ngày nghỉ lễ, học Thứ 7 (dùng chung cho điểm danh/tiền ăn/thực đơn)
│   ├── daily/               Vận hành hằng ngày: DailyLog (ăn ngủ), Message (nhắn/dặn thuốc/xin nghỉ), DailyManager
│   ├── applog.py            Nhật ký lỗi (xoay vòng) và nhật ký thao tác audit.jsonl
│   └── ui/
│       ├── console/         T08 - MainMenu, Menu, ConsoleIO, screens/ (mỗi nhóm nghiệp vụ 1 màn hình)
│       └── gui/             T34 - ứng dụng Tkinter (app.py, tabs_*.py, widgets.py)
├── tests/                   T33 - pytest cho từng manager
├── docs/                    danh sách task; docs/CSDL/ - thiết kế CSDL, câu lệnh tạo bảng, truy vấn mẫu
├── data/                    ql_mam_non.db - file CSDL SQLite; backups/ - các bản sao lưu .zip; file JSON cũ
├── exports/                 (tự tạo) báo cáo xuất ra .txt / .csv
└── logs/                    (tự tạo) error.log khi có lỗi ngoài dự kiến
```

## 6. Ánh xạ danh sách task → mã nguồn

| Mã | Nội dung | File / lớp |
|---|---|---|
| T01 | Lỗi nghiệp vụ | `exceptions.py`: `DuplicateIdError`, `NotFoundError`, `ClassFullError`, `InvalidAgeError`, `PermissionDeniedError` (+ `ValidationError`, `AuthenticationError`, `ScheduleConflictError`, `PaymentError`, `DataStoreError`) |
| T02 | BaseModel | `core/base_model.py`: mã tự sinh theo tiền tố (C001, T001, PH001...), `to_dict()`, `from_dict()` |
| T03 | BaseManager[T] | `core/base_manager.py`: `add`, `update` (hoàn tác nếu lỗi), `remove`, `get`, `find`, `search`, `sort`, sự kiện xóa |
| T04 | Person, Employee | `core/person.py`: `@property` kiểm tra họ tên, ngày sinh, SĐT; tuổi tối thiểu/tối đa |
| T05 | Tiện ích | `utils.py`: `validate_phone`, `parse_date`, `parse_money`, `format_vnd`, `normalize_text` (tìm không dấu)... |
| T06 | Role, User | `auth/user.py`: 5 vai trò (5 phân hệ), bảng quyền `ROLE_PERMISSIONS`, mật khẩu băm PBKDF2 (hashlib) + salt |
| T07 | AuthManager | `auth/auth_manager.py`: `login`, `logout`, `change_password`, `check_permission`, decorator `@require_permission` |
| T08 | MainMenu | `ui/console/main_menu.py` + `menu.py` + `screens/` |
| T09 | Parent | `people/parent.py`: nghề nghiệp, quan hệ, liên kết các con |
| T10 | Child | `people/child.py`: tuổi tự tính, phụ huynh, người đón hộ (`PickupPerson`), từ chối trẻ ngoài 1–6 tuổi |
| T11 | ChildManager, ParentManager | `people/managers.py`: tìm theo tên/lớp/độ tuổi, `children_of()` |
| T12 | HealthRecord | `health/records.py`: `calc_bmi()`, `assess()` → Nhẹ cân / Bình thường / Thừa cân / Béo phì |
| T13 | Allergy, HealthManager | `health/records.py`, `health/health_manager.py`: dị ứng, trẻ cần chú ý dinh dưỡng (đã bỏ tiêm chủng theo yêu cầu) |
| T14 | Teacher, Staff | `hr/employees.py`: mỗi lớp ghi đè `calculate_salary()` |
| T15 | EmployeeManager | `hr/employee_manager.py`: tìm kiếm, bảng lương tháng |
| T16 | Classroom | `classroom/classroom.py`: `add_child()`, `remove_child()`, `assign_teacher()`, kiểm tra sĩ số & độ tuổi |
| T17 | ClassManager | `classroom/class_manager.py`: xếp lớp, chuyển lớp, đổi GVCN, in danh sách lớp |
| T18 | TimeSlot, Timetable | `classroom/timetable.py`: báo lỗi trùng tiết theo lớp hoặc giáo viên |
| T19 | AttendanceStatus, AttendanceRecord | `attendance/records.py` (+ `LeaveRequest` - đơn xin nghỉ) |
| T20 | AttendanceManager | `attendance/attendance_manager.py`: điểm danh cả lớp, đơn xin nghỉ, thống kê tháng, sổ điểm danh |
| T21 | Fee, MonthlyFee, MealFee, ExtraFee | `finance/fees.py`: mỗi loại phí ghi đè `calculate()` |
| T22 | Discount | `finance/discount.py`: hộ nghèo, con thứ hai (mức giảm cấu hình trong `finance/settings.py`) |
| T23 | Invoice, Payment | `finance/invoice.py`: thanh toán một phần/đủ, trạng thái, quá hạn, phiếu báo |
| T24 | InvoiceManager | `finance/invoice_manager.py`: tạo hóa đơn hàng loạt, tra cứu công nợ, danh sách hộ còn nợ |
| T25 | Meal, Menu | `nutrition/meal.py` |
| T26 | MenuManager | `nutrition/menu_manager.py`: thực đơn tuần, sao chép tuần, cảnh báo dị ứng theo lớp |
| T27 | Report | `reports/reports.py`: `EnrollmentReport`, `AttendanceReport`, `RevenueReport`, `DebtReport` (+ `PayrollReport`) |
| T28 | export() | `Report.export()` → `.txt` hoặc `.csv` (UTF-8 có BOM, mở đúng tiếng Việt bằng Excel) |
| T29 | Dashboard | `reports/dashboard.py` |
| T30 | DataStore | `storage/sqlite_store.py`: `save_all()`, `load_all()` với **SQLite** (module `sqlite3`, giao dịch, chỉ ghi đối tượng thay đổi), sao lưu / khôi phục; `storage/schema.py`: 40 bảng + chuyển đối tượng ↔ dòng; `storage/datastore.py`: bản JSON cũ |
| T31 | seed_data.py | `seed_data.py` |
| T32 | main.py | `main.py` + `system.py` |
| T33 | tests/ | `tests/test_*.py` - 116 test (gồm `test_review_fixes.py` cho báo cáo rà soát, `test_portals_daily.py` cho 5 phân hệ và vận hành hằng ngày) |
| T34 | Tkinter (tùy chọn) | `ui/gui/` - 12 tab theo quyền |

## 6b. Vận hành hằng ngày (6 bước)

| Bước | Giờ | Ai làm | Màn hình (GUI) | Hệ thống ghi nhận |
|---|---|---|---|---|
| ① Đón trẻ | 07:00–08:00 | Giáo viên / bảo vệ | *Đón - trả trẻ* | giờ đến, người đưa, người nhận; tự chuyển "có mặt" |
| ② Điểm danh | 08:00–08:30 | Giáo viên | *Điểm danh* | chốt: trẻ chưa đón = vắng (không phép, hoặc có phép nếu có đơn) |
| ③ Cập nhật ăn ngủ | 10:30–14:00 | Giáo viên | *Ăn ngủ - sinh hoạt* | 3 bữa, giấc ngủ, tâm trạng, hoạt động, sức khỏe → **gửi riêng cho phụ huynh từng trẻ** |
| ④ Tương tác phụ huynh | 14:00–15:00 | Giáo viên ↔ phụ huynh | *Trao đổi phụ huynh* / *Trao đổi với cô* | lời nhắn, dặn thuốc (đánh dấu đã cho uống), xin nghỉ (duyệt → tự ghi đơn nghỉ có phép), thông báo lớp |
| ⑤ Trả trẻ | 16:00–17:00 | Giáo viên / bảo vệ | *Đón - trả trẻ* | chỉ giao cho người trong danh sách, ghi giờ đón |
| ⑥ Báo cáo cuối ngày | 17:00–17:30 | Giáo viên → BGH | *Lập & gửi báo cáo* → *Báo cáo nhận được* | giáo viên xem số liệu tự tổng hợp, **thêm ghi chú, gửi BGH**; BGH thấy lớp nào đã gửi / chưa gửi, duyệt hoặc yêu cầu bổ sung |

**Đón trẻ và điểm danh là MỘT trạng thái**: chưa đón = vắng; đón trẻ (hoặc điểm danh "có mặt" tại lớp) = có mặt.
Khi trả trẻ chỉ những trẻ có mặt mới ở lớp nên chỉ những trẻ đó được trả; trẻ vắng hiện mờ "Vắng (không ở lớp)".
Trẻ đến muộn sau khi đã chốt vắng vẫn đón được (chuyển sang có mặt); "Hủy lượt đón nhầm" đưa trẻ về "chưa đến".

**Chọn nhiều trẻ**: các bảng Đón - trả trẻ, Điểm danh, Ăn ngủ có cột ô tích ☐ - bấm ô để tích từng trẻ, bấm ☐ trên tiêu đề
để tích / bỏ tất cả, hoặc nút "Tích tất cả trẻ chưa đến" rồi "Đón các trẻ đã tích".

**Báo cáo theo quy trình**: mỗi bộ phận chỉ lập loại báo cáo của mình (giáo viên: cuối ngày, chuyên cần, đón trả, y tế
của lớp; kế toán: doanh thu, công nợ, bảng lương; bếp: thực đơn tuần; bảo vệ: đón trả; y tế: sức khỏe) → xem trước số liệu →
**ghi chú** → **Gửi Ban giám hiệu** (số liệu được chốt lúc gửi) → BGH **duyệt** hoặc **yêu cầu bổ sung** kèm ý kiến →
người lập cập nhật số liệu, sửa ghi chú và gửi lại. Có thể lưu nháp và xuất file báo cáo đã gửi.

**Ban giám hiệu** (nhóm *Báo cáo*):
- *Báo cáo nhận được*: hàng nút **Duyệt / Yêu cầu bổ sung / Xuất file** nằm ngay dưới thanh lọc (nháy đúp một báo cáo
  để duyệt nhanh); bên dưới là nội dung báo cáo kèm ghi chú của người gửi.
- *Lập báo cáo toàn trường*: chọn **tổng hợp NGÀY** hoặc **THÁNG** → hệ thống tải mọi báo cáo bộ phận đã gửi trong kỳ
  (bỏ tích để loại bớt) → báo cáo chung gồm danh sách báo cáo nguồn + ghi chú của từng bộ phận, trích phần tổng hợp
  của từng báo cáo, số liệu chung của trường (ngày: có mặt/vắng, nhật ký, thuốc, trả trẻ, lớp chưa gửi báo cáo;
  tháng: chuyên cần, học phí, công nợ, quỹ lương) → BGH ghi **kết luận / chỉ đạo** → *Hoàn tất & lưu hồ sơ*, xuất file.

Phụ huynh xem *Hôm nay của con* (giờ đến, điểm danh, ăn ngủ, đã được đón chưa, thực đơn hôm nay), phản hồi nhật ký
("tối qua bé ngủ muộn, nhờ cô để ý"), gửi lời nhắn / dặn thuốc / xin nghỉ, xem học phí và **tự đăng ký dịch vụ** cho con.

**Dịch vụ tự chọn** (mục *Dịch vụ*): Ban giám hiệu/kế toán thêm dịch vụ mới bất kỳ (VD Bơi lội 400.000 đ/tháng), sửa tên/giá,
xóa (tự gỡ đăng ký), đăng ký hàng loạt trẻ. **Lịch năm học** (mục *Lịch năm học*): thêm ngày nghỉ một ngày hoặc cả khoảng
(VD Tết Nguyên đán 5 ngày), thêm nhanh các ngày lễ cố định của một năm, bật/tắt học Thứ 7.

Phần **tiêm chủng đã được bỏ** theo yêu cầu (file `vaccinations.json` cũ, nếu có, được bỏ qua khi đọc).

## 7. Các kỹ thuật OOP được áp dụng

- **Trừu tượng (ABC)**: `BaseModel`, `Person`, `Employee`, `Fee`, `Report` không tạo đối tượng trực tiếp được.
- **Kế thừa**: `Person → Child, Parent, Employee → Teacher, Staff`; `Fee → MonthlyFee, MealFee, ExtraFee`; `Report → 5 báo cáo`.
- **Đa hình**: `calculate_salary()`, `calculate()`, `generate()`, `profile()`, `from_dict()` tự chọn đúng lớp con khi đọc file.
- **Đóng gói**: thuộc tính riêng `_x` + `@property` có kiểm tra; danh sách nội bộ chỉ trả về bản sao.
- **Generic**: `BaseManager[T]` dùng lại cho mọi loại đối tượng.
- **Thành phần (composition)**: `HealthManager` gồm 3 `BaseManager`; `KindergartenSystem` ghép toàn bộ (Facade).
- **Mẫu Observer**: `on_remove` / `on_before_remove` - xóa trẻ thì lớp, phụ huynh, sức khỏe, điểm danh tự cập nhật;
  chặn xóa trẻ còn nợ học phí, lớp còn trẻ, giáo viên đang chủ nhiệm.
- **Decorator**: `@require_permission`; **Enum**: vai trò, quyền, trạng thái điểm danh/hóa đơn, khối lớp, bữa ăn...;
  **dataclass**: `PickupPerson`, `FeeSettings`, `ReportData`, `AllergyWarning`.

## 8. Quy tắc nghiệp vụ chính

- **Mã tự sinh** C001, PH001, T001, NV001, L001, HD001... Mã chỉ được cấp khi lưu thành công nên nhập sai không làm "nhảy số";
  sau khi đọc file, mã tiếp tục tăng (không trùng).
- **Tiếp nhận trẻ** 1–6 tuổi. Lớp chỉ nhận trẻ đúng độ tuổi của khối (Nhà trẻ 1–3, Mầm 3–4, Chồi 4–5, Lá 5–6) và còn chỗ.
  Chuyển lớp kiểm tra lớp mới trước, không hợp lệ thì trẻ vẫn ở lớp cũ.
- **Lương giáo viên** = lương cơ sở 2.340.000 đ × hệ số + ưu đãi nghề 35% + thâm niên (đủ 5 năm: 5%, mỗi năm thêm 1%)
  + phụ cấp chủ nhiệm 500.000 đ. **Lương nhân viên** = lương cơ bản + phụ cấp + giờ làm thêm × (lương cơ bản / 208) × 150%.
  Lương cơ sở, % ưu đãi nghề, phụ cấp chủ nhiệm **chỉnh trong Cấu hình** (không còn là hằng số trong mã).
  Bảng lương tháng có thể **chốt**: kỳ đã chốt giữ nguyên số liệu dù sau đó đổi hệ số/phụ cấp; chỉ tính người đã vào làm.
- **Học phí** = học phí tháng + tiền ăn (số ngày **có mặt thực tế** × đơn giá) + dịch vụ tự chọn − miễn giảm.
  Miễn giảm chỉ áp dụng cho học phí: hộ nghèo 50%, con thứ hai trở đi 20% (lấy mức cao nhất). Các mức đều chỉnh được
  trong menu *Cấu hình học phí* (hiển thị đủ số lẻ, VD 12,5%); có thể đặt học phí riêng theo khối.
  Không lập hóa đơn cho tháng chưa diễn ra; hóa đơn tháng hiện tại là **tạm tính** và có thể *Tính lại* khi hết tháng.
- **Hóa đơn**: thanh toán nhiều lần, không cho nộp vượt số còn nợ; trạng thái tự tính; quá hạn sau 10 ngày (cấu hình được).
  Thu tiền có bước xác nhận và in phiếu thu; phiếu thu ghi nhầm được **hủy có lý do** (giữ dấu vết), không xóa.
  Hóa đơn đã có thanh toán không xóa được. Danh sách công nợ gộp anh chị em (kể cả cùng mẹ khác cha) thành một hộ.
  Số tiền nhập mơ hồ như `2.5` hay `2500.50` bị từ chối thay vì đoán sai.
- **Điểm danh**: mỗi trẻ một bản ghi/ngày; không điểm danh ngày tương lai, cuối tuần, ngày nghỉ lễ (theo *Lịch năm học*)
  hay trước ngày nhập học. Có đơn xin nghỉ thì tự gợi ý "nghỉ có phép" và chuyển các ngày "không phép" đã ghi thành
  "có phép"; hủy đơn nhập nhầm thì trả lại như cũ. **Xác nhận người đón**: chọn người từ danh sách đã đăng ký, trẻ phải
  đã được điểm danh *có mặt*; mỗi lần giao / từ chối đều ghi nhật ký (giờ đón, người giao).
- **Trẻ nghỉ học / ra trường**: dùng *Thôi học* (giữ toàn bộ lịch sử) thay vì xóa; *Kết thúc năm học* cho các lớp lên khối,
  lớp Lá ra trường. Xóa hẳn hồ sơ chỉ dùng cho hồ sơ nhập nhầm.
- **Phụ huynh**: hai hộ khác nhau không dùng chung SĐT (vợ chồng thì được); không xóa / bỏ liên kết phụ huynh cuối cùng
  của trẻ đang học nếu chưa xác nhận; giới tính phải khớp quan hệ (Bố/Mẹ).
- **Thực đơn**: cảnh báo món chứa chất trẻ bị dị ứng, hiểu nhóm chất (dị ứng "hải sản" → cảnh báo tôm, cua...; "đậu phộng" ↔ "lạc");
  so khớp giữ dấu để "cá" không nhầm với "ca cao", và cảnh báo cả khi món ghi tên nhóm ("hải sản tổng hợp").
  Chỉ lập thực đơn cho ngày học. Món đã dùng trong thực đơn không xóa được (để giữ lịch sử) - chỉ **ẩn** khỏi danh sách chọn.
- **Đánh giá dinh dưỡng** dùng ngưỡng BMI theo nhóm tuổi đơn giản hóa từ chuẩn WHO - chỉ mang tính tham khảo.

## 9. Dữ liệu và báo cáo

- Dữ liệu lưu trong CSDL **SQLite** - file `data/ql_mam_non.db` (UTF-8, tiếng Việt đầy đủ), thiết kế theo *Hướng dẫn xây dựng
  HTTTQL*: 40 bảng chuẩn hóa, tên bảng `MN_<HT|DM|NV>_<TÊN>` (HT = quản trị hệ thống, DM = danh mục, NV = nghiệp vụ),
  khóa chính / khóa ngoại / ràng buộc kiểm tra đầy đủ, quan hệ n-n tách bảng trung gian (trẻ - phụ huynh, trẻ - dịch vụ,
  thực đơn - món ăn...). Chi tiết, sơ đồ ERD và từ điển dữ liệu: `docs/CSDL/thiet_ke_csdl.md`; 15 truy vấn mẫu:
  `docs/CSDL/03_truy_van_mau.sql`.

  Ví dụ trong DB Browser for SQLite (thẻ Execute SQL):
  `SELECT HO_TEN, MA_LOP, TRANG_THAI FROM MN_DM_TRE WHERE TRANG_THAI = 'Đang học';`
- Tự lưu sau mỗi thao tác **thành công**: chỉ ghi các đối tượng thay đổi, tất cả trong **một giao dịch** - lỗi giữa
  chừng thì rollback, file CSDL giữ nguyên trạng cũ. Khóa ngoại được bật (`PRAGMA foreign_keys = ON`).
- **Làm nhóm**: mỗi người một file `.db`, trao đổi file khi cần dùng dữ liệu của nhau - xem
  `docs/CSDL/HUONG_DAN_LAM_VIEC_NHOM.md`. Mở 2 cửa sổ chương trình trên cùng file thì mỗi cửa sổ tự nhận thay đổi
  của cửa sổ kia (bảng `MN_HT_PHIEN_BAN`), không ghi đè khi cùng thêm mới trùng mã.
- **Sao lưu** (tab Hệ thống / tự động khi nạp dữ liệu mẫu, khôi phục): xuất mọi bảng ra file `.zip` trong `data/backups/`,
  giữ 10 bản gần nhất + 1 bản mỗi tháng. *Khôi phục* nạp bản `.zip` ngược lại vào CSDL (hiện trạng được sao lưu trước).
- Mã tự sinh được lưu trong bảng `MN_HT_BO_DEM_MA`, nên xóa hồ sơ mã lớn nhất rồi mở lại chương trình cũng không cấp trùng mã.
- **Nhật ký thao tác** (bảng `MN_HT_NHAT_KY_THAO_TAC`): ai thu tiền, hủy phiếu, đổi cấu hình, giao trẻ, xóa hồ sơ... xem trong tab Hệ thống.
- Báo cáo xuất ra `exports/`: file `.txt` dạng bảng hoặc `.csv` mở bằng Excel (số liệu được tính lại ngay khi xuất).
- Lỗi ngoài dự kiến không làm dừng chương trình; chi tiết ghi ở `logs/error.log` (tự xoay vòng, tối đa 5 file × 1 MB).
- Giao diện Tkinter: Ctrl+1..9 chuyển tab, Ctrl+S lưu; bảng bấm tiêu đề cột để sắp xếp; điểm danh tự tải khi đổi lớp/ngày,
  nút ◀ ▶ nhảy ngày học, nháy đúp đổi trạng thái; rời màn hình khi còn điểm danh chưa lưu sẽ được hỏi lại; đổi cỡ chữ ở tab Hệ thống.

## 10. Kiểm thử

```bash
pip install -r requirements.txt
python -m pytest
```

116 test kiểm tra: nền tảng (mã tự sinh, CRUD, kiểm tra dữ liệu), đăng nhập/phân quyền, trẻ & phụ huynh, sức khỏe,
lương đa hình, sĩ số/độ tuổi/chuyển lớp, trùng tiết TKB, điểm danh & đơn nghỉ, học phí/miễn giảm/công nợ,
cảnh báo dị ứng, báo cáo & xuất file, lưu/đọc JSON, và chạy menu console từ đầu đến cuối bằng dữ liệu nhập giả lập.
`tests/test_review_fixes.py` có một test hồi quy cho từng lỗi trong *Báo cáo rà soát hệ thống* (L01–L27, P01, P03).

## 11. Các sửa đổi theo báo cáo rà soát

Báo cáo: `docs/Bao_cao_ra_soat_he_thong.pdf`. Đã sửa toàn bộ 27 lỗi logic L01–L27 và phần lớn các mục K, P, U.
Các mục **chưa làm hoặc làm một phần** (vì đổi kiến trúc lớn, rủi ro cao so với lợi ích ở quy mô một trường):

- **K02** (một nguồn duy nhất cho quan hệ trẻ–lớp–phụ huynh): vẫn lưu hai chiều, có `sync_links()` đồng bộ khi đọc file.
- **K05** (bộ sinh mã riêng cho mỗi hệ thống): vẫn dùng bộ đếm theo lớp, nhưng đã lưu/khôi phục qua `meta.json` (L01).
- **P02** (tách file điểm danh theo tháng / SQLite): chỉ nén bản ghi điểm danh dạng hàng và bỏ thụt lề; chưa đổi sang SQLite.
- **P06** (`__slots__` toàn bộ model): chỉ intern mã trong bản ghi điểm danh.
- **U13** (ô chọn có tìm kiếm trong GUI): chưa làm. **U16** (báo cáo dạng bảng trong GUI): báo cáo vẫn hiển thị dạng văn bản,
  nhưng được tính lại ngay khi xuất file.
