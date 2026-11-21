# V. KIỂM THỬ

## 1. Quy trình

Theo hướng dẫn: **Project Setup → (Develop, Test & Feedback) lặp lại → Release**. Mỗi vòng:

1. **Develop** - viết / sửa một chức năng.
2. **Test** - chạy toàn bộ kiểm thử tự động (`chay_kiem_thu.bat` hoặc `python -m pytest`) + kiểm thử tay theo danh sách mục 4.
3. **Feedback** - thành viên còn lại / người dùng thử góp ý → ghi vào bảng mục 5 → vòng sau sửa.
4. Chỉ đẩy lên Git (`git push`) khi kiểm thử tự động **đạt 100%** và đã kiểm thử tay phần vừa sửa.

## 2. Các mức kiểm thử

| Mức | Nội dung | Ở đâu |
|---|---|---|
| Đơn vị | từng lớp / manager: tạo, sửa, xóa, kiểm tra dữ liệu sai, quy tắc nghiệp vụ | `tests/test_core.py`, `test_people.py`, `test_classroom.py`, `test_attendance.py`, `test_finance.py`, `test_health.py`, `test_hr.py`, `test_nutrition.py`, `test_auth.py`, `test_reports.py` |
| Tích hợp | hệ thống nhiều phân hệ, quy trình 6 bước trong ngày, báo cáo gửi - duyệt; lưu / đọc CSDL SQLite khớp 100%, giao dịch, khóa ngoại, 2 cửa sổ cùng file | `test_portals_daily.py`, `test_subsystems_reports.py`, `test_review_fixes.py`, `test_sqlite_store.py`, `test_datastore.py`, `test_console.py` |
| Giao diện (khói) | đăng nhập bằng **mọi tài khoản mẫu**, mở **mọi form** của từng phân hệ, khung xem chi tiết, form xóa - không phát sinh lỗi | `test_gui_smoke.py` |
| Chấp nhận (tay) | người dùng thử theo kịch bản | mục 4 |

## 3. Danh sách kiểm thử tự động (sinh tự động)

<!-- TESTS:BEGIN -->
| File | Nội dung | Số test |
|---|---|---:|
| `test_attendance.py` | Kiểm thử AttendanceStatus/AttendanceRecord (T19) và AttendanceManager (T20). | 5 |
| `test_auth.py` | Kiểm thử Role/User (T06) và AuthManager (T07). | 7 |
| `test_classroom.py` | Kiểm thử Classroom (T16), ClassManager (T17), TimeSlot/Timetable (T18). | 4 |
| `test_console.py` | Kiểm thử MainMenu console (T08) chạy từ đầu đến cuối bằng dữ liệu nhập giả lập (T32). | 5 |
| `test_core.py` | Kiểm thử nền tảng: exceptions (T01), BaseModel (T02), BaseManager (T03), Person/Employee (T04), utils (T05). | 8 |
| `test_datastore.py` | Kiểm thử DataStore lưu/đọc JSON (T30) và dữ liệu mẫu (T31). | 4 |
| `test_finance.py` | Kiểm thử Fee (T21), Discount (T22), Invoice/Payment (T23), InvoiceManager (T24). | 8 |
| `test_gui_smoke.py` | Kiểm thử khói giao diện Tkinter: với MỖI tài khoản mẫu (mỗi phân hệ), đăng nhập, mở lần lượt mọi form của phân hệ, | 13 |
| `test_health.py` | Kiểm thử HealthRecord (T12), Vaccination, Allergy, HealthManager (T13). | 4 |
| `test_hr.py` | Kiểm thử Teacher/Staff tính lương đa hình (T14) và EmployeeManager (T15). | 4 |
| `test_nutrition.py` | Kiểm thử Meal/Menu (T25) và MenuManager - cảnh báo dị ứng (T26). | 3 |
| `test_people.py` | Kiểm thử Parent (T09), Child (T10), ChildManager/ParentManager (T11). | 7 |
| `test_portals_daily.py` | Kiểm thử các yêu cầu mới: 5 phân hệ theo vai trò, tự đăng ký tài khoản, vận hành hằng ngày 6 bước, | 9 |
| `test_reports.py` | Kiểm thử Report và các báo cáo (T27), export .txt/.csv (T28), Dashboard (T29). | 5 |
| `test_review_fixes.py` | Kiểm thử hồi quy cho các lỗi trong 'Báo cáo rà soát hệ thống' (mục 8: L01-L27, P01, P03). | 25 |
| `test_sqlite_store.py` | Kiểm thử lưu trữ SQLite - thiết kế CSDL v3 (43 bảng đạt BCNF, file data/ql_mam_non.db). | 13 |
| `test_subsystems_reports.py` | Kiểm thử: phân hệ chỉ giữ chức năng đúng nhiệm vụ; đón trẻ đồng bộ điểm danh; quy trình gửi - duyệt báo cáo. | 5 |
| `test_teaching.py` | GV chủ nhiệm và GV bộ môn có công việc khác nhau; sổ tiết dạy bộ môn (nghiệp vụ riêng của GV bộ môn). | 5 |
| **Tổng** | (chưa tính các lần chạy lặp theo tham số, VD test giao diện chạy cho 12 tài khoản) | **134** |
<!-- TESTS:END -->

## 4. Kịch bản kiểm thử tay

Đăng nhập bằng các tài khoản mẫu (chọn ở ô "Dùng thử nhanh" của màn hình đăng nhập). Đánh dấu ✔ / ✘ vào cột Kết quả.

| # | Tài khoản | Thao tác | Kết quả mong đợi | Kết quả |
|---|---|---|---|---|
| 1 | bất kỳ | Đăng nhập sai mật khẩu 5 lần | Mỗi lần báo "còn ... lần thử"; lần thứ 5: "Sai quá 5 lần, tài khoản tạm khóa 5 phút" | |
| 2 | admin | Quản lý danh mục → Trẻ → **Thêm** trẻ mới, bỏ trống Họ tên → Thực hiện | Báo "'Họ tên' không được để trống", con trỏ về ô Họ tên | |
| 3 | admin | Thêm trẻ đủ thông tin (Giới tính chọn bằng nút tròn) | Message Box "Đã tiếp nhận ... - lớp: ...", trẻ xuất hiện trong lưới | |
| 4 | admin | Chọn trẻ vừa thêm → **Xóa** | Form xóa hiện thông tin trẻ + dòng đỏ "Lưu ý: Bạn có muốn xóa..."; Hủy bỏ → không xóa; Thực hiện → xóa | |
| 5 | admin | Form bất kỳ → **Thoát** | Về màn hình Tổng quan | |
| 6 | admin | Menu trên cùng → Trợ giúp → Sơ đồ chức năng | Hiện cây F1.1 - F1.5 và mã form | |
| 7 | gv.nhung | Vận hành hôm nay → Đón trẻ → Điểm danh → Ăn ngủ → Lập & gửi báo cáo cuối ngày | Mỗi bước cập nhật trạng thái; báo cáo hiện khung toàn trang, chữ bình thường | |
| 8 | admin | Báo cáo nhận được → Duyệt báo cáo vừa gửi | Trạng thái "BGH đã duyệt"; giáo viên thấy ý kiến | |
| 9 | ketoan | Học phí → Tạo hóa đơn cả trường → Thu tiền một hóa đơn | Phiếu thu; Còn nợ giảm đúng số tiền | |
| 10 | nv.hung | Đón - trả trẻ: trả một trẻ đã có mặt cho người KHÔNG có trong danh sách đón | Từ chối: "'...' KHÔNG có trong danh sách được phép đón ... Không giao trẻ, hãy liên hệ phụ huynh!"; ghi nhật ký thao tác | |
| 11 | nv.sau | Thực đơn: lập món có chất trẻ dị ứng | Cảnh báo dị ứng | |
| 12 | ph.mai | Hôm nay của con, Trao đổi với cô → gửi dặn thuốc | Giáo viên thấy tin chờ xử lý | |
| 13 | admin | Hệ thống → Sao lưu, sửa một trẻ, Khôi phục bản vừa sao lưu | Dữ liệu trở lại như lúc sao lưu | |
| 14 | - | Mở 2 cửa sổ chương trình trên cùng file, sửa ở cửa sổ 1 | Cửa sổ 2 tự cập nhật sau vài giây | |
| 15 | - | Mở `data/ql_mam_non.db` bằng DB Browser for SQLite, chạy `Database/03_truy_van_mau.sql` | 15 truy vấn chạy được, số liệu khớp chương trình | |

## 5. Ghi nhận phản hồi (Feedback)

| Ngày | Người thử | Form / chức năng | Vấn đề | Mức độ | Đã sửa (ngày, commit) |
|---|---|---|---|---|---|
| | | | | | |
