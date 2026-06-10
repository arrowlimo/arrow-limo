"""
Simple Receipt Editor Dialog - Quick edit form for receipts
"""

from datetime import date as dateobj
from decimal import Decimal

import psycopg2
from common_widgets import StandardDateEdit
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)
from vendor_lookup_widget import VendorLookupWidget


class SimpleReceiptEditor(QDialog):
    """Simple popup editor for receipt details."""

    def __init__(
        self,
        conn: psycopg2.extensions.connection,
        receipt_id: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.receipt_id = receipt_id
        self.setWindowTitle(f"Edit Receipt #{receipt_id}")
        self.setGeometry(200, 100, 800, 700)
        self.setModal(True)

        self._build_ui()
        self._load_receipt()

    @staticmethod
    def _python_date_to_qdate(date_obj) -> object:
        """Convert Python date to QDate."""
        if isinstance(date_obj, QDate):
            return date_obj
        if isinstance(date_obj, dateobj):
            return QDate(date_obj.year, date_obj.month, date_obj.day)
        return None

    @staticmethod
    def _qdate_to_python_date(qdate) -> object:
        """Convert QDate to Python date."""
        if qdate is None or not qdate.isValid():
            return None
        return dateobj(qdate.year(), qdate.month(), qdate.day())

    def _build_ui(self) -> None:
        """Build the editor form."""
        layout = QVBoxLayout(self)

        # === BASIC INFO ===
        basic_group = QGroupBox("Basic Information")
        basic_form = QFormLayout(basic_group)

        self.receipt_date = StandardDateEdit(allow_blank=False)
        basic_form.addRow("Receipt Date:", self.receipt_date)

        self.vendor_name = VendorLookupWidget(self.conn)
        basic_form.addRow("Vendor Name:", self.vendor_name)

        self.description = QTextEdit()
        self.description.setMaximumHeight(80)
        basic_form.addRow("Description:", self.description)

        layout.addWidget(basic_group)

        # === AMOUNTS ===
        amounts_group = QGroupBox("Amounts")
        amounts_form = QFormLayout(amounts_group)

        self.gross_amount = QDoubleSpinBox()
        self.gross_amount.setRange(0, 999999.99)
        self.gross_amount.setPrefix("$")
        self.gross_amount.setDecimals(2)
        amounts_form.addRow("Gross Amount:", self.gross_amount)

        self.gst_amount = QDoubleSpinBox()
        self.gst_amount.setRange(0, 999999.99)
        self.gst_amount.setPrefix("$")
        self.gst_amount.setDecimals(2)
        amounts_form.addRow("GST Amount:", self.gst_amount)

        self.net_amount = QDoubleSpinBox()
        self.net_amount.setRange(0, 999999.99)
        self.net_amount.setPrefix("$")
        self.net_amount.setDecimals(2)
        amounts_form.addRow("Net Amount:", self.net_amount)

        self.fuel_amount = QDoubleSpinBox()
        self.fuel_amount.setRange(0, 999999.99)
        self.fuel_amount.setPrefix("$")
        self.fuel_amount.setDecimals(2)
        amounts_form.addRow("Fuel Amount:", self.fuel_amount)

        layout.addWidget(amounts_group)

        # === CATEGORIZATION ===
        cat_group = QGroupBox("Categorization")
        cat_form = QFormLayout(cat_group)

        self.gl_account_combo = QComboBox()
        self.gl_account_combo.setEditable(False)
        self.gl_account_combo.currentIndexChanged.connect(
            self._on_gl_code_changed
        )
        self._load_gl_accounts()
        cat_form.addRow("GL Account:", self.gl_account_combo)

        self.category_edit = QLineEdit()
        self.category_edit.textChanged.connect(self._on_category_changed)
        cat_form.addRow("Category:", self.category_edit)

        self.payment_method = QComboBox()
        self.payment_method.addItems(
            ["", "CASH", "CREDIT", "DEBIT", "CHEQUE", "TRANSFER", "OTHER"]
        )
        self.payment_method.setEditable(True)
        cat_form.addRow("Payment Method:", self.payment_method)

        layout.addWidget(cat_group)

        # === LINKS ===
        links_group = QGroupBox("Links & References")
        links_form = QFormLayout(links_group)

        self.charter_id = QLineEdit()
        links_form.addRow("Charter ID:", self.charter_id)

        self.vehicle_number = QLineEdit()
        self.vehicle_number_label = QLabel("Vehicle Number:")
        links_form.addRow(self.vehicle_number_label, self.vehicle_number)

        self.odometer_reading = QSpinBox()
        self.odometer_reading.setRange(0, 9999999)
        self.odometer_reading.setSpecialValueText("Not recorded")
        self.odometer_reading.setSuffix(" km")
        self.odometer_reading_label = QLabel("Odometer Reading:")
        links_form.addRow(self.odometer_reading_label, self.odometer_reading)

        self.employee_id = QLineEdit()
        links_form.addRow("Employee ID:", self.employee_id)

        self.banking_transaction_id = QLineEdit()
        links_form.addRow(
            "Banking Transaction ID:", self.banking_transaction_id
        )

        layout.addWidget(links_group)

        # === FLAGS ===
        flags_group = QGroupBox("Flags")
        flags_layout = QHBoxLayout(flags_group)

        self.business_personal = QCheckBox("Business/Personal")
        flags_layout.addWidget(self.business_personal)

        self.verified_by_edit = QCheckBox("Verified")
        flags_layout.addWidget(self.verified_by_edit)

        flags_layout.addStretch()
        layout.addWidget(flags_group)

        # === NOTES ===
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.comment = QTextEdit()
        self.comment.setMaximumHeight(60)
        notes_layout.addWidget(self.comment)
        layout.addWidget(notes_group)

        # === BUTTONS ===
        button_box = QDialogButtonBox()
        save_btn = button_box.addButton(
            "💾 Save", QDialogButtonBox.ButtonRole.AcceptRole
        )
        save_btn.clicked.connect(self._save_receipt)
        cancel_btn = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        cancel_btn.clicked.connect(self.reject)

        layout.addWidget(button_box)

    def _load_receipt(self) -> None:
        """Load receipt data from database."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT
                    receipt_date, vendor_name, description, gross_amount,
                    gst_amount, net_amount,
                    category, gl_account_code, gl_account_name, payment_method,
                    banking_transaction_id, charter_id, vehicle_number,
                    employee_id,
                    fuel_amount, business_personal, verified_by_edit, comment,
                    odometer_reading
                FROM receipts
                WHERE receipt_id = %s
            """,
                (self.receipt_id,),
            )

            row = cur.fetchone()
            cur.close()

            if not row:
                QMessageBox.warning(
                    self, "Not Found", f"Receipt #{self.receipt_id} not found."
                )
                self.reject()
                return

            # Populate fields
            if row[0]:
                # Convert Python date to QDate
                qdate = self._python_date_to_qdate(row[0])
                if qdate:
                    self.receipt_date.setDate(qdate)
            self.vendor_name.set_vendor(row[1] or "")
            self.description.setPlainText(row[2] or "")
            self.gross_amount.setValue(float(row[3] or 0))
            self.gst_amount.setValue(float(row[4] or 0))
            self.net_amount.setValue(float(row[5] or 0))
            self.category_edit.setText(row[6] or "")

            # Set GL account in combo
            gl_code = row[7] or ""
            if gl_code:
                # Find and select the GL code in combo
                for i in range(self.gl_account_combo.count()):
                    if self.gl_account_combo.itemData(i) == gl_code:
                        self.gl_account_combo.setCurrentIndex(i)
                        break

            self.payment_method.setCurrentText(row[9] or "")
            self.banking_transaction_id.setText(
                str(row[10]) if row[10] else ""
            )
            self.charter_id.setText(str(row[11]) if row[11] else "")
            self.vehicle_number.setText(row[12] or "")
            self.employee_id.setText(str(row[13]) if row[13] else "")
            self.fuel_amount.setValue(float(row[14] or 0))
            _bp = row[15]
            self.business_personal.setChecked(
                _bp
                if isinstance(_bp, bool)
                else (
                    (
                        str(_bp).lower()
                        not in ("false", "business", "no", "0", "")
                    )
                    if _bp
                    else False
                )
            )
            self.verified_by_edit.setChecked(
                bool(row[16]) if row[16] is not None else False
            )
            self.comment.setPlainText(row[17] or "")
            self.odometer_reading.setValue(int(row[18]) if row[18] else 0)

            # Update field requirements based on loaded data
            self._update_field_requirements()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load receipt:\n{e}"
            )
            import traceback

            traceback.print_exc()
            self.reject()

    def _load_gl_accounts(self) -> None:
        """Load GL accounts from chart_of_accounts into combo box."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT account_code, account_name, account_type
                FROM chart_of_accounts
                WHERE is_active = true
                  AND account_type IN ('Expense', 'COGS')
                ORDER BY account_code
            """)

            self.gl_account_combo.clear()
            self.gl_account_combo.addItem("-- Select GL Account --", "")

            for code, name, acct_type in cur.fetchall():
                display_text = f"{code} - {name}"
                self.gl_account_combo.addItem(display_text, code)

            cur.close()
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to load GL accounts:\n{e}"
            )

    def _on_gl_code_changed(self) -> None:
        """Handle GL code changes to update field requirements."""
        self._update_field_requirements()

    def _on_category_changed(self) -> None:
        """Handle category changes to update field requirements."""
        self._update_field_requirements()

    def _update_field_requirements(self) -> None:
        """Update field requirements based on GL code and category."""
        gl_code = self.gl_account_combo.currentData() or ""
        category = self.category_edit.text().strip().lower()

        # Check if this is a fuel receipt
        is_fuel = category == "fuel"

        # Check if this is a maintenance/repair receipt (GL codes 5100, 5120)
        is_maintenance = gl_code in ("5100", "5120")

        # Update visual indicators
        if is_fuel:
            self.vehicle_number_label.setText("Vehicle Number: *")
            self.vehicle_number_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )
            self.odometer_reading_label.setText("Odometer Reading:")
            self.odometer_reading_label.setStyleSheet("")
        elif is_maintenance:
            self.vehicle_number_label.setText("Vehicle Number: *")
            self.vehicle_number_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )
            self.odometer_reading_label.setText("Odometer Reading: *")
            self.odometer_reading_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )
        else:
            self.vehicle_number_label.setText("Vehicle Number:")
            self.vehicle_number_label.setStyleSheet("")
            self.odometer_reading_label.setText("Odometer Reading:")
            self.odometer_reading_label.setStyleSheet("")

    def _save_receipt(self) -> None:
        """Save changes to database."""
        try:
            # Validate required fields
            if not self.vendor_name.get_vendor().strip():
                QMessageBox.warning(
                    self, "Validation", "Vendor name is required."
                )
                return

            # Validate GL-code-specific requirements
            gl_code = self.gl_account_combo.currentData() or ""
            category = self.category_edit.text().strip().lower()

            # Fuel receipts require vehicle
            if category == "fuel" and not self.vehicle_number.text().strip():
                QMessageBox.warning(
                    self,
                    "Validation",
                    "Vehicle is required for fuel receipts.",
                )
                return

            # Maintenance receipts (GL 5100, 5120) require vehicle AND odometer
            if gl_code in ("5100", "5120"):
                if not self.vehicle_number.text().strip():
                    QMessageBox.warning(
                        self,
                        "Validation",
                        "Vehicle is required for maintenance/repair receipts"
                        "(GL 5100/5120).",
                    )
                    return
                if self.odometer_reading.value() == 0:
                    QMessageBox.warning(
                        self,
                        "Validation",
                        "Odometer reading is required for maintenance/repair"
                        "receipts (GL 5100/5120).",
                    )
                    return

            # Prepare data
            charter_id_val = (
                int(self.charter_id.text())
                if self.charter_id.text().strip()
                else None
            )
            employee_id_val = (
                int(self.employee_id.text())
                if self.employee_id.text().strip()
                else None
            )
            banking_id_val = (
                int(self.banking_transaction_id.text())
                if self.banking_transaction_id.text().strip()
                else None
            )

            # Convert QDate to Python date
            receipt_date = self._qdate_to_python_date(
                self.receipt_date.getDate()
            )

            cur = self.conn.cursor()
            # Prepare odometer value (0 = NULL)
            odometer_val = (
                self.odometer_reading.value()
                if self.odometer_reading.value() > 0
                else None
            )

            cur.execute(
                """
                UPDATE receipts SET
                    receipt_date = %s,
                    vendor_name = %s,
                    description = %s,
                    gross_amount = %s,
                    gst_amount = %s,
                    net_amount = %s,
                    category = %s,
                    gl_account_code = %s,
                    gl_account_name = %s,
                    payment_method = %s,
                    banking_transaction_id = %s,
                    charter_id = %s,
                    vehicle_number = %s,
                    employee_id = %s,
                    fuel_amount = %s,
                    business_personal = %s,
                    verified_by_edit = %s,
                    comment = %s,
                    odometer_reading = %s
                WHERE receipt_id = %s
            """,
                (
                    receipt_date,
                    self.vendor_name.get_vendor().strip(),
                    self.description.toPlainText().strip(),
                    Decimal(str(self.gross_amount.value())),
                    Decimal(str(self.gst_amount.value())),
                    Decimal(str(self.net_amount.value())),
                    self.category_edit.text().strip() or None,
                    self.gl_account_combo.currentData()
                    or None,  # GL code from combo
                    (
                        self.gl_account_combo.currentText().split(" - ", 1)[1]
                        if " - " in self.gl_account_combo.currentText()
                        else None
                    ),  # GL name
                    self.payment_method.currentText().strip() or None,
                    banking_id_val,
                    charter_id_val,
                    self.vehicle_number.text().strip() or None,
                    employee_id_val,
                    Decimal(str(self.fuel_amount.value())),
                    self.business_personal.isChecked(),
                    self.verified_by_edit.isChecked(),
                    self.comment.toPlainText().strip() or None,
                    odometer_val,
                    self.receipt_id,
                ),
            )

            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "Success",
                f"Receipt #{self.receipt_id} updated successfully!",
            )
            self.accept()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(
                self, "Error", f"Failed to save receipt:\n{e}"
            )
            import traceback

            traceback.print_exc()
