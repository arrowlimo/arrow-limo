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
from common_widgets import PAYMENT_METHOD_LABELS, normalize_payment_method
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
        self.setWindowTitle(f"Split Receipt Editor - Receipt #{receipt_id}")
        self.setGeometry(100, 100, 1400, 800)
        self.setModal(True)

        # Use provided receipt_data or load it
        if receipt_data:
            self.receipt_data = self._normalize_receipt_data(receipt_data)
        else:
            self.receipt_data = self._normalize_receipt_data(
                self._load_receipt()
            )
        self.receipts_columns = self._load_receipts_columns()
        self.editing_existing_split_group = False
        self.split_group_id = None

        if not self.receipt_data:
            QMessageBox.critical(
                self, "Error", f"Receipt #{receipt_id} not found"
            )
            self.reject()
            return
        self._resolve_split_context()

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

    def _resolve_split_context(self) -> None:
        """When opened from a split child, operate on the full split group."""

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT split_group_id,
                       COALESCE(is_split_receipt, FALSE),
                       split_group_total
                FROM receipts
                WHERE receipt_id = %s
                """,
                (self.receipt_id,),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                return

            split_group_id, is_split, split_group_total = row
            if not (is_split or split_group_id):
                cur.close()
                return

            group_id = int(split_group_id or self.receipt_id)
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
                FROM receipts
                WHERE split_group_id = %s
                """,
                (group_id,),
            )
            count, summed_total = cur.fetchone() or (0, 0)
            cur.close()

            if int(count or 0) <= 0:
                return

            self.editing_existing_split_group = True
            self.split_group_id = group_id
            group_total = split_group_total or summed_total
            self.receipt_data["amount"] = float(group_total or 0)
            self.setWindowTitle(f"Split Receipt Editor - Group #{group_id}")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Error resolving split context: %s", e)

    def _load_receipt(self) -> dict | None:
        """Load receipt details."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       payment_method, description,
                       gst_amount, source_reference,
                       COALESCE(is_paper_verified, FALSE) AS is_paper_verified,
                       COALESCE(verified_by_edit, FALSE) AS verified_by_edit,
                       COALESCE(verified_by_user, '') AS verified_by_user
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
                    "gst_amount": row[6],
                    "source_reference": row[7],
                    "is_paper_verified": row[8],
                    "verified_by_edit": row[9],
                    "verified_by_user": row[10],
                }
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Error loading receipt: %s", e)
        return None

    def _load_receipts_columns(self) -> set[str]:
        """Load receipts columns for optional-field-safe inserts."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE "
                "table_name = 'receipts'"
            )
            cols = {row[0] for row in cur.fetchall()}
            cur.close()
            return cols
        except Exception:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return set()

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
        self.splits_table.setColumnCount(9)
        self.splits_table.setHorizontalHeaderLabels(
            [
                "GL Code",
                "Amount",
                "Payment Method",
                "Bus/Personal",
                "Reimb?",
                "Notes",
                "GST Mode",
                "GST",
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
            if self.editing_existing_split_group and self.split_group_id:
                cur.execute(
                    """
                    SELECT s.split_id,
                           COALESCE(s.split_order,
                               ROW_NUMBER() OVER (ORDER BY r.receipt_id)),
                           COALESCE(s.gl_code, r.gl_account_code),
                           COALESCE(s.amount, r.gross_amount),
                           COALESCE(s.payment_method, r.payment_method, 'cash'),
                           COALESCE(s.notes, r.description, ''),
                           COALESCE(s.business_personal,
                               r.business_personal, 'Business'),
                           COALESCE(s.reimbursed, FALSE),
                           r.receipt_id,
                           r.gst_amount
                    FROM receipts r
                    LEFT JOIN LATERAL (
                        SELECT split_id, split_order, gl_code, amount,
                               payment_method, notes, business_personal,
                               reimbursed
                        FROM receipt_gl_splits
                        WHERE receipt_id = r.receipt_id
                        ORDER BY split_order
                        LIMIT 1
                    ) s ON TRUE
                    WHERE r.split_group_id = %s
                    ORDER BY r.receipt_id
                    """,
                    (self.split_group_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT split_id, split_order, gl_code, amount, payment_method,
                    notes,
                           business_personal, reimbursed, NULL AS receipt_id,
                           NULL AS gst_amount
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
                    child_receipt_id = row_data[8] if len(row_data) > 8 else None
                    row = self.splits_table.rowCount()
                    self.splits_table.insertRow(row)

                    # Column 0: GL Code (dropdown)
                    gl_combo = QComboBox()
                    gl_combo.setEditable(True)
                    gl_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                    gl_codes = self._get_gl_codes()
                    gl_combo.addItem("", "")

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
                            if gl_combo.itemText(i).strip().startswith(str(gl)):
                                gl_combo.setCurrentIndex(i)
                                break
                    self.splits_table.setCellWidget(row, 0, gl_combo)

                    # Column 1: Amount (spinbox)
                    amount_spin = QDoubleSpinBox()
                    amount_spin.setMaximum(999999.99)
                    amount_spin.setMinimum(-999999.99)
                    amount_spin.setDecimals(2)
                    amount_spin.setPrefix("$")
                    amount_spin.setValue(float(amt) if amt else 0.00)
                    amount_spin.setProperty("receipt_id", child_receipt_id)
                    amount_spin.valueChanged.connect(self._on_amount_changed)
                    self.splits_table.setCellWidget(row, 1, amount_spin)

                    # Column 2: Payment Method (dropdown) - use the same
                    # canonical values/labels as the main receipt form so
                    # splits always match what's stored on receipts.
                    method_combo = QComboBox()
                    for pm_key, pm_label in PAYMENT_METHOD_LABELS.items():
                        method_combo.addItem(pm_label, pm_key)
                    canonical_method = (
                        normalize_payment_method(method) if method else "cash"
                    )
                    idx = method_combo.findData(canonical_method)
                    method_combo.setCurrentIndex(idx if idx >= 0 else 0)
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

                    # Column 5: Notes (text field, defaults to receipt desc)
                    self.splits_table.setItem(
                        row,
                        5,
                        QTableWidgetItem(
                            notes
                            or self.receipt_data.get("desc")
                            or self.receipt_data.get("vendor")
                            or ""
                        ),
                    )

                    # Column 6: GST mode for this line
                    gst_mode = QComboBox()
                    gst_mode.addItems(
                        ["Included", "Added", "None"]
                    )
                    gst_mode.setToolTip(
                        "Included = amount already contains GST.\n"
                        "Added = GST is charged on top of the amount.\n"
                        "None = non-taxable line (e.g. ice, discount)."
                    )
                    row_line_gst = row_data[9] if len(row_data) > 9 else None
                    if child_receipt_id is not None and row_line_gst is not None:
                        # Stored amounts are always GST-inclusive, so a saved
                        # line reloads as Included (or None when untaxed).
                        if abs(float(row_line_gst or 0)) < 0.005:
                            gst_mode.setCurrentText("None")
                    self.splits_table.setCellWidget(row, 6, gst_mode)

                    # Column 7: GST for this line (auto-prorated, editable)
                    gst_spin = QDoubleSpinBox()
                    gst_spin.setMaximum(999999.99)
                    gst_spin.setMinimum(-999999.99)
                    gst_spin.setDecimals(2)
                    gst_spin.setPrefix("$")
                    gst_spin.setToolTip(
                        "GST for this line. Auto-prorated, but override it to "
                        "match the printed receipt."
                    )
                    if row_line_gst is not None:
                        gst_spin.setValue(float(row_line_gst or 0))
                        gst_spin.setProperty("manual_gst", True)
                    gst_spin.valueChanged.connect(
                        lambda _v, w=gst_spin: w.setProperty("manual_gst", True)
                    )
                    self.splits_table.setCellWidget(row, 7, gst_spin)
                    gst_mode.currentTextChanged.connect(
                        lambda _t: self._recalc_line_gst()
                    )

                    # Column 8: Delete button
                    del_btn = QPushButton("🗑")
                    if self.editing_existing_split_group:
                        del_btn.clicked.connect(
                            lambda checked, btn=del_btn: (
                                self._delete_split_row_for_button(btn)
                            )
                        )
                    else:
                        del_btn.clicked.connect(
                            lambda checked, rid=split_id: self._delete_split(rid)
                        )
                    self.splits_table.setCellWidget(row, 8, del_btn)
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
        """Keep the last split line as the remaining unallocated balance."""

        row_count = self.splits_table.rowCount()
        if row_count >= 2:
            last_row = row_count - 1
            last_widget = self.splits_table.cellWidget(last_row, 1)
            sender = self.sender()

            # If the user edits the last row directly, treat it as manual and
            # only validate. Earlier rows drive the remaining-balance field.
            if sender is not last_widget and isinstance(
                last_widget, QDoubleSpinBox
            ):
                allocated = 0.0
                for row in range(last_row):
                    amt_widget = self.splits_table.cellWidget(row, 1)
                    if isinstance(amt_widget, QDoubleSpinBox):
                        allocated += self._row_total_effect(row)

                receipt_total = float(self.receipt_data["amount"])
                remaining = round(receipt_total - allocated, 2)
                if self._row_gst_mode(last_row) == "Added":
                    remaining = round(remaining / (1 + self.GST_RATE), 2)

                last_widget.blockSignals(True)
                last_widget.setValue(remaining)
                last_widget.blockSignals(False)

        # Update validation
        self._recalc_line_gst()
        self._validate_splits()

    def _validate_splits(self) -> None:
        """Validate that split lines (plus added GST) sum to receipt total."""
        total_split = 0.0
        for r in range(self.splits_table.rowCount()):
            amt_widget = self.splits_table.cellWidget(r, 1)
            if isinstance(amt_widget, QDoubleSpinBox):
                total_split += self._row_total_effect(r)
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
        gl_combo.addItem("", "")

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
        amount_spin.setMinimum(-999999.99)
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        amount_spin.setValue(0.00)
        # Connect to auto-calculate remaining amount
        amount_spin.valueChanged.connect(self._on_amount_changed)
        self.splits_table.setCellWidget(row, 1, amount_spin)

        # Column 2: Payment Method (dropdown with choices) - same canonical
        # values/labels as the main receipt form so splits always match
        # what's stored on receipts.
        method_combo = QComboBox()
        for pm_key, pm_label in PAYMENT_METHOD_LABELS.items():
            method_combo.addItem(pm_label, pm_key)
        raw_method = (
            self.receipt_data.get("payment_method", "cash")
            if self.receipt_data
            else "cash"
        )
        canonical_method = normalize_payment_method(raw_method) or "cash"
        idx = method_combo.findData(canonical_method)
        method_combo.setCurrentIndex(idx if idx >= 0 else 0)
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

        # Column 5: Notes (text field, prefilled from receipt description)
        self.splits_table.setItem(
            row,
            5,
            QTableWidgetItem(
                (self.receipt_data or {}).get("desc")
                or (self.receipt_data or {}).get("vendor")
                or ""
            ),
        )

        # Column 6: GST mode for this line
        gst_mode = QComboBox()
        gst_mode.addItems(["Included", "Added", "None"])
        gst_mode.setToolTip(
            "Included = amount already contains GST.\n"
            "Added = GST is charged on top of the amount.\n"
            "None = non-taxable line (e.g. ice, discount)."
        )
        self.splits_table.setCellWidget(row, 6, gst_mode)

        # Column 7: GST for this line (auto-prorated, editable)
        gst_spin = QDoubleSpinBox()
        gst_spin.setMaximum(999999.99)
        gst_spin.setMinimum(-999999.99)
        gst_spin.setDecimals(2)
        gst_spin.setPrefix("$")
        gst_spin.setToolTip(
            "GST for this line. Auto-prorated, but override it to match the "
            "printed receipt."
        )
        gst_spin.valueChanged.connect(
            lambda _v, w=gst_spin: w.setProperty("manual_gst", True)
        )
        self.splits_table.setCellWidget(row, 7, gst_spin)
        gst_mode.currentTextChanged.connect(lambda _t: self._recalc_line_gst())

        # Column 8: Delete button
        del_btn = QPushButton("🗑")
        del_btn.clicked.connect(
            lambda checked, r=row: self._delete_split_row(r)
        )
        self.splits_table.setCellWidget(row, 8, del_btn)
        self._recalc_line_gst()

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

    GST_RATE = 0.05

    def _row_gst_mode(self, row: int) -> str:
        """GST treatment for a split line: Included, Added or None."""
        widget = self.splits_table.cellWidget(row, 6)
        if isinstance(widget, QComboBox):
            return widget.currentText().strip() or "Included"
        return "Included"

    def _row_is_no_gst(self, row: int) -> bool:
        """True when the split line is flagged as non-taxable (e.g. ice)."""
        return self._row_gst_mode(row) == "None"

    def _row_line_gst(self, row: int) -> float | None:
        """GST entered for this line, or None when the column is absent."""
        if self._row_is_no_gst(row):
            return 0.0
        widget = self.splits_table.cellWidget(row, 7)
        if isinstance(widget, QDoubleSpinBox):
            return round(float(widget.value()), 2)
        return None

    def _row_amount(self, row: int) -> float:
        widget = self.splits_table.cellWidget(row, 1)
        return (
            float(widget.value()) if isinstance(widget, QDoubleSpinBox) else 0.0
        )

    def _row_total_effect(self, row: int) -> float:
        """What this line contributes to the receipt total.

        'Added' lines push GST on top of the entered amount, so they add
        amount + GST. 'Included' and 'None' lines contribute the amount only.
        """
        amount = self._row_amount(row)
        if self._row_gst_mode(row) == "Added":
            return round(amount + (self._row_line_gst(row) or 0.0), 2)
        return amount

    def _recalc_line_gst(self) -> None:
        """Derive GST per line from its mode, keeping manual overrides."""
        for row in range(self.splits_table.rowCount()):
            gst_widget = self.splits_table.cellWidget(row, 7)
            if not isinstance(gst_widget, QDoubleSpinBox):
                continue
            mode = self._row_gst_mode(row)
            amount = self._row_amount(row)

            if mode == "None":
                value = 0.0
            elif mode == "Added":
                value = round(amount * self.GST_RATE, 2)
            else:
                value = round(
                    amount - (amount / (1 + self.GST_RATE)),
                    2,
                )

            # Manual entries win, except a 'None' line is always zero.
            if gst_widget.property("manual_gst") and mode != "None":
                continue
            gst_widget.blockSignals(True)
            gst_widget.setValue(value)
            gst_widget.blockSignals(False)

    def _delete_split_row(self, row: int) -> None:
        """Delete a split row."""
        if row < 0 or row >= self.splits_table.rowCount():
            return
        self.splits_table.removeRow(row)
        self._validate_splits()

    def _delete_split_row_for_button(self, button: QPushButton) -> None:
        """Delete the table row containing this delete button."""
        for row in range(self.splits_table.rowCount()):
            if self.splits_table.cellWidget(row, 8) is button:
                self._delete_split_row(row)
                return

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

    def _save_existing_split_group(self) -> None:
        """Update an existing split group instead of re-splitting one child."""

        cur = self.conn.cursor()
        try:
            split_group_id = int(self.split_group_id)
            original_total = float(self.receipt_data["amount"] or 0)
            cur.execute(
                """
                SELECT receipt_id
                FROM receipts
                WHERE split_group_id = %s
                ORDER BY receipt_id
                """,
                (split_group_id,),
            )
            existing_ids = {int(row[0]) for row in cur.fetchall() or []}

            cur.execute(
                """
                SELECT receipt_date, vendor_name, description, gst_amount,
                       source_reference, reserve_number, payment_method
                FROM receipts
                WHERE receipt_id = %s
                """,
                (self.receipt_id,),
            )
            template = cur.fetchone()
            if not template:
                cur.execute(
                    """
                    SELECT receipt_date, vendor_name, description, gst_amount,
                           source_reference, reserve_number, payment_method
                    FROM receipts
                    WHERE split_group_id = %s
                    ORDER BY receipt_id
                    LIMIT 1
                    """,
                    (split_group_id,),
                )
                template = cur.fetchone()
            if not template:
                raise ValueError(
                    f"Could not find a template receipt for split group "
                    f"{split_group_id}"
                )

            (
                receipt_date,
                vendor_name,
                base_description,
                parent_gst_total,
                source_reference,
                reserve_number,
                fallback_payment_method,
            ) = template
            parent_gst_total = float(parent_gst_total or 0)
            allocated_gst = 0.0
            kept_ids: set[int] = set()
            row_payloads = []

            for row in range(self.splits_table.rowCount()):
                gl_widget = self.splits_table.cellWidget(row, 0)
                amt_widget = self.splits_table.cellWidget(row, 1)
                method_widget = self.splits_table.cellWidget(row, 2)
                bp_widget = self.splits_table.cellWidget(row, 3)
                reimb_container = self.splits_table.cellWidget(row, 4)
                notes_item = self.splits_table.item(row, 5)

                gl_display = gl_widget.currentText().strip() if gl_widget else ""
                gl = (
                    gl_display.split(" - ")[0].strip()
                    if " - " in gl_display
                    else gl_display
                )
                amount = (
                    float(amt_widget.value())
                    if isinstance(amt_widget, QDoubleSpinBox)
                    else 0.0
                )
                if not gl or abs(amount) < 0.005:
                    continue
                payment_method = (
                    (
                        method_widget.currentData()
                        or normalize_payment_method(
                            method_widget.currentText()
                        )
                    )
                    if isinstance(method_widget, QComboBox)
                    else (fallback_payment_method or "cash")
                )
                business_personal = (
                    bp_widget.currentText()
                    if isinstance(bp_widget, QComboBox)
                    else "Business"
                )
                reimb_chk = (
                    reimb_container.findChild(QCheckBox)
                    if reimb_container
                    else None
                )
                reimbursed = bool(reimb_chk.isChecked()) if reimb_chk else False
                notes = notes_item.text().strip() if notes_item else ""
                child_id = (
                    int(amt_widget.property("receipt_id"))
                    if isinstance(amt_widget, QDoubleSpinBox)
                    and amt_widget.property("receipt_id")
                    else None
                )
                row_payloads.append(
                    {
                        "child_id": child_id,
                        "gl": gl,
                        "amount": amount,
                        "payment_method": payment_method,
                        "business_personal": business_personal,
                        "reimbursed": reimbursed,
                        "notes": notes,
                        "no_gst": self._row_is_no_gst(row),
                        "line_gst": self._row_line_gst(row),
                        "gst_mode": self._row_gst_mode(row),
                    }
                )

            for index, payload in enumerate(row_payloads):
                line_gst = float(payload["line_gst"] or 0)
                gross_amount = round(
                    payload["amount"] + line_gst
                    if payload["gst_mode"] == "Added"
                    else payload["amount"],
                    2,
                )
                payload["amount"] = gross_amount
                net_amount = round(gross_amount - line_gst, 2)
                description = payload["notes"] or base_description or vendor_name

                child_id = payload["child_id"]
                if child_id and child_id in existing_ids:
                    kept_ids.add(child_id)
                    cur.execute(
                        """
                        UPDATE receipts
                        SET gross_amount = %s,
                            net_amount = %s,
                            gst_amount = %s,
                            gl_account_code = %s,
                            description = %s,
                            payment_method = %s,
                            split_group_id = %s,
                            is_split_receipt = TRUE,
                            split_group_total = %s,
                            split_status = 'single',
                            business_personal = %s,
                            gst_exempt = %s,
                            updated_at = NOW()
                        WHERE receipt_id = %s
                        """,
                        (
                            payload["amount"],
                            net_amount,
                            line_gst,
                            payload["gl"],
                            description,
                            payload["payment_method"],
                            split_group_id,
                            original_total,
                            payload["business_personal"],
                            bool(payload["no_gst"]),
                            child_id,
                        ),
                    )
                else:
                    extra_cols = [
                        c
                        for c in (
                            "charter_id",
                            "employee_id",
                            "vehicle_id",
                            "vehicle_number",
                            "vendor_account_id",
                            "fiscal_year",
                            "card_type",
                            "card_number",
                            "receipt_source",
                            "source_system",
                        )
                        if c in self.receipts_columns
                    ]
                    extra_vals: list = []
                    if extra_cols:
                        cur.execute(
                            f"SELECT {', '.join(extra_cols)} "
                            "FROM receipts WHERE receipt_id = %s",
                            (self.receipt_id,),
                        )
                        extra_vals = list(cur.fetchone() or [])
                    if len(extra_vals) != len(extra_cols):
                        extra_cols, extra_vals = [], []
                    extra_sql = (
                        (", " + ", ".join(extra_cols)) if extra_cols else ""
                    )
                    extra_ph = (
                        (", " + ", ".join(["%s"] * len(extra_cols)))
                        if extra_cols
                        else ""
                    )
                    cur.execute(
                        f"""
                        INSERT INTO receipts
                        (receipt_date, vendor_name, description, gross_amount,
                         net_amount, gst_amount, gl_account_code,
                         payment_method, split_group_id, is_split_receipt,
                         split_group_total, split_status, business_personal,
                         source_reference, reserve_number, created_at,
                         updated_at{extra_sql})
                        VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s,
                         'single', %s, %s, %s, NOW(), NOW(){extra_ph})
                        RETURNING receipt_id
                        """,
                        (
                            receipt_date,
                            vendor_name,
                            description,
                            payload["amount"],
                            net_amount,
                            line_gst,
                            payload["gl"],
                            payload["payment_method"],
                            split_group_id,
                            original_total,
                            payload["business_personal"],
                            source_reference,
                            reserve_number,
                        )
                        + tuple(extra_vals),
                    )
                    child_id = int(cur.fetchone()[0])
                    kept_ids.add(child_id)

                cur.execute(
                    "DELETE FROM receipt_gl_splits WHERE receipt_id = %s",
                    (child_id,),
                )
                cur.execute(
                    """
                    INSERT INTO receipt_gl_splits
                    (receipt_id, split_order, gl_code, gl_account_code, amount,
                     payment_method, notes, business_personal, reimbursed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        child_id,
                        index + 1,
                        payload["gl"],
                        payload["gl"],
                        payload["amount"],
                        payload["payment_method"],
                        payload["notes"],
                        payload["business_personal"],
                        payload["reimbursed"],
                    ),
                )

            delete_ids = sorted(existing_ids - kept_ids)
            if delete_ids:
                cur.execute(
                    """
                    UPDATE banking_transactions
                    SET receipt_id = NULL, reconciliation_status = NULL
                    WHERE receipt_id = ANY(%s)
                    """,
                    (delete_ids,),
                )
                cur.execute(
                    "DELETE FROM receipt_banking_links WHERE receipt_id = ANY(%s)",
                    (delete_ids,),
                )
                cur.execute(
                    "DELETE FROM receipt_gl_splits WHERE receipt_id = ANY(%s)",
                    (delete_ids,),
                )
                cur.execute(
                    "DELETE FROM receipts WHERE receipt_id = ANY(%s)",
                    (delete_ids,),
                )

            cur.execute(
                """
                SELECT COALESCE(SUM(gross_amount), 0)
                FROM receipts
                WHERE split_group_id = %s
                """,
                (split_group_id,),
            )
            saved_total = float((cur.fetchone() or [0])[0] or 0)
            if abs(saved_total - original_total) > 0.02:
                raise ValueError(
                    "Split integrity failure: group amount sum "
                    f"{saved_total:.2f} != split total {original_total:.2f}"
                )

            self.conn.commit()
            QMessageBox.information(
                self,
                "Success",
                f"✅ Split group #{split_group_id} updated.\n\n"
                f"Total: ${saved_total:.2f}",
            )
            self.splits_saved.emit(self.receipt_id)
            self.accept()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

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
            missing_gl_rows = []
            for row in range(self.splits_table.rowCount()):
                gl_widget = self.splits_table.cellWidget(row, 0)
                amt_widget = self.splits_table.cellWidget(row, 1)
                gl = gl_widget.currentText().strip() if gl_widget else ""
                amount = (
                    amt_widget.value()
                    if isinstance(amt_widget, QDoubleSpinBox)
                    else 0.0
                )
                if abs(amount) >= 0.005 and not gl:
                    missing_gl_rows.append(row + 1)
            if missing_gl_rows:
                QMessageBox.warning(
                    self,
                    "GL Code Required",
                    "Select a GL code for every split with an amount "
                    f"(row(s): {', '.join(map(str, missing_gl_rows))}).",
                )
                return

            if self.editing_existing_split_group and self.split_group_id:
                self._save_existing_split_group()
                return

            cur = self.conn.cursor()

            # Original receipt will be used as the split_group_id
            # All children get the same split_group_id = original receipt_id
            split_group_id = self.receipt_id
            original_total = self.receipt_data["amount"]

            # Read parent verification/review metadata so split children keep
            # consistent paper/no-receipt semantics.
            cur.execute(
                """
                SELECT COALESCE(is_paper_verified, FALSE),
                       COALESCE(receipt_review_status, ''),
                       COALESCE(verified_by_edit, FALSE),
                       COALESCE(verified_by_user, '')
                FROM receipts
                WHERE receipt_id = %s
                """,
                (self.receipt_id,),
            )
            parent_meta = cur.fetchone() or (False, "", False, "")
            parent_is_paper_verified = bool(parent_meta[0])
            parent_review_status = str(parent_meta[1] or "").strip().lower()
            parent_verified_by_edit = bool(parent_meta[2])
            parent_verified_by_user = str(parent_meta[3] or "").strip()

            # Linkage columns that must survive a split. The original receipt
            # is kept as the first split line and every additional line
            # inherits these links instead of losing them.
            linkage_columns = [
                col
                for col in (
                    "reserve_number",
                    "charter_id",
                    "employee_id",
                    "vehicle_id",
                    "vehicle_number",
                    "vendor_account_id",
                    "vendor_invoice_id",
                    "fiscal_year",
                    "invoice_date",
                    "card_type",
                    "card_number",
                    "mapped_bank_account_id",
                    "receipt_source",
                    "source_system",
                    "is_driver_reimbursement",
                    "odometer_reading",
                )
                if col in self.receipts_columns
            ]
            parent_linkage: dict = {}
            if linkage_columns:
                cur.execute(
                    f"SELECT {', '.join(linkage_columns)} "
                    "FROM receipts WHERE receipt_id = %s",
                    (self.receipt_id,),
                )
                linkage_row = cur.fetchone() or ()
                parent_linkage = dict(zip(linkage_columns, linkage_row))

            # Capture existing banking links on the parent so we can carry
            # them forward to child split receipts instead of dropping
            # reconciliation context.
            cur.execute(
                """
                SELECT transaction_id, COALESCE(linked_amount, 0)
                FROM receipt_banking_links
                WHERE receipt_id = %s
                ORDER BY linked_amount DESC, transaction_id DESC
                """,
                (self.receipt_id,),
            )
            parent_links = [
                (int(row[0]), float(row[1] or 0)) for row in (cur.fetchall() or [])
            ]
            if not parent_links:
                cur.execute(
                    """
                    SELECT transaction_id,
                           COALESCE(debit_amount, credit_amount, 0) AS linked_amount
                    FROM banking_transactions
                    WHERE receipt_id = %s
                    ORDER BY linked_amount DESC, transaction_id DESC
                    """,
                    (self.receipt_id,),
                )
                parent_links = [
                    (int(row[0]), float(row[1] or 0))
                    for row in (cur.fetchall() or [])
                ]

            # Create child receipts for each split
            child_count = 0
            child_ids = []
            child_rows: list[dict] = []
            remapped_link_count = 0
            ambiguous_link_count = 0
            parent_gst_total = float(self.receipt_data.get("gst_amount") or 0)
            allocated_gst = 0.0

            valid_row_indices: list[int] = []
            for r in range(self.splits_table.rowCount()):
                gl_widget = self.splits_table.cellWidget(r, 0)
                gl_display = (
                    gl_widget.currentText().strip() if gl_widget else ""
                )
                gl = (
                    gl_display.split(" - ")[0].strip()
                    if " - " in gl_display
                    else gl_display
                )
                amt_widget = self.splits_table.cellWidget(r, 1)
                amt = (
                    amt_widget.value()
                    if isinstance(amt_widget, QDoubleSpinBox)
                    else 0.0
                )
                if gl and abs(amt) >= 0.005:
                    valid_row_indices.append(r)

            for index, r in enumerate(valid_row_indices):
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
                    (
                        method_widget.currentData()
                        or normalize_payment_method(
                            method_widget.currentText()
                        )
                    )
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

                if gl and abs(amt) >= 0.005:
                    try:
                        line_gst = self._row_line_gst(r)
                        if line_gst is None:
                            line_gst = 0.0
                        # Stored gross is always GST-inclusive. 'Added' lines
                        # were entered pre-tax, so fold the GST in.
                        gross_amt = round(
                            amt + line_gst
                            if self._row_gst_mode(r) == "Added"
                            else amt,
                            2,
                        )

                        insert_cols = [
                            "receipt_date",
                            "vendor_name",
                            "gross_amount",
                            "gl_account_code",
                            "description",
                            "payment_method",
                            "split_group_id",
                            "is_split_receipt",
                            "split_group_total",
                            "business_personal",
                        ]
                        insert_vals = [
                            self.receipt_data["date"],
                            self.receipt_data["vendor"],
                            gross_amt,
                            gl,
                            (
                                self.receipt_data.get("desc", "").strip()
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
                        ]

                        method_lower = str(payment_method or "").strip().lower()
                        child_is_no_receipt = (
                            method_lower == "no_receipt_available"
                        )
                        child_is_paper_verified = (
                            parent_is_paper_verified and not child_is_no_receipt
                        )
                        if child_is_no_receipt:
                            child_review_status = "missing"
                        elif parent_review_status in (
                            "verified",
                            "missing",
                            "unreadable",
                            "data-error",
                        ):
                            child_review_status = parent_review_status
                        else:
                            child_review_status = (
                                "verified" if child_is_paper_verified else ""
                            )

                        if "gst_amount" in self.receipts_columns:
                            insert_cols.append("gst_amount")
                            insert_vals.append(line_gst)
                        if "source_reference" in self.receipts_columns:
                            insert_cols.append("source_reference")
                            insert_vals.append(
                                self.receipt_data.get("source_reference")
                            )
                        if "is_paper_verified" in self.receipts_columns:
                            insert_cols.append("is_paper_verified")
                            insert_vals.append(child_is_paper_verified)
                        if "receipt_review_status" in self.receipts_columns:
                            insert_cols.append("receipt_review_status")
                            insert_vals.append(child_review_status or None)
                        if "verified_by_edit" in self.receipts_columns:
                            insert_cols.append("verified_by_edit")
                            insert_vals.append(parent_verified_by_edit)
                        if "verified_by_user" in self.receipts_columns:
                            insert_cols.append("verified_by_user")
                            insert_vals.append(
                                parent_verified_by_user or "desktop_app_split"
                            )
                        if "is_verified_banking" in self.receipts_columns:
                            insert_cols.append("is_verified_banking")
                            insert_vals.append(False)
                        if "gst_exempt" in self.receipts_columns:
                            insert_cols.append("gst_exempt")
                            insert_vals.append(self._row_is_no_gst(r))

                        for link_col, link_val in parent_linkage.items():
                            if link_col not in insert_cols:
                                insert_cols.append(link_col)
                                insert_vals.append(link_val)

                        if index == 0:
                            # Keep the original receipt as the first split line
                            # so charter/vehicle/driver/banking links survive.
                            set_cols = [
                                c
                                for c in insert_cols
                                if c not in parent_linkage
                            ]
                            set_vals = [
                                insert_vals[insert_cols.index(c)]
                                for c in set_cols
                            ]
                            assignments = ", ".join(
                                f"{c} = %s" for c in set_cols
                            )
                            if "net_amount" in self.receipts_columns:
                                assignments += ", net_amount = %s"
                                set_vals.append(round(gross_amt - line_gst, 2))
                            if "split_status" in self.receipts_columns:
                                assignments += ", split_status = 'single'"
                            if "updated_at" in self.receipts_columns:
                                assignments += ", updated_at = NOW()"
                            cur.execute(
                                f"UPDATE receipts SET {assignments} "
                                "WHERE receipt_id = %s",
                                tuple(set_vals) + (self.receipt_id,),
                            )
                            child_id = self.receipt_id
                        else:
                            # Additional split lines are new receipts that
                            # inherit the original receipt's linkage.
                            placeholders = ", ".join(["%s"] * len(insert_vals))
                            cur.execute(
                                f"INSERT INTO receipts "
                                f"({', '.join(insert_cols)}) "
                                f"VALUES ({placeholders}) RETURNING receipt_id",
                                tuple(insert_vals),
                            )
                            child_id = cur.fetchone()[0]

                        child_count += 1
                        child_ids.append(child_id)
                        child_rows.append(
                            {
                                "receipt_id": int(child_id),
                                "amount": float(gross_amt),
                            }
                        )

                        cur.execute(
                            "DELETE FROM receipt_gl_splits WHERE receipt_id = %s",
                            (child_id,),
                        )

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
                                gross_amt,
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

            # Re-link any parent banking matches onto child receipts.
            if parent_links and child_rows:
                # Clear the original links first so remapping cannot leave a
                # transaction attached to both the original line and another.
                cur.execute(
                    "DELETE FROM receipt_banking_links WHERE receipt_id = %s",
                    (self.receipt_id,),
                )
                remaining_by_child = {
                    c["receipt_id"]: float(c["amount"]) for c in child_rows
                }
                links_by_child: dict[int, list[tuple[int, float]]] = {
                    c["receipt_id"]: [] for c in child_rows
                }

                for txn_id, linked_amount in parent_links:
                    eligible = [
                        cid
                        for cid, rem in remaining_by_child.items()
                        if rem >= (linked_amount - 0.01)
                    ]
                    if eligible:
                        best_child = min(
                            eligible,
                            key=lambda cid, target=linked_amount: abs(
                                remaining_by_child[cid] - target
                            ),
                        )
                    else:
                        ambiguous_link_count += 1
                        best_child = max(
                            remaining_by_child,
                            key=lambda cid: remaining_by_child[cid],
                        )

                    links_by_child[best_child].append((txn_id, linked_amount))
                    remapped_link_count += 1
                    remaining_by_child[best_child] = max(
                        0.0,
                        remaining_by_child[best_child] - linked_amount,
                    )

                for child_id, child_links in links_by_child.items():
                    if not child_links:
                        if "is_verified_banking" in self.receipts_columns:
                            cur.execute(
                                """
                                UPDATE receipts
                                SET is_verified_banking = FALSE
                                WHERE receipt_id = %s
                                """,
                                (child_id,),
                            )
                        continue
                    for txn_id, linked_amount in child_links:
                        cur.execute(
                            """
                            INSERT INTO receipt_banking_links
                            (receipt_id, transaction_id, linked_amount,
                             link_status, linked_at)
                            VALUES (%s, %s, %s, 'matched', NOW())
                            ON CONFLICT (receipt_id, transaction_id) DO UPDATE
                            SET linked_amount = %s,
                                link_status = 'matched',
                                linked_at = NOW()
                            """,
                            (
                                child_id,
                                txn_id,
                                linked_amount,
                                linked_amount,
                            ),
                        )
                        cur.execute(
                            """
                            UPDATE banking_transactions
                            SET receipt_id = %s,
                                reconciliation_status = 'matched'
                            WHERE transaction_id = %s
                            """,
                            (child_id, txn_id),
                        )

                    if "banking_transaction_id" in self.receipts_columns:
                        primary_txn_id = child_links[0][0]
                        cur.execute(
                            """
                            UPDATE receipts
                            SET banking_transaction_id = %s
                            WHERE receipt_id = %s
                            """,
                            (primary_txn_id, child_id),
                        )
                    if "is_verified_banking" in self.receipts_columns:
                        cur.execute(
                            """
                            UPDATE receipts
                            SET is_verified_banking = TRUE
                            WHERE receipt_id = %s
                            """,
                            (child_id,),
                        )

            # Transactional integrity gate: do not commit inconsistent split
            # outcomes.
            child_total = sum(float(c["amount"]) for c in child_rows)
            if abs(child_total - float(original_total or 0)) > 0.02:
                raise ValueError(
                    "Split integrity failure: child amount sum "
                    f"{child_total:.2f} != original total "
                    f"{float(original_total or 0):.2f}"
                )

            if (
                "gst_amount" in self.receipts_columns
                and abs(parent_gst_total) > 0
            ):
                cur.execute(
                    """
                    SELECT COALESCE(SUM(gst_amount), 0)
                    FROM receipts
                    WHERE receipt_id = ANY(%s)
                    """,
                    (child_ids,),
                )
                child_gst_total = float((cur.fetchone() or [0])[0] or 0)
                if abs(child_gst_total - parent_gst_total) > 0.02:
                    # Manual per-line GST overrides are authoritative: the
                    # printed receipt wins over the prorated estimate.
                    logger.info(
                        "Split GST adjusted from %.2f to %.2f from per-line "
                        "entries",
                        parent_gst_total,
                        child_gst_total,
                    )
            if parent_links:
                txn_ids = [txn_id for txn_id, _ in parent_links]
                cur.execute(
                    """
                    SELECT l.transaction_id, COUNT(DISTINCT l.receipt_id)
                    FROM receipt_banking_links l
                    WHERE l.receipt_id = ANY(%s)
                      AND l.transaction_id = ANY(%s)
                    GROUP BY l.transaction_id
                    HAVING COUNT(DISTINCT l.receipt_id) > 1
                    """,
                    (child_ids, txn_ids),
                )
                duplicate_txn_links = cur.fetchall() or []
                if duplicate_txn_links:
                    raise ValueError(
                        "Split banking integrity failure: duplicate "
                        "transaction-to-child mappings detected "
                        f"{duplicate_txn_links}"
                    )

            # The original receipt is retained as the first split line, so no
            # parent deletion happens here. Its charter/vehicle/driver and
            # banking links stay intact.

            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "Success",
                f"✅ Receipt #{self.receipt_id} split into {child_count} "
                f"linked receipts!\n\n"
                f"Split receipts: "
                f"{', '.join(f'#{cid}' for cid in child_ids)}\n"
                f"All share Group ID {split_group_id}\n\n"
                f"Original receipt #{self.receipt_id} was kept as the first "
                "split line, so its charter, vehicle, driver and banking "
                "links are preserved.\n\n"
                "✅ Existing banking links were remapped to split lines where "
                "possible.\n"
                f"🔗 Remapped links: "
                f"{remapped_link_count}"
                f" | Ambiguous assignments: "
                f"{ambiguous_link_count}\n"
                "⚠️  Review the Bank Match tab if ambiguous assignments are "
                "non-zero.\n\n"
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
