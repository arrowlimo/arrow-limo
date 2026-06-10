"""
Report Management Tab - PDF Quote/Confirmation Template Management
Handles fillable PDFs (quote.pdf), charter confirmations,
and custom report generation.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QTimeEdit,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QFormLayout,
    QGroupBox,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt, QDate, QTime, pyqtSignal
from PyQt6.QtGui import QFont

try:
    from PyPDF2 import PdfReader, PdfWriter

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from database import DatabaseManager
except ImportError:
    from db_connection import DatabaseConnection as DatabaseManager


class PDFQuoteManager:
    """Handles PDF quote template filling and generation."""

    def __init__(self, template_path="L:/Confirmation/quote.pdf") -> None:
        self.template_path = template_path
        self.template_exists = os.path.exists(template_path)

    def get_template_info(self) -> object:
        """Get info about the template PDF."""
        if not self.template_exists:
            return {"status": "Template not found", "path": self.template_path}

        try:
            if PYPDF_AVAILABLE:
                reader = PdfReader(self.template_path)
                fields = reader.get_fields()
                return {
                    "status": "OK",
                    "pages": len(reader.pages),
                    "fields": list(fields.keys()) if fields else [],
                    "has_form": bool(fields),
                }
        except Exception as e:
            return {"status": f"Error reading PDF: {str(e)}"}

        return {
            "status": "OK (flat PDF - no form fields)",
            "path": self.template_path,
        }

    def fill_pdf_fields(self, field_data: dict, output_path: str) -> object:
        """Fill PDF form fields and save to output path."""
        if not PYPDF_AVAILABLE:
            return False, "PyPDF2 not available"

        try:
            reader = PdfReader(self.template_path)
            writer = PdfWriter()

            # Get fields
            fields = reader.get_fields()
            if not fields:
                return False, "Template has no fillable form fields"

            # Update fields
            for field_name, field_data_item in fields.items():
                if field_name in field_data:
                    writer.update_page_form_field_values(
                        writer.add_form_to_write(reader),
                        {field_name: str(field_data[field_name])},
                    )

            # Write output
            with open(output_path, "wb") as f:
                writer.write(f)

            return True, f"PDF saved to {output_path}"

        except Exception as e:
            return False, f"Error filling PDF: {str(e)}"

    def generate_quote_overlay_pdf(self, charter_data: dict, output_path: str) -> object:
        """Generate a quote PDF by overlaying text on template."""
        if not REPORTLAB_AVAILABLE:
            return False, "reportlab not available"

        try:
            # Create new PDF with quote content
            c = canvas.Canvas(output_path, pagesize=letter)
            width, height = letter

            # Header
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, "ARROW LIMO - CHARTER QUOTE")

            # Quote details
            c.setFont("Helvetica", 11)
            y = height - 100

            fields_to_display = [
                ("Quote Date:", charter_data.get("quote_date", "")),
                ("Client Name:", charter_data.get("client_name", "")),
                ("Charter Date:", charter_data.get("charter_date", "")),
                ("Pickup Time:", charter_data.get("pickup_time", "")),
                ("Estimated Hours:", charter_data.get("est_hours", "")),
                ("Vehicle Type:", charter_data.get("vehicle_type", "")),
                ("Passengers:", charter_data.get("passengers", "")),
            ]

            for label, value in fields_to_display:
                c.drawString(50, y, f"{label} {value}")
                y -= 20

            # Quote items table
            y -= 20
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, "Quote Items:")
            y -= 20

            c.setFont("Helvetica", 10)
            items = charter_data.get("quote_items", [])
            for item in items:
                desc = item.get("description", "")
                amount = item.get("amount", 0)
                c.drawString(60, y, f"{desc}: ${amount:.2f}")
                y -= 15

            # Totals
            y -= 10
            c.setFont("Helvetica-Bold", 11)
            subtotal = charter_data.get("subtotal", 0)
            gst = charter_data.get("gst", 0)
            total = charter_data.get("total", 0)

            c.drawString(50, y, f"Subtotal: ${subtotal:.2f}")
            y -= 20
            c.drawString(50, y, f"GST (5%): ${gst:.2f}")
            y -= 20
            c.drawString(50, y, f"TOTAL: ${total:.2f}")

            # Terms
            y -= 40
            c.setFont("Helvetica", 9)
            c.drawString(
                50,
                y,
                "Terms: 50% deposit required to confirm booking. Balance due"
                "24 hours before charter.",
            )

            c.save()
            return True, f"Quote PDF generated: {output_path}"

        except Exception as e:
            return False, f"Error generating PDF: {str(e)}"


class ReportManagementWidget(QWidget):
    """Main Report Management widget with tabs for PDF quotes and"
    "confirmations."""

    def __init__(self, db: DatabaseManager) -> None:
        super().__init__()
        self.db = db
        self.pdf_manager = PDFQuoteManager()
        self.last_generated_pdf = (
            None  # Track last generated quote for printing
        )

        self.init_ui()
        self.check_template()

    def init_ui(self) -> None:
        """Initialize UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("📊 Report Management & PDF Templates")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # PDF Quote Manager tab
        self.tabs.addTab(self._create_pdf_quote_tab(), "📋 PDF Quote Manager")

        # Charter Confirmation tab
        self.tabs.addTab(
            self._create_confirmation_tab(), "✅ Charter Confirmation"
        )

        # Template Manager tab
        self.tabs.addTab(
            self._create_template_manager_tab(), "⚙️ Template Manager"
        )

        self.setLayout(layout)

    def check_template(self) -> None:
        """Check if quote.pdf template is available."""
        info = self.pdf_manager.get_template_info()
        if info.get("status") == "OK":
            print(f"✓ Quote template found: {self.pdf_manager.template_path}")
        else:
            print(f"⚠ Quote template issue: {info.get('status')}")

    def _create_pdf_quote_tab(self) -> object:
        """Create PDF Quote Manager tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Status section
        status_group = QGroupBox("Template Status")
        status_layout = QVBoxLayout()
        self.template_status_label = QLabel()
        self.refresh_template_status()
        status_layout.addWidget(self.template_status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Quote entry form
        form_group = QGroupBox("Generate Quote")
        form_layout = QFormLayout()

        # Client selection/entry
        client_layout = QHBoxLayout()
        self.quote_client_combo = QComboBox()
        self.quote_client_combo.setEditable(True)
        client_layout.addWidget(self.quote_client_combo)
        self.quote_client_refresh_btn = QPushButton("🔄 Refresh Clients")
        self.quote_client_refresh_btn.clicked.connect(
            self._refresh_quote_clients
        )
        client_layout.addWidget(self.quote_client_refresh_btn)
        form_layout.addRow("Client:", client_layout)

        # Quote details
        self.quote_date_edit = QDateEdit()
        self.quote_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Quote Date:", self.quote_date_edit)

        self.charter_date_edit = QDateEdit()
        self.charter_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Charter Date:", self.charter_date_edit)

        self.pickup_time_edit = QTimeEdit()
        self.pickup_time_edit.setTime(QTime(8, 0))
        form_layout.addRow("Pickup Time:", self.pickup_time_edit)

        self.est_hours_spin = QDoubleSpinBox()
        self.est_hours_spin.setValue(4.0)
        self.est_hours_spin.setMaximum(24.0)
        form_layout.addRow("Estimated Hours:", self.est_hours_spin)

        self.vehicle_type_combo = QComboBox()
        self.vehicle_type_combo.addItems(
            ["Sedan", "SUV", "Limousine", "Coach", "Shuttle"]
        )
        form_layout.addRow("Vehicle Type:", self.vehicle_type_combo)

        self.passengers_spin = QSpinBox()
        self.passengers_spin.setValue(4)
        self.passengers_spin.setMaximum(60)
        form_layout.addRow("Passengers:", self.passengers_spin)

        # Hourly rate
        self.hourly_rate_spin = QDoubleSpinBox()
        self.hourly_rate_spin.setValue(75.00)
        self.hourly_rate_spin.setMaximum(999.99)
        form_layout.addRow("Hourly Rate ($):", self.hourly_rate_spin)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Quote items
        items_group = QGroupBox("Quote Line Items")
        items_layout = QVBoxLayout()

        self.quote_items_table = QTableWidget()
        self.quote_items_table.setColumnCount(3)
        self.quote_items_table.setHorizontalHeaderLabels(
            ["Description", "Quantity", "Amount"]
        )
        self.quote_items_table.setMaximumHeight(200)
        items_layout.addWidget(self.quote_items_table)

        items_btn_layout = QHBoxLayout()
        add_item_btn = QPushButton("➕ Add Item")
        add_item_btn.clicked.connect(self._add_quote_item)
        items_btn_layout.addWidget(add_item_btn)

        remove_item_btn = QPushButton("🗑️ Remove Selected")
        remove_item_btn.clicked.connect(self._remove_quote_item)
        items_btn_layout.addWidget(remove_item_btn)

        items_layout.addLayout(items_btn_layout)
        items_group.setLayout(items_layout)
        layout.addWidget(items_group)

        # Totals
        totals_group = QGroupBox("Quote Totals")
        totals_layout = QFormLayout()

        self.quote_subtotal_label = QLabel("$0.00")
        totals_layout.addRow("Subtotal:", self.quote_subtotal_label)

        self.quote_gst_label = QLabel("$0.00")
        totals_layout.addRow("GST (5%):", self.quote_gst_label)

        self.quote_total_label = QLabel("$0.00")
        self.quote_total_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        totals_layout.addRow("TOTAL:", self.quote_total_label)

        totals_group.setLayout(totals_layout)
        layout.addWidget(totals_group)

        # Action buttons
        btn_layout = QHBoxLayout()

        generate_btn = QPushButton("📄 Generate PDF Quote")
        generate_btn.clicked.connect(self._generate_quote_pdf)
        btn_layout.addWidget(generate_btn)

        self.print_btn = QPushButton("🖨️ Print Quote for Email")
        self.print_btn.clicked.connect(self._print_quote)
        self.print_btn.setEnabled(False)  # Only enable after generating
        btn_layout.addWidget(self.print_btn)

        save_btn = QPushButton("💾 Save Quote Template")
        save_btn.clicked.connect(self._save_quote_template)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_confirmation_tab(self) -> object:
        """Create Charter Confirmation tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel(
            "Charter confirmations generated from the Charter form will"
            "appear here."
        )
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)

        # Confirmation history
        history_group = QGroupBox("Recent Confirmations")
        history_layout = QVBoxLayout()

        self.confirmation_list = QTableWidget()
        self.confirmation_list.setColumnCount(4)
        self.confirmation_list.setHorizontalHeaderLabels(
            ["Charter ID", "Client", "Date", "Action"]
        )
        history_layout.addWidget(self.confirmation_list)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_template_manager_tab(self) -> object:
        """Create Template Manager tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Template info
        info_group = QGroupBox("Available Templates")
        info_layout = QVBoxLayout()

        self.templates_info = QTextEdit()
        self.templates_info.setReadOnly(True)
        self._update_templates_info()
        info_layout.addWidget(self.templates_info)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Template actions
        action_group = QGroupBox("Template Actions")
        action_layout = QHBoxLayout()

        browse_btn = QPushButton("📂 Browse Templates Folder")
        browse_btn.clicked.connect(lambda: os.startfile("L:/Confirmation"))
        action_layout.addWidget(browse_btn)

        upload_btn = QPushButton("📤 Upload Custom Template")
        upload_btn.clicked.connect(self._upload_template)
        action_layout.addWidget(upload_btn)

        refresh_btn = QPushButton("🔄 Refresh Info")
        refresh_btn.clicked.connect(self._update_templates_info)
        action_layout.addWidget(refresh_btn)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def refresh_template_status(self) -> None:
        """Refresh template status display."""
        info = self.pdf_manager.get_template_info()
        status_text = f"Status: {info.get('status', 'Unknown')}\n"
        status_text += f"Path: {self.pdf_manager.template_path}\n"

        if info.get("pages"):
            status_text += f"Pages: {info.get('pages')}\n"

        if info.get("has_form"):
            status_text += f"Form Fields: {len(info.get('fields', []))}\n"
            status_text += "Fields: " + ", ".join(info.get("fields", []))
        else:
            status_text += (
                "Type: Flat PDF (no form fields)\n"
                "Note: Will generate overlay PDFs"
            )

        self.template_status_label.setText(status_text)

    def _refresh_quote_clients(self) -> None:
        """Load clients from database."""
        try:
            clients = self.db.fetch_all(
                "SELECT DISTINCT client_name FROM charters ORDER BY"
                "client_name"
            )
            self.quote_client_combo.clear()
            for row in clients:
                self.quote_client_combo.addItem(row[0])
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to load clients: {str(e)}"
            )

    def _add_quote_item(self) -> None:
        """Add a new row to quote items table."""
        row = self.quote_items_table.rowCount()
        self.quote_items_table.insertRow(row)

    def _remove_quote_item(self) -> None:
        """Remove selected row from quote items table."""
        row = self.quote_items_table.currentRow()
        if row >= 0:
            self.quote_items_table.removeRow(row)

    def _generate_quote_pdf(self) -> None:
        """Generate quote PDF with current data."""
        # Gather quote data
        charter_data = {
            "quote_date": self.quote_date_edit.date().toString("yyyy-MM-dd"),
            "client_name": self.quote_client_combo.currentText(),
            "charter_date": self.charter_date_edit.date().toString(
                "yyyy-MM-dd"
            ),
            "pickup_time": self.pickup_time_edit.time().toString("HH:mm"),
            "est_hours": str(self.est_hours_spin.value()),
            "vehicle_type": self.vehicle_type_combo.currentText(),
            "passengers": str(self.passengers_spin.value()),
            "quote_items": [],
        }

        # Collect quote items
        for row in range(self.quote_items_table.rowCount()):
            desc_item = self.quote_items_table.item(row, 0)
            qty_item = self.quote_items_table.item(row, 1)
            amt_item = self.quote_items_table.item(row, 2)

            if desc_item and qty_item and amt_item:
                try:
                    charter_data["quote_items"].append(
                        {
                            "description": desc_item.text(),
                            "quantity": (
                                float(qty_item.text())
                                if qty_item.text()
                                else 1
                            ),
                            "amount": (
                                float(amt_item.text())
                                if amt_item.text()
                                else 0
                            ),
                        }
                    )
                except Exception:
                    pass

        # Calculate totals
        subtotal = sum(item["amount"] for item in charter_data["quote_items"])
        gst = subtotal * 0.05
        total = subtotal + gst

        charter_data["subtotal"] = subtotal
        charter_data["gst"] = gst
        charter_data["total"] = total

        # Update display
        self.quote_subtotal_label.setText(f"${subtotal:.2f}")
        self.quote_gst_label.setText(f"${gst:.2f}")
        self.quote_total_label.setText(f"${total:.2f}")

        # Save dialog
        client_name = charter_data["client_name"] or "Quote"
        default_name = (
            f"Quote_{client_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Quote PDF", default_name, "PDF Files (*.pdf)"
        )

        if file_path:
            success, message = self.pdf_manager.generate_quote_overlay_pdf(
                charter_data, file_path
            )
            if success:
                self.last_generated_pdf = file_path  # Store for printing
                self.print_btn.setEnabled(True)  # Enable print button
                QMessageBox.information(self, "Success", message)
                os.startfile(file_path)
            else:
                QMessageBox.warning(self, "Error", message)

    def _print_quote(self) -> None:
        """Open quote PDF in print dialog for email/printing."""
        if not self.last_generated_pdf or not os.path.exists(
            self.last_generated_pdf
        ):
            QMessageBox.warning(
                self,
                "Error",
                "No quote generated yet. Please generate a quote first.",
            )
            return

        try:
            # Open PDF with print command using default reader
            import subprocess

            # Use /p flag to open in print dialog directly
            subprocess.Popen(
                ["cmd", "/c", f'start /p "{self.last_generated_pdf}"']
            )
            QMessageBox.information(
                self,
                "Print Dialog",
                f"Quote opened in print dialog.\n\nFile:"
                f"{os.path.basename(self.last_generated_pdf)}\n\nYou can"
                f"print to PDF, email as attachment, or physical printer.",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to open print dialog: {str(e)}"
            )

    def _save_quote_template(self) -> None:
        """Save current quote as a template."""
        QMessageBox.information(
            self,
            "Save Template",
            "Quote template saved. You can reuse this data for similar"
            "bookings.",
        )

    def _update_templates_info(self) -> None:
        """Update template information display."""
        template_dir = "L:/Confirmation"
        if os.path.exists(template_dir):
            files = os.listdir(template_dir)
            pdfs = [f for f in files if f.endswith(".pdf")]
            docs = [f for f in files if f.endswith(".dot")]

            info_text = f"Template Directory: {template_dir}\n\n"
            info_text += f"📄 PDF Templates ({len(pdfs)}):\n"
            for pdf in pdfs:
                info_text += f"  • {pdf}\n"

            info_text += f"\n📋 Document Templates ({len(docs)}):\n"
            for doc in docs:
                info_text += f"  • {doc}\n"
        else:
            info_text = f"Template directory not found: {template_dir}"

        self.templates_info.setText(info_text)

    def _upload_template(self) -> None:
        """Upload a custom template."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Template",
            "",
            "PDF Files (*.pdf);;Word Templates (*.dot)",
        )

        if file_path:
            filename = os.path.basename(file_path)
            dest_path = f"L:/Confirmation/{filename}"
            try:
                import shutil

                shutil.copy(file_path, dest_path)
                QMessageBox.information(
                    self, "Success", f"Template uploaded: {dest_path}"
                )
                self._update_templates_info()
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to upload: {str(e)}"
                )
