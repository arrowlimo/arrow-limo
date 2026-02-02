"""
Generate fillable PDF forms from charter data using reportlab
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


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
        self.width, self.height = letter
        self.left_margin = 0.5 * inch
        self.right_margin = 0.5 * inch
        self.top_margin = 0.5 * inch
        self.bottom_margin = 0.5 * inch

    def generate(self):
        """Generate the PDF form and return bytes"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            rightMargin=self.right_margin,
            leftMargin=self.left_margin,
            topMargin=self.top_margin,
            bottomMargin=self.bottom_margin,
            title=(
                "Charter Invoice - "
                "{}".format(self.data.get("reserve_number", "TBD"))
            ),
        )

        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#007bff"),
            spaceAfter=12,
            fontName="Helvetica-Bold",
        )

        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#007bff"),
            spaceAfter=8,
            spaceBefore=8,
            fontName="Helvetica-Bold",
            background="#f0f7ff",
        )

        normal_style = ParagraphStyle(
            "CustomNormal", parent=styles["Normal"], fontSize=10, spaceAfter=4
        )

        # HEADER
        header_data = [
            [
                Paragraph(
                    (
                        "<b>ALMS Charter Services</b><br/>"
                        "Charter Invoice & Receipt"
                    ),
                    title_style,
                ),
                Paragraph(
                    (
                        "<b>Invoice #:</b> {}<br/>"
                        "<b>Date:</b> {}"
                    ).format(
                        self.data.get("reserve_number", "TBD"),
                        self._format_date(self.data.get("charter_date")),
                    ),
                    normal_style,
                ),
            ]
        ]
        header_table = Table(header_data, colWidths=[4 * inch, 2.5 * inch])
        header_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.append(header_table)

        # BILL TO SECTION
        story.append(Paragraph("<b>BILL TO:</b>", section_style))
        bill_to_text = """
        <b>{self.data.get('client_name', 'Not specified')}</b><br/>
        {self.data.get('company_name', '')}<br/>
        {self.data.get('email', '')}<br/>
        {self.data.get('phone', '')}
        """
        story.append(Paragraph(bill_to_text, normal_style))
        story.append(Spacer(1, 0.2 * inch))

        # RESERVATION SUMMARY
        story.append(Paragraph("<b>RESERVATION SUMMARY</b>", section_style))
        res_data = [
            [
                Paragraph("<b>Reserve #:</b>", normal_style),
                Paragraph(self.data.get("reserve_number", ""), normal_style),
                Paragraph("<b>Charter Date:</b>", normal_style),
                Paragraph(
                    self._format_date(self.data.get("charter_date")),
                    normal_style,
                ),
            ],
            [
                Paragraph("<b>Status:</b>", normal_style),
                Paragraph(self.data.get("status", "Active"), normal_style),
                Paragraph("<b>Type:</b>", normal_style),
                Paragraph(
                    self._format_charter_type(self.data.get("charter_type")),
                    normal_style,
                ),
            ],
            [
                Paragraph("<b>Passengers:</b>", normal_style),
                Paragraph(
                    str(self.data.get("passenger_load", "TBD")), normal_style
                ),
                Paragraph("<b>Reconciliation:</b>", normal_style),
                Paragraph(
                    self.data.get("reconciliation_status", "Not Reconciled"),
                    normal_style,
                ),
            ],
        ]
        res_table = Table(
            res_data,
            colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch],
        )
        res_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.grey),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(res_table)
        story.append(Spacer(1, 0.15 * inch))

        # TRIP DETAILS
        story.append(Paragraph("<b>TRIP DETAILS</b>", section_style))
        trip_text = """
        <b>Pickup:</b> {self.data.get('pickup_address', 'Not specified')}<br/>
        <b>Dropoff:</b> {self.data.get('dropoff_address', 'Not specified')}
        """
        story.append(Paragraph(trip_text, normal_style))
        story.append(Spacer(1, 0.15 * inch))

        # VEHICLE & DRIVER
        story.append(Paragraph("<b>VEHICLE & DRIVER</b>", section_style))
        veh_data = [
            [
                Paragraph(
                    (
                        "<b>Vehicle:</b><br/>"
                        "{}"
                    ).format(self.data.get("vehicle", "Not assigned")),
                    normal_style,
                ),
                Paragraph(
                    (
                        "<b>Driver:</b><br/>"
                        "{}"
                    ).format(self.data.get("driver_name", "Not assigned")),
                    normal_style,
                ),
                Paragraph(
                    (
                        "<b>Capacity:</b><br/>"
                        "{} pax"
                    ).format(self.data.get("vehicle_capacity", "N/A")),
                    normal_style,
                ),
            ]
        ]
        veh_table = Table(veh_data, colWidths=[2 * inch, 2 * inch, 1.5 * inch])
        veh_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(veh_table)
        story.append(Spacer(1, 0.15 * inch))

        # CHARGES
        story.append(Paragraph("<b>CHARGES & FEES</b>", section_style))
        charges_data = [
            ["Description", "Qty", "Rate", "Amount"],
            [
                "Charter Service",
                "1",
                f"${float(self.data.get('total_amount_due', 0)):.2f}",
                f"${float(self.data.get('total_amount_due', 0)):.2f}",
            ],
        ]

        if float(self.data.get("nrr_amount", 0)) > 0:
            charges_data.append(
                [
                    "NRR/Retainer (Non-Refundable)",
                    "1",
                    f"${float(self.data.get('nrr_amount', 0)):.2f}",
                    f"${float(self.data.get('nrr_amount', 0)):.2f}",
                ]
            )

        charges_table = Table(
            charges_data,
            colWidths=[2.5 * inch, 0.75 * inch, 1.5 * inch, 1.25 * inch],
        )
        charges_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#e8f0f8"),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f9f9f9")],
                    ),
                ]
            )
        )
        story.append(charges_table)
        story.append(Spacer(1, 0.15 * inch))

        # PAYMENT SUMMARY
        story.append(Paragraph("<b>PAYMENT SUMMARY</b>", section_style))
        total_due = float(self.data.get("total_amount_due", 0))
        total_paid = float(self.data.get("total_paid", 0))
        balance = total_due - total_paid

        payment_data = [
            ["Total Charges:", f"${total_due:.2f}"],
            ["Total Payments:", f"${total_paid:.2f}"],
            ["NRR/Retainer:", f"${float(self.data.get('nrr_amount', 0)):.2f}"],
            ["Balance Due:", f"${balance:.2f}"],
        ]

        payment_table = Table(payment_data, colWidths=[4 * inch, 2.5 * inch])
        payment_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, -1), (1, -1), 11),
                    (
                        "BACKGROUND",
                        (0, -1),
                        (-1, -1),
                        colors.HexColor("#f0f7ff"),
                    ),
                    (
                        "LINEABOVE",
                        (0, -1),
                        (-1, -1),
                        1,
                        colors.HexColor("#007bff"),
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(payment_table)
        story.append(Spacer(1, 0.2 * inch))

        # GL CODES (if present)
        if self.data.get("gl_revenue_code") or self.data.get(
            "gl_expense_code"
        ):
            story.append(
                Paragraph("<b>BILLING & GL CODES</b>", section_style)
            )
            gl_data = [
                ["GL Revenue Code:", self.data.get("gl_revenue_code", "4000")],
                ["GL Expense Code:", self.data.get("gl_expense_code", "6100")],
            ]
            gl_table = Table(gl_data, colWidths=[2.5 * inch, 2 * inch])
            gl_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, -1),
                            colors.HexColor("#f9f9f9"),
                        ),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(gl_table)
            story.append(Spacer(1, 0.2 * inch))

        # EXCHANGE OF SERVICES (if applicable)
        if self.data.get("charter_type") == "exchange_of_services":
            story.append(
                Paragraph("<b>EXCHANGE OF SERVICES</b>", section_style)
            )
            exch_details = self.data.get("exchange_of_services_details", {})
            exch_text = (
                "<b>Service Provided:</b> "
                "{}<br/>"
                "<b>Service Provider:</b> "
                "{}<br/>"
                "<b>Exchange Value:</b> "
                "${:.2f}<br/>"
                "<b>Description:</b> {}"
            ).format(
                exch_details.get("service_provided", "Not specified"),
                exch_details.get("service_provider", "Not specified"),
                float(exch_details.get("exchange_value", 0)),
                exch_details.get("description", "No description"),
            )
            story.append(Paragraph(exch_text, normal_style))
            story.append(Spacer(1, 0.2 * inch))

        # FOOTER
        footer_text = (
            "Thank you for your business! | This is an automated "
            "invoice. Please contact our office for questions."
        )
        story.append(Spacer(1, 0.1 * inch))
        story.append(
            Paragraph(
                footer_text,
                ParagraphStyle(
                    "Footer",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=colors.HexColor("#666666"),
                    alignment=TA_CENTER,
                ),
            )
        )

        # Build PDF
        doc.build(story)
        self.buffer.seek(0)
        return self.buffer.getvalue()

    def _format_date(self, date_str):
        """Format date string for display"""
        if not date_str:
            return "Not specified"
        try:
            if isinstance(date_str, str):
                date_obj = datetime.fromisoformat(date_str)
            else:
                date_obj = date_str
            return date_obj.strftime("%B %d, %Y")
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


def generate_charter_pdf(charter_data):
    """
    Generate a charter PDF form

    Args:
        charter_data: dict with charter details

    Returns:
        bytes: PDF file content
    """
    form = CharterPDFForm(charter_data)
    return form.generate()
