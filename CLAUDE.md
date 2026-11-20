# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working with the user (quy tắc bắt buộc)

- **Khi người dùng chỉ hỏi** về một điểm trong project (vì sao code như vậy, có nên đổi không, chỗ này có lỗi không…):
  KHÔNG sửa code ngay theo hướng câu hỏi gợi ý. Trước tiên giải thích lý do code hiện tại được viết như vậy (dẫn
  file:dòng, quy tắc nghiệp vụ trong README, ràng buộc kiến trúc), nêu ưu/nhược nếu đổi, rồi **hỏi có muốn sửa không**.
  Chỉ sửa sau khi người dùng đồng ý.
- **Khi người dùng yêu cầu sửa ngay từ đầu** (câu lệnh rõ ràng: "sửa…", "thêm…", "đổi…", "xoá…"): làm theo đúng ý
  người dùng, không cần hỏi lại.
- Trả lời người dùng bằng tiếng Việt.

## Project

Kindergarten management system (Hệ thống thông tin quản lý Nhà trẻ - Mẫu giáo), a Python 3.10+ OOP course project.
It uses only the standard library (`tkinter`, `sqlite3`). `pytest` is the only dependency. The code, docstrings,
comments, user-facing messages and docs are all in **Vietnamese with diacritics**, so keep new text that way.
README.md is the detailed spec: business rules, role/screen matrix, task map T01–T34, and the list of review fixes
done or skipped.

## Commands

A venv is committed under `env/` (Python 3.11). Use `env\Scripts\python.exe`, or activate it first.

```powershell
python main.py                 # console UI (role-based menu)
python main.py --gui           # Tkinter UI
python main.py --seed --yes    # reload sample data (backs up the existing DB first)
python main.py --db PATH       # open another .db file
python main.py --json          # legacy JSON store in data/ (still used by tests)
python -m pytest               # all tests (pytest.ini: testpaths=tests, pythonpath=., -q)
python -m pytest tests/test_finance.py::test_name -q   # single test
python Database/sinh_tai_lieu_csdl.py                   # regenerate Database/01_tao_csdl.sql + thiet_ke_csdl.md from schema.py
python Resource/TaiLieu/sinh_tai_lieu.py --chay-test    # regenerate the auto-generated parts of the Resource/TaiLieu docs
```

The project has no linter config. Style follows `Resource/TaiLieu/04_CaiDat.md`: PEP 8, lines ≤ 120 characters, and
type hints on every function.

Demo logins (after seeding): `admin/admin123`, `ketoan/ketoan123`, `gv.nhung/giaovien123` (homeroom teacher),
`gv.tuan/giaovien123` (subject teacher), `nv.sau|nv.hung|nv.yen/nhanvien123` (kitchen, guard, nurse),
`ph.mai/phuhuynh123` (parent).

## Architecture

The code has three layers: UI (`kindergarten/ui/console`, `kindergarten/ui/gui`), business logic (the `kindergarten/*`
domain packages), and storage (`kindergarten/storage`).

**`KindergartenSystem` (`kindergarten/system.py`) is the Facade.** It builds every manager with its dependencies
passed in through the constructor. It also wires cross-module lookups and observer hooks, binds a write permission to
each manager (`_bind_permissions`), and holds operations that span modules: enrolment, accounts and registration,
services, holidays, pickup verification. Its user-scope helpers are `classes_for`, `children_for`,
`ensure_class_access` and `ensure_child_access`. Both UIs talk only to this object. `system.reset()` rebuilds
everything, so never cache manager references across a reload.

**Models and managers.**
- Every entity subclasses `core/base_model.BaseModel`. It gets an auto-generated prefixed ID (C001, PH001, HD001…)
  plus `to_dict()` and `from_dict()`. Polymorphic `from_dict` picks the right subclass.
- Collections subclass the generic `core/base_manager.BaseManager[T]`. It provides add/update/remove/find/search/sort.
  `update` is atomic: it snapshots the object and restores it if anything fails. Subclasses customise behaviour
  through hooks (`_validate_new`, `_validate_update`, `_before_remove`, `_after_*`). Cascades and delete-blocking use
  `on_before_remove` / `on_remove` listeners that other managers register.
- IDs are allocated only after validation passes, so a failed add does not skip a number.

**Permissions are enforced in the business layer, not only in the UI.** `BaseManager._authorize()` checks the
manager's `write_permission` whenever someone is logged in. When nobody is logged in, the action counts as a system
task (seeding, loading) and is allowed. `auth.elevated` bypasses the check for steps that were already authorised
higher up. Roles and the permission table live in `auth/user.py` (`Role`, `Permission`, `ROLE_PERMISSIONS`). Two
roles have sub-variants:
- Teachers: `teacher_duty` returns `chu_nhiem` (homeroom) or `bo_mon` (subject teacher). It is derived from the
  current homeroom assignment.
- Staff: `duty` (kitchen, guard, medical) comes from the job position in their HR record.

Teachers see only their homeroom class plus classes where they have timetable slots. Parents see only their own
children. Any new operation that crosses modules needs the same permission and scope checks.

**Persistence.**
- `storage/sqlite_store.SQLiteDataStore` is the main backend: `data/ql_mam_non.db` with 43 tables named
  `MN_<HT|DM|NV>_<NAME>`. `storage/datastore.DataStore` is the legacy JSON backend; the test `system` fixture uses it
  by default.
- Flow: model `to_dict()` → `DataStore.collections(system)` → per-collection encoders in `storage/schema.py`
  (`ENCODERS`, `ENTITIES`, `TABLE_LIST`) → rows. Loading goes the other way through `_decode` and `from_dict`.
- `save_all` writes only entities whose row hash changed, all in one transaction. It detects concurrent writers
  through `MN_HT_PHIEN_BAN`. The GUI polls `has_remote_changes` and calls `system.reload_keep_session()`.
- **Adding or changing a persisted field means editing:**
  - the model's `to_dict` and `from_dict`
  - the table definition and the encoder/decoder in `schema.py`
  - and then regenerating the `Database/` docs with `sinh_tai_lieu_csdl.py`
- `after_load()` rebuilds indexes and two-way links (`sync_links`). Child↔class and child↔parent links are stored on
  both sides.

**GUI (`ui/gui`).**
- `app.py` holds the login screen and `MainFrame`. In `app.py`, `NAVIGATION` lists tab classes per function group
  F1.x, `SIDEBAR_GROUPS` sets the sidebar layout, and `FORM_CODES` and `TAB_ICONS` give each form its code and icon.
- A tab appears only if the user has the tab class's `permission`. Each tab subclasses `base_tab.BaseTab` and
  implements `build()` and `refresh()`.
- Run business calls through `BaseTab.guard()`. It shows a `KindergartenError` in a message box, and on success it
  saves, refreshes and notifies. Use `BaseTab.form()` for detail dialogs and `BaseTab.confirm_delete()` for deletes.
- Widget attributes use the course naming convention: `m_txt_`, `m_cbo_`, `m_fg_` (grid), `m_lbl_`, `m_btn_`,
  `m_tab_`. Forms are numbered `frm000`–`frm027` (list in `Resource/TaiLieu/04_CaiDat.md`). The business layer stays
  plain PEP 8 `snake_case`.

**Console (`ui/console`).** `MainMenu` dispatches to one `screens/*_screen.py` per business area. Tests drive it end
to end with simulated input.

**Errors.** Business errors subclass `KindergartenError` (`exceptions.py`), and the UIs show them to the user. Any
unexpected exception goes to `logs/error.log` through `applog.py`. Audit entries go through `system.audit(...)` and
land in the `MN_HT_NHAT_KY_THAO_TAC` table (or `audit.jsonl` in JSON mode).

## Tests

- `tests/conftest.py` resets ID counters for every test and lowers PBKDF2 iterations. It provides these fixtures:
  - `system`: an empty system with the JSON store in `tmp_path`
  - `seeded`: the same system after `seed_data.seed`
  - `make_child`, `make_parent`, `make_teacher`, `dob_for`
- Sample data dates are relative to today.
- `test_gui_smoke.py` logs in as every demo account and opens every form. It needs a display and skips itself if Tk
  cannot start. It also turns off pytest capture while it creates `Tk()`, because of a Windows Tcl issue.
- `test_review_fixes.py` has one regression test per item of the review report (L01–L27, P01, P03), and the code
  comments refer to those IDs (L08, K06, P04…). Keep those references when you edit that code.

## Data and generated files

`data/`, `exports/`, `logs/` and `env/` are gitignored. The `.sln` / `.pyproj` files and the `Database/`, `Dlllib/`,
`Resource/` folders follow the course's Visual Studio solution convention. Do not reorganise them.
