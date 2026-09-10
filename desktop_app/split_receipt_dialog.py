"""
Split Receipt Dialog - Divide receipts into multiple payments (2019-style)

Pattern: One physical receipt is divided into multiple logical receipts
with different payment methods (cash, debit, gift card, rebate, etc.)
and different GL codes (fuel, food, oil, etc.)

All split receipts share: SPLIT/<total_amount> tag in description
Only the first split keeps the banking link (if original has one)
"""

import logging
from decimal import Decimal

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class SplitReceiptDialog(QDialog):
    """Dialog to divide a receipt into multiple payment methods and GL codes"""

    def __init__(self, receipt_id, receipt_data, parent_conn, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Divide Receipt by Payment Methods")
        self.setGeometry(100, 100, 900, 600)
        self.setModal(True)

        self.receipt_id = receipt_id
        # (receipt_date, vendor_name, gross_amount, description, gst_amount,
        # gst_code, sales_tax, tax_category, banking_transaction_id)
        self.receipt_data = receipt_data
        self.conn = parent_conn

        self.splits = []  # List of {amount, gl_code, payment_method, memo}

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)

        # Header with receipt info
        header = QGroupBox("Original Receipt")
        header_layout = QFormLayout()

        (
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            _gst_amount,
            gst_code,
            _sales_tax,
            _tax_category,
            banking_id,
        ) = self.receipt_data

        header_layout.addRow("Vendor:", QLabel(vendor_name or "Unknown"))
        header_layout.addRow("Amount:", QLabel(f"${gross_amount:,.2f}"))
        header_layout.addRow("Date:", QLabel(str(receipt_date)))
        header_layout.addRow(
            "Description:", QLabel(description or "(no description)")
        )
        header_layout.addRow(
            "Banking Link:",
            QLabel(f"ID {banking_id}" if banking_id else "No banking link"),
        )
        header_layout.addRow("GST Code:", QLabel(gst_code or "None"))

        header.setLayout(header_layout)
        layout.addWidget(header)

        # Number of splits selector
        split_selector = QHBoxLayout()
        split_selector.addWidget(QLabel("How many splits?"))

        self.split_count_spin = QSpinBox()
        self.split_count_spin.setMinimum(2)
        self.split_count_spin.setMaximum(10)
        self.split_count_spin.setValue(2)
        self.split_count_spin.valueChanged.connect(
            self._on_split_count_changed
        )
        split_selector.addWidget(self.split_count_spin)
        split_selector.addStretch()

        layout.addLayout(split_selector)

        # Splits table
        self.splits_table = QTableWidget(2, 5)
        self.splits_table.setHorizontalHeaderLabels(
            ["Amount", "GL Code", "Payment Method", "GST Treatment", "Memo"]
        )
        self.splits_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.splits_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.splits_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.splits_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.splits_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )

        # Populate initial rows
        self._populate_table()

        layout.addWidget(self.splits_table)

        # Total and validation row
        total_frame = QFrame()
        total_layout = QHBoxLayout(total_frame)
        total_layout.addWidget(QLabel("Total Entered:"))

        self.total_label = QLabel("$0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        total_layout.addWidget(self.total_label)

        total_layout.addWidget(QLabel(f"Target: ${gross_amount:,.2f}"))

        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: red; font-weight: bold;")
        total_layout.addWidget(self.validation_label)
        total_layout.addStretch()

        layout.addWidget(total_frame)

        # Buttons
        button_layout = QHBoxLayout()

        self.create_btn = QPushButton("✅ Create Splits")
        self.create_btn.clicked.connect(self._create_splits)
        self.create_btn.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold;"
        )
        button_layout.addWidget(self.create_btn)

        cancel_btn = QPushButton("✖️ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect cell changes to validation
        self.splits_table.itemChanged.connect(self._on_table_changed)

    def _populate_table(self) -> None:
        """Populate the splits table with editable cells"""
        count = self.split_count_spin.value()
        self.splits_table.setRowCount(count)

        self.receipt_data[2]
        self.receipt_data[5]

        # Get GL codes from database
        gl_codes = self._get_gl_codes()
        payment_methods = [
            "Debit",
            "Cash",
            "Check",
            "Credit Card",
            "Bank Transfer",
            "Gift Card",
            "Rebate",
            "Float",
        ]

        for row in range(count):
            # Amount (QLineEdit for currency)
            amount_input = QLineEdit()
            amount_input.setText("0.00")
            amount_input.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.splits_table.setCellWidget(row, 0, amount_input)

            # GL Code (QComboBox) - with fuzzy search
            gl_combo = QComboBox()
            gl_combo.setEditable(True)
            gl_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            gl_combo.addItem("-- Select GL Code --", "")

            # Build GL items list and populate combo with BOTH text and data
            gl_items = []
            for code, name in gl_codes:
                display_text = f"{code} - {name}"
                gl_items.append(display_text)
                # Set both display text AND data (code) for proper matching
                gl_combo.addItem(display_text, code)

            # Add fuzzy/contains autocomplete
            completer = QCompleter(gl_items)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            gl_combo.setCompleter(completer)

            self.splits_table.setCellWidget(row, 1, gl_combo)

            # Payment Method (QComboBox)
            payment_combo = QComboBox()
            payment_combo.addItems(payment_methods)
            if row == 0:
                payment_combo.setCurrentText("Debit")
            else:
                payment_combo.setCurrentText("Cash")
            self.splits_table.setCellWidget(row, 2, payment_combo)

            gst_combo = QComboBox()
            gst_combo.addItems(["Included", "Added", "None"])
            self.splits_table.setCellWidget(row, 3, gst_combo)

            # Memo (QLineEdit)
            memo_input = QLineEdit()
            memo_input.setPlaceholderText("e.g., Fuel, Food, Smokes, Rebate")
            self.splits_table.setCellWidget(row, 4, memo_input)

    def _on_split_count_changed(self, value) -> None:
        """Handle change in split count"""
        self._populate_table()
        self._on_table_changed()

    def _get_gl_codes(self) -> object:
        """Get available GL codes from chart_of_accounts ONLY (active,"
        "non-header accounts)."""

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    SELECT account_code, account_name, parent_account
                    FROM chart_of_accounts
                    WHERE account_code IS NOT NULL
                      AND account_code != ''
                      AND is_active = true
                      AND (is_header_account IS NULL OR is_header_account =
                      false)
                    ORDER BY account_code
                """)
                codes = cur.fetchall()
                if codes:
                    # Return tuples of (code, name) - ignore parent for now
                    return [(code, name) for code, name, parent in codes]
                else:
                    return [
                        ("5110", "Vehicle Fuel"),
                        ("5100", "Other Expense"),
                    ]
        except Exception as e:
            logger.error(f"Failed to load GL codes: {e}")
            return [("5110", "Vehicle Fuel"), ("5100", "Other Expense")]

    def _on_table_changed(self) -> None:
        """Handle changes to table cells - validate totals"""
        gross_amount = float(self.receipt_data[2])
        self.receipt_data[5]

        total = 0.0
        split_data = []

        for row in range(self.splits_table.rowCount()):
            # Get amount
            amount_widget = self.splits_table.cellWidget(row, 0)
            if isinstance(amount_widget, QLineEdit):
                try:
                    amount = float(amount_widget.text() or "0")
                except Exception:
                    amount = 0.0
            else:
                amount = 0.0

            # Get GL code
            gl_widget = self.splits_table.cellWidget(row, 1)
            gl_text = (
                gl_widget.currentText()
                if isinstance(gl_widget, QComboBox)
                else ""
            )
            gl_code = gl_text.split(" - ")[0] if " - " in gl_text else ""

            # Get payment method
            payment_widget = self.splits_table.cellWidget(row, 2)
            payment_method = (
                payment_widget.currentText()
                if isinstance(payment_widget, QComboBox)
                else ""
            )
            payment_method = {
                "debit": "debit_card",
                "credit card": "credit_card",
                "bank transfer": "bank_transfer",
                "check": "check",
                "cash": "cash",
                "gift card": "credit_adjustment",
                "rebate": "credit_adjustment",
                "float": "cash",
            }.get(payment_method.lower(), payment_method.lower())

            gst_widget = self.splits_table.cellWidget(row, 3)
            gst_treatment = (
                gst_widget.currentText()
                if isinstance(gst_widget, QComboBox)
                else "Included"
            )

            # Get memo
            memo_widget = self.splits_table.cellWidget(row, 4)
            memo = (
                memo_widget.text()
                if isinstance(memo_widget, QLineEdit)
                else ""
            )

            gst_amount = (
                amount * 0.05 / 1.05
                if gst_treatment == "Included"
                else amount * 0.05
                if gst_treatment == "Added"
                else 0.0
            )
            effect = amount + gst_amount if gst_treatment == "Added" else amount
            total += effect
            split_data.append(
                {
                    "amount": amount,
                    "gst_treatment": gst_treatment,
                    "gst_amount": gst_amount,
                    "gl_code": gl_code,
                    "payment_method": payment_method.lower(),
                    "memo": memo,
                }
            )

        self.splits = split_data

        # Update total label
        self.total_label.setText(f"${total:,.2f}")

        # Validate
        diff = abs(total - gross_amount)
        if diff < 0.01:
            self.validation_label.setText("✅ Totals match!")
            self.validation_label.setStyleSheet(
                "color: green; font-weight: bold;"
            )
            self.create_btn.setEnabled(True)
        else:
            self.validation_label.setText(f"⚠️ Difference: ${diff:,.2f}")
            self.validation_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )
            self.create_btn.setEnabled(False)

    def _create_splits(self) -> None:
        """Create the split receipts in the database"""
        if not self.splits or len(self.splits) < 2:
            QMessageBox.warning(
                self, "No Splits", "Please configure at least 2 splits."
            )
            return

        (
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            _gst_amount,
            _gst_code,
            _sales_tax,
            tax_category,
            banking_id,
        ) = self.receipt_data

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                # Generate split tag
                split_tag = f"SPLIT/{gross_amount:.2f}"

                new_receipt_ids = []

                for idx, split in enumerate(self.splits):
                    amount = split["amount"]
                    gl_code = split["gl_code"]
                    payment_method = split["payment_method"]
                    memo = split["memo"]

                    gst_treatment = split.get("gst_treatment", "Included")
                    if gst_treatment == "Included":
                        line_gst = amount * Decimal("0.05") / Decimal("1.05")
                        stored_amount = amount
                        stored_gst_code = "GST_INCL_5"
                    elif gst_treatment == "Added":
                        line_gst = amount * Decimal("0.05")
                        stored_amount = amount + line_gst
                        stored_gst_code = "GST_INCL_5"
                    else:
                        line_gst = Decimal("0")
                        stored_amount = amount
                        stored_gst_code = "GST_EXEMPT"

                    # Build description
                    if memo:
                        full_desc = f"{description} | {memo} | {split_tag}"
                    else:
                        full_desc = f"{description} | {split_tag}"

                    # Only link first split to banking
                    link_banking = banking_id if idx == 0 else None

                    # Keep the original row for the first split so its
                    # banking and receipt links survive the split.
                    insert_sql = """
                        INSERT INTO receipts (
                            receipt_date, vendor_name, canonical_vendor,
                            gross_amount,
                            gst_amount, gst_code, sales_tax, tax_category,
                            description, category, source_reference,
                            payment_method,
                            banking_transaction_id, is_driver_reimbursement,
                            vehicle_id,
                            gl_account_code, gl_account_name,
                            owner_personal_amount, fuel_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s)
                        RETURNING receipt_id
                    """

                    # Get GL name from code
                    gl_name = self._get_gl_name(gl_code)

                    params = (
                        receipt_date,  # receipt_date
                        vendor_name,  # vendor_name
                        vendor_name,  # canonical_vendor
                        stored_amount,  # gross_amount
                        line_gst,  # gst_amount
                        stored_gst_code,  # gst_code
                        0.0,  # sales_tax (PST)
                        tax_category,  # tax_category
                        full_desc,  # description
                        None,  # category
                        None,  # source_reference
                        payment_method,  # payment_method
                        link_banking,  # banking_transaction_id
                        False,  # is_driver_reimbursement
                        None,  # vehicle_id
                        gl_code,  # gl_account_code
                        gl_name,  # gl_account_name
                        None,  # owner_personal_amount
                        None,  # fuel_amount
                    )

                    if idx == 0:
                        cur.execute(
                            """
                            UPDATE receipts
                               SET gross_amount = %s,
                                   gst_amount = %s,
                                   gst_code = %s,
                                   sales_tax = %s,
                                   tax_category = %s,
                                   description = %s,
                                   payment_method = %s,
                                   gl_account_code = %s,
                                   gl_account_name = %s,
                                   fuel_amount = %s,
                                   is_split_receipt = TRUE,
                                   split_status = 'split_reconciled',
                                   split_key = %s,
                                   split_group_total = %s,
                                   updated_at = NOW()
                             WHERE receipt_id = %s
                            """,
                            (
                                stored_amount,
                                line_gst,
                                stored_gst_code,
                                0.0,
                                tax_category,
                                full_desc,
                                payment_method,
                                gl_code,
                                gl_name,
                                None,
                                split_tag,
                                gross_amount,
                                self.receipt_id,
                            ),
                        )
                        new_receipt_id = self.receipt_id
                    else:
                        cur.execute(insert_sql, params)
                        new_receipt_id = cur.fetchone()[0]
                        cur.execute(
                            """
                            UPDATE receipts
                               SET is_split_receipt = TRUE,
                                   split_status = 'split_reconciled',
                                   split_key = %s,
                                   split_group_total = %s,
                                   parent_receipt_id = %s
                             WHERE receipt_id = %s
                            """,
                            (split_tag, gross_amount, self.receipt_id, new_receipt_id),
                        )
                    new_receipt_ids.append(new_receipt_id)

                    # Create banking ledger entry only for first split (if
                    # banking link exists)
                    if link_banking:
                        cur.execute(
                            """
                            INSERT INTO banking_receipt_matching_ledger (
                                banking_transaction_id, receipt_id, match_date,
                                match_type,
                                match_status, match_confidence, notes,
                                created_by)
                            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
                        """,
                            (
                                link_banking,
                                new_receipt_id,
                                "split_first",
                                "linked",
                                0.95,
                                f"First split of {split_tag}",
                                "desktop_app_divide",
                            ),
                        )

            # Show success message
            msg = f"✅ Created {len(new_receipt_ids)} split receipts:\n\n"
            for i, rid in enumerate(new_receipt_ids, 1):
                split_amount = self.splits[i - 1]["amount"]
                split_method = self.splits[i - 1]["payment_method"]
                msg += f"  {i}. Receipt #{rid}: ${split_amount:,.2f}  ({split_method})\n"
            msg += f"\nAll tagged with: {split_tag}\n"
            msg += f"Banking link: Receipt #{new_receipt_ids[0]} only"

            QMessageBox.information(self, "✅ Success", msg)
            self.accept()

        except Exception as e:
            logger.error(f"Failed to create splits: {e}")
            QMessageBox.critical(
                self, "Creation Error", f"Failed to create splits:\n\n{e}"
            )

    def _get_gl_name(self, gl_code) -> object:
        """Get GL account name from code"""
        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(
                    "SELECT account_name FROM chart_of_accounts "
                    "WHERE account_code = %s",
                    (gl_code,),
                )
                result = cur.fetchone()
                return result[0] if result else gl_code
        except Exception as e:
            logger.error(f"Failed to get GL name: {e}")
            return gl_code
