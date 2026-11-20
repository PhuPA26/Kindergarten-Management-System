-- =====================================================================================================
-- TRUY VẤN MẪU - CSDL SQLite data/ql_mam_non.db
-- Mở file .db bằng DB Browser for SQLite > thẻ "Execute SQL" > dán câu lệnh > bấm ▶ (hoặc Ctrl+Return).
-- Các câu chỉ ĐỌC dữ liệu (SELECT). Dùng cho phần F1.5 Báo cáo thống kê và để kiểm tra dữ liệu.
-- =====================================================================================================

-- 1. Danh sách bảng và số dòng (SQLite không có information_schema -> dùng sqlite_master)
SELECT name AS BANG FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;

-- 2. Lần lưu dữ liệu gần nhất (ai lưu, lúc nào)
SELECT SO_PHIEN_BAN, CAP_NHAT_LUC, NGUOI_CAP_NHAT FROM MN_HT_PHIEN_BAN;

-- 3. Danh sách trẻ đang học kèm lớp, khối và giáo viên chủ nhiệm
SELECT t.MA_TRE, t.HO_TEN, t.TEN_O_NHA, t.NGAY_SINH, t.GIOI_TINH, l.TEN_LOP, k.TEN_KHOI, gv.HO_TEN AS GV_CHU_NHIEM
FROM MN_DM_TRE t
LEFT JOIN MN_DM_LOP_HOC l ON l.MA_LOP = t.MA_LOP
LEFT JOIN MN_DM_KHOI_LOP k ON k.MA_KHOI = l.MA_KHOI
LEFT JOIN MN_DM_NHAN_SU gv ON gv.MA_NHAN_SU = l.MA_GV_CHU_NHIEM
WHERE t.TRANG_THAI = 'Đang học'
ORDER BY l.TEN_LOP, t.HO_TEN;

-- 4. Phụ huynh của từng trẻ (quan hệ n-n qua bảng trung gian)
SELECT t.HO_TEN AS TRE, ph.QUAN_HE, ph.HO_TEN AS PHU_HUYNH, ph.SO_DIEN_THOAI, ph.NGHE_NGHIEP
FROM MN_DM_TRE t
JOIN MN_DM_TRE_PHU_HUYNH tp ON tp.MA_TRE = t.MA_TRE
JOIN MN_DM_PHU_HUYNH ph ON ph.MA_PHU_HUYNH = tp.MA_PHU_HUYNH
ORDER BY t.HO_TEN, tp.THU_TU;

-- 5. Sĩ số từng lớp so với chỉ tiêu
SELECT l.TEN_LOP, l.SI_SO_TOI_DA, COUNT(t.MA_TRE) AS SI_SO, l.SI_SO_TOI_DA - COUNT(t.MA_TRE) AS CON_TRONG
FROM MN_DM_LOP_HOC l
LEFT JOIN MN_DM_TRE t ON t.MA_LOP = l.MA_LOP AND t.TRANG_THAI = 'Đang học'
GROUP BY l.MA_LOP, l.TEN_LOP, l.SI_SO_TOI_DA ORDER BY l.TEN_LOP;

-- 6. Điểm danh / đón - trả trẻ HÔM NAY
SELECT l.TEN_LOP, t.HO_TEN, d.TRANG_THAI, time(d.GIO_DEN) AS GIO_DEN, d.NGUOI_DUA,
       time(d.GIO_VE) AS GIO_VE, d.NGUOI_DON, d.GHI_CHU
FROM MN_NV_DIEM_DANH d
JOIN MN_DM_TRE t ON t.MA_TRE = d.MA_TRE
LEFT JOIN MN_DM_LOP_HOC l ON l.MA_LOP = d.MA_LOP
WHERE d.NGAY = date('now', 'localtime')
ORDER BY l.TEN_LOP, t.HO_TEN;

-- 7. Tỷ lệ chuyên cần tháng này theo trẻ
SELECT t.HO_TEN, l.TEN_LOP,
       SUM(d.TRANG_THAI = 'PRESENT') AS CO_MAT, SUM(d.TRANG_THAI = 'EXCUSED') AS CO_PHEP,
       SUM(d.TRANG_THAI = 'UNEXCUSED') AS KHONG_PHEP,
       ROUND(100.0 * SUM(d.TRANG_THAI = 'PRESENT') / COUNT(*), 1) AS TY_LE_PHAN_TRAM
FROM MN_NV_DIEM_DANH d
JOIN MN_DM_TRE t ON t.MA_TRE = d.MA_TRE
LEFT JOIN MN_DM_LOP_HOC l ON l.MA_LOP = t.MA_LOP
WHERE strftime('%Y-%m', d.NGAY) = strftime('%Y-%m', 'now', 'localtime')
GROUP BY t.MA_TRE, t.HO_TEN, l.TEN_LOP
ORDER BY TY_LE_PHAN_TRAM;

-- 8. Hóa đơn: phải thu - miễn giảm - đã thu (thành tiền = DON_GIA x IFNULL(SO_LUONG, 1) tính khi truy vấn,
--    không lưu cột riêng để đạt BCNF; bỏ phiếu thu đã hủy)
SELECT h.MA_HOA_DON, h.TEN_TRE, h.TEN_LOP, printf('%02d/%d', h.THANG, h.NAM) AS KY, h.HAN_NOP,
       pt.TONG_PHI,
       MIN(pt.HOC_PHI, ROUND(pt.HOC_PHI * IFNULL(h.TY_LE_GIAM, 0)) + IFNULL(h.SO_TIEN_GIAM, 0)) AS MIEN_GIAM,
       IFNULL(thu.DA_THU, 0) AS DA_THU
FROM MN_NV_HOA_DON h
JOIN (SELECT MA_HOA_DON, SUM(DON_GIA * IFNULL(SO_LUONG, 1)) AS TONG_PHI,
             SUM(CASE WHEN LOAI_PHI = 'MonthlyFee' THEN DON_GIA * IFNULL(SO_LUONG, 1) ELSE 0 END) AS HOC_PHI
      FROM MN_NV_HOA_DON_KHOAN_PHI GROUP BY MA_HOA_DON) pt ON pt.MA_HOA_DON = h.MA_HOA_DON
LEFT JOIN (SELECT MA_HOA_DON, SUM(SO_TIEN) AS DA_THU FROM MN_NV_PHIEU_THU WHERE DA_HUY = 0
           GROUP BY MA_HOA_DON) thu ON thu.MA_HOA_DON = h.MA_HOA_DON
ORDER BY h.NAM DESC, h.THANG DESC, h.TEN_TRE;

-- 9. Doanh thu thực thu theo tháng (ngày thu tiền)
SELECT strftime('%Y-%m', NGAY_THU) AS THANG, COUNT(*) AS SO_PHIEU, SUM(SO_TIEN) AS THUC_THU
FROM MN_NV_PHIEU_THU WHERE DA_HUY = 0
GROUP BY strftime('%Y-%m', NGAY_THU) ORDER BY THANG DESC;

-- 10. Trẻ đăng ký dịch vụ tự chọn và tiền dịch vụ mỗi tháng
SELECT dv.TEN_DICH_VU, dv.DON_GIA, COUNT(dk.MA_TRE) AS SO_TRE, dv.DON_GIA * COUNT(dk.MA_TRE) AS TIEN_MOI_THANG
FROM MN_DM_DICH_VU dv LEFT JOIN MN_NV_DANG_KY_DICH_VU dk ON dk.TEN_DICH_VU = dv.TEN_DICH_VU
GROUP BY dv.TEN_DICH_VU, dv.DON_GIA ORDER BY SO_TRE DESC;

-- 11. Thực đơn tuần này và cảnh báo dị ứng (món có nguyên liệu trẻ bị dị ứng)
SELECT td.NGAY, ct.BUA_AN, m.TEN_MON, t.HO_TEN AS TRE_DI_UNG, du.CHAT_GAY_DI_UNG, du.MUC_DO
FROM MN_NV_THUC_DON td
JOIN MN_NV_THUC_DON_CHI_TIET ct ON ct.MA_THUC_DON = td.MA_THUC_DON
JOIN MN_DM_MON_AN m ON m.MA_MON = ct.MA_MON
JOIN MN_DM_THANH_PHAN_MON tp ON tp.MA_MON = m.MA_MON
JOIN MN_NV_DI_UNG du ON tp.TEN_THANH_PHAN LIKE '%' || du.CHAT_GAY_DI_UNG || '%'
JOIN MN_DM_TRE t ON t.MA_TRE = du.MA_TRE AND t.TRANG_THAI = 'Đang học'
WHERE td.NGAY BETWEEN date('now', 'localtime', 'weekday 1', '-7 days') AND date('now', 'localtime', 'weekday 0')
ORDER BY td.NGAY, ct.BUA_AN;

-- 12. Trẻ cần chú ý dinh dưỡng: lần cân đo gần nhất và chỉ số BMI
SELECT t.HO_TEN, l.TEN_LOP, cd.NGAY_DO, cd.CHIEU_CAO_CM, cd.CAN_NANG_KG,
       ROUND(cd.CAN_NANG_KG / ((cd.CHIEU_CAO_CM / 100.0) * (cd.CHIEU_CAO_CM / 100.0)), 1) AS BMI
FROM MN_NV_CAN_DO cd
JOIN (SELECT MA_TRE, MAX(NGAY_DO) AS NGAY_DO FROM MN_NV_CAN_DO GROUP BY MA_TRE) moi
     ON moi.MA_TRE = cd.MA_TRE AND moi.NGAY_DO = cd.NGAY_DO
JOIN MN_DM_TRE t ON t.MA_TRE = cd.MA_TRE
LEFT JOIN MN_DM_LOP_HOC l ON l.MA_LOP = t.MA_LOP
ORDER BY BMI;

-- 13. Nhật ký ăn ngủ đã gửi phụ huynh 7 ngày gần nhất, kèm mức ăn từng bữa
SELECT nk.NGAY, t.HO_TEN,
       (SELECT GROUP_CONCAT(BUA_AN || ': ' || MUC_AN, '; ')
        FROM (SELECT BUA_AN, MUC_AN FROM MN_NV_NHAT_KY_BUA_AN ba WHERE ba.MA_NHAT_KY = nk.MA_NHAT_KY ORDER BY STT))
           AS AN_UONG,
       nk.GIAC_NGU, nk.SO_PHUT_NGU, nk.TAM_TRANG, nk.LOI_NHAN_CUA_CO, nk.PHU_HUYNH_PHAN_HOI
FROM MN_NV_NHAT_KY_TRE nk
JOIN MN_DM_TRE t ON t.MA_TRE = nk.MA_TRE
WHERE nk.GUI_PHU_HUYNH_LUC IS NOT NULL AND nk.NGAY >= date('now', 'localtime', '-7 days')
ORDER BY nk.NGAY DESC, t.HO_TEN;

-- 14. Báo cáo các bộ phận gửi Ban giám hiệu và trạng thái duyệt
SELECT MA_BAO_CAO, LOAI_BAO_CAO, HO_TEN_NGUOI_LAP, BO_PHAN, TRANG_THAI, GUI_LUC, Y_KIEN_BGH
FROM MN_NV_BAO_CAO ORDER BY GUI_LUC DESC;

-- 15. Nhật ký thao tác gần nhất (ai làm gì, lúc nào)
SELECT THOI_DIEM, TEN_DANG_NHAP, HANH_DONG, DOI_TUONG
FROM MN_HT_NHAT_KY_THAO_TAC ORDER BY MA_NHAT_KY DESC LIMIT 50;
