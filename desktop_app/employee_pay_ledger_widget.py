"""
Employee Pay Ledger Widget
--------------------------
Shows a "verified pay vs actual payments" ledger for a selected
employee + period.

Left side  : Calculated/verified pay from employee_pay_master (gross,
deductions, net).
Right side : Physical payments actually made (employee_pay_transactions table).
             Each row: date | method | CHQ# | pay type | amount | notes |
             receipt link
Bottom row: Running total of payments vs net pay → highlights over/under.

Sits inside payroll_entry_widget as a collapsible group below Pay Event.
Does NOT touch the locked employee_pay_master record.
"""

import logging
from datetime import date as dateobj

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

PAYMENT_METHODS = ["CASH", "CHQ", "E-TRANSFER", "DIRECT_DEPOSIT", "OTHER"]
PAY_TYPES = [
    "REGULAR_PAY",
    "REIMBURSEMENT",
    "ADVANCE",
    "FLOAT",
    "PARTIAL_PAY",
    "BONUS",
]
PAY_TYPE_LABELS = {
    "REGULAR_PAY": "Regular Pay",
    "REIMBURSEMENT": "Reimbursement",
    "ADVANCE": "Advance",
    "FLOAT": "Float",
    "PARTIAL_PAY": "Partial Pay",
    "BONUS": "Bonus",
}
METHOD_LABELS = {
    "CASH": "💵 Cash",
    "CHQ": "📝 Cheque",
    "E-TRANSFER": "📲 E-Transfer",
    "DIRECT_DEPOSIT": "🏦 Direct Dep.",
    "OTHER": "Other",
}


# ---------------------------------------------------------------------------
# Receipt picker dialog (lightweight)
# ---------------------------------------------------------------------------
class _ReceiptPickerDialog(QDialog):
    """Small dialog to search and select an ALMS receipt to link."""

    def __init__(self, conn, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.selected_receipt_id = None
        self.selected_receipt_label = ""
        self.setWindowTitle("Link Receipt")
        self.setMinimumWidth(700)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Vendor:"))
        self.vendor_edit = QLineEdit()
        self.vendor_edit.setPlaceholderText("e.g. Shell, Centex…")
        self.vendor_edit.setMaximumWidth(160)
        filter_row.addWidget(self.vendor_edit)

        filter_row.addWidget(QLabel("Date from:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-2))
        self.date_from.setMaximumWidth(110)
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("to:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setMaximumWidth(110)
        filter_row.addWidget(self.date_to)

        search_btn = QPushButton("🔍 Search")
        search_btn.clicked.connect(self._search)
        filter_row.addWidget(search_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Receipt ID", "Date", "Vendor", "Amount", "Description"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.accept)
        layout.addWidget(self.table)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._search()

    def _search(self) -> None:
        vendor = self.vendor_edit.text().strip()
        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()

        sql = [
            "SELECT receipt_id, receipt_date, vendor_name, gross_amount,"
            "COALESCE(description,'') "
            "FROM receipts WHERE receipt_date BETWEEN %s AND %s"
        ]
        params = [d_from, d_to]
        if vendor:
            sql.append("AND LOWER(vendor_name) ILIKE %s")
            params.append(f"%{vendor.lower()}%")
        sql.append("ORDER BY receipt_date DESC LIMIT 200")

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(" ".join(sql), params)
                rows = cur.fetchall()
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                rid, rdate, vendor_name, amount, desc = row
                self.table.setItem(r, 0, QTableWidgetItem(str(rid)))
                self.table.setItem(r, 1, QTableWidgetItem(str(rdate)))
                self.table.setItem(r, 2, QTableWidgetItem(vendor_name or ""))
                amt_item = QTableWidgetItem(f"${float(amount or 0):,.2f}")
                amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                self.table.setItem(r, 3, amt_item)
                self.table.setItem(r, 4, QTableWidgetItem(desc[:80]))
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Search failed: {exc}")

    def _on_accept(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "No Selection", "Select a receipt first."
            )
            return
        rid = int(self.table.item(row, 0).text())
        rdate = self.table.item(row, 1).text()
        vendor_name = self.table.item(row, 2).text()
        amount = self.table.item(row, 3).text()
        self.selected_receipt_id = rid
        self.selected_receipt_label = (
            f"#{rid}   {rdate}   {vendor_name}   {amount}"
        )
        self.accept()


# ---------------------------------------------------------------------------
# Add / Edit transaction dialog
# ---------------------------------------------------------------------------
class _PayTransactionDialog(QDialog):
    """Dialog to add or edit a single pay transaction row."""

    def __init__(
        self,
        conn,
        employee_id,
        fiscal_year,
        pay_period_id,
        existing=None,
        parent=None,
    ) -> None:
        """
        existing: dict with existing row data for edit mode, or None for add.
        """
        super().__init__(parent)
        self.conn = conn
        self.employee_id = employee_id
        self.fiscal_year = fiscal_year
        self.pay_period_id = pay_period_id
        self.existing = existing or {}
        self._receipt_id = self.existing.get("receipt_id")
        self.setWindowTitle("Edit Payment" if existing else "Add Payment")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        if self.existing.get("transaction_date"):
            d = self.existing["transaction_date"]
            if isinstance(d, dateobj):
                self.date_edit.setDate(QDate(d.year, d.month, d.day))
            else:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        form.addRow("Date:", self.date_edit)

        # Amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("$")
        self.amount_spin.setValue(float(self.existing.get("amount") or 0))
        form.addRow("Amount:", self.amount_spin)

        # Payment method
        self.method_combo = QComboBox()
        for m in PAYMENT_METHODS:
            self.method_combo.addItem(METHOD_LABELS.get(m, m), m)
        current_method = self.existing.get("payment_method", "CASH")
        idx = (
            PAYMENT_METHODS.index(current_method)
            if current_method in PAYMENT_METHODS
            else 0
        )
        self.method_combo.setCurrentIndex(idx)
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        form.addRow("Method:", self.method_combo)

        # Cheque number (shown only for CHQ)
        self.chq_label = QLabel("Cheque #:")
        self.chq_edit = QLineEdit()
        self.chq_edit.setPlaceholderText("e.g. 347")
        self.chq_edit.setMaximumWidth(120)
        self.chq_edit.setText(self.existing.get("cheque_number") or "")
        form.addRow(self.chq_label, self.chq_edit)

        # Pay type
        self.type_combo = QComboBox()
        for pt in PAY_TYPES:
            self.type_combo.addItem(PAY_TYPE_LABELS.get(pt, pt), pt)
        current_type = self.existing.get("pay_type", "REGULAR_PAY")
        idx = PAY_TYPES.index(current_type) if current_type in PAY_TYPES else 0
        self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Pay Type:", self.type_combo)

        # Receipt link (shown for REIMBURSEMENT)
        self.receipt_label = QLabel("Link Receipt:")
        receipt_row = QHBoxLayout()
        self.receipt_display = QLineEdit()
        self.receipt_display.setReadOnly(True)
        self.receipt_display.setPlaceholderText("No receipt linked")
        if self._receipt_id:
            self.receipt_display.setText(f"Receipt #{self._receipt_id}")
        receipt_row.addWidget(self.receipt_display)
        pick_btn = QPushButton("🔍 Pick…")
        pick_btn.setMaximumWidth(70)
        pick_btn.clicked.connect(self._pick_receipt)
        receipt_row.addWidget(pick_btn)
        clear_btn = QPushButton("✕")
        clear_btn.setMaximumWidth(30)
        clear_btn.clicked.connect(self._clear_receipt)
        clear_btn.setToolTip("Remove receipt link")
        receipt_row.addWidget(clear_btn)
        receipt_container = QWidget()
        receipt_container.setLayout(receipt_row)
        form.addRow(self.receipt_label, receipt_container)

        # Notes
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional notes")
        self.notes_edit.setText(self.existing.get("notes") or "")
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # Apply initial state
        self._on_method_changed()
        self._on_type_changed()

    def _on_method_changed(self) -> None:
        is_chq = self.method_combo.currentData() == "CHQ"
        self.chq_label.setVisible(is_chq)
        self.chq_edit.setVisible(is_chq)

    def _on_type_changed(self) -> None:
        is_reimb = self.type_combo.currentData() == "REIMBURSEMENT"
        self.receipt_label.setVisible(is_reimb)
        (
            self.receipt_label.parent()
            .layout()
            .labelForField(
                self.receipt_label.parent()
                .layout()
                .itemAt(
                    self.receipt_label.parent()
                    .layout()
                    .indexOf(self.receipt_label)
                )
                .widget()
                if False
                else None
            )
            if False
            else None
        )  # visibility handled via form row below
        # Simpler: just show/hide the row widget
        for i in range(self.receipt_label.parent().layout().rowCount()):
            pass  # skip complex form row hide; use setVisible on both widgets
        self.receipt_label.setVisible(is_reimb)
        # find the receipt container widget in the form
        form_layout = self.receipt_label.parent().layout()
        if hasattr(form_layout, "itemAt"):
            for i in range(form_layout.count()):
                item = form_layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if (
                        hasattr(w, "layout")
                        and w.layout()
                        and w.layout().count() > 0
                    ):
                        # check if any child is self.receipt_display
                        for j in range(w.layout().count()):
                            child = w.layout().itemAt(j)
                            if (
                                child
                                and child.widget() == self.receipt_display
                            ):
                                w.setVisible(is_reimb)
                                break

    def _pick_receipt(self) -> None:
        dlg = _ReceiptPickerDialog(self.conn, parent=self)
        if (
            dlg.exec() == QDialog.DialogCode.Accepted
            and dlg.selected_receipt_id
        ):
            self._receipt_id = dlg.selected_receipt_id
            self.receipt_display.setText(dlg.selected_receipt_label)

    def _clear_receipt(self) -> None:
        self._receipt_id = None
        self.receipt_display.clear()

    def _validate_and_accept(self) -> None:
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(
                self, "Validation", "Amount must be greater than zero."
            )
            return
        self.accept()

    def get_data(self) -> object:
        return {
            "transaction_date": self.date_edit.date().toPyDate(),
            "amount": round(self.amount_spin.value(), 2),
            "payment_method": self.method_combo.currentData(),
            "cheque_number": self.chq_edit.text().strip() or None,
            "pay_type": self.type_combo.currentData(),
            "receipt_id": self._receipt_id,
            "notes": self.notes_edit.text().strip() or None,
        }


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------
class EmployeePayLedgerWidget(QGroupBox):
    """
    'Pay Verification' group — shows calculated net pay
    vs actual payments made.
    Embed in payroll_entry_widget below the Pay Event group.

    Call refresh(employee_id, fiscal_year, pay_period_id, net_pay) whenever
    the employee or pay period selection changes.
    """

    def __init__(self, db, parent=None) -> None:
        super().__init__(
            "💳 Pay Verification — Calculated vs Actual Payments", parent
        )
        self.db = db
        self._employee_id = None
        self._fiscal_year = None
        self._pay_period_id = None
        self._net_pay = 0.0
        self._editing_tx_id = (
            None  # transaction_id currently selected for edit
        )
        self._build_ui()
        self._ensure_table()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Header summary bar ---
        summary_row = QHBoxLayout()
        summary_row.addWidget(QLabel("<b>Calculated Net Pay:</b>"))
        self.lbl_net_pay = QLabel("$0.00")
        self.lbl_net_pay.setStyleSheet(
            "font-weight: bold; color: #1e40af; font-size: 11pt;"
        )
        summary_row.addWidget(self.lbl_net_pay)

        summary_row.addSpacing(30)
        summary_row.addWidget(QLabel("<b>Total Paid:</b>"))
        self.lbl_total_paid = QLabel("$0.00")
        self.lbl_total_paid.setStyleSheet(
            "font-weight: bold; color: #059669; font-size: 11pt;"
        )
        summary_row.addWidget(self.lbl_total_paid)

        summary_row.addSpacing(30)
        summary_row.addWidget(QLabel("<b>Difference:</b>"))
        self.lbl_diff = QLabel("$0.00")
        self.lbl_diff.setStyleSheet("font-weight: bold; font-size: 11pt;")
        summary_row.addWidget(self.lbl_diff)

        summary_row.addStretch()

        # Year-total toggle
        self.chk_show_year = QCheckBox("Show full year")
        self.chk_show_year.setToolTip(
            "Toggle between this pay period only vs all payments for the year"
        )
        self.chk_show_year.stateChanged.connect(self._reload)
        summary_row.addWidget(self.chk_show_year)
        layout.addLayout(summary_row)

        # --- Payments table ---
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Method", "CHQ #", "Type", "Amount", "Notes", "Receipt"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(140)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.table)

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("➕ Add Payment")
        self.add_btn.setStyleSheet("background-color: #2563eb; color: white;")
        self.add_btn.clicked.connect(self._add_payment)
        btn_row.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Edit Selected")
        self.edit_btn.clicked.connect(self._edit_payment)
        btn_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.setStyleSheet("color: #dc2626;")
        self.delete_btn.clicked.connect(self._delete_payment)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._reload)
        btn_row.addWidget(refresh_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _ensure_table(self) -> None:
        """Create table if it doesn't exist yet (idempotent)."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS employee_pay_transactions (
                        transaction_id   SERIAL PRIMARY KEY,
                        employee_id      INTEGER NOT NULL,
                        fiscal_year      INTEGER NOT NULL,
                        pay_period_id    INTEGER,
                        transaction_date DATE NOT NULL,
                        amount           NUMERIC(10,2) NOT NULL,
                        payment_method   VARCHAR(30) NOT NULL DEFAULT 'CASH',
                        cheque_number    VARCHAR(30),
                        pay_type         VARCHAR(30) NOT NULL
                            DEFAULT 'REGULAR_PAY',
                        receipt_id       INTEGER,
                        notes            TEXT,
                        created_at       TIMESTAMP DEFAULT NOW(),
                        created_by       VARCHAR(60) DEFAULT 'desktop_app'
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ept_emp_year
                    ON employee_pay_transactions(employee_id, fiscal_year)
                """)
        except Exception as exc:
            logger.warning(
                f"Could not ensure employee_pay_transactions: {exc}"
            )

    def _get_tx_id_at_row(self, row) -> object:
        """Return the hidden transaction_id stored in column 0 user data."""
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self, employee_id, fiscal_year, pay_period_id, net_pay) -> None:
        """Call this when employee/period selection changes in the parent"
        "widget."""

        self._employee_id = employee_id
        self._fiscal_year = fiscal_year
        self._pay_period_id = pay_period_id
        self._net_pay = float(net_pay or 0)
        self.lbl_net_pay.setText(f"${self._net_pay:,.2f}")
        self._reload()

    # ------------------------------------------------------------------
    # Load / display
    # ------------------------------------------------------------------
    def _reload(self) -> None:
        if not self._employee_id or not self._fiscal_year:
            self.table.setRowCount(0)
            self._update_totals([])
            return

        show_year = self.chk_show_year.isChecked()
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if show_year:
                    cur.execute(
                        """
                        SELECT transaction_id, transaction_date,
                        payment_method,
                               cheque_number, pay_type, amount, notes,
                               receipt_id
                        FROM employee_pay_transactions
                        WHERE employee_id = %s AND fiscal_year = %s
                        ORDER BY transaction_date, transaction_id
                    """,
                        (self._employee_id, self._fiscal_year),
                    )
                else:
                    if self._pay_period_id:
                        cur.execute(
                            """
                            SELECT transaction_id, transaction_date,
                            payment_method,
                                   cheque_number, pay_type, amount, notes,
                                   receipt_id
                            FROM employee_pay_transactions
                            WHERE employee_id = %s
                              AND pay_period_id = %s
                            ORDER BY transaction_date, transaction_id
                        """,
                            (self._employee_id, self._pay_period_id),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT transaction_id, transaction_date,
                            payment_method,
                                   cheque_number, pay_type, amount, notes,
                                   receipt_id
                            FROM employee_pay_transactions
                            WHERE employee_id = %s AND fiscal_year = %s
                            ORDER BY transaction_date, transaction_id
                        """,
                            (self._employee_id, self._fiscal_year),
                        )
                rows = cur.fetchall()
        except Exception as exc:
            logger.error(f"Failed to load pay transactions: {exc}")
            return

        self.table.setRowCount(len(rows))
        amounts = []
        for r, row in enumerate(rows):
            (
                tx_id,
                tx_date,
                method,
                chq,
                pay_type,
                amount,
                notes,
                receipt_id,
            ) = row
            amount_f = float(amount or 0)
            amounts.append(amount_f)

            # Col 0 — Date (carries hidden tx_id)
            date_item = QTableWidgetItem(str(tx_date or ""))
            date_item.setData(Qt.ItemDataRole.UserRole, tx_id)
            self.table.setItem(r, 0, date_item)

            # Col 1 — Method
            self.table.setItem(
                r, 1, QTableWidgetItem(METHOD_LABELS.get(method, method or ""))
            )

            # Col 2 — CHQ #
            self.table.setItem(r, 2, QTableWidgetItem(chq or ""))

            # Col 3 — Type (coloured)
            type_label = PAY_TYPE_LABELS.get(pay_type, pay_type or "")
            type_item = QTableWidgetItem(type_label)
            if pay_type == "REIMBURSEMENT":
                type_item.setForeground(QBrush(QColor("#b45309")))
            elif pay_type == "ADVANCE":
                type_item.setForeground(QBrush(QColor("#dc2626")))
            elif pay_type == "FLOAT":
                type_item.setForeground(QBrush(QColor("#7c3aed")))
            self.table.setItem(r, 3, type_item)

            # Col 4 — Amount
            amt_item = QTableWidgetItem(f"${amount_f:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 4, amt_item)

            # Col 5 — Notes
            self.table.setItem(r, 5, QTableWidgetItem(notes or ""))

            # Col 6 — Receipt link
            if receipt_id:
                rcpt_item = QTableWidgetItem(f"📎 #{receipt_id}")
                rcpt_item.setForeground(QBrush(QColor("#2563eb")))
            else:
                rcpt_item = QTableWidgetItem("")
            self.table.setItem(r, 6, rcpt_item)

        self._update_totals(amounts)

    def _update_totals(self, amounts) -> None:
        total_paid = sum(amounts)
        diff = self._net_pay - total_paid
        self.lbl_total_paid.setText(f"${total_paid:,.2f}")
        self.lbl_diff.setText(f"${diff:,.2f}")
        if abs(diff) < 0.01:
            self.lbl_diff.setStyleSheet(
                "font-weight: bold; color: #059669; font-size: 11pt;"
            )
        elif diff > 0:
            # Under-paid — still owed
            self.lbl_diff.setStyleSheet(
                "font-weight: bold; color: #d97706; font-size: 11pt;"
            )
        else:
            # Over-paid
            self.lbl_diff.setStyleSheet(
                "font-weight: bold; color: #dc2626; font-size: 11pt;"
            )

    # ------------------------------------------------------------------
    # Add / Edit / Delete
    # ------------------------------------------------------------------
    def _add_payment(self) -> None:
        if not self._employee_id:
            QMessageBox.warning(
                self, "No Employee", "Select an employee and pay period first."
            )
            return
        dlg = _PayTransactionDialog(
            self.db.conn if hasattr(self.db, "conn") else self.db,
            self._employee_id,
            self._fiscal_year,
            self._pay_period_id,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO employee_pay_transactions
                        (employee_id, fiscal_year, pay_period_id,
                         transaction_date, amount, payment_method,
                         cheque_number,
                         pay_type, receipt_id, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        self._employee_id,
                        self._fiscal_year,
                        self._pay_period_id,
                        data["transaction_date"],
                        data["amount"],
                        data["payment_method"],
                        data["cheque_number"],
                        data["pay_type"],
                        data["receipt_id"],
                        data["notes"],
                    ),
                )
            self._reload()
        except Exception as exc:
            logger.error(f"Failed to save pay transaction: {exc}")
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")

    def _edit_payment(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Edit", "Select a row to edit first."
            )
            return
        tx_id = self._get_tx_id_at_row(row)
        if not tx_id:
            return
        # Load existing record
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT transaction_id, transaction_date, amount,
                           payment_method, cheque_number, pay_type,
                           receipt_id, notes
                    FROM employee_pay_transactions
                    WHERE transaction_id = %s
                """,
                    (tx_id,),
                )
                rec = cur.fetchone()
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to load record:\n{exc}"
            )
            return
        if not rec:
            return
        existing = {
            "transaction_id": rec[0],
            "transaction_date": rec[1],
            "amount": rec[2],
            "payment_method": rec[3],
            "cheque_number": rec[4],
            "pay_type": rec[5],
            "receipt_id": rec[6],
            "notes": rec[7],
        }
        dlg = _PayTransactionDialog(
            self.db.conn if hasattr(self.db, "conn") else self.db,
            self._employee_id,
            self._fiscal_year,
            self._pay_period_id,
            existing=existing,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE employee_pay_transactions SET
                        transaction_date = %s,
                        amount           = %s,
                        payment_method   = %s,
                        cheque_number    = %s,
                        pay_type         = %s,
                        receipt_id       = %s,
                        notes            = %s
                    WHERE transaction_id = %s
                """,
                    (
                        data["transaction_date"],
                        data["amount"],
                        data["payment_method"],
                        data["cheque_number"],
                        data["pay_type"],
                        data["receipt_id"],
                        data["notes"],
                        tx_id,
                    ),
                )
            self._reload()
        except Exception as exc:
            logger.error(f"Failed to update pay transaction: {exc}")
            QMessageBox.critical(self, "Error", f"Failed to update:\n{exc}")

    def _delete_payment(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Delete", "Select a row to delete first."
            )
            return
        tx_id = self._get_tx_id_at_row(row)
        if not tx_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this payment entry? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM employee_pay_transactions "
                    "WHERE transaction_id = %s",
                    (tx_id,),
                )
            self._reload()
        except Exception as exc:
            logger.error(f"Failed to delete pay transaction: {exc}")
            QMessageBox.critical(self, "Error", f"Failed to delete:\n{exc}")
