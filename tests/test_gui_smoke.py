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


def test_pickup_dialog_lists_parents_and_toggles_buttons(gui_app):
    """Hộp thoại Người đón hộ: hiện phụ huynh, lưới trống có dòng hướng dẫn, Sửa/Xóa chỉ bật khi chọn dòng."""
    from kindergarten.people.child import PickupPerson
    from kindergarten.ui.gui.tabs_people import PickupDialog
    application, errors = gui_app
    user = application.system.auth.login("admin", "admin123")
    user.must_change_password = False
    application.on_login(user)
    assert application.main.show_tab("ChildrenTab")
    tab = application.main.current
    child = next(c for c in application.system.children.all_sorted() if not c.pickup_persons)
    dialog = PickupDialog(tab, child)
    application.root.update()
    try:
        assert dialog.m_lbl_empty.winfo_ismapped()
        assert dialog.m_btn_edit.instate(["disabled"]) and dialog.m_btn_delete.instate(["disabled"])
        child.add_pickup_person(PickupPerson("Hồ Văn Lộc", "Ông nội", "0977000444"))
        dialog.reload()
        dialog.m_fg_list.tree.selection_set("Hồ Văn Lộc")
        application.root.update()
        assert not dialog.m_lbl_empty.winfo_ismapped()
        assert dialog.m_btn_edit.instate(["!disabled"]) and dialog.m_btn_delete.instate(["!disabled"])
        assert dialog.m_fg_list.tree.set("Hồ Văn Lộc", "c4") == "—"
    finally:
        dialog.destroy()
    assert not errors, errors


def test_pick_up_mode_has_no_check_column(gui_app):
    """Đón trẻ: có cột ô tích (đón nhiều trẻ một lượt). Trả trẻ: trả từng trẻ -> không có cột ô tích."""
    application, errors = gui_app
    user = application.system.auth.login("gv.nhung", "giaovien123")
    user.must_change_password = False
    application.on_login(user)
    assert application.main.show_tab("CheckInOutTab")
    tab = application.main.current
    table = tab.m_fg_list
    for mode, has_check in (("in", True), ("out", False), ("in", True)):
        tab.mode.set(mode)
        tab._mode_changed()
        application.root.update()
        headings = [table.tree.heading(c, "text") for c in table.tree["columns"]]
        assert (headings[0] == table.UNCHECKED) is has_check, (mode, headings)
        assert headings[-1] == "Ghi chú"
    assert not errors, errors


def test_daily_log_only_present_children_can_be_ticked(gui_app):
    """Ăn ngủ - sinh hoạt: trẻ vắng / chưa đón không có ô tích, 'chọn tất cả' chỉ tích trẻ có mặt."""
    from datetime import date, timedelta
    from kindergarten.utils import format_date
    application, errors = gui_app
    system = application.system
    user = system.auth.login("gv.nhung", "giaovien123")
    user.must_change_password = False
    application.on_login(user)
    assert application.main.show_tab("DailyLogTab")
    tab = application.main.current
    class_id = system.teacher_of(user).homeroom_class_id
    day = date.today() - timedelta(days=1)   # ngày học gần nhất có cả trẻ có mặt lẫn trẻ vắng
    for _ in range(60):
        rows = system.daily.class_day(class_id, day) if system.calendar.is_school_day(day) else []
        present = {r["child"].id for r in rows if r["record"] is not None and r["record"].is_present}
        if present and len(present) < len(rows):
            break
        day -= timedelta(days=1)
    else:
        pytest.skip("Dữ liệu mẫu không có ngày vừa có trẻ có mặt vừa có trẻ vắng")
    tab.day_var.set(format_date(day))
    tab.refresh()
    application.root.update()
    table = tab.m_fg_list
    absent = [i for i in table.all_ids() if i not in present]
    assert all(table.tree.set(i, "c0") == "" for i in absent)          # trẻ vắng: không có ô tích
    assert all(table.tree.set(i, "c0") == table.UNCHECKED for i in present)
    table.set_checked(table.all_ids())                                   # như bấm ☐ ở tiêu đề
    assert set(table.checked_ids()) == present
    table.toggle(absent)
    assert set(table.checked_ids()) == present
    assert not errors, errors


def test_horizontal_touchpad_scroll_is_smooth(shared_root):
    """Vuốt ngang (Shift + lăn / touchpad, delta nhỏ) dịch bảng ít một theo điểm ảnh, không nhảy cả bước."""
    from types import SimpleNamespace
    from kindergarten.ui.gui.widgets import DataTable
    window = tk.Toplevel(shared_root)
    window.geometry("320x200")
    table = DataTable(window, [(f"Cột {i}", 150) for i in range(8)])
    table.pack(fill="both", expand=True)
    table.set_rows([[f"ô {r}-{i}" for i in range(8)] for r in range(5)])
    window.update()
    try:
        first, last = table.tree.xview()
        assert last - first < 1                      # bảng rộng hơn khung -> cuộn ngang được
        content = table.tree.winfo_width() / (last - first)
        steps = []
        for _ in range(4):                           # 4 lần vuốt nhỏ sang phải (delta -30 như touchpad)
            before = table.tree.xview()[0]
            table._on_horizontal_wheel(SimpleNamespace(delta=-30))
            window.update()
            steps.append((table.tree.xview()[0] - before) * content)
        assert all(0 < s < 40 for s in steps), steps  # mỗi lần dịch vài chục điểm ảnh, đều nhau
        before = table.tree.xview()[0]
        table._on_horizontal_wheel(SimpleNamespace(delta=30))   # vuốt ngược lại
        window.update()
        assert table.tree.xview()[0] < before
    finally:
        window.destroy()


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


def test_login_enter_on_username_moves_to_password(gui_app, monkeypatch):
    """Enter ở ô tên đăng nhập khi chưa gõ mật khẩu: chuyển xuống ô mật khẩu, không báo sai, không cộng lần sai."""
    application, errors = gui_app
    frame = next(w for w in application.container.winfo_children() if isinstance(w, gui.LoginFrame))
    attempts: list[tuple] = []
    real_login = application.system.auth.login
    monkeypatch.setattr(application.system.auth, "login", lambda *a: attempts.append(a) or real_login(*a))
    frame.username.set("admin")
    frame.password.set("")
    frame._username_return()   # Enter ở ô tên đăng nhập (cửa sổ test bị ẩn nên gọi thẳng hàm gắn với phím)
    assert not attempts and frame.m_lbl_message.cget("text") == ""
    frame.login()              # bấm nút Đăng nhập khi chưa có mật khẩu
    assert not attempts and "sai" not in frame.m_lbl_message.cget("text").lower()
    frame.password.set("sai-mat-khau")
    frame._username_return()   # đã có mật khẩu -> Enter là đăng nhập
    assert attempts and frame.m_lbl_message.cget("text") and frame.password.get() == ""
    assert application.main is None
    assert not errors, errors


def test_jump_between_functions_has_back_button(gui_app):
    application, errors = gui_app
    login_admin(application)
    main = application.main
    start = next(i for i, tab in enumerate(main.tabs) if type(tab).__name__ == "ChildrenTab")
    main.select_tab(start)                                       # mở từ menu trái
    assert not main.history
    assert main.show_tab("ParentsTab")                           # mở chức năng khác (không phải con) từ Trẻ
    assert main.history == [start]
    main.go_back()
    assert main.tabs.index(main.current) == start and not main.history
    assert not errors, errors
