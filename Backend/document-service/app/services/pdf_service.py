"""
PDF generation for timetables using ReportLab.
Produces official printable timetable documents with QR code verification.
"""
from __future__ import annotations
import io
import qrcode
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
HEADER_COLOR = colors.HexColor("#1E40AF")  # deep blue
ALT_ROW_COLOR = colors.HexColor("#EFF6FF")  # light blue
BREAK_COLOR = colors.HexColor("#FEF3C7")    # amber


def generate_timetable_pdf(timetable: dict, institution_name: str = "University") -> bytes:
    """
    Generate an A4 landscape PDF timetable.
    timetable: full dict from timetable-engine API (includes entries).
    Returns PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=HEADER_COLOR)
    story.append(Paragraph(institution_name, title_style))
    story.append(Paragraph(f"Academic Timetable — {timetable.get('name', '')}", title_style))
    story.append(Paragraph(
        f"Semester: {timetable.get('semester')} | Year: {timetable.get('academic_year')} | "
        f"Fitness Score: {timetable.get('fitness_score', 0):.2%}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    # Build grid: rows = time slots, cols = days
    entries = timetable.get("entries", [])
    slot_map: dict[tuple, list] = {}
    for entry in entries:
        slot = entry.get("time_slot", {})
        day = slot.get("day", "")
        time = f"{slot.get('start_time', '')}–{slot.get('end_time', '')}"
        key = (time, slot.get("slot_index", 0))
        slot_map.setdefault(key, {})
        slot_map[key][day] = entry

    # Unique time slots sorted
    time_keys = sorted(slot_map.keys(), key=lambda k: k[1])

    # Table header
    header = ["Time"] + DAYS
    table_data = [header]

    for (time_label, _), day_entries in zip(time_keys, [slot_map[k] for k in time_keys]):
        row = [time_label]
        for day in DAYS:
            entry = day_entries.get(day)
            if entry:
                course = entry.get("course", {})
                room = entry.get("room", {})
                lecturer = entry.get("lecturer", {})
                cell = f"{course.get('code', '')}\n{course.get('name', '')}\n{room.get('code', '')}\n{lecturer.get('name', '')}"
            else:
                cell = ""
            row.append(cell)
        table_data.append(row)

    # Create table
    col_widths = [3 * cm] + [5 * cm] * 5
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW_COLOR]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("WORDWRAP", (0, 0), (-1, -1), True),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # QR code for verification
    qr_data = f"https://shedulex.ac/verify/{timetable.get('id', '')}"
    qr_img = _generate_qr_image(qr_data)
    story.append(Paragraph("Scan to verify authenticity:", styles["Normal"]))
    story.append(qr_img)

    doc.build(story)
    return buffer.getvalue()


def _generate_qr_image(data: str) -> Image:
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return Image(buffer, width=3 * cm, height=3 * cm)
