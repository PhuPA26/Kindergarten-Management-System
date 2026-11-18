# III. THIẾT KẾ - Biểu mẫu

Output của bước Thiết kế theo hướng dẫn gồm **TK giao diện**, **TK CSDL** và **TK biểu mẫu**:

| Phần | Ở đâu |
|---|---|
| TK CSDL | `Database/thiet_ke_csdl.md`, `Database/01_tao_csdl.sql` |
| TK giao diện | Chương trình (`kindergarten/ui/gui/`): form danh mục Master - Detail (Bộ lọc, lưới, Thoát / Thêm / Sửa / Xóa; Detail: Thực hiện / Hủy bỏ, form xóa có cảnh báo), form nghiệp vụ có thanh menu + dòng "Người sử dụng - ngày giờ - phiên bản" |
| **TK biểu mẫu** | **Tài liệu này**: các chứng từ, phiếu, báo cáo chương trình in ra / gửi đi |

Mọi biểu mẫu xem được trong chương trình (khung xem có nút ✕, chữ bình thường, bảng thật) và **xuất file**
`.txt` / `.csv` (mở bằng Excel) vào thư mục `exports/`.

## 1. Phiếu báo học phí (hóa đơn tháng)

- **Người dùng:** kế toán lập, phụ huynh nhận. **Form:** `frm021_nv_hoc_phi` (nút Chi tiết), `frm022_nv_hoc_phi_cua_con`.
- **Nguồn dữ liệu:** `MN_NV_HOA_DON`, `MN_NV_HOA_DON_KHOAN_PHI`, `MN_NV_PHIEU_THU`.

| Phần | Nội dung |
|---|---|
| Tiêu đề | PHIẾU BÁO HỌC PHÍ THÁNG mm/yyyy |
| Thông tin chung | Mã hóa đơn, Trẻ (họ tên + mã), Lớp, Kỳ thu, Ngày lập / Hạn nộp, Trạng thái (Chưa thanh toán / Thanh toán một phần / Đã thanh toán; quá hạn nộp thì cảnh báo đỏ) |
| Bảng khoản thu | STT, Khoản thu, Cách tính (VD "20 ngày × 35.000 đ"), Thành tiền |
| Tổng | Cộng, Miễn giảm (VD "-1.250.000 đ (Hộ nghèo: giảm 50% học phí)"), **Tổng phải nộp**, Đã nộp, **Còn nợ** |
| Lịch sử thanh toán | Phiếu thu, Ngày nộp, Hình thức, Số tiền, Người thu, Tình trạng (Hợp lệ / Đã hủy) |

## 2. Phiếu thu học phí

- **Người dùng:** kế toán. **Form:** `frm021_nv_hoc_phi` (nút Thu tiền). **Nguồn:** `MN_NV_PHIEU_THU`, `MN_NV_HOA_DON`.
- **Nội dung:** PHIẾU THU HỌC PHÍ - Phiếu thu (mã), Hóa đơn (mã - tháng), Trẻ, Số tiền, Hình thức (Tiền mặt / Chuyển
  khoản), Ngày nộp, Người thu, **Còn nợ sau khi nộp**. Phiếu thu nhầm được **hủy** (giữ lại, ghi lý do), không xóa.

## 3. Nhật ký ăn ngủ gửi phụ huynh

- **Người dùng:** giáo viên lập, phụ huynh xem và phản hồi. **Form:** `frm011_nv_an_ngu_sinh_hoat`, `frm017_nv_nhat_ky_cua_con`.
- **Nguồn:** `MN_NV_NHAT_KY_TRE`, `MN_NV_NHAT_KY_BUA_AN`.
- **Nội dung:** Ngày; Ăn uống từng bữa (sáng / trưa / xế: ăn hết, ăn khá, ăn ít...); Giấc ngủ + số phút; Tâm trạng;
  Hoạt động; Sức khỏe; Lời nhắn của cô; Gửi lúc; Phụ huynh xem lúc; Phản hồi của phụ huynh.

## 4. Hồ sơ trẻ

- **Form:** `frm002_dm_tre` (Hồ sơ chi tiết). **Nguồn:** `MN_DM_TRE`, `MN_DM_TRE_PHU_HUYNH`, `MN_DM_NGUOI_DON_HO`,
  `MN_NV_DI_UNG`, `MN_NV_CAN_DO`.
- **Nội dung:** Mã, họ tên, giới tính, ngày sinh, tuổi, địa chỉ, tên ở nhà, ngày nhập học, lớp, trạng thái, diện hộ nghèo,
  dịch vụ đăng ký, người đón hộ; bảng Phụ huynh (mã, họ tên, quan hệ, SĐT, nghề nghiệp); dị ứng; lần cân đo gần nhất +
  BMI + đánh giá; công nợ học phí (chỉ kế toán / BGH thấy).

## 5. Sổ điểm danh tháng

- **Form:** `frm010_nv_diem_danh` (Sổ điểm danh tháng). **Nguồn:** `MN_NV_DIEM_DANH`, `MN_DM_NGAY_NGHI`.
- **Nội dung:** Sổ điểm danh lớp ... - tháng mm/yyyy; bảng: Mã, Họ tên, một cột cho mỗi ngày học (C = có mặt,
  P = có phép, K = không phép), cuối bảng 3 cột tổng C / P / K của từng trẻ.

## 6. Các báo cáo gửi Ban giám hiệu (11 loại)

Mỗi báo cáo gồm: **tiêu đề, kỳ, giờ lập**, phần **Tóm tắt** (gạch đầu dòng), bảng **Số liệu chi tiết**, **ghi chú
của người lập**, **ý kiến BGH**, trạng thái (Nháp → Đã gửi → BGH đã duyệt / Yêu cầu bổ sung). Số liệu được **chốt**
lúc gửi (`MN_NV_BAO_CAO.SO_LIEU`). Form lập: `frm024_bc_lap_gui_bao_cao`; nhận / duyệt: `frm025_bc_bao_cao_nhan_duoc`.

| Báo cáo | Kỳ | Bộ phận lập | Cột chính của bảng |
|---|---|---|---|
| Báo cáo cuối ngày của lớp | ngày | giáo viên | Lớp, GV chủ nhiệm, Sĩ số, Đã đón, Có mặt, Vắng, Nhật ký gửi, Thuốc, Tin chờ, Đã trả |
| Báo cáo đón - trả trẻ trong ngày | ngày | bảo vệ, giáo viên | Lớp, Trẻ, Giờ đến, Người đưa, Giờ về, Người đón |
| Báo cáo chuyên cần tháng | tháng | giáo viên | Mã, Họ tên, Lớp, Có mặt, Có phép, Không phép, Tổng ngày, Tỷ lệ |
| Báo cáo y tế - sức khỏe trẻ | đến hôm nay | y tế | Trẻ, Lớp, Ngày đo, Cao, Nặng, BMI, Đánh giá; danh sách dị ứng |
| Báo cáo bếp - thực đơn tuần | tuần | cấp dưỡng | Thứ, Ngày, Bữa sáng / trưa / xế, Kcal; món cần thay cho trẻ dị ứng |
| Báo cáo doanh thu tháng | tháng | kế toán | Lớp, Số HĐ, Học phí, Tiền ăn, Phí khác, Miễn giảm, Phải thu, Đã thu, Còn nợ |
| Báo cáo công nợ | hiện tại | kế toán | STT, Phụ huynh, SĐT, Trẻ, Số HĐ, Kỳ nợ, Còn nợ, Quá hạn |
| Bảng lương tháng | tháng | kế toán | STT, Mã, Họ tên, Loại, Chức vụ, Cách tính, Thực lĩnh |
| Báo cáo sĩ số toàn trường | hiện tại | BGH | Mã, Tên lớp, Khối, Độ tuổi, GV chủ nhiệm, Sĩ số, Tối đa |
| Tổng hợp NGÀY toàn trường | ngày | BGH | báo cáo các bộ phận đưa vào tổng hợp + số liệu chung + kết luận BGH |
| Tổng hợp THÁNG toàn trường | tháng | BGH | như trên, theo tháng (chuyên cần, học phí, công nợ, quỹ lương) |
