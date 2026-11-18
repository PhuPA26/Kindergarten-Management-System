# Dlllib - thư viện ngoài

Solution Folder theo *Hướng dẫn xây dựng HTTTQL* (mục IV. Cài đặt - Solution Convention: `Database`, `Dlllib`, `Resource`).

Với bản C#/.NET, thư mục này chứa các file `.dll` dùng chung. Dự án này viết bằng **Python** và **chỉ dùng thư viện
chuẩn** đi kèm Python, nên thư mục để trống:

| Thư viện | Dùng cho | Có sẵn trong Python? |
|---|---|---|
| `tkinter` | Giao diện cửa sổ | Có |
| `sqlite3` | CSDL SQLite (`data/ql_mam_non.db`) | Có |
| `pytest` | Chạy kiểm thử tự động | Không - cài bằng `pip install -r requirements.txt` |

Nếu sau này cần thư viện ngoài không cài được qua `pip` (VD gói `.whl` tải tay), đặt vào đây và ghi thêm vào bảng trên.
