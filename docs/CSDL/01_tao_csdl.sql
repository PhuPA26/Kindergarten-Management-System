-- ====================================================================================================
-- CSDL QUẢN LÝ NHÀ TRẺ - MẪU GIÁO (thiết kế v2) - tự sinh bởi docs/CSDL/sinh_tai_lieu_csdl.py
-- Quy ước tên bảng: SUB_SYSTEM + PURPOSE_TYPE + NAME  (MN = Mầm non; HT = hệ thống, DM = danh mục, NV = nghiệp vụ)
-- CSDL SQLite: file data/ql_mam_non.db. Chương trình TỰ tạo file và các bảng này ở lần chạy đầu -
-- file này chỉ để xem / tạo thủ công (DB Browser for SQLite: New Database > Execute SQL > dán > ▶).
-- ====================================================================================================
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS "MN_HT_VAI_TRO" ( /* Vai trò người dùng - mỗi vai trò là một phân hệ */
  "MA_VAI_TRO" VARCHAR(20) NOT NULL /* Mã vai trò (admin, teacher, accountant, staff, parent) */,
  "TEN_VAI_TRO" VARCHAR(100) NOT NULL /* Tên vai trò */,
  CONSTRAINT "PK_MN_HT_VAI_TRO" PRIMARY KEY ("MA_VAI_TRO")
);

CREATE TABLE IF NOT EXISTS "MN_HT_THAM_SO" ( /* Tham số hệ thống (học phí chung, tiền ăn, tỷ lệ miễn giảm, lương cơ sở...) */
  "MA_THAM_SO" VARCHAR(50) NOT NULL /* Mã tham số */,
  "GIA_TRI" VARCHAR(255) NOT NULL /* Giá trị */,
  "KIEU_DU_LIEU" VARCHAR(10) NOT NULL /* int / float / bool */,
  "MO_TA" VARCHAR(255) /* Ý nghĩa */,
  CONSTRAINT "PK_MN_HT_THAM_SO" PRIMARY KEY ("MA_THAM_SO")
);

CREATE TABLE IF NOT EXISTS "MN_HT_BO_DEM_MA" ( /* Bộ đếm sinh mã tự động (C021, HD039...) - dùng chung cho cả nhóm */
  "TIEN_TO" VARCHAR(10) NOT NULL /* Tiền tố mã (C, PH, HD...) */,
  "GIA_TRI_HIEN_TAI" INT NOT NULL /* Số thứ tự đã cấp gần nhất */,
  CONSTRAINT "PK_MN_HT_BO_DEM_MA" PRIMARY KEY ("TIEN_TO")
);

CREATE TABLE IF NOT EXISTS "MN_HT_PHIEN_BAN" ( /* Phiên bản dữ liệu - phát hiện thay đổi của người dùng khác */
  "MA_PHIEN_BAN" TINYINT NOT NULL /* Luôn = 1 (bảng một dòng) */,
  "SO_PHIEN_BAN" BIGINT NOT NULL DEFAULT 0 /* Tăng 1 sau mỗi lần lưu */,
  "PHIEN_BAN_LUOC_DO" INT NOT NULL /* Phiên bản thiết kế CSDL */,
  "CAP_NHAT_LUC" DATETIME /* Lần lưu gần nhất */,
  "NGUOI_CAP_NHAT" VARCHAR(150) /* Người / máy lưu gần nhất */,
  CONSTRAINT "PK_MN_HT_PHIEN_BAN" PRIMARY KEY ("MA_PHIEN_BAN")
);

CREATE TABLE IF NOT EXISTS "MN_HT_NHAT_KY_THAO_TAC" ( /* Nhật ký thao tác (ai làm gì, lúc nào) */
  "MA_NHAT_KY" INTEGER PRIMARY KEY AUTOINCREMENT /* Mã nhật ký (tự tăng) */,
  "THOI_DIEM" DATETIME NOT NULL /* Thời điểm */,
  "TEN_DANG_NHAP" VARCHAR(50) /* Người thực hiện */,
  "HANH_DONG" VARCHAR(190) NOT NULL /* Hành động */,
  "DOI_TUONG" VARCHAR(500) /* Đối tượng tác động */,
  "CHI_TIET" TEXT /* Chi tiết (JSON) */
);

CREATE TABLE IF NOT EXISTS "MN_DM_KHOI_LOP" ( /* Khối lớp theo độ tuổi (Nhà trẻ, Mầm, Chồi, Lá) */
  "MA_KHOI" VARCHAR(30) NOT NULL /* Mã khối */,
  "TEN_KHOI" VARCHAR(50) NOT NULL /* Tên khối */,
  "TUOI_TU" TINYINT /* Tuổi từ */,
  "TUOI_DEN" TINYINT /* Tuổi đến */,
  "HOC_PHI_RIENG" BIGINT /* Học phí riêng của khối (NULL = dùng học phí chung) */,
  CONSTRAINT "PK_MN_DM_KHOI_LOP" PRIMARY KEY ("MA_KHOI")
);

CREATE TABLE IF NOT EXISTS "MN_DM_DICH_VU" ( /* Dịch vụ tự chọn (năng khiếu, tiếng Anh...) và bảng giá */
  "TEN_DICH_VU" VARCHAR(100) NOT NULL /* Tên dịch vụ (khóa tự nhiên) */,
  "DON_GIA" BIGINT NOT NULL /* Giá mỗi tháng (đồng) */,
  "THU_TU" INT /* Thứ tự hiển thị */,
  CONSTRAINT "PK_MN_DM_DICH_VU" PRIMARY KEY ("TEN_DICH_VU")
);

CREATE TABLE IF NOT EXISTS "MN_DM_NGAY_NGHI" ( /* Lịch năm học - ngày nghỉ lễ */
  "NGAY" DATE NOT NULL /* Ngày nghỉ */,
  "TEN_NGAY_NGHI" VARCHAR(150) NOT NULL /* Tên ngày nghỉ */,
  CONSTRAINT "PK_MN_DM_NGAY_NGHI" PRIMARY KEY ("NGAY")
);

CREATE TABLE IF NOT EXISTS "MN_DM_NHAN_SU" ( /* Nhân sự của trường (thực thể cha của giáo viên / nhân viên) */
  "MA_NHAN_SU" VARCHAR(20) NOT NULL /* Mã nhân sự (Txxx giáo viên, NVxxx nhân viên) */,
  "LOAI_NHAN_SU" VARCHAR(10) NOT NULL /* GIAO_VIEN / NHAN_VIEN */,
  "HO_TEN" VARCHAR(150) NOT NULL /* Họ tên */,
  "NGAY_SINH" DATE /* Ngày sinh */,
  "GIOI_TINH" VARCHAR(10) /* Giới tính */,
  "SO_DIEN_THOAI" VARCHAR(20) /* Số điện thoại */,
  "DIA_CHI" VARCHAR(255) /* Địa chỉ */,
  "CHUC_VU" VARCHAR(50) /* Chức vụ */,
  "NGAY_VAO_LAM" DATE /* Ngày vào làm */,
  CONSTRAINT "PK_MN_DM_NHAN_SU" PRIMARY KEY ("MA_NHAN_SU"),
  CONSTRAINT "CK_MN_DM_NHAN_SU_1" CHECK (LOAI_NHAN_SU IN ('GIAO_VIEN', 'NHAN_VIEN'))
);

CREATE TABLE IF NOT EXISTS "MN_DM_GIAO_VIEN" ( /* Thông tin riêng của giáo viên (quan hệ 1-1 với MN_DM_NHAN_SU) */
  "MA_NHAN_SU" VARCHAR(20) NOT NULL /* Mã giáo viên */,
  "TRINH_DO" VARCHAR(50) /* Trình độ */,
  "HE_SO_LUONG" DECIMAL(5,2) /* Hệ số lương */,
  "CHUYEN_MON" VARCHAR(100) /* Chuyên môn (Âm nhạc, Tiếng Anh...) */,
  CONSTRAINT "PK_MN_DM_GIAO_VIEN" PRIMARY KEY ("MA_NHAN_SU"),
  CONSTRAINT "FK_MN_DM_GIAO_VIEN_1" FOREIGN KEY ("MA_NHAN_SU") REFERENCES "MN_DM_NHAN_SU" ("MA_NHAN_SU") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_DM_NHAN_VIEN" ( /* Thông tin riêng của nhân viên (quan hệ 1-1 với MN_DM_NHAN_SU) */
  "MA_NHAN_SU" VARCHAR(20) NOT NULL /* Mã nhân viên */,
  "LUONG_CO_BAN" BIGINT /* Lương cơ bản (đồng) */,
  "PHU_CAP" BIGINT /* Phụ cấp (đồng) */,
  CONSTRAINT "PK_MN_DM_NHAN_VIEN" PRIMARY KEY ("MA_NHAN_SU"),
  CONSTRAINT "FK_MN_DM_NHAN_VIEN_1" FOREIGN KEY ("MA_NHAN_SU") REFERENCES "MN_DM_NHAN_SU" ("MA_NHAN_SU") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_DM_LOP_HOC" ( /* Lớp học */
  "MA_LOP" VARCHAR(20) NOT NULL /* Mã lớp (Lxxx) */,
  "TEN_LOP" VARCHAR(100) NOT NULL /* Tên lớp */,
  "MA_KHOI" VARCHAR(30) NOT NULL /* Khối lớp */,
  "SI_SO_TOI_DA" INT /* Sĩ số tối đa */,
  "PHONG_HOC" VARCHAR(30) /* Phòng học */,
  "MA_GV_CHU_NHIEM" VARCHAR(20) /* Giáo viên chủ nhiệm (mỗi GV chủ nhiệm tối đa 1 lớp) */,
  CONSTRAINT "PK_MN_DM_LOP_HOC" PRIMARY KEY ("MA_LOP"),
  CONSTRAINT "UQ_MN_DM_LOP_HOC_MA_GV_CHU_NHIEM" UNIQUE ("MA_GV_CHU_NHIEM"),
  CONSTRAINT "FK_MN_DM_LOP_HOC_1" FOREIGN KEY ("MA_KHOI") REFERENCES "MN_DM_KHOI_LOP" ("MA_KHOI") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_DM_LOP_HOC_2" FOREIGN KEY ("MA_GV_CHU_NHIEM") REFERENCES "MN_DM_GIAO_VIEN" ("MA_NHAN_SU") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_DM_PHU_HUYNH" ( /* Phụ huynh */
  "MA_PHU_HUYNH" VARCHAR(20) NOT NULL /* Mã phụ huynh (PHxxx) */,
  "HO_TEN" VARCHAR(150) NOT NULL /* Họ tên */,
  "NGAY_SINH" DATE /* Ngày sinh */,
  "GIOI_TINH" VARCHAR(10) /* Giới tính */,
  "SO_DIEN_THOAI" VARCHAR(20) /* Số điện thoại */,
  "EMAIL" VARCHAR(150) /* Email */,
  "DIA_CHI" VARCHAR(255) /* Địa chỉ */,
  "NGHE_NGHIEP" VARCHAR(100) /* Nghề nghiệp */,
  "QUAN_HE" VARCHAR(30) /* Quan hệ với trẻ (Bố, Mẹ, Ông, Bà...) */,
  CONSTRAINT "PK_MN_DM_PHU_HUYNH" PRIMARY KEY ("MA_PHU_HUYNH")
);

CREATE TABLE IF NOT EXISTS "MN_DM_TRE" ( /* Hồ sơ trẻ */
  "MA_TRE" VARCHAR(20) NOT NULL /* Mã trẻ (Cxxx) */,
  "HO_TEN" VARCHAR(150) NOT NULL /* Họ tên */,
  "TEN_O_NHA" VARCHAR(50) /* Tên ở nhà */,
  "NGAY_SINH" DATE NOT NULL /* Ngày sinh */,
  "GIOI_TINH" VARCHAR(10) /* Giới tính */,
  "SO_DIEN_THOAI" VARCHAR(20) /* Số điện thoại liên hệ */,
  "DIA_CHI" VARCHAR(255) /* Địa chỉ */,
  "MA_LOP" VARCHAR(20) /* Lớp đang học (NULL = chưa xếp lớp) */,
  "NGAY_NHAP_HOC" DATE /* Ngày nhập học */,
  "TRANG_THAI" VARCHAR(30) /* Đang học / Đã nghỉ / Đã ra trường */,
  "NGAY_THOI_HOC" DATE /* Ngày thôi học */,
  "HO_NGHEO" TINYINT(1) NOT NULL DEFAULT 0 /* 1 = hộ nghèo (được miễn giảm) */,
  "GHI_CHU" TEXT /* Ghi chú */,
  CONSTRAINT "PK_MN_DM_TRE" PRIMARY KEY ("MA_TRE"),
  CONSTRAINT "FK_MN_DM_TRE_1" FOREIGN KEY ("MA_LOP") REFERENCES "MN_DM_LOP_HOC" ("MA_LOP") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_DM_TRE_PHU_HUYNH" ( /* Quan hệ n-n giữa trẻ và phụ huynh */
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "MA_PHU_HUYNH" VARCHAR(20) NOT NULL /* Phụ huynh */,
  "THU_TU" INT NOT NULL /* Thứ tự phụ huynh của trẻ */,
  CONSTRAINT "PK_MN_DM_TRE_PHU_HUYNH" PRIMARY KEY ("MA_TRE", "MA_PHU_HUYNH"),
  CONSTRAINT "FK_MN_DM_TRE_PHU_HUYNH_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_DM_TRE_PHU_HUYNH_2" FOREIGN KEY ("MA_PHU_HUYNH") REFERENCES "MN_DM_PHU_HUYNH" ("MA_PHU_HUYNH") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_DM_NGUOI_DON_HO" ( /* Người được phép đón trẻ thay bố mẹ */
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "STT" INT NOT NULL /* Số thứ tự */,
  "HO_TEN" VARCHAR(150) NOT NULL /* Họ tên */,
  "QUAN_HE" VARCHAR(50) /* Quan hệ với trẻ */,
  "SO_DIEN_THOAI" VARCHAR(20) /* Số điện thoại */,
  "SO_CCCD" VARCHAR(20) /* Số CCCD */,
  CONSTRAINT "PK_MN_DM_NGUOI_DON_HO" PRIMARY KEY ("MA_TRE", "STT"),
  CONSTRAINT "FK_MN_DM_NGUOI_DON_HO_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_DM_MON_AN" ( /* Danh mục món ăn */
  "MA_MON" VARCHAR(20) NOT NULL /* Mã món (MAxxx) */,
  "TEN_MON" VARCHAR(150) NOT NULL /* Tên món */,
  "NANG_LUONG_KCAL" INT /* Năng lượng (kcal) */,
  "MO_TA" TEXT /* Mô tả */,
  "DANG_SU_DUNG" TINYINT(1) NOT NULL DEFAULT 1 /* 1 = đang dùng trong thực đơn */,
  CONSTRAINT "PK_MN_DM_MON_AN" PRIMARY KEY ("MA_MON")
);

CREATE TABLE IF NOT EXISTS "MN_DM_THANH_PHAN_MON" ( /* Thành phần (nguyên liệu) của món ăn - dùng cảnh báo dị ứng */
  "MA_MON" VARCHAR(20) NOT NULL /* Món ăn */,
  "STT" INT NOT NULL /* Số thứ tự */,
  "TEN_THANH_PHAN" VARCHAR(100) NOT NULL /* Nguyên liệu */,
  CONSTRAINT "PK_MN_DM_THANH_PHAN_MON" PRIMARY KEY ("MA_MON", "STT"),
  CONSTRAINT "FK_MN_DM_THANH_PHAN_MON_1" FOREIGN KEY ("MA_MON") REFERENCES "MN_DM_MON_AN" ("MA_MON") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_LAM_THEM_GIO" ( /* Số giờ làm thêm của nhân viên theo tháng (tính lương) */
  "MA_NHAN_SU" VARCHAR(20) NOT NULL /* Nhân viên */,
  "KY_LUONG" VARCHAR(10) NOT NULL /* Kỳ lương (yyyy-mm) */,
  "SO_GIO" DECIMAL(6,2) NOT NULL /* Số giờ làm thêm */,
  CONSTRAINT "PK_MN_NV_LAM_THEM_GIO" PRIMARY KEY ("MA_NHAN_SU", "KY_LUONG"),
  CONSTRAINT "FK_MN_NV_LAM_THEM_GIO_1" FOREIGN KEY ("MA_NHAN_SU") REFERENCES "MN_DM_NHAN_SU" ("MA_NHAN_SU") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_DANG_KY_DICH_VU" ( /* Trẻ đăng ký dịch vụ tự chọn (quan hệ n-n trẻ - dịch vụ) */
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "TEN_DICH_VU" VARCHAR(100) NOT NULL /* Dịch vụ */,
  "THU_TU" INT NOT NULL /* Thứ tự */,
  CONSTRAINT "PK_MN_NV_DANG_KY_DICH_VU" PRIMARY KEY ("MA_TRE", "TEN_DICH_VU"),
  CONSTRAINT "FK_MN_NV_DANG_KY_DICH_VU_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_NV_DANG_KY_DICH_VU_2" FOREIGN KEY ("TEN_DICH_VU") REFERENCES "MN_DM_DICH_VU" ("TEN_DICH_VU") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_THOI_KHOA_BIEU" ( /* Thời khóa biểu - các tiết học trong tuần của từng lớp */
  "MA_TIET" VARCHAR(20) NOT NULL /* Mã tiết (TSxxx) */,
  "MA_LOP" VARCHAR(20) NOT NULL /* Lớp */,
  "THU" TINYINT NOT NULL /* Thứ (0 = Thứ Hai ... 6 = Chủ nhật) */,
  "GIO_BAT_DAU" TIME NOT NULL /* Giờ bắt đầu */,
  "GIO_KET_THUC" TIME NOT NULL /* Giờ kết thúc */,
  "HOAT_DONG" VARCHAR(150) NOT NULL /* Hoạt động */,
  "MA_GIAO_VIEN" VARCHAR(20) /* Giáo viên phụ trách */,
  CONSTRAINT "PK_MN_NV_THOI_KHOA_BIEU" PRIMARY KEY ("MA_TIET"),
  CONSTRAINT "FK_MN_NV_THOI_KHOA_BIEU_1" FOREIGN KEY ("MA_LOP") REFERENCES "MN_DM_LOP_HOC" ("MA_LOP") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_NV_THOI_KHOA_BIEU_2" FOREIGN KEY ("MA_GIAO_VIEN") REFERENCES "MN_DM_NHAN_SU" ("MA_NHAN_SU") ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT "CK_MN_NV_THOI_KHOA_BIEU_1" CHECK (THU BETWEEN 0 AND 6)
);

CREATE TABLE IF NOT EXISTS "MN_NV_CAN_DO" ( /* Kết quả cân đo sức khỏe định kỳ */
  "MA_CAN_DO" VARCHAR(20) NOT NULL /* Mã lần đo (SKxxx) */,
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "NGAY_DO" DATE NOT NULL /* Ngày đo */,
  "CHIEU_CAO_CM" DECIMAL(6,2) NOT NULL /* Chiều cao (cm) */,
  "CAN_NANG_KG" DECIMAL(6,2) NOT NULL /* Cân nặng (kg) */,
  "THANG_TUOI" INT /* Tháng tuổi lúc đo */,
  "GHI_CHU" TEXT /* Ghi chú */,
  CONSTRAINT "PK_MN_NV_CAN_DO" PRIMARY KEY ("MA_CAN_DO"),
  CONSTRAINT "FK_MN_NV_CAN_DO_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_DI_UNG" ( /* Thông tin dị ứng của trẻ */
  "MA_DI_UNG" VARCHAR(20) NOT NULL /* Mã (DUxxx) */,
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "CHAT_GAY_DI_UNG" VARCHAR(100) NOT NULL /* Chất gây dị ứng */,
  "MUC_DO" VARCHAR(20) NOT NULL /* MILD / MODERATE / SEVERE */,
  "BIEU_HIEN" TEXT /* Biểu hiện */,
  CONSTRAINT "PK_MN_NV_DI_UNG" PRIMARY KEY ("MA_DI_UNG"),
  CONSTRAINT "FK_MN_NV_DI_UNG_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_DON_XIN_NGHI" ( /* Đơn xin nghỉ của phụ huynh */
  "MA_DON" VARCHAR(20) NOT NULL /* Mã đơn (DNxxx) */,
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "TU_NGAY" DATE NOT NULL /* Nghỉ từ ngày */,
  "DEN_NGAY" DATE NOT NULL /* Đến ngày */,
  "LY_DO" TEXT /* Lý do */,
  "NGUOI_GUI" VARCHAR(150) /* Người gửi đơn */,
  "NGAY_TAO" DATETIME /* Tạo lúc */,
  CONSTRAINT "PK_MN_NV_DON_XIN_NGHI" PRIMARY KEY ("MA_DON"),
  CONSTRAINT "FK_MN_NV_DON_XIN_NGHI_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "CK_MN_NV_DON_XIN_NGHI_1" CHECK (DEN_NGAY >= TU_NGAY)
);

CREATE TABLE IF NOT EXISTS "MN_NV_DON_NGHI_NGAY_DA_DUYET" ( /* Các ngày của đơn nghỉ đã chuyển thành vắng có phép */
  "MA_DON" VARCHAR(20) NOT NULL /* Đơn xin nghỉ */,
  "NGAY" DATE NOT NULL /* Ngày */,
  CONSTRAINT "PK_MN_NV_DON_NGHI_NGAY_DA_DUYET" PRIMARY KEY ("MA_DON", "NGAY"),
  CONSTRAINT "FK_MN_NV_DON_NGHI_NGAY_DA_DUYET_1" FOREIGN KEY ("MA_DON") REFERENCES "MN_NV_DON_XIN_NGHI" ("MA_DON") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_DIEM_DANH" ( /* Điểm danh + đón trẻ đầu ngày + trả trẻ cuối ngày */
  "MA_DIEM_DANH" VARCHAR(20) NOT NULL /* Mã (DDxxx) */,
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "MA_LOP" VARCHAR(20) NOT NULL /* Lớp của trẻ tại ngày điểm danh (lưu lại, không ràng buộc) */,
  "NGAY" DATE NOT NULL /* Ngày */,
  "TRANG_THAI" VARCHAR(20) NOT NULL /* PRESENT / EXCUSED / UNEXCUSED */,
  "GHI_CHU" TEXT /* Ghi chú */,
  "GIO_DEN" DATETIME /* Giờ đến trường */,
  "NGUOI_DUA" VARCHAR(150) /* Người đưa trẻ */,
  "NGUOI_NHAN_TRE" VARCHAR(150) /* Cô nhận trẻ */,
  "GIO_VE" DATETIME /* Giờ về */,
  "NGUOI_DON" VARCHAR(150) /* Người đón */,
  "NGUOI_GIAO_TRE" VARCHAR(150) /* Cô giao trẻ */,
  CONSTRAINT "PK_MN_NV_DIEM_DANH" PRIMARY KEY ("MA_DIEM_DANH"),
  CONSTRAINT "FK_MN_NV_DIEM_DANH_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_HOA_DON" ( /* Hóa đơn học phí hằng tháng (kèm chế độ miễn giảm áp dụng) */
  "MA_HOA_DON" VARCHAR(20) NOT NULL /* Mã hóa đơn (HDxxx) */,
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "THANG" TINYINT NOT NULL /* Tháng */,
  "NAM" SMALLINT NOT NULL /* Năm */,
  "TEN_TRE" VARCHAR(150) /* Tên trẻ tại thời điểm lập */,
  "TEN_LOP" VARCHAR(100) /* Tên lớp tại thời điểm lập */,
  "NGAY_LAP" DATE NOT NULL /* Ngày lập */,
  "HAN_NOP" DATE /* Hạn nộp */,
  "TAM_TINH" TINYINT(1) NOT NULL DEFAULT 0 /* 1 = hóa đơn tạm tính (tháng chưa kết thúc) */,
  "GHI_CHU" TEXT /* Ghi chú */,
  "TEN_MIEN_GIAM" VARCHAR(100) /* Chế độ miễn giảm (NULL = không giảm) */,
  "TY_LE_GIAM" DECIMAL(8,6) /* Tỷ lệ giảm (0 - 1) */,
  "SO_TIEN_GIAM" BIGINT /* Số tiền giảm cố định */,
  "LY_DO_GIAM" VARCHAR(255) /* Lý do miễn giảm */,
  CONSTRAINT "PK_MN_NV_HOA_DON" PRIMARY KEY ("MA_HOA_DON"),
  CONSTRAINT "FK_MN_NV_HOA_DON_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "CK_MN_NV_HOA_DON_1" CHECK (THANG BETWEEN 1 AND 12)
);

CREATE TABLE IF NOT EXISTS "MN_NV_HOA_DON_KHOAN_PHI" ( /* Các khoản phí trong hóa đơn (học phí, tiền ăn, dịch vụ) */
  "MA_HOA_DON" VARCHAR(20) NOT NULL /* Hóa đơn */,
  "STT" INT NOT NULL /* Số thứ tự */,
  "LOAI_PHI" VARCHAR(20) NOT NULL /* MonthlyFee / MealFee / ExtraFee */,
  "TEN_KHOAN" VARCHAR(100) NOT NULL /* Tên khoản phí */,
  "DON_GIA" BIGINT NOT NULL /* Đơn giá (học phí tháng / tiền ăn 1 ngày / giá dịch vụ) */,
  "SO_LUONG" INT /* Số ngày ăn hoặc số lượng (NULL với học phí tháng) */,
  "THANH_TIEN" BIGINT GENERATED ALWAYS AS (DON_GIA * IFNULL(SO_LUONG, 1)) STORED /* = DON_GIA x SO_LUONG (cột tính toán) */,
  CONSTRAINT "PK_MN_NV_HOA_DON_KHOAN_PHI" PRIMARY KEY ("MA_HOA_DON", "STT"),
  CONSTRAINT "FK_MN_NV_HOA_DON_KHOAN_PHI_1" FOREIGN KEY ("MA_HOA_DON") REFERENCES "MN_NV_HOA_DON" ("MA_HOA_DON") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_PHIEU_THU" ( /* Phiếu thu tiền học phí */
  "MA_PHIEU_THU" VARCHAR(20) NOT NULL /* Mã phiếu thu (PTxxx) */,
  "MA_HOA_DON" VARCHAR(20) NOT NULL /* Hóa đơn được thanh toán */,
  "SO_TIEN" BIGINT NOT NULL /* Số tiền */,
  "NGAY_THU" DATE NOT NULL /* Ngày thu */,
  "HINH_THUC" VARCHAR(30) /* Tiền mặt / Chuyển khoản */,
  "GHI_CHU" TEXT /* Ghi chú */,
  "NGUOI_THU" VARCHAR(50) /* Người thu (tài khoản) */,
  "DA_HUY" TINYINT(1) NOT NULL DEFAULT 0 /* 1 = phiếu đã hủy */,
  "LY_DO_HUY" VARCHAR(255) /* Lý do hủy */,
  "NGUOI_HUY" VARCHAR(50) /* Người hủy */,
  "HUY_LUC" DATETIME /* Hủy lúc */,
  CONSTRAINT "PK_MN_NV_PHIEU_THU" PRIMARY KEY ("MA_PHIEU_THU"),
  CONSTRAINT "FK_MN_NV_PHIEU_THU_1" FOREIGN KEY ("MA_HOA_DON") REFERENCES "MN_NV_HOA_DON" ("MA_HOA_DON") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_THUC_DON" ( /* Thực đơn ngày */
  "MA_THUC_DON" VARCHAR(20) NOT NULL /* Mã thực đơn (TDxxx) */,
  "NGAY" DATE NOT NULL /* Ngày */,
  "GHI_CHU" TEXT /* Ghi chú */,
  CONSTRAINT "PK_MN_NV_THUC_DON" PRIMARY KEY ("MA_THUC_DON"),
  CONSTRAINT "UQ_MN_NV_THUC_DON_NGAY" UNIQUE ("NGAY")
);

CREATE TABLE IF NOT EXISTS "MN_NV_THUC_DON_CHI_TIET" ( /* Món ăn theo từng bữa của thực đơn (quan hệ n-n thực đơn - món) */
  "MA_THUC_DON" VARCHAR(20) NOT NULL /* Thực đơn */,
  "BUA_AN" VARCHAR(20) NOT NULL /* BREAKFAST / LUNCH / SNACK */,
  "STT" INT NOT NULL /* Thứ tự món trong bữa */,
  "MA_MON" VARCHAR(20) NOT NULL /* Món ăn */,
  CONSTRAINT "PK_MN_NV_THUC_DON_CHI_TIET" PRIMARY KEY ("MA_THUC_DON", "BUA_AN", "STT"),
  CONSTRAINT "FK_MN_NV_THUC_DON_CHI_TIET_1" FOREIGN KEY ("MA_THUC_DON") REFERENCES "MN_NV_THUC_DON" ("MA_THUC_DON") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_NV_THUC_DON_CHI_TIET_2" FOREIGN KEY ("MA_MON") REFERENCES "MN_DM_MON_AN" ("MA_MON") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_NHAT_KY_TRE" ( /* Nhật ký ăn - ngủ - sinh hoạt hằng ngày gửi phụ huynh */
  "MA_NHAT_KY" VARCHAR(20) NOT NULL /* Mã (NKxxx) */,
  "MA_TRE" VARCHAR(20) NOT NULL /* Trẻ */,
  "MA_LOP" VARCHAR(20) /* Lớp tại ngày ghi (lưu lại, không ràng buộc) */,
  "NGAY" DATE NOT NULL /* Ngày */,
  "GIAC_NGU" VARCHAR(30) /* Giấc ngủ */,
  "SO_PHUT_NGU" INT /* Số phút ngủ trưa */,
  "TAM_TRANG" VARCHAR(30) /* Tâm trạng */,
  "HOAT_DONG" TEXT /* Hoạt động trong ngày */,
  "SUC_KHOE" TEXT /* Ghi chú sức khỏe */,
  "LOI_NHAN_CUA_CO" TEXT /* Lời nhắn của cô */,
  "NGUOI_CAP_NHAT" VARCHAR(150) /* Người cập nhật */,
  "CAP_NHAT_LUC" DATETIME /* Cập nhật lúc */,
  "GUI_PHU_HUYNH_LUC" DATETIME /* Gửi phụ huynh lúc */,
  "PHU_HUYNH_XEM_LUC" DATETIME /* Phụ huynh xem lúc */,
  "PHU_HUYNH_PHAN_HOI" TEXT /* Phụ huynh phản hồi */,
  "PHAN_HOI_LUC" DATETIME /* Phản hồi lúc */,
  CONSTRAINT "PK_MN_NV_NHAT_KY_TRE" PRIMARY KEY ("MA_NHAT_KY"),
  CONSTRAINT "FK_MN_NV_NHAT_KY_TRE_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_NHAT_KY_BUA_AN" ( /* Mức ăn của trẻ theo từng bữa trong nhật ký */
  "MA_NHAT_KY" VARCHAR(20) NOT NULL /* Nhật ký */,
  "STT" INT NOT NULL /* Thứ tự bữa */,
  "BUA_AN" VARCHAR(30) NOT NULL /* Bữa (sáng, trưa, xế) */,
  "MUC_AN" VARCHAR(30) NOT NULL /* Mức ăn (Ăn hết, Ăn khá...) */,
  CONSTRAINT "PK_MN_NV_NHAT_KY_BUA_AN" PRIMARY KEY ("MA_NHAT_KY", "STT"),
  CONSTRAINT "FK_MN_NV_NHAT_KY_BUA_AN_1" FOREIGN KEY ("MA_NHAT_KY") REFERENCES "MN_NV_NHAT_KY_TRE" ("MA_NHAT_KY") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_TIN_NHAN" ( /* Trao đổi giữa phụ huynh và nhà trường (lời nhắn, dặn thuốc, xin nghỉ, thông báo) */
  "MA_TIN_NHAN" VARCHAR(20) NOT NULL /* Mã (TNxxx) */,
  "LOAI_TIN" VARCHAR(20) NOT NULL /* NOTE / MEDICINE / LEAVE / NOTICE... */,
  "MA_TRE" VARCHAR(20) /* Trẻ (NULL = thông báo cả lớp) */,
  "MA_LOP" VARCHAR(20) /* Lớp (lưu lại, không ràng buộc) */,
  "NOI_DUNG" TEXT NOT NULL /* Nội dung */,
  "NGUOI_GUI" VARCHAR(150) /* Người gửi */,
  "VAI_TRO_NGUOI_GUI" VARCHAR(50) /* Vai trò người gửi */,
  "NGAY_AP_DUNG" DATE /* Áp dụng cho ngày */,
  "DEN_NGAY" DATE /* Đến ngày (xin nghỉ nhiều ngày) */,
  "TEN_THUOC" VARCHAR(100) /* Tên thuốc */,
  "LIEU_DUNG" VARCHAR(100) /* Liều dùng */,
  "GIO_UONG" VARCHAR(100) /* Giờ uống */,
  "TRANG_THAI" VARCHAR(30) /* Trạng thái xử lý */,
  "TRA_LOI" TEXT /* Nhà trường trả lời */,
  "NGUOI_TRA_LOI" VARCHAR(150) /* Người trả lời */,
  "TRA_LOI_LUC" DATETIME /* Trả lời lúc */,
  "GUI_LUC" DATETIME /* Gửi lúc */,
  "THUC_HIEN_LUC" DATETIME /* Thực hiện lúc (cho uống thuốc) */,
  "MA_DON_NGHI" VARCHAR(20) /* Đơn xin nghỉ được tạo từ tin nhắn */,
  CONSTRAINT "PK_MN_NV_TIN_NHAN" PRIMARY KEY ("MA_TIN_NHAN"),
  CONSTRAINT "FK_MN_NV_TIN_NHAN_1" FOREIGN KEY ("MA_TRE") REFERENCES "MN_DM_TRE" ("MA_TRE") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_NV_TIN_NHAN_2" FOREIGN KEY ("MA_DON_NGHI") REFERENCES "MN_NV_DON_XIN_NGHI" ("MA_DON") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_BAO_CAO" ( /* Báo cáo các bộ phận gửi Ban giám hiệu và báo cáo toàn trường */
  "MA_BAO_CAO" VARCHAR(20) NOT NULL /* Mã báo cáo (BCxxx) */,
  "LOAI_BAO_CAO" VARCHAR(30) NOT NULL /* Loại (end_of_day, revenue, school_day...) */,
  "NGUOI_LAP" VARCHAR(50) NOT NULL /* Tài khoản người lập */,
  "HO_TEN_NGUOI_LAP" VARCHAR(150) /* Họ tên người lập */,
  "BO_PHAN" VARCHAR(50) /* Bộ phận */,
  "TRANG_THAI" VARCHAR(50) NOT NULL /* Nháp / Đã gửi / Đã duyệt / Yêu cầu bổ sung / Lưu hồ sơ */,
  "GHI_CHU" TEXT /* Ghi chú của người lập */,
  "TAO_LUC" DATETIME /* Tạo lúc */,
  "GUI_LUC" DATETIME /* Gửi lúc */,
  "NGUOI_DUYET" VARCHAR(150) /* Người duyệt (BGH) */,
  "DUYET_LUC" DATETIME /* Duyệt lúc */,
  "Y_KIEN_BGH" TEXT /* Ý kiến Ban giám hiệu */,
  "KY_NGAY" DATE /* Kỳ báo cáo - ngày */,
  "KY_THANG" TINYINT /* Kỳ báo cáo - tháng */,
  "KY_NAM" SMALLINT /* Kỳ báo cáo - năm */,
  "MA_LOP" VARCHAR(20) /* Phạm vi lớp (lưu lại, không ràng buộc) */,
  "TEN_LOP" VARCHAR(255) /* Tên lớp trong phạm vi */,
  "CO_CHON_NGUON" TINYINT(1) NOT NULL DEFAULT 0 /* 1 = báo cáo toàn trường có chọn báo cáo nguồn */,
  "SO_LIEU" TEXT /* Số liệu đã chốt (JSON: tiêu đề, cột, dòng, tổng hợp) - văn bản cố định */,
  CONSTRAINT "PK_MN_NV_BAO_CAO" PRIMARY KEY ("MA_BAO_CAO")
);

CREATE TABLE IF NOT EXISTS "MN_NV_BAO_CAO_NGUON" ( /* Báo cáo bộ phận được đưa vào báo cáo toàn trường (quan hệ n-n) */
  "MA_BAO_CAO" VARCHAR(20) NOT NULL /* Báo cáo toàn trường */,
  "STT" INT NOT NULL /* Thứ tự */,
  "MA_BAO_CAO_NGUON" VARCHAR(20) NOT NULL /* Báo cáo bộ phận */,
  CONSTRAINT "PK_MN_NV_BAO_CAO_NGUON" PRIMARY KEY ("MA_BAO_CAO", "STT"),
  CONSTRAINT "FK_MN_NV_BAO_CAO_NGUON_1" FOREIGN KEY ("MA_BAO_CAO") REFERENCES "MN_NV_BAO_CAO" ("MA_BAO_CAO") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_NV_BAO_CAO_NGUON_2" FOREIGN KEY ("MA_BAO_CAO_NGUON") REFERENCES "MN_NV_BAO_CAO" ("MA_BAO_CAO") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_BAO_CAO_LICH_SU" ( /* Lịch sử xử lý báo cáo (gửi, duyệt, yêu cầu bổ sung) */
  "MA_BAO_CAO" VARCHAR(20) NOT NULL /* Báo cáo */,
  "STT" INT NOT NULL /* Thứ tự */,
  "THOI_DIEM" DATETIME /* Thời điểm */,
  "NGUOI_THUC_HIEN" VARCHAR(150) /* Người thực hiện */,
  "HANH_DONG" VARCHAR(255) /* Hành động */,
  CONSTRAINT "PK_MN_NV_BAO_CAO_LICH_SU" PRIMARY KEY ("MA_BAO_CAO", "STT"),
  CONSTRAINT "FK_MN_NV_BAO_CAO_LICH_SU_1" FOREIGN KEY ("MA_BAO_CAO") REFERENCES "MN_NV_BAO_CAO" ("MA_BAO_CAO") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_NV_BANG_LUONG" ( /* Bảng lương tháng đã chốt */
  "KY_LUONG" VARCHAR(10) NOT NULL /* Kỳ lương (yyyy-mm) */,
  "CHOT_LUC" DATETIME /* Chốt lúc */,
  "NGUOI_CHOT" VARCHAR(150) /* Người chốt */,
  CONSTRAINT "PK_MN_NV_BANG_LUONG" PRIMARY KEY ("KY_LUONG")
);

CREATE TABLE IF NOT EXISTS "MN_NV_BANG_LUONG_CHI_TIET" ( /* Lương từng nhân sự trong bảng lương đã chốt (số liệu cố định) */
  "KY_LUONG" VARCHAR(10) NOT NULL /* Kỳ lương */,
  "STT" INT NOT NULL /* Số thứ tự */,
  "MA_NHAN_SU" VARCHAR(20) NOT NULL /* Nhân sự (lưu lại, không ràng buộc) */,
  "HO_TEN" VARCHAR(150) /* Họ tên */,
  "LOAI" VARCHAR(30) /* Giáo viên / Nhân viên */,
  "CHUC_VU" VARCHAR(100) /* Chức vụ */,
  "THUC_LINH" BIGINT NOT NULL /* Thực lĩnh (đồng) */,
  "CACH_TINH" VARCHAR(255) /* Diễn giải cách tính */,
  CONSTRAINT "PK_MN_NV_BANG_LUONG_CHI_TIET" PRIMARY KEY ("KY_LUONG", "STT"),
  CONSTRAINT "FK_MN_NV_BANG_LUONG_CHI_TIET_1" FOREIGN KEY ("KY_LUONG") REFERENCES "MN_NV_BANG_LUONG" ("KY_LUONG") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "MN_HT_TAI_KHOAN" ( /* Tài khoản đăng nhập */
  "MA_TAI_KHOAN" VARCHAR(20) NOT NULL /* Mã tài khoản (TKxxx) */,
  "TEN_DANG_NHAP" VARCHAR(50) NOT NULL /* Tên đăng nhập */,
  "HO_TEN" VARCHAR(150) NOT NULL /* Họ tên hiển thị */,
  "MA_VAI_TRO" VARCHAR(20) NOT NULL /* Vai trò */,
  "MAT_KHAU_BAM" VARCHAR(255) NOT NULL /* Mật khẩu đã băm (PBKDF2-SHA256) */,
  "MA_NHAN_SU" VARCHAR(20) /* Nhân sự gắn với tài khoản (GV, KT, NV) */,
  "MA_PHU_HUYNH" VARCHAR(20) /* Phụ huynh gắn với tài khoản */,
  "CONG_VIEC" VARCHAR(50) /* Công việc của nhân viên (bếp, bảo vệ, y tế) */,
  "SO_DIEN_THOAI" VARCHAR(20) /* Số điện thoại */,
  "DANG_HOAT_DONG" TINYINT(1) NOT NULL DEFAULT 1 /* 1 = đang hoạt động */,
  "CHO_DUYET" TINYINT(1) NOT NULL DEFAULT 0 /* 1 = tự đăng ký, chờ Ban giám hiệu duyệt */,
  "PHAI_DOI_MAT_KHAU" TINYINT(1) NOT NULL DEFAULT 0 /* 1 = bắt buộc đổi mật khẩu khi đăng nhập */,
  "NGAY_TAO" DATETIME /* Tạo lúc */,
  "LAN_DANG_NHAP_CUOI" DATETIME /* Đăng nhập gần nhất */,
  CONSTRAINT "PK_MN_HT_TAI_KHOAN" PRIMARY KEY ("MA_TAI_KHOAN"),
  CONSTRAINT "UQ_MN_HT_TAI_KHOAN_TEN_DANG_NHAP" UNIQUE ("TEN_DANG_NHAP"),
  CONSTRAINT "FK_MN_HT_TAI_KHOAN_1" FOREIGN KEY ("MA_VAI_TRO") REFERENCES "MN_HT_VAI_TRO" ("MA_VAI_TRO") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_HT_TAI_KHOAN_2" FOREIGN KEY ("MA_NHAN_SU") REFERENCES "MN_DM_NHAN_SU" ("MA_NHAN_SU") ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT "FK_MN_HT_TAI_KHOAN_3" FOREIGN KEY ("MA_PHU_HUYNH") REFERENCES "MN_DM_PHU_HUYNH" ("MA_PHU_HUYNH") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS "IX_MN_HT_NHAT_KY_THAO_TAC_THOI_DIEM" ON "MN_HT_NHAT_KY_THAO_TAC" ("THOI_DIEM");

CREATE INDEX IF NOT EXISTS "IX_MN_HT_NHAT_KY_THAO_TAC_TEN_DANG_NHAP" ON "MN_HT_NHAT_KY_THAO_TAC" ("TEN_DANG_NHAP");

CREATE INDEX IF NOT EXISTS "IX_MN_DM_PHU_HUYNH_SO_DIEN_THOAI" ON "MN_DM_PHU_HUYNH" ("SO_DIEN_THOAI");

CREATE INDEX IF NOT EXISTS "IX_MN_DM_TRE_TRANG_THAI" ON "MN_DM_TRE" ("TRANG_THAI");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_CAN_DO_NGAY_DO" ON "MN_NV_CAN_DO" ("NGAY_DO");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_DIEM_DANH_MA_TRE_NGAY" ON "MN_NV_DIEM_DANH" ("MA_TRE", "NGAY");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_DIEM_DANH_MA_LOP_NGAY" ON "MN_NV_DIEM_DANH" ("MA_LOP", "NGAY");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_DIEM_DANH_NGAY" ON "MN_NV_DIEM_DANH" ("NGAY");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_HOA_DON_NAM_THANG" ON "MN_NV_HOA_DON" ("NAM", "THANG");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_PHIEU_THU_NGAY_THU" ON "MN_NV_PHIEU_THU" ("NGAY_THU");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_NHAT_KY_TRE_MA_TRE_NGAY" ON "MN_NV_NHAT_KY_TRE" ("MA_TRE", "NGAY");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_NHAT_KY_TRE_NGAY" ON "MN_NV_NHAT_KY_TRE" ("NGAY");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_TIN_NHAN_MA_LOP" ON "MN_NV_TIN_NHAN" ("MA_LOP");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_TIN_NHAN_NGAY_AP_DUNG" ON "MN_NV_TIN_NHAN" ("NGAY_AP_DUNG");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_BAO_CAO_NGUOI_LAP" ON "MN_NV_BAO_CAO" ("NGUOI_LAP");

CREATE INDEX IF NOT EXISTS "IX_MN_NV_BAO_CAO_TRANG_THAI" ON "MN_NV_BAO_CAO" ("TRANG_THAI");

INSERT OR IGNORE INTO "MN_HT_PHIEN_BAN" ("MA_PHIEN_BAN", "SO_PHIEN_BAN", "PHIEN_BAN_LUOC_DO") VALUES (1, 0, 2);
