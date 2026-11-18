"""Kiểm thử khói giao diện Tkinter: với MỖI tài khoản mẫu (mỗi phân hệ), đăng nhập, mở lần lượt mọi form của phân hệ,
mở khung xem chi tiết và form xóa - không được phát sinh lỗi (sai tên control, thiếu thuộc tính...).

Cần màn hình (Tk); máy không có giao diện đồ họa thì tự bỏ qua.
"""
from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")

from kindergarten.ui.gui import app as gui  # noqa: E402
from kindergarten.ui.gui.app import FORM_CODES, KindergartenApp  # noqa: E402
from seed_data import DEMO_ACCOUNTS, seed  # noqa: E402

@pytest.fixture(scope="module")
def shared_root(pytestconfig):
    """Một cửa sổ Tk dùng chung cho cả module.
    - Trên Windows, Tcl không đọc được init.tcl / tk.tcl khi pytest đang bắt output ở mức file handle
      ("couldn't read file ... No error") -> tạm ngừng bắt output trong lúc khởi tạo Tk.
    - Tạo Tk() nhiều lần trong một tiến trình cũng đôi khi lỗi -> chỉ tạo một lần.
    Máy không có giao diện đồ họa thì bỏ qua cả module."""
    capture = pytestconfig.pluginmanager.getplugin("capturemanager")
    try:
        if capture is not None:
            with capture.global_and_fixture_disabled():
                root = tk.Tk()
        else:
            root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Không chạy được Tkinter: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def gui_app(tmp_path, monkeypatch, shared_root):
    from kindergarten.system import KindergartenSystem
    errors: list[str] = []
    for name in ("showerror", "showwarning"):   # lỗi hiện hộp thoại -> ghi lại để test bắt được
        monkeypatch.setattr(gui.messagebox, name, lambda title, message, **_k: errors.append(f"{title}: {message}"))
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
    system = KindergartenSystem(tmp_path / "data")
    seed(system)
    system.save()
    application = KindergartenApp(system, None, DEMO_ACCOUNTS, root=shared_root)
    application.save = lambda notify=False: True

    def report_error(exc_type, exc, tb):   # lỗi trong callback Tk -> làm test thất bại
        errors.append(f"{exc_type.__name__}: {exc}")
    shared_root.report_callback_exception = report_error
    yield application, errors
    for widget in shared_root.winfo_children():   # dọn giao diện cho lượt sau
        widget.destroy()
    shared_root.configure(menu="")


@pytest.mark.parametrize("username,password", [(u, p) for u, p, _d in DEMO_ACCOUNTS])
def test_every_form_of_every_subsystem_opens(gui_app, username, password):
    application, errors = gui_app
    user = application.system.auth.login(username, password)
    user.must_change_password = False
    application.on_login(user)
    main = application.main
    assert main.tabs, f"{username}: không có form nào"
    for index, tab in enumerate(main.tabs):
        main.select_tab(index)
        application.root.update_idletasks()
        assert main.current is tab
        assert FORM_CODES[type(tab).__name__].startswith("frm")   # mỗi form có mã theo quy ước đặt tên
    main.go_home()
    application.root.update()
    assert set(main.sidebar.items) == set(range(len(main.tabs)))   # mọi form đều có trên menu trái
    assert not errors, f"{username}: {errors}"


def test_detail_drawer_and_delete_form(gui_app):
    application, errors = gui_app
    user = application.system.auth.login("admin", "admin123")
    user.must_change_password = False
    application.on_login(user)
    main = application.main
    assert main.show_tab("ChildrenTab")
    tab = main.current
    tab.m_fg_list.tree.selection_set(tab.m_fg_list.all_ids()[0])
    tab.view_detail()                               # khung xem chi tiết (chữ bình thường, nút ✕)
    application.root.update()
    drawer = getattr(main.right, "_report_drawer", None)
    assert drawer is not None and drawer.winfo_exists()
    drawer.close()
    from kindergarten.ui.gui.widgets import DeleteDialog
    dialog = DeleteDialog(tab, "Xóa hồ sơ trẻ", [("Mã trẻ", "C001")], "ghi chú")   # form xóa theo mẫu Detail
    application.root.update()
    assert not dialog.confirmed
    dialog.destroy()
    assert not errors, errors


class FakeUnsavedTab:
    """Màn hình còn dữ liệu sửa dở (giống Điểm danh chưa lưu)."""
    title = "Điểm danh"

    def __init__(self) -> None:
        self.saved = self.discarded = 0

    def has_unsaved(self) -> bool:
        return not (self.saved or self.discarded)

    def unsaved_label(self) -> str:
        return "Điểm danh lớp Mầm 1"

    def save_unsaved(self) -> bool:
        self.saved += 1
        return True

    def discard_unsaved(self) -> None:
        self.discarded += 1


def login_admin(application):
    user = application.system.auth.login("admin", "admin123")
    user.must_change_password = False
    application.on_login(user)


def test_logout_without_unsaved_data_just_confirms(gui_app, monkeypatch):
    application, errors = gui_app
    login_admin(application)
    asked: list[str] = []
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda title, message, **_k: asked.append(message) or False)
    application.logout()
    assert application.system.auth.current_user is not None      # bấm "Không" -> ở lại
    assert "đã được lưu" in asked[0]
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)
    application.logout()
    assert application.system.auth.current_user is None
    assert not errors, errors


@pytest.mark.parametrize("answer", [None, True, False])   # Hủy / Có (lưu) / Không (bỏ thay đổi)
def test_logout_asks_to_save_unsaved_data(gui_app, monkeypatch, answer):
    application, errors = gui_app
    login_admin(application)
    tab = FakeUnsavedTab()
    application.main.tabs.append(tab)
    saves: list[bool] = []
    application.save = lambda notify=False: saves.append(True) or True
    reloads: list[bool] = []
    monkeypatch.setattr(application.system, "load", lambda: reloads.append(True) or True)
    asked: list[str] = []
    monkeypatch.setattr(gui.messagebox, "askyesnocancel", lambda title, message, **_k: asked.append(message) or answer)
    application.logout()
    assert "Điểm danh lớp Mầm 1" in asked[0]
    if answer is None:
        assert application.system.auth.current_user is not None and not saves and not tab.discarded
    elif answer:
        assert tab.saved == 1 and saves and not reloads
        assert application.system.auth.current_user is None
    else:
        assert tab.discarded == 1 and not saves and reloads
        assert application.system.auth.current_user is None
    assert not errors, errors
