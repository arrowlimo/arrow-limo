"""
Split Receipt Manager Widget - CRA audit-compliant split receipt allocation UI
Shows side-by-side splits with real-time validation and bank/cashbox
reconciliation
"""

import logging

import psycopg2
from banking_transaction_picker_dialog import (
    BankingTransactionPickerDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class SplitReceiptManagerDialog(QDialog):
    """Popup dialog for managing receipt splits with real-time validation."""

    splits_saved = pyqtSignal(int)  # receipt_id

    def __init__(
        self,
        conn: psycopg2.extensions.connection,
        receipt_id: int,
        receipt_data: dict = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.receipt_id = receipt_id
        self.setWindowTitle(f"Split Receipt Manager - Receipt #{receipt_id}")
        self.setGeometry(100, 100, 1400, 800)
        self.setModal(True)

        # Use provided receipt_data or load it
        if receipt_data:
            self.receipt_data = self._normalize_receipt_data(receipt_data)
        else:
            self.receipt_data = self._normalize_receipt_data(
                self._load_receipt()
            )

        if not self.receipt_data:
            QMessageBox.critical(
                self, "Error", f"Receipt #{receipt_id} not found"
            )
            self.reject()
            return

        try:
            self._build_ui()
            self._load_splits()
        except Exception as e:
            logger.exception("Error building split manager UI")
            QMessageBox.critical(
                self, "Error", f"Failed to initialize split manager: {e}"
            )
            self.reject()

    def _normalize_receipt_data(
        self, receipt_data: dict | None
    ) -> dict | None:
        """Normalize receipt payload so dialog accepts legacy and new key"
        "shapes."""

        if not receipt_data:
            return None

        normalized = dict(receipt_data)

        normalized["date"] = normalized.get(
            "date", normalized.get("receipt_date")
        )
        normalized["vendor"] = normalized.get(
            "vendor", normalized.get("vendor_name", "")
        )
        normalized["desc"] = normalized.get(
            "desc", normalized.get("description", "")
        )

        amount_value = normalized.get("amount", normalized.get("gross_amount"))
        try:
            normalized["amount"] = float(amount_value)
        except (TypeError, ValueError):
            normalized["amount"] = 0.0

        return normalized

    def _load_receipt(self) -> dict:
        """Load receipt details."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       payment_method, description
                FROM receipts WHERE receipt_id = %s
            """,
                (self.receipt_id,),
            )
            row = cur.fetchone()
            cur.close()
            if row:
                return {
                    "id": row[0],
                    "date": row[1],
                    "vendor": row[2],
                    "amount": row[3],
                    "payment_method": row[4],
                    "desc": row[5],
                }
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Error loading receipt: %s", e)
        return None

    def _build_ui(self) -> None:
        """Build the UI."""
        layout = QVBoxLayout(self)

        # Header: Receipt info + totals
        header_group = self._build_header()
        layout.addWidget(header_group)

        # Tabs: Splits | Banking | CashBox
        tabs = QTabWidget()
        tabs.addTab(self._build_splits_tab(), "GL Splits")
        tabs.addTab(self._build_banking_tab(), "Bank Match")
        tabs.addTab(self._build_cashbox_tab(), "Cash Box")
        layout.addWidget(tabs)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_split_btn = QPushButton("Save This Split")
        save_split_btn.clicked.connect(self._save_single_split)
        btn_row.addWidget(save_split_btn)

        save_all_btn = QPushButton("✅ Save All & Reconcile")
        save_all_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        save_all_btn.clicked.connect(self._save_all_splits)
        btn_row.addWidget(save_all_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _build_header(self) -> QGroupBox:
        """Build receipt header with totals."""
        group = QGroupBox("Receipt Details & Reconciliation Status")
        form = QFormLayout(group)

        # Receipt info
        form.addRow("Receipt #:", QLabel(str(self.receipt_id)))
        form.addRow("Date:", QLabel(str(self.receipt_data["date"])))
        form.addRow("Vendor:", QLabel(self.receipt_data["vendor"]))

        # Amount display (large font)
        amt_label = QLabel(f"${self.receipt_data['amount']:.2f}")
        amt_font = QFont()
        amt_font.setPointSize(14)
        amt_font.setBold(True)
        amt_label.setFont(amt_font)
        form.addRow("Receipt Total:", amt_label)

        # Validation status - will update dynamically
        self.bank_match_label = QLabel("🔴 Not Matched")
        self.cashbox_match_label = QLabel("🔴 No Cash Entry")
        form.addRow("Bank Match:", self.bank_match_label)
        form.addRow("Cash Box:", self.cashbox_match_label)

        return group

    def _build_splits_tab(self) -> QWidget:
        """Build GL splits allocation tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "Allocate receipt to GL codes. Amounts must sum to receipt total."
            "✅ = valid"
        )
        layout.addWidget(info)

        # Splits table
        self.splits_table = QTableWidget()
        self.splits_table.setColumnCount(7)
        self.splits_table.setHorizontalHeaderLabels(
            [
                "GL Code",
                "Amount",
                "Payment Method",
                "Bus/Personal",
                "Reimb?",
                "Notes",
                "Actions",
            ]
        )
        self.splits_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.splits_table)

        # Add split button
        add_btn = QPushButton("➕ Add Split")
        add_btn.clicked.connect(self._add_split_row)
        layout.addWidget(add_btn)

        # Validation message
        self.splits_validation_label = QLabel(
            "🔴 Splits do not sum to receipt total"
        )
        self.splits_validation_label.setStyleSheet(
            "color: red; font-weight: bold;"
        )
        layout.addWidget(self.splits_validation_label)

        return widget

    def _build_banking_tab(self) -> QWidget:
        """Build banking transaction linking tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "Link receipt to banking transactions. Total must match receipt"
            "amount."
        )
        layout.addWidget(info)

        # Banking links table
        self.banking_table = QTableWidget()
        self.banking_table.setColumnCount(5)
        self.banking_table.setHorizontalHeaderLabels(
            ["Transaction Date", "Description", "Amount", "Status", "Actions"]
        )
        self.banking_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.banking_table)

        # Link banking button
        link_btn = QPushButton("🔗 Link Banking Transaction")
        link_btn.clicked.connect(self._link_banking)
        layout.addWidget(link_btn)

        # Validation
        self.banking_validation_label = QLabel("🔴 Not matched to banking")
        self.banking_validation_label.setStyleSheet(
            "color: red; font-weight: bold;"
        )
        layout.addWidget(self.banking_validation_label)

        return widget

    def _build_cashbox_tab(self) -> QWidget:
        """Build cash box tracking tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "Track cash portions. Driver name required for"
            "float/reimbursement entries."
        )
        layout.addWidget(info)

        form = QFormLayout()

        # Cash amount
        form.addRow(
            "Cash Amount:", QLabel(f"${self.receipt_data['amount']:.2f}")
        )

        # Driver dropdown
        self.cashbox_driver = QComboBox()
        self._load_drivers_for_cashbox()
        form.addRow("Driver:", self.cashbox_driver)

        # Float/Reimbursement type
        self.cashbox_type = QComboBox()
        self.cashbox_type.addItems(
            ["float_out", "reimbursed", "cash_received", "other"]
        )
        form.addRow("Type:", self.cashbox_type)

        # Notes
        self.cashbox_notes = QLineEdit()
        self.cashbox_notes.setPlaceholderText(
            "Driver notes, float purpose, etc."
        )
        form.addRow("Notes:", self.cashbox_notes)

        layout.addLayout(form)

        # Confirmation checkbox
        self.cashbox_confirmed = QCheckBox("Confirmed - Driver signed off")
        layout.addWidget(self.cashbox_confirmed)

        # Validation
        self.cashbox_validation_label = QLabel("🔴 Cash not confirmed")
        self.cashbox_validation_label.setStyleSheet(
            "color: red; font-weight: bold;"
        )
        layout.addWidget(self.cashbox_validation_label)

        layout.addStretch()
        return widget

    def _load_splits(self) -> None:
        """Load existing splits from database, or auto-create 2 empty rows."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT split_id, split_order, gl_code, amount, payment_method,
                notes,
                       business_personal, reimbursed
                FROM receipt_gl_splits
                WHERE receipt_id = %s
                ORDER BY split_order
            """,
                (self.receipt_id,),
            )
            rows = cur.fetchall()
            cur.close()

            if rows:
                # Load existing splits - recreate rows using same widgets as
                # new splits
                self.splits_table.setRowCount(0)  # Clear first
                for row_data in rows:
                    split_id, order, gl, amt, method, notes = row_data[:6]
                    row = self.splits_table.rowCount()
                    self.splits_table.insertRow(row)

                    # Column 0: GL Code (dropdown)
                    gl_combo = QComboBox()
                    gl_combo.setEditable(True)
                    gl_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                    gl_codes = self._get_gl_codes()

                    # Populate combo with BOTH text and data
                    for gl_text in gl_codes:
                        # Extract code from "5110 - Vehicle Fuel" format
                        gl_code = (
                            gl_text.split(" - ")[0].strip()
                            if " - " in gl_text
                            else gl_text
                        )
                        gl_combo.addItem(gl_text, gl_code)

                    # Set the current GL code
                    if gl:
                        for i in range(gl_combo.count()):
                            if gl_combo.itemText(i).startswith(str(gl)):
                                gl_combo.setCurrentIndex(i)
                                break
                    self.splits_table.setCellWidget(row, 0, gl_combo)

                    # Column 1: Amount (spinbox)
                    amount_spin = QDoubleSpinBox()
                    amount_spin.setMaximum(999999.99)
                    amount_spin.setDecimals(2)
                    amount_spin.setPrefix("$")
                    amount_spin.setValue(float(amt) if amt else 0.00)
                    amount_spin.valueChanged.connect(self._on_amount_changed)
                    self.splits_table.setCellWidget(row, 1, amount_spin)

                    # Column 2: Payment Method (dropdown)
                    method_combo = QComboBox()
                    payment_methods = [
                        "cash",
                        "check",
                        "debit/credit_card",
                        "bank_transfer",
                        "etransfer",
                        "gift_card",
                        "personal",
                        "trade_of_services",
                        "unknown",
                    ]
                    method_combo.addItems(payment_methods)
                    if method:
                        if method in ("debit_card", "credit_card"):
                            method = "debit/credit_card"
                        if method_combo.findText(method) >= 0:
                            method_combo.setCurrentText(method)
                    self.splits_table.setCellWidget(row, 2, method_combo)

                    # Column 3: Business/Personal
                    bp_combo = QComboBox()
                    bp_combo.addItems(["Business", "Personal", "NEEDS_REVIEW"])
                    row_bp = row_data[6] if len(row_data) > 6 else "Business"
                    bp_combo.setCurrentText(row_bp or "Business")
                    self.splits_table.setCellWidget(row, 3, bp_combo)

                    # Column 4: Reimbursed checkbox
                    reimb_widget = QWidget()
                    reimb_layout = QHBoxLayout(reimb_widget)
                    reimb_layout.setContentsMargins(4, 0, 4, 0)
                    reimb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    reimb_chk = QCheckBox()
                    row_reimb = row_data[7] if len(row_data) > 7 else False
                    reimb_chk.setChecked(bool(row_reimb))
                    reimb_chk.setToolTip(
                        "Driver paid and was reimbursed by company"
                    )
                    reimb_layout.addWidget(reimb_chk)
                    self.splits_table.setCellWidget(row, 4, reimb_widget)

                    # Column 5: Notes (text field)
                    self.splits_table.setItem(
                        row, 5, QTableWidgetItem(notes or "")
                    )

                    # Column 6: Delete button
                    del_btn = QPushButton("🗑")
                    del_btn.clicked.connect(
                        lambda checked, rid=split_id: self._delete_split(rid)
                    )
                    self.splits_table.setCellWidget(row, 6, del_btn)
            else:
                # Auto-create 2 empty rows for easy splitting
                logger.info("No existing splits - creating 2 default rows")
                self._add_split_row()  # Row 1
                self._add_split_row()  # Row 2

            self._validate_splits()
        except Exception:
            logger.exception("Error loading splits")

    def _load_drivers_for_cashbox(self) -> None:
        """Load drivers dropdown."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT employee_id, first_name || ' ' || last_name"
                " FROM employees ORDER BY first_name"
            )
            self.cashbox_driver.addItem("", None)
            for emp_id, name in cur.fetchall():
                self.cashbox_driver.addItem(name, emp_id)
            cur.close()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Error loading drivers: %s", e)

    def _on_amount_changed(self) -> None:
        """Auto-calculate remaining amount for last row when first amounts"
        "change."""

        # Only auto-calculate if exactly 2 rows and last row is empty/zero
        if self.splits_table.rowCount() == 2:
            # Get first row amount
            first_widget = self.splits_table.cellWidget(0, 1)
            if isinstance(first_widget, QDoubleSpinBox):
                first_amount = first_widget.value()
                receipt_total = float(self.receipt_data["amount"])
                remaining = receipt_total - first_amount

                # Set second row to remaining amount
                second_widget = self.splits_table.cellWidget(1, 1)
                if isinstance(second_widget, QDoubleSpinBox):
                    # Block signals to prevent infinite loop
                    second_widget.blockSignals(True)
                    second_widget.setValue(remaining)
                    second_widget.blockSignals(False)

        # Update validation
        self._validate_splits()

    def _validate_splits(self) -> None:
        """Validate that splits sum to receipt total."""
        total_split = 0.0
        for r in range(self.splits_table.rowCount()):
            # Check if it's a spinbox (new style) or text item (old style)
            amt_widget = self.splits_table.cellWidget(r, 1)
            if isinstance(amt_widget, QDoubleSpinBox):
                total_split += amt_widget.value()
            else:
                amt_item = self.splits_table.item(r, 1)
                if amt_item:
                    try:
                        total_split += float(amt_item.text().replace("$", ""))
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
        receipt_amt = float(self.receipt_data["amount"])
        variance = abs(total_split - receipt_amt)

        if variance < 0.01:
            self.splits_validation_label.setText(
                f"✅ Splits validated (${total_split:.2f} = ${receipt_amt:.2f})"
            )
            self.splits_validation_label.setStyleSheet(
                "color: green; font-weight: bold;"
            )
        else:
            needed = receipt_amt - total_split
            self.splits_validation_label.setText(
                f"🔴 Variance: ${variance:.2f} (Need ${needed:.2f})"
            )
            self.splits_validation_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )

    def _add_split_row(self) -> None:
        """Add a new split row."""
        row = self.splits_table.rowCount()
        self.splits_table.insertRow(row)

        # Column 0: GL Code (dropdown with fuzzy search)
        gl_combo = QComboBox()
        gl_combo.setEditable(True)
        gl_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        gl_codes = self._get_gl_codes()

        # Populate combo with BOTH text and data for proper matching
        for gl_text in gl_codes:
            # Extract code from "5110 - Vehicle Fuel" format
            gl_code = (
                gl_text.split(" - ")[0].strip()
                if " - " in gl_text
                else gl_text
            )
            gl_combo.addItem(gl_text, gl_code)

        # Add fuzzy/contains autocomplete
        if len(gl_codes) > 1:  # Skip completer if only placeholder
            completer = QCompleter(gl_codes)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            gl_combo.setCompleter(completer)

        self.splits_table.setCellWidget(row, 0, gl_combo)

        # Column 1: Amount (editable spinbox with auto-calculation)
        amount_spin = QDoubleSpinBox()
        amount_spin.setMaximum(999999.99)
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        amount_spin.setValue(0.00)
        # Connect to auto-calculate remaining amount
        amount_spin.valueChanged.connect(self._on_amount_changed)
        self.splits_table.setCellWidget(row, 1, amount_spin)

        # Column 2: Payment Method (dropdown with choices)
        method_combo = QComboBox()
        payment_methods = [
            "cash",
            "check",
            "debit/credit_card",
            "bank_transfer",
            "etransfer",
            "gift_card",
            "personal",
            "trade_of_services",
            "unknown",
        ]
        method_combo.addItems(payment_methods)
        current_method = (
            self.receipt_data.get("payment_method", "cash")
            if self.receipt_data
            else "cash"
        )
        # Map database values to combined option
        if current_method in ("debit_card", "credit_card"):
            current_method = "debit/credit_card"
        if method_combo.findText(current_method) >= 0:
            method_combo.setCurrentText(current_method)
        else:
            method_combo.setCurrentText("cash")
        self.splits_table.setCellWidget(row, 2, method_combo)

        # Column 3: Business/Personal
        bp_combo = QComboBox()
        bp_combo.addItems(["Business", "Personal", "NEEDS_REVIEW"])
        bp_combo.setCurrentText("Business")
        bp_combo.setToolTip(
            "Business = company expense; Personal = driver's own (e.g. smokes)"
        )
        self.splits_table.setCellWidget(row, 3, bp_combo)

        # Column 4: Reimbursed checkbox
        reimb_widget = QWidget()
        reimb_layout = QHBoxLayout(reimb_widget)
        reimb_layout.setContentsMargins(4, 0, 4, 0)
        reimb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reimb_chk = QCheckBox()
        reimb_chk.setToolTip(
            "Driver paid out-of-pocket and was (or will be) reimbursed"
        )
        reimb_layout.addWidget(reimb_chk)
        self.splits_table.setCellWidget(row, 4, reimb_widget)

        # Column 5: Notes (text field)
        self.splits_table.setItem(row, 5, QTableWidgetItem(""))

        # Column 6: Delete button
        del_btn = QPushButton("🗑")
        del_btn.clicked.connect(
            lambda checked, r=row: self._delete_split_row(r)
        )
        self.splits_table.setCellWidget(row, 6, del_btn)

    def _get_gl_codes(self) -> list:
        """Get list of available GL codes from chart_of_accounts ONLY."""
        try:
            cur = self.conn.cursor()

            # Pull ONLY from chart_of_accounts - the single source of truth
            cur.execute("""
                SELECT account_code, account_name, parent_account,
                is_header_account, is_active
                FROM chart_of_accounts
                WHERE account_code IS NOT NULL AND account_code != ''
                  AND is_active = true
                  AND (is_header_account IS NULL OR is_header_account = false)
                ORDER BY account_code
            """)

            gl_accounts = cur.fetchall()
            cur.close()

            if gl_accounts:
                formatted = []
                for (
                    account_code,
                    account_name,
                    parent_account,
                    is_header,
                    is_active,
                ) in gl_accounts:
                    code = str(account_code).strip()
                    name = (account_name or "GL Account").strip()

                    # Add indentation for sub-accounts
                    if parent_account:
                        indent = "  "  # Two spaces for child accounts
                    else:
                        indent = ""

                    label = f"{indent}{code} - {name}"
                    formatted.append(label)
                return formatted

            return [
                "5110 - Vehicle Fuel",
                "5306 - Cost of Goods Sold",
                "6000 - Operating Expenses",
                "6800 - Other Expenses",
            ]
        except Exception:
            logger.exception("Error loading GL codes")
            # Return basic GL codes as fallback
            return [
                "5110 - Vehicle Fuel",
                "5306 - Cost of Goods Sold",
                "6000 - Operating Expenses",
                "6800 - Other Expenses",
                "5900 - Direct Costs",
            ]

    def _delete_split_row(self, row: int) -> None:
        """Delete a split row."""
        self.splits_table.removeRow(row)
        self._validate_splits()

    def _delete_split(self, split_id: int) -> None:
        """Delete a split from database."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM receipt_gl_splits WHERE split_id = %s",
                (split_id,),
            )
            self.conn.commit()
            cur.close()
            self._load_splits()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(self, "Error", f"Could not delete split: {e}")

    def _link_banking(self) -> None:
        """Link to banking transaction using the picker dialog."""
        try:
            # Launch banking transaction picker
            picker = BankingTransactionPickerDialog(
                self.conn, self.receipt_id, self.receipt_data["amount"]
            )

            if picker.exec() == QDialog.DialogCode.Accepted:
                result = picker.get_result()
                if result:
                    txn_id, linked_amount = result

                    # Add to banking table display
                    cur = self.conn.cursor()
                    cur.execute(
                        """
                        SELECT transaction_date, description, debit, credit
                        FROM banking_transactions WHERE transaction_id = %s
                    """,
                        (txn_id,),
                    )
                    txn_row = cur.fetchone()
                    cur.close()

                    if txn_row:
                        row = self.banking_table.rowCount()
                        self.banking_table.insertRow(row)

                        self.banking_table.setItem(
                            row, 0, QTableWidgetItem(str(txn_row[0]))
                        )
                        self.banking_table.setItem(
                            row, 1, QTableWidgetItem(txn_row[1] or "")
                        )
                        self.banking_table.setItem(
                            row, 2, QTableWidgetItem(f"${linked_amount:,.2f}")
                        )
                        self.banking_table.setItem(
                            row, 3, QTableWidgetItem("✅ Linked")
                        )

                        # Unlink button
                        unlink_btn = QPushButton("🔌 Unlink")
                        unlink_btn.clicked.connect(
                            lambda: self._unlink_banking_transaction(
                                txn_id, row
                            )
                        )
                        self.banking_table.setCellWidget(row, 4, unlink_btn)

                        # Update validation
                        self._validate_banking_amounts()
                        QMessageBox.information(
                            self,
                            "Success",
                            f"Banking transaction #{txn_id} linked!",
                        )

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Error", f"Could not link banking transaction:\n{e}"
            )

    def _unlink_banking_transaction(self, txn_id: int, row: int) -> None:
        """Unlink a banking transaction."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                DELETE FROM receipt_banking_links
                WHERE receipt_id = %s AND transaction_id = %s
            """,
                (self.receipt_id, txn_id),
            )
            cur.execute(
                """
                UPDATE banking_transactions
                SET receipt_id = NULL, reconciliation_status = NULL
                WHERE transaction_id = %s
            """,
                (txn_id,),
            )
            self.conn.commit()
            cur.close()

            self.banking_table.removeRow(row)
            self._validate_banking_amounts()
            QMessageBox.information(
                self, "Success", "Banking transaction unlinked!"
            )

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Error", f"Could not unlink transaction:\n{e}"
            )

    def _validate_banking_amounts(self) -> None:
        """Validate that linked banking transactions sum to receipt total."""
        total_linked = 0.0
        for r in range(self.banking_table.rowCount()):
            amt_item = self.banking_table.item(r, 2)
            if amt_item:
                try:
                    # Remove $ and , from amount
                    amt_text = (
                        amt_item.text().replace("$", "").replace(",", "")
                    )
                    total_linked += float(amt_text)
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
        receipt_amt = float(self.receipt_data["amount"])
        variance = abs(total_linked - receipt_amt)

        if variance < 0.01:
            self.banking_validation_label.setText(
                f"✅ Banking matched (${total_linked:.2f} = ${receipt_amt:.2f})"
            )
            self.banking_validation_label.setStyleSheet(
                "color: green; font-weight: bold;"
            )
            self.bank_match_label.setText("✅ Matched")
            self.bank_match_label.setStyleSheet(
                "color: green; font-weight: bold;"
            )
        else:
            needed = receipt_amt - total_linked
            self.banking_validation_label.setText(
                f"🔴 Variance: ${variance:.2f} (Need ${needed:.2f})"
            )
            self.banking_validation_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )
            self.bank_match_label.setText("🔴 Not Matched")
            self.bank_match_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )

    def _save_single_split(self) -> None:
        """Save all splits (same as 'Save All & Reconcile')."""
        self._save_all_splits()

    def _save_all_splits(self) -> None:
        """Save all splits by deleting parent, creating child receipts with"
        "same split_group_id."""

        try:
            # Validate first
            self._validate_splits()
            if "green" not in self.splits_validation_label.styleSheet():
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "Splits must sum to receipt total before saving",
                )
                return

            cur = self.conn.cursor()

            # Original receipt will be used as the split_group_id
            # All children get the same split_group_id = original receipt_id
            split_group_id = self.receipt_id
            original_total = self.receipt_data["amount"]

            # Create child receipts for each split
            child_count = 0
            child_ids = []

            for r in range(self.splits_table.rowCount()):
                # Column 0 is now GL Code (ComboBox)
                gl_widget = self.splits_table.cellWidget(r, 0)
                gl_display = (
                    gl_widget.currentText().strip() if gl_widget else ""
                )
                # Extract GL code from "CODE - Description" format
                gl = (
                    gl_display.split(" - ")[0].strip()
                    if " - " in gl_display
                    else gl_display
                )

                # Column 1 is Amount (QDoubleSpinBox widget)
                amt_widget = self.splits_table.cellWidget(r, 1)
                amt = (
                    amt_widget.value()
                    if isinstance(amt_widget, QDoubleSpinBox)
                    else 0.0
                )

                # Column 2 is Payment Method (ComboBox)
                method_widget = self.splits_table.cellWidget(r, 2)
                payment_method = (
                    method_widget.currentText()
                    if method_widget
                    else self.receipt_data.get("payment_method", "cash")
                )

                # Column 3: Business/Personal
                bp_widget = self.splits_table.cellWidget(r, 3)
                business_personal = (
                    bp_widget.currentText()
                    if isinstance(bp_widget, QComboBox)
                    else "Business"
                )

                # Column 4: Reimbursed checkbox
                reimb_container = self.splits_table.cellWidget(r, 4)
                reimb_chk = (
                    reimb_container.findChild(QCheckBox)
                    if reimb_container
                    else None
                )
                reimbursed = reimb_chk.isChecked() if reimb_chk else False

                # Column 5 is Notes/Category
                notes_item = self.splits_table.item(r, 5)
                split_notes = notes_item.text().strip() if notes_item else ""

                if gl and amt > 0 and gl != "-- Select GL Code --":
                    try:

                        # Create new child receipt with same split_group_id and
                        # is_split_receipt=true
                        cur.execute(
                            """
                            INSERT INTO receipts
                            (receipt_date, vendor_name, gross_amount,
                            gl_account_code,
                             description, payment_method, split_group_id,
                             is_split_receipt,
                             split_group_total, business_personal)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING receipt_id
                        """,
                            (
                                self.receipt_data["date"],
                                self.receipt_data["vendor"],
                                amt,
                                gl,
                                (
                                    self.receipt_data.get(
                                        "desc", ""
                                    ).strip()
                                    + " | "
                                    + split_notes
                                    if split_notes
                                    and self.receipt_data.get("desc")
                                    else (
                                        split_notes
                                        or self.receipt_data.get("desc")
                                        or self.receipt_data.get("vendor")
                                        or f"Split portion (GL: {gl})"
                                    )
                                ),
                                payment_method,
                                split_group_id,
                                True,
                                original_total,
                                business_personal,
                            ),
                        )

                        child_id = cur.fetchone()[0]
                        child_count += 1
                        child_ids.append(child_id)

                        # Also create entry in receipt_gl_splits for tracking
                        cur.execute(
                            """
                            INSERT INTO receipt_gl_splits
                            (receipt_id, split_order, gl_code, gl_account_code,
                            amount,
                             payment_method, notes, business_personal,
                             reimbursed)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                            (
                                child_id,
                                r + 1,
                                gl,
                                gl,
                                amt,
                                payment_method,
                                (split_notes or self.receipt_data.get("desc")),
                                business_personal,
                                reimbursed,
                            ),
                        )

                    except Exception as e:
                        try:
                            self.conn.rollback()
                        except Exception as _e:
                            logger.debug('Suppressed: %s', _e)
                        print(f"Error creating child receipt: {e}")
                        raise

            # Now DELETE the original parent receipt (was causing accounting
            # issues)
            cur.execute(
                """
                DELETE FROM receipt_gl_splits WHERE receipt_id = %s
            """,
                (self.receipt_id,),
            )

            # Clear any banking_transactions FK references to the parent
            # receipt before deleting it (banking links must be re-established
            # on the child receipts after the split).
            cur.execute(
                """
                UPDATE banking_transactions
                SET receipt_id = NULL, reconciliation_status = NULL
                WHERE receipt_id = %s
            """,
                (self.receipt_id,),
            )

            cur.execute(
                """
                DELETE FROM receipt_banking_links WHERE receipt_id = %s
            """,
                (self.receipt_id,),
            )

            cur.execute(
                """
                DELETE FROM receipts WHERE receipt_id = %s
            """,
                (self.receipt_id,),
            )

            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "Success",
                f"✅ Receipt #{self.receipt_id} split into {child_count}"
                f"linked receipts!\n\n"
                f"Child receipts: "
                f"{', '.join(f'#{cid}' for cid in child_ids)}\n"
                f"All share Group ID {split_group_id}\n\n"
                f"Original receipt #{self.receipt_id} has been deleted.\n\n"
                "⚠️  Any banking transaction that was linked to the original"
                "receipt\n"
                "    has been unlinked. Please re-link it to the appropriate"
                "child receipt.\n\n"
                "💡 TO VIEW SPLIT RECEIPTS:\n"
                "   ✓ Check the 'Show linked splits' checkbox in the search"
                "panel\n"
                "   ✓ Search by total amount or individual amounts\n"
                "   ✓ All split receipts are searchable and individually"
                "editable",
            )
            self.splits_saved.emit(self.receipt_id)
            self.accept()
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Error", f"Could not save splits: {e}")
            print(f"Split save error: {e}")
            import traceback

            traceback.print_exc()
