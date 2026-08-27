"""
Vendor Invoice Management System
Comprehensive tool for managing vendor invoices, payments, and account balances

Features:
- Vendor-specific invoice pools with search
- Add/edit invoices with original dates
- Link payments to single or multiple invoices
- Track outstanding balances per vendor
- Handle multi-invoice statements
- Link banking transactions to invoice payments
- Manage invoice additions/fees (WCB late fees, etc.)
"""

import logging
from datetime import datetime
from decimal import Decimal

from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from vendor_lookup_widget import VendorLookupWidget

logger = logging.getLogger(__name__)


class CurrencyInput(QLineEdit):
    """Currency input field with validation (compact 6-digit max)"""

    def __init__(self, parent=None, compact=False) -> None:
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.compact = compact
        if compact:
            self.setMaxLength(10)  # "999999.99" = 9 chars
            self.setMaximumWidth(100)

    def focusInEvent(self, event) -> None:
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        self.selectAll()

    def mousePressEvent(self, event) -> None:
        """Select all on any mouse click - prevents cursor positioning"""
        # Don't call super first - we want selectAll to stick
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._format()

    def _format(self) -> None:
        text = self.text().replace(",", "").replace("$", "").strip()
        try:
            val = float(text)
            self.setText(f"{val:.2f}")
        except Exception:
            self.setText("0.00")

    def get_value(self) -> float:
        try:
            return float(self.text().replace(",", ""))
        except Exception:
            return 0.0


class SimpleCalculator(QDialog):
    """Simple calculator dialog with number pad"""

    def __init__(self, initial_value=0.0, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
        self.display_value = str(initial_value)
        self.pending_operation = None
        self.pending_value = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Display
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setText(self.display_value)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        display_font = QFont()
        display_font.setPointSize(18)
        display_font.setBold(True)
        self.display.setFont(display_font)
        self.display.setStyleSheet(
            "padding: 10px; background-color: #f0f0f0; "
            "border: 2px solid #333;"
        )
        layout.addWidget(self.display)

        # Button grid
        grid = QVBoxLayout()

        # Row 1: 7, 8, 9, ÷
        row1 = QHBoxLayout()
        for btn_text in ["7", "8", "9", "÷"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(
                lambda checked, t=btn_text: self._on_button_click(t)
            )
            row1.addWidget(btn)
        grid.addLayout(row1)

        # Row 2: 4, 5, 6, ×
        row2 = QHBoxLayout()
        for btn_text in ["4", "5", "6", "×"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(
                lambda checked, t=btn_text: self._on_button_click(t)
            )
            row2.addWidget(btn)
        grid.addLayout(row2)

        # Row 3: 1, 2, 3, −
        row3 = QHBoxLayout()
        for btn_text in ["1", "2", "3", "−"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(
                lambda checked, t=btn_text: self._on_button_click(t)
            )
            row3.addWidget(btn)
        grid.addLayout(row3)

        # Row 4: 0, ., =, +
        row4 = QHBoxLayout()
        zero_btn = QPushButton("0")
        zero_btn.setMinimumHeight(50)
        zero_btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
        zero_btn.clicked.connect(lambda checked: self._on_button_click("0"))
        row4.addWidget(zero_btn)

        dec_btn = QPushButton(".")
        dec_btn.setMinimumHeight(50)
        dec_btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
        dec_btn.clicked.connect(lambda checked: self._on_button_click("."))
        row4.addWidget(dec_btn)

        eq_btn = QPushButton("=")
        eq_btn.setMinimumHeight(50)
        eq_btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
        eq_btn.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold;"
        )
        eq_btn.clicked.connect(self._on_equals)
        row4.addWidget(eq_btn)

        plus_btn = QPushButton("+")
        plus_btn.setMinimumHeight(50)
        plus_btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
        plus_btn.clicked.connect(lambda checked: self._on_button_click("+"))
        row4.addWidget(plus_btn)

        grid.addLayout(row4)

        layout.addLayout(grid)

        # Clear and OK buttons
        bottom_row = QHBoxLayout()

        clear_btn = QPushButton("C (Clear)")
        clear_btn.setMinimumHeight(40)
        clear_btn.setStyleSheet(
            "background-color: #dc3545; color: white; font-weight: bold;"
        )
        clear_btn.clicked.connect(self._clear)
        bottom_row.addWidget(clear_btn)

        ok_btn = QPushButton("✓ OK")
        ok_btn.setMinimumHeight(40)
        ok_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold;"
        )
        ok_btn.clicked.connect(self.accept)
        bottom_row.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        layout.addLayout(bottom_row)

    def _on_button_click(self, text) -> None:
        """Handle number and operator button clicks"""
        if text in ["+", "−", "×", "÷"]:
            if self.display_value and self.display_value != "0":
                if self.pending_value is not None and self.pending_operation:
                    # Complete previous operation
                    self._calculate()
                self.pending_value = float(self.display_value)
                self.pending_operation = text
                self.display_value = ""
                self.display.setText("")
        elif text == ".":
            if "." not in self.display_value:
                if not self.display_value:
                    self.display_value = "0"
                self.display_value += "."
                self.display.setText(self.display_value)
        else:  # Number
            if self.display_value == "0" and text != "0":
                self.display_value = text
            else:
                self.display_value += text
            self.display.setText(self.display_value)

    def _calculate(self) -> None:
        """Perform pending calculation"""
        if self.pending_value is None or self.pending_operation is None:
            return

        try:
            current = float(self.display_value) if self.display_value else 0

            if self.pending_operation == "+":
                result = self.pending_value + current
            elif self.pending_operation == "−":
                result = self.pending_value - current
            elif self.pending_operation == "×":
                result = self.pending_value * current
            elif self.pending_operation == "÷":
                if current == 0:
                    self.display.setText("Error: Div by 0")
                    return
                result = self.pending_value / current
            else:
                result = current

            self.display_value = str(round(result, 2))
            self.display.setText(self.display_value)
            self.pending_value = None
            self.pending_operation = None
        except Exception:
            self.display.setText("Error")

    @pyqtSlot()
    def _on_equals(self) -> None:
        """Handle equals button"""
        self._calculate()

    @pyqtSlot()
    def _clear(self) -> None:
        """Clear calculator"""
        self.display_value = "0"
        self.pending_operation = None
        self.pending_value = None
        self.display.setText("0")

    def get_value(self) -> float:
        """Return the calculated value"""
        try:
            return float(self.display_value)
        except Exception:
            return 0.0


class CalculatorButton(QPushButton):
    """Quick calculator for currency amounts"""

    def __init__(self, target_field, parent=None) -> None:
        super().__init__(parent)
        self.setText("🧮")
        self.setMaximumWidth(35)
        self.setToolTip("Open calculator")
        self.target_field = target_field
        self.clicked.connect(self._open_calculator)

    def _open_calculator(self) -> None:
        """Open calculator dialog"""
        try:
            current = self.target_field.get_value()
            calc = SimpleCalculator(initial_value=current, parent=self)
            result = calc.exec()
            if result == 1:  # Accepted in PyQt6
                value = calc.get_value()
                self.target_field.setText(f"{value:.2f}")
        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self,
                "Calculator Error",
                f"Error: {e!s}",
            )


class SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with optional sort key in UserRole.

    Uses `UserRole` as the sortable key for numeric/date sorting.
    """

    def __lt__(self, other) -> bool:
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)

        self_key = self.data(Qt.ItemDataRole.UserRole)
        other_key = other.data(Qt.ItemDataRole.UserRole)

        if self_key is not None and other_key is not None:
            return self_key < other_key

        return super().__lt__(other)


class MultiInvoicePaymentDialog(QDialog):
    """Dialog for allocating a single payment across multiple invoices"""

    def __init__(
        self,
        conn,
        vendor_name,
        payment_amount,
        available_invoices,
        parent=None,
        payment_method="check",
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.vendor_name = vendor_name
        self.payment_amount = payment_amount
        self.available_invoices = available_invoices
        self.payment_method = payment_method
        self.allocations = {}  # invoice_id -> allocated_amount

        self.setWindowTitle(f"Allocate Payment - {vendor_name}")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f"💰 Allocate ${self.payment_amount:,.2f} Payment Across Invoices"
        )
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 10px;"
        )
        layout.addWidget(header)

        # Vendor info
        vendor_label = QLabel(f"Vendor: {self.vendor_name}")
        vendor_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(vendor_label)

        # Invoice selection table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(7)
        self.invoice_table.setHorizontalHeaderLabels(
            [
                "Select",
                "Invoice #",
                "Date",
                "Amount",
                "Paid",
                "Balance Due",
                "To Pay",
            ]
        )
        self.invoice_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.invoice_table)

        # Allocation summary
        summary_group = QGroupBox("Payment Allocation Summary")
        summary_layout = QFormLayout()

        self.total_payment_label = QLabel(f"${self.payment_amount:,.2f}")
        self.total_payment_label.setStyleSheet("font-weight: bold;")
        summary_layout.addRow("Payment Amount:", self.total_payment_label)

        self.allocated_label = QLabel("$0.00")
        summary_layout.addRow("Allocated:", self.allocated_label)

        self.remaining_label = QLabel(f"${self.payment_amount:,.2f}")
        self.remaining_label.setStyleSheet("color: red; font-weight: bold;")
        summary_layout.addRow("Remaining:", self.remaining_label)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Auto-allocate button
        auto_btn = QPushButton("⚡ Auto-Allocate (Oldest First)")
        auto_btn.clicked.connect(self._auto_allocate)
        auto_btn.setStyleSheet(
            "background-color: #007bff; color: white; padding: 8px;"
        )
        layout.addWidget(auto_btn)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load invoices
        self._load_invoices()

    def _load_invoices(self) -> None:
        """Load available invoices with outstanding balances"""
        self.invoice_table.setRowCount(len(self.available_invoices))

        for idx, invoice in enumerate(self.available_invoices):
            # invoice = (
            #   receipt_id, ref, details, date, orig_amt, paid, balance, status
            # )
            (
                receipt_id,
                ref,
                _details,
                date,
                amount,
                paid,
                balance,
                status,
            ) = invoice

            # Checkbox
            check = QCheckBox()
            check.setChecked(False)
            check.stateChanged.connect(
                lambda state, row=idx: self._on_checkbox_changed(row, state)
            )
            self.invoice_table.setCellWidget(idx, 0, check)

            # Invoice #
            self.invoice_table.setItem(
                idx, 1, QTableWidgetItem(str(ref or f"R-{receipt_id}"))
            )

            # Date - standardize format to MM/dd/yyyy
            if isinstance(date, str):
                # Try to parse if it's a string
                try:
                    parsed_date = datetime.strptime(date, "%Y-%m-%d").strftime(
                        "%m/%d/%Y"
                    )
                except Exception:
                    parsed_date = date
            else:
                # If it's a date object
                parsed_date = (
                    date.strftime("%m/%d/%Y")
                    if hasattr(date, "strftime")
                    else str(date)
                )
            self.invoice_table.setItem(idx, 2, QTableWidgetItem(parsed_date))

            # Amount
            amt_item = QTableWidgetItem(f"${amount:,.2f}")
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.invoice_table.setItem(idx, 3, amt_item)

            # Paid
            paid_item = QTableWidgetItem(f"${paid:,.2f}")
            paid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.invoice_table.setItem(idx, 4, paid_item)

            # Balance
            bal_item = QTableWidgetItem(f"${balance:,.2f}")
            bal_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if balance > 0:
                bal_item.setForeground(QBrush(QColor("red")))
            self.invoice_table.setItem(idx, 5, bal_item)

            # To Pay (initially empty, filled during allocation)
            to_pay_item = QTableWidgetItem("$0.00")
            to_pay_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            to_pay_item.setFont(self._get_bold_font())
            self.invoice_table.setItem(idx, 6, to_pay_item)

    def _get_bold_font(self) -> QFont:
        """Get bold font"""
        font = QFont()
        font.setBold(True)
        return font

    def _on_checkbox_changed(self, row, state) -> None:
        """When checkbox changes, auto-allocate to that invoice"""
        invoice = self.available_invoices[row]
        receipt_id = invoice[0]
        balance = invoice[6]

        if state == Qt.CheckState.Checked.value:
            # Calculate how much we can allocate
            remaining = self._get_remaining()
            to_allocate = min(balance, remaining)
            self.allocations[receipt_id] = to_allocate

            # Update "To Pay" column
            to_pay_item = self.invoice_table.item(row, 6)
            to_pay_item.setText(f"${to_allocate:,.2f}")

            # Color code: green for full payment, yellow for partial
            row_color = (
                QColor("#c8e6c9")
                if to_allocate >= balance
                else QColor("#fff9c4")
            )
            for col in range(self.invoice_table.columnCount()):
                item = self.invoice_table.item(row, col)
                if item:
                    item.setBackground(QBrush(row_color))
        else:
            if receipt_id in self.allocations:
                del self.allocations[receipt_id]

            # Clear "To Pay" and reset background
            to_pay_item = self.invoice_table.item(row, 6)
            to_pay_item.setText("$0.00")

            for col in range(self.invoice_table.columnCount()):
                item = self.invoice_table.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor("white")))

        self._update_summary()

    @pyqtSlot()
    def _auto_allocate(self) -> None:
        """Auto-allocate payment to oldest invoices first.

        Full payment is prioritized.
        """
        self.allocations.clear()
        remaining = self.payment_amount

        # Clear all checkboxes and reset colors first
        for idx in range(len(self.available_invoices)):
            checkbox = self.invoice_table.cellWidget(idx, 0)
            if checkbox:
                checkbox.setChecked(False)
            # Reset background
            for col in range(self.invoice_table.columnCount()):
                item = self.invoice_table.item(idx, col)
                if item:
                    item.setBackground(QBrush(QColor("white")))
            # Clear To Pay
            to_pay = self.invoice_table.item(idx, 6)
            if to_pay:
                to_pay.setText("$0.00")

        # Sort by date (oldest first)
        sorted_invoices = sorted(self.available_invoices, key=lambda x: x[3])

        for invoice in sorted_invoices:
            balance = invoice[6]

            if remaining <= 0:
                break

            if balance > 0:
                orig_idx = self.available_invoices.index(invoice)
                checkbox = self.invoice_table.cellWidget(orig_idx, 0)
                if checkbox:
                    checkbox.setChecked(True)
                    remaining = self._get_remaining()

        self._update_summary()

    def _get_remaining(self) -> float:
        """Get remaining unallocated amount"""
        allocated = sum(self.allocations.values())
        return self.payment_amount - allocated

    def _update_summary(self) -> None:
        """Update allocation summary"""
        allocated = sum(self.allocations.values())
        remaining = self.payment_amount - allocated

        self.allocated_label.setText(f"${allocated:,.2f}")
        self.allocated_label.setStyleSheet(
            "color: green; font-weight: bold;" if allocated > 0 else ""
        )

        self.remaining_label.setText(f"${remaining:,.2f}")
        if abs(remaining) < 0.01:
            self.remaining_label.setStyleSheet(
                "color: green; font-weight: bold;"
            )
        elif remaining > 0:
            self.remaining_label.setStyleSheet(
                "color: orange; font-weight: bold;"
            )
        else:
            self.remaining_label.setStyleSheet(
                "color: red; font-weight: bold;"
            )

    def get_allocations(self) -> dict:
        """Return the allocation map"""
        return self.allocations


class VendorInvoiceManager(QWidget):
    """
    Main vendor invoice management interface
    """

    def __init__(self, db_connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = db_connection
        self.current_vendor = None
        self.current_invoices = []
        self.editing_receipt_id = None
        self.hide_auto_import_checkbox = None
        self._vendor_filter_cache = {}
        self._init_vendor_invoice_filters_table()
        self.init_ui()

    def _init_vendor_invoice_filters_table(self) -> None:
        """Create and seed DB-backed invoice vendor filters.

        Used for pseudo-vendor buckets.
        """
        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vendor_invoice_vendor_filters (
                        vendor_name VARCHAR(255) PRIMARY KEY,
                        include_in_invoice_manager BOOLEAN
                            NOT NULL DEFAULT TRUE,
                        reason TEXT,
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """)

                seed_rows = [
                    (
                        "WITHDRAWAL",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "CASH WITHDRAWAL",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "BANK WITHDRAWAL",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "LOAN PAYMENT",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "UNCATEGORIZED EXPENSE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "UNKNOWN PAYEE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "DEPOSIT",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "SQUARE DEPOSIT",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "EMAIL TRANSFER",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "E-TRANSFER PAYMENT",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "SERVICE CHARGE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "NSF CHARGE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "POINT OF SALE PURCHASE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "PURCHASE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "FUEL PURCHASE",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "DRIVER REIMBURSEMENT",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "CHARTER PAYMENT",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "BANK",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                    (
                        "CIBC",
                        False,
                        "Pseudo-vendor bucket (banking derived)",
                    ),
                ]

                cur.executemany(
                    """
                    INSERT INTO vendor_invoice_vendor_filters (
                        vendor_name,
                        include_in_invoice_manager,
                        reason
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (vendor_name) DO NOTHING
                    """,
                    seed_rows,
                )
        except Exception as e:
            logger.warning(
                "Failed to initialize vendor invoice filters table: " f"{e}"
            )

    def _is_vendor_included_by_db_filter(
        self, vendor_name: str | None
    ) -> bool:
        """Return inclusion decision from DB-backed filter table.

        Defaults to include.
        """
        normalized = (vendor_name or "").strip().upper()
        if not normalized:
            return True

        if normalized in self._vendor_filter_cache:
            return self._vendor_filter_cache[normalized]

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT include_in_invoice_manager
                    FROM vendor_invoice_vendor_filters
                    WHERE UPPER(vendor_name) = %s
                    LIMIT 1
                    """,
                    (normalized,),
                )
                row = cur.fetchone()

            # Keep prior safety behavior: if no explicit DB rule exists,
            # pseudo-vendor names remain excluded by default.
            included = (
                bool(row[0])
                if row
                else (not self._is_pseudo_vendor_name(normalized))
            )
            self._vendor_filter_cache[normalized] = included
            return included
        except Exception as e:
            logger.warning(
                f"Failed DB vendor filter lookup for {normalized}: {e}"
            )
            # Fallback to existing heuristic to stay safe if DB lookup fails
            return not self._is_pseudo_vendor_name(normalized)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Keep vendor selection and common actions in one compact top row.
        top_controls = QWidget()
        top_controls_layout = QHBoxLayout(top_controls)
        top_controls_layout.setContentsMargins(0, 0, 0, 0)
        top_controls_layout.setSpacing(6)

        vendor_controls = self._create_vendor_search()
        vendor_controls.setMinimumWidth(390)
        top_controls_layout.addWidget(vendor_controls, stretch=2)

        quick_actions = self._create_quick_actions()
        top_controls_layout.addWidget(quick_actions, stretch=3)
        top_controls_layout.addStretch(1)
        layout.addWidget(top_controls)

        # The invoice list uses the full width below the compact controls.
        invoice_panel = self._create_invoice_list()
        layout.addWidget(invoice_panel, stretch=4)

        # 3. Expandable details section
        self.details_tabs = QTabWidget()
        self.details_tabs.setMaximumHeight(280)
        self.details_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #ccc; } "
            "QTabBar::tab { padding: 8px 16px; font-size: 11px; "
            "font-weight: bold; }"
        )
        self.details_tabs.addTab(
            self._create_add_invoice_tab(), "➕ Add Invoice"
        )
        self.details_tabs.addTab(
            self._create_edit_invoice_tab(), "✏️ Edit Invoice"
        )
        self.details_tabs.addTab(
            self._create_payment_tab(), "💰 Apply Payment"
        )
        self.details_tabs.addTab(
            self._create_banking_link_tab(), "🏦 Banking Link"
        )
        self.ledger_tab_widget = self._create_ledger_tab()
        self.details_tabs.addTab(self.ledger_tab_widget, "📒 Ledger")
        self.details_tabs.addTab(
            self._create_account_summary_tab(), "📊 Summary"
        )

        layout.addWidget(self.details_tabs, stretch=1)

        # Trigger initial invoice load for vendor shown in combo at startup.
        QTimer.singleShot(0, self._load_initial_vendor)

    def _load_initial_vendor(self) -> None:
        """Load invoices for vendor already shown in combo at startup."""
        if self.current_vendor:
            return  # Already loaded via signal
        current_text = self.vendor_lookup.vendor_combo.currentText()
        if current_text:
            vendor_name = (
                current_text.split(" (")[0]
                if " (" in current_text
                else current_text
            )
            if vendor_name:
                self._on_vendor_selected(vendor_name)

    def _create_quick_actions(self) -> QWidget:
        """Quick action buttons for common tasks"""
        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        # Add invoice button
        add_invoice_btn = QPushButton("➕ Add")
        add_invoice_btn.setStyleSheet(
            "background-color: #28a745; color: white; padding: 4px 8px; "
            "font-weight: bold; font-size: 10px;"
        )
        add_invoice_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        add_invoice_btn.setFixedHeight(24)
        add_invoice_btn.setToolTip("Add a new invoice for the selected vendor")
        add_invoice_btn.clicked.connect(self._add_invoice)
        layout.addWidget(add_invoice_btn)

        # Edit selected invoice button
        edit_invoice_btn = QPushButton("✏️ Edit")
        edit_invoice_btn.setStyleSheet(
            "background-color: #fd7e14; color: white; padding: 4px 8px; "
            "font-weight: bold; font-size: 10px;"
        )
        edit_invoice_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        edit_invoice_btn.setFixedHeight(24)
        edit_invoice_btn.setToolTip("Select one invoice and edit its details")
        edit_invoice_btn.clicked.connect(self._edit_selected_invoice)
        layout.addWidget(edit_invoice_btn)

        # Pay single button
        pay_single_btn = QPushButton("💵 Pay")
        pay_single_btn.setStyleSheet(
            "background-color: #17a2b8; color: white; padding: 4px 8px; "
            "font-weight: bold; font-size: 10px;"
        )
        pay_single_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        pay_single_btn.setFixedHeight(24)
        pay_single_btn.setToolTip(
            "Select one invoice from table, fill payment details in "
            "'Apply Payment' tab, then click here"
        )
        pay_single_btn.clicked.connect(self._quick_pay_single)
        layout.addWidget(pay_single_btn)

        # Pay multiple button
        pay_multi_btn = QPushButton("💰 Multi")
        pay_multi_btn.setStyleSheet(
            "background-color: #6f42c1; color: white; padding: 4px 8px; "
            "font-weight: bold; font-size: 10px;"
        )
        pay_multi_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        pay_multi_btn.setFixedHeight(24)
        pay_multi_btn.setToolTip(
            "Select multiple invoices (Ctrl+Click), fill payment in "
            "'Apply Payment' tab, then click here"
        )
        pay_multi_btn.clicked.connect(self._quick_pay_multiple)
        layout.addWidget(pay_multi_btn)

        # View ledger button
        ledger_btn = QPushButton("📒 Ledger")
        ledger_btn.setStyleSheet(
            "background-color: #ffc107; color: black; padding: 4px 8px; "
            "font-weight: bold; font-size: 10px;"
        )
        ledger_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        ledger_btn.setFixedHeight(24)
        ledger_btn.setToolTip(
            "Open the chronological invoice/payment ledger editor"
        )
        ledger_btn.clicked.connect(self._open_ledger_editor)
        layout.addWidget(ledger_btn)

        return controls

    def _create_vendor_search(self) -> QWidget:
        """Vendor search and selection using verified vendor master list"""
        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        # Verified vendor lookup with fuzzy search and add-new support
        self.vendor_lookup = VendorLookupWidget(self.conn, self)
        self.vendor_lookup.vendorChanged.connect(self._on_vendor_selected)
        layout.addWidget(self.vendor_lookup)

        refresh_btn = QPushButton("🔄 Refresh Invoices")
        refresh_btn.setStyleSheet(
            "padding: 4px 8px; font-weight: bold; font-size: 11px;"
        )
        refresh_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        refresh_btn.setFixedHeight(24)
        refresh_btn.clicked.connect(self._refresh_current_vendor)
        layout.addWidget(refresh_btn)

        return controls

    def _create_invoice_list(self) -> QGroupBox:
        """Invoice list for selected vendor with inline editing"""
        group = QGroupBox()
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px; } "
            "QGroupBox::title { left: 6px; padding: 0 2px; }"
        )
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(5)

        # Vendor info and balance with Save button
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)

        self.vendor_header = QLabel("No vendor selected")
        self.vendor_header.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 0px;"
        )
        info_layout.addWidget(self.vendor_header, stretch=1)

        self.balance_label = QLabel("")
        self.balance_label.setStyleSheet(
            "font-size: 11px; padding: 0px; font-weight: bold;"
        )
        info_layout.addWidget(self.balance_label)

        # Save Changes button for direct edits
        self.save_changes_btn = QPushButton("💾 Save Changes")
        self.save_changes_btn.setStyleSheet(
            "background-color: #28a745; color: white; "
            "font-weight: bold; padding: 4px 8px; font-size: 10px;"
        )
        self.save_changes_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.save_changes_btn.setFixedSize(100, 24)
        self.save_changes_btn.clicked.connect(self._save_direct_edits)
        self.save_changes_btn.setEnabled(False)
        info_layout.addWidget(self.save_changes_btn)

        layout.addLayout(info_layout)

        # Filters section
        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            "QFrame { background-color: #f5f5f5; border: 1px solid #ddd; "
            "border-radius: 3px;}"
        )
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(5, 5, 5, 5)

        filter_layout.addWidget(QLabel("🔍 Filters:"))

        # Invoice number filter
        filter_layout.addWidget(QLabel("Invoice #:"))
        self.filter_invoice_num = QLineEdit()
        self.filter_invoice_num.setPlaceholderText("Search invoice #...")
        self.filter_invoice_num.setMaximumWidth(150)
        self.filter_invoice_num.textChanged.connect(
            self._apply_invoice_filters
        )
        filter_layout.addWidget(self.filter_invoice_num)

        lookup_btn = QPushButton("Find")
        lookup_btn.setMaximumWidth(60)
        lookup_btn.setToolTip("Jump to first visible invoice number match")
        lookup_btn.clicked.connect(self._lookup_invoice_number)
        filter_layout.addWidget(lookup_btn)

        self.filter_invoice_num.returnPressed.connect(
            self._lookup_invoice_number
        )

        # Year filter
        filter_layout.addWidget(QLabel("Year:"))
        self.filter_year = QComboBox()
        self.filter_year.addItem("All Years", None)
        # Add years from 2010 to current
        current_year = QDate.currentDate().year()
        for year in range(current_year, 2009, -1):
            self.filter_year.addItem(str(year), year)
        self.filter_year.setMaximumWidth(100)
        self.filter_year.currentIndexChanged.connect(
            self._apply_invoice_filters
        )
        filter_layout.addWidget(self.filter_year)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["All", "Paid", "Unpaid"])
        self.filter_status.setMaximumWidth(100)
        self.filter_status.currentIndexChanged.connect(
            self._apply_invoice_filters
        )
        filter_layout.addWidget(self.filter_status)

        self.hide_auto_import_checkbox = QCheckBox("Hide BANKING_IMPORT")
        self.hide_auto_import_checkbox.setChecked(True)
        self.hide_auto_import_checkbox.setToolTip(
            "Exclude auto-imported pseudo-invoices from the invoice manager "
            "view and balance calculation."
        )
        self.hide_auto_import_checkbox.stateChanged.connect(
            lambda _state: self._refresh_current_vendor()
        )
        filter_layout.addWidget(self.hide_auto_import_checkbox)

        self.hide_pseudo_vendor_checkbox = QCheckBox("Hide Pseudo Vendors")
        self.hide_pseudo_vendor_checkbox.setChecked(True)
        self.hide_pseudo_vendor_checkbox.setToolTip(
            "Exclude non-AP pseudo-vendor buckets like withdrawals, "
            "deposits, and auto-banking categories."
        )
        self.hide_pseudo_vendor_checkbox.stateChanged.connect(
            lambda _state: self._refresh_current_vendor()
        )
        filter_layout.addWidget(self.hide_pseudo_vendor_checkbox)

        # Clear filters button
        clear_filters_btn = QPushButton("❌ Clear")
        clear_filters_btn.setMaximumWidth(70)
        clear_filters_btn.clicked.connect(self._clear_invoice_filters)
        filter_layout.addWidget(clear_filters_btn)

        filter_layout.addStretch()

        layout.addWidget(filter_frame)

        # Invoice table - now includes running balance and is editable
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(10)
        self.invoice_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Invoice #",
                "Description",
                "Date",
                "Invoice Total",
                "Receipt Evidence",
                "Payments Made",
                "Running Balance",
                "Balance",
                "Status",
            ]
        )
        # Set specific column widths for better appearance
        header = self.invoice_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # ID
        self.invoice_table.setColumnWidth(0, 60)
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )  # Invoice # - editable
        self.invoice_table.setColumnWidth(1, 140)
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive
        )  # Description
        self.invoice_table.setColumnWidth(2, 260)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Date
        self.invoice_table.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Amount
        self.invoice_table.setColumnWidth(4, 110)
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.Fixed
        )  # Receipts
        self.invoice_table.setColumnWidth(5, 110)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)  # Paid
        self.invoice_table.setColumnWidth(6, 110)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)  # Balance
        self.invoice_table.setColumnWidth(7, 130)
        header.setSectionResizeMode(
            8, QHeaderView.ResizeMode.Fixed
        )  # Running Balance
        self.invoice_table.setColumnWidth(8, 110)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)  # Status
        self.invoice_table.setColumnWidth(9, 80)
        self.invoice_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.invoice_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.invoice_table.setAlternatingRowColors(True)
        self.invoice_table.setStyleSheet("QTableWidget { font-size: 11px;}")
        self.invoice_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.invoice_table.customContextMenuRequested.connect(
            self._show_invoice_context_menu
        )
        self.invoice_table.itemDoubleClicked.connect(
            self._on_invoice_double_clicked
        )
        self.invoice_table.itemSelectionChanged.connect(
            self._refresh_payment_history
        )
        # Enable inline editing
        self.invoice_table.itemChanged.connect(self._on_invoice_item_changed)
        # Keep invoice list in FIFO date order (oldest to newest).
        self.invoice_table.setSortingEnabled(False)
        layout.addWidget(self.invoice_table)

        hint = QLabel(
            "💡 Double-click Invoice # or Date to edit • Use Find for invoice "
            "lookup • Payments may be split across multiple invoices • Grid "
            "ordered oldest to newest"
        )
        hint.setStyleSheet(
            "font-size: 11px; color: #666; font-style: italic; padding: 5px; "
            "background-color: #f8f9fa;"
        )
        layout.addWidget(hint)

        return group

    def _create_add_invoice_tab(self) -> QWidget:
        """Tab for adding new invoices with split capability for fees"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Main form
        form = QFormLayout()

        # Date and Invoice# on same line (matching receipt layout)
        date_invoice_layout = QHBoxLayout()

        self.new_invoice_date = StandardDateEdit(prefer_month_text=True)
        self.new_invoice_date.setCalendarPopup(True)
        self.new_invoice_date.setDate(QDate.currentDate())
        self.new_invoice_date.setDisplayFormat("MM/dd/yyyy")
        self.new_invoice_date.setMaximumWidth(110)  # Shortened like receipt
        self.new_invoice_date.lineEdit().setClearButtonEnabled(True)
        date_invoice_layout.addWidget(QLabel("Date:"))
        date_invoice_layout.addWidget(self.new_invoice_date)

        self.new_invoice_num = QLineEdit()
        self.new_invoice_num.setPlaceholderText("Invoice #")
        self.new_invoice_num.setMaximumWidth(120)
        date_invoice_layout.addWidget(QLabel("Invoice #:"))
        date_invoice_layout.addWidget(self.new_invoice_num)
        date_invoice_layout.addStretch()

        form.addRow("", date_invoice_layout)

        # Amount (compact with calculator)
        amount_row = QHBoxLayout()
        self.new_invoice_amount = CurrencyInput(compact=True)
        amount_row.addWidget(self.new_invoice_amount, stretch=0)
        calc_btn = CalculatorButton(self.new_invoice_amount)
        amount_row.addWidget(calc_btn, stretch=0)
        amount_row.addStretch()
        form.addRow("Amount:", amount_row)

        # Description
        self.new_invoice_desc = QTextEdit()
        self.new_invoice_desc.setMaximumHeight(60)
        self.new_invoice_desc.setPlaceholderText("Optional description...")
        form.addRow("Description:", self.new_invoice_desc)

        # Category
        self.new_invoice_category = QComboBox()
        self.new_invoice_category.setEditable(True)
        self._load_categories(self.new_invoice_category)
        form.addRow("Category:", self.new_invoice_category)

        layout.addLayout(form)

        # Split fees section (for vendors like WCB with overdue fees)
        split_group = QGroupBox(
            "💳 Split Fees (Optional - for WCB overdue fees, "
            "CRA adjustments, etc.)"
        )
        split_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 10px;} "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px;}"
        )
        split_layout = QVBoxLayout()

        # Split checkbox
        self.new_invoice_use_split = QCheckBox(
            "Split this invoice into vendor charge + separate fee"
        )
        self.new_invoice_use_split.setToolTip(
            "Enable to separate base charge from overdue fees "
            "or other adjustments"
        )
        self.new_invoice_use_split.stateChanged.connect(
            self._on_split_checkbox_changed
        )
        split_layout.addWidget(self.new_invoice_use_split)

        # Split details (hidden by default)
        self.split_details = QWidget()
        split_details_layout = QFormLayout(self.split_details)

        # Base amount
        base_amount_row = QHBoxLayout()
        self.new_invoice_base_amount = CurrencyInput(compact=True)
        base_amount_row.addWidget(self.new_invoice_base_amount, stretch=0)
        base_calc_btn = CalculatorButton(self.new_invoice_base_amount)
        base_amount_row.addWidget(base_calc_btn, stretch=0)
        base_amount_row.addStretch()
        split_details_layout.addRow("Base Charge Amount:", base_amount_row)

        # Fee amount
        fee_amount_row = QHBoxLayout()
        self.new_invoice_fee_amount = CurrencyInput(compact=True)
        fee_amount_row.addWidget(self.new_invoice_fee_amount, stretch=0)
        fee_calc_btn = CalculatorButton(self.new_invoice_fee_amount)
        fee_amount_row.addWidget(fee_calc_btn, stretch=0)
        fee_amount_row.addStretch()
        split_details_layout.addRow("Fee/Adjustment Amount:", fee_amount_row)

        # Fee type
        self.new_invoice_fee_type = QComboBox()
        self.new_invoice_fee_type.addItems(
            [
                "Overdue Fee",
                "Interest Charge",
                "Penalty",
                "Service Charge",
                "Late Payment Fee",
                "CRA Adjustment",
                "Other",
            ]
        )
        self.new_invoice_fee_type.setToolTip(
            "CRA: Fees are NOT included in income calculations - "
            "tracked separately for reporting"
        )
        split_details_layout.addRow("Fee Type:", self.new_invoice_fee_type)

        # Info note
        fee_note = QLabel(
            "ℹ️ Overdue fees and penalties are tracked separately for CRA "
            "reporting (not counted as income)"
        )
        fee_note.setStyleSheet(
            "font-size: 9px; color: #0066cc; font-style: italic;"
        )
        split_details_layout.addRow("", fee_note)

        self.split_details.setVisible(False)
        split_layout.addWidget(self.split_details)

        split_group.setLayout(split_layout)
        layout.addWidget(split_group)

        # Add button
        add_btn = QPushButton("✅ Add Invoice")
        add_btn.setStyleSheet(
            "background-color: #28a745; color: white; "
            "font-weight: bold; padding: 4px 8px; font-size: 11px;"
        )
        add_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        add_btn.setFixedHeight(24)
        add_btn.clicked.connect(self._add_invoice)
        layout.addWidget(add_btn)

        layout.addStretch()

        return widget

    def _create_edit_invoice_tab(self) -> QWidget:
        """Tab for editing selected invoice details"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Selection info with status
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(5, 5, 5, 5)
        info_widget.setStyleSheet(
            "background-color: #d4edda; border-radius: 5px;"
        )

        tip_label = QLabel(
            "💡 TIP: Edit Invoice # and Date directly in table! "
            "Double-click, then Save."
        )
        tip_label.setStyleSheet(
            "font-size: 11px; color: #155724; font-weight: bold;"
        )
        info_layout.addWidget(tip_label)

        self.edit_status_label = QLabel(
            "No invoice loaded. Select an invoice and click "
            "'Edit Selected Invoice' button."
        )
        self.edit_status_label.setStyleSheet(
            "font-size: 11px; color: #004085; font-weight: bold; "
            "margin-top: 5px;"
        )
        info_layout.addWidget(self.edit_status_label)

        layout.addWidget(info_widget)

        # Main form - 2 column layout
        form_widget = QWidget()
        form_main = QHBoxLayout(form_widget)

        # LEFT COLUMN
        left_form = QFormLayout()

        self.edit_invoice_num = QLineEdit()
        self.edit_invoice_num.setPlaceholderText("Invoice #")
        left_form.addRow("Invoice #:", self.edit_invoice_num)

        self.edit_invoice_date = StandardDateEdit(prefer_month_text=True)
        self.edit_invoice_date.setCalendarPopup(True)
        self.edit_invoice_date.setDisplayFormat("MM/dd/yyyy")
        self.edit_invoice_date.setMaximumWidth(130)
        left_form.addRow("Date:", self.edit_invoice_date)

        amount_row = QHBoxLayout()
        self.edit_invoice_amount = CurrencyInput(compact=True)
        amount_row.addWidget(self.edit_invoice_amount)
        calc_btn = CalculatorButton(self.edit_invoice_amount)
        amount_row.addWidget(calc_btn)
        amount_row.addStretch()
        left_form.addRow("Amount:", amount_row)

        form_main.addLayout(left_form, stretch=1)

        # RIGHT COLUMN
        right_form = QFormLayout()

        self.edit_invoice_category = QComboBox()
        self.edit_invoice_category.setEditable(True)
        self._load_categories(self.edit_invoice_category)
        right_form.addRow("Category:", self.edit_invoice_category)

        self.edit_invoice_desc = QTextEdit()
        self.edit_invoice_desc.setMaximumHeight(90)
        self.edit_invoice_desc.setPlaceholderText("Optional description...")
        right_form.addRow("Description:", self.edit_invoice_desc)

        form_main.addLayout(right_form, stretch=1)

        layout.addWidget(form_widget)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)

        # Save button
        save_btn = QPushButton("💾 Save Changes")
        save_btn.setStyleSheet(
            "background-color: #28a745; color: white; "
            "font-weight: bold; padding: 4px 8px; font-size: 11px;"
        )
        save_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        save_btn.setFixedHeight(24)
        save_btn.clicked.connect(self._save_invoice_changes)
        btn_layout.addWidget(save_btn)

        # Delete button
        delete_btn = QPushButton("🗑️ Delete Invoice")
        delete_btn.setStyleSheet(
            "background-color: #dc3545; color: white; "
            "font-weight: bold; padding: 4px 8px; font-size: 11px;"
        )
        delete_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        delete_btn.setFixedHeight(24)
        delete_btn.clicked.connect(self._delete_invoice)
        btn_layout.addWidget(delete_btn)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(
            "padding: 4px 8px; font-size: 11px;"
        )
        clear_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_edit_fields)
        btn_layout.addWidget(clear_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        return widget

    def _on_split_checkbox_changed(self, state) -> None:
        """Show/hide split fee details"""
        self.split_details.setVisible(state == Qt.CheckState.Checked.value)

    def _create_payment_tab(self) -> QWidget:
        """Tab for adding payments to invoices - compact layout"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # Top section - payment details in 2 columns
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # LEFT COLUMN - Payment info
        left_form = QFormLayout()
        left_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        payment_amount_row = QHBoxLayout()
        self.payment_amount = CurrencyInput(compact=True)
        payment_amount_row.addWidget(self.payment_amount)
        payment_calc_btn = CalculatorButton(self.payment_amount)
        payment_amount_row.addWidget(payment_calc_btn)
        payment_amount_row.addStretch()
        left_form.addRow("Amount:", payment_amount_row)

        self.payment_reference = QLineEdit()
        self.payment_reference.setPlaceholderText("Check # or reference")
        self.payment_reference.setMaximumWidth(200)
        left_form.addRow("Reference:", self.payment_reference)

        self.payment_receipt_tx = QLineEdit()
        self.payment_receipt_tx.setPlaceholderText("Receipt/TX # (optional)")
        self.payment_receipt_tx.setMaximumWidth(200)
        left_form.addRow("Receipt TX #:", self.payment_receipt_tx)

        top_layout.addLayout(left_form, stretch=1)

        # RIGHT COLUMN - Date and method
        right_form = QFormLayout()
        right_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self.payment_date = StandardDateEdit(prefer_month_text=True)
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setDisplayFormat("MM/dd/yyyy")
        self.payment_date.setMaximumWidth(130)
        right_form.addRow("Date:", self.payment_date)

        self.payment_method = QComboBox()
        self.payment_method.addItems(
            [
                "check",
                "bank_transfer",
                "cash",
                "credit_card",
                "debit_card",
                "trade_of_services",
                "credit_adjustment",
                "unknown",
            ]
        )
        self.payment_method.setMaximumWidth(150)
        right_form.addRow("Method:", self.payment_method)

        top_layout.addLayout(right_form, stretch=1)

        layout.addWidget(top_widget)

        # Optional banking ID
        banking_layout = QHBoxLayout()
        banking_layout.addWidget(QLabel("Banking TX ID:"))
        self.payment_banking_id = QLineEdit()
        self.payment_banking_id.setPlaceholderText("Optional")
        self.payment_banking_id.setMaximumWidth(150)
        banking_layout.addWidget(self.payment_banking_id)
        banking_layout.addStretch()
        layout.addLayout(banking_layout)

        # Hint - payment buttons are in Quick Actions at the top
        hint = QLabel(
            "💡 Enter payment details above, then use the Quick Action "
            "buttons at the TOP:\n"
            "   • Pay One - Select 1 invoice, click 'Pay One' button\n"
            "   • Pay Multiple - Select multiple invoices (Ctrl+Click), "
            "click 'Pay Multiple' button"
        )
        hint.setStyleSheet(
            "font-size: 11px; color: #0066cc; font-weight: bold; "
            "padding: 10px; background-color: #e7f3ff; "
            "border-left: 3px solid #0066cc;"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.auto_create_cash_receipt_chk = QCheckBox(
            "Auto-create receipt for cash when no match found"
        )
        self.auto_create_cash_receipt_chk.setChecked(True)
        self.auto_create_cash_receipt_chk.setToolTip(
            "If enabled, cash payments with no matching receipt will "
            "create and link a receipt automatically."
        )
        layout.addWidget(self.auto_create_cash_receipt_chk)

        history_row = QHBoxLayout()
        history_refresh_btn = QPushButton("🔄 Refresh Payment History")
        history_refresh_btn.clicked.connect(self._refresh_payment_history)
        history_row.addWidget(history_refresh_btn)
        history_row.addStretch()
        layout.addLayout(history_row)

        self.payment_history_label = QLabel(
            "Entered payment rows for this vendor (manual + banking linked)."
        )
        self.payment_history_label.setStyleSheet(
            "font-size: 11px; color: #444; padding: 4px;"
        )
        layout.addWidget(self.payment_history_label)

        self.payment_history_table = QTableWidget()
        self.payment_history_table.setColumnCount(9)
        self.payment_history_table.setHorizontalHeaderLabels(
            [
                "Payment ID",
                "Invoice ID",
                "Invoice #",
                "Date",
                "Amount",
                "Method",
                "Reference",
                "Bank TX",
                "Created",
            ]
        )
        self.payment_history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.payment_history_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.payment_history_table.setAlternatingRowColors(True)
        self.payment_history_table.setMinimumHeight(140)
        self.payment_history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.payment_history_table.horizontalHeader().setStretchLastSection(
            True
        )
        layout.addWidget(self.payment_history_table)

        layout.addStretch()

        return widget

    def _create_receipt_evidence_tab(self) -> QWidget:
        """Tab for reviewing receipts separately from invoice payments."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        info = QLabel(
            "🧾 Receipts are expense/ITC evidence only. Linking a receipt "
            "does not reduce A/P unless a payment is entered."
        )
        info.setStyleSheet(
            "padding: 8px; background-color: #fff4ce; "
            "font-size: 11px; font-weight: bold;"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        controls = QHBoxLayout()

        refresh_btn = QPushButton("🔄 Refresh Receipts")
        refresh_btn.clicked.connect(self._refresh_receipt_evidence)
        controls.addWidget(refresh_btn)

        link_btn = QPushButton("🔗 Link Selected Receipt")
        link_btn.clicked.connect(
            self._link_selected_receipt_to_selected_invoice
        )
        controls.addWidget(link_btn)

        unlink_btn = QPushButton("⛓️ Remove Receipt Link")
        unlink_btn.clicked.connect(self._unlink_selected_receipt_from_invoice)
        controls.addWidget(unlink_btn)

        self.receipt_selected_only_chk = QCheckBox("Selected invoice only")
        self.receipt_selected_only_chk.stateChanged.connect(
            self._refresh_receipt_evidence
        )
        controls.addWidget(self.receipt_selected_only_chk)
        controls.addStretch()
        layout.addLayout(controls)

        self.receipt_evidence_label = QLabel(
            "Select a vendor to load receipt evidence."
        )
        self.receipt_evidence_label.setStyleSheet(
            "font-size: 11px; color: #444; padding: 4px;"
        )
        layout.addWidget(self.receipt_evidence_label)

        self.receipt_evidence_table = QTableWidget()
        self.receipt_evidence_table.setColumnCount(8)
        self.receipt_evidence_table.setHorizontalHeaderLabels(
            [
                "Receipt ID",
                "Date",
                "Amount",
                "Reference",
                "Description",
                "Bank TX",
                "Linked Invoice",
                "Linked?",
            ]
        )
        self.receipt_evidence_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.receipt_evidence_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.receipt_evidence_table.setAlternatingRowColors(True)
        self.receipt_evidence_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.receipt_evidence_table.horizontalHeader().setStretchLastSection(
            True
        )
        layout.addWidget(self.receipt_evidence_table)

        return widget

    def _create_banking_link_tab(self) -> QWidget:
        """Tab for linking banking transactions"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        info = QLabel("🏦 Search banking transactions and link to invoices")
        info.setStyleSheet(
            "padding: 8px; background-color: #e3f2fd; "
            "font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(info)

        # Banking search - compact 2 column layout
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)

        left_form = QFormLayout()
        self.banking_search_amount = CurrencyInput(compact=True)
        left_form.addRow("Amount:", self.banking_search_amount)

        self.banking_search_desc = QLineEdit()
        self.banking_search_desc.setPlaceholderText("Description...")
        self.banking_search_desc.setMaximumWidth(200)
        left_form.addRow("Description:", self.banking_search_desc)

        search_layout.addLayout(left_form)

        # Date filter
        right_form = QFormLayout()

        self.banking_use_date_filter = QCheckBox("Filter by date")
        self.banking_use_date_filter.stateChanged.connect(
            self._toggle_banking_date_filter
        )
        right_form.addRow("", self.banking_use_date_filter)

        date_row = QHBoxLayout()
        self.banking_date_from = StandardDateEdit(prefer_month_text=True)
        self.banking_date_from.setCalendarPopup(True)
        self.banking_date_from.setDisplayFormat("MM/dd/yyyy")
        self.banking_date_from.setMaximumWidth(110)
        self.banking_date_from.setEnabled(False)
        date_row.addWidget(QLabel("From:"))
        date_row.addWidget(self.banking_date_from)

        self.banking_date_to = StandardDateEdit(prefer_month_text=True)
        self.banking_date_to.setCalendarPopup(True)
        self.banking_date_to.setDate(QDate.currentDate())
        self.banking_date_to.setDisplayFormat("MM/dd/yyyy")
        self.banking_date_to.setMaximumWidth(110)
        self.banking_date_to.setEnabled(False)
        date_row.addWidget(QLabel("To:"))
        date_row.addWidget(self.banking_date_to)
        date_row.addStretch()
        right_form.addRow("", date_row)

        search_layout.addLayout(right_form)
        search_layout.addStretch()

        layout.addWidget(search_widget)

        # Search button
        search_btn = QPushButton("🔍 Search Banking Transactions")
        search_btn.setStyleSheet(
            "background-color: #007bff; color: white; padding: 8px; "
            "font-weight: bold;"
        )
        search_btn.clicked.connect(self._search_banking)
        layout.addWidget(search_btn)

        # Results table
        self.banking_table = QTableWidget()
        self.banking_table.setColumnCount(6)
        self.banking_table.setHorizontalHeaderLabels(
            ["TX ID", "Date", "Description", "Amount", "Check #", "Linked"]
        )
        self.banking_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.banking_table.itemDoubleClicked.connect(
            self._link_banking_to_invoice
        )
        layout.addWidget(self.banking_table)

        hint = QLabel(
            "💡 Double-click a transaction to link it to selected invoice(s)"
        )
        hint.setStyleSheet("font-size: 11px; color: #666; padding: 5px;")
        layout.addWidget(hint)

        return widget

    def _create_ledger_tab(self) -> QWidget:
        """Tab showing a chronological vendor ledger with running balance."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        info = QLabel(
            "📒 Ledger view: invoice rows add to balance, payment rows "
            "reduce balance. Receipts remain separate evidence."
        )
        info.setStyleSheet(
            "padding: 8px; background-color: #e8f4fd; "
            "font-size: 11px; font-weight: bold;"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        header_row = QHBoxLayout()
        self.ledger_label = QLabel("Select a vendor to load the ledger.")
        self.ledger_label.setStyleSheet(
            "font-size: 11px; color: #444; padding: 4px;"
        )
        header_row.addWidget(self.ledger_label)
        header_row.addStretch()

        refresh_btn = QPushButton("🔄 Refresh Ledger")
        refresh_btn.clicked.connect(self._refresh_vendor_ledger)
        header_row.addWidget(refresh_btn)

        edit_btn = QPushButton("✏️ Open Editable Ledger")
        edit_btn.clicked.connect(self._open_ledger_editor)
        header_row.addWidget(edit_btn)

        self.ledger_row_filter = QComboBox()
        self.ledger_row_filter.addItems(
            [
                "All",
                "Invoices only",
                "Payments only",
            ]
        )
        self.ledger_row_filter.setMaximumWidth(140)
        self.ledger_row_filter.currentIndexChanged.connect(
            self._refresh_vendor_ledger
        )
        header_row.addWidget(self.ledger_row_filter)

        self.ledger_use_date_filter = QCheckBox("Date range")
        self.ledger_use_date_filter.stateChanged.connect(
            self._toggle_ledger_date_filter
        )
        header_row.addWidget(self.ledger_use_date_filter)

        self.ledger_date_from = StandardDateEdit(prefer_month_text=True)
        self.ledger_date_from.setCalendarPopup(True)
        self.ledger_date_from.setDisplayFormat("MM/dd/yyyy")
        self.ledger_date_from.setDate(QDate(QDate.currentDate().year(), 1, 1))
        self.ledger_date_from.setMaximumWidth(110)
        self.ledger_date_from.setEnabled(False)
        self.ledger_date_from.dateChanged.connect(self._refresh_vendor_ledger)
        header_row.addWidget(self.ledger_date_from)

        self.ledger_date_to = StandardDateEdit(prefer_month_text=True)
        self.ledger_date_to.setCalendarPopup(True)
        self.ledger_date_to.setDisplayFormat("MM/dd/yyyy")
        self.ledger_date_to.setDate(QDate.currentDate())
        self.ledger_date_to.setMaximumWidth(110)
        self.ledger_date_to.setEnabled(False)
        self.ledger_date_to.dateChanged.connect(self._refresh_vendor_ledger)
        header_row.addWidget(self.ledger_date_to)

        layout.addLayout(header_row)

        self.ledger_table = QTableWidget()
        self.ledger_table.setColumnCount(8)
        self.ledger_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Type",
                "Invoice #",
                "Details",
                "Owed",
                "Paid",
                "Balance",
                "Evidence",
            ]
        )
        self.ledger_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.ledger_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.ledger_table.setAlternatingRowColors(True)
        self.ledger_table.itemSelectionChanged.connect(
            self._show_selected_ledger_details
        )
        self.ledger_table.itemDoubleClicked.connect(
            self._on_ledger_row_activated
        )
        self.ledger_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.ledger_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.ledger_table)

        hint = QLabel(
            "💡 Double-click a ledger row to jump to that invoice in the "
            "main invoice table."
        )
        hint.setStyleSheet("font-size: 11px; color: #666; padding: 4px;")
        layout.addWidget(hint)

        self.ledger_details_text = QTextEdit()
        self.ledger_details_text.setReadOnly(True)
        self.ledger_details_text.setMaximumHeight(130)
        self.ledger_details_text.setStyleSheet(
            "font-family: 'Courier New'; font-size: 11px; "
            "background-color: #fafafa;"
        )
        self.ledger_details_text.setPlainText(
            "Select a ledger row to view details."
        )
        layout.addWidget(self.ledger_details_text)

        return widget

    def _open_ledger_editor(self) -> None:
        """Open a chronological ledger popup with guarded row editing."""
        if not self.current_vendor:
            QMessageBox.warning(
                self, "No Vendor", "Select a vendor before opening the ledger."
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(
            f"Editable Vendor Ledger - {self.current_vendor}"
        )
        dialog.resize(1180, 720)
        layout = QVBoxLayout(dialog)

        info = QLabel(
            "Invoices increase the running balance; payments reduce it. "
            "Document # is the invoice number on invoice rows and the payment "
            "number/reference on payment rows. Applied To Invoice identifies "
            "the invoice receiving a payment. Select a row, edit the fields "
            "below, then click Save Corrected Row."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "padding: 8px; background-color: #e8f4fd; font-weight: bold;"
        )
        layout.addWidget(info)

        self.ledger_editor_summary = QLabel()
        layout.addWidget(self.ledger_editor_summary)

        self.ledger_editor_table = QTableWidget()
        self.ledger_editor_table.setColumnCount(10)
        self.ledger_editor_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Type",
                "Document #",
                "Applied To Invoice",
                "Details",
                "Charge",
                "Payment",
                "Running Balance",
                "Record ID",
                "Invoice ID",
            ]
        )
        self.ledger_editor_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.ledger_editor_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.ledger_editor_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.ledger_editor_table.setAlternatingRowColors(True)
        self.ledger_editor_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.ledger_editor_table.horizontalHeader().setStretchLastSection(
            True
        )
        self.ledger_editor_table.itemSelectionChanged.connect(
            self._load_ledger_editor_selection
        )
        layout.addWidget(self.ledger_editor_table, stretch=1)

        editor_group = QGroupBox("Selected Row")
        editor_layout = QFormLayout(editor_group)

        self.ledger_editor_date = StandardDateEdit(prefer_month_text=True)
        self.ledger_editor_date.setCalendarPopup(True)
        self.ledger_editor_date.setDisplayFormat("MM/dd/yyyy")
        editor_layout.addRow("Date:", self.ledger_editor_date)

        self.ledger_editor_invoice_number = QLineEdit()
        self.ledger_editor_invoice_number_label = QLabel("Invoice #:")
        editor_layout.addRow(
            self.ledger_editor_invoice_number_label,
            self.ledger_editor_invoice_number,
        )

        self.ledger_editor_amount = CurrencyInput()
        editor_layout.addRow("Amount:", self.ledger_editor_amount)

        self.ledger_editor_method = QComboBox()
        self.ledger_editor_method.addItems(
            [
                "check",
                "bank_transfer",
                "cash",
                "credit_card",
                "debit_card",
                "trade_of_services",
                "credit_adjustment",
                "unknown",
            ]
        )
        editor_layout.addRow("Payment method:", self.ledger_editor_method)

        self.ledger_editor_reference = QLineEdit()
        editor_layout.addRow(
            "Payment # / reference:", self.ledger_editor_reference
        )

        self.ledger_editor_notes = QTextEdit()
        self.ledger_editor_notes.setMaximumHeight(80)
        editor_layout.addRow("Details / notes:", self.ledger_editor_notes)
        layout.addWidget(editor_group)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_ledger_editor)
        button_row.addWidget(refresh_btn)

        add_invoice_btn = QPushButton("Add Invoice")
        add_invoice_btn.clicked.connect(self._add_ledger_editor_invoice)
        button_row.addWidget(add_invoice_btn)

        add_payment_btn = QPushButton("Add Payment")
        add_payment_btn.clicked.connect(self._add_ledger_editor_payment)
        button_row.addWidget(add_payment_btn)

        save_btn = QPushButton("Save Corrected Row")
        save_btn.setStyleSheet(
            "background-color: #28a745; color: white; "
            "font-weight: bold; padding: 7px;"
        )
        save_btn.clicked.connect(self._save_ledger_editor_row)
        button_row.addWidget(save_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setStyleSheet(
            "background-color: #dc3545; color: white; "
            "font-weight: bold; padding: 7px;"
        )
        delete_btn.clicked.connect(self._delete_ledger_editor_row)
        button_row.addWidget(delete_btn)
        button_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        self._refresh_ledger_editor()
        dialog.exec()

    def _selected_ledger_editor_metadata(self) -> dict | None:
        """Return metadata for the selected editable ledger row."""
        row = self.ledger_editor_table.currentRow()
        if row < 0:
            return None

        item = self.ledger_editor_table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _refresh_after_ledger_change(self) -> None:
        """Refresh every surface affected by a ledger correction."""
        self._refresh_ledger_editor()
        self._load_vendor_invoices()
        self._refresh_vendor_ledger()
        self._refresh_payment_history()
        self._refresh_account_summary()

    def _add_ledger_editor_invoice(self) -> None:
        """Create an invoice using the values in the ledger editor."""
        invoice_number = self.ledger_editor_invoice_number.text().strip()
        amount = Decimal(str(self.ledger_editor_amount.get_value()))
        notes = self.ledger_editor_notes.toPlainText().strip()

        confirm = QMessageBox.question(
            self,
            "Confirm New Invoice",
            f"Add invoice {invoice_number or '(no number)'} for "
            f"${amount:,.2f} to {self.current_vendor}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO vendor_invoices
                        (vendor_name, invoice_number, invoice_date,
                         invoice_amount, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING vendor_invoice_id
                    """,
                    (
                        self.current_vendor,
                        invoice_number or None,
                        self.ledger_editor_date.date().toPyDate(),
                        amount,
                        notes or None,
                    ),
                )
                invoice_id = cur.fetchone()[0]

            self._refresh_after_ledger_change()
            QMessageBox.information(
                self,
                "Invoice Added",
                f"Invoice record {invoice_id} was added.",
            )
        except Exception as e:
            logger.error("Failed to add invoice from ledger editor: %s", e)
            QMessageBox.critical(
                self, "Add Error", f"Unable to add the invoice:\n\n{e}"
            )

    def _add_ledger_editor_payment(self) -> None:
        """Create a payment for the invoice linked to the selected row."""
        metadata = self._selected_ledger_editor_metadata()
        if not metadata:
            QMessageBox.warning(
                self,
                "No Invoice Selection",
                "Select an invoice or one of its payment rows first.",
            )
            return

        invoice_id = metadata["invoice_id"]
        amount = Decimal(str(self.ledger_editor_amount.get_value()))
        if amount <= 0:
            QMessageBox.warning(
                self, "Invalid Amount", "Payment must be greater than $0.00."
            )
            return

        reference = self.ledger_editor_reference.text().strip()
        confirm = QMessageBox.question(
            self,
            "Confirm New Payment",
            f"Add a ${amount:,.2f} payment to invoice "
            f"{metadata['invoice_number'] or invoice_id}?\n\n"
            f"Reference: {reference or '(none)'}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    """
                    SELECT vendor_invoice_id
                    FROM vendor_invoices
                    WHERE vendor_invoice_id = %s
                      AND vendor_name = %s
                    FOR UPDATE
                    """,
                    (invoice_id, self.current_vendor),
                )
                if cur.fetchone() is None:
                    raise ValueError(
                        "The selected invoice no longer exists for this vendor."
                    )

                cur.execute(
                    """
                    INSERT INTO vendor_invoice_payments
                        (receipt_id, payment_date, payment_amount,
                         payment_method, reference, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING payment_id
                    """,
                    (
                        invoice_id,
                        self.ledger_editor_date.date().toPyDate(),
                        amount,
                        self.ledger_editor_method.currentText(),
                        reference or None,
                        self.ledger_editor_notes.toPlainText().strip() or None,
                    ),
                )
                payment_id = cur.fetchone()[0]

            self._refresh_after_ledger_change()
            QMessageBox.information(
                self,
                "Payment Added",
                f"Payment record {payment_id} was added.",
            )
        except Exception as e:
            logger.error("Failed to add payment from ledger editor: %s", e)
            QMessageBox.critical(
                self, "Add Error", f"Unable to add the payment:\n\n{e}"
            )

    def _delete_ledger_editor_row(self) -> None:
        """Delete the selected ledger row after dependency checks."""
        metadata = self._selected_ledger_editor_metadata()
        if not metadata:
            QMessageBox.warning(
                self, "No Selection", "Select a ledger row to delete."
            )
            return

        row_type = metadata["row_type"]
        record_id = metadata["record_id"]
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Permanently delete {row_type.lower()} record {record_id}?\n\n"
            "This cannot be undone and will recalculate all subsequent "
            "running balances.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                if row_type == "PAYMENT":
                    cur.execute(
                        """
                        DELETE FROM vendor_invoice_payments vip
                        WHERE vip.payment_id = %s
                          AND EXISTS (
                              SELECT 1
                              FROM vendor_invoices vi
                              WHERE vi.vendor_invoice_id = vip.receipt_id
                                AND vi.vendor_name = %s
                          )
                        RETURNING vip.payment_id
                        """,
                        (record_id, self.current_vendor),
                    )
                else:
                    cur.execute(
                        """
                        SELECT
                            (SELECT COUNT(*)
                             FROM vendor_invoice_payments
                             WHERE receipt_id = vi.vendor_invoice_id),
                            (SELECT COUNT(*)
                             FROM receipts
                             WHERE vendor_invoice_id = vi.vendor_invoice_id)
                        FROM vendor_invoices vi
                        WHERE vi.vendor_invoice_id = %s
                          AND vi.vendor_name = %s
                        FOR UPDATE
                        """,
                        (record_id, self.current_vendor),
                    )
                    dependency_counts = cur.fetchone()
                    if dependency_counts is None:
                        raise ValueError(
                            f"Invoice record {record_id} was not found."
                        )
                    payment_count, receipt_count = dependency_counts
                    if payment_count or receipt_count:
                        raise ValueError(
                            "This invoice cannot be deleted while it has "
                            f"{payment_count} payment(s) or "
                            f"{receipt_count} linked receipt(s). Delete or "
                            "unlink those records first."
                        )

                    cur.execute(
                        """
                        DELETE FROM vendor_invoices
                        WHERE vendor_invoice_id = %s
                          AND vendor_name = %s
                        RETURNING vendor_invoice_id
                        """,
                        (record_id, self.current_vendor),
                    )

                if cur.fetchone() is None:
                    raise ValueError(
                        f"{row_type.title()} record {record_id} was not found."
                    )

            self._refresh_after_ledger_change()
            QMessageBox.information(
                self,
                "Ledger Row Deleted",
                f"{row_type.title()} record {record_id} was deleted.",
            )
        except Exception as e:
            logger.error("Failed to delete ledger row: %s", e)
            QMessageBox.critical(
                self, "Delete Error", f"Unable to delete the row:\n\n{e}"
            )

    def _fetch_editable_ledger_rows(self) -> list[tuple]:
        """Return invoice and payment rows in deterministic ledger order."""
        with DatabaseContext(self.conn, auto_commit=True) as cur:
            cur.execute(
                """
                WITH ledger_rows AS (
                    SELECT
                        vi.invoice_date AS row_date,
                        'INVOICE'::text AS row_type,
                        vi.vendor_invoice_id AS record_id,
                        vi.vendor_invoice_id,
                        COALESCE(vi.invoice_number, '') AS invoice_number,
                        COALESCE(vi.notes, '') AS details,
                        COALESCE(vi.invoice_amount, 0) AS amount,
                        ''::text AS payment_method,
                        ''::text AS reference
                    FROM vendor_invoices vi
                    WHERE vi.vendor_name = %s
                      AND (
                          %s = false
                          OR COALESCE(vi.invoice_number, '')
                              <> 'BANKING_IMPORT'
                      )

                    UNION ALL

                    SELECT
                        vip.payment_date AS row_date,
                        'PAYMENT'::text AS row_type,
                        vip.payment_id AS record_id,
                        vi.vendor_invoice_id,
                        COALESCE(vi.invoice_number, '') AS invoice_number,
                        COALESCE(vip.notes, '') AS details,
                        COALESCE(vip.payment_amount, 0) AS amount,
                        COALESCE(vip.payment_method, '') AS payment_method,
                        COALESCE(vip.reference, '') AS reference
                    FROM vendor_invoice_payments vip
                    JOIN vendor_invoices vi
                        ON vi.vendor_invoice_id = vip.receipt_id
                    WHERE vi.vendor_name = %s
                      AND ABS(COALESCE(vip.payment_amount, 0)) >= 0.005
                      AND (
                          %s = false
                          OR COALESCE(vi.invoice_number, '')
                              <> 'BANKING_IMPORT'
                      )
                )
                SELECT
                    row_date,
                    row_type,
                    record_id,
                    vendor_invoice_id,
                    invoice_number,
                    details,
                    amount,
                    payment_method,
                    reference
                FROM ledger_rows
                ORDER BY
                    row_date NULLS LAST,
                    CASE WHEN row_type = 'INVOICE' THEN 0 ELSE 1 END,
                    vendor_invoice_id,
                    record_id
                """,
                (
                    self.current_vendor,
                    self._hide_auto_import_invoices(),
                    self.current_vendor,
                    self._hide_auto_import_invoices(),
                ),
            )
            return cur.fetchall()

    def _refresh_ledger_editor(self) -> None:
        """Reload the editable ledger and recalculate its running balance."""
        if not hasattr(self, "ledger_editor_table"):
            return

        try:
            rows = self._fetch_editable_ledger_rows()
            self.ledger_editor_table.setRowCount(len(rows))
            running_balance = 0.0
            total_charges = 0.0
            total_payments = 0.0

            for row_index, row in enumerate(rows):
                (
                    row_date,
                    row_type,
                    record_id,
                    invoice_id,
                    invoice_number,
                    details,
                    amount,
                    payment_method,
                    reference,
                ) = row
                raw_amount = Decimal(str(amount or 0))
                display_amount = float(
                    abs(raw_amount) if row_type == "PAYMENT" else raw_amount
                )

                if row_type == "INVOICE":
                    charge = display_amount
                    payment = 0.0
                    total_charges += display_amount
                    running_balance += display_amount
                    detail_text = details
                    document_number = invoice_number
                    applied_to_invoice = ""
                else:
                    charge = 0.0
                    payment = display_amount
                    total_payments += display_amount
                    running_balance -= display_amount
                    detail_text = " | ".join(
                        value
                        for value in (payment_method, details)
                        if value
                    )
                    document_number = reference
                    applied_to_invoice = invoice_number

                values = [
                    (
                        row_date.strftime("%m/%d/%Y")
                        if hasattr(row_date, "strftime")
                        else str(row_date or "")
                    ),
                    row_type,
                    str(document_number),
                    str(applied_to_invoice),
                    detail_text,
                    f"${charge:,.2f}" if charge else "",
                    f"${payment:,.2f}" if payment else "",
                    f"${running_balance:,.2f}",
                    str(record_id),
                    str(invoice_id),
                ]

                metadata = {
                    "row_date": row_date,
                    "row_type": row_type,
                    "record_id": int(record_id),
                    "invoice_id": int(invoice_id),
                    "invoice_number": str(invoice_number),
                    "details": str(details or ""),
                    "amount": raw_amount,
                    "payment_method": str(payment_method or ""),
                    "reference": str(reference or ""),
                }

                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column in (5, 6, 7):
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    item.setBackground(
                        QBrush(
                            QColor(
                                "#fff8e1"
                                if row_type == "INVOICE"
                                else "#e8f5e9"
                            )
                        )
                    )
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, metadata)
                    self.ledger_editor_table.setItem(
                        row_index, column, item
                    )

            self.ledger_editor_summary.setText(
                f"{self.current_vendor}: {len(rows)} rows | "
                f"Charges ${total_charges:,.2f} | "
                f"Payments ${total_payments:,.2f} | "
                f"Balance ${running_balance:,.2f}"
            )
        except Exception as e:
            logger.error("Failed to load editable vendor ledger: %s", e)
            QMessageBox.critical(
                self,
                "Ledger Error",
                f"Unable to load the editable ledger:\n\n{e}",
            )

    def _load_ledger_editor_selection(self) -> None:
        """Load the selected ledger row into the edit controls."""
        row = self.ledger_editor_table.currentRow()
        if row < 0:
            return

        item = self.ledger_editor_table.item(row, 0)
        metadata = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        if not metadata:
            return

        row_date = metadata["row_date"]
        if hasattr(row_date, "year"):
            self.ledger_editor_date.setDate(
                QDate(row_date.year, row_date.month, row_date.day)
            )

        is_invoice = metadata["row_type"] == "INVOICE"
        self.ledger_editor_invoice_number_label.setText(
            "Invoice #:" if is_invoice else "Applied to invoice #:"
        )
        self.ledger_editor_invoice_number.setText(
            metadata["invoice_number"]
        )
        self.ledger_editor_invoice_number.setReadOnly(False)
        editor_amount = (
            abs(metadata["amount"])
            if metadata["row_type"] == "PAYMENT"
            else metadata["amount"]
        )
        self.ledger_editor_amount.setText(f"{editor_amount:.2f}")
        self.ledger_editor_method.setEnabled(not is_invoice)
        self.ledger_editor_reference.setEnabled(not is_invoice)

        method = metadata["payment_method"] or "unknown"
        method_index = self.ledger_editor_method.findText(method)
        if method_index < 0:
            self.ledger_editor_method.addItem(method)
            method_index = self.ledger_editor_method.findText(method)
        self.ledger_editor_method.setCurrentIndex(method_index)
        self.ledger_editor_reference.setText(metadata["reference"])
        self.ledger_editor_notes.setPlainText(metadata["details"])

    def _save_ledger_editor_row(self) -> None:
        """Persist corrections for the selected invoice or payment row."""
        row = self.ledger_editor_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "No Selection", "Select a ledger row to edit."
            )
            return

        item = self.ledger_editor_table.item(row, 0)
        metadata = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        if not metadata:
            QMessageBox.warning(
                self, "Invalid Selection", "The selected row has no record ID."
            )
            return

        row_type = metadata["row_type"]
        record_id = metadata["record_id"]
        amount = Decimal(str(self.ledger_editor_amount.get_value()))
        if row_type == "PAYMENT":
            original_amount = metadata["amount"]
            amount = (
                -abs(amount) if original_amount < 0 else abs(amount)
            )
        confirm = QMessageBox.question(
            self,
            "Confirm Ledger Correction",
            f"Save changes to {row_type.lower()} record {record_id}?\n\n"
            "This changes the accounting record and recalculates all "
            "subsequent running balances.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                if row_type == "INVOICE":
                    cur.execute(
                        """
                        SELECT
                            invoice_date,
                            COALESCE(invoice_number, ''),
                            COALESCE(invoice_amount, 0),
                            COALESCE(notes, '')
                        FROM vendor_invoices
                        WHERE vendor_invoice_id = %s
                          AND vendor_name = %s
                        FOR UPDATE
                        """,
                        (record_id, self.current_vendor),
                    )
                    current_row = cur.fetchone()
                    expected_row = (
                        metadata["row_date"],
                        metadata["invoice_number"],
                        metadata["amount"],
                        metadata["details"],
                    )
                    if current_row is None:
                        raise ValueError(
                            f"Invoice record {record_id} was not found."
                        )
                    if tuple(current_row) != expected_row:
                        raise ValueError(
                            "This invoice changed after the ledger was loaded. "
                            "Refresh the ledger and review the latest values."
                        )

                    cur.execute(
                        """
                        UPDATE vendor_invoices
                        SET invoice_date = %s,
                            invoice_number = %s,
                            invoice_amount = %s,
                            notes = %s,
                            updated_at = NOW()
                        WHERE vendor_invoice_id = %s
                          AND vendor_name = %s
                        RETURNING vendor_invoice_id
                        """,
                        (
                            self.ledger_editor_date.date().toPyDate(),
                            self.ledger_editor_invoice_number.text().strip(),
                            amount,
                            self.ledger_editor_notes.toPlainText().strip(),
                            record_id,
                            self.current_vendor,
                        ),
                    )
                else:
                    target_invoice_number = (
                        self.ledger_editor_invoice_number.text().strip()
                    )
                    if not target_invoice_number:
                        raise ValueError(
                            "Invoice # is required for a payment record."
                        )

                    cur.execute(
                        """
                        SELECT vendor_invoice_id
                        FROM vendor_invoices
                        WHERE vendor_name = %s
                          AND LOWER(TRIM(COALESCE(invoice_number, '')))
                              = LOWER(TRIM(%s))
                        ORDER BY vendor_invoice_id
                        FOR UPDATE
                        """,
                        (self.current_vendor, target_invoice_number),
                    )
                    matching_invoices = cur.fetchall()
                    if not matching_invoices:
                        raise ValueError(
                            f"Invoice {target_invoice_number} was not found "
                            f"for {self.current_vendor}."
                        )
                    if len(matching_invoices) > 1:
                        raise ValueError(
                            f"Invoice number {target_invoice_number} is not "
                            "unique for this vendor. Correct the duplicate "
                            "invoice numbers before moving this payment."
                        )
                    target_invoice_id = int(matching_invoices[0][0])

                    cur.execute(
                        """
                        SELECT
                            vip.payment_date,
                            COALESCE(vip.payment_amount, 0),
                            COALESCE(vip.payment_method, ''),
                            COALESCE(vip.reference, ''),
                            COALESCE(vip.notes, '')
                        FROM vendor_invoice_payments vip
                        JOIN vendor_invoices vi
                            ON vi.vendor_invoice_id = vip.receipt_id
                        WHERE vip.payment_id = %s
                          AND vi.vendor_name = %s
                        FOR UPDATE OF vip
                        """,
                        (record_id, self.current_vendor),
                    )
                    current_row = cur.fetchone()
                    expected_row = (
                        metadata["row_date"],
                        metadata["amount"],
                        metadata["payment_method"],
                        metadata["reference"],
                        metadata["details"],
                    )
                    if current_row is None:
                        raise ValueError(
                            f"Payment record {record_id} was not found."
                        )
                    if tuple(current_row) != expected_row:
                        raise ValueError(
                            "This payment changed after the ledger was loaded. "
                            "Refresh the ledger and review the latest values."
                        )

                    cur.execute(
                        """
                        UPDATE vendor_invoice_payments vip
                        SET receipt_id = %s,
                            payment_date = %s,
                            payment_amount = %s,
                            payment_method = %s,
                            reference = %s,
                            notes = %s
                        WHERE vip.payment_id = %s
                          AND EXISTS (
                              SELECT 1
                              FROM vendor_invoices vi
                              WHERE vi.vendor_invoice_id = vip.receipt_id
                                AND vi.vendor_name = %s
                          )
                        RETURNING vip.payment_id
                        """,
                        (
                            target_invoice_id,
                            self.ledger_editor_date.date().toPyDate(),
                            amount,
                            self.ledger_editor_method.currentText(),
                            self.ledger_editor_reference.text().strip(),
                            self.ledger_editor_notes.toPlainText().strip(),
                            record_id,
                            self.current_vendor,
                        ),
                    )

                if cur.fetchone() is None:
                    raise ValueError(
                        f"{row_type.title()} record {record_id} "
                        "was not found for the selected vendor."
                    )

            self._refresh_ledger_editor()
            self._load_vendor_invoices()
            self._refresh_vendor_ledger()
            self._refresh_payment_history()
            self._refresh_account_summary()
            QMessageBox.information(
                self,
                "Ledger Updated",
                f"{row_type.title()} record {record_id} was saved.",
            )
        except Exception as e:
            logger.error("Failed to save ledger correction: %s", e)
            QMessageBox.critical(
                self,
                "Save Error",
                f"Unable to save the ledger correction:\n\n{e}",
            )

    def _create_account_summary_tab(self) -> QWidget:
        """Tab showing account summary and payment history"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setStyleSheet(
            "font-family: 'Courier New'; font-size: 11px;"
        )
        layout.addWidget(self.summary_text)

        refresh_btn = QPushButton("🔄 Refresh Summary")
        refresh_btn.setStyleSheet(
            "background-color: #007bff; color: white; padding: 8px; "
            "font-weight: bold;"
        )
        refresh_btn.clicked.connect(self._refresh_account_summary)
        layout.addWidget(refresh_btn)

        return widget

    def _load_categories(self, combo_box=None) -> None:
        """Load GL account codes into the category combo box(es)"""
        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    SELECT account_code, account_name
                    FROM chart_of_accounts
                    WHERE is_header_account = false
                    ORDER BY account_code
                """)
                accounts = cur.fetchall()

            # Build list of "code - name" entries
            gl_entries = [f"{row[0]} - {row[1]}" for row in accounts if row[0]]

            # If specific combo box provided, populate only that one
            if combo_box is not None:
                combo_box.clear()
                combo_box.addItems([""] + gl_entries)
            else:
                # Populate both combo boxes if they exist
                if hasattr(self, "new_invoice_category"):
                    self.new_invoice_category.clear()
                    self.new_invoice_category.addItems([""] + gl_entries)
                if hasattr(self, "edit_invoice_category"):
                    self.edit_invoice_category.clear()
                    self.edit_invoice_category.addItems([""] + gl_entries)

        except Exception as e:
            logger.error("Error loading GL codes for categories: %s", e)

    def _on_vendor_selected(self, vendor_name) -> None:
        """Load invoices for selected vendor"""
        if not vendor_name:
            return

        self.current_vendor = vendor_name
        self._load_vendor_invoices()
        self._refresh_account_summary()
        self._refresh_payment_history()
        self._refresh_receipt_evidence()

    def _ensure_receipt_invoice_link_schema(self) -> None:
        """Ensure receipts can link to vendor invoices.

        Used for evidence tracking.
        """
        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    "ALTER TABLE receipts "
                    "ADD COLUMN IF NOT EXISTS vendor_invoice_id INTEGER"
                )
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_receipts_vendor_invoice_id
                    ON receipts (vendor_invoice_id)
                    """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_vendor_invoices_vendor_invoice_id_unique
                    ON vendor_invoices (vendor_invoice_id)
                    """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'fk_receipts_vendor_invoice'
                        ) THEN
                            BEGIN
                                ALTER TABLE receipts
                                ADD CONSTRAINT fk_receipts_vendor_invoice
                                FOREIGN KEY (vendor_invoice_id)
                                REFERENCES vendor_invoices(vendor_invoice_id)
                                ON DELETE SET NULL;
                            EXCEPTION
                                WHEN duplicate_object THEN
                                    NULL;
                                WHEN invalid_foreign_key THEN
                                    NULL;
                            END;
                        END IF;
                    END $$;
                    """)
                cur.execute("""
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'receipts'
                      AND column_name = 'vendor_invoice_id'
                    """)
                if cur.fetchone() is None:
                    raise RuntimeError(
                        "Schema update did not create "
                        "receipts.vendor_invoice_id"
                    )
        except Exception as e:
            logger.error(f"Failed ensuring receipt invoice link schema: {e}")
            # Do not block invoice UI on optional schema hardening.
            # Queries can still run without the FK when column creation
            # succeeds.

    def _get_vendor_account_id(self, cur, vendor_name) -> int | None:
        """Resolve vendor account ID for current vendor when available."""
        cur.execute(
            """
            SELECT account_id FROM vendor_accounts
            WHERE display_name = %s OR canonical_vendor = %s
            LIMIT 1
            """,
            (vendor_name, vendor_name),
        )
        row = cur.fetchone()
        return row[0] if row else None

    @pyqtSlot()
    def _refresh_receipt_evidence(self) -> None:
        """Load receipt evidence rows for current vendor and selected"
        "invoice."""

        if not hasattr(self, "receipt_evidence_table"):
            return

        if not self.current_vendor:
            self.receipt_evidence_table.setRowCount(0)
            self.receipt_evidence_label.setText(
                "Select a vendor to load receipt evidence."
            )
            return

        selected_ids = self._selected_invoice_ids()
        selected_only = (
            hasattr(self, "receipt_selected_only_chk")
            and self.receipt_selected_only_chk.isChecked()
        )

        try:
            self._ensure_receipt_invoice_link_schema()
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                vendor_account_id = self._get_vendor_account_id(
                    cur, self.current_vendor
                )

                sql = """
                    SELECT
                        r.receipt_id,
                        r.receipt_date,
                        COALESCE(r.gross_amount, 0) AS gross_amount,
                        COALESCE(r.source_reference, '') AS source_reference,
                        COALESCE(r.description, '') AS description,
                        r.banking_transaction_id,
                        r.vendor_invoice_id,
                        COALESCE(vi.invoice_number, '(unlinked)')
                            AS linked_invoice_number
                    FROM receipts r
                    LEFT JOIN vendor_invoices vi
                        ON vi.vendor_invoice_id = r.vendor_invoice_id
                    WHERE COALESCE(r.is_voided, false) = false
                """
                params = []

                if vendor_account_id is not None:
                    sql += " AND r.vendor_account_id = %s"
                    params.append(vendor_account_id)
                else:
                    sql += " AND r.vendor_name ILIKE %s"
                    params.append(self.current_vendor)

                if selected_only and selected_ids:
                    sql += " AND r.vendor_invoice_id = ANY(%s)"
                    params.append(selected_ids)
                elif selected_only:
                    self.receipt_evidence_table.setRowCount(0)
                    self.receipt_evidence_label.setText(
                        "No invoice selected. Select one invoice to filter "
                        "receipt evidence."
                    )
                    return

                sql += (
                    " ORDER BY r.receipt_date DESC, r.receipt_id DESC "
                    "LIMIT 400"
                )
                cur.execute(sql, params)
                rows = cur.fetchall()

            self.receipt_evidence_table.setRowCount(len(rows))
            total_amount = 0.0
            linked_total = 0.0
            for idx, row in enumerate(rows):
                (
                    receipt_id,
                    receipt_date,
                    gross_amount,
                    source_reference,
                    description,
                    bank_tx,
                    linked_invoice_id,
                    linked_invoice_number,
                ) = row
                gross_amount = float(gross_amount or 0)
                total_amount += gross_amount
                if linked_invoice_id is not None:
                    linked_total += gross_amount

                values = [
                    str(receipt_id),
                    (
                        receipt_date.strftime("%m/%d/%Y")
                        if hasattr(receipt_date, "strftime")
                        else str(receipt_date)
                    ),
                    f"${gross_amount:,.2f}",
                    source_reference,
                    description,
                    str(bank_tx or ""),
                    (
                        linked_invoice_number
                        if linked_invoice_id is not None
                        else ""
                    ),
                    "✅ Yes" if linked_invoice_id is not None else "❌ No",
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 2:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    if linked_invoice_id is not None:
                        item.setBackground(QBrush(QColor("#e8f5e9")))
                    self.receipt_evidence_table.setItem(idx, col, item)

            if selected_only:
                scope = "selected invoice"
            else:
                scope = "all vendor receipts"
            self.receipt_evidence_label.setText(
                f"Receipt evidence ({scope}) for {self.current_vendor}: "
                f"{len(rows)} rows, ${total_amount:,.2f} total, "
                f"${linked_total:,.2f} linked"
            )

        except Exception as e:
            logger.error(f"Failed to refresh receipt evidence: {e}")
            self.receipt_evidence_table.setRowCount(0)
            self.receipt_evidence_label.setText(
                f"Unable to load receipt evidence: {e}"
            )

    @pyqtSlot()
    def _refresh_vendor_ledger(self) -> None:
        """Build a chronological vendor ledger from invoice and payment"
        "rows."""

        if not hasattr(self, "ledger_table"):
            return

        if not self.current_vendor:
            self.ledger_table.setRowCount(0)
            self.ledger_label.setText("Select a vendor to load the ledger.")
            if hasattr(self, "ledger_details_text"):
                self.ledger_details_text.setPlainText(
                    "Select a ledger row to view details."
                )
            return

        try:
            self._ensure_receipt_invoice_link_schema()
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                if (
                    self._hide_pseudo_vendor_invoices()
                    and self._is_pseudo_vendor_name(self.current_vendor)
                ):
                    if not self._is_vendor_included_by_db_filter(
                        self.current_vendor
                    ):
                        self.ledger_table.setRowCount(0)
                        self.ledger_label.setText(
                            "Pseudo-vendor bucket hidden by filter table."
                        )
                        if hasattr(self, "ledger_details_text"):
                            self.ledger_details_text.setPlainText(
                                "No ledger rows available for current "
                                "filters."
                            )
                        return

                cur.execute(
                    """
                    WITH invoice_receipts AS (
                        SELECT
                            vendor_invoice_id,
                            COUNT(*) AS receipt_count,
                            COALESCE(SUM(gross_amount), 0) AS receipt_total
                        FROM receipts
                        WHERE vendor_invoice_id IS NOT NULL
                          AND COALESCE(is_voided, false) = false
                        GROUP BY vendor_invoice_id
                    ),
                    invoice_rows AS (
                        SELECT
                            vi.invoice_date AS row_date,
                            'INVOICE'::text AS row_type,
                            vi.vendor_invoice_id,
                            NULL::integer AS payment_id,
                            COALESCE(vi.invoice_number, '(no #)')
                                AS invoice_number,
                            COALESCE(vi.notes, '') AS details,
                            COALESCE(vi.invoice_amount, 0) AS amount_owed,
                            0::numeric AS amount_paid,
                            COALESCE(ir.receipt_count, 0) AS receipt_count,
                            COALESCE(ir.receipt_total, 0) AS receipt_total,
                            NULL::text AS payment_method,
                            NULL::text AS reference,
                            NULL::integer AS banking_transaction_id
                        FROM vendor_invoices vi
                        LEFT JOIN invoice_receipts ir
                            ON ir.vendor_invoice_id = vi.vendor_invoice_id
                        WHERE vi.vendor_name = %s
                          AND (
                              %s = false
                              OR COALESCE(
                                  vi.invoice_number, ''
                              ) <> 'BANKING_IMPORT'
                          )
                    ),
                    payment_rows AS (
                        SELECT
                            vip.payment_date AS row_date,
                            'PAYMENT'::text AS row_type,
                            vi.vendor_invoice_id,
                            vip.payment_id,
                            COALESCE(vi.invoice_number, '(no #)')
                                AS invoice_number,
                            COALESCE(vip.notes, '') AS details,
                            0::numeric AS amount_owed,
                            ABS(
                                COALESCE(vip.payment_amount, 0)
                            ) AS amount_paid,
                            0::bigint AS receipt_count,
                            0::numeric AS receipt_total,
                            COALESCE(vip.payment_method, '') AS payment_method,
                            COALESCE(vip.reference, '') AS reference,
                            vip.banking_transaction_id
                        FROM vendor_invoice_payments vip
                        JOIN vendor_invoices vi
                            ON vi.vendor_invoice_id = vip.receipt_id
                        WHERE vi.vendor_name = %s
                          AND ABS(COALESCE(vip.payment_amount, 0)) >= 0.005
                          AND (
                              %s = false
                              OR COALESCE(
                                  vi.invoice_number, ''
                              ) <> 'BANKING_IMPORT'
                          )
                    )
                    SELECT *
                    FROM (
                        SELECT * FROM invoice_rows
                        UNION ALL
                        SELECT * FROM payment_rows
                    ) ledger
                    ORDER BY row_date NULLS LAST,
                             CASE WHEN row_type = 'INVOICE' THEN 0 ELSE 1 END,
                             vendor_invoice_id,
                             payment_id NULLS FIRST
                    """,
                    (
                        self.current_vendor,
                        self._hide_auto_import_invoices(),
                        self.current_vendor,
                        self._hide_auto_import_invoices(),
                    ),
                )
                rows = cur.fetchall()

            selected_filter = (
                self.ledger_row_filter.currentText()
                if hasattr(self, "ledger_row_filter")
                else "All"
            )

            if (
                hasattr(self, "ledger_use_date_filter")
                and self.ledger_use_date_filter.isChecked()
            ):
                from_date = self.ledger_date_from.date().toPyDate()
                to_date = self.ledger_date_to.date().toPyDate()
                rows = [
                    r
                    for r in rows
                    if r[0] is not None and from_date <= r[0] <= to_date
                ]

            if selected_filter == "Invoices only":
                rows = [r for r in rows if r[1] == "INVOICE"]
            elif selected_filter == "Payments only":
                rows = [r for r in rows if r[1] == "PAYMENT"]

            self.ledger_table.setRowCount(len(rows))
            running_balance = 0.0
            total_owed = 0.0
            total_paid = 0.0

            for idx, row in enumerate(rows):
                (
                    row_date,
                    row_type,
                    invoice_id,
                    payment_id,
                    invoice_number,
                    details,
                    amount_owed,
                    amount_paid,
                    receipt_count,
                    receipt_total,
                    payment_method,
                    reference,
                    banking_transaction_id,
                ) = row

                amount_owed = float(amount_owed or 0)
                amount_paid = float(amount_paid or 0)
                total_owed += amount_owed
                total_paid += amount_paid
                running_balance += amount_owed - amount_paid

                if row_type == "INVOICE":
                    detail_text = details or ""
                    evidence_text = (
                        f"{int(receipt_count)} receipt(s), "
                        f"${float(receipt_total or 0):,.2f}"
                        if receipt_count
                        else ""
                    )
                else:
                    parts = [
                        part
                        for part in [payment_method, reference, details]
                        if part
                    ]
                    detail_text = " | ".join(parts)
                    if banking_transaction_id:
                        detail_text = (
                            f"{detail_text} | bank tx {banking_transaction_id}"
                            if detail_text
                            else f"bank tx {banking_transaction_id}"
                        )
                    evidence_text = ""

                values = [
                    (
                        row_date.strftime("%m/%d/%Y")
                        if hasattr(row_date, "strftime")
                        else str(row_date or "")
                    ),
                    row_type,
                    invoice_number,
                    detail_text,
                    f"${amount_owed:,.2f}" if amount_owed else "",
                    f"${amount_paid:,.2f}" if amount_paid else "",
                    f"${running_balance:,.2f}",
                    evidence_text,
                ]

                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col in (4, 5, 6):
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    if row_type == "INVOICE":
                        item.setBackground(QBrush(QColor("#fff8e1")))
                    else:
                        item.setBackground(QBrush(QColor("#e8f5e9")))
                    if col == 6:
                        item.setFont(self._get_bold_font())
                    if col == 0:
                        item.setData(
                            Qt.ItemDataRole.UserRole,
                            {
                                "invoice_id": (
                                    int(invoice_id)
                                    if invoice_id is not None
                                    else None
                                ),
                                "row_type": row_type,
                                "payment_id": (
                                    int(payment_id)
                                    if payment_id is not None
                                    else None
                                ),
                            },
                        )
                    self.ledger_table.setItem(idx, col, item)

            self.ledger_label.setText(
                f"Ledger ({selected_filter}) for {self.current_vendor}: "
                f"{len(rows)} rows | Invoiced ${total_owed:,.2f} | "
                f"Paid ${total_paid:,.2f} | Balance ${running_balance:,.2f}"
                + (
                    f" | Date: "
                    f"{self.ledger_date_from.date().toString('MM/dd/yyyy')}"
                    f" to "
                    f"{self.ledger_date_to.date().toString('MM/dd/yyyy')}"
                    if (
                        hasattr(self, "ledger_use_date_filter")
                        and self.ledger_use_date_filter.isChecked()
                    )
                    else ""
                )
            )
            if hasattr(self, "ledger_details_text"):
                self.ledger_details_text.setPlainText(
                    "Select a ledger row to view details."
                )

        except Exception as e:
            logger.error(f"Failed to refresh vendor ledger: {e}")
            self.ledger_table.setRowCount(0)
            self.ledger_label.setText(f"Unable to load ledger: {e}")
            if hasattr(self, "ledger_details_text"):
                self.ledger_details_text.setPlainText(
                    "Unable to load ledger details."
                )

    def _on_ledger_row_activated(self, item) -> None:
        """Jump to matching invoice row when a ledger row is double-clicked."""
        try:
            row = item.row()
            meta_item = self.ledger_table.item(row, 0)
            if not meta_item:
                return

            metadata = meta_item.data(Qt.ItemDataRole.UserRole) or {}
            invoice_id = metadata.get("invoice_id")
            if invoice_id is None:
                return

            selected_row = -1
            for table_row in range(self.invoice_table.rowCount()):
                id_item = self.invoice_table.item(table_row, 0)
                if (
                    id_item
                    and id_item.text().isdigit()
                    and int(id_item.text()) == int(invoice_id)
                ):
                    selected_row = table_row
                    break

            if selected_row >= 0:
                self.invoice_table.selectRow(selected_row)
                self.invoice_table.scrollToItem(
                    self.invoice_table.item(selected_row, 0)
                )
                self.details_tabs.setCurrentIndex(1)  # Edit tab
                self._edit_selected_invoice()
                return

            QMessageBox.information(
                self,
                "Invoice Not In Current View",
                "The linked invoice is not visible with current filters. "
                "Clear filters and try again.",
            )
        except Exception as e:
            logger.error(f"Failed ledger navigation: {e}")

    def _show_selected_ledger_details(self) -> None:
        """Show details for selected ledger row in the inline details panel."""
        if not hasattr(self, "ledger_details_text"):
            return

        row = self.ledger_table.currentRow()
        if row < 0:
            self.ledger_details_text.setPlainText(
                "Select a ledger row to view details."
            )
            return

        meta_item = self.ledger_table.item(row, 0)
        if not meta_item:
            self.ledger_details_text.setPlainText(
                "No metadata available for this row."
            )
            return

        metadata = meta_item.data(Qt.ItemDataRole.UserRole) or {}
        invoice_id = metadata.get("invoice_id")
        row_type = metadata.get("row_type")
        payment_id = metadata.get("payment_id")

        if not invoice_id or not row_type:
            self.ledger_details_text.setPlainText(
                "No details available for this row."
            )
            return

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                if row_type == "INVOICE":
                    cur.execute(
                        """
                        SELECT
                            vi.vendor_invoice_id,
                            COALESCE(vi.invoice_number, '(no #)')
                                AS invoice_number,
                            vi.invoice_date,
                            COALESCE(vi.invoice_amount, 0) AS invoice_amount,
                            COALESCE(vi.notes, '') AS notes,
                            COALESCE(SUM(vip.payment_amount), 0) AS paid_total,
                            COUNT(vip.payment_id) AS payment_rows
                        FROM vendor_invoices vi
                        LEFT JOIN vendor_invoice_payments vip
                            ON vip.receipt_id = vi.vendor_invoice_id
                        WHERE vi.vendor_invoice_id = %s
                        GROUP BY
                            vi.vendor_invoice_id,
                            vi.invoice_number,
                            vi.invoice_date,
                            vi.invoice_amount,
                            vi.notes
                        """,
                        (invoice_id,),
                    )
                    inv_row = cur.fetchone()

                    cur.execute(
                        """
                        SELECT
                            COUNT(*) AS receipt_count,
                            COALESCE(SUM(gross_amount), 0) AS receipt_total
                        FROM receipts
                        WHERE vendor_invoice_id = %s
                          AND COALESCE(is_voided, false) = false
                        """,
                        (invoice_id,),
                    )
                    receipt_count, receipt_total = cur.fetchone()

                    if not inv_row:
                        self.ledger_details_text.setPlainText(
                            "Invoice details not found."
                        )
                        return

                    (
                        inv_id,
                        inv_num,
                        inv_date,
                        inv_amt,
                        notes,
                        paid_total,
                        payment_rows,
                    ) = inv_row
                    balance = float(inv_amt or 0) - float(paid_total or 0)
                    details = [
                        "LEDGER ROW DETAILS",
                        "=" * 40,
                        "Type: INVOICE",
                        f"Invoice ID: {inv_id}",
                        f"Invoice #: {inv_num}",
                        f"Date: {inv_date}",
                        f"Amount Owed: ${float(inv_amt or 0):,.2f}",
                        f"Payments Entered: ${float(paid_total or 0):,.2f} "
                        f"({int(payment_rows or 0)} row(s))",
                        f"Balance: ${balance:,.2f}",
                        f"Linked Receipts: {int(receipt_count or 0)} row(s), "
                        f"${float(receipt_total or 0):,.2f}",
                        f"Notes: {notes or '-'}",
                    ]
                    self.ledger_details_text.setPlainText("\n".join(details))
                    return

                if row_type == "PAYMENT" and payment_id:
                    cur.execute(
                        """
                        SELECT
                            vip.payment_id,
                            vip.payment_date,
                            COALESCE(vip.payment_amount, 0) AS payment_amount,
                            COALESCE(vip.payment_method, '') AS payment_method,
                            COALESCE(vip.reference, '') AS reference,
                            vip.banking_transaction_id,
                            COALESCE(vip.notes, '') AS notes,
                            COALESCE(vi.invoice_number, '(no #)')
                                AS invoice_number,
                            vi.vendor_invoice_id,
                            bt.transaction_date,
                            COALESCE(bt.check_number, '') AS check_number,
                            COALESCE(bt.description, '') AS bank_description
                        FROM vendor_invoice_payments vip
                        JOIN vendor_invoices vi
                            ON vi.vendor_invoice_id = vip.receipt_id
                        LEFT JOIN banking_transactions bt
                            ON bt.transaction_id = vip.banking_transaction_id
                        WHERE vip.payment_id = %s
                        """,
                        (payment_id,),
                    )
                    pay_row = cur.fetchone()

                    if not pay_row:
                        self.ledger_details_text.setPlainText(
                            "Payment details not found."
                        )
                        return

                    (
                        pay_id,
                        pay_date,
                        pay_amt,
                        pay_method,
                        pay_ref,
                        bank_tx,
                        pay_notes,
                        inv_num,
                        inv_id,
                        bank_date,
                        check_number,
                        bank_desc,
                    ) = pay_row

                    details = [
                        "LEDGER ROW DETAILS",
                        "=" * 40,
                        "Type: PAYMENT",
                        f"Payment ID: {pay_id}",
                        f"Date: {pay_date}",
                        f"Amount Paid: ${float(pay_amt or 0):,.2f}",
                        f"Method: {pay_method or '-'}",
                        f"Reference: {pay_ref or '-'}",
                        f"Invoice: {inv_num} (ID {inv_id})",
                        f"Bank TX: {bank_tx or '-'}",
                        f"Bank Date: {bank_date or '-'}",
                        f"Check #: {check_number or '-'}",
                        f"Bank Description: {bank_desc or '-'}",
                        f"Notes: {pay_notes or '-'}",
                    ]
                    self.ledger_details_text.setPlainText("\n".join(details))
                    return

                self.ledger_details_text.setPlainText(
                    "No detail view available for this row type."
                )

        except Exception as e:
            logger.error(f"Failed ledger detail view: {e}")
            self.ledger_details_text.setPlainText(
                f"Unable to load row details: {e}"
            )

    def _link_selected_receipt_to_selected_invoice(self) -> None:
        """Link the selected receipt evidence row to the selected invoice."""
        if not self.current_vendor:
            QMessageBox.warning(
                self, "No Vendor", "Please select a vendor first."
            )
            return

        invoice_row = self.invoice_table.currentRow()
        if invoice_row < 0 or invoice_row >= len(self.current_invoices):
            QMessageBox.warning(
                self, "No Invoice", "Select an invoice row first."
            )
            return

        receipt_row = self.receipt_evidence_table.currentRow()
        if receipt_row < 0:
            QMessageBox.warning(
                self, "No Receipt", "Select a receipt row first."
            )
            return

        receipt_id = int(
            self.receipt_evidence_table.item(receipt_row, 0).text()
        )
        invoice_id = int(self.current_invoices[invoice_row][0])
        invoice_ref = (
            self.current_invoices[invoice_row][1] or f"R-{invoice_id}"
        )

        try:
            self._ensure_receipt_invoice_link_schema()
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE receipts"
                    " SET vendor_invoice_id = %s"
                    " WHERE receipt_id = %s",
                    (invoice_id, receipt_id),
                )

            QMessageBox.information(
                self,
                "Receipt Linked",
                f"Receipt #{receipt_id} linked to invoice"
                f" {invoice_ref}.\n\nThis affects receipt"
                " evidence only, not payment balance.",
            )
            self._load_vendor_invoices()
            self._refresh_receipt_evidence()
            self._refresh_account_summary()

        except Exception as e:
            logger.error(f"Failed to link receipt: {e}")
            QMessageBox.critical(
                self, "Link Error", f"Failed to link receipt:\n\n{e}"
            )

    @pyqtSlot()
    def _unlink_selected_receipt_from_invoice(self) -> None:
        """Remove the invoice link from the selected receipt evidence row."""
        receipt_row = self.receipt_evidence_table.currentRow()
        if receipt_row < 0:
            QMessageBox.warning(
                self, "No Receipt", "Select a linked receipt row first."
            )
            return

        receipt_id = int(
            self.receipt_evidence_table.item(receipt_row, 0).text()
        )
        linked_invoice = (
            self.receipt_evidence_table.item(receipt_row, 6).text() or ""
        ).strip()
        if not linked_invoice:
            QMessageBox.information(
                self,
                "Already Unlinked",
                "This receipt is not linked to an invoice.",
            )
            return

        try:
            self._ensure_receipt_invoice_link_schema()
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE receipts"
                    " SET vendor_invoice_id = NULL"
                    " WHERE receipt_id = %s",
                    (receipt_id,),
                )

            QMessageBox.information(
                self,
                "Receipt Unlinked",
                f"Removed invoice link from receipt #{receipt_id}.",
            )
            self._load_vendor_invoices()
            self._refresh_receipt_evidence()
            self._refresh_account_summary()

        except Exception as e:
            logger.error(f"Failed to unlink receipt: {e}")
            QMessageBox.critical(
                self, "Unlink Error", f"Failed to unlink receipt:\n\n{e}"
            )

    def _selected_invoice_ids(self) -> list[int]:
        """Return selected invoice IDs from the invoice grid."""
        ids = []
        selected_rows = set(
            item.row() for item in self.invoice_table.selectedItems()
        )
        for row in selected_rows:
            if row < len(self.current_invoices):
                ids.append(int(self.current_invoices[row][0]))
        return ids

    @pyqtSlot()
    def _refresh_payment_history(self) -> None:
        """Load entered payment rows for current vendor.

        Helps users verify data entry.
        """
        if not hasattr(self, "payment_history_table"):
            return

        if not self.current_vendor:
            self.payment_history_table.setRowCount(0)
            self.payment_history_label.setText(
                "Select a vendor to view payment history."
            )
            return

        selected_ids = self._selected_invoice_ids()
        selected_only = (
            hasattr(self, "payment_selected_only_chk")
            and self.payment_selected_only_chk.isChecked()
        )

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vendor_invoice_payments (
                        payment_id SERIAL PRIMARY KEY,
                        receipt_id INTEGER NOT NULL,
                        payment_date DATE NOT NULL,
                        payment_amount DECIMAL(10,2) NOT NULL,
                        payment_method VARCHAR(50),
                        reference VARCHAR(255),
                        banking_transaction_id INTEGER,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                sql = """
                    SELECT
                        vip.payment_id,
                        vip.receipt_id,
                        COALESCE(vi.invoice_number, '(no #)')
                            AS invoice_number,
                        vip.payment_date,
                        vip.payment_amount,
                        COALESCE(vip.payment_method, '') AS payment_method,
                        COALESCE(vip.reference, '') AS reference,
                        vip.banking_transaction_id,
                        vip.created_at
                    FROM vendor_invoice_payments vip
                    JOIN vendor_invoices vi
                        ON vi.vendor_invoice_id = vip.receipt_id
                    WHERE vi.vendor_name = %s
                      AND ABS(COALESCE(vip.payment_amount, 0)) >= 0.005
                """
                params = [self.current_vendor]

                if selected_only and selected_ids:
                    sql += " AND vip.receipt_id = ANY(%s)"
                    params.append(selected_ids)
                elif selected_only:
                    self.payment_history_table.setRowCount(0)
                    self.payment_history_label.setText(
                        "No invoice selected. Select one or more invoices to "
                        "filter payment rows."
                    )
                    return

                sql += (
                    " ORDER BY vip.payment_date DESC, vip.payment_id DESC "
                    "LIMIT 300"
                )
                cur.execute(sql, params)
                rows = cur.fetchall()

            self.payment_history_table.setRowCount(len(rows))
            total_amount = 0.0

            for idx, row in enumerate(rows):
                (
                    payment_id,
                    invoice_id,
                    invoice_num,
                    pay_date,
                    pay_amt,
                    pay_method,
                    pay_ref,
                    bank_tx,
                    created_at,
                ) = row
                pay_amt = abs(float(pay_amt or 0))
                total_amount += pay_amt

                values = [
                    str(payment_id),
                    str(invoice_id),
                    str(invoice_num),
                    (
                        pay_date.strftime("%m/%d/%Y")
                        if hasattr(pay_date, "strftime")
                        else str(pay_date)
                    ),
                    f"${pay_amt:,.2f}",
                    pay_method,
                    pay_ref,
                    str(bank_tx or ""),
                    (
                        created_at.strftime("%Y-%m-%d %H:%M")
                        if hasattr(created_at, "strftime")
                        else str(created_at)
                    ),
                ]

                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 4:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    if col == 5 and str(pay_method).lower() == "cash":
                        item.setBackground(QBrush(QColor("#fff4ce")))
                    self.payment_history_table.setItem(idx, col, item)

            scope = "selected invoices" if selected_only else "all invoices"
            self.payment_history_label.setText(
                f"Payment rows ({scope}) for {self.current_vendor}: "
                f"{len(rows)} rows, ${total_amount:,.2f} total"
            )

        except Exception as e:
            logger.error(f"Failed to refresh payment history: {e}")
            self.payment_history_table.setRowCount(0)
            self.payment_history_label.setText(
                f"Unable to load payment history: {e}"
            )

    def _find_existing_payment_rows(
        self,
        allocations,
        payment_date,
        payment_method,
        payment_ref,
        receipt_tx=None,
    ) -> list[tuple]:
        """Find existing rows likely to be duplicate payment entries."""
        if not self.current_vendor or not allocations:
            return []

        matches = []
        ref_like = f"%{payment_ref.strip()}%" if payment_ref else None
        receipt_tx_like = f"%{receipt_tx.strip()}%" if receipt_tx else None

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vendor_invoice_payments (
                        payment_id SERIAL PRIMARY KEY,
                        receipt_id INTEGER NOT NULL,
                        payment_date DATE NOT NULL,
                        payment_amount DECIMAL(10,2) NOT NULL,
                        payment_method VARCHAR(50),
                        reference VARCHAR(255),
                        banking_transaction_id INTEGER,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                for receipt_id, expected_amount in allocations.items():
                    if ref_like or receipt_tx_like:
                        cur.execute(
                            """
                            SELECT
                                vip.payment_id,
                                vip.receipt_id,
                                COALESCE(vi.invoice_number, '(no #)'),
                                vip.payment_date,
                                vip.payment_amount,
                                COALESCE(vip.payment_method, ''),
                                COALESCE(vip.reference, ''),
                                vip.banking_transaction_id
                            FROM vendor_invoice_payments vip
                            JOIN vendor_invoices vi
                                ON vi.vendor_invoice_id = vip.receipt_id
                            WHERE vi.vendor_name = %s
                              AND vip.receipt_id = %s
                              AND vip.payment_date = %s
                              AND LOWER(
                                  COALESCE(vip.payment_method, '')
                              ) = LOWER(%s)
                              AND (
                                    ABS(ABS(vip.payment_amount) - %s) < 0.01
                                OR COALESCE(vip.reference, '') ILIKE %s
                                OR COALESCE(vip.notes, '') ILIKE %s
                              )
                            ORDER BY vip.payment_id DESC
                            LIMIT 20
                            """,
                            (
                                self.current_vendor,
                                receipt_id,
                                payment_date,
                                payment_method,
                                expected_amount,
                                ref_like or "",
                                receipt_tx_like or "",
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT
                                vip.payment_id,
                                vip.receipt_id,
                                COALESCE(vi.invoice_number, '(no #)'),
                                vip.payment_date,
                                vip.payment_amount,
                                COALESCE(vip.payment_method, ''),
                                COALESCE(vip.reference, ''),
                                vip.banking_transaction_id
                            FROM vendor_invoice_payments vip
                            JOIN vendor_invoices vi
                                ON vi.vendor_invoice_id = vip.receipt_id
                            WHERE vi.vendor_name = %s
                              AND vip.receipt_id = %s
                              AND vip.payment_date = %s
                              AND LOWER(
                                  COALESCE(vip.payment_method, '')
                              ) = LOWER(%s)
                              AND ABS(ABS(vip.payment_amount) - %s) < 0.01
                            ORDER BY vip.payment_id DESC
                            LIMIT 20
                            """,
                            (
                                self.current_vendor,
                                receipt_id,
                                payment_date,
                                payment_method,
                                expected_amount,
                            ),
                        )

                    matches.extend(cur.fetchall())

        except Exception as e:
            logger.error(f"Failed duplicate lookup: {e}")

        return matches

    def _find_matching_receipts_for_allocations(
        self, allocations, payment_date, banking_id=None, receipt_tx=None
    ) -> dict[int, list[tuple]]:
        """Find receipt rows matching vendor+amount+date and/or banking tx."""
        if not self.current_vendor or not allocations:
            return {}

        matches_by_invoice = {
            int(invoice_id): [] for invoice_id in allocations.keys()
        }

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                vendor_account_id = self._get_vendor_account_id(
                    cur, self.current_vendor
                )

                for invoice_id, alloc_amount in allocations.items():
                    receipt_tx_clean = (receipt_tx or "").strip()
                    sql = """
                        SELECT
                            r.receipt_id,
                            r.receipt_date,
                            COALESCE(r.gross_amount, 0) AS gross_amount,
                            r.banking_transaction_id,
                            r.vendor_invoice_id,
                            COALESCE(r.source_reference, '')
                                AS source_reference,
                            COALESCE(r.description, '') AS description
                        FROM receipts r
                        WHERE COALESCE(r.is_voided, false) = false
                    """
                    params = []

                    if vendor_account_id is not None:
                        sql += " AND r.vendor_account_id = %s"
                        params.append(vendor_account_id)
                    else:
                        sql += " AND r.vendor_name ILIKE %s"
                        params.append(self.current_vendor)

                    match_clauses = [
                        "(r.receipt_date = %s"
                        " AND ABS(COALESCE(r.gross_amount, 0) - %s) < 0.01)"
                    ]
                    params.extend([payment_date, alloc_amount])

                    if banking_id is not None:
                        match_clauses.append("r.banking_transaction_id = %s")
                        params.append(banking_id)

                    if receipt_tx_clean:
                        match_clauses.append("CAST(r.receipt_id AS TEXT) = %s")
                        params.append(receipt_tx_clean)
                        match_clauses.append(
                            "UPPER(COALESCE(r.source_reference, ''))"
                            " = UPPER(%s)"
                        )
                        params.append(receipt_tx_clean)

                    sql += " AND (" + " OR ".join(match_clauses) + ")"

                    sql += """
                        ORDER BY
                            CASE WHEN r.vendor_invoice_id IS NULL
                                THEN 0 ELSE 1 END,
                            r.receipt_date,
                            r.receipt_id
                        LIMIT 20
                    """

                    cur.execute(sql, params)
                    matches_by_invoice[int(invoice_id)] = cur.fetchall()
        except Exception as e:
            logger.error(f"Failed receipt match lookup: {e}")

        return matches_by_invoice

    def _validate_receipt_matches_before_payment(
        self,
        allocations,
        payment_date,
        banking_id=None,
        receipt_tx=None,
        payment_method=None,
        payment_ref=None,
        allow_auto_create_cash_receipt=True,
    ) -> bool:
        """Validate receipt matches before posting payments.

        Auto-links safe unique matches.
        """
        if not allocations:
            return True

        matches_by_invoice = self._find_matching_receipts_for_allocations(
            allocations,
            payment_date,
            banking_id,
            receipt_tx,
        )

        missing = []
        ambiguous = []
        linked_elsewhere = []
        auto_link_updates = []
        auto_created_receipts = []

        for invoice_id, alloc_amount in allocations.items():
            candidates = matches_by_invoice.get(int(invoice_id), [])
            if not candidates:
                missing.append((invoice_id, alloc_amount))
                continue

            exact_for_invoice = [
                row for row in candidates if row[4] == int(invoice_id)
            ]
            unlinked = [row for row in candidates if row[4] is None]
            linked_other = [
                row
                for row in candidates
                if row[4] not in (None, int(invoice_id))
            ]

            if exact_for_invoice:
                continue

            if len(unlinked) == 1 and not linked_other:
                auto_link_updates.append(
                    (int(invoice_id), int(unlinked[0][0]))
                )
                continue

            if linked_other and not unlinked:
                linked_elsewhere.append(
                    (invoice_id, alloc_amount, linked_other)
                )
                continue

            ambiguous.append((invoice_id, alloc_amount, candidates))

        is_cash_payment = str(payment_method or "").strip().lower() == "cash"
        if is_cash_payment and allow_auto_create_cash_receipt and missing:
            still_missing = []
            for invoice_id, alloc_amount in missing:
                rec_id = self._create_auto_cash_receipt_for_invoice(
                    int(invoice_id),
                    float(alloc_amount),
                    payment_date,
                    receipt_tx=receipt_tx,
                    payment_ref=payment_ref,
                    banking_id=banking_id,
                )
                if rec_id is not None:
                    auto_created_receipts.append(
                        (int(invoice_id), int(rec_id), float(alloc_amount))
                    )
                else:
                    still_missing.append((invoice_id, alloc_amount))
            missing = still_missing

        if auto_link_updates:
            try:
                with DatabaseContext(self.conn, auto_commit=True) as cur:
                    for invoice_id, receipt_id in auto_link_updates:
                        cur.execute(
                            """
                            UPDATE receipts
                            SET vendor_invoice_id = %s
                            WHERE receipt_id = %s
                              AND vendor_invoice_id IS NULL
                            """,
                            (invoice_id, receipt_id),
                        )
            except Exception as e:
                logger.error(f"Failed auto-linking matched receipts: {e}")

        issues = []
        if missing:
            for invoice_id, alloc_amount in missing:
                issues.append(
                    f"No exact receipt match for invoice ID"
                    f" {invoice_id} at"
                    f" ${float(alloc_amount):,.2f}"
                    f" on {payment_date}"
                )

        if linked_elsewhere:
            for invoice_id, alloc_amount, rows in linked_elsewhere:
                first = rows[0]
                issues.append(
                    f"Matching receipt exists but is linked"
                    f" to invoice ID {first[4]}"
                    f" (target invoice ID {invoice_id},"
                    f" ${float(alloc_amount):,.2f})"
                )

        if ambiguous:
            for invoice_id, alloc_amount, rows in ambiguous:
                issues.append(
                    f"Multiple receipt matches for invoice"
                    f" ID {invoice_id} at"
                    f" ${float(alloc_amount):,.2f}"
                    f" on {payment_date}"
                    f" ({len(rows)} candidates)"
                )

        if not issues:
            if auto_link_updates or auto_created_receipts:
                created_msg = ""
                if auto_created_receipts:
                    created_msg = (
                        f"\nCreated {len(auto_created_receipts)}"
                        " cash receipt row(s) and linked"
                        " them to invoice(s)."
                    )
                QMessageBox.information(
                    self,
                    "Receipt Match Check",
                    f"Matched and linked"
                    f" {len(auto_link_updates)} receipt row(s)"
                    " to invoice(s) before posting"
                    f" payment.{created_msg}",
                )
            return True

        prompt_lines = []
        if auto_link_updates:
            prompt_lines.append(
                f"Auto-linked {len(auto_link_updates)}"
                " exact receipt match(es) before posting."
            )
            prompt_lines.append("")

        if auto_created_receipts:
            prompt_lines.append(
                f"Auto-created {len(auto_created_receipts)}"
                " cash receipt row(s) for missing matches."
            )
            prompt_lines.append("")

        prompt_lines.append(
            "Receipt match check found issues"
            " (using date/amount, banking tx,"
            " and receipt tx if provided):"
        )
        prompt_lines.extend([f"- {line}" for line in issues[:12]])
        if len(issues) > 12:
            prompt_lines.append(f"- ... and {len(issues) - 12} more")
        prompt_lines.append("")
        prompt_lines.append("Post payment anyway?")

        choice = QMessageBox.question(
            self,
            "Receipt Match Warning",
            "\n".join(prompt_lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return choice == QMessageBox.StandardButton.Yes

    def _create_auto_cash_receipt_for_invoice(
        self,
        invoice_id,
        amount,
        payment_date,
        receipt_tx=None,
        payment_ref=None,
        banking_id=None,
    ) -> int | None:
        """Create a cash receipt linked to an invoice when none exists."""
        if amount <= 0:
            return None

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                # Reuse existing equivalent cash receipt if one already exists.
                cur.execute(
                    """
                    SELECT receipt_id
                    FROM receipts
                    WHERE vendor_invoice_id = %s
                      AND receipt_date = %s
                      AND ABS(COALESCE(gross_amount, 0) - %s) < 0.01
                      AND LOWER(COALESCE(payment_method, '')) = 'cash'
                      AND COALESCE(is_voided, false) = false
                    ORDER BY receipt_id DESC
                    LIMIT 1
                    """,
                    (invoice_id, payment_date, amount),
                )
                existing = cur.fetchone()
                if existing:
                    return int(existing[0])

                cur.execute(
                    """
                    SELECT
                        vi.vendor_invoice_id,
                        vi.vendor_name,
                        COALESCE(vi.invoice_number, '') AS invoice_number,
                        va.account_id,
                        COALESCE(va.canonical_vendor, vi.vendor_name)
                            AS canonical_vendor
                    FROM vendor_invoices vi
                    LEFT JOIN vendor_accounts va
                        ON va.display_name = vi.vendor_name
                        OR va.canonical_vendor = vi.vendor_name
                    WHERE vi.vendor_invoice_id = %s
                    LIMIT 1
                    """,
                    (invoice_id,),
                )
                invoice_row = cur.fetchone()
                if not invoice_row:
                    return None

                (
                    _,
                    vendor_name,
                    invoice_number,
                    vendor_account_id,
                    canonical_vendor,
                ) = invoice_row
                receipt_tx_clean = (receipt_tx or "").strip()
                payment_ref_clean = (payment_ref or "").strip()

                source_reference = (
                    receipt_tx_clean
                    or payment_ref_clean
                    or f"AUTO-CASH-{invoice_id}-{payment_date}"
                )
                description_parts = ["Auto-generated cash receipt"]
                if invoice_number:
                    description_parts.append(f"for invoice #{invoice_number}")
                else:
                    description_parts.append(f"for invoice ID {invoice_id}")
                description = " ".join(description_parts)

                cur.execute(
                    """
                    INSERT INTO receipts (
                        receipt_date,
                        vendor_name,
                        canonical_vendor,
                        vendor_account_id,
                        gross_amount,
                        net_amount,
                        gst_amount,
                        payment_method,
                        source_reference,
                        description,
                        receipt_source,
                        source_system,
                        banking_transaction_id,
                        vendor_invoice_id
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING receipt_id
                    """,
                    (
                        payment_date,
                        vendor_name,
                        canonical_vendor,
                        vendor_account_id,
                        amount,
                        amount,
                        0,
                        "cash",
                        source_reference,
                        description,
                        "auto_cash_payment",
                        "vendor_invoice_manager",
                        banking_id,
                        invoice_id,
                    ),
                )
                created_id = cur.fetchone()
                return int(created_id[0]) if created_id else None
        except Exception as e:
            logger.error(
                f"Failed auto-create cash receipt"
                f" for invoice {invoice_id}: {e}"
            )
            return None

    def _confirm_duplicate_payment_continue(
        self,
        allocations,
        payment_date,
        payment_method,
        payment_ref,
        receipt_tx=None,
    ) -> bool:
        """Prompt user when likely duplicate payment rows already exist."""
        existing = self._find_existing_payment_rows(
            allocations,
            payment_date,
            payment_method,
            payment_ref,
            receipt_tx,
        )
        if not existing:
            return True

        lines = []
        for row in existing[:12]:
            (
                payment_id,
                receipt_id,
                invoice_num,
                pay_date,
                pay_amt,
                method,
                ref,
                bank_tx,
            ) = row
            lines.append(
                f"  \u2022 payment_id={payment_id},"
                f" invoice={invoice_num} (ID {receipt_id}),"
                f" date={pay_date},"
                f" amount=${float(pay_amt):.2f},"
                f" method={method},"
                f" ref={ref or '-'},"
                f" bank_tx={bank_tx or '-'}"
            )

        warning = (
            "Potential duplicate payment entries found"
            " for this vendor/invoice/date.\n\n"
            + "\n".join(lines)
            + "\n\nContinue and record another payment anyway?"
        )

        choice = QMessageBox.question(
            self,
            "Possible Duplicate Payment",
            warning,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return choice == QMessageBox.StandardButton.Yes

    @staticmethod
    def _compose_payment_note(base_note, receipt_tx=None) -> str:
        """Build consistent notes payload for payment rows."""
        receipt_tx_clean = (receipt_tx or "").strip()
        if receipt_tx_clean:
            return f"ReceiptTX:{receipt_tx_clean} | {base_note}"
        return base_note

    @staticmethod
    def _lock_and_validate_payment_allocations(cur, allocations) -> None:
        """Lock invoices and validate payment rows before insertion."""
        for receipt_id in sorted(allocations):
            payment_amount = Decimal(str(allocations[receipt_id]))
            if payment_amount <= 0:
                raise ValueError(
                    f"Payment for invoice ID {receipt_id} must be greater than $0.00."
                )

            cur.execute(
                """
                SELECT
                    COALESCE(invoice_number, '')
                FROM vendor_invoices
                WHERE vendor_invoice_id = %s
                FOR UPDATE
                """,
                (receipt_id,),
            )
            invoice_row = cur.fetchone()
            if not invoice_row:
                raise ValueError(f"Invoice ID {receipt_id} no longer exists.")

    def _check_existing_payment_entries(self) -> None:
        """Manual check: verify a cash/check payment was already entered."""
        if not self.current_vendor:
            QMessageBox.warning(
                self, "No Vendor", "Please select a vendor first."
            )
            return

        selected_ids = self._selected_invoice_ids()
        if not selected_ids:
            QMessageBox.warning(
                self,
                "No Invoice Selection",
                "Select at least one invoice row,"
                " then click 'Check Existing Payment'.",
            )
            return

        payment_amt = self.payment_amount.get_value()
        payment_date = self.payment_date.date().toPyDate()
        payment_method = self.payment_method.currentText()
        payment_ref = self.payment_reference.text().strip()
        receipt_tx = self.payment_receipt_tx.text().strip()

        allocations = {
            invoice_id: (payment_amt if payment_amt > 0 else 0.0)
            for invoice_id in selected_ids
        }
        matches = self._find_existing_payment_rows(
            allocations,
            payment_date,
            payment_method,
            payment_ref,
            receipt_tx,
        )

        if not matches:
            QMessageBox.information(
                self,
                "No Exact Matches",
                "No matching entered payment rows found"
                " for selected invoice(s) with this"
                " date/method.\n"
                "Tip: add check/reference number to tighten the search.",
            )
            return

        lines = []
        for row in matches[:20]:
            (
                payment_id,
                receipt_id,
                invoice_num,
                pay_date,
                pay_amt,
                method,
                ref,
                bank_tx,
            ) = row
            lines.append(
                f"payment_id={payment_id}"
                f" | invoice={invoice_num} (ID {receipt_id}) | "
                f"date={pay_date}"
                f" | amount=${float(pay_amt):.2f}"
                f" | method={method} | "
                f"ref={ref or '-'}"
                f" | bank_tx={bank_tx or '-'}"
            )

        QMessageBox.information(
            self,
            "Existing Payment Rows Found",
            "\n".join(lines),
        )

    def _toggle_banking_date_filter(self, checked) -> None:
        """Enable/disable date range filter for banking search"""
        self.banking_date_from.setEnabled(checked)
        self.banking_date_to.setEnabled(checked)
        self.banking_preset_label.setEnabled(checked)
        self.banking_preset_year.setEnabled(checked)
        self.banking_preset_lastyear.setEnabled(checked)
        self.banking_preset_all.setEnabled(checked)

    def _toggle_ledger_date_filter(self, checked) -> None:
        """Enable or disable date filter controls for ledger view."""
        if hasattr(self, "ledger_date_from"):
            self.ledger_date_from.setEnabled(checked)
        if hasattr(self, "ledger_date_to"):
            self.ledger_date_to.setEnabled(checked)
        self._refresh_vendor_ledger()

    def _set_banking_date_preset(self, preset) -> None:
        """Set date range to preset values"""
        today = QDate.currentDate()

        if preset == "year":
            # This calendar year
            start = QDate(today.year(), 1, 1)
            end = today
        elif preset == "last_year":
            # Last calendar year
            start = QDate(today.year() - 1, 1, 1)
            end = QDate(today.year() - 1, 12, 31)
        elif preset == "all":
            # All time (5 years back is reasonable for banking)
            start = QDate(2010, 1, 1)
            end = today
        else:
            return

        self.banking_date_from.setDate(start)
        self.banking_date_to.setDate(end)
        self.banking_use_date_filter.setChecked(True)

    def _apply_invoice_filters(self) -> None:
        """Apply filters to invoice table"""
        if not hasattr(self, "current_invoices") or not self.current_invoices:
            return

        invoice_num_filter = self.filter_invoice_num.text().strip().lower()
        year_filter = self.filter_year.currentData()
        status_filter = self.filter_status.currentText()

        # Store full list if not already stored
        if not hasattr(self, "unfiltered_invoices"):
            self.unfiltered_invoices = self.current_invoices.copy()

        # Start with all invoices
        filtered = self.unfiltered_invoices.copy()

        # Apply invoice number filter
        if invoice_num_filter:
            filtered = [
                inv
                for inv in filtered
                if invoice_num_filter in str(inv[1]).lower()
            ]

        # Apply year filter
        if year_filter is not None:
            filtered = [
                inv
                for inv in filtered
                if inv[3] and str(inv[3]).startswith(str(year_filter))
            ]

        # Apply status filter
        if status_filter == "Paid":
            filtered = [inv for inv in filtered if inv[7] == "✅ Paid"]
        elif status_filter == "Unpaid":
            filtered = [inv for inv in filtered if inv[7] == "❌ Unpaid"]

        # Keep filtered results in chronological order.
        filtered.sort(key=self._invoice_sort_key)

        # Update current_invoices and refresh
        self.current_invoices = filtered
        self._refresh_invoice_table()

        # Show count
        if filtered != self.unfiltered_invoices:
            self.vendor_header.setText(
                f"📋 Invoices for: {self.current_vendor} "
                f"(showing {len(filtered)}"
                f" of {len(self.unfiltered_invoices)})"
            )

    def _invoice_sort_key(self, invoice_row) -> tuple[int, int]:
        """Sort invoices oldest to newest by date, then by ID."""
        invoice_id = (
            int(invoice_row[0])
            if invoice_row and invoice_row[0] is not None
            else 0
        )
        invoice_date = invoice_row[3] if len(invoice_row) > 3 else None

        if hasattr(invoice_date, "toordinal"):
            return (invoice_date.toordinal(), invoice_id)

        if isinstance(invoice_date, str):
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(invoice_date, fmt).date()
                    return (parsed.toordinal(), invoice_id)
                except Exception:
                    continue

        return (0, invoice_id)

    @pyqtSlot()
    def _clear_invoice_filters(self) -> None:
        """Clear all invoice filters"""
        self.filter_invoice_num.clear()
        self.filter_year.setCurrentIndex(0)
        self.filter_status.setCurrentIndex(0)
        if self.hide_auto_import_checkbox is not None:
            self.hide_auto_import_checkbox.setChecked(True)
        if (
            hasattr(self, "hide_pseudo_vendor_checkbox")
            and self.hide_pseudo_vendor_checkbox is not None
        ):
            self.hide_pseudo_vendor_checkbox.setChecked(True)

        # Restore full list
        if hasattr(self, "unfiltered_invoices"):
            self.current_invoices = self.unfiltered_invoices.copy()
            self._refresh_invoice_table()
            self._refresh_payment_history()
            self.vendor_header.setText(
                f"📋 Invoices for: {self.current_vendor}"
            )

    @pyqtSlot()
    def _lookup_invoice_number(self) -> None:
        """Scroll to first visible invoice matching the search text."""
        query = self.filter_invoice_num.text().strip().lower()
        if not query:
            return

        for row in range(self.invoice_table.rowCount()):
            item = self.invoice_table.item(row, 1)
            if item and query in item.text().strip().lower():
                self.invoice_table.setCurrentCell(row, 1)
                self.invoice_table.selectRow(row)
                self.invoice_table.scrollToItem(item)
                return

        QMessageBox.information(
            self,
            "Invoice Not Found",
            f"No visible invoice number matches '{query}'.",
        )

    def _hide_auto_import_invoices(self) -> bool:
        """Return True if BANKING_IMPORT invoices should be hidden."""
        return bool(
            self.hide_auto_import_checkbox is not None
            and self.hide_auto_import_checkbox.isChecked()
        )

    def _hide_pseudo_vendor_invoices(self) -> bool:
        """Return True when pseudo-vendor buckets should be excluded."""
        return bool(
            hasattr(self, "hide_pseudo_vendor_checkbox")
            and self.hide_pseudo_vendor_checkbox is not None
            and self.hide_pseudo_vendor_checkbox.isChecked()
        )

    @staticmethod
    def _is_pseudo_vendor_name(vendor_name: str | None) -> bool:
        """Heuristic filter for non-AP pseudo-vendor bucket names."""
        normalized = (vendor_name or "").strip().upper()
        if not normalized:
            return False

        exact_matches = {
            "WITHDRAWAL",
            "CASH WITHDRAWAL",
            "BANK WITHDRAWAL",
            "LOAN PAYMENT",
            "UNCATEGORIZED EXPENSE",
            "UNKNOWN PAYEE",
            "DEPOSIT",
            "SQUARE DEPOSIT",
            "EMAIL TRANSFER",
            "E-TRANSFER PAYMENT",
            "SERVICE CHARGE",
            "NSF CHARGE",
            "POINT OF SALE PURCHASE",
            "PURCHASE",
            "FUEL PURCHASE",
            "DRIVER REIMBURSEMENT",
            "CHARTER PAYMENT",
            "BANK",
            "CIBC",
        }
        if normalized in exact_matches:
            return True

        keyword_matches = (
            "WITHDRAWAL",
            "DEPOSIT",
            "NSF",
            "SERVICE CHARGE",
            "POINT OF SALE",
        )
        return any(keyword in normalized for keyword in keyword_matches)

    def _load_vendor_invoices(self) -> None:
        """Load all invoices for current vendor using direct payment totals.

        Invoice balances are based only on rows in vendor_invoice_payments.
        Vendor receipts are separate evidence/support records for ITC
        review and are shown separately in the header/summary, but they do not
        automatically reduce invoice balances.
        """
        if not self.current_vendor:
            return

        if self._hide_pseudo_vendor_invoices() and self._is_pseudo_vendor_name(
            self.current_vendor
        ):
            if self._is_vendor_included_by_db_filter(self.current_vendor):
                # Explicitly included in DB filter table, so do not hide.
                pass
            else:
                self.current_invoices = []
                self.unfiltered_invoices = []
                self.current_receipts_total = 0.0
                self.current_entered_payments_total = 0.0
                self.vendor_header.setText(
                    f"📋 Invoices for: {self.current_vendor}"
                    " (hidden pseudo-vendor)"
                )
                self.balance_label.setText(
                    "Pseudo-vendor hidden by filter table."
                    " Disable 'Hide Pseudo Vendors' to view."
                )
                self.balance_label.setStyleSheet(
                    "font-size: 12px; padding: 5px;"
                    " color: #666; font-weight: bold;"
                )
                self._refresh_invoice_table()
                return

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                self._ensure_receipt_invoice_link_schema()
                # 1. Load all invoices sorted oldest first (FIFO order)
                invoice_sql = [
                    "SELECT",
                    "    vi.vendor_invoice_id,",
                    "    vi.invoice_number,",
                    "    COALESCE(vi.notes, '') as invoice_details,",
                    "    vi.invoice_date,",
                    "    COALESCE(vi.invoice_amount, 0) as invoice_amount",
                    "FROM vendor_invoices vi",
                    "WHERE vi.vendor_name = %s",
                ]
                invoice_params = [self.current_vendor]

                if self._hide_auto_import_invoices():
                    invoice_sql.append(
                        "AND COALESCE(vi.invoice_number, '') "
                        "<> 'BANKING_IMPORT'"
                    )

                invoice_sql.append(
                    "ORDER BY vi.invoice_date, vi.vendor_invoice_id"
                )
                cur.execute("\n".join(invoice_sql), invoice_params)
                invoices = cur.fetchall()

                # 2. Separate receipt totals (expense/ITC evidence).
                vendor_account_id = self._get_vendor_account_id(
                    cur, self.current_vendor
                )

                if vendor_account_id is not None:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(gross_amount), 0)
                        FROM receipts
                        WHERE vendor_account_id = %s
                          AND COALESCE(is_voided, false) = false
                    """,
                        (vendor_account_id,),
                    )
                else:
                    # Fallback: match by vendor_name case-insensitive
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(gross_amount), 0)
                        FROM receipts
                        WHERE vendor_name ILIKE %s
                          AND COALESCE(is_voided, false) = false
                    """,
                        (self.current_vendor,),
                    )
                receipts_total = float(cur.fetchone()[0])

                receipt_totals = {}
                linked_receipts_total = 0.0
                if invoices:
                    invoice_ids = [inv[0] for inv in invoices]
                    cur.execute(
                        """
                        SELECT vendor_invoice_id,
                               COALESCE(SUM(gross_amount), 0)
                        FROM receipts
                        WHERE vendor_invoice_id = ANY(%s)
                            AND COALESCE(is_voided, false) = false
                        GROUP BY vendor_invoice_id
                        """,
                        (invoice_ids,),
                    )
                    for linked_invoice_id, receipt_total in cur.fetchall():
                        receipt_total = float(receipt_total or 0)
                        receipt_totals[int(linked_invoice_id)] = receipt_total
                        linked_receipts_total += receipt_total

                # 3. Payment totals are invoice-specific (not shared).
                payment_totals = {}
                total_entered_payments = 0.0
                if invoices:
                    invoice_ids = [inv[0] for inv in invoices]
                    cur.execute(
                        """
                        SELECT receipt_id,
                               COALESCE(SUM(ABS(payment_amount)), 0)
                        FROM vendor_invoice_payments
                        WHERE receipt_id = ANY(%s)
                        GROUP BY receipt_id
                    """,
                        (invoice_ids,),
                    )
                    for receipt_id, paid_total in cur.fetchall():
                        paid_total = abs(float(paid_total or 0))
                        payment_totals[int(receipt_id)] = paid_total
                        total_entered_payments += paid_total

            invoice_data = []
            total_invoiced = 0.0
            total_paid = 0.0

            for inv in invoices:
                invoice_id, ref, details, date, amount = inv
                amount = float(amount)

                paid_total = abs(
                    float(payment_totals.get(int(invoice_id), 0.0))
                )
                balance = amount - paid_total
                status = "✅ Paid" if balance <= 0.01 else "❌ Unpaid"

                invoice_data.append(
                    (
                        invoice_id,
                        ref,
                        details,
                        date,
                        amount,
                        paid_total,
                        balance,
                        status,
                    )
                )
                total_invoiced += amount
                total_paid += paid_total

            total_balance = total_invoiced - total_paid

            invoice_data.sort(key=self._invoice_sort_key)
            self.current_invoices = invoice_data
            self.unfiltered_invoices = invoice_data.copy()
            self.current_receipts_total = receipts_total
            self.current_entered_payments_total = total_paid
            self.current_invoice_receipt_totals = receipt_totals
            self.current_linked_receipts_total = linked_receipts_total

            # Re-apply active filters if any are active.
            has_active_filters = (
                bool(self.filter_invoice_num.text().strip())
                or self.filter_year.currentData() is not None
                or self.filter_status.currentText() != "All"
            )
            if has_active_filters:
                self._apply_invoice_filters()

            # 5. Update header (payments drive A/P; receipts shown separately).
            self.vendor_header.setText(
                f"📋 Invoices for: {self.current_vendor}"
            )
            self.balance_label.setText(
                f"Payments Entered: ${total_paid:,.2f} | "
                f"Receipts on File: ${receipts_total:,.2f} | "
                f"Linked Receipts: ${linked_receipts_total:,.2f} | "
                f"Total Invoiced: ${total_invoiced:,.2f} | "
                f"Balance Due: ${total_balance:,.2f}"
                + (
                    " | BANKING_IMPORT hidden"
                    if self._hide_auto_import_invoices()
                    else ""
                )
                + (
                    " | pseudo-vendors hidden"
                    if self._hide_pseudo_vendor_invoices()
                    else ""
                )
            )

            if total_balance > 0.01:
                self.balance_label.setStyleSheet(
                    "font-size: 12px; padding: 5px;"
                    " color: red; font-weight: bold;"
                )
            elif total_balance < -0.01:
                # Overpaid — entered payments exceed invoiced amount.
                self.balance_label.setStyleSheet(
                    "font-size: 12px; padding: 5px;"
                    " color: darkorange; font-weight: bold;"
                )
            else:
                self.balance_label.setStyleSheet(
                    "font-size: 12px; padding: 5px;"
                    " color: green; font-weight: bold;"
                )

            self._refresh_invoice_table()
            self._refresh_vendor_ledger()

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Load Error", f"Error loading invoices: {e}"
            )

    def _refresh_invoice_table(self) -> None:
        """Refresh the invoice table display with running balance"""
        was_sorting = self.invoice_table.isSortingEnabled()
        self.invoice_table.setSortingEnabled(False)
        self.invoice_table.setRowCount(len(self.current_invoices))

        running_balance = 0.0
        receipt_totals = getattr(self, "current_invoice_receipt_totals", {})

        for idx, invoice in enumerate(self.current_invoices):
            receipt_id, ref, details, date, amount, paid, balance, status = (
                invoice
            )

            # Convert to float to avoid type mismatch
            balance = float(balance) if balance is not None else 0.0
            amount = float(amount) if amount is not None else 0.0
            paid = float(paid) if paid is not None else 0.0

            # Update running balance (cumulative)
            running_balance += balance

            # Check if this row is selected
            is_selected = (
                self.invoice_table.item(idx, 0)
                and self.invoice_table.item(idx, 0).isSelected()
            )
            row_color = (
                QColor("#e3f2fd") if is_selected else QColor("white")
            )  # Light blue for selected

            # ID (read-only)
            id_item = SortableTableWidgetItem(str(receipt_id))
            id_item.setData(Qt.ItemDataRole.UserRole, int(receipt_id))
            id_item.setBackground(QBrush(row_color))
            id_item.setFlags(
                id_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )  # Make read-only
            self.invoice_table.setItem(idx, 0, id_item)

            # Invoice # (editable)
            inv_item = SortableTableWidgetItem(str(ref or f"R-{receipt_id}"))
            inv_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 1, inv_item)

            # Description / details (read-only)
            details_item = SortableTableWidgetItem(str(details or ""))
            details_item.setBackground(QBrush(row_color))
            details_item.setFlags(
                details_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.invoice_table.setItem(idx, 2, details_item)

            # Date (editable) - standardize format to MM/dd/yyyy
            if isinstance(date, str):
                try:
                    parsed_date = datetime.strptime(date, "%Y-%m-%d").strftime(
                        "%m/%d/%Y"
                    )
                except Exception:
                    parsed_date = date
            else:
                parsed_date = (
                    date.strftime("%m/%d/%Y")
                    if hasattr(date, "strftime")
                    else str(date)
                )
            if hasattr(date, "toordinal"):
                date_sort_key = date.toordinal()
            elif isinstance(date, str):
                date_sort_key = 0
                for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                    try:
                        date_sort_key = (
                            datetime.strptime(date, fmt).date().toordinal()
                        )
                        break
                    except Exception:
                        continue
            else:
                date_sort_key = 0
            date_item = SortableTableWidgetItem(parsed_date)
            date_item.setData(Qt.ItemDataRole.UserRole, date_sort_key)
            date_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 3, date_item)

            # Amount (read-only)
            amt_item = SortableTableWidgetItem(f"${amount:,.2f}")
            amt_item.setData(Qt.ItemDataRole.UserRole, amount)
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            amt_item.setBackground(QBrush(row_color))
            amt_item.setFlags(amt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.invoice_table.setItem(idx, 4, amt_item)

            # Receipts linked as evidence (read-only; does not affect balance)
            receipt_total = float(receipt_totals.get(int(receipt_id), 0.0))
            receipt_item = SortableTableWidgetItem(f"${receipt_total:,.2f}")
            receipt_item.setData(Qt.ItemDataRole.UserRole, receipt_total)
            receipt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            receipt_item.setBackground(QBrush(row_color))
            receipt_item.setFlags(
                receipt_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            if receipt_total > 0:
                receipt_item.setForeground(QBrush(QColor("darkgreen")))
            self.invoice_table.setItem(idx, 5, receipt_item)

            # Paid (read-only)
            paid_item = SortableTableWidgetItem(f"${paid:,.2f}")
            paid_item.setData(Qt.ItemDataRole.UserRole, paid)
            paid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            paid_item.setBackground(QBrush(row_color))
            paid_item.setFlags(paid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.invoice_table.setItem(idx, 6, paid_item)

            # Running Balance (read-only - cumulative)
            running_bal_item = SortableTableWidgetItem(
                f"${running_balance:,.2f}"
            )
            running_bal_item.setData(Qt.ItemDataRole.UserRole, running_balance)
            running_bal_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            running_bal_item.setForeground(QBrush(QColor("darkblue")))
            running_bal_item.setFont(self._get_bold_font())
            running_bal_item.setBackground(QBrush(row_color))
            running_bal_item.setFlags(
                running_bal_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.invoice_table.setItem(idx, 7, running_bal_item)

            # Balance (read-only - individual invoice balance)
            bal_item = SortableTableWidgetItem(f"${balance:,.2f}")
            bal_item.setData(Qt.ItemDataRole.UserRole, balance)
            bal_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            bal_item.setBackground(QBrush(row_color))
            bal_item.setFlags(bal_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if balance > 0:
                bal_item.setForeground(QBrush(QColor("red")))
            self.invoice_table.setItem(idx, 8, bal_item)

            # Status (read-only)
            status_item = SortableTableWidgetItem(status)
            status_item.setData(
                Qt.ItemDataRole.UserRole, 0 if "Paid" in status else 1
            )
            status_item.setBackground(QBrush(row_color))
            status_item.setFlags(
                status_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.invoice_table.setItem(idx, 9, status_item)

        self.invoice_table.setSortingEnabled(was_sorting)

    def _get_bold_font(self) -> QFont:
        """Get bold font for running balance"""
        font = QFont()
        font.setBold(True)
        return font

    def _add_invoice(self) -> None:
        """Add a new invoice for current vendor (with optional fee split)"""
        if not self.current_vendor:
            QMessageBox.warning(
                self, "No Vendor", "Please select a vendor first."
            )
            return

        invoice_num = self.new_invoice_num.text().strip()
        amount = self.new_invoice_amount.get_value()

        if amount < 0:
            QMessageBox.warning(
                self,
                "Invalid Amount",
                "Amount must be greater than or equal to 0.",
            )
            return

        # Check if using split
        use_split = self.new_invoice_use_split.isChecked()
        base_amount = amount
        fee_amount = 0.0
        fee_type = None

        if use_split:
            base_amount = self.new_invoice_base_amount.get_value()
            fee_amount = self.new_invoice_fee_amount.get_value()
            fee_type = self.new_invoice_fee_type.currentText()

            if base_amount + fee_amount != amount:
                QMessageBox.warning(
                    self,
                    "Split Mismatch",
                    f"Base ({base_amount:.2f}) + Fee ({fee_amount:.2f})"
                    f" must equal Total ({amount:.2f})",
                )
                return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                notes = self.new_invoice_desc.toPlainText().strip() or None
                if use_split and fee_amount > 0:
                    split_note = (
                        f"Base: ${base_amount:.2f}"
                        f" + {fee_type}: ${fee_amount:.2f}"
                    )
                    notes = f"{notes} | {split_note}" if notes else split_note

                cur.execute(
                    """
                    INSERT INTO vendor_invoices
                        (vendor_name, invoice_number,
                         invoice_date, invoice_amount, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING vendor_invoice_id
                """,
                    (
                        self.current_vendor,
                        invoice_num or None,
                        self.new_invoice_date.date().toPyDate(),
                        amount,
                        notes,
                    ),
                )
                receipt_id = cur.fetchone()[0]

                # If split, create fee entry in vendor ledger (if table exists)
                if use_split and fee_amount > 0:
                    try:
                        # Fee tracking (vendor_account_ledger, future use)
                        pass
                    except Exception as e:
                        logger.error(f"Failed: {e}")
                        pass

            msg = (
                f"✅ Invoice added!\n\nInvoice ID: {receipt_id}\n"
                f"Amount: ${amount:,.2f}"
            )
            if use_split and fee_amount > 0:
                msg += (
                    f"\n\nBreakdown:\n  Base: ${base_amount:,.2f}\n"
                    f"  {fee_type}: ${fee_amount:,.2f}\n\n"
                    "⚠️ Fee tracked separately for CRA reporting"
                )

            QMessageBox.information(self, "Success", msg)

            # Clear form
            self.new_invoice_num.clear()
            self.new_invoice_amount.setText("0.00")
            self.new_invoice_base_amount.setText("0.00")
            self.new_invoice_fee_amount.setText("0.00")
            self.new_invoice_desc.clear()
            self.new_invoice_use_split.setChecked(False)
            self.split_details.setVisible(False)

            # Refresh
            self._load_vendor_invoices()

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Add Error", f"Failed to add invoice:\n\n{e}"
            )

    def _apply_to_single_invoice(self) -> None:
        """Apply payment to a single selected invoice"""
        selected = self.invoice_table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self, "No Selection", "Please select an invoice from the list."
            )
            return

        row = self.invoice_table.currentRow()
        if row < 0:
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, _details, date, amount, paid, balance, status = (
            invoice
        )

        payment_amt = self.payment_amount.get_value()
        if payment_amt <= 0:
            QMessageBox.warning(
                self,
                "Invalid Payment",
                "Payment amount must be greater than 0.",
            )
            return

        payment_date = self.payment_date.date().toPyDate()
        payment_method = self.payment_method.currentText()
        payment_ref_raw = self.payment_reference.text().strip()
        receipt_tx = self.payment_receipt_tx.text().strip()

        banking_id = None
        banking_text = self.payment_banking_id.text().strip()
        if banking_text:
            try:
                banking_id = int(banking_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Banking ID",
                    "Banking TX ID must be a number.",
                )
                return

        if not self._validate_receipt_matches_before_payment(
            {receipt_id: payment_amt},
            payment_date,
            banking_id,
            receipt_tx,
            payment_method,
            payment_ref_raw,
            bool(
                getattr(self, "auto_create_cash_receipt_chk", None)
                and self.auto_create_cash_receipt_chk.isChecked()
            ),
        ):
            return

        if not self._confirm_duplicate_payment_continue(
            {receipt_id: payment_amt},
            payment_date,
            payment_method,
            payment_ref_raw,
            receipt_tx,
        ):
            return

        # Confirm
        confirm = QMessageBox.question(
            self,
            "Confirm Payment",
            f"Apply ${payment_amt:,.2f} payment to:\n\n"
            f"Invoice: {ref or f'R-{receipt_id}'}\n"
            f"Date: {date}\n"
            f"Balance: ${balance:,.2f}\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                # Get payment reference and date
                payment_ref = (
                    payment_ref_raw
                    or f"Payment for invoice {ref or receipt_id}"
                )

                # Create vendor_invoice_payments table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vendor_invoice_payments (
                        payment_id SERIAL PRIMARY KEY,
                        receipt_id INTEGER NOT NULL,
                        payment_date DATE NOT NULL,
                        payment_amount DECIMAL(10,2) NOT NULL,
                        payment_method VARCHAR(50),
                        reference VARCHAR(255),
                        banking_transaction_id INTEGER,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                self._lock_and_validate_payment_allocations(
                    cur, {receipt_id: payment_amt}
                )

                # Record the payment
                cur.execute(
                    """
                    INSERT INTO vendor_invoice_payments
                    (receipt_id, payment_date, payment_amount,
                     payment_method, reference,
                     banking_transaction_id, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        receipt_id,
                        payment_date,
                        payment_amt,
                        payment_method,
                        payment_ref,
                        banking_id,
                        self._compose_payment_note(
                            f"Payment to {self.current_vendor}", receipt_tx
                        ),
                    ),
                )

                # (banking_transaction_id not stored on vendor_invoices)

            QMessageBox.information(
                self,
                "Success",
                f"✅ Payment of ${payment_amt:,.2f}"
                f" recorded successfully!\n\n"
                f"Invoice: {ref or receipt_id}\n"
                f"Reference: {payment_ref}",
            )

            # Clear form
            self.payment_amount.setText("0.00")
            self.payment_reference.clear()
            self.payment_receipt_tx.clear()
            self.payment_banking_id.clear()

            # Refresh
            self._load_vendor_invoices()
            self._refresh_payment_history()

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Payment Error", f"Failed to apply payment:\n\n{e}"
            )

    def _apply_to_multiple_invoices(self) -> None:
        """Apply payment across multiple invoices"""
        if not self.current_vendor:
            QMessageBox.warning(
                self, "No Vendor", "Please select a vendor first."
            )
            return

        payment_amt = self.payment_amount.get_value()
        if payment_amt <= 0:
            QMessageBox.warning(
                self,
                "Invalid Payment",
                "Payment amount must be greater than 0.",
            )
            return

        # Get payment method
        payment_method = self.payment_method.currentText()

        # Get invoices with outstanding balances
        # inv[6] = balance
        unpaid_invoices = [inv for inv in self.current_invoices if inv[6] > 0]

        if not unpaid_invoices:
            QMessageBox.information(
                self,
                "No Outstanding Invoices",
                "All invoices are paid in full.",
            )
            return

        # Show allocation dialog
        dialog = MultiInvoicePaymentDialog(
            self.conn,
            self.current_vendor,
            payment_amt,
            unpaid_invoices,
            self,
            payment_method,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            allocations = dialog.get_allocations()

            if not allocations:
                QMessageBox.warning(
                    self,
                    "No Allocation",
                    "No invoices were selected for payment.",
                )
                return

            # Apply allocations
            try:
                payment_ref_raw = self.payment_reference.text().strip()
                payment_date = self.payment_date.date().toPyDate()
                payment_method = self.payment_method.currentText()
                receipt_tx = self.payment_receipt_tx.text().strip()

                banking_id = None
                banking_text = self.payment_banking_id.text().strip()
                if banking_text:
                    try:
                        banking_id = int(banking_text)
                    except ValueError:
                        QMessageBox.warning(
                            self,
                            "Invalid Banking ID",
                            "Banking TX ID must be a number.",
                        )
                        return

                if not self._validate_receipt_matches_before_payment(
                    allocations,
                    payment_date,
                    banking_id,
                    receipt_tx,
                    payment_method,
                    payment_ref_raw,
                    bool(
                        getattr(self, "auto_create_cash_receipt_chk", None)
                        and self.auto_create_cash_receipt_chk.isChecked()
                    ),
                ):
                    return

                if not self._confirm_duplicate_payment_continue(
                    allocations,
                    payment_date,
                    payment_method,
                    payment_ref_raw,
                    receipt_tx,
                ):
                    return

                with DatabaseContext(self.conn, auto_commit=True) as cur:
                    # Get payment reference and date
                    payment_ref = (
                        payment_ref_raw
                        or f"Multi-invoice payment to {self.current_vendor}"
                    )

                    # Create vendor_invoice_payments table if it doesn't exist
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS vendor_invoice_payments (
                            payment_id SERIAL PRIMARY KEY,
                            receipt_id INTEGER NOT NULL,
                            payment_date DATE NOT NULL,
                            payment_amount DECIMAL(10,2) NOT NULL,
                            payment_method VARCHAR(50),
                            reference VARCHAR(255),
                            banking_transaction_id INTEGER,
                            notes TEXT,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)

                    self._lock_and_validate_payment_allocations(cur, allocations)

                    # Record payments for each allocated invoice
                    for receipt_id, allocated_amt in allocations.items():
                        cur.execute(
                            """
                            INSERT INTO vendor_invoice_payments
                            (receipt_id, payment_date, payment_amount,
                             payment_method, reference,
                             banking_transaction_id, notes)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                            (
                                receipt_id,
                                payment_date,
                                allocated_amt,
                                payment_method,
                                payment_ref,
                                banking_id,
                                self._compose_payment_note(
                                    f"Split payment to {self.current_vendor}",
                                    receipt_tx,
                                ),
                            ),
                        )

                alloc_summary = "\n".join(
                    [
                        f"Invoice {rid}: ${amt:,.2f}"
                        for rid, amt in allocations.items()
                    ]
                )

                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ Payment allocated successfully!\n\n{alloc_summary}",
                )

                # Clear form
                self.payment_amount.setText("0.00")
                self.payment_reference.clear()
                self.payment_receipt_tx.clear()
                self.payment_banking_id.clear()

                # Refresh
                self._load_vendor_invoices()
                self._refresh_payment_history()

            except Exception as e:
                logger.error(f"Failed: {e}")
                QMessageBox.critical(
                    self,
                    "Allocation Error",
                    f"Failed to allocate payment:\n\n{e}",
                )

    @pyqtSlot()
    def _search_banking(self) -> None:
        """Search banking transactions"""
        amount = self.banking_search_amount.get_value()
        desc = self.banking_search_desc.text().strip()

        if amount < 0 and not desc:
            QMessageBox.warning(
                self,
                "No Search Criteria",
                "Enter amount or description to search.",
            )
            return

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                sql = """
                    SELECT
                        transaction_id,
                        transaction_date,
                        description,
                        debit_amount,
                        check_number,
                        (SELECT COUNT(*) FROM vendor_invoice_payments vip
                         WHERE vip.banking_transaction_id
                           = bt.transaction_id) as linked_count
                    FROM banking_transactions bt
                    WHERE debit_amount > 0
                """
                params = []

                if amount > 0:
                    sql += " AND ABS(debit_amount - %s) < 1.00"
                    params.append(amount)

                if desc:
                    sql += " AND description ILIKE %s"
                    params.append(f"%{desc}%")

                # Add date filter if enabled
                if self.banking_use_date_filter.isChecked():
                    date_from = self.banking_date_from.date().toPyDate()
                    date_to = self.banking_date_to.date().toPyDate()
                    sql += " AND transaction_date BETWEEN %s AND %s"
                    params.append(date_from)
                    params.append(date_to)

                sql += " ORDER BY transaction_date DESC LIMIT 100"

                cur.execute(sql, params)
                results = cur.fetchall()

            # Display results
            self.banking_table.setRowCount(len(results))
            for idx, row in enumerate(results):
                tx_id, date, description, amt, check, linked = row

                self.banking_table.setItem(
                    idx, 0, QTableWidgetItem(str(tx_id))
                )
                # Standardize date format to MM/dd/yyyy
                if isinstance(date, str):
                    try:
                        formatted_date = datetime.strptime(
                            date, "%Y-%m-%d"
                        ).strftime("%m/%d/%Y")
                    except Exception:
                        formatted_date = date
                else:
                    formatted_date = (
                        date.strftime("%m/%d/%Y")
                        if hasattr(date, "strftime")
                        else str(date)
                    )
                self.banking_table.setItem(
                    idx, 1, QTableWidgetItem(formatted_date)
                )
                self.banking_table.setItem(
                    idx, 2, QTableWidgetItem(description[:50])
                )

                amt_item = QTableWidgetItem(f"${amt:,.2f}")
                amt_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.banking_table.setItem(idx, 3, amt_item)

                self.banking_table.setItem(
                    idx, 4, QTableWidgetItem(str(check or ""))
                )

                linked_item = QTableWidgetItem(
                    "✅ Yes" if linked > 0 else "❌ No"
                )
                self.banking_table.setItem(idx, 5, linked_item)

            # Show info message about results
            if len(results) == 0:
                QMessageBox.information(
                    self,
                    "No Results",
                    "No banking transactions found matching your criteria.\n\n"
                    "💡 Tip: If searching by amount only,"
                    " uncheck 'Filter by date range' "
                    "or use 'All Time' to search all years.",
                )
            else:
                date_info = ""
                if self.banking_use_date_filter.isChecked():
                    fmt = "MM/dd/yyyy"
                    d_from = self.banking_date_from.date().toString(fmt)
                    d_to = self.banking_date_to.date().toString(fmt)
                    date_info = f"\n📅 Filtered: {d_from} to {d_to}"

                QMessageBox.information(
                    self,
                    "Search Results",
                    f"Found {len(results)} transactions{date_info}",
                )

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Search Error", f"Error searching banking:\n\n{e}"
            )

    def _link_banking_to_invoice(self, item) -> None:
        """Link a banking transaction to selected invoice(s)."""
        row = self.banking_table.currentRow()
        if row < 0:
            return

        # Get banking transaction details
        tx_id = int(self.banking_table.item(row, 0).text())
        tx_amount_text = (
            self.banking_table.item(row, 3)
            .text()
            .replace("$", "")
            .replace(",", "")
        )
        tx_amount = float(tx_amount_text)
        tx_date_text = self.banking_table.item(row, 1).text()

        # Get selected invoices
        selected_rows = set(
            item.row() for item in self.invoice_table.selectedItems()
        )
        if not selected_rows:
            QMessageBox.warning(
                self,
                "No Invoices Selected",
                "Please select one or more invoices from "
                "the table first,\nthen double-click the "
                "banking transaction.",
            )
            return

        selected_invoices = [
            self.current_invoices[row]
            for row in selected_rows
            if row < len(self.current_invoices)
        ]

        if not selected_invoices:
            QMessageBox.warning(
                self, "No Invoices", "No valid invoices selected."
            )
            return

        # Calculate total needed
        total_to_pay = sum(
            inv[6] for inv in selected_invoices
        )  # inv[6] is balance

        # Confirm allocation
        invoice_list = "\n".join(
            f"  \u2022 Invoice {inv[1]}: ${inv[6]:,.2f}"
            for inv in selected_invoices
        )

        confirm = QMessageBox.question(
            self,
            "Confirm Payment Allocation",
            f"Apply banking transaction #{tx_id} (${tx_amount:,.2f})\n"
            f"to {len(selected_invoices)} invoice(s):\n\n{invoice_list}\n\n"
            f"Total to allocate: ${min(total_to_pay, tx_amount):,.2f}\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Apply payments directly to invoices
        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                # Create vendor_invoice_payments table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vendor_invoice_payments (
                        payment_id SERIAL PRIMARY KEY,
                        receipt_id INTEGER NOT NULL,
                        payment_date DATE NOT NULL,
                        payment_amount DECIMAL(10,2) NOT NULL,
                        payment_method VARCHAR(50),
                        banking_transaction_id INTEGER,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                remaining = tx_amount
                applied_count = 0

                payment_date = datetime.strptime(
                    tx_date_text, "%m/%d/%Y"
                ).date()

                for inv in selected_invoices:
                    if remaining <= 0.01:
                        break

                    receipt_id = inv[0]
                    invoice_balance = inv[6]

                    # Apply up to the balance or remaining amount
                    apply_amount = min(invoice_balance, remaining)

                    if apply_amount > 0.01:
                        # Insert payment record
                        cur.execute(
                            """
                            INSERT INTO vendor_invoice_payments (
                                receipt_id, payment_date, payment_amount,
                                payment_method, banking_transaction_id, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                            (
                                receipt_id,
                                payment_date,
                                apply_amount,
                                "Banking Link",
                                tx_id,
                                f"Auto-allocated from banking"
                                f" transaction #{tx_id}",
                            ),
                        )

                        # (banking_transaction_id not on vendor_invoices)

                        remaining -= apply_amount
                        applied_count += 1

            QMessageBox.information(
                self,
                "✅ Payment Applied",
                f"Successfully linked banking transaction #{tx_id}\n"
                f"to {applied_count} invoice(s).\n\n"
                f"Total applied: ${tx_amount - remaining:,.2f}\n"
                f"Remaining: ${remaining:,.2f}",
            )

            # Refresh the display
            self._load_vendor_invoices()
            self._refresh_payment_history()
            self._search_banking()  # Refresh banking table to show it's linked

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Payment Error", f"Failed to apply payment:\n\n{e}"
            )

    @pyqtSlot()
    def _refresh_current_vendor(self) -> None:
        """Refresh current vendor's invoices"""
        if not self.current_vendor:
            # Pull vendor from combo if not yet set
            current_text = self.vendor_lookup.vendor_combo.currentText()
            if current_text:
                vendor_name = (
                    current_text.split(" (")[0]
                    if " (" in current_text
                    else current_text
                )
                if vendor_name:
                    self._on_vendor_selected(vendor_name)
            return
        self._load_vendor_invoices()
        self._refresh_account_summary()

    @pyqtSlot()
    def _refresh_account_summary(self) -> None:
        """Generate and display account summary"""
        if not self.current_vendor:
            self.summary_text.setPlainText(
                "Select a vendor to view account summary."
            )
            return

        if not hasattr(self, "current_invoices") or not self.current_invoices:
            self.summary_text.setPlainText(
                f"No invoices found for {self.current_vendor}.\n\n"
                "This vendor may not have any invoices yet."
            )
            return

        summary = f"ACCOUNT SUMMARY: {self.current_vendor}\n"
        summary += "=" * 60 + "\n\n"

        total_invoiced = sum(float(inv[4]) for inv in self.current_invoices)
        total_paid = sum(float(inv[5]) for inv in self.current_invoices)
        total_balance = sum(float(inv[6]) for inv in self.current_invoices)
        receipts_total = float(getattr(self, "current_receipts_total", 0.0))
        linked_receipts_total = float(
            getattr(self, "current_linked_receipts_total", 0.0)
        )

        summary += f"Total Invoiced:    ${total_invoiced:>12,.2f}\n"
        summary += f"Payments Entered:  ${total_paid:>12,.2f}\n"
        summary += f"Receipts on File:  ${receipts_total:>12,.2f}\n"
        summary += f"Linked Receipts:   ${linked_receipts_total:>12,.2f}\n"
        summary += f"Balance Due:       ${total_balance:>12,.2f}\n"
        summary += "\n" + "=" * 60 + "\n\n"

        summary += f"INVOICE DETAILS ({len(self.current_invoices)} total):\n"
        summary += "-" * 60 + "\n"

        for inv in self.current_invoices:
            receipt_id, ref, details, date, amount, paid, balance, status = inv
            summary += (
                f"\nInvoice: {ref or f'R-{receipt_id}':<15}" f" Date: {date}\n"
            )
            if details:
                summary += f"  Details: {details}\n"
            summary += f"  Amount:  ${float(amount):>10,.2f}\n"
            summary += f"  Paid:    ${float(paid):>10,.2f}\n"
            summary += f"  Balance: ${float(balance):>10,.2f}  {status}\n"

        self.summary_text.setPlainText(summary)

    def _show_invoice_context_menu(self, pos) -> None:
        """Show right-click context menu on invoice"""
        menu = QMenu(self)

        edit_action = QAction("✏️ Edit Invoice", self)
        edit_action.triggered.connect(self._edit_selected_invoice)
        menu.addAction(edit_action)

        delete_action = QAction("🗑️ Delete Invoice", self)
        delete_action.triggered.connect(self._delete_selected_invoice)
        menu.addAction(delete_action)

        menu.addSeparator()

        view_action = QAction("👁️ View Full Details", self)
        view_action.triggered.connect(self._view_invoice_details)
        menu.addAction(view_action)

        menu.exec(self.invoice_table.viewport().mapToGlobal(pos))

    def _on_invoice_double_clicked(self, item) -> None:
        """Handle invoice double-click - load into edit form"""
        # Only allow editing Invoice # and Date columns
        if item.column() in [1, 3]:  # Invoice # or Date
            return  # Let inline editing happen
        else:
            # Other columns - load full edit form
            self._edit_selected_invoice()

    @pyqtSlot()
    def _edit_selected_invoice(self) -> None:
        """Edit selected invoice - load into edit form"""
        row = self.invoice_table.currentRow()
        if row < 0 or row >= len(self.current_invoices):
            QMessageBox.warning(
                self, "No Selection", "Please select an invoice to edit."
            )
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, _details, date, amount, paid, balance, status = (
            invoice
        )

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT vendor_invoice_id, invoice_number,
                        invoice_date, invoice_amount, notes
                    FROM vendor_invoices
                    WHERE vendor_invoice_id = %s
                """,
                    (receipt_id,),
                )

                data = cur.fetchone()

            if data:
                self.editing_receipt_id = data[0]
                self.edit_invoice_num.setText(data[1] or "")

                # Parse date
                invoice_date = data[2]
                if isinstance(invoice_date, str):
                    try:
                        from datetime import datetime

                        invoice_date = datetime.strptime(
                            invoice_date, "%Y-%m-%d"
                        ).date()
                    except Exception:
                        pass

                if hasattr(invoice_date, "year"):
                    self.edit_invoice_date.setDate(
                        QDate(
                            invoice_date.year,
                            invoice_date.month,
                            invoice_date.day,
                        )
                    )

                self.edit_invoice_amount.setText(f"{data[3]:.2f}")
                self.edit_invoice_desc.setPlainText(data[4] or "")

                # Switch to edit tab (index 1)
                self.details_tabs.setCurrentIndex(1)

                # Update status label
                self.edit_status_label.setText(
                    f"✅ Editing: Invoice {ref or receipt_id}"
                    f" (ID: {receipt_id})"
                    " - Make changes and click Save"
                )
                self.edit_status_label.setStyleSheet(
                    "font-size: 11px; color: #28a745;"
                    " font-weight: bold; margin-top: 5px;"
                )

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load invoice:\n\n{e}"
            )

    @pyqtSlot()
    def _delete_selected_invoice(self) -> None:
        """Delete selected invoice with safety checks"""
        row = self.invoice_table.currentRow()
        if row < 0 or row >= len(self.current_invoices):
            QMessageBox.warning(
                self, "No Selection", "Please select an invoice to delete."
            )
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, _details, date, amount, paid, balance, status = (
            invoice
        )

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                # Check invoice exists
                cur.execute(
                    """
                    SELECT vendor_invoice_id FROM vendor_invoices
                    WHERE vendor_invoice_id = %s
                """,
                    (receipt_id,),
                )
                if not cur.fetchone():
                    QMessageBox.warning(
                        self, "Not Found", "Invoice not found in database."
                    )
                    return

                # Check for payments
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(payment_amount),0)
                    FROM vendor_invoice_payments WHERE receipt_id = %s
                """,
                    (receipt_id,),
                )
                pay_count, pay_total = cur.fetchone()

                warning_msg = f"Delete invoice {ref or f'VI-{receipt_id}'}?\n"
                warning_msg += f"Date: {date}  Amount: ${amount:.2f}\n\n"
                if pay_count > 0:
                    warning_msg += (
                        f"⚠️ Has {pay_count} payment record(s)"
                        f" totalling ${float(pay_total):.2f}\n"
                    )
                    warning_msg += "   Payment records will be deleted\n\n"
                warning_msg += "This CANNOT be undone!\n\nContinue?"

                confirm = QMessageBox.question(
                    self,
                    "⚠️ Confirm Delete",
                    warning_msg,
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if confirm != QMessageBox.StandardButton.Yes:
                    return

                # Delete payment records first
                cur.execute(
                    "DELETE FROM vendor_invoice_payments"
                    " WHERE receipt_id = %s",
                    (receipt_id,),
                )

                # Delete the invoice
                cur.execute(
                    "DELETE FROM vendor_invoices"
                    " WHERE vendor_invoice_id = %s",
                    (receipt_id,),
                )

            invoice_ref = ref or f"R-{receipt_id}"
            QMessageBox.information(
                self,
                "✅ Deleted",
                f"Invoice {invoice_ref} deleted successfully.",
            )
            self._load_vendor_invoices()

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Delete Error", f"Failed to delete:\n\n{e}"
            )

    @pyqtSlot()
    def _view_invoice_details(self) -> None:
        """View full invoice details"""
        row = self.invoice_table.currentRow()
        if row < 0:
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, _details, date, amount, paid, balance, status = (
            invoice
        )

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        vendor_invoice_id, vendor_name, invoice_number,
                        invoice_date,
                        invoice_amount, notes, status
                    FROM vendor_invoices
                    WHERE vendor_invoice_id = %s
                """,
                    (receipt_id,),
                )

                full_data = cur.fetchone()

            if full_data:
                details = f"INVOICE DETAILS\n{'=' * 50}\n\n"
                details += f"Invoice ID:         {full_data[0]}\n"
                details += f"Vendor:             {full_data[1]}\n"
                details += f"Invoice #:          {full_data[2] or 'N/A'}\n"
                details += f"Date:               {full_data[3]}\n"
                details += f"Amount:             ${full_data[4]:,.2f}\n"
                details += f"Notes:              {full_data[5] or 'N/A'}\n"
                details += f"Status:             {full_data[6] or 'N/A'}\n"

                QMessageBox.information(self, "Invoice Details", details)

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load details:\n\n{e}"
            )

    def _on_invoice_item_changed(self, item) -> None:
        """Track changes to invoice items for inline editing"""
        if not hasattr(self, "_editing_enabled"):
            self._editing_enabled = True

        # Only allow editing invoice # (column 1) and date (column 3)
        col = item.column()
        if col not in [1, 3]:
            return

        # Enable save button
        self.save_changes_btn.setEnabled(True)

        # Mark row as edited
        row = item.row()
        for c in range(self.invoice_table.columnCount()):
            cell_item = self.invoice_table.item(row, c)
            if cell_item:
                cell_item.setBackground(
                    QBrush(QColor("#fff3cd"))
                )  # Light yellow

    @pyqtSlot()
    def _save_direct_edits(self) -> None:
        """Save direct edits made in the invoice table"""
        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                changes_made = 0

                # Temporarily disable sorting to preserve row order
                self.invoice_table.setSortingEnabled(False)

                for row in range(self.invoice_table.rowCount()):
                    # Check if row has yellow background (edited)
                    item = self.invoice_table.item(row, 1)
                    colour = QColor("#fff3cd")
                    if not item or item.background().color() != colour:
                        continue

                    # Get receipt_id from first column
                    receipt_id = int(self.invoice_table.item(row, 0).text())

                    # Get new values
                    new_invoice_num = self.invoice_table.item(row, 1).text()
                    new_date_str = self.invoice_table.item(row, 3).text()

                    # Parse date (MM/dd/yyyy format)
                    try:
                        from datetime import datetime

                        new_date = datetime.strptime(
                            new_date_str, "%m/%d/%Y"
                        ).date()
                    except Exception:
                        QMessageBox.warning(
                            self,
                            "Invalid Date",
                            f"Row {row + 1}: Invalid date format."
                            " Use MM/DD/YYYY",
                        )
                        continue

                    # Update database
                    cur.execute(
                        """
                        UPDATE vendor_invoices
                        SET invoice_number = %s, invoice_date = %s
                        WHERE vendor_invoice_id = %s
                    """,
                        (new_invoice_num, new_date, receipt_id),
                    )

                    changes_made += 1

            if changes_made > 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ Saved {changes_made} invoice change(s)!",
                )
                self.save_changes_btn.setEnabled(False)
                self._load_vendor_invoices()  # Reload to show updated data
            else:
                QMessageBox.information(
                    self, "No Changes", "No changes detected to save."
                )

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save changes:\n\n{e}"
            )
        finally:
            self.invoice_table.setSortingEnabled(False)

    @pyqtSlot()
    def _save_invoice_changes(self) -> None:
        """Save changes from the edit form"""
        if not getattr(self, "editing_receipt_id", None):
            QMessageBox.warning(
                self, "No Invoice", "No invoice loaded for editing."
            )
            return

        try:
            # Get values from form
            invoice_num = self.edit_invoice_num.text().strip()
            invoice_date = self.edit_invoice_date.date().toPyDate()
            amount = self.edit_invoice_amount.get_value()
            description = self.edit_invoice_desc.toPlainText().strip()

            if amount < 0:
                QMessageBox.warning(
                    self,
                    "Invalid Amount",
                    "Amount must be greater than" " or equal to 0.",
                )
                return

            # Update database
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE vendor_invoices
                    SET invoice_number = %s,
                        invoice_date = %s,
                        invoice_amount = %s,
                        notes = %s
                    WHERE vendor_invoice_id = %s
                """,
                    (
                        invoice_num,
                        invoice_date,
                        amount,
                        description,
                        self.editing_receipt_id,
                    ),
                )

            QMessageBox.information(
                self, "Success", "✅ Invoice updated successfully!"
            )

            # Update status
            self.edit_status_label.setText(
                f"✅ Saved! Invoice"
                f" {invoice_num or self.editing_receipt_id} updated."
            )
            self.edit_status_label.setStyleSheet(
                "font-size: 11px; color: #28a745;"
                " font-weight: bold; margin-top: 5px;"
            )

            # Reload invoice list
            self._load_vendor_invoices()

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save invoice:\n\n{e}"
            )

    @pyqtSlot()
    def _delete_invoice(self) -> None:
        """Delete the currently loaded invoice from edit form"""
        if not getattr(self, "editing_receipt_id", None):
            QMessageBox.warning(
                self, "No Invoice", "No invoice loaded for deletion."
            )
            return

        # Delegate to the existing delete method which has safety checks
        # Find the row in the invoice table
        for row in range(self.invoice_table.rowCount()):
            item = self.invoice_table.item(row, 0)
            if item and int(item.text()) == self.editing_receipt_id:
                self.invoice_table.selectRow(row)
                self._delete_selected_invoice()
                self._clear_edit_fields()
                return

        QMessageBox.warning(
            self, "Not Found", "Invoice not found in current list."
        )

    @pyqtSlot()
    def _clear_edit_fields(self) -> None:
        """Clear all edit form fields"""
        self.editing_receipt_id = None
        self.edit_invoice_num.clear()
        self.edit_invoice_date.setDate(QDate.currentDate())
        self.edit_invoice_amount.setText("0.00")
        self.edit_invoice_desc.clear()
        self.edit_invoice_category.setCurrentIndex(0)
        self.edit_status_label.setText(
            "No invoice loaded. Select an invoice"
            " and click 'Edit Selected Invoice' button."
        )
        self.edit_status_label.setStyleSheet(
            "font-size: 11px; color: #004085;"
            " font-weight: bold; margin-top: 5px;"
        )

    @pyqtSlot()
    def _quick_pay_single(self) -> None:
        """Quick pay from left panel (payment tab, single invoice)."""
        # Switch to payment tab first
        self.details_tabs.setCurrentIndex(2)  # Apply Payment tab
        # Then call the actual payment function
        self._apply_to_single_invoice()

    @pyqtSlot()
    def _quick_pay_multiple(self) -> None:
        """Quick pay from left panel (payment tab, multiple invoices)."""
        # Switch to payment tab first
        self.details_tabs.setCurrentIndex(2)  # Apply Payment tab
        # Then call the actual payment function
        self._apply_to_multiple_invoices()

    @pyqtSlot()
    def _show_summary_tab(self) -> None:
        """Show ledger tab and refresh data."""
        self.details_tabs.setCurrentWidget(self.ledger_tab_widget)
        self._refresh_vendor_ledger()
        self._refresh_account_summary()
