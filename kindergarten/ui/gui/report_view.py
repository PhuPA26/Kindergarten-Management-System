"""Hiển thị báo cáo như một văn bản bình thường (thay cho bảng ký tự máy móc):
tiêu đề rõ ràng, câu mở đầu tự nhiên, phần tóm tắt dạng gạch đầu dòng, bảng số liệu thật, ghi chú / ý kiến
trong khung màu. Kèm khung trượt nửa trang (ReportDrawer) đóng bằng nút ✕ hoặc phím Esc.
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from ...exceptions import KindergartenError
from ...reports.reports import Report, ReportData, _display
from .widgets import COLORS, DataTable, open_folder, px, tint, ui_font

if TYPE_CHECKING:
    from ...reports.submissions import SubmittedReport
    from ...system import KindergartenSystem

# Chữ viết tắt giữ nguyên chữ in hoa khi làm mềm câu chữ
ABBREVIATIONS = {"BGH", "BMI", "SĐT", "HĐ", "GV", "CN", "CCCD", "BC", "TXT", "CSV", "ID", "OK", "PH", "NV"}
STATUS_CHIPS = {"DRAFT": "muted", "SENT": "info", "APPROVED": "ok", "REVISE": "warn", "FINAL": "ok"}


def soften(text: Any) -> str:
    """'Trẻ CHƯA được đón về' -> 'Trẻ chưa được đón về'; 'CHƯA ĐÓN' -> 'Chưa đón' (giữ chữ viết tắt, mã số)."""
    text = str(text)
    if not text:
        return text

    def fix(match: re.Match) -> str:
        word = match.group(0)
        if word in ABBREVIATIONS or any(ch.isdigit() for ch in word) or len(word) < 2 or not word.isupper():
            return word
        return word.lower()

    result = re.sub(r"\w+", fix, text)
    if result != text and text[:1].isupper() and result[:1].islower():
        result = result[:1].upper() + result[1:]
    return result


_SECTION = re.compile(r"^\[\s*(.+?)\s*\]$")                                     # [ CHUYÊN CẦN ]
_BULLET = re.compile(r"^([-•*]|[①-⑳])\s*(.*)$")                       # - mục / ① mục
_KEY_VALUE = re.compile(r"^([^:|]{1,60}?)\s*:\s+(.+)$")                          # Nhãn : giá trị


def _mostly_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) >= 0.8 * len(letters)


_MONEY = re.compile(r"^-?[\d.,]+\s*đ$")                                         # 3.200.000 đ
# giá trị ngắn, độ dài gần như cố định: số đo, %, ngày, kỳ, giờ, mã -> căn giữa cho bảng cân đối
_SHORT = re.compile(r"^(-?[\d.,]+\s*(%|cm|kg|kcal|tuổi|tháng|năm)?|\d{1,2}/\d{1,2}(/\d{4})?|\d{1,2}:\d{2}"
                    r"|[A-Z]{1,3}\d{2,5}|-|—)$")


def _column_anchor(values: list[str], fmt: str | None) -> str:
    """Căn lề cột theo nội dung: tiền bên phải, số / ngày / mã ngắn ở giữa, chữ bên trái."""
    filled = [v.strip() for v in values if v.strip()]
    if fmt in ("money", "percent") or (filled and all(_MONEY.match(v) for v in filled)):
        return "e"
    if filled and all(_SHORT.match(v) for v in filled):
        return "center"
    return "w"


def _cap_first(text: str) -> str:
    """Viết hoa chữ cái đầu tiên (bỏ qua ký hiệu đứng trước như ④)."""
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1:]
    return text


def heading_case(text: str) -> str:
    """'HỒ SƠ TRẺ: NGUYỄN MINH KHANG' -> 'Hồ sơ trẻ: Nguyễn Minh Khang'; '[ TRẺ - LỚP ]' -> 'Trẻ - lớp'
    (phần tên riêng sau dấu ':' / 'CỦA' viết hoa chữ đầu mỗi từ)."""
    text = text.strip().rstrip(":").strip()
    for sep in (": ", " CỦA "):
        if sep in text:
            left, right = text.split(sep, 1)
            if _mostly_upper(right):
                right = right.title()
            return _cap_first(soften(left)) + (sep.lower() if sep.strip().isalpha() else sep) + right
    return _cap_first(soften(text))


def _stamp(value: str) -> tuple[str, str]:
    """'2026-11-17T11:24:05' -> ('11:24', '17/11/2026')."""
    value = value.replace("T", " ")
    day = value[:10]
    try:
        y, m, d = day.split("-")
        day = f"{d}/{m}/{y}"
    except ValueError:
        pass
    return value[11:16], day


# =============================================================================
class ReportView(tk.Frame):
    """Khung xem báo cáo cuộn được, chữ thường, bảng thật nhúng bên trong."""

    def __init__(self, master: tk.Misc, height: int = 12) -> None:
        c = COLORS
        super().__init__(master, bg=c["card"])
        self.text = tk.Text(self, wrap="word", height=height, cursor="arrow", font=ui_font(1), padx=px(26),
                            pady=px(18), highlightthickness=0, bd=0, bg=c["card"], fg=c["text"])
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self._tables: list[tk.Frame] = []
        self._pad = px(26)
        self.text.bind("<Configure>", lambda _e: self._fit_tables())
        t = self.text.tag_configure
        t("h1", font=ui_font(8, "bold"), foreground=c["navy"], spacing3=px(4))
        t("sub", font=ui_font(0), foreground=c["muted"], spacing3=px(6))
        t("lead", font=ui_font(1), foreground=c["text"], spacing1=px(6), spacing3=px(4))
        t("h2", font=ui_font(3, "bold"), foreground=c["navy"], spacing1=px(20), spacing3=px(8))
        t("count", font=ui_font(0), foreground=c["muted"])
        t("body", font=ui_font(1), foreground=c["text"], spacing1=px(2), spacing3=px(2))
        t("muted", font=ui_font(0), foreground=c["muted"])
        t("b", font=ui_font(1, "bold"), foreground=c["navy"])
        t("item", lmargin1=px(4), lmargin2=px(24), spacing1=px(3), spacing3=px(3))
        t("subitem", lmargin1=px(28), lmargin2=px(46), spacing1=px(1), spacing3=px(1))
        t("dot", foreground=c["primary"], font=ui_font(1, "bold"))
        t("subdot", foreground=c["muted_light"])
        for name, color in (("quote", c["primary"]), ("okquote", c["ok"]), ("warnquote", c["warn"])):
            t(name, background=tint(color, 0.92), lmargin1=px(16), lmargin2=px(16), rmargin=px(16),
              spacing1=px(10), spacing3=px(10), font=ui_font(1), foreground=c["text"])
        for name, color in (("chip_info", c["primary"]), ("chip_ok", c["ok"]), ("chip_warn", c["warn"]),
                            ("chip_muted", c["muted"])):
            t(name, background=tint(color, 0.86), foreground=color, font=ui_font(0, "bold"))
        t("divider", font=ui_font(-6), foreground=c["border_strong"], spacing1=px(16), spacing3=px(16))

    # ------------------------------------------------------------------ tiện ích ghi
    def _put(self, text: str, *tags: str) -> None:
        self.text.insert("end", text, tags)

    def _begin(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for holder in self._tables:
            holder.destroy()
        self._tables.clear()

    def _end(self) -> None:
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def show_message(self, message: str) -> None:
        self._begin()
        self._put("\n" + message + "\n", "muted")
        self._end()

    # ------------------------------------------------------------------ bảng nhúng
    MAX_LINE = 1100   # độ rộng tối đa của phần chữ (thiết kế ở 100%) - màn rộng thì căn giữa cho dễ đọc

    def _fit_tables(self) -> None:
        total = self.text.winfo_width()
        pad = max(px(26), (total - px(self.MAX_LINE)) // 2)
        if pad != self._pad:
            self._pad = pad
            self.text.configure(padx=pad)
        width = total - 2 * pad - px(6)
        if width > 100:
            for holder in self._tables:
                holder.configure(width=width)

    def _table(self, data: ReportData) -> None:
        headers = [soften(h) for h in data.headers]
        cells = [[soften(_display(v, data.column_format(i))) for i, v in enumerate(row)] for row in data.rows]
        columns = []
        for i, header in enumerate(headers):
            longest = max([len(header)] + [len(r[i][:60]) for r in cells if i < len(r)])
            anchor = _column_anchor([r[i] for r in cells if i < len(r)], data.column_format(i))
            columns.append((header, min(max(longest * 8 + 26, 64), 380), anchor))
        visible = min(len(cells), 12)
        row_h = int(ttk.Style().lookup("Treeview", "rowheight") or px(30))
        height = row_h * (visible + 1) + px(30)
        width = max(self.text.winfo_width() - 2 * self._pad - px(6), px(560))
        holder = tk.Frame(self.text, bg=COLORS["card"], width=width, height=height)
        holder.pack_propagate(False)
        table = DataTable(holder, columns, height=visible)
        table.pack(fill="both", expand=True)
        tags = ["warn" if any(str(v).upper().startswith(("CHƯA", "QUÁ HẠN")) for v in row) else None
                for row in data.rows]
        table.set_rows(cells, tags=tags)
        self.text.window_create("end", window=holder)
        self._put("\n")
        self._tables.append(holder)

    # ------------------------------------------------------------------ các phần của báo cáo
    def _summary(self, summary: Iterable[tuple[str, str]]) -> None:
        for label, value in summary:
            nested = label.startswith("  ")
            label, value = soften(label.strip()), soften(str(value).strip())
            if nested:
                self._put("◦  ", "subitem", "subdot")
            else:
                self._put("•  ", "item", "dot")
            tag = "subitem" if nested else "item"
            labels = [p.strip() for p in label.split(" / ")]
            values = [p.strip() for p in value.split(" / ")]
            if len(labels) > 1 and len(labels) == len(values):   # "Có mặt / vắng: 5 / 1" -> "Có mặt 5, vắng 1"
                for i, (lab, val) in enumerate(zip(labels, values)):
                    lab = lab[:1].upper() + lab[1:] if i == 0 else lab[:1].lower() + lab[1:]
                    self._put(f"{lab} ", tag, "body")
                    self._put(val, tag, "b")
                    self._put(", " if i < len(labels) - 1 else "", tag, "body")
            else:
                self._put(f"{label}: ", tag, "body")
                self._put(value, tag, "b" if len(value) <= 22 else "body")
            self._put("\n", tag)

    def _report_body(self, data: ReportData, header: bool = True) -> None:
        if header:
            self._put(soften(data.title) + "\n", "h1")
            when = data.generated_at
            parts = [soften(data.subtitle)] if data.subtitle else []
            parts.append(f"lập lúc {when:%H:%M} ngày {when:%d/%m/%Y}")
            line = "  •  ".join(parts)
            self._put(line[:1].upper() + line[1:] + "\n", "sub")
        if data.summary:
            self._put("Tóm tắt\n", "h2")
            self._summary(data.summary)
        if len(data.headers) == 1:   # VD: hôm nay không phải ngày học -> chỉ là một câu
            self._put("Ghi chú\n", "h2")
            for row in data.rows:
                self._put(soften(row[0]) + "\n", "body")
            return
        self._put("Số liệu chi tiết", "h2")
        self._put(f"   {len(data.rows)} dòng\n", "h2", "count")
        if data.rows:
            self._table(data)
        else:
            self._put("Chưa có số liệu nào trong kỳ này.\n", "muted")

    def _quote(self, text: str, tag: str = "quote") -> None:
        self._put(text.strip() + "\n", tag)

    # ------------------------------------------------------------------ API
    def render_report(self, report: Report | ReportData, conclusion: str = "",
                      conclusion_title: str = "Kết luận / chỉ đạo của Ban giám hiệu") -> None:
        data = report.data if isinstance(report, Report) else report
        self._begin()
        self._report_body(data)
        if conclusion.strip():
            self._put(conclusion_title + "\n", "h2")
            self._quote(conclusion)
        self._end()

    def _submission(self, item: "SubmittedReport", system: "KindergartenSystem") -> None:
        data = item.report(system).data
        self._put(soften(item.label) + "\n", "h1")
        self._put(f"{item.id}  •  {soften(item.period_text)}\n", "sub")
        chip = STATUS_CHIPS.get(item.status.name, "muted")
        self._put(f"  {item.status.value}  ", f"chip_{chip}")
        self._put("\n", "body")
        sentence = f"{item.author_name or 'Người lập'} ({item.author_role}) đã lập báo cáo này"
        if item.sent_at:
            time, day = _stamp(item.sent_at)
            sentence += f" và gửi Ban giám hiệu lúc {time} ngày {day}"
        when = data.generated_at
        sentence += f". Số liệu được chốt lúc {when:%H:%M} ngày {when:%d/%m/%Y}.\n"
        self._put(sentence, "lead")
        if item.review_comment:
            self._put("Ý kiến của Ban giám hiệu\n", "h2")
            self._quote(item.review_comment, "okquote" if item.status.name in ("APPROVED", "FINAL") else "warnquote")
            if item.reviewed_at:
                time, day = _stamp(item.reviewed_at)
                self._put(f"— {item.reviewed_by}, {time} ngày {day}\n", "muted")
        self._put("Ghi chú của người lập\n", "h2")
        if item.note:
            self._quote(item.note)
        else:
            self._put("Người lập không để lại ghi chú.\n", "muted")
        self._report_body(data, header=False)

    def render_submission(self, item: "SubmittedReport", system: "KindergartenSystem") -> None:
        self._begin()
        self._submission(item, system)
        self._end()

    def render_plain(self, text: str, title: str = "", top: str = "h1") -> None:
        """Văn bản kiểu máy (bảng kẻ '+---+', tiêu đề IN HOA, 'Nhãn : giá trị', '[ MỤC ]') -> văn bản bình thường:
        bảng thật, tiêu đề chữ thường, gạch đầu dòng - cùng kiểu với phần báo cáo.
        Dòng đầu tiên là tiêu đề của văn bản (cỡ `top`: h1 trong khung xem, h2 khi nằm trong một màn hình)."""
        self._begin()
        has_title = bool(title)
        if title:
            self._put(heading_case(title) + "\n", top)
        lines = str(text).splitlines()
        i = 0
        while i < len(lines):
            raw = lines[i].rstrip()
            line = raw.strip()
            indent = len(raw) - len(raw.lstrip())
            if not line:
                i += 1
                continue
            if line.startswith(("+", "|")):                         # bảng kẻ khung -> bảng thật
                block = []
                while i < len(lines) and lines[i].strip().startswith(("+", "|")):
                    block.append(lines[i].strip())
                    i += 1
                self._plain_table(block)
                continue
            i += 1
            section = _SECTION.match(line)
            if not has_title:                                       # dòng đầu = tiêu đề của văn bản
                self._put(heading_case(section.group(1) if section else line) + "\n", top)
                has_title = True
                continue
            next_is_table = i < len(lines) and lines[i].strip().startswith("+")
            tag = "subitem" if indent >= 4 else "item"
            bullet = _BULLET.match(line)
            marker = ""
            if bullet:
                marker, line = bullet.group(1), bullet.group(2)
            pair = _KEY_VALUE.match(line)
            is_pair = bool(pair) and len(pair.group(1)) <= 40 and not _mostly_upper(pair.group(2))
            if section or (not is_pair and (next_is_table or _mostly_upper(line) or line.endswith(":"))):
                self._put(heading_case((marker + " " if marker not in ("", "-", "•", "*") else "")
                                       + (section.group(1) if section else line)) + "\n", "h2")
                continue
            if is_pair:                                             # "Nhãn : giá trị" -> gạch đầu dòng
                label = soften(pair.group(1))
                label = label[:1].upper() + label[1:]
                if marker not in ("", "-", "•", "*"):
                    label = f"{marker} {label}"
                self._summary([(("  " if tag == "subitem" else "") + label, pair.group(2))])
            elif bullet or indent >= 2:
                if marker and marker not in ("-", "•", "*"):
                    self._put(f"{marker}  ", tag, "dot")
                else:
                    self._put("◦  " if tag == "subitem" else "•  ", tag, "subdot" if tag == "subitem" else "dot")
                self._put(soften(line) + "\n", tag, "body")
            else:
                self._put(soften(line) + "\n", "body")
        self._end()

    def _plain_table(self, block: list[str]) -> None:
        rows = [[cell.strip() for cell in line.strip("|").split(" | ")] for line in block if line.startswith("|")]
        if not rows:
            return
        headers, body = rows[0], rows[1:]
        body = [r for r in body if not (len(r) == 1 and "không có dữ liệu" in r[0])]
        if not body:
            self._put("Không có dữ liệu.\n", "muted")
            return
        width = len(headers)
        body = [(r + [""] * width)[:width] for r in body]
        self._table(ReportData("", headers, body))

    def render_submissions(self, items: list["SubmittedReport"], system: "KindergartenSystem") -> None:
        self._begin()
        for index, item in enumerate(items):
            if index:
                self._put("\n" + "─" * 40 + "\n", "divider")
            self._submission(item, system)
        self._end()


# =============================================================================
class ReportDrawer(tk.Frame):
    """Khung báo cáo phủ kín vùng bên phải menu (thanh tiêu đề + nội dung), trượt vào từ mép phải;
    đóng bằng nút ✕ hoặc Esc."""

    def __init__(self, host: tk.Misc, title: str, report: Report | None = None,
                 export_dir: Path | None = None, notice: str = "") -> None:
        c = COLORS
        super().__init__(host, bg=c["card"], highlightthickness=1, highlightbackground=c["border_strong"])
        self.host, self.report, self.export_dir = host, report, export_dir or Path("exports")
        tk.Frame(self, bg=c["primary"], height=px(4)).pack(fill="x")
        header = tk.Frame(self, bg=c["card"], padx=px(20), pady=px(12))
        header.pack(fill="x")
        close = tk.Label(header, text="✕", font=ui_font(5), fg=c["muted"], bg=c["card"], padx=px(10), pady=px(2),
                         cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: self.close())
        close.bind("<Enter>", lambda _e: close.configure(bg=tint(c["warn"], 0.88), fg=c["warn"]))
        close.bind("<Leave>", lambda _e: close.configure(bg=c["card"], fg=c["muted"]))
        tk.Label(header, text=title, font=ui_font(3, "bold"), fg=c["navy"], bg=c["card"], anchor="w").pack(
            side="left", fill="x", expand=True)
        if report is not None:   # hàng nút xuất file riêng, không che tiêu đề
            tools = tk.Frame(self, bg=c["card"], padx=px(20))
            tools.pack(fill="x", pady=(0, px(10)))
            tk.Label(tools, text="Nhấn ✕ hoặc Esc để đóng", font=ui_font(-1), fg=c["muted"], bg=c["card"]).pack(
                side="right")
            ttk.Button(tools, text="Xuất TXT", command=lambda: self._export("txt")).pack(side="left")
            ttk.Button(tools, text="Xuất Excel", command=lambda: self._export("xlsx")).pack(side="left", padx=4)
            ttk.Button(tools, text="Xuất PDF", command=lambda: self._export("pdf")).pack(side="left", padx=4)
            ttk.Button(tools, text="Xuất Excel (CSV)", command=lambda: self._export("csv")).pack(
                side="left", padx=(px(6), 0))
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")
        if notice:
            tk.Label(self, text="✓  " + notice, font=ui_font(0, "bold"), fg=c["ok"], bg=tint(c["ok"], 0.9),
                     anchor="w", padx=px(20), pady=px(8)).pack(fill="x")
        self.view = ReportView(self)
        self.view.pack(fill="both", expand=True)
        top = self.winfo_toplevel()
        self._esc = top.bind("<Escape>", lambda _e: self.close(), add="+")
        setattr(host, "_report_drawer", self)
        self._slide(1.7)

    def _slide(self, relx: float) -> None:
        if not self.winfo_exists():
            return
        self.place(relx=relx, rely=0, relwidth=1, relheight=1, anchor="ne")
        self.lift()
        if relx > 1.0:
            self.after(12, self._slide, max(1.0, relx - 0.14))

    @classmethod
    def open(cls, host: tk.Misc, title: str, **kwargs: Any) -> "ReportDrawer":
        previous = getattr(host, "_report_drawer", None)
        if previous is not None and previous.winfo_exists():
            previous.close()
        return cls(host, title, **kwargs)

    def close(self) -> None:
        try:
            self.winfo_toplevel().unbind("<Escape>", self._esc)
        except tk.TclError:
            pass
        if getattr(self.host, "_report_drawer", None) is self:
            setattr(self.host, "_report_drawer", None)
        self.destroy()

    def _export(self, fmt: str) -> None:
        try:
            path = self.report.export(fmt=fmt, directory=self.export_dir)
        except KindergartenError as exc:
            messagebox.showerror("Không xuất được", exc.message, parent=self)
            return
        if messagebox.askyesno("Đã xuất file", f"Đã lưu: {path}\n\nMở thư mục chứa file?", parent=self):
            open_folder(path.parent)


def close_drawer(host: tk.Misc) -> None:
    drawer = getattr(host, "_report_drawer", None)
    if drawer is not None and drawer.winfo_exists():
        drawer.close()
