"""
GST Remittance Manager
Desktop UI for tracking GST payments to CRA with support for:
- Manual payment entry (payments made at other banks)
- Multi-bank payment tracking
- Banking transaction linkage
- Remittance status and audit trail
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class GSTRemittanceDialog(QDialog):
    """Dialog for creating/editing GST remittance payments"""

    saved = pyqtSignal()

    def __init__(self, parent=None, tax_year=None, gst_period_month=None, payment_data=None):
        super().__init__(parent)
        self.tax_year = tax_year or datetime.now().year
        self.gst_period_month = gst_period_month or datetime.now().month
        self.payment_data = payment_data or {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(
            f"GST Remittance Payment - {self.tax_year}/{self.gst_period_month:02d}"
        )
        self.setMinimumWidth(500)

        layout = QFormLayout()

        # Tax Year and Period (read-only if editing)
        self.year_label = QLabel(str(self.tax_year))
        self.month_label = QLabel(f"{self.gst_period_month:02d}")
        layout.addRow("Tax Year:", self.year_label)
        layout.addRow("GST Period Month:", self.month_label)

        # GST Amount Collected
        self.gst_collected_input = QDoubleSpinBox()
        self.gst_collected_input.setRange(0, 999999.99)
        self.gst_collected_input.setDecimals(2)
        self.gst_collected_input.setValue(
            float(self.payment_data.get("gst_amount_collected", 0))
        )
        layout.addRow("GST Amount Collected:", self.gst_collected_input)

        # Payment Amount
        self.payment_amount_input = QDoubleSpinBox()
        self.payment_amount_input.setRange(0, 999999.99)
        self.payment_amount_input.setDecimals(2)
        self.payment_amount_input.setValue(
            float(self.payment_data.get("payment_amount", 0))
        )
        layout.addRow("Payment Amount to CRA:", self.payment_amount_input)

        # Payment Date
        self.payment_date_input = QDateEdit()
        self.payment_date_input.setCalendarPopup(True)
        payment_date = self.payment_data.get("payment_date")
        if payment_date:
            if isinstance(payment_date, str):
                self.payment_date_input.setDate(datetime.fromisoformat(payment_date).date())
            else:
                self.payment_date_input.setDate(payment_date)
        else:
            self.payment_date_input.setDate(date.today())
        layout.addRow("Payment Date:", self.payment_date_input)

        # Payment Method
        self.payment_method_input = QComboBox()
        self.payment_method_input.addItems(
            [
                "manual_entry",
                "banking_transaction",
                "forced_debit",
            ]
        )
        current_method = self.payment_data.get("payment_method", "manual_entry")
        self.payment_method_input.setCurrentText(current_method)
        layout.addRow("Payment Method:", self.payment_method_input)

        # Banking Institution (for multi-bank tracking)
        self.banking_inst_input = QLineEdit()
        self.banking_inst_input.setPlaceholderText("e.g., RBC, TD, BMO, CIBC")
        self.banking_inst_input.setText(self.payment_data.get("banking_institution", ""))
        layout.addRow("Banking Institution:", self.banking_inst_input)

        # Reference Number (CRA confirmation, cheque#, wire reference)
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText(
            "CRA confirmation #, cheque #, wire reference, etc."
        )
        self.reference_input.setText(self.payment_data.get("reference_number", ""))
        layout.addRow("Reference Number:", self.reference_input)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(100)
        self.notes_input.setPlainText(self.payment_data.get("notes", ""))
        layout.addRow("Notes:", self.notes_input)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_payment)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setLayout(layout)

    def save_payment(self):
        try:
            payment_data = {
                "tax_year": self.tax_year,
                "gst_period_month": self.gst_period_month,
                "gst_amount_collected": self.gst_collected_input.value(),
                "payment_amount": self.payment_amount_input.value(),
                "payment_date": self.payment_date_input.date().toPyDate(),
                "payment_method": self.payment_method_input.currentText(),
                "banking_institution": self.banking_inst_input.text() or None,
                "reference_number": self.reference_input.text() or None,
                "notes": self.notes_input.toPlainText() or None,
            }

            with DatabaseContext() as db:
                cur = db.cursor()
                retained_until = date(self.tax_year, 12, 31)
                # Add 6 years for CRA record retention (Income Tax Act Section 230)
                from datetime import timedelta

                retained_until = retained_until + timedelta(days=365 * 6)

                # Check if record exists
                cur.execute(
                    """
                    SELECT gst_payment_id FROM gst_remittance_payments
                    WHERE tax_year = %s AND gst_period_month = %s
                    """,
                    (self.tax_year, self.gst_period_month),
                )
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        """
                        UPDATE gst_remittance_payments
                        SET gst_amount_collected = %s,
                            payment_amount = %s,
                            payment_date = %s,
                            payment_method = %s,
                            banking_institution = %s,
                            reference_number = %s,
                            notes = %s,
                            updated_at = NOW()
                        WHERE tax_year = %s AND gst_period_month = %s
                        """,
                        (
                            payment_data["gst_amount_collected"],
                            payment_data["payment_amount"],
                            payment_data["payment_date"],
                            payment_data["payment_method"],
                            payment_data["banking_institution"],
                            payment_data["reference_number"],
                            payment_data["notes"],
                            self.tax_year,
                            self.gst_period_month,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO gst_remittance_payments
                        (tax_year, gst_period_month, gst_amount_collected, payment_amount,
                         payment_date, payment_method, banking_institution, reference_number,
                         notes, retained_until, remittance_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                        """,
                        (
                            self.tax_year,
                            self.gst_period_month,
                            payment_data["gst_amount_collected"],
                            payment_data["payment_amount"],
                            payment_data["payment_date"],
                            payment_data["payment_method"],
                            payment_data["banking_institution"],
                            payment_data["reference_number"],
                            payment_data["notes"],
                            retained_until,
                        ),
                    )

                db.commit()
                self.saved.emit()
                self.accept()

        except Exception as e:
            logger.error(f"Error saving GST remittance payment: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save GST remittance payment: {e}",
            )


class GSTRemittanceManager(QWidget):
    """Main widget for managing GST remittance payments"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_payments()

    def init_ui(self):
        layout = QVBoxLayout()

        # Controls
        button_layout = QVBoxLayout()
        add_btn = QPushButton("Add Payment")
        add_btn.clicked.connect(self.add_payment)
        button_layout.addWidget(add_btn)
        layout.addLayout(button_layout)

        # Payments table
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(9)
        self.payments_table.setHorizontalHeaderLabels(
            [
                "Tax Year",
                "Period",
                "GST Collected",
                "Payment Amount",
                "Payment Date",
                "Method",
                "Institution",
                "Reference #",
                "Status",
            ]
        )
        self.payments_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.payments_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.payments_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.payments_table.itemDoubleClicked.connect(self.edit_payment)

        layout.addWidget(self.payments_table)

        self.setLayout(layout)

    def load_payments(self):
        """Load GST remittance payments from database"""
        try:
            with DatabaseContext() as db:
                cur = db.cursor()
                cur.execute(
                    """
                    SELECT gst_payment_id, tax_year, gst_period_month, 
                           gst_amount_collected, payment_amount, payment_date,
                           payment_method, banking_institution, reference_number,
                           remittance_status
                    FROM gst_remittance_payments
                    ORDER BY tax_year DESC, gst_period_month DESC
                    """
                )
                rows = cur.fetchall()

                self.payments_table.setRowCount(len(rows))
                for row_idx, row in enumerate(rows):
                    items = [
                        str(row[1]),  # tax_year
                        f"{row[2]:02d}",  # period
                        f"${row[3]:,.2f}",  # gst_collected
                        f"${row[4]:,.2f}",  # payment_amount
                        str(row[5]),  # payment_date
                        row[6],  # payment_method
                        row[7] or "",  # banking_institution
                        row[8] or "",  # reference_number
                        row[9],  # remittance_status
                    ]
                    for col_idx, item_text in enumerate(items):
                        table_item = QTableWidgetItem(item_text)
                        if col_idx == 1:  # payment_date
                            table_item.setData(Qt.ItemDataRole.UserRole, row[5])
                        self.payments_table.setItem(row_idx, col_idx, table_item)

        except Exception as e:
            logger.error(f"Error loading GST remittance payments: {e}")
            QMessageBox.warning(
                self,
                "Load Error",
                f"Failed to load GST remittance payments: {e}",
            )

    def add_payment(self):
        """Add new GST remittance payment"""
        dialog = GSTRemittanceDialog(self)
        dialog.saved.connect(self.load_payments)
        dialog.exec()

    def edit_payment(self, item):
        """Edit selected GST remittance payment"""
        row = self.payments_table.row(item)
        tax_year_text = self.payments_table.item(row, 0).text()
        period_text = self.payments_table.item(row, 1).text()

        try:
            tax_year = int(tax_year_text)
            gst_period_month = int(period_text)

            with DatabaseContext() as db:
                cur = db.cursor()
                cur.execute(
                    """
                    SELECT tax_year, gst_period_month, gst_amount_collected,
                           payment_amount, payment_date, payment_method,
                           banking_institution, reference_number, notes
                    FROM gst_remittance_payments
                    WHERE tax_year = %s AND gst_period_month = %s
                    """,
                    (tax_year, gst_period_month),
                )
                row_data = cur.fetchone()

                if row_data:
                    payment_data = {
                        "gst_amount_collected": row_data[2],
                        "payment_amount": row_data[3],
                        "payment_date": row_data[4],
                        "payment_method": row_data[5],
                        "banking_institution": row_data[6],
                        "reference_number": row_data[7],
                        "notes": row_data[8],
                    }

                    dialog = GSTRemittanceDialog(
                        self,
                        tax_year=tax_year,
                        gst_period_month=gst_period_month,
                        payment_data=payment_data,
                    )
                    dialog.saved.connect(self.load_payments)
                    dialog.exec()

        except Exception as e:
            logger.error(f"Error editing GST remittance payment: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to edit GST remittance payment: {e}",
            )
