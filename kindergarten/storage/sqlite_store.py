"""Lưu trữ bằng SQLite - toàn bộ CSDL nằm trong MỘT file (mặc định data/ql_mam_non.db), không cần cài máy chủ.

Thiết kế bảng: schema.py (43 bảng chuẩn hóa, tài liệu Database/thiet_ke_csdl.md). Xem / sửa bảng bằng
"DB Browser for SQLite" (mở thẳng file .db).

Ghi dữ liệu:
- Đơn vị so sánh là một "tập dòng" của mỗi đối tượng (dòng chính + các dòng chi tiết của nó). Chỉ đối tượng
  thay đổi mới được ghi: cập nhật dòng chính bằng UPSERT (INSERT ... ON CONFLICT DO UPDATE - không xóa rồi chèn lại
  nên không kích hoạt xóa dây chuyền), xóa rồi ghi lại các dòng chi tiết. Tất cả trong MỘT giao dịch
  (BEGIN IMMEDIATE ... COMMIT) - lỗi giữa chừng thì ROLLBACK, file CSDL giữ nguyên trạng cũ.
- Khóa ngoại được bật (PRAGMA foreign_keys = ON) nên ràng buộc ON DELETE / ON UPDATE hoạt động như thiết kế.
- MN_HT_PHIEN_BAN giữ số phiên bản dữ liệu: nếu mở hai cửa sổ chương trình trên cùng file, cửa sổ này biết
  cửa sổ kia vừa lưu và tự tải lại; hai bên cùng thêm mới trùng mã thì lần lưu sau bị từ chối, không ghi đè.
"""
from __future__ import annotations

import json
import shutil
import socket
import sqlite3
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from ..core.base_model import BaseModel
from ..exceptions import DataStoreError
from ..finance.settings import FeeSettings
from ..school_calendar import SchoolCalendar
from .datastore import LOAD_ERRORS, DataStore
from .schema import (DATABASE_NAME, ENTITIES, SCHEMA_VERSION, TABLE_LIST, TABLES, Rowset, Table, _decode, _hash,
                     _pickup_identity, _rows_of, pickup_person_id)

if TYPE_CHECKING:
    from ..system import KindergartenSystem

DB_FILE = f"{DATABASE_NAME}.db"
CONFLICT_MESSAGE = ("Một cửa sổ chương trình khác vừa thêm dữ liệu trùng mã với dữ liệu bạn đang lưu. Để không ghi "
                    "đè lên dữ liệu đó, thao tác vừa rồi CHƯA được lưu. Chương trình đã tải lại dữ liệu mới nhất - "
                    "bạn hãy thực hiện lại thao tác.")

# Kiểu ngày giờ: lưu dạng văn bản ISO ('2026-11-17', '2026-11-17 07:25:00'), đọc ra lại thành date / datetime
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(datetime, lambda d: d.isoformat(" "))
sqlite3.register_adapter(time, lambda t: t.strftime("%H:%M"))
sqlite3.register_adapter(Decimal, lambda d: float(d))
sqlite3.register_converter("DATE", lambda b: date.fromisoformat(b.decode()))
sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode()))
sqlite3.register_converter("TIME", lambda b: time.fromisoformat(b.decode()))
sqlite3.register_converter("DECIMAL", lambda b: Decimal(b.decode()))


# =============================================================================
# Câu lệnh tạo bảng (SQLite)
# =============================================================================
def _q(name: str) -> str:
    return f'"{name}"'


def table_sql(table: Table) -> str:
    lines = []
    single_auto = len(table.pk) == 1 and any(c.auto and c.name == table.pk[0] for c in table.cols)
    for col in table.cols:
        comment = f" /* {col.comment} */"
        if col.auto:
            lines.append(f"  {_q(col.name)} INTEGER PRIMARY KEY AUTOINCREMENT{comment}")
            continue
        if col.generated:
            lines.append(f"  {_q(col.name)} {col.sql} GENERATED ALWAYS AS ({col.generated}) STORED{comment}")
            continue
        null = "" if col.null else " NOT NULL"
        default = f" DEFAULT {col.default}" if col.default is not None else ""
        lines.append(f"  {_q(col.name)} {col.sql}{null}{default}{comment}")
    if not single_auto:
        lines.append("  CONSTRAINT " + _q(f"PK_{table.name}") + " PRIMARY KEY (" + ", ".join(map(_q, table.pk)) + ")")
    for cols in table.uniques:
        lines.append("  CONSTRAINT " + _q(f"UQ_{table.name}_{'_'.join(cols)}") + " UNIQUE ("
                     + ", ".join(map(_q, cols)) + ")")
    for i, (cols, ref, ref_cols, on_delete) in enumerate(table.fks, 1):
        lines.append("  CONSTRAINT " + _q(f"FK_{table.name}_{i}") + " FOREIGN KEY (" + ", ".join(map(_q, cols))
                     + f") REFERENCES {_q(ref)} (" + ", ".join(map(_q, ref_cols))
                     + f") ON DELETE {on_delete} ON UPDATE CASCADE")
    for i, check in enumerate(table.checks, 1):
        lines.append("  CONSTRAINT " + _q(f"CK_{table.name}_{i}") + f" CHECK ({check})")
    return (f"CREATE TABLE IF NOT EXISTS {_q(table.name)} ( /* {table.comment} */\n" + ",\n".join(lines) + "\n)")


def index_sql(table: Table) -> list[str]:
    return [f"CREATE INDEX IF NOT EXISTS {_q('IX_' + table.name + '_' + '_'.join(cols))} ON {_q(table.name)} ("
            + ", ".join(map(_q, cols)) + ")" for cols in table.indexes]


def create_table_sql() -> list[str]:
    """Câu lệnh tạo bảng theo thứ tự phụ thuộc khóa ngoại (bảng được tham chiếu tạo trước) + chỉ mục."""
    order: list[str] = []
    pending = list(TABLES)
    while pending:
        for name in list(pending):
            refs = {ref for _c, ref, _r, _d in TABLES[name].fks if ref != name}
            if refs <= set(order):
                order.append(name)
                pending.remove(name)
    return [table_sql(TABLES[n]) for n in order] + [s for n in order for s in index_sql(TABLES[n])]


# =============================================================================
# Nâng cấp CSDL tạo bởi bản cũ (VD v2 -> v3: tách người đón hộ, bỏ cột THANH_TIEN, LOAI để đạt BCNF)
# =============================================================================
OLD_SUFFIX = "_CU"


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_xinfo({_q(table)})")]   # xinfo: kể cả cột tính toán


def _upgrade_before(conn: sqlite3.Connection) -> list[str]:
    """Bảng có danh sách cột khác thiết kế hiện tại -> đổi tên thành <bảng>_CU để tạo lại đúng thiết kế;
    dữ liệu được chép sang ở _upgrade_after. Trả về tên các bảng đã đổi."""
    existing = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    moved = []
    for table in TABLE_LIST:
        if table.name in existing and _columns(conn, table.name) != [c.name for c in table.cols]:
            conn.execute(f"DROP TABLE IF EXISTS {_q(table.name + OLD_SUFFIX)}")
            conn.execute(f"ALTER TABLE {_q(table.name)} RENAME TO {_q(table.name + OLD_SUFFIX)}")
            moved.append(table.name)
    return moved


def _upgrade_after(conn: sqlite3.Connection, moved: list[str]) -> None:
    """Chép dữ liệu từ bảng <bảng>_CU sang bảng mới (các cột còn giữ) rồi xóa bảng cũ."""
    for name in moved:
        old = name + OLD_SUFFIX
        old_cols = _columns(conn, old)
        if name == "MN_DM_NGUOI_DON_HO" and "MA_TRE" in old_cols:
            _migrate_pickups(conn, old)
        else:
            keep = ", ".join(_q(c) for c in TABLES[name].insert_cols if c in old_cols)
            conn.execute(f"INSERT INTO {_q(name)} ({keep}) SELECT {keep} FROM {_q(old)}")
        conn.execute(f"DROP TABLE {_q(old)}")
        for statement in index_sql(TABLES[name]):   # chỉ mục cũ đã bị xóa cùng bảng _CU
            conn.execute(statement)


def _migrate_pickups(conn: sqlite3.Connection, old: str) -> None:
    """v2: một dòng người đón hộ cho MỖI trẻ (lặp thông tin khi một người đón nhiều trẻ) ->
    v3: MN_DM_NGUOI_DON_HO (mỗi người một dòng) + MN_DM_TRE_NGUOI_DON_HO (quan hệ với từng trẻ)."""
    rows = conn.execute(f'SELECT "MA_TRE", "STT", "HO_TEN", "QUAN_HE", "SO_DIEN_THOAI", "SO_CCCD" FROM {_q(old)} '
                        'ORDER BY "MA_TRE", "STT"').fetchall()
    for child_id, order, name, relationship, phone, card in rows:
        key = pickup_person_id(_pickup_identity({"full_name": name, "phone": phone, "id_card": card}))
        conn.execute('INSERT OR IGNORE INTO "MN_DM_NGUOI_DON_HO" ("MA_NGUOI_DON", "HO_TEN", "SO_DIEN_THOAI", '
                     '"SO_CCCD") VALUES (?, ?, ?, ?)', (key, name, phone or "", card or None))
        conn.execute('INSERT OR IGNORE INTO "MN_DM_TRE_NGUOI_DON_HO" ("MA_TRE", "MA_NGUOI_DON", "STT", "QUAN_HE") '
                     'VALUES (?, ?, ?, ?)', (child_id, key, order, relationship or ""))


# =============================================================================
class SQLiteDataStore:
    """Cùng giao diện với DataStore (JSON) nên các phần khác của chương trình không phải đổi."""

    backend = "sqlite"
    KEEP_BACKUPS = DataStore.KEEP_BACKUPS

    def __init__(self, data_dir: str | Path = "data", db_path: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir)             # thư mục chứa file CSDL; bản sao lưu .db nằm trong backups/
        self.backup_dir = self.data_dir / "backups"
        self.path = Path(db_path) if db_path else self.data_dir / DB_FILE
        self._hashes: dict[str, dict[str, str]] | None = None   # None = chưa biết CSDL đang có những dòng nào
        self._revision: int | None = None          # phiên bản dữ liệu lúc nạp / lưu gần nhất
        self.needs_reload = False                  # cửa sổ khác đã thay đổi dữ liệu -> nên tải lại
        self.last_writer = ""
        self._connection: sqlite3.Connection | None = None
        self.ensure_schema()

    # ------------------------------------------------------------------ kết nối, lược đồ
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES, isolation_level=None,
                                       timeout=10)
                conn.execute("PRAGMA foreign_keys = ON")
            except (sqlite3.Error, OSError) as exc:
                raise DataStoreError(f"Không mở được file CSDL '{self.path}': {exc}") from exc
            self._connection = conn
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def ensure_schema(self) -> None:
        conn = self.connection()
        # đổi tên bảng khi nâng cấp: KHÔNG sửa theo tên mới ở khóa ngoại của bảng khác (bảng sẽ được tạo lại)
        conn.execute("PRAGMA legacy_alter_table = ON")
        try:
            conn.execute("BEGIN")
            moved = _upgrade_before(conn)
            for statement in create_table_sql():
                conn.execute(statement)
            _upgrade_after(conn, moved)
            conn.execute('INSERT OR IGNORE INTO "MN_HT_PHIEN_BAN" ("MA_PHIEN_BAN", "SO_PHIEN_BAN", '
                         '"PHIEN_BAN_LUOC_DO") VALUES (1, 0, ?)', (SCHEMA_VERSION,))
            if moved:
                conn.execute('UPDATE "MN_HT_PHIEN_BAN" SET "PHIEN_BAN_LUOC_DO" = ? WHERE "MA_PHIEN_BAN" = 1',
                             (SCHEMA_VERSION,))
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise DataStoreError(f"Không tạo được bảng trong '{self.path}': {exc}") from exc
        finally:
            conn.execute("PRAGMA legacy_alter_table = OFF")

    def _query(self, sql: str, args: Any = ()) -> list[tuple]:
        try:
            return list(self.connection().execute(sql, args).fetchall())
        except sqlite3.Error as exc:
            raise DataStoreError(f"Lỗi đọc CSDL: {exc}") from exc

    def has_data(self) -> bool:
        try:
            return bool(self._query('SELECT COUNT(*) FROM "MN_HT_TAI_KHOAN"')[0][0])
        except DataStoreError:
            return False

    @property
    def location(self) -> str:
        return f"SQLite {self.path.resolve()}"

    # ------------------------------------------------------------------ nhiều cửa sổ cùng một file
    def remote_revision(self) -> tuple[int, str]:
        rows = self._query('SELECT "SO_PHIEN_BAN", "NGUOI_CAP_NHAT" FROM "MN_HT_PHIEN_BAN" WHERE "MA_PHIEN_BAN" = 1')
        return (int(rows[0][0]), rows[0][1] or "") if rows else (0, "")

    def has_remote_changes(self) -> bool:
        """Cửa sổ chương trình khác đã lưu thay đổi kể từ lần nạp / lưu gần nhất của mình chưa."""
        if self._revision is None:
            return False
        try:
            revision, writer = self.remote_revision()
        except DataStoreError:
            return False
        self.last_writer = writer
        return revision != self._revision

    @staticmethod
    def _writer(system: "KindergartenSystem") -> str:
        return f"{system.username or '(hệ thống)'} @ {socket.gethostname()}"[:150]

    # ------------------------------------------------------------------ ghi
    def save_all(self, system: "KindergartenSystem", force: bool = False) -> str:
        """Ghi các đối tượng thay đổi trong MỘT giao dịch. force=True: ghi đè (khôi phục, nạp dữ liệu mẫu)."""
        if self._hashes is None:   # chưa đọc từ CSDL (VD: nạp dữ liệu mẫu) -> lấy danh sách mã hiện có để xóa đúng
            self._hashes = self._existing_keys()
        current = _rows_of(system)
        changed: dict[str, dict[str, Rowset]] = {}
        removed: dict[str, list[str]] = {}
        new_hashes: dict[str, dict[str, str]] = {}
        for entity in ENTITIES:
            old = self._hashes.get(entity.name, {})
            items = current[entity.name]
            digests = {key: _hash(rows) for key, rows in items.items()}
            changed[entity.name] = {k: items[k] for k, h in digests.items() if old.get(k) != h}
            removed[entity.name] = [k for k in old if k not in items]
            new_hashes[entity.name] = digests
        conn = self.connection()
        try:
            conn.execute("BEGIN IMMEDIATE")   # giữ quyền ghi ngay từ đầu: hai cửa sổ lưu cùng lúc sẽ lần lượt
            revision = int(conn.execute('SELECT "SO_PHIEN_BAN" FROM "MN_HT_PHIEN_BAN" WHERE "MA_PHIEN_BAN" = 1')
                           .fetchone()[0])
            others = self._revision is not None and revision != self._revision
            if not any(changed.values()) and not any(removed.values()):
                conn.execute("ROLLBACK")
                self.needs_reload = others
                return self.location
            if others and not force:
                self._check_conflicts(conn, changed)
            self._write(conn, changed, removed)
            conn.executemany(
                'INSERT INTO "MN_HT_BO_DEM_MA" ("TIEN_TO", "GIA_TRI_HIEN_TAI") VALUES (?, ?) ON CONFLICT ("TIEN_TO") '
                'DO UPDATE SET "GIA_TRI_HIEN_TAI" = MAX("GIA_TRI_HIEN_TAI", excluded."GIA_TRI_HIEN_TAI")',
                list(BaseModel.counters().items()))
            conn.execute('UPDATE "MN_HT_PHIEN_BAN" SET "SO_PHIEN_BAN" = ?, "CAP_NHAT_LUC" = ?, "NGUOI_CAP_NHAT" = ?, '
                         '"PHIEN_BAN_LUOC_DO" = ? WHERE "MA_PHIEN_BAN" = 1',
                         (revision + 1, datetime.now().replace(microsecond=0), self._writer(system), SCHEMA_VERSION))
            conn.execute("COMMIT")
        except DataStoreError:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")   # L21: không để CSDL ở trạng thái nửa cũ nửa mới
            raise DataStoreError(f"Không ghi được dữ liệu vào CSDL: {exc}") from exc
        self._hashes = new_hashes
        self._revision = revision + 1
        self.needs_reload = others and not force
        return self.location

    def pending_changes(self, system: "KindergartenSystem") -> int:
        """Số đối tượng trong bộ nhớ đã thay đổi / bị xóa mà CHƯA ghi vào CSDL (0 = đã lưu hết)."""
        if self._hashes is None:
            return 0
        count = 0
        for name, items in _rows_of(system).items():
            old = self._hashes.get(name, {})
            count += sum(1 for key, rows in items.items() if old.get(key) != _hash(rows))
            count += sum(1 for key in old if key not in items)
        return count

    def _check_conflicts(self, conn: sqlite3.Connection, changed: dict[str, dict[str, Rowset]]) -> None:
        """Đối tượng MỚI của mình có mã đã bị cửa sổ khác dùng (cùng thêm mới một lúc) -> không ghi đè."""
        for entity in ENTITIES:
            new_keys = [k for k in changed[entity.name] if k not in self._hashes.get(entity.name, {})]
            for part in _chunks(new_keys):
                marks = ", ".join("?" * len(part))
                if conn.execute(f"SELECT 1 FROM {_q(entity.table)} WHERE {_q(entity.key)} IN ({marks}) LIMIT 1",
                                part).fetchone():
                    self.needs_reload = True
                    raise DataStoreError(CONFLICT_MESSAGE)

    @staticmethod
    def _write(conn: sqlite3.Connection, changed: dict[str, dict[str, Rowset]], removed: dict[str, list[str]]) -> None:
        def upsert(table: Table, rows: list[tuple]) -> None:
            cols = table.insert_cols
            others = [c for c in cols if c not in table.pk]
            action = ("DO UPDATE SET " + ", ".join(f"{_q(c)} = excluded.{_q(c)}" for c in others)) if others \
                else "DO NOTHING"
            conn.executemany(f"INSERT INTO {_q(table.name)} (" + ", ".join(map(_q, cols)) + ") VALUES ("
                             + ", ".join("?" * len(cols)) + ") ON CONFLICT (" + ", ".join(map(_q, table.pk))
                             + f") {action}", rows)

        def insert(table: Table, rows: list[tuple]) -> None:
            cols = table.insert_cols
            conn.executemany(f"INSERT INTO {_q(table.name)} (" + ", ".join(map(_q, cols)) + ") VALUES ("
                             + ", ".join("?" * len(cols)) + ")", rows)

        # 1. xóa dòng chi tiết của đối tượng thay đổi / bị xóa (sẽ ghi lại ở bước 3)
        for entity in reversed(ENTITIES):
            keys = list(changed[entity.name]) + removed[entity.name]
            for owned in entity.owned:
                for part in _chunks(keys):
                    conn.execute(f"DELETE FROM {_q(owned)} WHERE {_q(entity.key)} IN ({', '.join('?' * len(part))})",
                                 part)
        # 2. thêm / cập nhật dòng chính (+ bảng 1-1) theo thứ tự phụ thuộc
        for entity in ENTITIES:
            items = changed[entity.name].values()
            for name in (entity.table,) + entity.subtypes:
                rows = [row for rowset in items for row in rowset.get(name, [])]
                if rows:
                    upsert(TABLES[name], rows)
        # 3. ghi lại dòng chi tiết
        for entity in ENTITIES:
            for owned in entity.owned:
                rows = [row for rowset in changed[entity.name].values() for row in rowset.get(owned, [])]
                if rows:
                    insert(TABLES[owned], rows)
        # 4. xóa đối tượng đã bị xóa (ngược thứ tự phụ thuộc)
        for entity in reversed(ENTITIES):
            for part in _chunks(removed[entity.name]):
                conn.execute(f"DELETE FROM {_q(entity.table)} WHERE {_q(entity.key)} IN "
                             f"({', '.join('?' * len(part))})", part)

    def _existing_keys(self) -> dict[str, dict[str, str]]:
        return {e.name: {str(k): "" for (k,) in self._query(f"SELECT {_q(e.key)} FROM {_q(e.table)}")}
                for e in ENTITIES}

    # ------------------------------------------------------------------ đọc
    def read_tables(self) -> tuple[dict[str, list[dict[str, Any]]], int, dict[str, int]]:
        """Đọc mọi bảng trong cùng một giao dịch (cửa sổ khác đang lưu cũng không đọc lẫn)."""
        conn = self.connection()
        tables: dict[str, list[dict[str, Any]]] = {}
        try:
            conn.execute("BEGIN")
            row = conn.execute('SELECT "SO_PHIEN_BAN" FROM "MN_HT_PHIEN_BAN" WHERE "MA_PHIEN_BAN" = 1').fetchone()
            revision = int(row[0]) if row else 0
            for table in TABLE_LIST:
                if table.name in ("MN_HT_NHAT_KY_THAO_TAC", "MN_HT_PHIEN_BAN"):
                    continue
                cols = [c.name for c in table.cols]
                cursor = conn.execute(f"SELECT {', '.join(map(_q, cols))} FROM {_q(table.name)} ORDER BY "
                                      + ", ".join(map(_q, table.pk)))
                tables[table.name] = [dict(zip(cols, r)) for r in cursor.fetchall()]
            conn.execute("COMMIT")
        except (sqlite3.Error, ValueError) as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise DataStoreError(f"Không đọc được dữ liệu từ CSDL: {exc}") from exc
        counters = {r["TIEN_TO"]: int(r["GIA_TRI_HIEN_TAI"]) for r in tables.pop("MN_HT_BO_DEM_MA", [])}
        return tables, revision, counters

    def read_payload(self) -> tuple[dict[str, Any], int]:
        tables, revision, counters = self.read_tables()
        payload = _decode(tables)
        payload["meta"] = {"version": DataStore.VERSION, "counters": counters}
        return payload, revision

    def load_all(self, system: "KindergartenSystem") -> bool:
        if not self.has_data():
            return False
        try:
            payload, revision = self.read_payload()
            self._apply(payload, system)
        except DataStoreError:
            system.reset()
            raise
        except LOAD_ERRORS as exc:
            system.reset()
            raise DataStoreError(f"Dữ liệu trong CSDL bị lỗi, không đọc được: {exc!r}") from exc
        self._remember(system)
        self._revision = revision
        self.needs_reload = False
        return True

    @staticmethod
    def _apply(payload: dict[str, Any], system: "KindergartenSystem") -> None:
        system.reset(FeeSettings.from_dict(payload["settings"]) if payload.get("settings") else None)
        system.calendar = SchoolCalendar.from_dict(payload.get("calendar"))
        system.attendance.calendar = system.calendar
        system.menus.calendar = system.calendar
        for name, (manager, factory) in DataStore.collections(system).items():
            manager.load_list(payload.get(name, []), factory)
        system.employees.load_closed_payrolls(payload.get("payroll", {}))
        BaseModel.restore_counters(payload.get("meta", {}).get("counters", {}))
        system.after_load()

    def _remember(self, system: "KindergartenSystem") -> None:
        """Sau khi nạp: coi dữ liệu trong bộ nhớ = dữ liệu trong CSDL, lần lưu sau chỉ ghi phần thay đổi."""
        self._hashes = {name: {key: _hash(rows) for key, rows in items.items()}
                        for name, items in _rows_of(system).items()}

    def read_meta(self) -> dict[str, Any]:
        try:
            at, by, revision = self._query('SELECT "CAP_NHAT_LUC", "NGUOI_CAP_NHAT", "SO_PHIEN_BAN" '
                                           'FROM "MN_HT_PHIEN_BAN"')[0]
            return {"saved_at": at.isoformat(timespec="seconds") if at else "-", "saved_by": by or "-",
                    "revision": revision}
        except (DataStoreError, IndexError):
            return {}

    # ------------------------------------------------------------------ chuyển dữ liệu JSON cũ sang
    def import_json(self, data_dir: str | Path, system: "KindergartenSystem") -> bool:
        """Nạp dữ liệu từ thư mục JSON cũ rồi ghi toàn bộ vào CSDL (chỉ khi CSDL còn trống)."""
        source = DataStore(data_dir)
        if self.has_data() or not source.has_data():
            return False
        source.load_all(system)
        self.replace_all(system)
        audit = Path(data_dir) / "audit.jsonl"   # nhật ký thao tác cũ
        if audit.exists():
            rows = []
            for line in audit.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                    rows.append((datetime.fromisoformat(entry["at"]), entry.get("user"), entry.get("action", ""),
                                 str(entry.get("target", ""))[:500],
                                 json.dumps(entry.get("detail"), ensure_ascii=False, default=str)))
                except (ValueError, KeyError, TypeError):
                    continue
            self.insert_audit(rows)
        return True

    def insert_audit(self, rows: list[tuple]) -> None:
        if not rows:
            return
        try:
            self.connection().executemany(
                'INSERT INTO "MN_HT_NHAT_KY_THAO_TAC" ("THOI_DIEM", "TEN_DANG_NHAP", "HANH_DONG", "DOI_TUONG", '
                '"CHI_TIET") VALUES (?, ?, ?, ?, ?)', rows)
        except sqlite3.Error as exc:
            raise DataStoreError(f"Không ghi được nhật ký thao tác: {exc}") from exc

    # ------------------------------------------------------------------ sao lưu / khôi phục
    # Bản sao lưu là một file CSDL SQLite (.db) hoàn chỉnh - đủ 43 bảng, kể cả nhật ký thao tác - tạo bằng
    # sqlite3 backup API nên chụp được ngay cả khi chương trình đang mở CSDL. Mở thẳng bằng DB Browser for SQLite.
    def list_backup_paths(self) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob("*.db"), reverse=True)

    def list_backups(self) -> list[str]:
        return [p.name for p in self.list_backup_paths()]

    def backup(self, label: str = "") -> Path:
        """Chụp toàn bộ file CSDL thành data/backups/<thời điểm>[_nhãn].db."""
        if not self.has_data():
            raise DataStoreError("Chưa có dữ liệu để sao lưu.")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        target = self.backup_dir / f"{stamp}{'_' + label if label else ''}.db"
        try:
            dest = sqlite3.connect(target)
            try:
                self.connection().backup(dest)
            finally:
                dest.close()
        except (sqlite3.Error, OSError) as exc:
            target.unlink(missing_ok=True)
            raise DataStoreError(f"Không sao lưu được CSDL: {exc}") from exc
        DataStore._prune_backups(self)   # type: ignore[arg-type]
        return target

    @staticmethod
    def _check_backup_file(source: Path) -> None:
        """Bản sao lưu phải là CSDL SQLite của chương trình, có tài khoản, lược đồ không mới hơn bản đang chạy."""
        try:
            conn = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
            try:
                if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise DataStoreError(f"File '{source.name}' bị hỏng.")
                users = conn.execute('SELECT COUNT(*) FROM "MN_HT_TAI_KHOAN"').fetchone()[0]
                version = conn.execute('SELECT "PHIEN_BAN_LUOC_DO" FROM "MN_HT_PHIEN_BAN" '
                                       'WHERE "MA_PHIEN_BAN" = 1').fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise DataStoreError(f"'{source.name}' không phải bản sao lưu CSDL hợp lệ: {exc}") from exc
        if not users:
            raise DataStoreError(f"Bản sao lưu '{source.name}' không có tài khoản nào.")
        if version and int(version[0] or 0) > SCHEMA_VERSION:
            raise DataStoreError(f"Bản sao lưu '{source.name}' được tạo bởi phiên bản chương trình mới hơn.")

    def restore(self, name: str, system: "KindergartenSystem") -> Path:
        """Khôi phục CSDL từ một bản sao lưu .db (hiện trạng được tự sao lưu trước).

        Bản sao lưu được kiểm tra và nạp thử từ một bản chép tạm; chỉ khi đọc được trọn vẹn mới ghi đè CSDL thật.
        Nhật ký thao tác KHÔNG bị quay lui (giữ nguyên lịch sử đến thời điểm khôi phục).
        """
        source = self.backup_dir / name
        if not source.exists():
            raise DataStoreError(f"Không có bản sao lưu '{name}'.")
        self._check_backup_file(source)
        current = self.backup(label="truoc_khoi_phuc") if self.has_data() else None
        temp = Path(tempfile.mkdtemp(prefix="kg_restore_"))
        trial = None
        try:
            shutil.copy2(source, temp / DB_FILE)
            trial = SQLiteDataStore(temp)          # tự bổ sung bảng còn thiếu nếu bản sao lưu có lược đồ cũ hơn
            try:
                trial.load_all(system)             # nạp thử: lỗi thì CSDL thật chưa bị động tới
            except DataStoreError:
                self.load_all(system)              # trả lại dữ liệu hiện tại cho bộ nhớ
                raise
            audit = self._query('SELECT * FROM "MN_HT_NHAT_KY_THAO_TAC"')
            revision, _writer = self.remote_revision()
            conn = self.connection()
            trial.connection().backup(conn)        # thay toàn bộ nội dung file CSDL
            conn.execute("BEGIN IMMEDIATE")
            conn.execute('DELETE FROM "MN_HT_NHAT_KY_THAO_TAC"')
            if audit:
                conn.executemany('INSERT INTO "MN_HT_NHAT_KY_THAO_TAC" VALUES (' + ", ".join("?" * len(audit[0]))
                                 + ")", audit)
            # phiên bản tăng tiếp từ hiện trạng -> các cửa sổ khác đang mở chắc chắn thấy thay đổi và tải lại
            conn.execute('UPDATE "MN_HT_PHIEN_BAN" SET "SO_PHIEN_BAN" = ?, "CAP_NHAT_LUC" = ?, '
                         '"NGUOI_CAP_NHAT" = ? WHERE "MA_PHIEN_BAN" = 1',
                         (revision + 1, datetime.now().replace(microsecond=0), self._writer(system)))
            conn.execute("COMMIT")
        except (sqlite3.Error, OSError) as exc:
            if self._connection is not None and self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            self.load_all(system)                  # bộ nhớ khớp lại với những gì đang có trong CSDL
            raise DataStoreError(f"Không khôi phục được '{name}': {exc}") from exc
        finally:
            if trial is not None:
                trial.close()
            shutil.rmtree(temp, ignore_errors=True)
        self.load_all(system)
        return current or source

    def replace_all(self, system: "KindergartenSystem") -> None:
        """Ghi đè TOÀN BỘ dữ liệu trong CSDL bằng dữ liệu trong bộ nhớ (khôi phục, nạp dữ liệu mẫu)."""
        self._hashes = self._existing_keys()
        self.save_all(system, force=True)


def _chunks(keys: list[str], size: int = 500) -> Iterable[list[str]]:
    for i in range(0, len(keys), size):
        yield keys[i:i + size]


# =============================================================================
class SQLiteAuditLog:
    """Nhật ký thao tác lưu trong bảng MN_HT_NHAT_KY_THAO_TAC."""

    def __init__(self, store: SQLiteDataStore) -> None:
        self.store = store

    def write(self, user: str, action: str, target: str = "", detail: Any = None) -> None:
        try:
            self.store.insert_audit([(datetime.now().replace(microsecond=0), user or "(hệ thống)", action,
                                      str(target)[:500], json.dumps(detail, ensure_ascii=False, default=str))])
        except Exception:   # noqa: BLE001 - không để lỗi ghi nhật ký làm hỏng thao tác chính
            pass

    def read(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.store._query('SELECT "THOI_DIEM", "TEN_DANG_NHAP", "HANH_DONG", "DOI_TUONG", "CHI_TIET" '
                                 'FROM "MN_HT_NHAT_KY_THAO_TAC" ORDER BY "MA_NHAT_KY" DESC LIMIT ?', (int(limit),))
        return [{"at": at.isoformat(timespec="seconds") if isinstance(at, datetime) else str(at), "user": user,
                 "action": action, "target": target, "detail": json.loads(detail) if detail else None}
                for at, user, action, target, detail in rows]
