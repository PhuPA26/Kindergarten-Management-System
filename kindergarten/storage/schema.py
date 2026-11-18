"""Lược đồ CSDL quan hệ của hệ thống (thiết kế v2, theo "Hướng dẫn xây dựng HTTTQL") và phần chuyển
đối tượng của chương trình <-> dòng trong các bảng. Không phụ thuộc loại CSDL (SQLite dùng ở sqlite_store.py).

- Tên bảng VIẾT HOA theo quy ước SUB_SYSTEM + PURPOSE_TYPE + NAME:
    MN = phân hệ Mầm non; HT = quản trị hệ thống; DM = thông tin danh mục; NV = nghiệp vụ / giao dịch.
- Mỗi thực thể một bảng, có khóa chính; quan hệ 1-n bằng khóa ngoại; quan hệ n-n tách bảng trung gian;
  danh sách lồng nhau (người đón hộ, khoản phí, phiếu thu, món theo bữa...) tách thành bảng chi tiết.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable

from ..exceptions import DataStoreError
from ..finance.settings import FeeSettings
from .datastore import DataStore

if TYPE_CHECKING:
    from ..system import KindergartenSystem

SCHEMA_VERSION = 2
DATABASE_NAME = "ql_mam_non"


# =============================================================================
# Lược đồ CSDL
# =============================================================================
@dataclass
class Col:
    name: str
    sql: str
    comment: str
    null: bool = True
    default: str | None = None
    generated: str | None = None     # biểu thức cột tính toán (STORED)
    auto: bool = False               # khóa tự tăng


@dataclass
class Table:
    name: str
    group: str                        # HT / DM / NV
    comment: str
    cols: list[Col]
    pk: tuple[str, ...]
    fks: list[tuple[tuple[str, ...], str, tuple[str, ...], str]] = field(default_factory=list)  # cột, bảng, cột, ON DELETE
    uniques: list[tuple[str, ...]] = field(default_factory=list)
    indexes: list[tuple[str, ...]] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    @property
    def insert_cols(self) -> list[str]:
        return [c.name for c in self.cols if not c.generated and not c.auto]


def C(name: str, sql: str, comment: str, null: bool = True, default: str | None = None,
      generated: str | None = None, auto: bool = False) -> Col:
    return Col(name, sql, comment, null, default, generated, auto)


MA, TEN, SDT, CHU, DAI = "VARCHAR(20)", "VARCHAR(150)", "VARCHAR(20)", "VARCHAR(255)", "TEXT"
NGAY, THOI_DIEM, GIO, BOOL, TIEN, SO = "DATE", "DATETIME", "TIME", "TINYINT(1)", "BIGINT", "INT"

TABLE_LIST: list[Table] = [
    # ------------------------------------------------------------------ F1.1 QUẢN TRỊ HỆ THỐNG
    Table("MN_HT_VAI_TRO", "HT", "Vai trò người dùng - mỗi vai trò là một phân hệ", [
        C("MA_VAI_TRO", MA, "Mã vai trò (admin, teacher, accountant, staff, parent)", False),
        C("TEN_VAI_TRO", "VARCHAR(100)", "Tên vai trò", False)], ("MA_VAI_TRO",)),
    Table("MN_HT_TAI_KHOAN", "HT", "Tài khoản đăng nhập", [
        C("MA_TAI_KHOAN", MA, "Mã tài khoản (TKxxx)", False),
        C("TEN_DANG_NHAP", "VARCHAR(50)", "Tên đăng nhập", False),
        C("HO_TEN", TEN, "Họ tên hiển thị", False),
        C("MA_VAI_TRO", MA, "Vai trò", False),
        C("MAT_KHAU_BAM", CHU, "Mật khẩu đã băm (PBKDF2-SHA256)", False),
        C("MA_NHAN_SU", MA, "Nhân sự gắn với tài khoản (GV, KT, NV)"),
        C("MA_PHU_HUYNH", MA, "Phụ huynh gắn với tài khoản"),
        C("CONG_VIEC", "VARCHAR(50)", "Công việc của nhân viên (bếp, bảo vệ, y tế)"),
        C("SO_DIEN_THOAI", SDT, "Số điện thoại"),
        C("DANG_HOAT_DONG", BOOL, "1 = đang hoạt động", False, "1"),
        C("CHO_DUYET", BOOL, "1 = tự đăng ký, chờ Ban giám hiệu duyệt", False, "0"),
        C("PHAI_DOI_MAT_KHAU", BOOL, "1 = bắt buộc đổi mật khẩu khi đăng nhập", False, "0"),
        C("NGAY_TAO", THOI_DIEM, "Tạo lúc"),
        C("LAN_DANG_NHAP_CUOI", THOI_DIEM, "Đăng nhập gần nhất")],
        ("MA_TAI_KHOAN",),
        fks=[(("MA_VAI_TRO",), "MN_HT_VAI_TRO", ("MA_VAI_TRO",), "RESTRICT"),
             (("MA_NHAN_SU",), "MN_DM_NHAN_SU", ("MA_NHAN_SU",), "SET NULL"),
             (("MA_PHU_HUYNH",), "MN_DM_PHU_HUYNH", ("MA_PHU_HUYNH",), "SET NULL")],
        uniques=[("TEN_DANG_NHAP",)]),
    Table("MN_HT_THAM_SO", "HT", "Tham số hệ thống (học phí chung, tiền ăn, tỷ lệ miễn giảm, lương cơ sở...)", [
        C("MA_THAM_SO", "VARCHAR(50)", "Mã tham số", False),
        C("GIA_TRI", CHU, "Giá trị", False),
        C("KIEU_DU_LIEU", "VARCHAR(10)", "int / float / bool", False),
        C("MO_TA", CHU, "Ý nghĩa")], ("MA_THAM_SO",)),
    Table("MN_HT_BO_DEM_MA", "HT", "Bộ đếm sinh mã tự động (C021, HD039...) - dùng chung cho cả nhóm", [
        C("TIEN_TO", "VARCHAR(10)", "Tiền tố mã (C, PH, HD...)", False),
        C("GIA_TRI_HIEN_TAI", SO, "Số thứ tự đã cấp gần nhất", False)], ("TIEN_TO",)),
    Table("MN_HT_PHIEN_BAN", "HT", "Phiên bản dữ liệu - phát hiện thay đổi của người dùng khác", [
        C("MA_PHIEN_BAN", "TINYINT", "Luôn = 1 (bảng một dòng)", False),
        C("SO_PHIEN_BAN", TIEN, "Tăng 1 sau mỗi lần lưu", False, "0"),
        C("PHIEN_BAN_LUOC_DO", SO, "Phiên bản thiết kế CSDL", False),
        C("CAP_NHAT_LUC", THOI_DIEM, "Lần lưu gần nhất"),
        C("NGUOI_CAP_NHAT", TEN, "Người / máy lưu gần nhất")], ("MA_PHIEN_BAN",)),
    Table("MN_HT_NHAT_KY_THAO_TAC", "HT", "Nhật ký thao tác (ai làm gì, lúc nào)", [
        C("MA_NHAT_KY", "INTEGER", "Mã nhật ký (tự tăng)", False, auto=True),
        C("THOI_DIEM", THOI_DIEM, "Thời điểm", False),
        C("TEN_DANG_NHAP", "VARCHAR(50)", "Người thực hiện"),
        C("HANH_DONG", "VARCHAR(190)", "Hành động", False),
        C("DOI_TUONG", "VARCHAR(500)", "Đối tượng tác động"),
        C("CHI_TIET", DAI, "Chi tiết (JSON)")], ("MA_NHAT_KY",), indexes=[("THOI_DIEM",), ("TEN_DANG_NHAP",)]),

    # ------------------------------------------------------------------ F1.2 THÔNG TIN DANH MỤC
    Table("MN_DM_KHOI_LOP", "DM", "Khối lớp theo độ tuổi (Nhà trẻ, Mầm, Chồi, Lá)", [
        C("MA_KHOI", "VARCHAR(30)", "Mã khối", False),
        C("TEN_KHOI", "VARCHAR(50)", "Tên khối", False),
        C("TUOI_TU", "TINYINT", "Tuổi từ"),
        C("TUOI_DEN", "TINYINT", "Tuổi đến"),
        C("HOC_PHI_RIENG", TIEN, "Học phí riêng của khối (NULL = dùng học phí chung)")], ("MA_KHOI",)),
    Table("MN_DM_DICH_VU", "DM", "Dịch vụ tự chọn (năng khiếu, tiếng Anh...) và bảng giá", [
        C("TEN_DICH_VU", "VARCHAR(100)", "Tên dịch vụ (khóa tự nhiên)", False),
        C("DON_GIA", TIEN, "Giá mỗi tháng (đồng)", False),
        C("THU_TU", SO, "Thứ tự hiển thị")], ("TEN_DICH_VU",)),
    Table("MN_DM_NGAY_NGHI", "DM", "Lịch năm học - ngày nghỉ lễ", [
        C("NGAY", NGAY, "Ngày nghỉ", False),
        C("TEN_NGAY_NGHI", TEN, "Tên ngày nghỉ", False)], ("NGAY",)),
    Table("MN_DM_NHAN_SU", "DM", "Nhân sự của trường (thực thể cha của giáo viên / nhân viên)", [
        C("MA_NHAN_SU", MA, "Mã nhân sự (Txxx giáo viên, NVxxx nhân viên)", False),
        C("LOAI_NHAN_SU", "VARCHAR(10)", "GIAO_VIEN / NHAN_VIEN", False),
        C("HO_TEN", TEN, "Họ tên", False),
        C("NGAY_SINH", NGAY, "Ngày sinh"),
        C("GIOI_TINH", "VARCHAR(10)", "Giới tính"),
        C("SO_DIEN_THOAI", SDT, "Số điện thoại"),
        C("DIA_CHI", CHU, "Địa chỉ"),
        C("CHUC_VU", "VARCHAR(50)", "Chức vụ"),
        C("NGAY_VAO_LAM", NGAY, "Ngày vào làm")], ("MA_NHAN_SU",),
        checks=["LOAI_NHAN_SU IN ('GIAO_VIEN', 'NHAN_VIEN')"]),
    Table("MN_DM_GIAO_VIEN", "DM", "Thông tin riêng của giáo viên (quan hệ 1-1 với MN_DM_NHAN_SU)", [
        C("MA_NHAN_SU", MA, "Mã giáo viên", False),
        C("TRINH_DO", "VARCHAR(50)", "Trình độ"),
        C("HE_SO_LUONG", "DECIMAL(5,2)", "Hệ số lương"),
        C("CHUYEN_MON", "VARCHAR(100)", "Chuyên môn (Âm nhạc, Tiếng Anh...)")], ("MA_NHAN_SU",),
        fks=[(("MA_NHAN_SU",), "MN_DM_NHAN_SU", ("MA_NHAN_SU",), "CASCADE")]),
    Table("MN_DM_NHAN_VIEN", "DM", "Thông tin riêng của nhân viên (quan hệ 1-1 với MN_DM_NHAN_SU)", [
        C("MA_NHAN_SU", MA, "Mã nhân viên", False),
        C("LUONG_CO_BAN", TIEN, "Lương cơ bản (đồng)"),
        C("PHU_CAP", TIEN, "Phụ cấp (đồng)")], ("MA_NHAN_SU",),
        fks=[(("MA_NHAN_SU",), "MN_DM_NHAN_SU", ("MA_NHAN_SU",), "CASCADE")]),
    Table("MN_DM_LOP_HOC", "DM", "Lớp học", [
        C("MA_LOP", MA, "Mã lớp (Lxxx)", False),
        C("TEN_LOP", "VARCHAR(100)", "Tên lớp", False),
        C("MA_KHOI", "VARCHAR(30)", "Khối lớp", False),
        C("SI_SO_TOI_DA", SO, "Sĩ số tối đa"),
        C("PHONG_HOC", "VARCHAR(30)", "Phòng học"),
        C("MA_GV_CHU_NHIEM", MA, "Giáo viên chủ nhiệm (mỗi GV chủ nhiệm tối đa 1 lớp)")], ("MA_LOP",),
        fks=[(("MA_KHOI",), "MN_DM_KHOI_LOP", ("MA_KHOI",), "RESTRICT"),
             (("MA_GV_CHU_NHIEM",), "MN_DM_GIAO_VIEN", ("MA_NHAN_SU",), "SET NULL")],
        uniques=[("MA_GV_CHU_NHIEM",)]),
    Table("MN_DM_PHU_HUYNH", "DM", "Phụ huynh", [
        C("MA_PHU_HUYNH", MA, "Mã phụ huynh (PHxxx)", False),
        C("HO_TEN", TEN, "Họ tên", False),
        C("NGAY_SINH", NGAY, "Ngày sinh"),
        C("GIOI_TINH", "VARCHAR(10)", "Giới tính"),
        C("SO_DIEN_THOAI", SDT, "Số điện thoại"),
        C("EMAIL", TEN, "Email"),
        C("DIA_CHI", CHU, "Địa chỉ"),
        C("NGHE_NGHIEP", "VARCHAR(100)", "Nghề nghiệp"),
        C("QUAN_HE", "VARCHAR(30)", "Quan hệ với trẻ (Bố, Mẹ, Ông, Bà...)")], ("MA_PHU_HUYNH",),
        indexes=[("SO_DIEN_THOAI",)]),
    Table("MN_DM_TRE", "DM", "Hồ sơ trẻ", [
        C("MA_TRE", MA, "Mã trẻ (Cxxx)", False),
        C("HO_TEN", TEN, "Họ tên", False),
        C("TEN_O_NHA", "VARCHAR(50)", "Tên ở nhà"),
        C("NGAY_SINH", NGAY, "Ngày sinh", False),
        C("GIOI_TINH", "VARCHAR(10)", "Giới tính"),
        C("SO_DIEN_THOAI", SDT, "Số điện thoại liên hệ"),
        C("DIA_CHI", CHU, "Địa chỉ"),
        C("MA_LOP", MA, "Lớp đang học (NULL = chưa xếp lớp)"),
        C("NGAY_NHAP_HOC", NGAY, "Ngày nhập học"),
        C("TRANG_THAI", "VARCHAR(30)", "Đang học / Đã nghỉ / Đã ra trường"),
        C("NGAY_THOI_HOC", NGAY, "Ngày thôi học"),
        C("HO_NGHEO", BOOL, "1 = hộ nghèo (được miễn giảm)", False, "0"),
        C("GHI_CHU", DAI, "Ghi chú")], ("MA_TRE",),
        fks=[(("MA_LOP",), "MN_DM_LOP_HOC", ("MA_LOP",), "SET NULL")], indexes=[("TRANG_THAI",)]),
    Table("MN_DM_TRE_PHU_HUYNH", "DM", "Quan hệ n-n giữa trẻ và phụ huynh", [
        C("MA_TRE", MA, "Trẻ", False),
        C("MA_PHU_HUYNH", MA, "Phụ huynh", False),
        C("THU_TU", SO, "Thứ tự phụ huynh của trẻ", False)], ("MA_TRE", "MA_PHU_HUYNH"),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE"),
             (("MA_PHU_HUYNH",), "MN_DM_PHU_HUYNH", ("MA_PHU_HUYNH",), "CASCADE")]),
    Table("MN_DM_NGUOI_DON_HO", "DM", "Người được phép đón trẻ thay bố mẹ", [
        C("MA_TRE", MA, "Trẻ", False),
        C("STT", SO, "Số thứ tự", False),
        C("HO_TEN", TEN, "Họ tên", False),
        C("QUAN_HE", "VARCHAR(50)", "Quan hệ với trẻ"),
        C("SO_DIEN_THOAI", SDT, "Số điện thoại"),
        C("SO_CCCD", SDT, "Số CCCD")], ("MA_TRE", "STT"),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")]),
    Table("MN_DM_MON_AN", "DM", "Danh mục món ăn", [
        C("MA_MON", MA, "Mã món (MAxxx)", False),
        C("TEN_MON", TEN, "Tên món", False),
        C("NANG_LUONG_KCAL", SO, "Năng lượng (kcal)"),
        C("MO_TA", DAI, "Mô tả"),
        C("DANG_SU_DUNG", BOOL, "1 = đang dùng trong thực đơn", False, "1")], ("MA_MON",)),
    Table("MN_DM_THANH_PHAN_MON", "DM", "Thành phần (nguyên liệu) của món ăn - dùng cảnh báo dị ứng", [
        C("MA_MON", MA, "Món ăn", False),
        C("STT", SO, "Số thứ tự", False),
        C("TEN_THANH_PHAN", "VARCHAR(100)", "Nguyên liệu", False)], ("MA_MON", "STT"),
        fks=[(("MA_MON",), "MN_DM_MON_AN", ("MA_MON",), "CASCADE")]),

    # ------------------------------------------------------------------ F1.3 - F1.4 NGHIỆP VỤ
    Table("MN_NV_LAM_THEM_GIO", "NV", "Số giờ làm thêm của nhân viên theo tháng (tính lương)", [
        C("MA_NHAN_SU", MA, "Nhân viên", False),
        C("KY_LUONG", "VARCHAR(10)", "Kỳ lương (yyyy-mm)", False),
        C("SO_GIO", "DECIMAL(6,2)", "Số giờ làm thêm", False)], ("MA_NHAN_SU", "KY_LUONG"),
        fks=[(("MA_NHAN_SU",), "MN_DM_NHAN_SU", ("MA_NHAN_SU",), "CASCADE")]),
    Table("MN_NV_DANG_KY_DICH_VU", "NV", "Trẻ đăng ký dịch vụ tự chọn (quan hệ n-n trẻ - dịch vụ)", [
        C("MA_TRE", MA, "Trẻ", False),
        C("TEN_DICH_VU", "VARCHAR(100)", "Dịch vụ", False),
        C("THU_TU", SO, "Thứ tự", False)], ("MA_TRE", "TEN_DICH_VU"),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE"),
             (("TEN_DICH_VU",), "MN_DM_DICH_VU", ("TEN_DICH_VU",), "RESTRICT")]),
    Table("MN_NV_THOI_KHOA_BIEU", "NV", "Thời khóa biểu - các tiết học trong tuần của từng lớp", [
        C("MA_TIET", MA, "Mã tiết (TSxxx)", False),
        C("MA_LOP", MA, "Lớp", False),
        C("THU", "TINYINT", "Thứ (0 = Thứ Hai ... 6 = Chủ nhật)", False),
        C("GIO_BAT_DAU", GIO, "Giờ bắt đầu", False),
        C("GIO_KET_THUC", GIO, "Giờ kết thúc", False),
        C("HOAT_DONG", TEN, "Hoạt động", False),
        C("MA_GIAO_VIEN", MA, "Giáo viên phụ trách")], ("MA_TIET",),
        fks=[(("MA_LOP",), "MN_DM_LOP_HOC", ("MA_LOP",), "CASCADE"),
             (("MA_GIAO_VIEN",), "MN_DM_NHAN_SU", ("MA_NHAN_SU",), "SET NULL")],
        checks=["THU BETWEEN 0 AND 6"]),
    Table("MN_NV_CAN_DO", "NV", "Kết quả cân đo sức khỏe định kỳ", [
        C("MA_CAN_DO", MA, "Mã lần đo (SKxxx)", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("NGAY_DO", NGAY, "Ngày đo", False),
        C("CHIEU_CAO_CM", "DECIMAL(6,2)", "Chiều cao (cm)", False),
        C("CAN_NANG_KG", "DECIMAL(6,2)", "Cân nặng (kg)", False),
        C("THANG_TUOI", SO, "Tháng tuổi lúc đo"),
        C("GHI_CHU", DAI, "Ghi chú")], ("MA_CAN_DO",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")], indexes=[("NGAY_DO",)]),
    Table("MN_NV_DI_UNG", "NV", "Thông tin dị ứng của trẻ", [
        C("MA_DI_UNG", MA, "Mã (DUxxx)", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("CHAT_GAY_DI_UNG", "VARCHAR(100)", "Chất gây dị ứng", False),
        C("MUC_DO", "VARCHAR(20)", "MILD / MODERATE / SEVERE", False),
        C("BIEU_HIEN", DAI, "Biểu hiện")], ("MA_DI_UNG",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")]),
    Table("MN_NV_DON_XIN_NGHI", "NV", "Đơn xin nghỉ của phụ huynh", [
        C("MA_DON", MA, "Mã đơn (DNxxx)", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("TU_NGAY", NGAY, "Nghỉ từ ngày", False),
        C("DEN_NGAY", NGAY, "Đến ngày", False),
        C("LY_DO", DAI, "Lý do"),
        C("NGUOI_GUI", TEN, "Người gửi đơn"),
        C("NGAY_TAO", THOI_DIEM, "Tạo lúc")], ("MA_DON",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")], checks=["DEN_NGAY >= TU_NGAY"]),
    Table("MN_NV_DON_NGHI_NGAY_DA_DUYET", "NV", "Các ngày của đơn nghỉ đã chuyển thành vắng có phép", [
        C("MA_DON", MA, "Đơn xin nghỉ", False),
        C("NGAY", NGAY, "Ngày", False)], ("MA_DON", "NGAY"),
        fks=[(("MA_DON",), "MN_NV_DON_XIN_NGHI", ("MA_DON",), "CASCADE")]),
    Table("MN_NV_DIEM_DANH", "NV", "Điểm danh + đón trẻ đầu ngày + trả trẻ cuối ngày", [
        C("MA_DIEM_DANH", MA, "Mã (DDxxx)", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("MA_LOP", MA, "Lớp của trẻ tại ngày điểm danh (lưu lại, không ràng buộc)", False),
        C("NGAY", NGAY, "Ngày", False),
        C("TRANG_THAI", "VARCHAR(20)", "PRESENT / EXCUSED / UNEXCUSED", False),
        C("GHI_CHU", DAI, "Ghi chú"),
        C("GIO_DEN", THOI_DIEM, "Giờ đến trường"),
        C("NGUOI_DUA", TEN, "Người đưa trẻ"),
        C("NGUOI_NHAN_TRE", TEN, "Cô nhận trẻ"),
        C("GIO_VE", THOI_DIEM, "Giờ về"),
        C("NGUOI_DON", TEN, "Người đón"),
        C("NGUOI_GIAO_TRE", TEN, "Cô giao trẻ")], ("MA_DIEM_DANH",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")],
        indexes=[("MA_TRE", "NGAY"), ("MA_LOP", "NGAY"), ("NGAY",)]),
    Table("MN_NV_HOA_DON", "NV", "Hóa đơn học phí hằng tháng (kèm chế độ miễn giảm áp dụng)", [
        C("MA_HOA_DON", MA, "Mã hóa đơn (HDxxx)", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("THANG", "TINYINT", "Tháng", False),
        C("NAM", "SMALLINT", "Năm", False),
        C("TEN_TRE", TEN, "Tên trẻ tại thời điểm lập"),
        C("TEN_LOP", "VARCHAR(100)", "Tên lớp tại thời điểm lập"),
        C("NGAY_LAP", NGAY, "Ngày lập", False),
        C("HAN_NOP", NGAY, "Hạn nộp"),
        C("TAM_TINH", BOOL, "1 = hóa đơn tạm tính (tháng chưa kết thúc)", False, "0"),
        C("GHI_CHU", DAI, "Ghi chú"),
        C("TEN_MIEN_GIAM", "VARCHAR(100)", "Chế độ miễn giảm (NULL = không giảm)"),
        C("TY_LE_GIAM", "DECIMAL(8,6)", "Tỷ lệ giảm (0 - 1)"),
        C("SO_TIEN_GIAM", TIEN, "Số tiền giảm cố định"),
        C("LY_DO_GIAM", CHU, "Lý do miễn giảm")], ("MA_HOA_DON",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")], indexes=[("NAM", "THANG")],
        checks=["THANG BETWEEN 1 AND 12"]),
    Table("MN_NV_HOA_DON_KHOAN_PHI", "NV", "Các khoản phí trong hóa đơn (học phí, tiền ăn, dịch vụ)", [
        C("MA_HOA_DON", MA, "Hóa đơn", False),
        C("STT", SO, "Số thứ tự", False),
        C("LOAI_PHI", "VARCHAR(20)", "MonthlyFee / MealFee / ExtraFee", False),
        C("TEN_KHOAN", "VARCHAR(100)", "Tên khoản phí", False),
        C("DON_GIA", TIEN, "Đơn giá (học phí tháng / tiền ăn 1 ngày / giá dịch vụ)", False),
        C("SO_LUONG", SO, "Số ngày ăn hoặc số lượng (NULL với học phí tháng)"),
        C("THANH_TIEN", TIEN, "= DON_GIA x SO_LUONG (cột tính toán)",
          generated="DON_GIA * IFNULL(SO_LUONG, 1)")], ("MA_HOA_DON", "STT"),
        fks=[(("MA_HOA_DON",), "MN_NV_HOA_DON", ("MA_HOA_DON",), "CASCADE")]),
    Table("MN_NV_PHIEU_THU", "NV", "Phiếu thu tiền học phí", [
        C("MA_PHIEU_THU", MA, "Mã phiếu thu (PTxxx)", False),
        C("MA_HOA_DON", MA, "Hóa đơn được thanh toán", False),
        C("SO_TIEN", TIEN, "Số tiền", False),
        C("NGAY_THU", NGAY, "Ngày thu", False),
        C("HINH_THUC", "VARCHAR(30)", "Tiền mặt / Chuyển khoản"),
        C("GHI_CHU", DAI, "Ghi chú"),
        C("NGUOI_THU", "VARCHAR(50)", "Người thu (tài khoản)"),
        C("DA_HUY", BOOL, "1 = phiếu đã hủy", False, "0"),
        C("LY_DO_HUY", CHU, "Lý do hủy"),
        C("NGUOI_HUY", "VARCHAR(50)", "Người hủy"),
        C("HUY_LUC", THOI_DIEM, "Hủy lúc")], ("MA_PHIEU_THU",),
        fks=[(("MA_HOA_DON",), "MN_NV_HOA_DON", ("MA_HOA_DON",), "CASCADE")], indexes=[("NGAY_THU",)]),
    Table("MN_NV_THUC_DON", "NV", "Thực đơn ngày", [
        C("MA_THUC_DON", MA, "Mã thực đơn (TDxxx)", False),
        C("NGAY", NGAY, "Ngày", False),
        C("GHI_CHU", DAI, "Ghi chú")], ("MA_THUC_DON",), uniques=[("NGAY",)]),
    Table("MN_NV_THUC_DON_CHI_TIET", "NV", "Món ăn theo từng bữa của thực đơn (quan hệ n-n thực đơn - món)", [
        C("MA_THUC_DON", MA, "Thực đơn", False),
        C("BUA_AN", "VARCHAR(20)", "BREAKFAST / LUNCH / SNACK", False),
        C("STT", SO, "Thứ tự món trong bữa", False),
        C("MA_MON", MA, "Món ăn", False)], ("MA_THUC_DON", "BUA_AN", "STT"),
        fks=[(("MA_THUC_DON",), "MN_NV_THUC_DON", ("MA_THUC_DON",), "CASCADE"),
             (("MA_MON",), "MN_DM_MON_AN", ("MA_MON",), "RESTRICT")]),
    Table("MN_NV_NHAT_KY_TRE", "NV", "Nhật ký ăn - ngủ - sinh hoạt hằng ngày gửi phụ huynh", [
        C("MA_NHAT_KY", MA, "Mã (NKxxx)", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("MA_LOP", MA, "Lớp tại ngày ghi (lưu lại, không ràng buộc)"),
        C("NGAY", NGAY, "Ngày", False),
        C("GIAC_NGU", "VARCHAR(30)", "Giấc ngủ"),
        C("SO_PHUT_NGU", SO, "Số phút ngủ trưa"),
        C("TAM_TRANG", "VARCHAR(30)", "Tâm trạng"),
        C("HOAT_DONG", DAI, "Hoạt động trong ngày"),
        C("SUC_KHOE", DAI, "Ghi chú sức khỏe"),
        C("LOI_NHAN_CUA_CO", DAI, "Lời nhắn của cô"),
        C("NGUOI_CAP_NHAT", TEN, "Người cập nhật"),
        C("CAP_NHAT_LUC", THOI_DIEM, "Cập nhật lúc"),
        C("GUI_PHU_HUYNH_LUC", THOI_DIEM, "Gửi phụ huynh lúc"),
        C("PHU_HUYNH_XEM_LUC", THOI_DIEM, "Phụ huynh xem lúc"),
        C("PHU_HUYNH_PHAN_HOI", DAI, "Phụ huynh phản hồi"),
        C("PHAN_HOI_LUC", THOI_DIEM, "Phản hồi lúc")], ("MA_NHAT_KY",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")], indexes=[("MA_TRE", "NGAY"), ("NGAY",)]),
    Table("MN_NV_NHAT_KY_BUA_AN", "NV", "Mức ăn của trẻ theo từng bữa trong nhật ký", [
        C("MA_NHAT_KY", MA, "Nhật ký", False),
        C("STT", SO, "Thứ tự bữa", False),
        C("BUA_AN", "VARCHAR(30)", "Bữa (sáng, trưa, xế)", False),
        C("MUC_AN", "VARCHAR(30)", "Mức ăn (Ăn hết, Ăn khá...)", False)], ("MA_NHAT_KY", "STT"),
        fks=[(("MA_NHAT_KY",), "MN_NV_NHAT_KY_TRE", ("MA_NHAT_KY",), "CASCADE")]),
    Table("MN_NV_TIN_NHAN", "NV", "Trao đổi giữa phụ huynh và nhà trường (lời nhắn, dặn thuốc, xin nghỉ, thông báo)", [
        C("MA_TIN_NHAN", MA, "Mã (TNxxx)", False),
        C("LOAI_TIN", "VARCHAR(20)", "NOTE / MEDICINE / LEAVE / NOTICE...", False),
        C("MA_TRE", MA, "Trẻ (NULL = thông báo cả lớp)"),
        C("MA_LOP", MA, "Lớp (lưu lại, không ràng buộc)"),
        C("NOI_DUNG", DAI, "Nội dung", False),
        C("NGUOI_GUI", TEN, "Người gửi"),
        C("VAI_TRO_NGUOI_GUI", "VARCHAR(50)", "Vai trò người gửi"),
        C("NGAY_AP_DUNG", NGAY, "Áp dụng cho ngày"),
        C("DEN_NGAY", NGAY, "Đến ngày (xin nghỉ nhiều ngày)"),
        C("TEN_THUOC", "VARCHAR(100)", "Tên thuốc"),
        C("LIEU_DUNG", "VARCHAR(100)", "Liều dùng"),
        C("GIO_UONG", "VARCHAR(100)", "Giờ uống"),
        C("TRANG_THAI", "VARCHAR(30)", "Trạng thái xử lý"),
        C("TRA_LOI", DAI, "Nhà trường trả lời"),
        C("NGUOI_TRA_LOI", TEN, "Người trả lời"),
        C("TRA_LOI_LUC", THOI_DIEM, "Trả lời lúc"),
        C("GUI_LUC", THOI_DIEM, "Gửi lúc"),
        C("THUC_HIEN_LUC", THOI_DIEM, "Thực hiện lúc (cho uống thuốc)"),
        C("MA_DON_NGHI", MA, "Đơn xin nghỉ được tạo từ tin nhắn")], ("MA_TIN_NHAN",),
        fks=[(("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE"),
             (("MA_DON_NGHI",), "MN_NV_DON_XIN_NGHI", ("MA_DON",), "SET NULL")],
        indexes=[("MA_LOP",), ("NGAY_AP_DUNG",)]),
    Table("MN_NV_SO_TIET_DAY", "NV", "Sổ tiết dạy bộ môn - giáo viên bộ môn ghi mỗi tiết đã dạy ở một lớp", [
        C("MA_TIET_DAY", MA, "Mã (TDxxx)", False),
        C("NGAY_DAY", NGAY, "Ngày dạy", False),
        C("MA_LOP", MA, "Lớp được dạy", False),
        C("MA_GIAO_VIEN", MA, "Giáo viên bộ môn", False),
        C("MON_HOC", "VARCHAR(100)", "Môn học / hoạt động (Âm nhạc, Tiếng Anh...)", False),
        C("MA_TIET", MA, "Tiết trong thời khóa biểu (lưu lại, không ràng buộc)"),
        C("GIO_DAY", "VARCHAR(20)", "Giờ dạy (VD: 09:00 - 09:35)"),
        C("NOI_DUNG", DAI, "Nội dung bài dạy", False),
        C("DANH_GIA_CHUNG", "VARCHAR(30)", "Đánh giá chung cả lớp (Tốt / Khá / Trung bình / Cần cố gắng)"),
        C("GHI_CHU", DAI, "Ghi chú"),
        C("NGUOI_GHI", TEN, "Người ghi sổ"),
        C("CAP_NHAT_LUC", THOI_DIEM, "Cập nhật lúc")], ("MA_TIET_DAY",),
        fks=[(("MA_LOP",), "MN_DM_LOP_HOC", ("MA_LOP",), "CASCADE"),
             (("MA_GIAO_VIEN",), "MN_DM_NHAN_SU", ("MA_NHAN_SU",), "CASCADE")],
        uniques=[("NGAY_DAY", "MA_LOP", "MA_GIAO_VIEN", "MON_HOC")], indexes=[("MA_GIAO_VIEN", "NGAY_DAY")]),
    Table("MN_NV_TIET_DAY_NHAN_XET", "NV", "Nhận xét từng trẻ trong tiết dạy bộ môn", [
        C("MA_TIET_DAY", MA, "Tiết dạy", False),
        C("MA_TRE", MA, "Trẻ", False),
        C("MUC_DANH_GIA", "VARCHAR(30)", "Nổi bật / Đạt / Cần hỗ trợ"),
        C("NHAN_XET", CHU, "Nhận xét của giáo viên bộ môn")], ("MA_TIET_DAY", "MA_TRE"),
        fks=[(("MA_TIET_DAY",), "MN_NV_SO_TIET_DAY", ("MA_TIET_DAY",), "CASCADE"),
             (("MA_TRE",), "MN_DM_TRE", ("MA_TRE",), "CASCADE")]),
    Table("MN_NV_BAO_CAO", "NV", "Báo cáo các bộ phận gửi Ban giám hiệu và báo cáo toàn trường", [
        C("MA_BAO_CAO", MA, "Mã báo cáo (BCxxx)", False),
        C("LOAI_BAO_CAO", "VARCHAR(30)", "Loại (end_of_day, revenue, school_day...)", False),
        C("NGUOI_LAP", "VARCHAR(50)", "Tài khoản người lập", False),
        C("HO_TEN_NGUOI_LAP", TEN, "Họ tên người lập"),
        C("BO_PHAN", "VARCHAR(50)", "Bộ phận"),
        C("TRANG_THAI", "VARCHAR(50)", "Nháp / Đã gửi / Đã duyệt / Yêu cầu bổ sung / Lưu hồ sơ", False),
        C("GHI_CHU", DAI, "Ghi chú của người lập"),
        C("TAO_LUC", THOI_DIEM, "Tạo lúc"),
        C("GUI_LUC", THOI_DIEM, "Gửi lúc"),
        C("NGUOI_DUYET", TEN, "Người duyệt (BGH)"),
        C("DUYET_LUC", THOI_DIEM, "Duyệt lúc"),
        C("Y_KIEN_BGH", DAI, "Ý kiến Ban giám hiệu"),
        C("KY_NGAY", NGAY, "Kỳ báo cáo - ngày"),
        C("KY_THANG", "TINYINT", "Kỳ báo cáo - tháng"),
        C("KY_NAM", "SMALLINT", "Kỳ báo cáo - năm"),
        C("MA_LOP", MA, "Phạm vi lớp (lưu lại, không ràng buộc)"),
        C("TEN_LOP", CHU, "Tên lớp trong phạm vi"),
        C("CO_CHON_NGUON", BOOL, "1 = báo cáo toàn trường có chọn báo cáo nguồn", False, "0"),
        C("SO_LIEU", "TEXT","Số liệu đã chốt (JSON: tiêu đề, cột, dòng, tổng hợp) - văn bản cố định")],
        ("MA_BAO_CAO",), indexes=[("NGUOI_LAP",), ("TRANG_THAI",)]),
    Table("MN_NV_BAO_CAO_NGUON", "NV", "Báo cáo bộ phận được đưa vào báo cáo toàn trường (quan hệ n-n)", [
        C("MA_BAO_CAO", MA, "Báo cáo toàn trường", False),
        C("STT", SO, "Thứ tự", False),
        C("MA_BAO_CAO_NGUON", MA, "Báo cáo bộ phận", False)], ("MA_BAO_CAO", "STT"),
        fks=[(("MA_BAO_CAO",), "MN_NV_BAO_CAO", ("MA_BAO_CAO",), "CASCADE"),
             (("MA_BAO_CAO_NGUON",), "MN_NV_BAO_CAO", ("MA_BAO_CAO",), "RESTRICT")]),
    Table("MN_NV_BAO_CAO_LICH_SU", "NV", "Lịch sử xử lý báo cáo (gửi, duyệt, yêu cầu bổ sung)", [
        C("MA_BAO_CAO", MA, "Báo cáo", False),
        C("STT", SO, "Thứ tự", False),
        C("THOI_DIEM", THOI_DIEM, "Thời điểm"),
        C("NGUOI_THUC_HIEN", TEN, "Người thực hiện"),
        C("HANH_DONG", CHU, "Hành động")], ("MA_BAO_CAO", "STT"),
        fks=[(("MA_BAO_CAO",), "MN_NV_BAO_CAO", ("MA_BAO_CAO",), "CASCADE")]),
    Table("MN_NV_BANG_LUONG", "NV", "Bảng lương tháng đã chốt", [
        C("KY_LUONG", "VARCHAR(10)", "Kỳ lương (yyyy-mm)", False),
        C("CHOT_LUC", THOI_DIEM, "Chốt lúc"),
        C("NGUOI_CHOT", TEN, "Người chốt")], ("KY_LUONG",)),
    Table("MN_NV_BANG_LUONG_CHI_TIET", "NV", "Lương từng nhân sự trong bảng lương đã chốt (số liệu cố định)", [
        C("KY_LUONG", "VARCHAR(10)", "Kỳ lương", False),
        C("STT", SO, "Số thứ tự", False),
        C("MA_NHAN_SU", MA, "Nhân sự (lưu lại, không ràng buộc)", False),
        C("HO_TEN", TEN, "Họ tên"),
        C("LOAI", "VARCHAR(30)", "Giáo viên / Nhân viên"),
        C("CHUC_VU", "VARCHAR(100)", "Chức vụ"),
        C("THUC_LINH", TIEN, "Thực lĩnh (đồng)", False),
        C("CACH_TINH", CHU, "Diễn giải cách tính")], ("KY_LUONG", "STT"),
        fks=[(("KY_LUONG",), "MN_NV_BANG_LUONG", ("KY_LUONG",), "CASCADE")]),
]
TABLES: dict[str, Table] = {t.name: t for t in TABLE_LIST}


# =============================================================================
# Chuyển đổi giá trị
# =============================================================================
def _date_in(value: Any) -> Any:
    return value or None


def _date_out(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _dt_in(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise DataStoreError(f"Thời điểm '{value}' không đúng định dạng.") from exc


def _dt_out(value: Any, seconds: bool = False) -> str:
    """DATETIME -> chuỗi như chương trình đang dùng ('yyyy-mm-ddThh:mm' hoặc có giây)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds" if seconds or value.second else "minutes")
    return str(value)


def _time_out(value: Any) -> str:
    if isinstance(value, timedelta):
        minutes = int(value.total_seconds()) // 60
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value or "")


def _num_out(value: Any) -> Any:
    """DECIMAL -> số nguyên nếu tròn, ngược lại số thực."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _float_out(value: Any) -> float | None:
    return None if value is None else float(value)


def _b(value: Any) -> int:
    return 1 if value else 0


def _s(value: Any) -> Any:
    """Chuỗi rỗng / None -> NULL (cho mã liên kết tùy chọn)."""
    return value if value not in (None, "") else None


def _txt(value: Any) -> str:
    return "" if value is None else str(value)


# =============================================================================
# Đối tượng <-> tập dòng
# =============================================================================
Rowset = dict[str, list[tuple]]   # bảng -> các dòng


@dataclass
class Entity:
    """Một loại đối tượng: bảng chính + bảng con (xóa / ghi lại cùng đối tượng) + bảng 1-1 (ghi đè)."""
    name: str
    table: str
    owned: tuple[str, ...] = ()
    subtypes: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return TABLES[self.table].pk[0]


ENTITIES: list[Entity] = [   # thứ tự = thứ tự ghi (bảng được tham chiếu trước)
    Entity("vai_tro", "MN_HT_VAI_TRO"),
    Entity("tham_so", "MN_HT_THAM_SO"),
    Entity("khoi_lop", "MN_DM_KHOI_LOP"),
    Entity("dich_vu", "MN_DM_DICH_VU"),
    Entity("ngay_nghi", "MN_DM_NGAY_NGHI"),
    Entity("employees", "MN_DM_NHAN_SU", ("MN_NV_LAM_THEM_GIO",), ("MN_DM_GIAO_VIEN", "MN_DM_NHAN_VIEN")),
    Entity("classes", "MN_DM_LOP_HOC"),
    Entity("parents", "MN_DM_PHU_HUYNH"),
    Entity("children", "MN_DM_TRE", ("MN_DM_TRE_PHU_HUYNH", "MN_DM_NGUOI_DON_HO", "MN_NV_DANG_KY_DICH_VU")),
    Entity("users", "MN_HT_TAI_KHOAN"),
    Entity("meals", "MN_DM_MON_AN", ("MN_DM_THANH_PHAN_MON",)),
    Entity("timetable", "MN_NV_THOI_KHOA_BIEU"),
    Entity("health_records", "MN_NV_CAN_DO"),
    Entity("allergies", "MN_NV_DI_UNG"),
    Entity("leave_requests", "MN_NV_DON_XIN_NGHI", ("MN_NV_DON_NGHI_NGAY_DA_DUYET",)),
    Entity("attendance", "MN_NV_DIEM_DANH"),
    Entity("invoices", "MN_NV_HOA_DON", ("MN_NV_HOA_DON_KHOAN_PHI", "MN_NV_PHIEU_THU")),
    Entity("menus", "MN_NV_THUC_DON", ("MN_NV_THUC_DON_CHI_TIET",)),
    Entity("daily_logs", "MN_NV_NHAT_KY_TRE", ("MN_NV_NHAT_KY_BUA_AN",)),
    Entity("messages", "MN_NV_TIN_NHAN"),
    Entity("lesson_logs", "MN_NV_SO_TIET_DAY", ("MN_NV_TIET_DAY_NHAN_XET",)),
    Entity("reports", "MN_NV_BAO_CAO", ("MN_NV_BAO_CAO_NGUON", "MN_NV_BAO_CAO_LICH_SU")),
    Entity("bang_luong", "MN_NV_BANG_LUONG", ("MN_NV_BANG_LUONG_CHI_TIET",)),
]
ENTITY_BY_NAME = {e.name: e for e in ENTITIES}

# Tham số hệ thống (MN_HT_THAM_SO): khóa trong FeeSettings -> (mã tham số, mô tả)
SETTING_PARAMS = {
    "monthly_tuition": ("HOC_PHI_THANG", "Học phí tháng chung cho mọi khối (đồng)"),
    "meal_rate_per_day": ("TIEN_AN_MOT_NGAY", "Tiền ăn một ngày đi học (đồng)"),
    "second_child_rate": ("TY_LE_GIAM_CON_THU_HAI", "Tỷ lệ giảm học phí con thứ hai trở đi (0 - 1)"),
    "poor_household_rate": ("TY_LE_GIAM_HO_NGHEO", "Tỷ lệ giảm học phí hộ nghèo (0 - 1)"),
    "due_days": ("SO_NGAY_HAN_NOP", "Số ngày được nộp kể từ ngày lập hóa đơn"),
    "base_salary_unit": ("LUONG_CO_SO", "Lương cơ sở (đồng)"),
    "teacher_incentive_rate": ("TY_LE_UU_DAI_NGHE", "Phụ cấp ưu đãi nghề giáo viên mầm non (0 - 1)"),
    "homeroom_allowance": ("PHU_CAP_CHU_NHIEM", "Phụ cấp chủ nhiệm lớp (đồng)"),
}
SATURDAY_PARAM = "HOC_THU_BAY"


def _rows_of(system: "KindergartenSystem") -> dict[str, dict[str, Rowset]]:
    """Toàn bộ dữ liệu trong bộ nhớ -> {thực thể: {mã: tập dòng}}."""
    from ..auth.user import Role
    from ..classroom.classroom import AgeGroup
    from ..utils import normalize_text

    out: dict[str, dict[str, Rowset]] = {e.name: {} for e in ENTITIES}
    out["vai_tro"] = {r.value: {"MN_HT_VAI_TRO": [(r.value, r.label)]} for r in Role}
    settings = system.settings.to_dict()
    for key, (code, note) in SETTING_PARAMS.items():
        value = settings[key]
        kind = "float" if isinstance(value, float) else "int"
        out["tham_so"][code] = {"MN_HT_THAM_SO": [(code, repr(value) if kind == "float" else str(value), kind, note)]}
    saturday = system.calendar.to_dict().get("saturday_classes", False)
    out["tham_so"][SATURDAY_PARAM] = {"MN_HT_THAM_SO": [(SATURDAY_PARAM, "1" if saturday else "0", "bool",
                                                          "Trường có học thứ Bảy (1 = có)")]}
    tuition = dict(settings["tuition_by_group"])
    for group in AgeGroup:
        price = next((v for k, v in tuition.items() if normalize_text(k) == normalize_text(group.label)), None)
        tuition = {k: v for k, v in tuition.items() if normalize_text(k) != normalize_text(group.label)}
        out["khoi_lop"][group.name] = {"MN_DM_KHOI_LOP": [(group.name, group.label, group.min_age, group.max_age,
                                                           price)]}
    for label, price in tuition.items():   # học phí riêng đặt cho tên khối khác 4 khối chuẩn
        out["khoi_lop"][label] = {"MN_DM_KHOI_LOP": [(label, label, None, None, price)]}
    for order, (name, price) in enumerate(settings["extra_services"].items(), 1):
        out["dich_vu"][name] = {"MN_DM_DICH_VU": [(name, price, order)]}
    for day, name in system.calendar.to_dict().get("holidays", {}).items():
        out["ngay_nghi"][day] = {"MN_DM_NGAY_NGHI": [(day, name)]}
    for period, closed in system.employees.closed_payrolls_to_dict().items():
        out["bang_luong"][period] = {
            "MN_NV_BANG_LUONG": [(period, _dt_in(closed.get("closed_at")), closed.get("by", ""))],
            "MN_NV_BANG_LUONG_CHI_TIET": [
                (period, i, r.get("employee_id", ""), r.get("name", ""), r.get("type", ""), r.get("position", ""),
                 int(r.get("salary", 0)), r.get("note", "")) for i, r in enumerate(closed.get("rows", []), 1)]}

    for collection, (manager, _factory) in DataStore.collections(system).items():
        encode = ENCODERS[collection]
        target = out[collection]
        for item in manager:
            data = item.to_dict()
            target[data["id"]] = encode(data)
    return out


def _enc_user(d: dict[str, Any]) -> Rowset:
    return {"MN_HT_TAI_KHOAN": [(
        d["id"], d["username"], d.get("full_name", ""), d["role"], d["password_hash"], _s(d.get("employee_id")),
        _s(d.get("parent_id")), _txt(d.get("duty")), _txt(d.get("phone")), _b(d.get("active", True)),
        _b(d.get("pending")), _b(d.get("must_change_password")), _dt_in(d.get("created_at")),
        _dt_in(d.get("last_login")))]}


def _enc_employee(d: dict[str, Any]) -> Rowset:
    teacher = d.get("type") == "Teacher"
    rows: Rowset = {"MN_DM_NHAN_SU": [(
        d["id"], "GIAO_VIEN" if teacher else "NHAN_VIEN", d["full_name"], _date_in(d.get("dob")),
        _txt(d.get("gender")), _txt(d.get("phone")), _txt(d.get("address")), _txt(d.get("position")),
        _date_in(d.get("hire_date")))]}
    if teacher:
        rows["MN_DM_GIAO_VIEN"] = [(d["id"], _txt(d.get("qualification")), d.get("salary_coefficient"),
                                    _txt(d.get("specialty")))]
    else:
        rows["MN_DM_NHAN_VIEN"] = [(d["id"], d.get("base_salary"), d.get("allowance"))]
        rows["MN_NV_LAM_THEM_GIO"] = [(d["id"], period, hours) for period, hours in (d.get("overtime") or {}).items()]
    return rows


def _enc_child(d: dict[str, Any]) -> Rowset:
    return {
        "MN_DM_TRE": [(d["id"], d["full_name"], _txt(d.get("nickname")), _date_in(d.get("dob")), _txt(d.get("gender")),
                       _txt(d.get("phone")), _txt(d.get("address")), _s(d.get("class_id")),
                       _date_in(d.get("enrollment_date")), _txt(d.get("status")), _date_in(d.get("leave_date")),
                       _b(d.get("is_poor_household")), _txt(d.get("notes")))],
        "MN_DM_TRE_PHU_HUYNH": [(d["id"], pid, i) for i, pid in enumerate(d.get("parent_ids") or [], 1)],
        "MN_DM_NGUOI_DON_HO": [(d["id"], i, p.get("full_name", ""), _txt(p.get("relationship")), _txt(p.get("phone")),
                                _txt(p.get("id_card"))) for i, p in enumerate(d.get("pickup_persons") or [], 1)],
        "MN_NV_DANG_KY_DICH_VU": [(d["id"], name, i) for i, name in enumerate(d.get("extra_services") or [], 1)],
    }


def _enc_parent(d: dict[str, Any]) -> Rowset:
    return {"MN_DM_PHU_HUYNH": [(d["id"], d["full_name"], _date_in(d.get("dob")), _txt(d.get("gender")),
                                 _txt(d.get("phone")), _txt(d.get("email")), _txt(d.get("address")),
                                 _txt(d.get("occupation")), _txt(d.get("relationship")))]}


def _enc_class(d: dict[str, Any]) -> Rowset:
    return {"MN_DM_LOP_HOC": [(d["id"], d["name"], d["age_group"], d.get("capacity"), _txt(d.get("room")),
                               _s(d.get("teacher_id")))]}


def _enc_slot(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_THOI_KHOA_BIEU": [(d["id"], d["class_id"], d["weekday"], d["start"], d["end"], d["activity"],
                                      _s(d.get("teacher_id")))]}


def _enc_health(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_CAN_DO": [(d["id"], d["child_id"], d["measure_date"], d["height_cm"], d["weight_kg"],
                              d.get("age_months"), _txt(d.get("note")))]}


def _enc_allergy(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_DI_UNG": [(d["id"], d["child_id"], d["allergen"], d["severity"], _txt(d.get("reaction")))]}


def _enc_leave(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_DON_XIN_NGHI": [(d["id"], d["child_id"], d["from_date"], d["to_date"], _txt(d.get("reason")),
                                    _txt(d.get("submitted_by")), _dt_in(d.get("created_at")))],
            "MN_NV_DON_NGHI_NGAY_DA_DUYET": [(d["id"], day) for day in d.get("converted_dates") or []]}


def _enc_attendance(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_DIEM_DANH": [(d["id"], d["child_id"], d["class_id"], d["date"], d["status"], _txt(d.get("note")),
                                 _dt_in(d.get("arrived_at")), _txt(d.get("brought_by")), _txt(d.get("received_by")),
                                 _dt_in(d.get("picked_up_at")), _txt(d.get("picked_up_by")),
                                 _txt(d.get("released_by")))]}


FEE_COLUMNS = {"MonthlyFee": ("amount", None), "MealFee": ("rate_per_day", "days"), "ExtraFee": ("amount", "quantity")}


def _enc_invoice(d: dict[str, Any]) -> Rowset:
    discount = d.get("discount") or {}
    rows: Rowset = {"MN_NV_HOA_DON": [(
        d["id"], d["child_id"], d["month"], d["year"], _txt(d.get("child_name")), _txt(d.get("class_name")),
        d["issue_date"], _date_in(d.get("due_date")), _b(d.get("provisional")), _txt(d.get("note")),
        discount.get("name") if discount else None, discount.get("rate") if discount else None,
        discount.get("amount") if discount else None, discount.get("reason") if discount else None)]}
    fees = []
    for i, fee in enumerate(d.get("fees") or [], 1):
        price_key, qty_key = FEE_COLUMNS[fee["type"]]
        fees.append((d["id"], i, fee["type"], fee["name"], fee[price_key], fee.get(qty_key) if qty_key else None))
    rows["MN_NV_HOA_DON_KHOAN_PHI"] = fees
    rows["MN_NV_PHIEU_THU"] = [(p["id"], d["id"], p["amount"], p["pay_date"], _txt(p.get("method")),
                                _txt(p.get("note")), _txt(p.get("collected_by")), _b(p.get("voided")),
                                _txt(p.get("void_reason")), _txt(p.get("voided_by")), _dt_in(p.get("voided_at")))
                               for p in d.get("payments") or []]
    return rows


def _enc_meal(d: dict[str, Any]) -> Rowset:
    return {"MN_DM_MON_AN": [(d["id"], d["name"], d.get("calories"), _txt(d.get("description")),
                              _b(d.get("active", True)))],
            "MN_DM_THANH_PHAN_MON": [(d["id"], i, name) for i, name in enumerate(d.get("ingredients") or [], 1)]}


def _enc_menu(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_THUC_DON": [(d["id"], d["date"], _txt(d.get("note")))],
            "MN_NV_THUC_DON_CHI_TIET": [(d["id"], meal_type, i, meal_id)
                                        for meal_type, ids in (d.get("items") or {}).items()
                                        for i, meal_id in enumerate(ids, 1)]}


def _enc_daily(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_NHAT_KY_TRE": [(
        d["id"], d["child_id"], _s(d.get("class_id")), d["date"], _txt(d.get("nap")), d.get("nap_minutes"),
        _txt(d.get("mood")), _txt(d.get("activities")), _txt(d.get("health_note")), _txt(d.get("teacher_note")),
        _txt(d.get("updated_by")), _dt_in(d.get("updated_at")), _dt_in(d.get("sent_at")),
        _dt_in(d.get("parent_seen_at")), _txt(d.get("parent_reply")), _dt_in(d.get("parent_reply_at")))],
        "MN_NV_NHAT_KY_BUA_AN": [(d["id"], i, meal, level)
                                 for i, (meal, level) in enumerate((d.get("meals") or {}).items(), 1)]}


def _enc_message(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_TIN_NHAN": [(
        d["id"], d["kind"], _s(d.get("child_id")), _s(d.get("class_id")), d.get("content", ""), _txt(d.get("sender")),
        _txt(d.get("sender_role")), _date_in(d.get("for_date")), _date_in(d.get("to_date")), _txt(d.get("medicine")),
        _txt(d.get("dosage")), _txt(d.get("time_text")), _txt(d.get("status")), _txt(d.get("reply")),
        _txt(d.get("replied_by")), _dt_in(d.get("replied_at")), _dt_in(d.get("created_at")), _dt_in(d.get("done_at")),
        _s(d.get("leave_request_id")))]}


def _enc_report(d: dict[str, Any]) -> Rowset:
    p = d.get("params") or {}
    sources = p.get("report_ids")
    return {"MN_NV_BAO_CAO": [(
        d["id"], d["type_key"], d["author"], _txt(d.get("author_name")), _txt(d.get("author_role")), d["status"],
        _txt(d.get("note")), _dt_in(d.get("created_at")), _dt_in(d.get("sent_at")), _txt(d.get("reviewed_by")),
        _dt_in(d.get("reviewed_at")), _txt(d.get("review_comment")), _date_in(p.get("on_date")), p.get("month"),
        p.get("year"), _s(p.get("class_id")), p.get("class_name"), _b(sources is not None),
        json.dumps(d.get("data") or {}, ensure_ascii=False, default=str))],
        "MN_NV_BAO_CAO_NGUON": [(d["id"], i, rid) for i, rid in enumerate(sources or [], 1)],
        "MN_NV_BAO_CAO_LICH_SU": [(d["id"], i, _dt_in(h.get("at")), _txt(h.get("by")), _txt(h.get("action")))
                                  for i, h in enumerate(d.get("history") or [], 1)]}


def _enc_lesson(d: dict[str, Any]) -> Rowset:
    return {"MN_NV_SO_TIET_DAY": [(
        d["id"], d["date"], d["class_id"], d["teacher_id"], d["subject"], _s(d.get("slot_id")),
        _txt(d.get("time_text")), d["content"], _txt(d.get("rating")), _txt(d.get("note")),
        _txt(d.get("created_by")), _dt_in(d.get("updated_at")))],
        "MN_NV_TIET_DAY_NHAN_XET": [(d["id"], child_id, _txt(item.get("level")), _txt(item.get("comment")))
                                    for child_id, item in sorted((d.get("child_notes") or {}).items())]}


ENCODERS: dict[str, Callable[[dict[str, Any]], Rowset]] = {
    "users": _enc_user, "employees": _enc_employee, "children": _enc_child, "parents": _enc_parent,
    "classes": _enc_class, "timetable": _enc_slot, "health_records": _enc_health, "allergies": _enc_allergy,
    "attendance": _enc_attendance, "leave_requests": _enc_leave, "invoices": _enc_invoice, "meals": _enc_meal,
    "menus": _enc_menu, "daily_logs": _enc_daily, "messages": _enc_message, "reports": _enc_report,
    "lesson_logs": _enc_lesson,
}


# ------------------------------------------------------------------ đọc: dòng -> dữ liệu của chương trình
def _put(record: dict[str, Any], key: str, value: Any) -> None:
    """NULL = không có giá trị -> để from_dict dùng giá trị mặc định."""
    if value is not None:
        record[key] = value


def _decode(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Các bảng (dạng danh sách dòng) -> dữ liệu cùng định dạng bản JSON để nạp vào chương trình."""
    def by(table: str, key: str) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in tables.get(table, []):
            groups.setdefault(row[key], []).append(row)
        return groups

    payload: dict[str, Any] = {}
    # ---- tham số, khối, dịch vụ, lịch, bảng lương
    params = {r["MA_THAM_SO"]: r for r in tables.get("MN_HT_THAM_SO", [])}
    defaults = FeeSettings().to_dict()
    settings: dict[str, Any] = {}
    for key, (code, _note) in SETTING_PARAMS.items():
        if code in params:
            raw = params[code]["GIA_TRI"]
            settings[key] = float(raw) if params[code]["KIEU_DU_LIEU"] == "float" else int(raw)
        else:
            settings[key] = defaults[key]
    services = sorted(tables.get("MN_DM_DICH_VU", []), key=lambda r: (r["THU_TU"] or 0, r["TEN_DICH_VU"]))
    settings["extra_services"] = {r["TEN_DICH_VU"]: int(r["DON_GIA"]) for r in services}
    settings["tuition_by_group"] = {r["TEN_KHOI"]: int(r["HOC_PHI_RIENG"]) for r in tables.get("MN_DM_KHOI_LOP", [])
                                    if r["HOC_PHI_RIENG"] is not None}
    payload["settings"] = settings
    saturday = params.get(SATURDAY_PARAM, {}).get("GIA_TRI") == "1"
    payload["calendar"] = {"saturday_classes": saturday,
                           "holidays": {_date_out(r["NGAY"]): r["TEN_NGAY_NGHI"]
                                        for r in tables.get("MN_DM_NGAY_NGHI", [])}}
    payroll_rows = by("MN_NV_BANG_LUONG_CHI_TIET", "KY_LUONG")
    payload["payroll"] = {r["KY_LUONG"]: {
        "closed_at": _dt_out(r["CHOT_LUC"], seconds=True), "by": r["NGUOI_CHOT"] or "",
        "rows": [{"employee_id": x["MA_NHAN_SU"], "name": x["HO_TEN"] or "", "type": x["LOAI"] or "",
                  "position": x["CHUC_VU"] or "", "salary": int(x["THUC_LINH"]), "note": x["CACH_TINH"] or ""}
                 for x in sorted(payroll_rows.get(r["KY_LUONG"], []), key=lambda x: x["STT"])]}
        for r in tables.get("MN_NV_BANG_LUONG", [])}

    # ---- tài khoản
    users = []
    for r in tables.get("MN_HT_TAI_KHOAN", []):
        u = {"type": "User", "id": r["MA_TAI_KHOAN"], "username": r["TEN_DANG_NHAP"], "full_name": r["HO_TEN"],
             "role": r["MA_VAI_TRO"], "password_hash": r["MAT_KHAU_BAM"], "employee_id": r["MA_NHAN_SU"],
             "parent_id": r["MA_PHU_HUYNH"], "active": bool(r["DANG_HOAT_DONG"]), "pending": bool(r["CHO_DUYET"]),
             "must_change_password": bool(r["PHAI_DOI_MAT_KHAU"]), "duty": r["CONG_VIEC"] or "",
             "phone": r["SO_DIEN_THOAI"] or ""}
        _put(u, "created_at", _dt_out(r["NGAY_TAO"], True) or None)
        _put(u, "last_login", _dt_out(r["LAN_DANG_NHAP_CUOI"], True) or None)
        users.append(u)
    payload["users"] = users

    # ---- nhân sự
    teachers = {r["MA_NHAN_SU"]: r for r in tables.get("MN_DM_GIAO_VIEN", [])}
    staffs = {r["MA_NHAN_SU"]: r for r in tables.get("MN_DM_NHAN_VIEN", [])}
    overtime = by("MN_NV_LAM_THEM_GIO", "MA_NHAN_SU")
    homeroom = {r["MA_GV_CHU_NHIEM"]: r["MA_LOP"] for r in tables.get("MN_DM_LOP_HOC", []) if r["MA_GV_CHU_NHIEM"]}
    employees = []
    for r in tables.get("MN_DM_NHAN_SU", []):
        e = {"id": r["MA_NHAN_SU"], "full_name": r["HO_TEN"], "gender": r["GIOI_TINH"] or "",
             "phone": r["SO_DIEN_THOAI"] or "", "address": r["DIA_CHI"] or "", "position": r["CHUC_VU"] or ""}
        _put(e, "dob", _date_out(r["NGAY_SINH"]))
        _put(e, "hire_date", _date_out(r["NGAY_VAO_LAM"]))
        if r["LOAI_NHAN_SU"] == "GIAO_VIEN":
            t = teachers.get(r["MA_NHAN_SU"], {})
            e.update(type="Teacher", qualification=t.get("TRINH_DO") or "", specialty=t.get("CHUYEN_MON") or "",
                     homeroom_class_id=homeroom.get(r["MA_NHAN_SU"]))
            _put(e, "salary_coefficient", _float_out(t.get("HE_SO_LUONG")))
        else:
            s = staffs.get(r["MA_NHAN_SU"], {})
            e.update(type="Staff", overtime={x["KY_LUONG"]: _num_out(x["SO_GIO"])
                                              for x in overtime.get(r["MA_NHAN_SU"], [])})
            _put(e, "base_salary", s.get("LUONG_CO_BAN"))
            _put(e, "allowance", s.get("PHU_CAP"))
        employees.append(e)
    payload["employees"] = employees

    # ---- trẻ, phụ huynh, lớp
    links = by("MN_DM_TRE_PHU_HUYNH", "MA_TRE")
    pickups = by("MN_DM_NGUOI_DON_HO", "MA_TRE")
    services_of = by("MN_NV_DANG_KY_DICH_VU", "MA_TRE")
    children = []
    for r in tables.get("MN_DM_TRE", []):
        c = {"type": "Child", "id": r["MA_TRE"], "full_name": r["HO_TEN"], "nickname": r["TEN_O_NHA"] or "",
             "dob": _date_out(r["NGAY_SINH"]), "gender": r["GIOI_TINH"] or "", "phone": r["SO_DIEN_THOAI"] or "",
             "address": r["DIA_CHI"] or "", "class_id": r["MA_LOP"], "is_poor_household": bool(r["HO_NGHEO"]),
             "notes": r["GHI_CHU"] or "", "leave_date": _date_out(r["NGAY_THOI_HOC"]),
             "parent_ids": [x["MA_PHU_HUYNH"] for x in sorted(links.get(r["MA_TRE"], []), key=lambda x: x["THU_TU"])],
             "pickup_persons": [{"full_name": x["HO_TEN"], "relationship": x["QUAN_HE"] or "",
                                 "phone": x["SO_DIEN_THOAI"] or "", "id_card": x["SO_CCCD"] or ""}
                                for x in sorted(pickups.get(r["MA_TRE"], []), key=lambda x: x["STT"])],
             "extra_services": [x["TEN_DICH_VU"] for x in sorted(services_of.get(r["MA_TRE"], []),
                                                                  key=lambda x: x["THU_TU"])]}
        _put(c, "enrollment_date", _date_out(r["NGAY_NHAP_HOC"]))
        _put(c, "status", r["TRANG_THAI"] or None)
        children.append(c)
    payload["children"] = children
    children_of_parent: dict[str, list[str]] = {}
    for row in sorted(tables.get("MN_DM_TRE_PHU_HUYNH", []), key=lambda x: x["MA_TRE"]):
        children_of_parent.setdefault(row["MA_PHU_HUYNH"], []).append(row["MA_TRE"])
    parents = []
    for r in tables.get("MN_DM_PHU_HUYNH", []):
        p = {"type": "Parent", "id": r["MA_PHU_HUYNH"], "full_name": r["HO_TEN"], "gender": r["GIOI_TINH"] or "",
             "phone": r["SO_DIEN_THOAI"] or "", "email": r["EMAIL"] or "", "address": r["DIA_CHI"] or "",
             "occupation": r["NGHE_NGHIEP"] or "", "relationship": r["QUAN_HE"] or "",
             "child_ids": children_of_parent.get(r["MA_PHU_HUYNH"], [])}
        _put(p, "dob", _date_out(r["NGAY_SINH"]))
        parents.append(p)
    payload["parents"] = parents
    pupils: dict[str, list[str]] = {}
    for row in sorted(tables.get("MN_DM_TRE", []), key=lambda x: x["MA_TRE"]):
        if row["MA_LOP"]:
            pupils.setdefault(row["MA_LOP"], []).append(row["MA_TRE"])
    payload["classes"] = [{"type": "Classroom", "id": r["MA_LOP"], "name": r["TEN_LOP"], "age_group": r["MA_KHOI"],
                           "capacity": r["SI_SO_TOI_DA"], "room": r["PHONG_HOC"] or "",
                           "teacher_id": r["MA_GV_CHU_NHIEM"], "child_ids": pupils.get(r["MA_LOP"], [])}
                          for r in tables.get("MN_DM_LOP_HOC", [])]
    payload["timetable"] = [{"type": "TimeSlot", "id": r["MA_TIET"], "class_id": r["MA_LOP"], "weekday": r["THU"],
                             "start": _time_out(r["GIO_BAT_DAU"]), "end": _time_out(r["GIO_KET_THUC"]),
                             "activity": r["HOAT_DONG"], "teacher_id": r["MA_GIAO_VIEN"]}
                            for r in tables.get("MN_NV_THOI_KHOA_BIEU", [])]

    # ---- sức khỏe, điểm danh, đơn nghỉ
    payload["health_records"] = [{"type": "HealthRecord", "id": r["MA_CAN_DO"], "child_id": r["MA_TRE"],
                                  "measure_date": _date_out(r["NGAY_DO"]), "height_cm": float(r["CHIEU_CAO_CM"]),
                                  "weight_kg": float(r["CAN_NANG_KG"]), "age_months": r["THANG_TUOI"],
                                  "note": r["GHI_CHU"] or ""} for r in tables.get("MN_NV_CAN_DO", [])]
    payload["allergies"] = [{"type": "Allergy", "id": r["MA_DI_UNG"], "child_id": r["MA_TRE"],
                             "allergen": r["CHAT_GAY_DI_UNG"], "severity": r["MUC_DO"], "reaction": r["BIEU_HIEN"] or ""}
                            for r in tables.get("MN_NV_DI_UNG", [])]
    payload["attendance"] = [{"type": "AttendanceRecord", "id": r["MA_DIEM_DANH"], "child_id": r["MA_TRE"],
                              "class_id": r["MA_LOP"], "date": _date_out(r["NGAY"]), "status": r["TRANG_THAI"],
                              "note": r["GHI_CHU"] or "", "arrived_at": _dt_out(r["GIO_DEN"]),
                              "brought_by": r["NGUOI_DUA"] or "", "received_by": r["NGUOI_NHAN_TRE"] or "",
                              "picked_up_at": _dt_out(r["GIO_VE"]), "picked_up_by": r["NGUOI_DON"] or "",
                              "released_by": r["NGUOI_GIAO_TRE"] or ""} for r in tables.get("MN_NV_DIEM_DANH", [])]
    converted = by("MN_NV_DON_NGHI_NGAY_DA_DUYET", "MA_DON")
    payload["leave_requests"] = [{"type": "LeaveRequest", "id": r["MA_DON"], "child_id": r["MA_TRE"],
                                  "from_date": _date_out(r["TU_NGAY"]), "to_date": _date_out(r["DEN_NGAY"]),
                                  "reason": r["LY_DO"] or "", "submitted_by": r["NGUOI_GUI"] or "",
                                  "created_at": _dt_out(r["NGAY_TAO"], True),
                                  "converted_dates": sorted(_date_out(x["NGAY"]) for x in converted.get(r["MA_DON"], []))}
                                 for r in tables.get("MN_NV_DON_XIN_NGHI", [])]

    # ---- học phí
    fees_of = by("MN_NV_HOA_DON_KHOAN_PHI", "MA_HOA_DON")
    payments_of = by("MN_NV_PHIEU_THU", "MA_HOA_DON")
    invoices = []
    for r in tables.get("MN_NV_HOA_DON", []):
        fees = []
        for x in sorted(fees_of.get(r["MA_HOA_DON"], []), key=lambda x: x["STT"]):
            price_key, qty_key = FEE_COLUMNS[x["LOAI_PHI"]]
            fee = {"type": x["LOAI_PHI"], "name": x["TEN_KHOAN"], price_key: int(x["DON_GIA"])}
            if qty_key:
                fee[qty_key] = x["SO_LUONG"]
            fees.append(fee)
        discount = None if r["TEN_MIEN_GIAM"] is None else {
            "name": r["TEN_MIEN_GIAM"], "rate": float(r["TY_LE_GIAM"] or 0), "amount": int(r["SO_TIEN_GIAM"] or 0),
            "reason": r["LY_DO_GIAM"] or ""}
        payments = [{"type": "Payment", "id": p["MA_PHIEU_THU"], "invoice_id": r["MA_HOA_DON"],
                     "amount": int(p["SO_TIEN"]), "pay_date": _date_out(p["NGAY_THU"]), "method": p["HINH_THUC"] or "",
                     "note": p["GHI_CHU"] or "", "collected_by": p["NGUOI_THU"] or "", "voided": bool(p["DA_HUY"]),
                     "void_reason": p["LY_DO_HUY"] or "", "voided_by": p["NGUOI_HUY"] or "",
                     "voided_at": _dt_out(p["HUY_LUC"], True)}
                    for p in sorted(payments_of.get(r["MA_HOA_DON"], []), key=lambda p: p["MA_PHIEU_THU"])]
        inv = {"type": "Invoice", "id": r["MA_HOA_DON"], "child_id": r["MA_TRE"], "month": r["THANG"],
               "year": r["NAM"], "child_name": r["TEN_TRE"] or "", "class_name": r["TEN_LOP"] or "",
               "issue_date": _date_out(r["NGAY_LAP"]), "due_date": _date_out(r["HAN_NOP"]),
               "note": r["GHI_CHU"] or "", "provisional": bool(r["TAM_TINH"]), "fees": fees, "discount": discount,
               "payments": payments}
        invoices.append(inv)
    payload["invoices"] = invoices

    # ---- bếp
    parts = by("MN_DM_THANH_PHAN_MON", "MA_MON")
    payload["meals"] = [{"type": "Meal", "id": r["MA_MON"], "name": r["TEN_MON"], "calories": r["NANG_LUONG_KCAL"],
                         "ingredients": [x["TEN_THANH_PHAN"] for x in sorted(parts.get(r["MA_MON"], []),
                                                                              key=lambda x: x["STT"])],
                         "description": r["MO_TA"] or "", "active": bool(r["DANG_SU_DUNG"])}
                        for r in tables.get("MN_DM_MON_AN", [])]
    menu_items = by("MN_NV_THUC_DON_CHI_TIET", "MA_THUC_DON")
    menus = []
    for r in tables.get("MN_NV_THUC_DON", []):
        items: dict[str, list[str]] = {}
        for x in sorted(menu_items.get(r["MA_THUC_DON"], []), key=lambda x: (x["BUA_AN"], x["STT"])):
            items.setdefault(x["BUA_AN"], []).append(x["MA_MON"])
        menus.append({"type": "Menu", "id": r["MA_THUC_DON"], "date": _date_out(r["NGAY"]), "note": r["GHI_CHU"] or "",
                      "items": items})
    payload["menus"] = menus

    # ---- nhật ký, tin nhắn, báo cáo
    meals_of = by("MN_NV_NHAT_KY_BUA_AN", "MA_NHAT_KY")
    payload["daily_logs"] = [{
        "type": "DailyLog", "id": r["MA_NHAT_KY"], "child_id": r["MA_TRE"], "class_id": r["MA_LOP"],
        "date": _date_out(r["NGAY"]),
        "meals": {x["BUA_AN"]: x["MUC_AN"] for x in sorted(meals_of.get(r["MA_NHAT_KY"], []), key=lambda x: x["STT"])},
        "nap": r["GIAC_NGU"] or "", "nap_minutes": r["SO_PHUT_NGU"], "mood": r["TAM_TRANG"] or "",
        "activities": r["HOAT_DONG"] or "", "health_note": r["SUC_KHOE"] or "",
        "teacher_note": r["LOI_NHAN_CUA_CO"] or "", "updated_by": r["NGUOI_CAP_NHAT"] or "",
        "updated_at": _dt_out(r["CAP_NHAT_LUC"]), "sent_at": _dt_out(r["GUI_PHU_HUYNH_LUC"]),
        "parent_seen_at": _dt_out(r["PHU_HUYNH_XEM_LUC"]), "parent_reply": r["PHU_HUYNH_PHAN_HOI"] or "",
        "parent_reply_at": _dt_out(r["PHAN_HOI_LUC"])} for r in tables.get("MN_NV_NHAT_KY_TRE", [])]
    payload["messages"] = [{
        "type": "Message", "id": r["MA_TIN_NHAN"], "kind": r["LOAI_TIN"], "content": r["NOI_DUNG"],
        "sender": r["NGUOI_GUI"] or "", "sender_role": r["VAI_TRO_NGUOI_GUI"] or "", "child_id": r["MA_TRE"],
        "class_id": r["MA_LOP"], "for_date": _date_out(r["NGAY_AP_DUNG"]), "to_date": _date_out(r["DEN_NGAY"]),
        "medicine": r["TEN_THUOC"] or "", "dosage": r["LIEU_DUNG"] or "", "time_text": r["GIO_UONG"] or "",
        "status": r["TRANG_THAI"] or "", "reply": r["TRA_LOI"] or "", "replied_by": r["NGUOI_TRA_LOI"] or "",
        "replied_at": _dt_out(r["TRA_LOI_LUC"]), "created_at": _dt_out(r["GUI_LUC"]),
        "done_at": _dt_out(r["THUC_HIEN_LUC"]), "leave_request_id": r["MA_DON_NGHI"] or ""}
        for r in tables.get("MN_NV_TIN_NHAN", [])]
    notes_of = by("MN_NV_TIET_DAY_NHAN_XET", "MA_TIET_DAY")
    payload["lesson_logs"] = [{
        "type": "LessonLog", "id": r["MA_TIET_DAY"], "date": _date_out(r["NGAY_DAY"]), "class_id": r["MA_LOP"],
        "teacher_id": r["MA_GIAO_VIEN"], "subject": r["MON_HOC"], "slot_id": r["MA_TIET"],
        "time_text": r["GIO_DAY"] or "", "content": r["NOI_DUNG"], "rating": r["DANH_GIA_CHUNG"] or "",
        "note": r["GHI_CHU"] or "", "created_by": r["NGUOI_GHI"] or "", "updated_at": _dt_out(r["CAP_NHAT_LUC"]),
        "child_notes": {x["MA_TRE"]: {"level": x["MUC_DANH_GIA"] or "", "comment": x["NHAN_XET"] or ""}
                        for x in notes_of.get(r["MA_TIET_DAY"], [])}}
        for r in tables.get("MN_NV_SO_TIET_DAY", [])]
    sources_of = by("MN_NV_BAO_CAO_NGUON", "MA_BAO_CAO")
    history_of = by("MN_NV_BAO_CAO_LICH_SU", "MA_BAO_CAO")
    reports = []
    for r in tables.get("MN_NV_BAO_CAO", []):
        params: dict[str, Any] = {}
        _put(params, "on_date", _date_out(r["KY_NGAY"]))
        _put(params, "month", r["KY_THANG"])
        _put(params, "year", r["KY_NAM"])
        _put(params, "class_id", r["MA_LOP"])
        _put(params, "class_name", r["TEN_LOP"])
        if r["CO_CHON_NGUON"]:
            params["report_ids"] = [x["MA_BAO_CAO_NGUON"] for x in sorted(sources_of.get(r["MA_BAO_CAO"], []),
                                                                         key=lambda x: x["STT"])]
        reports.append({
            "type": "SubmittedReport", "id": r["MA_BAO_CAO"], "type_key": r["LOAI_BAO_CAO"], "params": params,
            "data": json.loads(r["SO_LIEU"]) if r["SO_LIEU"] else {}, "author": r["NGUOI_LAP"],
            "author_name": r["HO_TEN_NGUOI_LAP"] or "", "author_role": r["BO_PHAN"] or "",
            "note": r["GHI_CHU"] or "", "status": r["TRANG_THAI"], "created_at": _dt_out(r["TAO_LUC"]),
            "sent_at": _dt_out(r["GUI_LUC"]), "reviewed_by": r["NGUOI_DUYET"] or "",
            "reviewed_at": _dt_out(r["DUYET_LUC"]), "review_comment": r["Y_KIEN_BGH"] or "",
            "history": [{"at": _dt_out(x["THOI_DIEM"]), "by": x["NGUOI_THUC_HIEN"] or "", "action": x["HANH_DONG"] or ""}
                        for x in sorted(history_of.get(r["MA_BAO_CAO"], []), key=lambda x: x["STT"])]})
    payload["reports"] = reports
    return payload


def _hash(rowset: Rowset) -> str:
    return hashlib.sha1(repr(sorted(rowset.items())).encode("utf-8")).hexdigest()
