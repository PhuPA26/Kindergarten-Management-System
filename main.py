"""T32 - main.py: ghép tất cả các module, chạy chương trình từ đầu đến cuối.

Dữ liệu được lưu trong CSDL SQLite - một file duy nhất data/ql_mam_non.db (tự tạo ở lần chạy đầu, không cần cài
máy chủ CSDL). Xem / sửa bảng bằng "DB Browser for SQLite".

Cách chạy (trong thư mục dự án):
    python main.py              # giao diện console, menu theo vai trò đăng nhập
    python main.py --gui        # giao diện đồ họa Tkinter (T34)
    python main.py --seed       # nạp lại dữ liệu mẫu (hỏi xác nhận + tự sao lưu nếu đã có dữ liệu)
    python main.py --seed --yes # như trên nhưng không hỏi (dùng trong script)
    python main.py --db D:\\du_lieu_cua_ban.db   # mở một file CSDL khác (VD file bạn cùng nhóm gửi)
    python main.py --json       # chạy bằng file JSON trong thư mục data/ (chế độ cũ, dùng cho kiểm thử)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from kindergarten import APP_NAME  # noqa: E402
from kindergarten.exceptions import DataStoreError  # noqa: E402
from kindergarten.storage.datastore import DataStore  # noqa: E402
from kindergarten.system import KindergartenSystem  # noqa: E402
from seed_data import DEMO_ACCOUNTS, seed  # noqa: E402


def configure_console() -> None:
    """Đảm bảo in được tiếng Việt kể cả khi chuyển hướng output ra file."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--gui", action="store_true", help="chạy giao diện đồ họa Tkinter")
    parser.add_argument("--seed", action="store_true",
                        help="nạp dữ liệu mẫu (dữ liệu hiện có được sao lưu trước, cần xác nhận)")
    parser.add_argument("--yes", "-y", action="store_true", help="không hỏi xác nhận khi dùng --seed")
    parser.add_argument("--db", default=None, help="đường dẫn file CSDL SQLite (mặc định data/ql_mam_non.db)")
    parser.add_argument("--json", action="store_true", help="dùng file JSON thay cho SQLite (chế độ cũ)")
    parser.add_argument("--config", type=Path, help="tệp cấu hình JSON (mặc định appsettings.json nếu có)")
    parser.add_argument("--data-dir",
                        help="thư mục chứa file CSDL, bản sao lưu (và dữ liệu khi chạy --json)")
    args = parser.parse_args(argv)
    config_file = args.config or BASE_DIR / "appsettings.json"
    config = {}
    if args.config or config_file.is_file():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8-sig"))
            if not isinstance(config, dict):
                raise ValueError("cần một đối tượng JSON")
            for name in ("data_dir", "db"):
                if name in config and config[name] is not None and (
                    not isinstance(config[name], str) or not config[name].strip()
                ):
                    raise ValueError(f"{name} phải là một đường dẫn hoặc null")
        except (OSError, ValueError) as exc:
            parser.error(f"Cấu hình {config_file}: {exc}")

    for name in ("data_dir", "db"):
        value = config.get(name)
        if getattr(args, name) is None and value is not None:
            setattr(args, name, str(config_file.parent / value))
    args.data_dir = args.data_dir or str(BASE_DIR / "data")
    return args


def open_store(args: argparse.Namespace) -> Any:
    """Mở file CSDL SQLite (tự tạo file và các bảng nếu chưa có)."""
    if args.json:
        return DataStore(args.data_dir)
    from kindergarten.storage.sqlite_store import SQLiteDataStore
    return SQLiteDataStore(args.data_dir, args.db)


def migrate_json(system: KindergartenSystem, data_dir: str) -> None:
    """Lần đầu dùng CSDL: chuyển dữ liệu từ các file JSON cũ trong data/ (nếu có). File JSON được giữ nguyên."""
    store = system.store
    if getattr(store, "backend", "") != "sqlite" or store.has_data() or not DataStore(data_dir).has_data():
        return
    if store.import_json(data_dir, system):
        print(f"Đã chuyển dữ liệu JSON trong {data_dir} sang {store.location}.")


def prepare_reseed(system: KindergartenSystem, assume_yes: bool = False,
                   ask: Callable[[str], str] = input) -> bool:
    """L02: --seed không còn xóa im lặng dữ liệu thật - hỏi xác nhận và sao lưu trước."""
    if not system.store.has_data():
        return True
    where = getattr(system.store, "location", system.store.data_dir)
    if not assume_yes:
        try:
            answer = ask(f"{where} ĐÃ CÓ DỮ LIỆU. Thay bằng dữ liệu mẫu? (dữ liệu cũ sẽ được sao lưu) [y/N]: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes", "c", "co", "có"):
            print("Đã hủy - dữ liệu hiện có được giữ nguyên. (Dùng --seed --yes để bỏ qua câu hỏi.)")
            return False
    backup = system.store.backup("truoc_khi_nap_mau")
    print(f"Đã sao lưu dữ liệu cũ vào {backup}")
    return True


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    try:
        store = open_store(args)
    except DataStoreError as exc:
        print(f"[LỖI] {exc}")
        return 1
    system = KindergartenSystem(args.data_dir, store=store)
    if args.seed:
        if not prepare_reseed(system, args.yes):
            return 1
        counts = seed(system)
        system.save()
        print("Đã nạp dữ liệu mẫu: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    else:
        try:
            migrate_json(system, args.data_dir)
            system.load()  # T30: mở lại chương trình vẫn còn dữ liệu
        except DataStoreError as exc:
            print(f"[LỖI] {exc}")
            print("Gợi ý: kiểm tra file CSDL (--db) hoặc chạy 'python main.py --seed' để tạo dữ liệu mẫu.")
            return 1

    if args.gui:
        from kindergarten.ui.gui.app import run_gui
        run_gui(system, seed_func=seed, demo_accounts=DEMO_ACCOUNTS)
    else:
        from kindergarten.ui.console.main_menu import MainMenu
        MainMenu(system, seed_func=seed, demo_accounts=DEMO_ACCOUNTS).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
