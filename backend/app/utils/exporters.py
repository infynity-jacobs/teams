import io
from typing import List, Sequence, Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, portrait, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm


def build_xlsx(headers: Sequence[str], rows: Sequence[Sequence[Any]], title: str = "Report") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31] if title else "Report"

    ws.append(list(headers))
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill

    for row in rows:
        ws.append(list(row))

    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(length + 2, 10), 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _pdf_page_layout(headers: Sequence[str], rows: Sequence[Sequence[Any]]):
    """Choose a readable A4 orientation from report width and size.

    Wide reports use landscape; compact reports use portrait. Very long
    reports also use landscape to give the table more horizontal room while
    keeping normal multi-page vertical pagination.
    """
    column_count = len(headers)
    row_count = len(rows)
    orientation = landscape if column_count >= 7 or row_count >= 25 else portrait
    page_size = orientation(A4)
    return page_size, orientation is landscape


def build_pdf(headers: Sequence[str], rows: Sequence[Sequence[Any]], title: str = "Report",
              subtitle: str = "") -> bytes:
    buf = io.BytesIO()
    pagesize, is_landscape = _pdf_page_layout(headers, rows)
    margin = 1.2 * cm
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize,
        leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"])]
    if subtitle:
        elements.append(Paragraph(subtitle, styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    table_data = [list(headers)] + [[str(c) if c is not None else "" for c in row] for row in rows]

    # Give long text columns more room while keeping compact numeric columns.
    # ReportLab will paginate long tables vertically; orientation is selected
    # separately so reports remain readable rather than forcing every report
    # into landscape.
    available_width = pagesize[0] - (2 * margin)
    if headers:
        preferred = []
        for idx, header in enumerate(headers):
            values = [str(row[idx]) if idx < len(row) and row[idx] is not None else "" for row in rows[:100]]
            sample_len = max([len(str(header))] + [len(v) for v in values] or [1])
            if header.lower() in {"id", "qty", "leads", "converted", "new", "pending", "lost", "conversion %"}:
                weight = min(max(sample_len, 5), 12)
            elif header.lower() in {"email", "phone", "sku", "created", "converted"}:
                weight = min(max(sample_len, 8), 20)
            else:
                weight = min(max(sample_len, 10), 28)
            preferred.append(weight)
        total = sum(preferred) or 1
        col_widths = [available_width * w / total for w in preferred]
    else:
        col_widths = None

    table = Table(table_data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return buf.read()
