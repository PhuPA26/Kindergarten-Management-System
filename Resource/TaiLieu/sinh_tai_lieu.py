"""Sinh các phần tự động của tài liệu từ chính chương trình (luôn khớp với code):
    02_PhanTich.md  - Sơ đồ phân cấp chức năng (từ menu NAVIGATION + mã form FORM_CODES)
    04_CaiDat.md    - Danh sách form theo quy ước đặt tên
    05_KiemThu.md   - Danh sách kiểm thử tự động (+ kết quả nếu chạy với --chay-test)

Chạy trong thư mục dự án:   python Resource/TaiLieu/sinh_tai_lieu.py [--chay-test]
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from kindergarten.auth.user import ROLE_PERMISSIONS, STAFF_DUTIES, Role  # noqa: E402
from kindergarten.ui.gui.app import FORM_CODES, LOGIN_FORM, NAVIGATION  # noqa: E402


def replace_block(path: Path, tag: str, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    begin, end = f"<!-- {tag}:BEGIN -->", f"<!-- {tag}:END -->"
    new = re.sub(re.escape(begin) + r".*?" + re.escape(end), lambda _m: f"{begin}\n{content.strip()}\n{end}", text,
                 flags=re.S)
    path.write_text(new, encoding="utf-8")


def roles_of(permission) -> str:
    """Vai trò (phân hệ) được mở form."""
    if permission is None:
        return "mọi vai trò"
    names = [r.label for r in Role if r is not Role.STAFF and permission in ROLE_PERMISSIONS[r]]
    names += [f"NV {label.lower()}" for _key, (label, extra) in STAFF_DUTIES.items()
              if permission in ROLE_PERMISSIONS[Role.STAFF] | extra]
    return ", ".join(names)


def functions() -> list[tuple[str, str, list[tuple[str, str, str, str]]]]:
    """[(mã chức năng nhóm, tên nhóm, [(mã chức năng lá, tên, mã form, vai trò)])]"""
    out = []
    for group, classes in NAVIGATION:
        code, name = group.split(" ", 1)
        leaves = [(f"{code}.{i}", cls.title, FORM_CODES[cls.__name__], roles_of(cls.permission))
                  for i, cls in enumerate(classes, 1)]
        if code == "F1.1":   # đăng nhập và đổi mật khẩu cũng là chức năng của Quản trị hệ thống
            leaves = [(f"{code}.1", "Đăng nhập / đăng ký tài khoản", LOGIN_FORM, "mọi người dùng"),
                      (f"{code}.2", "Đổi mật khẩu", "(hộp thoại, menu Hệ thống)", "mọi vai trò")] + \
                     [(f"{code}.{i + 2}", t, f, r) for i, (_c, t, f, r) in enumerate(leaves, 1)]
        out.append((code, name, leaves))
    return out


def bfd() -> str:
    data = functions()
    lines = ["```mermaid", "flowchart TD", '    F1["F1. Hệ thống quản lý<br/>Nhà trẻ - Mẫu giáo"]']
    for code, name, leaves in data:
        gid = code.replace(".", "_")
        lines.append(f'    F1 --> {gid}["{code}<br/>{name}"]')
        previous = gid
        for leaf, title, form, _roles in leaves:   # xếp dọc các chức năng lá dưới mỗi nhóm cho gọn
            lid = leaf.replace(".", "_")
            lines.append(f'    {previous} --- {lid}["{leaf} {title}<br/><small>{form}</small>"]')
            previous = lid
    lines.append("```")
    total = sum(len(leaves) for _c, _n, leaves in data)
    table = ["", f"**{len(data)} chức năng đỉnh, {total} chức năng lá (form)** - 3 cấp: F1 → F1.x → F1.x.y.", "",
             "| Mã chức năng | Chức năng | Form | Vai trò được dùng |", "|---|---|---|---|"]
    for code, name, leaves in data:
        table.append(f"| **{code}** | **{name}** | | |")
        table += [f"| {leaf} | {title} | `{form}` | {roles} |" for leaf, title, form, roles in leaves]
    return "\n".join(lines + table)


def forms() -> str:
    rows = ["| Mã form | Form | Nhóm chức năng | Loại |", "|---|---|---|---|",
            f"| `{LOGIN_FORM}` | Đăng nhập | F1.1 Quản trị hệ thống | ht - hệ thống |"]
    kinds = {"ht": "ht - hệ thống", "dm": "dm - danh mục (Master - Detail)", "nv": "nv - nghiệp vụ", "bc": "bc - báo cáo"}
    for group, classes in NAVIGATION:
        for cls in classes:
            code = FORM_CODES[cls.__name__]
            rows.append(f"| `{code}` | {cls.title} | {group} | {kinds[code.split('_')[1]]} |")
    return "\n".join(rows)


def tests(run: bool) -> str:
    rows = ["| File | Nội dung | Số test |", "|---|---|---:|"]
    total = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc = (ast.get_docstring(tree) or "").strip().splitlines()[0] if ast.get_docstring(tree) else ""
        count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
        total += count
        rows.append(f"| `{path.name}` | {doc} | {count} |")
    rows.append(f"| **Tổng** | (chưa tính các lần chạy lặp theo tham số, VD test giao diện chạy cho 12 tài khoản) "
                f"| **{total}** |")
    if run:
        result = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-p", "no:cacheprovider"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        summary = next((line for line in reversed(result.stdout.splitlines())
                        if re.search(r"\d+ (passed|failed)", line)), "không đọc được kết quả")
        rows += ["", f"**Kết quả lần chạy {datetime.now():%d/%m/%Y %H:%M}:** `{summary.strip(' =')}`"]
    return "\n".join(rows)


if __name__ == "__main__":
    replace_block(HERE / "02_PhanTich.md", "BFD", bfd())
    replace_block(HERE / "04_CaiDat.md", "FORMS", forms())
    replace_block(HERE / "05_KiemThu.md", "TESTS", tests("--chay-test" in sys.argv))
    print("Đã cập nhật 02_PhanTich.md, 04_CaiDat.md, 05_KiemThu.md")
