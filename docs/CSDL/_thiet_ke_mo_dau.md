# Thiết kế cơ sở dữ liệu - Hệ thống quản lý Nhà trẻ - Mẫu giáo

> Phần 4 - 6 (sơ đồ ERD, khóa ngoại, từ điển dữ liệu) được **sinh tự động** từ định nghĩa lược đồ trong
> `kindergarten/storage/schema.py` bằng lệnh `python docs/CSDL/sinh_tai_lieu_csdl.py`, nên luôn khớp với
> CSDL mà chương trình tạo ra. Phần 1 - 3 viết tay trong `docs/CSDL/_thiet_ke_mo_dau.md`.
>
> Hệ quản trị CSDL: **SQLite** - toàn bộ CSDL là một file `data/ql_mam_non.db`, không cần cài máy chủ.
> Xem / sửa bảng bằng **DB Browser for SQLite** (mở thẳng file `.db`).

Thiết kế làm theo các bước trong *Hướng dẫn xây dựng HTTTQL* (SAMI - HUST), phần **III. Thiết kế → Thiết kế CSDL**:
liệt kê thực thể cụ thể / trừu tượng → xác định quan hệ 1-1, 1-n, n-n (mô tả thuộc tính của liên kết n-n) →
chuyển sang mô hình quan hệ, chỉ rõ khóa chính, khóa ngoại → xác định thực thể phụ → kiểm tra đủ thuộc tính,
đúng kiểu dữ liệu.

## 1. Quy ước

| Quy ước | Áp dụng |
|---|---|
| Tên CSDL | `ql_mam_non` - file SQLite `data/ql_mam_non.db` (UTF-8, tiếng Việt đầy đủ dấu); bật `PRAGMA foreign_keys = ON` để khóa ngoại có hiệu lực |
| Tên bảng | VIẾT HOA, `SUB_SYSTEM + PURPOSE_TYPE + NAME`: `MN` = phân hệ Mầm non; `HT` = quản trị hệ thống (F1.1), `DM` = thông tin danh mục (F1.2), `NV` = nghiệp vụ (F1.3, F1.4). Ví dụ `MN_DM_TRE`, `MN_NV_HOA_DON` |
| Tên cột | VIẾT HOA, tiếng Việt không dấu: `MA_...` = mã (khóa), `TEN_...`, `NGAY_...`, `SO_...`; mỗi cột có chú thích (COMMENT) |
| Khóa chính | Mã nghiệp vụ dạng chuỗi do chương trình cấp (`C001`, `HD012`...) - dễ đọc trên hóa đơn, phiếu thu; bảng chi tiết dùng khóa ghép (mã cha + `STT`) |
| Khóa ngoại | Đặt tên `FK_<bảng>_<n>`, luôn `ON UPDATE CASCADE`; `ON DELETE` chọn theo nghiệp vụ (xem mục 5) |
| Kiểu dữ liệu | Tiền: `BIGINT` (đồng, không có phần lẻ); tỷ lệ: `DECIMAL(8,6)`; chiều cao / cân nặng: `DECIMAL(6,2)`; đúng/sai: `TINYINT(1)` (0/1); ngày: `DATE` (`yyyy-mm-dd`); thời điểm: `DATETIME` (`yyyy-mm-dd hh:mm:ss`); giờ học: `TIME` (`hh:mm`) |

> SQLite lưu dữ liệu theo "kiểu gần đúng" (type affinity): `DATE`, `DATETIME`, `TIME` được lưu dạng văn bản ISO như
> trên nên sắp xếp, so sánh, dùng hàm `date()`, `strftime()` đúng; chương trình tự đổi qua lại thành ngày giờ.

## 2. Thực thể

**Thực thể cụ thể** (người, vật có thật): Trẻ (`MN_DM_TRE`), Phụ huynh (`MN_DM_PHU_HUYNH`), Nhân sự
(`MN_DM_NHAN_SU`) chuyên biệt hóa thành Giáo viên (`MN_DM_GIAO_VIEN`) và Nhân viên (`MN_DM_NHAN_VIEN`),
Lớp học (`MN_DM_LOP_HOC`), Món ăn (`MN_DM_MON_AN`), Người đón hộ (`MN_DM_NGUOI_DON_HO`), Tài khoản (`MN_HT_TAI_KHOAN`).

**Thực thể trừu tượng** (sự kiện, giao dịch, chứng từ): Điểm danh - đón trả (`MN_NV_DIEM_DANH`), Đơn xin nghỉ
(`MN_NV_DON_XIN_NGHI`), Cân đo (`MN_NV_CAN_DO`), Dị ứng (`MN_NV_DI_UNG`), Thời khóa biểu (`MN_NV_THOI_KHOA_BIEU`),
Hóa đơn (`MN_NV_HOA_DON`) - Khoản phí (`MN_NV_HOA_DON_KHOAN_PHI`) - Phiếu thu (`MN_NV_PHIEU_THU`), Thực đơn
(`MN_NV_THUC_DON`), Nhật ký ăn ngủ (`MN_NV_NHAT_KY_TRE`), Tin nhắn trao đổi (`MN_NV_TIN_NHAN`), Báo cáo
(`MN_NV_BAO_CAO`), Bảng lương đã chốt (`MN_NV_BANG_LUONG`), Giờ làm thêm (`MN_NV_LAM_THEM_GIO`).

**Thực thể phụ** (danh mục nhỏ, tham số): Vai trò (`MN_HT_VAI_TRO`), Khối lớp (`MN_DM_KHOI_LOP`), Dịch vụ tự chọn
(`MN_DM_DICH_VU`), Ngày nghỉ lễ (`MN_DM_NGAY_NGHI`), Tham số hệ thống (`MN_HT_THAM_SO`), Bộ đếm mã
(`MN_HT_BO_DEM_MA`), Phiên bản dữ liệu (`MN_HT_PHIEN_BAN`), Nhật ký thao tác (`MN_HT_NHAT_KY_THAO_TAC`).

## 3. Quan hệ giữa các thực thể

**Quan hệ 1 - 1**
- Nhân sự - Giáo viên, Nhân sự - Nhân viên: chuyên biệt hóa (bảng con dùng chính `MA_NHAN_SU` làm khóa chính).
- Giáo viên - Lớp chủ nhiệm (1 - 0..1): `MN_DM_LOP_HOC.MA_GV_CHU_NHIEM` có ràng buộc `UNIQUE`.
- Tài khoản - Nhân sự, Tài khoản - Phụ huynh (0..1 - 1): tài khoản đăng nhập của giáo viên / kế toán / nhân viên / phụ huynh.

**Quan hệ 1 - n**
- Khối lớp - Lớp học; Lớp học - Trẻ; Lớp học - Tiết học (thời khóa biểu); Vai trò - Tài khoản.
- Trẻ - Điểm danh, Cân đo, Dị ứng, Đơn xin nghỉ, Nhật ký, Tin nhắn, Hóa đơn, Người đón hộ.
- Hóa đơn - Khoản phí, Hóa đơn - Phiếu thu; Món ăn - Thành phần; Nhật ký - Mức ăn từng bữa; Đơn xin nghỉ - Tin nhắn.
- Báo cáo - Lịch sử xử lý; Bảng lương - Chi tiết lương; Nhân viên - Giờ làm thêm.

**Quan hệ n - n** (tách bảng trung gian, kèm thuộc tính của liên kết)

| Quan hệ | Bảng trung gian | Thuộc tính của liên kết |
|---|---|---|
| Trẻ - Phụ huynh | `MN_DM_TRE_PHU_HUYNH` | `THU_TU` (thứ tự liên hệ) |
| Trẻ - Dịch vụ tự chọn | `MN_NV_DANG_KY_DICH_VU` | `THU_TU` |
| Thực đơn - Món ăn | `MN_NV_THUC_DON_CHI_TIET` | `BUA_AN` (sáng / trưa / xế), `STT` |
| Báo cáo toàn trường - Báo cáo bộ phận | `MN_NV_BAO_CAO_NGUON` | `STT` |

**Một số quyết định thiết kế**
- *Dữ liệu lịch sử giữ nguyên giá trị tại thời điểm phát sinh*: hóa đơn lưu `TEN_TRE`, `TEN_LOP`; điểm danh, nhật ký,
  tin nhắn lưu `MA_LOP` của ngày đó (không ràng buộc khóa ngoại - trẻ chuyển lớp hay lớp giải thể thì lịch sử vẫn đúng);
  bảng lương đã chốt và số liệu báo cáo đã gửi (`MN_NV_BAO_CAO.SO_LIEU`) là văn bản cố định, không tính lại.
- *Cột tính toán*: `MN_NV_HOA_DON_KHOAN_PHI.THANH_TIEN = DON_GIA × IFNULL(SO_LUONG, 1)` do SQLite tự tính
  (`GENERATED ALWAYS AS ... STORED`) - truy vấn tổng tiền không cần lặp lại công thức.
- *Ràng buộc kiểm tra (CHECK)*: thứ trong tuần 0 - 6, tháng 1 - 12, ngày kết thúc đơn nghỉ ≥ ngày bắt đầu, loại nhân sự.
- *Xóa dây chuyền có chủ đích*: xóa hồ sơ trẻ (nhập nhầm) thì điểm danh, nhật ký, cân đo... của trẻ đó cũng bị xóa;
  món ăn đang có trong thực đơn, dịch vụ đang có trẻ đăng ký, báo cáo đã được dùng làm nguồn thì **không cho xóa**.
- *Phiên bản dữ liệu*: `MN_HT_PHIEN_BAN` (số phiên bản tăng sau mỗi lần lưu, ai lưu, lúc nào) và `MN_HT_BO_DEM_MA`
  (bộ đếm mã) giúp hai cửa sổ chương trình mở cùng một file không ghi đè dữ liệu của nhau. Cách hai thành viên
  trao đổi dữ liệu: `HUONG_DAN_LAM_VIEC_NHOM.md`.

| Nhóm chức năng (sơ đồ phân cấp chức năng) | Bảng chính |
|---|---|
| F1.1 Quản trị hệ thống | `MN_HT_TAI_KHOAN`, `MN_HT_VAI_TRO`, `MN_HT_THAM_SO`, `MN_HT_NHAT_KY_THAO_TAC` |
| F1.2 Quản lý thông tin danh mục | `MN_DM_TRE`, `MN_DM_PHU_HUYNH`, `MN_DM_NHAN_SU`, `MN_DM_LOP_HOC`, `MN_DM_MON_AN`, `MN_DM_DICH_VU`, `MN_DM_KHOI_LOP`, `MN_DM_NGAY_NGHI` |
| F1.3 Vận hành hằng ngày | `MN_NV_DIEM_DANH`, `MN_NV_NHAT_KY_TRE`, `MN_NV_TIN_NHAN`, `MN_NV_DON_XIN_NGHI`, `MN_NV_THUC_DON`, `MN_NV_CAN_DO`, `MN_NV_THOI_KHOA_BIEU` |
| F1.4 Tài chính - nhân sự | `MN_NV_HOA_DON`, `MN_NV_PHIEU_THU`, `MN_NV_DANG_KY_DICH_VU`, `MN_NV_BANG_LUONG`, `MN_NV_LAM_THEM_GIO` |
| F1.5 Báo cáo thống kê | `MN_NV_BAO_CAO`, `MN_NV_BAO_CAO_NGUON`, `MN_NV_BAO_CAO_LICH_SU` (+ truy vấn mẫu `03_truy_van_mau.sql`) |
