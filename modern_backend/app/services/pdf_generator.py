"""
Generate fillable and static PDF forms from charter data using reportlab.
Includes T4 tax forms, invoices, and fillable charter forms.
"""

import json
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, letter
from reportlab.lib.pagesizes import legal as LEGAL
from reportlab.lib.utils import simpleSplit
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Table,
    TableStyle,
)

from .pdf_layout_settings import load_pdf_layout_settings

SERVICE_FEE_LABEL = "Service Fee"
UTC_OFFSET_SUFFIX = "+00:00"


class CharterPDFForm:
    """Generate fillable PDF forms for charter bookings"""

    def __init__(self, charter_data):
        """
        Initialize with charter data

        Args:
            charter_data: dict with charter details
        """
        self.data = charter_data
        self.buffer = BytesIO()
        self.width, self.height = LETTER
        self.left_margin = 0.5 * inch
        self.right_margin = 0.5 * inch
        self.top_margin = 0.5 * inch
        self.bottom_margin = 0.5 * inch
        self.layout = load_pdf_layout_settings()

    def generate(self):
        """Generate the reservation run sheet and return bytes."""
        pdf = canvas.Canvas(self.buffer, pagesize=LETTER)
        pdf.setTitle(
            "Charter Sheet - {}".format(self.data.get("reserve_number", "TBD"))
        )

        page_left = 0.35 * inch
        page_right = self.width - 0.35 * inch
        content_width = page_right - page_left
        y = self.height - 0.35 * inch

        y = self._draw_header(pdf, page_left, page_right, y)
        y = self._draw_summary_and_client(pdf, page_left, content_width, y)
        y = self._draw_routing_and_totals(pdf, page_left, content_width, y)
        y = self._draw_beverages_and_notes(pdf, page_left, content_width, y)
        y = self._draw_driver_and_vehicle(pdf, page_left, content_width, y)
        y = self._draw_policies_terms(pdf, page_left, content_width, y)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(
            page_left + 5,
            y - 2,
            "CLIENT SIGNATURE: _______________________________________________   "
            "DATE: ______________",
        )

        pdf.showPage()
        pdf.save()
        self.buffer.seek(0)
        return self.buffer.getvalue()

    def _draw_header(self, pdf, x_left, x_right, y_top):
        center_x = (x_left + x_right) / 2
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(
            center_x, y_top, "ARROW LIMOUSINE & SEDAN SERVICES LTD."
        )
        return y_top - 10

    def _draw_summary_and_client(self, pdf, x_left, width, y_top):
        summary_cfg = self.layout.get("summary_client", {})
        left_width = float(summary_cfg.get("left_width_in", 4.05)) * inch
        gap = float(summary_cfg.get("gap_in", 0.12)) * inch
        right_width = width - left_width - gap

        reserve_id = self._safe(self.data.get("reserve_number"))
        heading_date = self._format_heading_date(self.data.get("charter_date"))
        reservation_title = f"Reservation  #{reserve_id}   {heading_date}"

        pickup_time = self._format_time(
            self.data.get("pickup_time") or self.data.get("actual_pickup_time")
        )
        dropoff_time = self._format_time(
            self.data.get("dropoff_time")
            or self.data.get("actual_dropoff_time")
        )
        status_text = self._safe(
            self.data.get("status") or self.data.get("reconciliation_status")
        )
        vehicle_type_text = self._safe(
            self.data.get("vehicle_type_requested")
            or self.data.get("vehicle_description")
            or self.data.get("vehicle")
        )
        vehicle_id_text = self._safe(
            self.data.get("vehicle_number")
            or self.data.get("vehicle_booked_id")
        )
        driver_text = self._safe(
            self.data.get("driver_name") or self.data.get("driver")
        )

        summary_lines = [
            [
                f"Run Type:"
                f"{self._friendly_run_type(self.data.get('charter_type'))}",
                f"Pickup: {pickup_time}",
                f"DO Time: {dropoff_time}",
            ],
            [
                f"Status: {status_text}",
                f"Est Hours:"
                f"{self._format_decimal(self.data.get('quoted_hours'))}",
                f"Pax: {self._safe(self.data.get('passenger_load'))}",
            ],
            [
                f"Vehicle Type:{vehicle_type_text}",
                f"Vehicle ID: {vehicle_id_text}",
                "",
            ],
            [
                f"Driver: {driver_text}",
                "",
                "",
            ],
        ]

        client_name = self._safe(self.data.get("client_name"))
        client_detail_lines = [
            f"Address: {self._safe(self.data.get('address_line1'))}",
            (
                f"City: {self._safe(self.data.get('city'))}, "
                f"{self._safe(self.data.get('province'))}  "
                f"Zip Code: {self._safe(self.data.get('zip_code'))}"
            ),
            f"Phone: {self._safe(self.data.get('phone'))}",
            "Alternate Phone: ____________________",
            f"Email: {self._safe(self.data.get('email'))}",
        ]

        summary_font_size = float(summary_cfg.get("summary_font_size", 7.8))
        summary_height = self._estimate_box_height(
            summary_lines, summary_font_size
        )
        # client: bold name (13pt) + 5 detail lines at 10.4pt + 23pt header =
        # ~92pt
        client_height = 23 + 13 + len(client_detail_lines) * 10.4 + 4
        box_height = max(summary_height, client_height)
        box_height = max(
            box_height, float(summary_cfg.get("client_min_height", 90))
        )

        self._draw_box(
            pdf,
            x_left,
            y_top - box_height,
            left_width,
            box_height,
            reservation_title,
        )
        self._draw_box(
            pdf,
            x_left + left_width + gap,
            y_top - box_height,
            right_width,
            box_height,
            "Client",
        )
        self._draw_text_grid(
            pdf,
            x_left + 6,
            y_top - 23,
            left_width - 12,
            summary_lines,
            summary_font_size,
        )

        # Draw client name bold and larger
        client_x = x_left + left_width + gap + 6
        client_content_width = right_width - 12
        pdf.setFont(
            "Helvetica-Bold",
            float(summary_cfg.get("client_name_font_size", 9.5)),
        )
        pdf.drawString(client_x, y_top - 23, client_name)
        # Draw remaining client detail lines
        self._draw_wrapped_lines(
            pdf,
            client_x,
            y_top - 36,
            client_content_width,
            client_detail_lines,
            7.8,
            line_height=10.4,
        )
        return y_top - box_height - 8

    def _draw_routing_and_totals(self, pdf, x_left, width, y_top):
        routing_cfg = self.layout.get("routing", {})
        invoicing_cfg = self.layout.get("invoicing", {})
        left_width = float(routing_cfg.get("left_width_in", 4.55)) * inch
        gap = float(routing_cfg.get("gap_in", 0.12)) * inch
        right_width = width - left_width - gap

        route_rows = [["#", "Event", "Time", "Details"]]
        routes = self.data.get("routes") or []
        if routes:
            for route in routes:
                route_rows.append(
                    [
                        str(route.get("route_sequence") or ""),
                        self._friendly_route_label(
                            route.get("event_type_code")
                        ),
                        self._format_time(route.get("stop_time")),
                        self._safe(route.get("address")),
                    ]
                )
        else:
            route_rows.extend(
                [
                    [
                        "1",
                        "Leave",
                        self._format_time(self.data.get("pickup_time")),
                        self._safe(self.data.get("pickup_address")),
                    ],
                    [
                        "2",
                        "Drop",
                        self._format_time(self.data.get("dropoff_time")),
                        self._safe(self.data.get("dropoff_address")),
                    ],
                ]
            )

        charges = self._normalize_charges()
        charge_rows = [["CHARGES", "RATE", "AMOUNT"]]
        for charge in charges:
            amount = float(charge.get("amount") or 0)
            charge_rows.append(
                [
                    self._safe(charge.get("label")),
                    f"{amount:.2f}",
                    f"{amount:.2f}",
                ]
            )

        total_due = float(self.data.get("total_amount_due") or 0)
        total_paid = float(self.data.get("total_paid") or 0)
        deposit = float(self.data.get("nrr_amount") or 0)
        balance = total_due - total_paid
        chauffeur_cash_collected = self._safe(
            self.data.get("chauffeur_cash_collected")
            or self.data.get("driver_cash_collected")
        )
        summary_rows = [
            ["Total Charges:", "", f"${total_due:.2f}"],
            ["Deposit:", "", f"${deposit:.2f}"],
            ["Payments Made:", "", f"${total_paid:.2f}"],
            ["Amount Due:", "", f"${balance:.2f}"],
            ["Chauffeur Cash Collected:", "", chauffeur_cash_collected],
        ]

        # Calculate heights dynamically: header 15pt + each data row 15pt +
        # padding
        route_row_height = float(routing_cfg.get("row_height", 15))
        charge_row_height = float(invoicing_cfg.get("row_height", 15))
        route_height = 22 + len(route_rows) * route_row_height
        charge_table_rows = max(
            len(charge_rows), int(invoicing_cfg.get("min_charge_rows", 4))
        )
        charge_rows_display = charge_rows + [["", "", ""]] * (
            charge_table_rows - len(charge_rows)
        )
        charge_rows_display += [["", "", ""]] + summary_rows
        charge_height = 22 + len(charge_rows_display) * charge_row_height

        # Auto-size invoicing columns so first column can fit the longest
        # label.
        table_total_width = right_width - 8
        min_numeric_col = (
            float(invoicing_cfg.get("numeric_col_min_in", 0.68)) * inch
        )
        preferred_numeric_col = (
            float(invoicing_cfg.get("numeric_col_pref_in", 0.80)) * inch
        )
        longest_label_width = 0
        for i, row in enumerate(charge_rows_display):
            label = str(row[0] or "")
            if not label:
                continue
            font_name = "Helvetica-Bold" if i == 0 else "Helvetica"
            longest_label_width = max(
                longest_label_width,
                pdfmetrics.stringWidth(
                    label, font_name, float(invoicing_cfg.get("font_size", 7))
                ),
            )
        target_first_col = longest_label_width + float(
            invoicing_cfg.get("label_padding", 10)
        )
        remaining_width = table_total_width - target_first_col
        if remaining_width >= (2 * preferred_numeric_col):
            rate_col_width = preferred_numeric_col
            amount_col_width = preferred_numeric_col
        elif remaining_width >= (2 * min_numeric_col):
            rate_col_width = remaining_width / 2
            amount_col_width = remaining_width / 2
        else:
            rate_col_width = min_numeric_col
            amount_col_width = min_numeric_col
        first_col_width = table_total_width - rate_col_width - amount_col_width

        # Use a shared section height so routing/invoicing feel balanced.
        content_height = max(route_height, charge_height)

        # Expand routing display rows to fill available height with clean blanks.
        target_route_rows = max(
            len(route_rows),
            int(max(0, content_height - 22) / route_row_height),
        )
        route_rows_display = route_rows + [["", "", "", ""]] * (
            target_route_rows - len(route_rows)
        )

        self._draw_box(
            pdf,
            x_left,
            y_top - content_height,
            left_width,
            content_height,
            "Routing",
        )
        self._draw_table(
            pdf,
            x_left + 4,
            y_top - 22,
            [
                0.35 * inch,
                0.9 * inch,
                0.7 * inch,
                left_width - 0.35 * inch - 0.9 * inch - 0.7 * inch - 14,
            ],
            route_rows_display,
            row_height=route_row_height,
            font_size=float(routing_cfg.get("font_size", 6.8)),
            col_alignments=["CENTER", "RIGHT", "CENTER", "LEFT"],
            col_font_sizes=[
                None,
                None,
                float(routing_cfg.get("time_font_size", 7.8)),
                None,
            ],
            col_bold=[
                False,
                False,
                bool(routing_cfg.get("time_bold", True)),
                False,
            ],
        )

        self._draw_box(
            pdf,
            x_left + left_width + gap,
            y_top - content_height,
            right_width,
            content_height,
            "Invoicing",
        )
        self._draw_table(
            pdf,
            x_left + left_width + gap + 4,
            y_top - 22,
            [first_col_width, rate_col_width, amount_col_width],
            charge_rows_display,
            row_height=charge_row_height,
            font_size=float(invoicing_cfg.get("font_size", 7)),
            show_inner_grid=False,
            col_alignments=[
                str(invoicing_cfg.get("first_col_align", "RIGHT")).upper(),
                str(invoicing_cfg.get("second_col_align", "CENTER")).upper(),
                str(invoicing_cfg.get("third_col_align", "CENTER")).upper(),
            ],
            col_font_sizes=[None, None, None],
            col_bold=[False, False, False],
            center_header=bool(invoicing_cfg.get("center_header", True)),
        )

        return y_top - content_height - 8

    def _draw_driver_and_vehicle(self, pdf, x_left, width, y_top):  # noqa: C901
        driver_vehicle_cfg = self.layout.get("driver_vehicle", {})
        table_row_height = float(driver_vehicle_cfg.get("line_height", 26.0))
        detail_line_step = 18

        # ── Raw data ────────────────────────────────────────────────────────
        driver_name = self._safe(
            self.data.get("driver_name") or self.data.get("driver")
        )
        driver_license = self._safe(
            self.data.get("employee_number")
            or self.data.get("driver_license_number")
            or self.data.get("license_number")
        )
        
        # Full date format
        raw_charter_date = self.data.get("charter_date")
        if raw_charter_date:
            try:
                if isinstance(raw_charter_date, str):
                    dt = datetime.fromisoformat(raw_charter_date.split('T')[0])
                else:
                    dt = raw_charter_date
                charter_date_full = dt.strftime("%B %d, %Y")
            except Exception:
                charter_date_full = self._format_short_date(raw_charter_date) or "-"
        else:
            charter_date_full = "-"

        # Work shift start
        raw_ws_start = (
            self.data.get("workshift_start")
            or self.data.get("hos_start_time")
            or self.data.get("on_duty_started_at")
        )
        ws_start = self._format_time(raw_ws_start) if raw_ws_start else "________"

        is_second_trip = bool(self.data.get("is_second_trip"))
        if is_second_trip:
            raw_prior_ws = self.data.get("prior_trip_workshift_start")
            if raw_prior_ws:
                ws_start = self._format_time(raw_prior_ws) + " [Trip 1]"

        # Vehicle info
        vehicle_id = self._safe(self.data.get("vehicle_id") or self.data.get("vehicle") or "-")
        odo_start = self._safe(self.data.get("odometer_start"))
        odo_end = self._safe(self.data.get("odometer_end"))
        try:
            total_odo = round(float(odo_end or 0) - float(odo_start or 0), 1)
        except Exception:
            total_odo = "-"

        # ── Build routing-based duty status table ──────────────────────────
        routes = self.data.get("routes") or []
        is_over_10_pax = int(self.data.get("passenger_count") or 0) > 10

        # Get vehicle type for duty status label
        driving_label = "Driving a Bus" if is_over_10_pax else "On-Duty"

        # Build table rows: [Location, Time, Description, Duty Status, Comments]
        table_rows = [
            [
                "Location/Event",
                "Time",
                "Description",
                "Duty Status",
                "Comments",
            ],
            [
                "START WORKSHIFT",
                ws_start,
                "",
                "On-Duty",
                "",
            ],
        ]

        # Add routing entries
        for route in routes[:8]:
            event_type = self._friendly_route_label(route.get("event_type_code")) or ""
            raw_addr = route.get("address")
            address = self._safe(raw_addr) if raw_addr else ""
            if address == "-":
                address = ""
            time_val = self._format_time(route.get("stop_time")) or ""
            duty_status = driving_label if "driving" in event_type.lower() else "On-Duty"
            raw_notes = route.get("route_notes")
            notes = self._safe(raw_notes) if raw_notes else ""
            if notes == "-":
                notes = ""

            table_rows.append([event_type, time_val, address, duty_status, notes])

        # Add 4 blank rows for manual entry
        for _ in range(4):
            table_rows.append(["", "", "", "", ""])

        # Define column widths
        col_widths = [
            1.0 * inch,  # Location
            0.9 * inch,  # Time
            1.8 * inch,  # Description
            1.4 * inch,  # Duty Status
            1.4 * inch,  # Comments
        ]

        route_table = Table(table_rows, colWidths=col_widths)
        route_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.6),
                    ("LEADING", (0, 0), (-1, -1), 7.8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWHEIGHTS", (0, 0), (-1, -1), table_row_height),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        # Pre-compute heights so the CDDL box fits its actual content.
        _, route_table_height = route_table.wrapOn(pdf, 0, 0)

        day_headers, _ = self._build_hos_day_headers(include_today=False)
        hos_rows = [
            ["Status", *day_headers],
            ["Off-Duty", *( ["-"] * 14 )],
            ["On-Duty", *( ["-"] * 14 )],
            ["24h", *( ["-"] * 14 )],
        ]
        status_col_width = 0.58 * inch
        numeric_total_width = width - status_col_width - 8
        day_col_width = numeric_total_width / 14
        hos_col_widths = [status_col_width, *([day_col_width] * 14)]
        hos_styles = [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 5.2),
            ("LEADING", (0, 0), (-1, -1), 6.0),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]
        hos_table = Table(hos_rows, colWidths=hos_col_widths, rowHeights=[6.5] * 4)
        hos_table.setStyle(TableStyle(hos_styles))
        _, hos_table_height = hos_table.wrapOn(pdf, 0, 0)

        exemption_lines = [
            "I operate within 160 km of my home terminal and returned to the home terminal by end of work shift for a minimum of 8 consecutive hours off-duty.",
            "I did not exceed the 13-hour driving limit for a vehicle carrying more than 10 passengers, and I was released from work within 15 hours of shift start with at least 1 hour off-duty. All duty-status changes for this shift or previous shift are documented on this record. I am employed by a motor carrier that maintains a Record of Duty Status for each driver. This is a copy of last 14 days log.",
        ]
        wrapped_exemption_lines = []
        for line in exemption_lines:
            wrapped_exemption_lines.extend(
                simpleSplit(line, "Helvetica", 5.2, width - 10)
            )

        route_table_top_y = y_top - 46
        route_table_bottom_y = route_table_top_y - route_table_height
        totals_y = route_table_bottom_y - 10
        vehicle_row_1_y = totals_y - detail_line_step
        vehicle_row_2_y = vehicle_row_1_y - detail_line_step
        grid_top_y = vehicle_row_2_y - 6
        grid_bottom_y = grid_top_y - hos_table_height
        exemption_y = grid_bottom_y - 10
        exemption_text_y = exemption_y - 6
        exemption_bottom_y = exemption_text_y - (
            max(len(wrapped_exemption_lines) - 1, 0) * 6.2
        )
        box_height = y_top - (exemption_bottom_y - 4)

        # ─── Draw box sized to content ──────────────────────────────────────
        self._draw_box(
            pdf,
            x_left,
            y_top - box_height,
            width,
            box_height,
            "Commercial Driving Daily Log Exemption- Record of Duty Status",
        )

        # ─── Draw header section at top ──────────────────────────────────────
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(
            x_left + 5,
            y_top - 23,
            (
                f"Date: {charter_date_full} | Driver Name: "
                f"{driver_name} | Employee #: {driver_license} | Vehicle ID: {vehicle_id}"
            ),
        )
        pdf.setFont("Helvetica", 7.0)
        pdf.drawString(
            x_left + 5,
            y_top - 33,
            f"Home Terminal: 38014 C and E Trail, Red Deer County, AB T4E 1R9",
        )

        # Draw table
        route_table.drawOn(pdf, x_left + 4, route_table_bottom_y)

        # Totals line below grid (hours:minutes)
        pdf.setFont("Helvetica-Bold", 6.9)
        pdf.drawString(
            x_left + 5,
            totals_y,
            (
                f"TOTALS  Off-Duty: ___:____ hrs | On-Duty: ___:____ hrs | "
                f"Driving a Bus: ___:____ hrs"
            ),
        )

        # ─── Vehicle & Fuel Section — 2 columns ────────────────────────────
        half = width / 2 - 8
        pdf.setFont("Helvetica", 6.8)
        # Row 1 left: odometers
        pdf.drawString(
            x_left + 5,
            vehicle_row_1_y,
            (
                f"Start Odo: {(odo_start or '_______'):<9} "
                f"End Odo: {(odo_end or '_______'):<9} "
                f"Distance: {str(total_odo)} km"
            ),
        )
        # Row 1 right: fuel / float
        pdf.drawString(
            x_left + half + 10,
            vehicle_row_1_y,
            "Fuel Added: _______ L    Float: $_______ Reimb: [ ]",
        )
        # Row 2 left: driver signature
        pdf.drawString(
            x_left + 5,
            vehicle_row_2_y,
            "Driver Signature: _________________________________   Date: __________",
        )
        # Row 2 right: missing info notes
        pdf.drawString(
            x_left + half + 10,
            vehicle_row_2_y,
            "Missing info notes: _________________________________",
        )

        # ─── HOS 14-Day Grid (inline, no box) ───────────────────────────────
        hos_table.drawOn(pdf, x_left + 4, grid_bottom_y)

        # 160-KM Exemption statement — plain text below grid (tight spacing)
        pdf.setFont("Helvetica-Bold", 5.8)
        pdf.drawString(
            x_left + 5,
            exemption_y,
            "160-KM EXEMPTION — Statement to officer: I confirm all of the following apply to this shift:",
        )
        pdf.setFont("Helvetica", 5.2)
        self._draw_wrapped_lines(
            pdf,
            x_left + 5,
            exemption_text_y,
            width - 10,
            wrapped_exemption_lines,
            5.2,
            line_height=6.2,
        )

        return y_top - box_height - 4

    def _draw_exemption_statement(self, pdf, x_left, width, y_top):
        """Light banner with the 160-km officer statement, drawn above the HOS grid."""
        lines = [
            (
                "160-KM EXEMPTION \u2014 Statement to officer:"
                " I confirm all of the following apply to this shift:"
            ),
            (
                "I operate within 160 km of my home terminal and returned"
                " to the home terminal by end of work shift for a minimum"
                " of 8 consecutive hours off-duty."
            ),
            (
                "I did not exceed the 13-hour driving limit for a vehicle"
                " carrying more than 10 passengers, and I was released from"
                " work within 15 hours of shift start with at least 1 hour"
                " off-duty. All duty-status changes for this shift or"
                " previous shift are documented on this record."
                " I am employed by a motor carrier that maintains a Record"
                " of Duty Status for each driver."
                " This is a copy of last 14 days log."
            ),
        ]
        banner_height = 0.72 * inch
        pdf.setLineWidth(0.6)
        pdf.setFillColor(colors.HexColor("#F0F4F8"))
        pdf.rect(
            x_left, y_top - banner_height, width, banner_height, fill=1, stroke=1
        )
        pdf.setFillColor(colors.black)
        self._draw_wrapped_lines(
            pdf,
            x_left + 5,
            y_top - 7,
            width - 10,
            lines,
            6.3,
            line_height=8.1,
        )
        return y_top - banner_height - 4

    def _draw_hos_grid(self, pdf, x_left, width, y_top):
        box_height = 0.95 * inch
        self._draw_box(
            pdf,
            x_left,
            y_top - box_height,
            width,
            box_height,
            "Hours of Service (Last 14 Days)",
        )

        is_second_trip = bool(self.data.get("is_second_trip"))
        day_headers, today_col = self._build_hos_day_headers(is_second_trip)

        # For second trip: pull prior trip's on-duty hours into today's column
        today_off = "-"
        today_on = "-"
        if is_second_trip:
            raw_hrs = (
                self.data.get("prior_trip_actual_hours")
                or self.data.get("actual_hours")
            )
            try:
                hrs = round(float(raw_hrs or 0), 1)
                if hrs > 0:
                    today_on = str(hrs)
                    today_off = str(round(24 - hrs, 1))
            except Exception:
                pass

        off_vals = ["-"] * 13 + [today_off]
        on_vals = ["-"] * 13 + [today_on]
        tot_vals = ["-"] * 14

        rows = [
            ["Status", *day_headers, "Total"],
            ["Off-Duty", *off_vals, "—"],
            ["On-Duty", *on_vals, "—"],
            ["Total (24hr)", *tot_vals, "—"],
        ]

        status_col_width = 0.95 * inch
        numeric_total_width = width - status_col_width - 8
        day_col_width = numeric_total_width / 15
        col_widths = [status_col_width, *([day_col_width] * 15)]

        styles = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 5.8),
            ("LEADING", (0, 0), (-1, -1), 6.4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f5f5f5")),
            ("BACKGROUND", (1, 1), (14, 1), colors.HexColor("#E6F3FF")),
            ("BACKGROUND", (1, 2), (14, 2), colors.HexColor("#FFFFCC")),
            ("BACKGROUND", (1, 3), (14, 3), colors.HexColor("#D3D3D3")),
            ("BACKGROUND", (15, 1), (15, 2), colors.HexColor("#FFE6CC")),
            ("BACKGROUND", (15, 3), (15, 3), colors.HexColor("#C0C0C0")),
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            # Reduced padding
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]
        # Highlight today's column green when it's a second trip
        if is_second_trip and today_col is not None:
            styles.append(
                (
                    "BACKGROUND",
                    (today_col, 1),
                    (today_col, 3),
                    colors.HexColor("#D4EDDA"),
                )
            )
            styles.append(
                ("FONTNAME", (today_col, 0), (today_col, 0), "Helvetica-Bold")
            )

        table = Table(rows, colWidths=col_widths, rowHeights=[10, 10, 10, 10])
        table.setStyle(TableStyle(styles))

        _, table_height = table.wrapOn(pdf, 0, 0)
        table.drawOn(pdf, x_left + 4, y_top - 19 - table_height)

        return y_top - box_height - 4

    def _build_hos_day_headers(self, include_today: bool = False):
        """Return (list_of_14_day_labels, today_col_index_or_None).

        The window always ends on yesterday (col 13, 0-indexed from day cols).
        When include_today is True the 14th day col shows today with a '*'
        suffix and today_col is set to its 1-based table column index.
        """
        from datetime import date as _date, timedelta as _td

        charter_date = self.data.get("charter_date")
        try:
            if isinstance(charter_date, str):
                base = datetime.fromisoformat(
                    charter_date.replace("Z", UTC_OFFSET_SUFFIX)
                ).date()
            elif hasattr(charter_date, "date"):
                base = charter_date.date()
            elif isinstance(charter_date, _date):
                base = charter_date
            else:
                base = datetime.now().date()
        except Exception:
            base = datetime.now().date()

        yesterday = base - _td(days=1)
        # Cols 1-14: days [yesterday-13 .. yesterday-1], col 14: yesterday (14 days total)
        headers = [
            str((yesterday - _td(days=i)).day) for i in range(13, 0, -1)
        ]
        headers.append(str(yesterday.day))  # col 14 = yesterday

        today_col = None
        if include_today:
            headers.append(str(base.day) + "*")  # col 15 = today
            today_col = 14  # table col index (col 0 = status label)

        return headers, today_col

    def _draw_beverages_and_notes(self, pdf, x_left, width, y_top):
        left_width = (width - (0.12 * inch)) / 2
        gap = 0.12 * inch
        right_width = width - left_width - gap
        row_height = 1.0 * inch

        # Draw boxes WITHOUT titles
        pdf.setStrokeColor(colors.black)
        pdf.setLineWidth(0.5)
        pdf.rect(x_left, y_top - row_height, left_width, row_height)
        pdf.rect(x_left + left_width + gap, y_top - row_height, right_width, row_height)

        # Notes (left content only, no title)
        notes_text = " ".join(
            part
            for part in [
                self._safe(self.data.get("notes")),
                self._safe(self.data.get("booking_notes")),
                self._safe(self.data.get("special_requirements")),
            ]
            if part and part != "-"
        )
        notes_lines = [notes_text] if notes_text else ["", "", "", "", ""]
        pdf.setFont("Helvetica", 6.8)
        self._draw_wrapped_lines(
            pdf,
            x_left + 3,
            y_top - 10,
            left_width - 6,
            notes_lines,
            6.8,
            line_height=9,
        )

        # Beverages (right content only, no title)
        beverages = self.data.get("beverages") or []
        beverage_lines = []
        for beverage in beverages[:24]:
            beverage_lines.append(
                f"{self._safe(beverage.get('quantity'))} "
                f"{self._safe(beverage.get('item_name'))}"
            )
        generic_items = [
            "12 Bud Light",
            "24 Kokanee",
            "12 Coors Light",
            "12 Corona",
            "12 Coors Banquet",
            "12 Heineken",
            "12 Michelob Ultra",
            "12 Budweiser",
            "Soft Drinks / Water",
            "Juice / Mix",
            "Other: ________________",
            "Other: ________________",
            "Other: ________________",
            "Other: ________________",
            "Other: ________________",
        ]
        while len(beverage_lines) < 15:
            beverage_lines.append(generic_items[len(beverage_lines)])

        # Split into 3 columns of 5 rows each
        col_count = 3
        rows_per_col = 5
        bev_x = x_left + left_width + gap + 3
        bev_col_width = (right_width - 6) / col_count
        bev_y_start = y_top - 10
        bev_line_height = 8.5
        pdf.setFont("Helvetica", 6.8)
        for i, line in enumerate(beverage_lines[:col_count * rows_per_col]):
            col = i // rows_per_col
            row = i % rows_per_col
            tx = bev_x + col * bev_col_width
            ty = bev_y_start - row * bev_line_height
            pdf.drawString(tx, ty, str(line))
        return y_top - row_height - 4

    def _draw_policies_terms(self, pdf, x_left, width, y_top):
        font_size = 5.5
        line_height = 6.6
        inner_pad = 6
        header_gap = 6
        footer_gap = 4

        policy_paragraphs = [
            "By placing a reservation and securing it with a nonrefundable retainer you acknowledge and expressly agree to the following policies, terms and conditions and further expressly authorize Arrow Limousine to charge your credit card in full or part amounts relating to your reservation including but not limited to charging your credit card in full for the reservation should you be considered a no-show or extra time is required or damages or excessive mess.",
            "We accept Visa, or MasterCard. Cash or E-transfer can be arranged. All orders are charged in Canadian Dollars (CAD). We automatically add a standard but adjustable 18 percent gratuity, and GST. All beverage orders, parking fees, tolls, event entrance fees or other charter requirement are billed to your credit card/account unless alternate arrangements are made with the office and noted on the booking.",
            "A retainer is a fee paid in advance and used to hold goods or services and is nonrefundable (NRR). A set non-refundable retainer (NRR) is required to confirm and secure a charter run. As soon as your retainer clears, the vehicle is yours for that specific time and date and a confirmation run charter is sent to your email address. We immediately begin turning away business for any, and all inquiries that come in for that vehicle and date.",
            "Bookings for 5 or more hours require a NRR equal to half of the total run charter charges. Charges to your credit card will be processed immediately for your NRR. The remaining balance is due within 7 days of date of services date. In the event the charter goes longer than planned, additional hourly charges at the extra time rate will apply. Charges will be made within 2 business days for all services added or incurred during your run charter.",
            "Our company is based out of Red Deer, and as such any out-of-town run charters will be billed from the time the vehicle leaves Red Deer and again until it returns to Red Deer.",
            "The Party paying for the Reservation is responsible for all damages and/or cleaning charges incurred by the renter and/or Party of the Renter, including but not limited to some of these minimum rates: Vomit/Sickness/bodily fluids (minimum $250 Fee); Alcohol Spillage cleaning fee; Broken Glassware ($10/glass); Burns ($500 Replacement/Repair); Smoking ($100/violation); Upholstery Tears or damaging stereo/TV/Lights/vehicle ($500-1000); Opening a Car Door into another Vehicle or Stationary Object ($1500-2000); tampering/opening emergency exits ($850). Any and all charges incurred will be charged to the credit card provided within 2 days, unless alternate arrangements are made. AGLC rules apply.",
            "Arrow Limousine is not responsible for acts of God, acts of Mother Nature and/or circumstances beyond our control, including but not limited to traffic congestion, road closures, accidents, flight delays, weather delays, etc. Reimbursements or reconciliation will not be made for these conditions. We drive to the conditions. We will adapt our driving to account for changes in the environment; your safety is our Chauffeurs' primary concern.",
            "By agreeing to a discounted rate, you the Client waive any claims regarding vehicle age, cosmetic condition, climate control irregularities (heating/air conditioning), or non-essential amenities, as long as the service meets safety and regulatory requirements.",
        ]

        wrapped_lines = []
        for paragraph in policy_paragraphs:
            wrapped_lines.extend(
                simpleSplit(paragraph, "Helvetica", font_size, width - (inner_pad * 2))
            )
            wrapped_lines.append("")
        if wrapped_lines and wrapped_lines[-1] == "":
            wrapped_lines.pop()

        # Draw bold "POLICIES & TERMS" header line
        header_font_size = 6.5
        header_line_height = header_font_size + 3
        pdf.setFont("Helvetica-Bold", header_font_size)
        pdf.drawString(x_left + inner_pad, y_top - header_line_height, "POLICIES & TERMS")

        body_y = y_top - header_line_height - header_gap
        body_bottom_y = self._draw_wrapped_lines(
            pdf,
            x_left + inner_pad,
            body_y,
            width - (inner_pad * 2),
            wrapped_lines,
            font_size,
            line_height=line_height,
        )
        return body_bottom_y - footer_gap

    def _draw_signature_box(self, pdf, x_left, width, y_top):
        signature_height = 0.66 * inch
        self._draw_box(
            pdf,
            x_left,
            y_top - signature_height,
            width,
            signature_height,
            "Signature",
        )
        pdf.setFont("Helvetica", 7.6)
        signature_y = y_top - 37
        pdf.drawString(
            x_left + 8,
            signature_y,
            (
                "CLIENT SIGNATURE: "
                "_______________________________________________"
            ),
        )
        pdf.drawString(
            x_left + width - 170, signature_y, "DATE: __________________"
        )

    def _draw_box(
        self, pdf, x, y, width, height, title, right_header_text=None
    ):
        pdf.setLineWidth(0.8)
        pdf.rect(x, y, width, height)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(x + (width / 2), y + height - 9, title)
        if right_header_text:
            pdf.setFont("Helvetica", 7.2)
            pdf.drawRightString(
                x + width - 4, y + height - 9, right_header_text
            )
        pdf.line(x, y + height - 15, x + width, y + height - 15)

    def _draw_text_grid(self, pdf, x, y_top, width, rows, font_size):
        current_y = y_top
        for row in rows:
            if not row:
                continue
            if len(row) == 1:
                self._draw_wrapped_lines(
                    pdf, x, current_y, width, row, font_size
                )
                current_y -= 14
                continue
            if len(row) == 3:
                column_gap = 8
                column_width = (width - 2 * column_gap) / 3
                self._draw_wrapped_lines(
                    pdf, x, current_y, column_width, [row[0]], font_size
                )
                self._draw_wrapped_lines(
                    pdf,
                    x + column_width + column_gap,
                    current_y,
                    column_width,
                    [row[1]],
                    font_size,
                )
                self._draw_wrapped_lines(
                    pdf,
                    x + 2 * (column_width + column_gap),
                    current_y,
                    column_width,
                    [row[2]],
                    font_size,
                )
                current_y -= 15
                continue
            column_gap = 10
            column_width = (width - column_gap) / 2
            self._draw_wrapped_lines(
                pdf, x, current_y, column_width, [row[0]], font_size
            )
            self._draw_wrapped_lines(
                pdf,
                x + column_width + column_gap,
                current_y,
                column_width,
                [row[1]],
                font_size,
            )
            current_y -= 15

    def _draw_wrapped_lines(
        self, pdf, x, y_top, width, lines, font_size, line_height=None
    ):
        pdf.setFont("Helvetica", font_size)
        current_y = y_top
        effective_line_height = line_height or (font_size + 3)
        for line in lines:
            wrapped = simpleSplit(str(line), "Helvetica", font_size, width)
            for subline in wrapped[:3]:
                pdf.drawString(x, current_y, subline)
                current_y -= effective_line_height
        return current_y

    def _draw_table(
        self,
        pdf,
        x,
        y_top,
        col_widths,
        rows,
        row_height,
        font_size,
        show_inner_grid=True,
        col_alignments=None,
        col_font_sizes=None,
        col_bold=None,
        center_header=False,
    ):
        table = Table(
            rows, colWidths=col_widths, rowHeights=[row_height] * len(rows)
        )
        style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("LEADING", (0, 0), (-1, -1), font_size + 1),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ededed")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]

        # Center header row if requested
        if center_header:
            style.append(("ALIGN", (0, 0), (-1, 0), "CENTER"))

        # Apply per-column alignments if specified (data rows only, not header)
        if col_alignments:
            for col_idx, alignment in enumerate(col_alignments):
                style.append(("ALIGN", (col_idx, 1), (col_idx, -1), alignment))

        # Apply per-column font sizes if specified
        if col_font_sizes:
            for col_idx, size in enumerate(col_font_sizes):
                if size:
                    style.append(
                        ("FONTSIZE", (col_idx, 1), (col_idx, -1), size)
                    )

        # Apply per-column bold if specified
        if col_bold:
            for col_idx, is_bold in enumerate(col_bold):
                if is_bold:
                    style.append(
                        (
                            "FONTNAME",
                            (col_idx, 1),
                            (col_idx, -1),
                            "Helvetica-Bold",
                        )
                    )

        if show_inner_grid:
            style.append(("GRID", (0, 0), (-1, -1), 0.4, colors.black))
        else:
            style.extend(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.black),
                ]
            )

        table.setStyle(TableStyle(style))
        _, table_height = table.wrapOn(pdf, 0, 0)
        table.drawOn(pdf, x, y_top - table_height)

    def _estimate_box_height(self, rows, font_size):
        height = 18
        for row in rows:
            row_h = 0
            for cell in row:
                width = 180 if len(row) > 1 else 260
                wrapped = simpleSplit(str(cell), "Helvetica", font_size, width)
                row_h = max(row_h, max(1, len(wrapped)) * (font_size + 2))
            height += row_h + 1
        return max(height, 60)

    def _format_heading_date(self, value):
        if not value:
            return ""
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(
                    value.replace("Z", UTC_OFFSET_SUFFIX)
                )
            else:
                dt = value
            month_map = {
                1: "Jan",
                2: "Feb",
                3: "Mar",
                4: "Apr",
                5: "May",
                6: "Jun",
                7: "Jul",
                8: "Aug",
                9: "Sept",
                10: "Oct",
                11: "Nov",
                12: "Dec",
            }
            month_name = month_map.get(dt.month, dt.strftime("%b"))
            return f"{dt.strftime('%A')} {month_name}-{dt.strftime('%d-%Y')}"
        except Exception:
            return str(value)

    def _normalize_charges(self):
        normalized = []
        label_map = {
            "base_rate": SERVICE_FEE_LABEL,
            "service_fee": SERVICE_FEE_LABEL,
            "gratuity": "Gratuity",
            "gst": "G.S.T.",
            "airport_fee": "Airport Fee",
            "additional": "Additional",
        }
        for charge in self.data.get("charges") or []:
            label = (
                charge.get("description")
                or label_map.get(charge.get("charge_type"))
                or "Charge"
            )
            normalized.append(
                {"label": label, "amount": charge.get("amount") or 0}
            )
        if not normalized:
            total_due = float(self.data.get("total_amount_due") or 0)
            normalized.append(
                {"label": SERVICE_FEE_LABEL, "amount": total_due}
            )
        return normalized

    def _format_datetime_line(self):
        charter_date = self.data.get("charter_date")
        pickup_time = self.data.get("pickup_time") or self.data.get(
            "actual_pickup_time"
        )
        date_part = self._format_date(charter_date)
        time_part = self._format_time(pickup_time)
        if date_part == "Not specified":
            return f"Pickup: {time_part}"
        return f"{date_part} {time_part}".strip()

    def _format_short_date(self, value):
        if not value:
            return ""
        try:
            if isinstance(value, str):
                value = datetime.fromisoformat(
                    value.replace("Z", UTC_OFFSET_SUFFIX)
                )
            return value.strftime("%m/%d")
        except Exception:
            return str(value)[:5]

    def _format_time(self, value):
        if not value:
            return ""
        try:
            if isinstance(value, str):
                clean_value = value.replace("Z", "+00:00")
                if "T" in clean_value:
                    value = datetime.fromisoformat(clean_value)
                else:
                    return clean_value[:5]
            return value.strftime("%H:%M")
        except Exception:
            return str(value)[:5]

    def _format_decimal(self, value):
        try:
            return f"{float(value or 0):.2f}"
        except Exception:
            return "0.00"

    def _safe(self, value):
        if value is None or value == "":
            return "-"
        return str(value)

    def _friendly_run_type(self, value):
        mapping = {
            "standard": "Charter",
            "airport": "Airport",
            "airport_pu": "Airport PU",
            "airport dropoff": "Airport DO",
            "exchange_of_services": "Exchange",
        }
        key = (
            str(value or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        return mapping.get(key, self._safe(value))

    def _friendly_route_label(self, value):
        mapping = {
            "pickup": "PU",
            "dropoff": "DO",
            "airport_pu": "Airport PU",
            "airport_do": "Airport DO",
            "leave_red_deer": "Leave",
            "return_red_deer": "Return",
            "stop": "Stop",
        }
        key = str(value or "").strip().lower()
        if key in mapping:
            return mapping[key]
        if not key:
            return "Stop"
        return key.replace("_", " ").title()

    def _format_date(self, date_str):
        """Format date string for display"""
        if not date_str:
            return "Not specified"
        try:
            if isinstance(date_str, str):
                date_obj = datetime.fromisoformat(
                    date_str.replace("Z", UTC_OFFSET_SUFFIX)
                )
            else:
                date_obj = date_str
            return date_obj.strftime("%m/%d/%Y %A")
        except Exception:
            return str(date_str)

    def _format_charter_type(self, charter_type):
        """Format charter type for display"""
        type_map = {
            "standard": "Standard Charter",
            "exchange_of_services": "Exchange of Services",
            "promotional": "Promotional",
            "internal": "Internal",
        }
        return type_map.get(charter_type, charter_type or "Standard")


class T4PDFForm:
    """Generate CRA T4 Statement of Remuneration Paid"""

    def __init__(
        self,
        employee_data: dict[str, Any],
        t4_data: dict[str, Any],
        tax_year: int = 2025,
    ):
        """
        Initialize with employee and T4 data

        Args:
            employee_data: Employee info (name, SIN, address, etc.)
            t4_data: T4 box values (box 14, 16, 18, 22, etc.)
            tax_year: Tax year for the T4
        """
        self.employee = employee_data
        self.t4 = t4_data
        self.tax_year = tax_year
        self.buffer = BytesIO()

    def generate(self):
        """Generate the T4 PDF and return bytes"""
        c = canvas.Canvas(self.buffer, pagesize=LETTER)
        width, height = LETTER

        # T4 Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(
            0.5 * inch, height - 0.5 * inch, "Statement of Remuneration Paid"
        )
        c.drawString(0.5 * inch, height - 0.75 * inch, f"T4 - {self.tax_year}")

        # Employer information
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.5 * inch, height - 1.25 * inch, "EMPLOYER INFORMATION")

        c.setFont("Helvetica", 10)
        y_pos = height - 1.5 * inch
        c.drawString(
            0.75 * inch, y_pos, "Arrow Limousine & Sedan Services LTD"
        )
        y_pos -= 0.2 * inch
        c.drawString(0.75 * inch, y_pos, "Business Number: [BN from CRA]")
        y_pos -= 0.2 * inch
        c.drawString(0.75 * inch, y_pos, "[Address]")
        y_pos -= 0.2 * inch
        c.drawString(0.75 * inch, y_pos, "[City, Province, Postal Code]")

        # Employee information
        y_pos -= 0.4 * inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.5 * inch, y_pos, "EMPLOYEE INFORMATION")

        c.setFont("Helvetica", 10)
        y_pos -= 0.25 * inch
        c.drawString(
            0.75 * inch,
            y_pos,
            f"Name: {self.employee.get('full_name', 'N/A')}",
        )
        y_pos -= 0.2 * inch
        c.drawString(
            0.75 * inch,
            y_pos,
            f"SIN: {self.employee.get('sin', 'XXX XXX XXX')}",
        )
        y_pos -= 0.2 * inch
        c.drawString(
            0.75 * inch,
            y_pos,
            f"Address: {self.employee.get('address', 'N/A')}",
        )
        y_pos -= 0.2 * inch
        c.drawString(
            0.75 * inch,
            y_pos,
            (
                f"{self.employee.get('city', '')}, "
                f"{self.employee.get('province', '')} "
                f"{self.employee.get('postal_code', '')}"
            ),
        )

        # T4 Boxes
        y_pos -= 0.5 * inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.5 * inch, y_pos, "T4 BOXES - AMOUNTS")

        c.setFont("Helvetica", 10)
        y_pos -= 0.3 * inch

        # Create table for T4 boxes
        boxes = [
            [
                "Box 14",
                "Employment Income",
                f"${self.t4.get('box14', 0.00):.2f}",
            ],
            [
                "Box 16",
                "Employee's CPP Contributions",
                f"${self.t4.get('box16', 0.00):.2f}",
            ],
            [
                "Box 18",
                "Employee's EI Premiums",
                f"${self.t4.get('box18', 0.00):.2f}",
            ],
            [
                "Box 22",
                "Income Tax Deducted",
                f"${self.t4.get('box22', 0.00):.2f}",
            ],
            [
                "Box 24",
                "EI Insurable Earnings",
                f"${self.t4.get('box24', 0.00):.2f}",
            ],
            [
                "Box 26",
                "CPP/QPP Pensionable Earnings",
                f"${self.t4.get('box26', 0.00):.2f}",
            ],
        ]

        # Draw boxes as table
        col_widths = [0.75 * inch, 2.5 * inch, 1.5 * inch]
        row_height = 0.25 * inch

        for i, box_row in enumerate(boxes):
            x_pos = 0.75 * inch
            box_y = y_pos - (i * row_height)

            # Draw box number
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x_pos, box_y, box_row[0])

            # Draw description
            c.setFont("Helvetica", 10)
            c.drawString(x_pos + col_widths[0], box_y, box_row[1])

            # Draw amount
            c.setFont("Helvetica-Bold", 10)
            c.drawRightString(
                x_pos + col_widths[0] + col_widths[1] + col_widths[2],
                box_y,
                box_row[2],
            )

            # Draw separator line
            if i < len(boxes) - 1:
                c.setStrokeColor(colors.lightgrey)
                c.line(
                    0.75 * inch,
                    box_y - 0.05 * inch,
                    5.5 * inch,
                    box_y - 0.05 * inch,
                )

        y_pos -= len(boxes) * row_height + 0.3 * inch

        # Additional boxes if needed
        if self.t4.get("box44", 0) > 0:
            c.setFont("Helvetica", 10)
            c.drawString(
                0.75 * inch,
                y_pos,
                f"Box 44 - Commissions: ${self.t4.get('box44', 0.00):.2f}",
            )
            y_pos -= 0.2 * inch

        if self.t4.get("box52", 0) > 0:
            c.drawString(
                0.75 * inch,
                y_pos,
                f"Box 52 - Union Dues: ${self.t4.get('box52', 0.00):.2f}",
            )
            y_pos -= 0.2 * inch

        # Footer
        y_pos -= 0.5 * inch
        c.setFont("Helvetica", 8)
        c.drawString(0.5 * inch, y_pos, f"Tax Year: {self.tax_year}")
        c.drawString(
            0.5 * inch,
            y_pos - 0.15 * inch,
            "Keep this slip for your income tax records",
        )
        c.drawString(
            0.5 * inch,
            y_pos - 0.3 * inch,
            "Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # CRA copy marker
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(
            width - 0.5 * inch, height - 0.5 * inch, "EMPLOYEE COPY"
        )

        c.save()
        self.buffer.seek(0)
        return self.buffer.getvalue()


def generate_charter_pdf(charter_data):
    """
    Generate a charter PDF form (invoice style)

    Args:
        charter_data: dict with charter details

    Returns:
        bytes: PDF file content
    """
    form = CharterPDFForm(charter_data)
    return form.generate()


def generate_t4_pdf(
    employee_data: dict[str, Any],
    t4_data: dict[str, Any],
    tax_year: int = 2025,
):
    """
    Generate a T4 tax form PDF

    Args:
        employee_data: dict with employee details (name, SIN, address, etc.)
        t4_data: dict with T4 box values (box14, box16, box18, box22, etc.)
        tax_year: tax year for the T4

    Returns:
        bytes: PDF file content
    """
    form = T4PDFForm(employee_data, t4_data, tax_year)
    return form.generate()
