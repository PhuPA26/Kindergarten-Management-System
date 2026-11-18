"""Sinh tài liệu CSDL từ định nghĩa lược đồ trong kindergarten/storage/schema.py
(luôn khớp với CSDL SQLite thật mà chương trình tạo ra).

Chạy trong thư mục dự án:   python Database/sinh_tai_lieu_csdl.py
Tạo / ghi đè:
    Database/01_tao_csdl.sql      - câu lệnh tạo toàn bộ bảng SQLite (chạy được trong DB Browser for SQLite)
    Database/thiet_ke_csdl.md     - thiết kế: thực thể, quan hệ, sơ đồ ERD, từ điển dữ liệu
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kindergarten.storage.schema import DATABASE_NAME, ENTITIES, SCHEMA_VERSION, TABLE_LIST, TABLES  # noqa: E402
from kindergarten.storage.sqlite_store import create_table_sql  # noqa: E402

OUT = Path(__file__).resolve().parent
GROUPS = {"HT": "F1.1 - Quản trị hệ thống", "DM": "F1.2 - Thông tin danh mục", "NV": "F1.3/F1.4 - Nghiệp vụ"}


def write_sql() -> Path:
    lines = [
        "-- " + "=" * 100,
        f"-- CSDL QUẢN LÝ NHÀ TRẺ - MẪU GIÁO (thiết kế v{SCHEMA_VERSION}) - tự sinh bởi Database/sinh_tai_lieu_csdl.py",
        "-- Quy ước tên bảng: SUB_SYSTEM + PURPOSE_TYPE + NAME  (MN = Mầm non; HT = hệ thống, DM = danh mục, NV = nghiệp vụ)",
        f"-- CSDL SQLite: file data/{DATABASE_NAME}.db. Chương trình TỰ tạo file và các bảng này ở lần chạy đầu -",
        "-- file này chỉ để xem / tạo thủ công (DB Browser for SQLite: New Database > Execute SQL > dán > ▶).",
        "-- " + "=" * 100,
        "PRAGMA foreign_keys = ON;",
        "",
    ]
    for statement in create_table_sql():
        lines += [statement + ";", ""]
    lines.append('INSERT OR IGNORE INTO "MN_HT_PHIEN_BAN" ("MA_PHIEN_BAN", "SO_PHIEN_BAN", "PHIEN_BAN_LUOC_DO") '
                 f"VALUES (1, 0, {SCHEMA_VERSION});")
    path = OUT / "01_tao_csdl.sql"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _short(sql: str) -> str:
    sql = sql.upper()
    for key, word in (("VARCHAR", "varchar"), ("INTEGER", "int"), ("TEXT", "text"), ("DATETIME", "datetime"),
                      ("DATE", "date"), ("TIME", "time"), ("TINYINT(1)", "bool"), ("DECIMAL", "decimal"),
                      ("BIGINT", "bigint"), ("SMALLINT", "int"), ("TINYINT", "int"), ("INT", "int")):
        if sql.startswith(key):
            return word
    return "string"


def mermaid(tables: list) -> list[str]:
    lines = ["```mermaid", "erDiagram"]
    for table in tables:
        fk_cols = {c for cols, _r, _rc, _d in table.fks for c in cols}
        lines.append(f"    {table.name} {{")
        for col in table.cols:
            keys = ",".join(k for k, ok in (("PK", col.name in table.pk), ("FK", col.name in fk_cols)) if ok)
            lines.append(f"        {_short(col.sql)} {col.name}{' ' + keys if keys else ''}")
        lines.append("    }")
    for table in tables:
        for cols, ref, _rc, _d in table.fks:
            nullable = any(next(c for c in table.cols if c.name == col).null for col in cols)
            if tuple(cols) == table.pk:
                card = "||--o|"                      # 1 - 0..1 (bảng con 1-1)
            else:
                card = ("|o--o{" if nullable else "||--o{")   # 1 (hoặc 0..1) - n
            lines.append(f'    {ref} {card} {table.name} : "{", ".join(cols)}"')
    lines.append("```")
    return lines


def relation_rows() -> list[str]:
    rows = ["| Bảng cha (1) | Bảng con (n) | Khóa ngoại | Kiểu quan hệ | Khi xóa dòng cha |", "|---|---|---|---|---|"]
    for table in TABLE_LIST:
        for cols, ref, _rc, on_delete in table.fks:
            nullable = any(next(c for c in table.cols if c.name == col).null for col in cols)
            kind = "1 - 0..1 (chuyên biệt hóa)" if tuple(cols) == table.pk else ("0..1 - n" if nullable else "1 - n")
            action = {"CASCADE": "xóa theo", "SET NULL": "để trống liên kết", "RESTRICT": "không cho xóa"}[on_delete]
            rows.append(f"| `{ref}` | `{table.name}` | `{', '.join(cols)}` | {kind} | {action} |")
    return rows


def dictionary() -> list[str]:
    out: list[str] = []
    for group, title in GROUPS.items():
        out += [f"### {title}", ""]
        for table in (t for t in TABLE_LIST if t.group == group):
            fk_map = {cols[0]: ref for cols, ref, _rc, _d in table.fks if len(cols) == 1}
            out += [f"#### `{table.name}` - {table.comment}", "",
                    "| Cột | Kiểu | Khóa | Bắt buộc | Ý nghĩa |", "|---|---|---|---|---|"]
            for col in table.cols:
                keys = []
                if col.name in table.pk:
                    keys.append("PK")
                if col.name in fk_map:
                    keys.append(f"FK → `{fk_map[col.name]}`")
                if any(col.name in u for u in table.uniques):
                    keys.append("UNIQUE")
                sql = col.sql + (" (tự tăng)" if col.auto else "") \
                    + (" (cột tính toán)" if col.generated else "")
                out.append(f"| `{col.name}` | {sql} | {' '.join(keys)} | {'' if col.null else 'x'} | {col.comment} |")
            if table.checks:
                out.append("")
                out.append("Ràng buộc kiểm tra: " + "; ".join(f"`{c}`" for c in table.checks))
            out.append("")
    return out


def write_markdown() -> Path:
    text = (OUT / "_thiet_ke_mo_dau.md").read_text(encoding="utf-8")
    groups = {g: [t for t in TABLE_LIST if t.group == g] for g in GROUPS}
    owned = {table for e in ENTITIES for table in e.owned + e.subtypes}
    lines = [text.rstrip(), "",
             "## 4. Sơ đồ thực thể liên kết (ERD)", "",
             "Mở bằng VS Code (cài *Markdown Preview Mermaid Support*), GitHub, hoặc dán vào <https://mermaid.live>. "
             "Ký hiệu: `||--o{` = 1 - n, `|o--o{` = 0..1 - n (khóa ngoại được để trống), `||--o|` = 1 - 0..1.", ""]
    for group, title in GROUPS.items():
        related = set(t.name for t in groups[group])
        lines += [f"### {title}", ""] + mermaid([TABLES[n] for n in TABLES if n in related]) + [""]
    lines += ["### Toàn bộ quan hệ giữa các bảng (chỉ tên bảng)", "", "```mermaid", "erDiagram"]
    for table in TABLE_LIST:
        for cols, ref, _rc, _d in table.fks:
            nullable = any(next(c for c in table.cols if c.name == col).null for col in cols)
            card = "||--o|" if tuple(cols) == table.pk else ("|o--o{" if nullable else "||--o{")
            lines.append(f'    {ref} {card} {table.name} : "{", ".join(cols)}"')
    lines += ["```", "", "## 5. Mô hình quan hệ - danh sách khóa ngoại", ""] + relation_rows()
    lines += ["", "## 6. Từ điển dữ liệu", "",
              f"Tổng cộng **{len(TABLE_LIST)} bảng**: {len(groups['HT'])} bảng hệ thống, {len(groups['DM'])} bảng "
              f"danh mục, {len(groups['NV'])} bảng nghiệp vụ. Bảng chi tiết (xóa / ghi lại cùng thực thể cha): "
              + ", ".join(f"`{t}`" for t in sorted(owned)) + ".", ""] + dictionary()
    path = OUT / "thiet_ke_csdl.md"
    path.write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    for written in (write_sql(), write_markdown()):
        print("Đã ghi", written.relative_to(ROOT))
