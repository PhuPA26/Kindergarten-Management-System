# Hướng dẫn dùng CSDL SQLite khi làm nhóm 2 người

## CSDL nằm ở đâu

Toàn bộ dữ liệu (43 bảng) nằm trong **một file duy nhất**: `data/ql_mam_non.db`.
- Không cần cài MySQL hay bất kỳ máy chủ nào: SQLite có sẵn trong Python.
- Chương trình tự tạo file này ở lần chạy đầu. Nếu thư mục `data/` có các file JSON cũ, chương trình tự chuyển chúng sang.
- Muốn mở một file CSDL khác (ví dụ file bạn cùng nhóm gửi): `python main.py --gui --db D:\duong_dan\ql_mam_non.db`.

## Xem và sửa các bảng không cần gõ lệnh: DB Browser for SQLite

1. Tải bản miễn phí ở <https://sqlitebrowser.org/dl/> (Windows: *DB Browser for SQLite - Standard installer for 64-bit Windows*).
2. Mở chương trình, bấm **Open Database** và chọn file `data\ql_mam_non.db`.
3. Có 4 thẻ:
   - **Database Structure**: danh sách 43 bảng, các cột, khóa chính / khóa ngoại.
   - **Browse Data**: chọn bảng trong ô *Table*, dữ liệu hiện như Excel. Bấm tiêu đề cột để sắp xếp, gõ vào ô *Filter* để lọc.
   - **Execute SQL**: dán câu lệnh trong `03_truy_van_mau.sql` rồi bấm ▶.
   - **Edit Pragmas**: các thiết lập của file CSDL.
4. Nếu sửa dữ liệu trong *Browse Data*, nhớ bấm **Write Changes** (Ctrl+S) để ghi.

> **Lưu ý khi sửa bằng DB Browser:** hãy **tắt chương trình quản lý trước**. Chương trình giữ dữ liệu trong bộ nhớ; nếu
> đang mở mà bạn sửa bằng DB Browser, chương trình không biết. Lần sau nó lưu đúng bản ghi đó thì sẽ ghi đè lên chỗ
> bạn vừa sửa. Chỉ xem thì mở song song thoải mái.
>
> Ngược lại, khi DB Browser còn **thay đổi chưa ghi** (chưa bấm Write Changes), file bị khóa, chương trình sẽ báo
> không lưu được. Bấm *Write Changes* hoặc *Revert Changes* là hết.

## Hai người làm việc thế nào

SQLite là CSDL dạng file, **không có máy chủ** nên hai máy không kết nối trực tiếp vào nhau được như MySQL. Cũng
**không nên** để file `.db` trong thư mục đồng bộ (OneDrive, Google Drive, Dropbox) rồi hai người cùng mở: hai bên
cùng ghi thì file dễ bị xung đột hoặc hỏng.

Cách làm khuyến nghị:

| Việc | Cách làm |
|---|---|
| Mã nguồn | Chia sẻ qua Git / GitHub như bình thường. Thư mục `data/` (chứa file `.db`) đã nằm trong `.gitignore`, nên mỗi người có file dữ liệu riêng trên máy mình |
| Mỗi người có dữ liệu để chạy thử | Chạy `python main.py --seed` để tạo dữ liệu mẫu giống nhau (20 trẻ, 3 lớp...) |
| Cần dùng đúng dữ liệu của bạn kia | Bạn kia **tắt chương trình**, gửi file `data\ql_mam_non.db` (qua Zalo, Drive, USB...). Bạn **tắt chương trình**, chép đè vào `data\` của mình (nên đổi tên file cũ thành `ql_mam_non_cu.db` trước để giữ lại) |
| Chọn một "bản chính" | Thống nhất một người giữ file dữ liệu chính (VD để nộp / demo). Người kia sửa thì gửi lại file, hoặc gửi danh sách việc cần sửa để người giữ file làm |
| Sao lưu | Trong chương trình: *Quản trị hệ thống → Hệ thống → Sao lưu dữ liệu* (tạo một file `.db` hoàn chỉnh trong `data\backups\`, chụp được cả khi chương trình đang mở; mở được bằng DB Browser). Hoặc đơn giản là chép file `.db` khi chương trình đang tắt |
| Sửa thiết kế bảng | Sửa trong `kindergarten/storage/schema.py`, chạy `python Database/sinh_tai_lieu_csdl.py` để cập nhật tài liệu, đẩy code lên Git. Báo người kia `git pull` |

Trên **cùng một máy**, có thể mở 2 cửa sổ chương trình trên cùng file. Mỗi cửa sổ tự nhận thay đổi của cửa sổ kia
sau vài giây (nhờ bảng `MN_HT_PHIEN_BAN`), và không ghi đè khi cả hai cùng thêm mới trùng mã.

## Lỗi thường gặp

| Thông báo | Nguyên nhân / cách sửa |
|---|---|
| *database is locked* / *Không ghi được dữ liệu vào CSDL* | DB Browser (hoặc chương trình khác) đang giữ thay đổi chưa ghi trên file. Bấm *Write Changes* / *Revert Changes* trong DB Browser, rồi bấm *Lưu dữ liệu* lại |
| Mở chương trình thấy trống / mất dữ liệu | Đang mở nhầm file (`--db`), hoặc chép file `.db` khi chương trình kia còn đang chạy. Tắt hết rồi chép lại; kiểm tra `data\backups\` |
| *Không mở được file CSDL* | Đường dẫn sai, thư mục không có quyền ghi, hoặc file đang được đồng bộ / bị phần mềm diệt virus khóa |
