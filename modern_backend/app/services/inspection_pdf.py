"""
Vehicle Pre-Trip Inspection fillable PDF generator using ReportLab.
Produces a blank, printable DVIR-style form for Arrow Limo drivers.
"""

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


# Checklist sections — each item: (label, indent_level)
CHECKLIST_SECTIONS = [
    ("EXTERIOR", [
        "Body damage / dents / scratches",
        "Doors latch & seal properly",
        "Windows & mirrors clean / uncracked",
        "Windshield wipers & washers",
        "Licence plates (front & rear) legible",
        "Fuel cap secured",
        "Mud flaps present",
    ]),
    ("LIGHTS", [
        "Headlights (low & high beam)",
        "Tail lights & brake lights",
        "Turn signals / hazard flashers",
        "Reverse lights",
        "Interior cabin lights",
        "Dash warning lights (none on at start)",
    ]),
    ("ENGINE & FLUIDS", [
        "Engine oil level",
        "Coolant level",
        "Brake fluid level",
        "Washer fluid level",
        "Power steering fluid level",
        "No visible leaks under vehicle",
        "Battery cables secure",
    ]),
    ("BRAKES & STEERING", [
        "Brake pedal firm (pump test)",
        "Parking / emergency brake holds",
        "Steering — no excessive play",
        "No brake warning light",
    ]),
    ("TIRES & WHEELS", [
        "Tire tread depth adequate",
        "Tire pressure correct (all 4 + spare)",
        "No cuts, bulges, or embedded objects",
        "Lug nuts tight / no missing",
    ]),
    ("INTERIOR", [
        "Horn operational",
        "Seat belts functional (all positions)",
        "Seats / carpet clean & undamaged",
        "HVAC / climate control functional",
        "GPS / dispatch device operational",
        "Divider window operational (if equipped)",
        "Odometer reading recorded",
    ]),
    ("SAFETY EQUIPMENT", [
        "First aid kit present & stocked",
        "Fire extinguisher charged & mounted",
        "Reflective triangles / flares present",
        "Vehicle registration & insurance in vehicle",
        "Driver licence & chauffeur permit present",
    ]),
]


def _checkbox(c: canvas.Canvas, x: float, y: float, size: float = 8.0):
    """Draw a small square checkbox."""
    c.rect(x, y, size, size, stroke=1, fill=0)


def _header(c: canvas.Canvas, width: float, y: float) -> float:
    """Draw the company header and form title. Returns updated y."""
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, "ARROW LIMOUSINE LTD.")
    y -= 16
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, "DRIVER VEHICLE INSPECTION REPORT — PRE-TRIP")
    y -= 10
    c.setLineWidth(1)
    c.line(0.4 * inch, y, width - 0.4 * inch, y)
    return y - 8


def _info_row(
    c: canvas.Canvas,
    x: float,
    y: float,
    fields: list,
    row_height: float = 20,
) -> float:
    """
    Draw a row of labelled underline fields.
    fields: list of (label, width_in_points)
    Returns updated y after drawing.
    """
    cx = x
    line_y = y - row_height + 4
    c.setFont("Helvetica", 8)
    for label, fw in fields:
        c.drawString(cx, y - 10, label)
        c.line(cx, line_y, cx + fw, line_y)
        cx += fw + 10
    return y - row_height - 4


def generate_pre_trip_pdf() -> bytes:
    """
    Generate a blank Vehicle Pre-Trip Inspection PDF.
    Returns raw PDF bytes.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    LEFT = 0.4 * inch
    RIGHT = width - 0.4 * inch
    COL_W = (RIGHT - LEFT)

    y = height - 0.45 * inch

    # ── Header ─────────────────────────────────────────────────────────────
    y = _header(c, width, y)

    # ── Info fields row 1 ──────────────────────────────────────────────────
    y = _info_row(c, LEFT, y, [
        ("Date:", 90),
        ("Departure Time:", 80),
        ("Return Time:", 80),
        ("Trip / Reserve #:", 90),
    ], row_height=22)

    # ── Info fields row 2 ──────────────────────────────────────────────────
    y = _info_row(c, LEFT, y, [
        ("Driver Name:", 140),
        ("Vehicle # / Unit:", 80),
        ("Licence Plate:", 80),
        ("Odometer (start):", 80),
    ], row_height=22)

    y -= 4
    c.setLineWidth(0.5)
    c.line(LEFT, y, RIGHT, y)
    y -= 8

    # ── Legend ─────────────────────────────────────────────────────────────
    lx = LEFT
    c.setFont("Helvetica-Bold", 8)
    c.drawString(lx, y, "LEGEND:")
    lx += 52
    box_size = 8
    for sym, lbl in [("P", "PASS"), ("F", "FAIL"), ("N", "N/A")]:
        _checkbox(c, lx, y - 1, box_size)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(lx + box_size / 2, y + 0.5, sym)
        c.setFont("Helvetica", 7)
        c.drawString(lx + box_size + 3, y, lbl)
        lx += 60
    c.setFont("Helvetica", 7)
    c.drawString(lx + 10, y, "Mark each item with P / F / N — circle defective items and describe below.")
    y -= 14

    # ── Checklist columns ──────────────────────────────────────────────────
    # Two-column layout
    COL_X = [LEFT, LEFT + COL_W / 2 + 4]
    col_y = [y, y]
    NUM_COLS = 2
    SECTION_H = 11   # section header row height
    ITEM_H = 11      # item row height
    CHECK_SIZE = 7
    CHECK_GAP = 9    # gap between P / F / N boxes

    for col in range(NUM_COLS):
        num_sections = (len(CHECKLIST_SECTIONS) + NUM_COLS - 1) // NUM_COLS
        start_sec = col * num_sections
        end_sec = min(start_sec + num_sections, len(CHECKLIST_SECTIONS))

        cx = COL_X[col]
        cy = col_y[col]
        col_width = COL_W / 2 - 4

        for sec_label, items in CHECKLIST_SECTIONS[start_sec:end_sec]:
            # Section header bar
            c.setFillColor(colors.HexColor("#D0D8E8"))
            c.rect(cx, cy - SECTION_H + 2, col_width, SECTION_H, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(cx + 3, cy - SECTION_H + 5, sec_label)

            # Column header P / F / N
            check_x_start = cx + col_width - (3 * CHECK_GAP + CHECK_SIZE + 6)
            c.setFont("Helvetica-Bold", 6)
            for i, lbl in enumerate(["P", "F", "N"]):
                c.drawCentredString(
                    check_x_start + i * CHECK_GAP + CHECK_SIZE / 2,
                    cy - SECTION_H + 5,
                    lbl,
                )

            cy -= SECTION_H + 1

            # Items
            for item in items:
                c.setFont("Helvetica", 7)
                # Truncate label if too long for column
                c.drawString(cx + 3, cy - ITEM_H + 3, item[:52])

                # P / F / N checkboxes
                for i in range(3):
                    bx = check_x_start + i * CHECK_GAP
                    by = cy - ITEM_H + 2
                    _checkbox(c, bx, by, CHECK_SIZE)

                cy -= ITEM_H

            cy -= 4  # spacing between sections

    # ── Defects / Notes section ────────────────────────────────────────────
        # Use a safe fixed y based on available page space.
    y = 2.6 * inch

    c.setLineWidth(0.5)
    c.line(LEFT, y, RIGHT, y)
    y -= 4

    c.setFont("Helvetica-Bold", 9)
    c.drawString(LEFT, y, "DEFECTS / NOTES  (describe all FAIL items — use vehicle # and section):")
    y -= 4

    # Three lined notes rows
    c.setLineWidth(0.5)
    c.setFont("Helvetica", 8)
    for _ in range(3):
        y -= 16
        c.line(LEFT, y, RIGHT, y)

    y -= 16
    c.setLineWidth(0.5)
    c.line(LEFT, y, RIGHT, y)

    # ── Certification ──────────────────────────────────────────────────────
    y -= 10
    c.setFont("Helvetica", 7)
    cert = (
        "I certify that I have inspected the above vehicle in accordance with applicable regulations "
        "and that it is in satisfactory condition for operation, except as noted above."
    )
    c.drawString(LEFT, y, cert)
    y -= 20

    # Signature row
    sig_fields = [
        ("Driver Signature:", 170),
        ("Print Name:", 130),
        ("Date / Time:", 100),
    ]
    lx = LEFT
    for label, fw in sig_fields:
        c.setFont("Helvetica", 8)
        c.drawString(lx, y, label)
        c.line(lx, y - 12, lx + fw, y - 12)
        lx += fw + 18

    y -= 28

    # Supervisor sign-off
    c.setFont("Helvetica-Bold", 8)
    c.drawString(LEFT, y, "DEFECTS CORRECTED (supervisor use):")
    y -= 4
    c.setFont("Helvetica", 8)
    corr_fields = [
        ("Corrective action taken:", 170),
        ("Supervisor Signature:", 130),
        ("Date:", 70),
    ]
    lx = LEFT
    for label, fw in corr_fields:
        c.drawString(lx, y, label)
        c.line(lx, y - 12, lx + fw, y - 12)
        lx += fw + 18

    y -= 28
    c.setLineWidth(0.3)
    c.line(LEFT, y, RIGHT, y)
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        width / 2,
        y - 9,
        "Arrow Limousine Ltd. — Vehicle Pre-Trip Inspection Form  |  "
        "Retain completed forms for minimum 12 months.",
    )

    c.save()
    return buf.getvalue()


def _sections_height(sections: list) -> float:
    """Estimate total height of checklist sections in points."""
    SECTION_H = 11
    ITEM_H = 11
    total = 0
    for _, items in sections:
        total += SECTION_H + 1 + len(items) * ITEM_H + 4
    return total
