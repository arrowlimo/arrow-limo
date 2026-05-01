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

        # Keep policies readable for route-heavy charters by moving them
        # to a fresh page when remaining space is too small.
        if y < 220:
            pdf.showPage()
            y = self.height - 0.45 * inch

        y = self._draw_policies_terms(pdf, page_left, content_width, y - 6)
        pdf.setFont("Helvetica", 8)
        signature_y = max(18, y - 10)
        pdf.drawString(
            page_left + 5,
            signature_y,
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
        pdf.setFont("Helvetica", 7.5)
        pdf.drawCentredString(
            center_x,
            y_top - 11,
            "3, 6841 52 Ave, Red Deer, Alberta T4N 4L2, (403) 346-0034,"
            " www.Arrowlimousine.ca, G.S.T.#: 861 556 827",
        )
        return y_top - 22

    def _draw_summary_and_client(self, pdf, x_left, width, y_top):
        summary_cfg = self.layout.get("summary_client", {})
        routing_cfg = self.layout.get("routing", {})
        notes_width = float(routing_cfg.get("notes_col_in", 3.70)) * inch
        left_width = width - notes_width
        gap = float(summary_cfg.get("gap_in", 0.0)) * inch
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
                f"Est Hours:"
                f"{self._format_decimal(self.data.get('quoted_hours'))}",
                f"Pax: {self._safe(self.data.get('passenger_load'))}",
                "",
            ],
            [
                f"Vehicle Type: {vehicle_type_text}   |   Vehicle ID: {vehicle_id_text}",
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
                f"{self._safe(self.data.get('province'))}"
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

        # Shared top frame: one outer box with a single divider, no separate Client label.
        box_y = y_top - box_height
        separator_y = box_y + box_height - 17
        divider_x = x_left + left_width
        pdf.setLineWidth(0.8)
        pdf.line(x_left, box_y, x_left, separator_y)
        pdf.line(x_left, box_y, x_left + width, box_y)
        pdf.line(x_left + width, box_y, x_left + width, separator_y)
        pdf.line(x_left, separator_y, x_left + width, separator_y)
        pdf.line(divider_x, box_y, divider_x, separator_y)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(x_left + 6, y_top - 11, reservation_title)
        self._draw_text_grid(
            pdf,
            x_left + 6,
            y_top - 29,
            left_width - 12,
            summary_lines,
            summary_font_size,
        )

        # Draw client name bold and larger
        client_x = divider_x + 6
        client_content_width = right_width - 12
        pdf.setFont(
            "Helvetica-Bold",
            float(summary_cfg.get("client_name_font_size", 9.5)),
        )
        pdf.drawString(client_x, y_top - 29, client_name)
        # Draw remaining client detail lines
        self._draw_wrapped_lines(
            pdf,
            client_x,
            y_top - 42,
            client_content_width,
            client_detail_lines,
            7.8,
            line_height=10.4,
        )
        return y_top - box_height

    def _draw_routing_and_totals(self, pdf, x_left, width, y_top):
        routing_cfg = self.layout.get("routing", {})
        route_rows = [["Event Type", "Details", "", "Time", "Notes"]]
        routes = self.data.get("routes") or []
        if routes:
            for route in routes:
                route_rows.append(
                    [
                        self._friendly_route_label(
                            route.get("event_type_code")
                        ),
                        self._safe(route.get("address")),
                        route.get("at_by") or "at",
                        self._format_time(route.get("stop_time")),
                        self._safe(route.get("route_notes")),
                    ]
                )
        else:
            route_rows.extend(
                [
                    [
                        "Leave",
                        self._safe(self.data.get("pickup_address")),
                        "at",
                        self._format_time(self.data.get("pickup_time")),
                        "",
                    ],
                    [
                        "Drop",
                        self._safe(self.data.get("dropoff_address")),
                        "at",
                        self._format_time(self.data.get("dropoff_time")),
                        "",
                    ],
                ]
            )

        # Calculate height for routing area.
        route_row_height = float(routing_cfg.get("row_height", 15))
        route_height = len(route_rows) * route_row_height
        min_top_rows = int(routing_cfg.get("min_rows", 9))
        content_height = max(route_height, min_top_rows * route_row_height)

        # Expand routing display rows to fill available height with clean blanks.
        target_route_rows = max(
            len(route_rows),
            int(max(0, content_height) / route_row_height),
        )
        route_rows_display = route_rows + [["", "", "", "", ""]] * (
            target_route_rows - len(route_rows)
        )

        # Column widths: Event Type, Details, At/By, Time, Notes — full page width
        _ev_w = float(routing_cfg.get("event_col_in", 1.18)) * inch
        _ab_w = float(routing_cfg.get("at_by_col_in", 0.28)) * inch
        _tm_w = float(routing_cfg.get("time_col_in", 0.50)) * inch
        _nt_w = float(routing_cfg.get("notes_col_in", 3.70)) * inch
        _dest_w = width - _ev_w - _ab_w - _tm_w - _nt_w
        self._draw_table(
            pdf,
            x_left,
            y_top,
            [_ev_w, _dest_w, _ab_w, _tm_w, _nt_w],
            route_rows_display,
            row_height=route_row_height,
            font_size=float(routing_cfg.get("font_size", 6.8)),
            col_alignments=["LEFT", "LEFT", "CENTER", "CENTER", "LEFT"],
            col_font_sizes=[
                None,
                float(routing_cfg.get("details_font_size", 6.8)),
                None,
                float(routing_cfg.get("time_font_size", 7.8)),
                float(routing_cfg.get("notes_font_size", 6.6)),
            ],
            col_bold=[False, False, False, bool(routing_cfg.get("time_bold", True)), False],
        )

        return y_top - content_height

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

        # ── Build duty status table (manual fill lines) ────────────────────

        # Build table rows: [Location/Event, Duty Status, Time, Comments]
        table_rows = [
            [
                "Location / Event",
                "Duty Status",
                "Time",
                "Comments",
            ],
            [
                "START WORKSHIFT",
                "On-Duty",
                ws_start,
                "",
            ],
        ]

        # Add 8 blank rows for manual entry
        for _ in range(8):
            table_rows.append(["", "", "", ""])

        # Define column widths (expand comments to use available width).
        table_inner_width = width - 8
        duty_col_width = 1.0 * inch
        time_col_width = 0.55 * inch
        comments_col_width = 2.3 * inch
        location_col_width = max(
            1.6 * inch,
            table_inner_width - duty_col_width - time_col_width - comments_col_width,
        )
        col_widths = [
            location_col_width,  # Location / Event
            duty_col_width,      # Duty Status
            time_col_width,      # Time
            comments_col_width,  # Comments
        ]

        route_table = Table(table_rows, colWidths=col_widths)
        route_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white),  # remove header underline
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
        hos_records = self.data.get("hos_records") or []
        off_vals = ["-"] * 14
        on_vals = ["-"] * 14
        total_vals = ["-"] * 14
        for idx, rec in enumerate(hos_records[:14]):
            off_vals[idx] = str(rec.get("off_duty") or "-")
            on_vals[idx] = str(rec.get("on_duty") or "-")
            total_vals[idx] = str(rec.get("total_24h") or "-")

        hos_rows = [
            ["Status", *day_headers],
            ["Off-Duty", *off_vals],
            ["On-Duty", *on_vals],
            ["24h", *total_vals],
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
        hos_table = Table(hos_rows, colWidths=hos_col_widths, rowHeights=[13.0] * 4)
        hos_table.setStyle(TableStyle(hos_styles))
        _, hos_table_height = hos_table.wrapOn(pdf, 0, 0)

        exemption_lines = [
            "I operate within 160 km of my home terminal and returned to the home terminal by end of work shift for a minimum of 8 consecutive hours off-duty.",
            "I did not exceed the 13-hour driving limit for a vehicle carrying more than 10 passengers, and I was released from work within 15 hours of shift start with at least 1 hour off-duty. All duty-status changes for this shift or previous shift are documented on this record. I am employed by a motor carrier that maintains a Record of Duty Status for each driver. This is a copy of last 14 days log.",
        ]
        wrapped_exemption_lines = []
        for line in exemption_lines:
            wrapped_exemption_lines.extend(
                simpleSplit(line, "Helvetica", 6.8, width - 10)
            )

        route_table_top_y = y_top - 46
        route_table_bottom_y = route_table_top_y - route_table_height
        totals_y = route_table_bottom_y - 10
        vehicle_row_1_y = totals_y - detail_line_step
        vehicle_row_2_y = vehicle_row_1_y - detail_line_step
        grid_top_y = vehicle_row_2_y - 10
        grid_bottom_y = grid_top_y - hos_table_height
        exemption_y = grid_bottom_y - 14
        exemption_text_y = exemption_y - 8
        exemption_bottom_y = exemption_text_y - (
            max(len(wrapped_exemption_lines) - 1, 0) * 8.0
        )
        box_height = y_top - (exemption_bottom_y - 12)

        # ─── Draw box sized to content ──────────────────────────────────────
        self._draw_box(
            pdf,
            x_left,
            y_top - box_height,
            width,
            box_height,
            "Commercial Driving Daily Log Exemption- Record of Duty Status",
        )
        # Add a second inset stroke for a double outer border on the HOS box.
        hos_box_y = y_top - box_height
        hos_separator_y = hos_box_y + box_height - 17
        inset = 2
        pdf.setLineWidth(0.6)
        # Complete the outer frame through the header strip.
        pdf.line(x_left, hos_separator_y, x_left, y_top)
        pdf.line(x_left + width, hos_separator_y, x_left + width, y_top)
        pdf.line(x_left, y_top, x_left + width, y_top)
        # Second inset frame.
        pdf.line(x_left + inset, hos_box_y + inset, x_left + inset, y_top - inset)
        pdf.line(x_left + inset, hos_box_y + inset, x_left + width - inset, hos_box_y + inset)
        pdf.line(x_left + width - inset, hos_box_y + inset, x_left + width - inset, y_top - inset)
        pdf.line(x_left + inset, y_top - inset, x_left + width - inset, y_top - inset)
        pdf.line(x_left + inset, hos_separator_y, x_left + width - inset, hos_separator_y)

        # ─── Draw header section at top ──────────────────────────────────────
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(
            x_left + 5,
            y_top - 29,
            (
                f"Date: {charter_date_full} | Driver Name: "
                f"{driver_name} | Employee #: {driver_license} | Vehicle ID: {vehicle_id}"
            ),
        )
        pdf.setFont("Helvetica", 7.0)
        pdf.drawString(
            x_left + 5,
            y_top - 39,
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
                f"Start Odo: {(odo_start or '___________'):<11}   "
                f"End Odo: {(odo_end or '___________'):<11}"
            ),
        )
        # Row 1 right: fuel / float
        pdf.drawString(
            x_left + half + 10,
            vehicle_row_1_y,
            f"Distance: {str(total_odo)} km   Fuel: ______ L   Float: $______",
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
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(
            x_left + 5,
            exemption_y,
            "160-KM EXEMPTION — Statement to officer: I confirm all of the following apply to this shift:",
        )
        pdf.setFont("Helvetica", 6.8)
        self._draw_wrapped_lines(
            pdf,
            x_left + 5,
            exemption_text_y,
            width - 10,
            wrapped_exemption_lines,
            6.8,
            line_height=8.0,
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
        invoicing_cfg = self.layout.get("invoicing", {})
        left_width = width * 0.38
        gap = 0.12 * inch
        right_width = width - left_width - gap
        charge_row_height = float(invoicing_cfg.get("row_height", 10.5))

        # Invoicing now sits under routing (left side).
        charges = self._normalize_charges()
        charge_rows = [["CHARGES", "RATE", "UNIT", "AMOUNT"]]
        for charge in charges:
            amount = float(charge.get("amount") or 0)
            rate = float(charge.get("rate") or amount)
            unit_type = self._safe(charge.get("unit_type") or charge.get("rate_type") or "flat")
            charge_rows.append(
                [
                    self._safe(charge.get("label")),
                    f"{rate:.2f}",
                    unit_type,
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
            ["Total Charges:", "", "", f"${total_due:.2f}"],
            ["Non-Refundable Retainer:", "", "", f"${deposit:.2f}"],
            ["Payments Made:", "", "", f"${total_paid:.2f}"],
            ["Amount Due:", "", "", f"${balance:.2f}"],
            ["Chauffeur Cash Collected:", "", "", chauffeur_cash_collected],
        ]

        charge_table_rows = max(
            len(charge_rows), int(invoicing_cfg.get("min_charge_rows", 4))
        )
        charge_rows_display = charge_rows + [["", "", "", ""]] * max(0, charge_table_rows - len(charge_rows))
        charge_rows_display += [["", "", "", ""]] + summary_rows

        table_total_width = left_width
        invoice_font_size = float(invoicing_cfg.get("font_size", 7))
        sample_currency = str(invoicing_cfg.get("currency_width_sample", "$0000.00"))
        numeric_padding = float(invoicing_cfg.get("numeric_padding", 8))
        currency_fit_width = (
            pdfmetrics.stringWidth(sample_currency, "Helvetica", invoice_font_size)
            + numeric_padding
        )
        min_numeric_col = max(
            float(invoicing_cfg.get("numeric_col_min_in", 0.56)) * inch,
            pdfmetrics.stringWidth("$0.00", "Helvetica", invoice_font_size) + 6,
        )
        preferred_numeric_col = max(
            float(invoicing_cfg.get("numeric_col_pref_in", 0.62)) * inch,
            currency_fit_width,
        )
        longest_label_width = 0
        for i, row in enumerate(charge_rows_display):
            label = str(row[0] or "")
            if not label:
                continue
            font_name = "Helvetica-Bold" if i == 0 else "Helvetica"
            longest_label_width = max(
                longest_label_width,
                pdfmetrics.stringWidth(label, font_name, invoice_font_size),
            )
        target_first_col = longest_label_width + float(
            invoicing_cfg.get("label_padding", 10)
        )
        # Fixed narrow UNIT column
        type_col_width = 0.38 * inch
        remaining_width = table_total_width - target_first_col - type_col_width
        if remaining_width >= (2 * preferred_numeric_col):
            rate_col_width = preferred_numeric_col
            amount_col_width = preferred_numeric_col
        elif remaining_width >= (2 * min_numeric_col):
            rate_col_width = remaining_width / 2
            amount_col_width = remaining_width / 2
        else:
            rate_col_width = min_numeric_col
            amount_col_width = min_numeric_col
        first_col_width = table_total_width - type_col_width - rate_col_width - amount_col_width

        # Row indices for styling:
        # row 0 = header, rows 1..charge_table_rows = charge lines,
        # charge_table_rows+1 = blank separator, charge_table_rows+2..+6 = summary rows
        sep_row = charge_table_rows + 1
        summary_start_row = sep_row + 1
        amount_due_row = charge_table_rows + 5
        invoicing_extra_styles = [
            # Header alignment matches the column contents.
            ("ALIGN", (0, 0), (0, 0), "RIGHT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("ALIGN", (2, 0), (2, 0), "CENTER"),
            ("ALIGN", (3, 0), (3, 0), "RIGHT"),
            # Subtle alternating fill on charge rows for readability
            ("ROWBACKGROUNDS", (0, 1), (-1, charge_table_rows), [colors.white, colors.HexColor("#fafafa")]),
            # Thick line above the summary block
            ("LINEABOVE", (0, summary_start_row), (-1, summary_start_row), 0.8, colors.black),
            # Light tint across the whole summary block
            ("BACKGROUND", (0, summary_start_row), (-1, summary_start_row + 4), colors.HexColor("#f7f7f7")),
            # Summary section becomes a 2-column block: label spans first 3 cols
            ("SPAN", (0, summary_start_row), (2, summary_start_row)),
            ("SPAN", (0, summary_start_row + 1), (2, summary_start_row + 1)),
            ("SPAN", (0, summary_start_row + 2), (2, summary_start_row + 2)),
            ("SPAN", (0, summary_start_row + 3), (2, summary_start_row + 3)),
            ("SPAN", (0, summary_start_row + 4), (2, summary_start_row + 4)),
            ("ALIGN", (0, summary_start_row), (2, summary_start_row + 4), "RIGHT"),
            ("ALIGN", (3, summary_start_row), (3, summary_start_row + 4), "RIGHT"),
            # Light lines between each summary row
            ("LINEBELOW", (0, summary_start_row), (-1, -2), 0.3, colors.HexColor("#cccccc")),
            # Bold + slightly larger font for Amount Due row
            ("FONTNAME", (0, amount_due_row), (-1, amount_due_row), "Helvetica-Bold"),
            ("FONTSIZE", (0, amount_due_row), (-1, amount_due_row), invoice_font_size + 0.5),
            # Light shading on Amount Due row
            ("BACKGROUND", (0, amount_due_row), (-1, amount_due_row), colors.HexColor("#f0f0f0")),
        ]

        self._draw_table(
            pdf,
            x_left,
            y_top,
            [first_col_width, rate_col_width, type_col_width, amount_col_width],
            charge_rows_display,
            row_height=charge_row_height,
            font_size=invoice_font_size,
            show_inner_grid=False,
            col_alignments=[
                "RIGHT",
                "RIGHT",
                "CENTER",
                "RIGHT",
            ],
            col_font_sizes=[None, None, None, None],
            col_bold=[False, False, False, False],
            center_header=False,
            extra_styles=invoicing_extra_styles,
        )

        # Right of invoicing: client notes + single beverage strip row.
        notes_text = " ".join(
            part
            for part in [
                self._safe(self.data.get("notes")),
                self._safe(self.data.get("booking_notes")),
                self._safe(self.data.get("special_requirements")),
            ]
            if part and part != "-"
        )
        right_x = x_left + left_width + gap + 3
        right_content_w = right_width - 6

        # Pre-measure notes wrapping so we can size the section correctly
        notes_font_size = 6.6
        notes_lh = 9
        all_notes_sublines = []
        if notes_text:
            for raw in [notes_text]:
                all_notes_sublines.extend(
                    simpleSplit(str(raw), "Helvetica", notes_font_size, right_content_w)
                )
        max_notes_display = 9
        notes_display = all_notes_sublines[:max_notes_display]

        bev_lh = 7.0
        bev_rows = 5  # 3 cols × 5 = 15 slots for 14 items
        bev_block_h = 14 + bev_rows * bev_lh  # label + 5 rows

        notes_block_h = 12 + 9 * notes_lh  # "Notes:" label + fixed 9 rows
        right_col_h = notes_block_h + bev_block_h + 6

        charge_height = len(charge_rows_display) * charge_row_height
        row_height = max(charge_height, right_col_h)

        # Draw notes
        pdf.setFont("Helvetica-Bold", notes_font_size)
        pdf.drawString(right_x, y_top - 10, "Notes:")
        pdf.setFont("Helvetica", notes_font_size)
        note_y = y_top - 20
        for subline in notes_display:
            pdf.drawString(right_x, note_y, subline)
            note_y -= notes_lh

        # Beverage strip: 2-column list after notes
        beverages = self.data.get("beverages") or []
        bev_lines = []
        for bev in beverages[:15]:
            bev_lines.append(
                f"{self._safe(bev.get('quantity'))} {self._safe(bev.get('item_name'))}"
            )
        generic_items = [
            "12 Bud Light", "24 Kokanee", "12 Coors Light", "12 Corona",
            "12 Coors Banquet", "12 Heineken", "12 Michelob Ultra", "12 Budweiser",
            "Soft Drinks / Water", "Juice / Mix",
            "Other: ____________", "Other: ____________",
            "Other: ____________", "Other: ____________",
            "Other: ____________",
        ]
        while len(bev_lines) < 15:
            bev_lines.append(generic_items[len(bev_lines)])

        pdf.setFont("Helvetica-Bold", 6.6)
        bev_label_y = y_top - 20 - 9 * notes_lh - 4  # fixed position after 9-line notes block
        pdf.drawString(right_x, bev_label_y, "Beverages:")
        bev_y = bev_label_y - 13
        bev_col_w = right_content_w / 3
        pdf.setFont("Helvetica", 6.0)
        for i, line in enumerate(bev_lines[:15]):
            col = i // 5
            row = i % 5
            tx = right_x + col * bev_col_w
            ty = bev_y - row * bev_lh
            pdf.drawString(tx, ty, str(line))

        return y_top - row_height

    def _draw_policies_terms(self, pdf, x_left, width, y_top):
        font_size = 7.0
        line_height = 8.4
        inner_pad = 6
        header_gap = 6
        footer_gap = 4

        policy_paragraphs = [
            "By placing a reservation and securing it with a nonrefundable retainer you acknowledge and expressly agree to the following policies, terms and conditions and further expressly authorize Arrow Limousine to charge your credit card in full or part amounts relating to your reservation including but not limited to charging your credit card in full for the reservation should you be considered a no-show.",
            "We accept Visa, or MasterCard. Cash or E-transfer can be arranged. All orders are charged in Canadian Dollars (CAD). We automatically add a standard but adjustable 18 percent gratuity, and GST. All beverage orders, parking fees, tolls, event entrance fees or other charter requirement are billed to your credit card/account unless alternate arrangements are made with the office and noted on the booking.",
            "A retainer is a fee paid in advance and used to hold goods or services and is nonrefundable (NRR).",
            "A Set non-refundable retainer (NRR) is required to confirm and secure a charter run. As soon as your retainer clears, the vehicle is yours for that specific time and date and a confirmation run charter is sent to your email address. We immediately begin turning away business for any, and all inquiries that come in for that vehicle and date.",
            "Bookings for 5 or more hours require a NRR equal to half of the total run charter charges.",
            "Charges to your credit card will be processed immediately for your NRR. The remaining balance is due within 7 days of date of services date. In the event the charter goes longer than planned, additional hourly charges at the extra time rate will apply. Charges will be made within 2 business days for all services added or incurred during your run charter.",
            "Our company is based out of Red Deer, and as such any out-of-town run charters will be billed from the time the vehicle leaves Red Deer and again until it returns to Red Deer.",
            "The Party paying for the Reservation is responsible for all damages and/or cleaning charges incurred by the renter and/or Party of the Renter, including but not limited to some of these minimum rates: Vomit/Sickness/bodily fluids (minimum $250 Fee to cover the hazmat kit) in order for the vehicle to be used again it must be thoroughly sanitized, Alcohol Spillage will in incur a cleaning fee dependent on extent of the cleanup, Broken Glassware ($10,Per Glass), Burns ($500 Replacement/Repair), Smoking ($100. per violation) Upholstery Tears, or damaging stereo/TV/Lights/ or the vehicle itself ($500-1000, Replacement/Repair) as an example Opening a Car Door into another Vehicle or Stationary Object ($1500-2000) tampering/opening emergency exits ($850) etc. these are only some of the minimum charges applicable based on past charters, Any and all charges incurred will be charged to the credit card provided within 2 days, unless alternate arrangements are made by the client.",
            "AGLC rules apply.",
            "Uncontrollable Acts, Acts of God and/or Acts of Mother Nature",
            "- Arrow Limousine is not responsible for acts of God, acts of Mother Nature and/or circumstances that are beyond our control, including but not limited to traffic congestion, road closures, accidents, flight delays, weather delays, etc. Reimbursements or reconciliation will not be made for these conditions. We drive to the conditions.",
            "- We will adapt our driving to account for changes in the environment. If the weather is not favorable our estimate timings will change drastically. We will drive slower when the road conditions require, or the visibility is reduced or the vehicle passenger load is full. Your safety is our Chauffeurs' primary concern so please be patient and try to understand why we are not driving at less than the speed limit on non-paved roads, in towns or during adverse weather.",
            "- By agreeing to a discounted rate, you the Client waive any claims regarding vehicle age, cosmetic condition, climate control irregularities (heating/air conditioning), or non-essential amenities, as long as the service meets safety and regulatory requirements.",
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
        header_font_size = 8.0
        header_line_height = header_font_size + 9
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
        separator_y = y + height - 17
        # Content area borders (below separator): left, bottom, right
        pdf.line(x, y, x, separator_y)                     # left (content only)
        pdf.line(x, y, x + width, y)                       # bottom
        pdf.line(x + width, y, x + width, separator_y)     # right (content only)
        # Title — no top/left/right, just the separator line underneath
        if title:
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawCentredString(x + (width / 2), y + height - 11, title)
            if right_header_text:
                pdf.setFont("Helvetica", 7.2)
                pdf.drawRightString(
                    x + width - 4, y + height - 11, right_header_text
                )
            pdf.line(x, separator_y, x + width, separator_y)

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
        extra_styles=None,
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

        table.setStyle(TableStyle(style + (extra_styles or [])))
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


class ConfirmationLetterPDF:
    """
    Generate a client-facing confirmation letter that mirrors the legacy
    L:\\Confirmation\\quote.pdf layout:
      Page 1 — letterhead, date, Dear client, itinerary, charges, balance, payment method, clauses 1–3
      Page 2 — clauses 4–16, closing / Sincerely block
    """

    COMPANY_NAME = "Arrow Limousine & Sedan Services Ltd."
    COMPANY_ADDR = "#3 6841-52 Ave, Red Deer, Alberta T4N-4L2"
    COMPANY_PHONE = "403-346-0034  |  403-346-4444"
    COMPANY_WEB = "www.arrowlimousine.ca"
    COMPANY_TAGLINE = "Serving the Ground Transportation Industry since 1989  \u2022  Member of the NLA"
    GST_NUMBER = "G.S.T.#: 861 556 827"

    CLAUSES = [
        "Customer hereby verifies that the rental date, anticipated times, number of people and billing information are correctly stated.",
        "Customer shall be liable for all damages to the limousine sustained during Customer's charter, including all spills, burns, rips, tears, or damage to the television, stereo or other electrical or power equipment.",
        "Customer shall pay a service charge of $250.00 to clean any vomit in the limousine.",
        "Customer shall not open any emergency exits, including the sunroof/emergency escape hatch. Penalty is $850.00.",
        "While the vehicle is in motion Customers shall refrain from exiting the vehicle, or littering.",
        "Arrow Limousine reserves the right, without any liability or set-off to the amounts due the charter, to discharge any passenger(s) who interferes with the safe operation of the vehicle, vomits, or engages in any illegal conduct or activity.",
        "Arrow Limousine shall not be liable for any damages arising out of the inability to perform due to inclement weather, mechanical difficulties, delays due to traffic conditions, or any unforeseen events beyond the reasonable control of Arrow Limousine.",
        "Arrow Limousine shall not be the Bailee of any items left in the Limousine, and shall not be responsible for the safe-keeping of any such item.",
        "Customer must pay a NON-REFUNDABLE retainer equal to two hour vehicle rate, with the balance due prior to the charter pickup. Once the retainer is received it is acknowledged that you have agreed on these conditions and agreed on the contract.",
        "Customer hereby authorizes Arrow Limousine to charge any unpaid charges to the above credit card account.",
        "SMOKING/VAPING is not permitted inside limousines and will be charged accordingly. Thank You.",
        "We are licensed under the AGLC and adhere to all Gaming and Liquor Act, Regulation and related policy. (E.g. 18+, all liquor purchased, provided or consumed in a limousine must be from the licensee. Liquor provided under our license may only be consumed on route.)",
        "All beverage totals are final. If requested a multiple total per beverage list prices may increase for extra work.",
        "Customer must pay for any extra time added for additional trip time due to time extensions.",
        "We charge all cards 2 business days prior/after to date of reservations, along with any extra charges.",
        "All out of town charters will be billed from the time the vehicle leaves Red Deer and again until it returns to Red Deer.",
    ]

    def __init__(self, charter_data: dict[str, Any]):
        self.d = charter_data
        self.buffer = BytesIO()
        self.width, self.height = LETTER
        self.lm = 0.75 * inch   # left margin
        self.rm = 0.75 * inch   # right margin
        self.cw = self.width - self.lm - self.rm  # content width

    # ── helpers ──────────────────────────────────────────────────────────────

    def _s(self, v, default="-"):
        if v is None or str(v).strip() == "":
            return default
        return str(v).strip()

    def _fmt_date(self, v):
        if not v:
            return "-"
        try:
            if hasattr(v, "strftime"):
                return v.strftime("%m/%d/%Y")
            from datetime import date
            if isinstance(v, str):
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        return datetime.strptime(v[:10], fmt).strftime("%m/%d/%Y")
                    except ValueError:
                        pass
        except Exception:
            pass
        return str(v)[:10]

    def _fmt_time(self, v):
        if not v:
            return ""
        try:
            s = str(v)
            if ":" in s:
                parts = s.split(":")
                h, m = int(parts[0]), int(parts[1])
                suffix = "AM" if h < 12 else "PM"
                h12 = h % 12 or 12
                return f"{h12}:{m:02d}:00 {suffix}"
        except Exception:
            pass
        return str(v)

    def _fmt_currency(self, v):
        try:
            return f"{float(v or 0):.2f}"
        except (TypeError, ValueError):
            return "0.00"

    def _draw_letterhead(self, pdf, y):
        """Draw top letterhead block, return y after."""
        ctr = self.lm + self.cw / 2
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(ctr, y, "Arrow Limousine")
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(ctr, y - 16, "& SEDAN SERVICES LTD.")
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(ctr, y - 30, f"{self.COMPANY_PHONE}    {self.COMPANY_WEB}")
        pdf.setFont("Helvetica-Oblique", 7.5)
        pdf.drawCentredString(ctr, y - 41, self.COMPANY_TAGLINE)
        pdf.setFont("Helvetica", 7.5)
        pdf.drawCentredString(ctr, y - 52, f"{self.COMPANY_ADDR}    {self.GST_NUMBER}")
        # rule
        pdf.setLineWidth(0.8)
        pdf.line(self.lm, y - 60, self.lm + self.cw, y - 60)
        return y - 68

    def _draw_wrapped(self, pdf, x, y, w, text, font="Helvetica", size=9.5, lh=13):
        """Draw wrapped text, return y after last line."""
        lines = simpleSplit(str(text), font, size, w)
        pdf.setFont(font, size)
        for line in lines:
            pdf.drawString(x, y, line)
            y -= lh
        return y

    def _draw_clause(self, pdf, x, y, w, num, text, size=8.5, lh=11.5):
        label = f"{num}."
        label_w = pdfmetrics.stringWidth(label, "Helvetica-Bold", size) + 4
        pdf.setFont("Helvetica-Bold", size)
        pdf.drawString(x, y, label)
        lines = simpleSplit(text, "Helvetica", size, w - label_w)
        pdf.setFont("Helvetica", size)
        for i, line in enumerate(lines):
            pdf.drawString(x + label_w, y, line)
            y -= lh
        return y - 2

    # ── main generator ───────────────────────────────────────────────────────

    def generate(self) -> bytes:
        pdf = canvas.Canvas(self.buffer, pagesize=LETTER)
        d = self.d
        lm, cw = self.lm, self.cw

        # ── PAGE 1 ────────────────────────────────────────────────────────
        y = self.height - 0.55 * inch
        y = self._draw_letterhead(pdf, y)

        # Date + reservation number
        today = datetime.now().strftime("%m/%d/%Y")
        reserve = self._s(d.get("reserve_number"), "TBD")
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(lm, y, today)
        pdf.drawString(lm + 2.2 * inch, y,
                       f"Your Reservation Number is {reserve}.")
        y -= 11
        pdf.drawRightString(lm + cw, y,
                            "Please quote this number when calling us.")
        y -= 18

        # Dear
        client = self._s(
            d.get("client_display_name") or d.get("client_name"), ""
        )
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(lm, y, f"Dear {client}:")
        y -= 16

        # Body intro
        intro = (
            "Thank you for choosing Arrow Limousine & Sedan Services Ltd.  "
            "We have reserved the following transportation for you:"
        )
        y = self._draw_wrapped(pdf, lm, y, cw, intro, size=9.5, lh=13)
        y -= 6

        # Charter summary
        charter_date = self._fmt_date(d.get("charter_date"))
        res_time = self._fmt_time(d.get("pickup_time") or d.get("actual_pickup_time"))
        vehicle = self._s(
            d.get("vehicle_description")
            or d.get("vehicle")
            or d.get("vehicle_type"), ""
        )
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(lm, y,
                       f"Date for the Reservation: {charter_date}"
                       f"            Reservation Time: {res_time}")
        y -= 13
        pdf.drawString(lm, y, f"Type of Vehicle:  {vehicle}")
        y -= 16

        # Itinerary
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(lm, y, "Itinerary:")
        y -= 13
        routes = d.get("routes") or []
        if routes:
            pdf.setFont("Helvetica", 9)
            for route in routes:
                etype = self._s(route.get("event_type_code"), "")
                addr = self._s(
                    route.get("address")
                    or route.get("pickup_location")
                    or route.get("dropoff_location"), ""
                )
                t = self._fmt_time(
                    route.get("stop_time")
                    or route.get("pickup_time")
                    or route.get("dropoff_time")
                )
                seq = route.get("route_sequence") or ""
                t_part = f"{t}, " if t else ""
                line = f"{etype}  {t_part}{addr}"
                notes = self._s(route.get("route_notes"), "")
                if notes:
                    line += f"  — {notes}"
                lines = simpleSplit(line, "Helvetica", 9, cw - 12)
                for ln in lines:
                    pdf.drawString(lm + 12, y, ln)
                    y -= 12
        else:
            pdf.setFont("Helvetica", 9)
            pu = self._s(d.get("pickup_address"), "")
            do = self._s(d.get("dropoff_address"), "")
            if pu:
                pdf.drawString(lm + 12, y,
                               f"Pick up, {self._fmt_time(d.get('pickup_time'))}, Leave For {pu}")
                y -= 12
            if do:
                pdf.drawString(lm + 12, y,
                               f"Drop off, {self._fmt_time(d.get('dropoff_time'))}, {do}")
                y -= 12
        y -= 8

        # Charges
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(lm, y, "Current Charges:")
        y -= 14

        charges = d.get("charges") or []
        col1_w = 2.8 * inch
        col2_w = 0.9 * inch
        col3_w = 0.9 * inch
        col4_w = 1.0 * inch
        pdf.setFont("Helvetica", 9)
        # charges table has: charge_type, description, amount (no unit/rate columns)
        for ch in charges:
            desc = self._s(ch.get("description") or ch.get("charge_type"), "")
            amt = float(ch.get("amount") or 0)
            if amt == 0 and not desc:
                continue
            pdf.drawString(lm, y, desc)
            pdf.drawRightString(lm + col1_w + col2_w + col3_w, y, self._fmt_currency(amt))
            y -= 12

        if not charges:
            total_due = float(d.get("total_amount_due") or d.get("grand_total") or 0)
            if total_due:
                pdf.drawString(lm, y, "Service Fee")
                pdf.drawRightString(lm + col1_w + col2_w + col3_w, y,
                                    self._fmt_currency(total_due))
                y -= 12
        y -= 6

        # Totals
        total = float(d.get("total_amount_due") or d.get("grand_total") or 0)
        paid = float(d.get("total_paid") or d.get("amount_paid") or d.get("paid_amount") or 0)
        balance = total - paid
        nrr = float(d.get("nrr_amount") or 0)

        # Totals block
        right_edge = lm + cw
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(lm, y, "Total Charges:")
        pdf.drawRightString(right_edge, y, f"${self._fmt_currency(total)}")
        y -= 13

        # NRR received line — always show so the client can see retainer applied
        nrr_label = "Non-Refundable Retainer (NRR) Received:"
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(lm, y, nrr_label)
        pdf.drawRightString(right_edge, y, f"(${self._fmt_currency(nrr)})")
        y -= 1
        # underline under the NRR line
        pdf.setLineWidth(0.5)
        pdf.line(lm, y, right_edge, y)
        y -= 11

        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(lm, y, "Balance Owing:")
        pdf.drawRightString(right_edge, y, f"${self._fmt_currency(balance)}")
        y -= 8

        # Placed by
        placed_by = self._s(
            d.get("client_display_name") or d.get("client_name") or d.get("company_name"), ""
        )
        if placed_by:
            pdf.setFont("Helvetica", 9)
            pdf.drawString(lm, y, f"Your order was placed by {placed_by}.")
            y -= 16

        # Mid-body paragraph
        mid_text = (
            "If you find it necessary to change your plans, please inform us 24 hours prior to the "
            "Reservation Time indicated above.  All deposits are non refundable.  We recommend "
            "a standard gratuity of 10-15%, we automatically proceed with a 18% gratuity "
            "unless otherwise informed prior.  If you are not able to contact us for your change or "
            "cancellation, we will proceed as per the information listed above and the regular fees "
            "will apply."
        )
        y = self._draw_wrapped(pdf, lm, y, cw, mid_text, size=9, lh=12)
        y -= 10

        # Payment method
        pm = self._s(d.get("payment_method"), "")
        if pm:
            pdf.setFont("Helvetica", 9.5)
            pdf.drawString(lm, y, f"Method of Payment: {pm}")
            y -= 16

        # Liability header
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(lm, y, "Liability")
        y -= 14

        # Clauses 1-3 on page 1 (whatever fits)
        clauses_page1 = self.CLAUSES[:3]
        for i, clause in enumerate(clauses_page1):
            y = self._draw_clause(pdf, lm, y, cw, i + 1, clause)
            if y < 72:
                break

        pdf.showPage()

        # ── PAGE 2 ────────────────────────────────────────────────────────
        y = self.height - 0.55 * inch
        y = self._draw_letterhead(pdf, y)

        # Page 2 marker
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(lm, y, f"\u2013  2 \u2013  {datetime.now().strftime('%B %d, %Y')}")
        y -= 16

        # Clauses 4-16
        for i, clause in enumerate(self.CLAUSES[3:], start=4):
            y = self._draw_clause(pdf, lm, y, cw, i, clause)
            if y < 160:
                # Need a new page if we run out of room
                pdf.showPage()
                y = self.height - 0.55 * inch
                y = self._draw_letterhead(pdf, y)

        y -= 8

        # Closing paragraph
        closing = (
            "We appreciate your business.  If you need further clarification or would like to make "
            "changes please contact us at (403) 346-0034 or www.arrowlimousine.ca"
        )
        y = self._draw_wrapped(pdf, lm, y, cw, closing, size=9, lh=12)
        y -= 20

        # Sincerely block
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(lm, y, "Sincerely,")
        y -= 36
        pdf.drawString(lm, y, "Sales")
        y -= 13
        pdf.drawString(lm, y, "Reservations Agent")
        y -= 13
        pdf.drawString(lm, y, self.COMPANY_NAME)

        pdf.save()
        self.buffer.seek(0)
        return self.buffer.getvalue()


def generate_confirmation_letter_pdf(charter_data: dict[str, Any]) -> bytes:
    """
    Generate a client-facing confirmation letter PDF mirroring the legacy quote.pdf layout.

    Args:
        charter_data: dict with charter fields, routes, charges, payments

    Returns:
        bytes: PDF file content
    """
    return ConfirmationLetterPDF(charter_data).generate()


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
