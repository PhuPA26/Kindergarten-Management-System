"""File exporters shared by the GUI and console."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from xml.sax.saxutils import escape

from ..exceptions import DataStoreError

if TYPE_CHECKING:
    from .reports import ReportData


class ReportExporter(Protocol):
    def write(self, data: ReportData, target: Path) -> None: ...


class ExcelExporter:
    def write(self, data: ReportData, target: Path) -> None:
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter

        book = Workbook()
        sheet = book.active
        sheet.title = "Báo cáo"
        for line in (data.title, data.subtitle, f"Ngày xuất: {data.generated_at:%d/%m/%Y %H:%M}"):
            if line:
                sheet.append([line])
        sheet.append(data.headers)
        header = sheet.max_row
        sheet.freeze_panes = f"A{header + 1}"
        for cell in sheet[header]:
            cell.font = Font(bold=True)
        for row in data.rows:
            sheet.append(row)
            for index, cell in enumerate(sheet[sheet.max_row]):
                if isinstance(cell.value, (int, float)) and data.column_format(index) == "money":
                    cell.number_format = "#,##0"
        sheet.auto_filter.ref = f"A{header}:{get_column_letter(len(data.headers))}{sheet.max_row}"
        for label, value in data.summary:
            sheet.append([label, value])
        for index, cells in enumerate(sheet.iter_cols(), 1):
            for cell in cells:
                if cell.data_type == "f":
                    cell.data_type = "s"
            width = max((len(str(cell.value or "")) for cell in cells if cell.row >= header), default=12)
            sheet.column_dimensions[get_column_letter(index)].width = min(50, max(12, width + 2))
        book.save(target)


class PdfExporter:
    @staticmethod
    def _font_path() -> Path:
        custom = os.environ.get("KINDERGARTEN_PDF_FONT")
        candidates = [
            Path(custom) if custom else None,
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        font = next((path for path in candidates if path and path.is_file()), None)
        if font is None:
            raise DataStoreError("Chưa tìm được font PDF hỗ trợ tiếng Việt. Hãy đặt KINDERGARTEN_PDF_FONT đến file TTF.")
        return font

    def write(self, data: ReportData, target: Path) -> None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

        from .reports import _display

        pdfmetrics.registerFont(TTFont("KindergartenReport", str(self._font_path())))
        body = ParagraphStyle("ReportBody", fontName="KindergartenReport", fontSize=8, leading=11, splitLongWords=True)
        title = ParagraphStyle("ReportTitle", parent=body, fontSize=15, leading=19)

        def paragraph(value: str, style: ParagraphStyle = body) -> Paragraph:
            return Paragraph(escape(value).replace("\n", "<br/>"), style)

        document = SimpleDocTemplate(str(target), pagesize=landscape(A4), leftMargin=28, rightMargin=28,
                                     title=data.title)
        content = [paragraph(data.title, title)]
        if data.subtitle:
            content.append(paragraph(data.subtitle))
        content.extend([paragraph(f"Ngày xuất: {data.generated_at:%d/%m/%Y %H:%M}"), Spacer(1, 10)])
        rows = [[paragraph(header) for header in data.headers]]
        rows.extend([paragraph(_display(value, data.column_format(index))) for index, value in enumerate(row)]
                    for row in data.rows)
        table = LongTable(rows, colWidths=[(document.width - 12) / len(data.headers)] * len(data.headers),
                          repeatRows=1, splitInRow=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8F7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        content.extend([table, Spacer(1, 10)])
        content.extend(paragraph(f"{label}: {value}") for label, value in data.summary)
        document.build(content)


FILE_EXPORTERS: dict[str, ReportExporter] = {"xlsx": ExcelExporter(), "pdf": PdfExporter()}
