"""T05 - Các hàm tiện ích dùng chung.

- Kiểm tra dữ liệu: số điện thoại, ngày tháng, giờ, số tiền, họ tên.
- Định dạng hiển thị: tiền VNĐ, ngày dd/mm/yyyy, phần trăm, bảng văn bản.
- Hỗ trợ tìm kiếm tiếng Việt không dấu ("nguyen" khớp "Nguyễn").
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Sequence

from .exceptions import ValidationError

WEEKDAY_NAMES = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")
SCHOOL_WEEKDAYS = (0, 1, 2, 3, 4)  # Thứ 2 → Thứ 6


# =============================================================================
# Văn bản
# =============================================================================
def normalize_spaces(text: Any) -> str:
    """Bỏ khoảng trắng thừa và chuẩn hóa Unicode NFC (tránh lỗi chữ tổ hợp khi gõ tiếng Việt)."""
    return " ".join(unicodedata.normalize("NFC", str(text if text is not None else "")).split())


def remove_accents(text: Any) -> str:
    """Bỏ dấu tiếng Việt: 'Nguyễn Đức' -> 'Nguyen Duc'."""
    decomposed = unicodedata.normalize("NFD", str(text if text is not None else ""))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.replace("đ", "d").replace("Đ", "D")


def normalize_text(text: Any) -> str:
    """Chuỗi dùng để so khớp/tìm kiếm: chữ thường, không dấu, gọn khoảng trắng."""
    return normalize_spaces(remove_accents(text)).lower()


def text_contains(text: Any, keyword: Any) -> bool:
    """Tìm kiếm không phân biệt hoa/thường và dấu."""
    return normalize_text(keyword) in normalize_text(text)


def require_text(value: Any, field: str = "Giá trị", max_length: int = 200) -> str:
    text = normalize_spaces(value)
    if not text:
        raise ValidationError(f"{field} không được để trống.")
    if len(text) > max_length:
        raise ValidationError(f"{field} quá dài (tối đa {max_length} ký tự).")
    return text


_NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '\-.][^\W\d_]+)*\.?$")


def validate_name(value: Any, field: str = "Họ tên") -> str:
    """Họ tên chỉ gồm chữ cái (có dấu) và khoảng trắng; tự viết hoa chữ cái đầu mỗi từ."""
    name = require_text(value, field, max_length=60)
    if not _NAME_PATTERN.match(name):
        raise ValidationError(f"{field} '{name}' không hợp lệ (chỉ gồm chữ cái và khoảng trắng).")
    return " ".join(word[:1].upper() + word[1:].lower() for word in name.split(" "))


# =============================================================================
# Số điện thoại
# =============================================================================
_PHONE_PATTERN = re.compile(r"^0(?:[35789]\d{8}|2\d{9})$")


def normalize_phone(value: Any) -> str:
    phone = re.sub(r"[\s.\-()]", "", str(value if value is not None else ""))
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84") and len(phone) in (11, 12):
        phone = "0" + phone[2:]
    return phone


def is_valid_phone(value: Any) -> bool:
    return bool(_PHONE_PATTERN.match(normalize_phone(value)))


def validate_phone(value: Any, required: bool = True, field: str = "Số điện thoại") -> str:
    """SĐT Việt Nam: di động 10 số (03x, 05x, 07x, 08x, 09x) hoặc cố định 11 số (02x).

    Chấp nhận dạng +84..., có dấu cách/chấm/gạch; trả về dạng chuẩn 0xxxxxxxxx.
    """
    phone = normalize_phone(value)
    if not phone:
        if required:
            raise ValidationError(f"{field} không được để trống.")
        return ""
    if not _PHONE_PATTERN.match(phone):
        raise ValidationError(
            f"{field} '{value}' không hợp lệ (di động 10 số bắt đầu bằng 03/05/07/08/09 "
            "hoặc cố định 11 số bắt đầu bằng 02)."
        )
    return phone


# =============================================================================
# Ngày, giờ, tháng
# =============================================================================
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")


def parse_date(value: Any, field: str = "Ngày") -> date:
    """Nhận date/datetime hoặc chuỗi dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy, dd.mm.yyyy."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value if value is not None else "").strip()
    if not text:
        raise ValidationError(f"{field} không được để trống.")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"{field} '{text}' không hợp lệ (định dạng dd/mm/yyyy).")


def parse_optional_date(value: Any, field: str = "Ngày") -> date | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return parse_date(value, field)


def validate_not_future(value: Any, field: str = "Ngày", today: date | None = None) -> date:
    d = parse_date(value, field)
    if d > (today or date.today()):
        raise ValidationError(f"{field} ({format_date(d)}) không được ở tương lai.")
    return d


def format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def parse_time(value: Any, field: str = "Giờ") -> time:
    """Nhận '7:30', '07:30', '7h30', '7h' hoặc đối tượng time."""
    if isinstance(value, time):
        return value
    text = str(value if value is not None else "").strip().lower().replace("h", ":").replace(".", ":")
    if text.endswith(":"):
        text += "00"
    match = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?", text)
    if not match:
        raise ValidationError(f"{field} '{value}' không hợp lệ (định dạng HH:MM).")
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValidationError(f"{field} '{value}' không hợp lệ.")
    return time(hour, minute)


def format_time(value: time | None) -> str:
    return value.strftime("%H:%M") if value else ""


def calculate_age(dob: date, on: date | None = None) -> int:
    """Tuổi tròn (số năm đã đủ) tính đến ngày `on` (mặc định hôm nay)."""
    on = on or date.today()
    years = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
    return max(years, 0)


def age_in_months(dob: date, on: date | None = None) -> int:
    on = on or date.today()
    months = (on.year - dob.year) * 12 + (on.month - dob.month) - (on.day < dob.day)
    return max(months, 0)


def format_age(dob: date, on: date | None = None) -> str:
    years, months = divmod(age_in_months(dob, on), 12)
    if years == 0:
        return f"{months} tháng"
    return f"{years} tuổi" + (f" {months} tháng" if months else "")


def add_months(d: date, months: int) -> date:
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_dates(d: date, days: int = 5) -> list[date]:
    start = monday_of(d)
    return [start + timedelta(days=i) for i in range(days)]


def month_bounds(month: int, year: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def month_dates(month: int, year: int) -> list[date]:
    first, last = month_bounds(month, year)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def school_days(month: int, year: int, until: date | None = None) -> list[date]:
    """Các ngày đi học (Thứ 2 - Thứ 6) trong tháng, có thể giới hạn đến ngày `until`."""
    return [d for d in month_dates(month, year)
            if d.weekday() in SCHOOL_WEEKDAYS and (until is None or d <= until)]


def weekday_name(value: date | int) -> str:
    index = value.weekday() if isinstance(value, date) else int(value)
    return WEEKDAY_NAMES[index]


def parse_weekday(value: Any) -> int:
    """Trả về chỉ số thứ theo Python (0 = Thứ 2 ... 6 = Chủ nhật).

    - Số nguyên: hiểu là chỉ số Python 0..6.
    - Chuỗi: '2'..'7' hoặc 'Thứ 2'..'Thứ 7', 'CN'/'Chủ nhật'.
    """
    if isinstance(value, bool):
        raise ValidationError("Thứ không hợp lệ.")
    if isinstance(value, int):
        if 0 <= value <= 6:
            return value
        raise ValidationError("Thứ không hợp lệ.")
    text = normalize_text(value).replace("thu", "").strip()
    if text in ("cn", "chu nhat", "8"):
        return 6
    if text.isdigit() and 2 <= int(text) <= 7:
        return int(text) - 2
    raise ValidationError(f"Thứ '{value}' không hợp lệ (nhập 2-7 hoặc CN).")


def parse_month(value: Any) -> tuple[int, int]:
    """Trả về (tháng, năm). Nhận '11/2026', '2026-11', (11, 2026) hoặc đối tượng date."""
    if isinstance(value, (date, datetime)):
        month, year = value.month, value.year
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        month, year = value
    else:
        text = str(value if value is not None else "").strip()
        match = re.fullmatch(r"(\d{1,2})\s*[/\-.]\s*(\d{4})", text)
        if match:
            month, year = int(match.group(1)), int(match.group(2))
        else:
            match = re.fullmatch(r"(\d{4})\s*[/\-.]\s*(\d{1,2})", text)
            if not match:
                raise ValidationError(f"Tháng '{text}' không hợp lệ (định dạng mm/yyyy).")
            year, month = int(match.group(1)), int(match.group(2))
    try:
        month, year = int(month), int(year)
    except (TypeError, ValueError):
        raise ValidationError("Tháng/năm không hợp lệ.") from None
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise ValidationError(f"Tháng {month}/{year} không hợp lệ.")
    return month, year


def month_label(month: int, year: int) -> str:
    return f"{month:02d}/{year}"


def previous_month(month: int, year: int) -> tuple[int, int]:
    return (12, year - 1) if month == 1 else (month - 1, year)


def next_month(month: int, year: int) -> tuple[int, int]:
    return (1, year + 1) if month == 12 else (month + 1, year)


def current_month(today: date | None = None) -> tuple[int, int]:
    today = today or date.today()
    return today.month, today.year


def in_month(d: date, month: int, year: int) -> bool:
    return d.month == month and d.year == year


# =============================================================================
# Tiền và số
# =============================================================================
def parse_money(value: Any, field: str = "Số tiền", allow_zero: bool = True) -> int:
    """Chuyển chuỗi tiền thành số nguyên VNĐ.

    Chấp nhận: 2500000, '2.500.000', '2,500,000', '2.500.000 đ', '300k', '2,5tr', '1.5 triệu'.
    """
    if isinstance(value, bool):
        raise ValidationError(f"{field} không hợp lệ.")
    if isinstance(value, (int, float)):
        amount: float = value
    else:
        text = normalize_text(value).replace(" ", "")
        text = re.sub(r"(vnd|dong|d)$", "", text)
        match = re.fullmatch(r"(\d[\d.,]*)(k|tr|trieu)?", text)
        if not match:
            raise ValidationError(f"{field} '{value}' không hợp lệ.")
        number, unit = match.groups()
        if unit:
            number = number.replace(",", ".")
            if number.count(".") > 1:
                raise ValidationError(f"{field} '{value}' không hợp lệ.")
            amount = Decimal(number) * (1_000 if unit == "k" else 1_000_000)
        else:
            # L18: không có đơn vị thì chỉ nhận số nguyên hoặc nhóm 3 chữ số (2.500.000 / 2,500,000)
            if not re.fullmatch(r"\d+|\d{1,3}(?:[.,]\d{3})+", number):
                raise ValidationError(f"{field} '{value}' không rõ ràng "
                                      "(nhập 2500000, 2.500.000 hoặc 2,5tr).")
            amount = int(re.sub(r"[.,]", "", number))
    if amount < 0:
        raise ValidationError(f"{field} không được âm.")
    if not allow_zero and amount == 0:
        raise ValidationError(f"{field} phải lớn hơn 0.")
    return round_money(amount)


validate_money = parse_money


def round_money(amount: Any) -> int:
    """Làm tròn tiền về đồng theo quy tắc 0,5 làm tròn lên (K04) - không dùng kiểu 'ngân hàng' của round()."""
    return int(Decimal(str(amount)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def id_sort_key(value: Any) -> tuple[str, int, str]:
    """Khóa sắp xếp mã theo (tiền tố, số): HD999 < HD1000 (L25)."""
    text = str(value or "")
    match = re.fullmatch(r"([A-Za-z]*)(\d+)", text)
    if match:
        return match.group(1).upper(), int(match.group(2)), ""
    return text.upper(), -1, text


def format_vnd(amount: Any) -> str:
    """2500000 -> '2.500.000 đ'."""
    value = int(round(amount or 0))
    return f"{value:,}".replace(",", ".") + " đ"


def parse_number(value: Any, field: str = "Giá trị", min_value: float | None = None,
                 max_value: float | None = None, integer: bool = False) -> float | int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} không hợp lệ.")
    if isinstance(value, (int, float)):
        number: float = value
    else:
        text = str(value if value is not None else "").strip().replace(",", ".")
        if not text:
            raise ValidationError(f"{field} không được để trống.")
        try:
            number = float(text)
        except ValueError:
            raise ValidationError(f"{field} '{value}' phải là số.") from None
    if integer:
        if number != int(number):
            raise ValidationError(f"{field} phải là số nguyên.")
        number = int(number)
    if min_value is not None and number < min_value:
        raise ValidationError(f"{field} không được nhỏ hơn {format_number(min_value, 2).rstrip('0').rstrip(',')}.")
    if max_value is not None and number > max_value:
        raise ValidationError(f"{field} không được lớn hơn {format_number(max_value, 2).rstrip('0').rstrip(',')}.")
    return number


def parse_int(value: Any, field: str = "Số", min_value: int | None = None, max_value: int | None = None) -> int:
    return int(parse_number(value, field, min_value, max_value, integer=True))


def parse_float(value: Any, field: str = "Số", min_value: float | None = None,
                max_value: float | None = None) -> float:
    return float(parse_number(value, field, min_value, max_value))


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize_text(value)
    if text in ("c", "co", "y", "yes", "1", "true", "x", "dung", "d"):
        return True
    if text in ("", "k", "khong", "n", "no", "0", "false", "sai"):
        return False
    raise ValidationError(f"Giá trị '{value}' không hợp lệ (nhập c = có, k = không).")


def format_number(value: float, digits: int = 1) -> str:
    """Số thập phân kiểu Việt Nam: 16.5 -> '16,5'."""
    return f"{value:.{digits}f}".replace(".", ",")


def format_percent(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{format_number(value, digits)}%"


def format_rate(rate: float) -> str:
    """Tỷ lệ (0..1) thành số phần trăm gọn, không mất chữ số: 0.125 -> '12,5'; 0.07 -> '7' (L17)."""
    text = f"{Decimal(str(rate)) * 100:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


# =============================================================================
# Bảng văn bản (console, file .txt)
# =============================================================================
def text_width(value: Any) -> int:
    text = unicodedata.normalize("NFC", str(value))
    return sum(0 if unicodedata.combining(ch) else 1 for ch in text)


def _fit(text: str, width: int) -> str:
    if text_width(text) <= width:
        return text
    return text[: max(width - 3, 1)] + "..."


_NUMERIC_CELL = re.compile(r"^[-+]?\d[\d.,]*(?: ?(?:đ|%|kg|cm|kcal))?$")


def format_table(headers: Sequence[Any], rows: Iterable[Sequence[Any]], title: str | None = None,
                 aligns: Sequence[str] | None = None, max_width: int = 42) -> str:
    """Tạo bảng văn bản có khung. Cột toàn số/tiền/% được căn phải tự động."""
    header_cells = [str(h) for h in headers]
    ncols = len(header_cells)
    body: list[list[str]] = []
    for row in rows:
        cells = ["" if c is None else str(c) for c in row]
        cells = (cells + [""] * ncols)[:ncols]
        body.append([_fit(c, max_width) for c in cells])
    widths = [max([text_width(header_cells[i])] + [text_width(r[i]) for r in body]) for i in range(ncols)]
    if aligns is None:
        aligns = []
        for i in range(ncols):
            values = [r[i] for r in body if r[i] not in ("", "-")]
            numeric = bool(values) and all(_NUMERIC_CELL.match(v) for v in values)
            aligns.append("r" if numeric else "l")

    def pad(text: str, width: int, align: str) -> str:
        gap = width - text_width(text)
        if align == "r":
            return " " * gap + text
        if align == "c":
            left = gap // 2
            return " " * left + text + " " * (gap - left)
        return text + " " * gap

    def line(cells: Sequence[str], cell_aligns: Sequence[str]) -> str:
        return "| " + " | ".join(pad(c, widths[i], cell_aligns[i]) for i, c in enumerate(cells)) + " |"

    separator = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out: list[str] = []
    if title:
        out.append(title)
    out += [separator, line(header_cells, ["c"] * ncols), separator]
    out += [line(r, aligns) for r in body]
    if not body:
        total = sum(widths) + 3 * (ncols - 1)
        out.append("| " + pad("(không có dữ liệu)", total, "l") + " |")
    out.append(separator)
    return "\n".join(out)


def format_key_values(pairs: Iterable[tuple[str, Any]], title: str | None = None) -> str:
    """Hiển thị dạng 'Nhãn : Giá trị' thẳng hàng (hồ sơ chi tiết)."""
    items = [(str(k), "" if v is None else str(v)) for k, v in pairs]
    width = max((text_width(k) for k, _ in items), default=0)
    lines = [title] if title else []
    lines += [f"  {k}{' ' * (width - text_width(k))} : {v}" for k, v in items]
    return "\n".join(lines)
