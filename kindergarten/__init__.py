"""Hệ thống thông tin quản lý Nhà trẻ - Mẫu giáo (OOP Python).

Các gói con (ánh xạ với danh sách task):
    core        - Nền tảng: BaseModel, BaseManager[T], Person/Employee   (T02-T04)
    auth        - Vai trò, tài khoản, đăng nhập, phân quyền              (T06-T07)
    people      - Trẻ và phụ huynh                                       (T09-T11)
    health      - Cân đo, tiêm chủng, dị ứng                             (T12-T13)
    hr          - Nhân sự, tính lương đa hình                            (T14-T15)
    classroom   - Lớp học, xếp lớp, thời khóa biểu                       (T16-T18)
    attendance  - Điểm danh, đơn xin nghỉ, chuyên cần                    (T19-T20)
    finance     - Học phí, miễn giảm, hóa đơn, công nợ                   (T21-T24)
    nutrition   - Món ăn, thực đơn, cảnh báo dị ứng                      (T25-T26)
    reports     - Báo cáo, xuất file, dashboard                          (T27-T29)
    storage     - Lưu/đọc dữ liệu JSON                                   (T30)
    ui          - Giao diện console (T08) và Tkinter (T34)
Ngoài ra: exceptions.py (T01), utils.py (T05), system.py (ghép các module).
"""

__version__ = "1.0.0"
APP_NAME = "Hệ thống quản lý Nhà trẻ - Mẫu giáo"
