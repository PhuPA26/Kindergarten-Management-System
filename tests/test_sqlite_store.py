"""Kiểm thử lưu trữ SQLite - thiết kế CSDL v2 (42 bảng, file data/ql_mam_non.db).

Mỗi test dùng một file CSDL riêng trong thư mục tạm, không đụng dữ liệu thật.
"""
from __future__ import annotations

from datetime import date

import pytest

from kindergarten.core.base_model import BaseModel
from kindergarten.exceptions import DataStoreError
from kindergarten.storage.datastore import DataStore
from kindergarten.storage.schema import TABLES
from kindergarten.storage.sqlite_store import SQLiteDataStore
from kindergarten.system import KindergartenSystem


@pytest.fixture
def store(tmp_path):
    s = SQLiteDataStore(tmp_path / "data")
    yield s
    s.close()


def count(store: SQLiteDataStore, table: str, where: str = "1=1", args=()) -> int:
    return store._query(f'SELECT COUNT(*) FROM "{table}" WHERE {where}', args)[0][0]


def snapshot(system: KindergartenSystem) -> dict:
    out = {name: {i.id: i.to_dict() for i in manager} for name, (manager, _f) in DataStore.collections(system).items()}
    for name in ("parents", "classes"):   # danh sách suy ra từ bảng liên kết: so sánh không phụ thuộc thứ tự
        for item in out[name].values():
            item["child_ids"] = sorted(item["child_ids"])
    out["settings"] = system.settings.to_dict()
    out["calendar"] = system.calendar.to_dict()
    out["payroll"] = system.employees.closed_payrolls_to_dict()
    return out


def seeded(store: SQLiteDataStore, tmp_path) -> KindergartenSystem:
    from seed_data import seed
    system = KindergartenSystem(tmp_path / "data", store=store)
    seed(system)
    system.save()
    return system


def open_again(tmp_path) -> KindergartenSystem:
    """Một cửa sổ chương trình khác mở cùng file CSDL."""
    other = KindergartenSystem(tmp_path / "data", store=SQLiteDataStore(tmp_path / "data"))
    assert other.load()
    return other


def test_schema_follows_naming_convention(store):
    tables = {name for (name,) in store._query("SELECT name FROM sqlite_master WHERE type = 'table' "
                                               "AND name NOT LIKE 'sqlite_%'")}
    assert tables == set(TABLES) and len(tables) == 42
    assert all(t.startswith(("MN_HT_", "MN_DM_", "MN_NV_")) and t == t.upper() for t in tables)
    fks = sum(len(store._query(f'PRAGMA foreign_key_list("{t}")')) for t in tables)
    assert fks >= 30                                          # quan hệ được ràng buộc bằng khóa ngoại thật
    assert store._query("PRAGMA foreign_keys")[0][0] == 1     # khóa ngoại được bật


def test_seed_save_and_reload_round_trip(store, tmp_path):
    from seed_data import seed
    system = KindergartenSystem(tmp_path / "data", store=store)
    counts = seed(system)
    system.auth.login("gv.nhung", "giaovien123")
    report = system.reports.create("end_of_day", note="Ghi chú có dấu: bé ăn tốt")
    system.reports.submit(report.id)
    system.auth.logout()
    system.calendar.add_holiday(date(2026, 12, 31), "Nghỉ cuối năm")
    month, year = date.today().month, date.today().year
    system.employees.close_payroll(month, year)
    system.settings.update(tuition_by_group={"Lá": 2_800_000})
    system.save()
    assert store.path.exists() and store.path.name == "ql_mam_non.db"
    assert count(store, "MN_DM_TRE") == counts["trẻ"]
    assert count(store, "MN_NV_DIEM_DANH") == counts["điểm danh"]
    assert count(store, "MN_DM_TRE", '"HO_TEN" = ?', ("Nguyễn Minh Khang",)) == 1   # tiếng Việt đủ dấu
    assert count(store, "MN_DM_TRE_PHU_HUYNH") > 0 and count(store, "MN_NV_HOA_DON_KHOAN_PHI") > 0
    # cột tính toán THANH_TIEN = DON_GIA x SO_LUONG khớp với số tiền chương trình tính
    total = store._query('SELECT SUM("THANH_TIEN") FROM "MN_NV_HOA_DON_KHOAN_PHI"')[0][0]
    assert int(total) == sum(fee.calculate() for inv in system.invoices for fee in inv.fees)

    before = snapshot(system)
    BaseModel.reset_counters()
    again = open_again(tmp_path)
    assert snapshot(again) == before   # đọc lại khớp 100% mọi trường của mọi đối tượng
    assert again.calendar.holiday_name(date(2026, 12, 31)) == "Nghỉ cuối năm"
    assert again.employees.is_closed(month, year)
    assert again.auth.login("ph.mai", "phuhuynh123").parent_id
    again.auth.logout()
    khang = again.children.find_one(full_name="Nguyễn Minh Khang")
    new_child_id = again.children.add(type(khang)("Trẻ Mới Thêm", khang.dob, "Nam")).id
    assert new_child_id not in system.children._items   # bộ đếm mã được lưu trong CSDL (L01)


def test_incremental_save_and_delete(store, tmp_path):
    system = seeded(store, tmp_path)
    khang = system.children.find_one(full_name="Nguyễn Minh Khang")
    calls: list[str] = []
    store.connection().set_trace_callback(lambda sql: calls.append(sql))
    system.children.update(khang.id, nickname="Bin Bin")
    system.save()
    written = " ".join(calls)
    assert '"MN_DM_TRE"' in written and '"MN_NV_DIEM_DANH"' not in written   # chỉ ghi đối tượng thay đổi
    calls.clear()
    system.save()
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql in calls)   # không thay đổi -> không ghi
    store.connection().set_trace_callback(None)
    allergy = system.health.allergies_of(system.children.find_one(full_name="Lê Bảo Ngọc").id)[0]
    system.health.remove_allergy(allergy.id)
    system.save()
    assert count(store, "MN_NV_DI_UNG", '"MA_DI_UNG" = ?', (allergy.id,)) == 0
    assert store._query('SELECT "TEN_O_NHA" FROM "MN_DM_TRE" WHERE "MA_TRE" = ?', (khang.id,))[0][0] == "Bin Bin"


def test_pending_changes_counts_unsaved_edits(store, tmp_path):
    system = seeded(store, tmp_path)
    assert store.pending_changes(system) == 0                     # vừa lưu xong -> không còn gì chưa lưu
    khang = system.children.find_one(full_name="Nguyễn Minh Khang")
    system.children.update(khang.id, nickname="Tí")
    assert store.pending_changes(system) == 1                     # sửa 1 hồ sơ trong bộ nhớ, chưa ghi
    system.load()                                                 # "Không lưu" khi đăng xuất -> nạp lại từ CSDL
    assert store.pending_changes(system) == 0
    assert system.children.get(khang.id).nickname != "Tí"


def test_foreign_keys_enforced(store, tmp_path):
    seeded(store, tmp_path)
    with pytest.raises(DataStoreError):   # mã lớp không tồn tại -> khóa ngoại từ chối
        store._query('UPDATE "MN_DM_TRE" SET "MA_LOP" = ? WHERE "MA_TRE" = ?', ("L999", "C001"))


def test_two_windows_edit_different_records(store, tmp_path):
    a = seeded(store, tmp_path)
    b = open_again(tmp_path)
    khang, ngoc = a.children.find_one(full_name="Nguyễn Minh Khang"), a.children.find_one(full_name="Lê Bảo Ngọc")
    a.children.update(khang.id, nickname="Sửa bởi A")
    a.save()
    assert b.store.has_remote_changes()
    b.children.update(ngoc.id, nickname="Sửa bởi B")
    b.save()
    assert b.store.needs_reload
    b.reload_keep_session()
    assert b.children.get(khang.id).nickname == "Sửa bởi A" and b.children.get(ngoc.id).nickname == "Sửa bởi B"
    a.reload_keep_session()
    assert a.children.get(ngoc.id).nickname == "Sửa bởi B"


def test_two_windows_add_same_id_do_not_overwrite(store, tmp_path):
    a = seeded(store, tmp_path)
    b = open_again(tmp_path)
    template = a.children.find_one(full_name="Nguyễn Minh Khang")
    start = BaseModel.counters()["C"]
    first = a.children.add(type(template)("Bé Của A", template.dob, "Nam"))
    a.save()
    BaseModel._counters["C"] = start   # mô phỏng cửa sổ B có bộ đếm riêng chưa biết A vừa cấp mã
    second = b.children.add(type(template)("Bé Của B", template.dob, "Nữ"))
    assert second.id == first.id
    with pytest.raises(DataStoreError):
        b.save()                       # không ghi đè trẻ của A
    assert b.store.needs_reload
    assert store._query('SELECT "HO_TEN" FROM "MN_DM_TRE" WHERE "MA_TRE" = ?', (first.id,))[0][0] == "Bé Của A"
    b.reload_keep_session()
    again = b.children.add(type(template)("Bé Của B", template.dob, "Nữ"))
    b.save()
    assert again.id != first.id and count(store, "MN_DM_TRE", '"HO_TEN" = ?', ("Bé Của B",)) == 1


def test_audit_backup_restore_and_json_import(store, tmp_path):
    from seed_data import seed
    json_dir = tmp_path / "json_data"
    old = KindergartenSystem(json_dir)
    seed(old)
    old.save()
    system = KindergartenSystem(tmp_path / "data", store=store)
    assert store.import_json(json_dir, system)                   # chuyển dữ liệu JSON cũ sang SQLite
    assert count(store, "MN_DM_TRE") == len(old.children)
    system.audit("Thử ghi nhật ký", "C001", {"a": 1})
    assert system.audit_log.read(5)[0]["action"] == "Thử ghi nhật ký"
    backup = store.backup("thu")
    khang = system.children.find_one(full_name="Nguyễn Minh Khang")
    system.children.update(khang.id, nickname="Đã sửa")
    system.save()
    store.restore(backup.name, system)
    assert system.children.get(khang.id).nickname == "Bin"
    assert store._query('SELECT "TEN_O_NHA" FROM "MN_DM_TRE" WHERE "MA_TRE" = ?', (khang.id,))[0][0] == "Bin"
