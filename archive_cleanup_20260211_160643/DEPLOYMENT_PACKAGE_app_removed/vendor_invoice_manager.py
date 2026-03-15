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

from datetime import datetime
from decimal import Decimal

import psycopg2
from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,)

from common_widgets import StandardDateEdit


class CurrencyInput(QLineEdit):
    """Currency input field with validation (compact 6-digit max)"""
    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.compact = compact
        if compact:
            self.setMaxLength(10)  # "999999.99" = 9 chars
            self.setMaximumWidth(100)

    def focusInEvent(self, event):
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        self.selectAll()

    def mousePressEvent(self, event):
        """Select all on any mouse click - prevents cursor positioning"""
        # Don't call super first - we want selectAll to stick
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._format()

    def _format(self):
        text = self.text().replace(',', '').replace('$', '').strip()
        try:
            val = float(text)
            self.setText(f"{val:.2f}")
        except Exception:
            self.setText("0.00")

    def get_value(self):
        try:
            return float(self.text().replace(',', ''))
        except Exception:
            return 0.0


class SimpleCalculator(QDialog):
    """Simple calculator dialog with number pad"""
    def __init__(self, initial_value=0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
        self.display_value = str(initial_value)
        self.pending_operation = None
        self.pending_value = None
        self.init_ui()

    def init_ui(self):
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
            "padding: 10px; background-color: #f0f0f0; border: 2px solid #333;")
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
    lambda checked,
     t=btn_text: self._on_button_click(t))
            row1.addWidget(btn)
        grid.addLayout(row1)

        # Row 2: 4, 5, 6, ×
        row2 = QHBoxLayout()
        for btn_text in ["4", "5", "6", "×"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(
    lambda checked,
     t=btn_text: self._on_button_click(t))
            row2.addWidget(btn)
        grid.addLayout(row2)

        # Row 3: 1, 2, 3, −
        row3 = QHBoxLayout()
        for btn_text in ["1", "2", "3", "−"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(
    lambda checked,
     t=btn_text: self._on_button_click(t))
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
            "background-color: #28a745; color: white; font-weight: bold;")
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
            "background-color: #dc3545; color: white; font-weight: bold;")
        clear_btn.clicked.connect(self._clear)
        bottom_row.addWidget(clear_btn)

        ok_btn = QPushButton("✓ OK")
        ok_btn.setMinimumHeight(40)
        ok_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        bottom_row.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        layout.addLayout(bottom_row)

    def _on_button_click(self, text):
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

    def _calculate(self):
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

    def _on_equals(self):
        """Handle equals button"""
        self._calculate()

    def _clear(self):
        """Clear calculator"""
        self.display_value = "0"
        self.pending_operation = None
        self.pending_value = None
        self.display.setText("0")

    def get_value(self):
        """Return the calculated value"""
        try:
            return float(self.display_value)
        except Exception:
            return 0.0


class CalculatorButton(QPushButton):
    """Quick calculator for currency amounts"""
    def __init__(self, target_field, parent=None):
        super().__init__(parent)
        self.setText("🧮")
        self.setMaximumWidth(35)
        self.setToolTip("Open calculator")
        self.target_field = target_field
        self.clicked.connect(self._open_calculator)

    def _open_calculator(self):
        """Open calculator dialog"""
        try:
            current = self.target_field.get_value()
            calc = SimpleCalculator(initial_value=current, parent=self)
            result = calc.exec()
            if result == 1:  # Accepted in PyQt6
                value = calc.get_value()
                self.target_field.setText(f"{value:.2f}")
        except Exception as e:
            QMessageBox.critical(self, "Calculator Error", f"Error: {str(e)}")


class MultiInvoicePaymentDialog(QDialog):
    """Dialog for allocating a single payment across multiple invoices"""

    def __init__(
    self,
    conn,
    vendor_name,
    payment_amount,
    available_invoices,
    parent=None,
     payment_method='check'):
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

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f"💰 Allocate ${self.payment_amount:,.2f} Payment Across Invoices")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Vendor info
        vendor_label = QLabel(f"Vendor: {self.vendor_name}")
        vendor_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(vendor_label)

        # Invoice selection table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(7)
        self.invoice_table.setHorizontalHeaderLabels([
            "Select", "Invoice #", "Date", "Amount", "Paid", "Balance Due", "To Pay"])
        self.invoice_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
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
            "background-color: #007bff; color: white; padding: 8px;")
        layout.addWidget(auto_btn)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load invoices
        self._load_invoices()

    def _load_invoices(self):
        """Load available invoices with outstanding balances"""
        self.invoice_table.setRowCount(len(self.available_invoices))

        for idx, invoice in enumerate(self.available_invoices):
            # invoice = (receipt_id, ref, date, orig_amt, paid, balance, status)
            receipt_id, ref, date, amount, paid, balance, status = invoice

            # Checkbox
            check = QCheckBox()
            check.setChecked(False)
            check.stateChanged.connect(
    lambda state,
    row=idx: self._on_checkbox_changed(
        row,
         state))
            self.invoice_table.setCellWidget(idx, 0, check)

            # Invoice #
            self.invoice_table.setItem(
                idx, 1, QTableWidgetItem(str(ref or f"R-{receipt_id}")))

            # Date - standardize format to MM/dd/yyyy
            if isinstance(date, str):
                # Try to parse if it's a string
                try:
                                        parsed_date = datetime.strptime(
                                            date, "%Y-%m-%d").strftime("%m/%d/%Y")
                except Exception:
                    parsed_date = date
            else:
                # If it's a date object
                parsed_date = date.strftime(
                    "%m/%d/%Y") if hasattr(date, 'strftime') else str(date)
            self.invoice_table.setItem(idx, 2, QTableWidgetItem(parsed_date))

            # Amount
            amt_item = QTableWidgetItem(f"${amount:,.2f}")
            amt_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.invoice_table.setItem(idx, 3, amt_item)

            # Paid
            paid_item = QTableWidgetItem(f"${paid:,.2f}")
            paid_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.invoice_table.setItem(idx, 4, paid_item)

            # Balance
            bal_item = QTableWidgetItem(f"${balance:,.2f}")
            bal_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if balance > 0:
                bal_item.setForeground(QBrush(QColor("red")))
            self.invoice_table.setItem(idx, 5, bal_item)

            # To Pay (initially empty, filled during allocation)
            to_pay_item = QTableWidgetItem("$0.00")
            to_pay_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            to_pay_item.setFont(self._get_bold_font())
            self.invoice_table.setItem(idx, 6, to_pay_item)

    def _get_bold_font(self):
        """Get bold font"""
        font = QFont()
        font.setBold(True)
        return font

    def _on_checkbox_changed(self, row, state):
        """When checkbox changes, auto-allocate to that invoice"""
        invoice = self.available_invoices[row]
        receipt_id = invoice[0]
        balance = invoice[5]

        if state == Qt.CheckState.Checked.value:
            # Calculate how much we can allocate
            remaining = self._get_remaining()
            to_allocate = min(balance, remaining)
            self.allocations[receipt_id] = to_allocate

            # Update "To Pay" column
            to_pay_item = self.invoice_table.item(row, 6)
            to_pay_item.setText(f"${to_allocate:,.2f}")

            # Color code: green for full payment, yellow for partial
            row_color = QColor(
                "#c8e6c9") if to_allocate >= balance else QColor("#fff9c4")
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

    def _auto_allocate(self):
        """Auto-allocate payment to oldest invoices first (full payment priority)"""
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
        sorted_invoices = sorted(self.available_invoices, key=lambda x: x[2])

        for idx, invoice in enumerate(sorted_invoices):
            receipt_id, ref, date, amount, paid, balance, status = invoice

            if remaining <= 0:
                break

            if balance > 0:
                to_allocate = min(balance, remaining)
                self.allocations[receipt_id] = to_allocate
                remaining -= to_allocate

                # Check the checkbox
                orig_idx = self.available_invoices.index(invoice)

                # Update "To Pay" column
                to_pay_item = self.invoice_table.item(orig_idx, 6)
                if to_pay_item:
                    to_pay_item.setText(f"${to_allocate:,.2f}")

                # Color code the row: green for fully paid, yellow for partial
                row_color = QColor(
                    "#c8e6c9") if to_allocate >= balance else QColor("#fff9c4")
                for col in range(self.invoice_table.columnCount()):
                    item = self.invoice_table.item(orig_idx, col)
                    if item:
                        item.setBackground(QBrush(row_color))
                checkbox = self.invoice_table.cellWidget(orig_idx, 0)
                checkbox.setChecked(True)

        self._update_summary()

    def _get_remaining(self):
        """Get remaining unallocated amount"""
        allocated = sum(self.allocations.values())
        return self.payment_amount - allocated

    def _update_summary(self):
        """Update allocation summary"""
        allocated = sum(self.allocations.values())
        remaining = self.payment_amount - allocated

        self.allocated_label.setText(f"${allocated:,.2f}")
        self.allocated_label.setStyleSheet(
    "color: green; font-weight: bold;" if allocated > 0 else "")

        self.remaining_label.setText(f"${remaining:,.2f}")
        if abs(remaining) < 0.01:
            self.remaining_label.setStyleSheet(
                "color: green; font-weight: bold;")
        elif remaining > 0:
            self.remaining_label.setStyleSheet(
                "color: orange; font-weight: bold;")
        else:
            self.remaining_label.setStyleSheet(
                "color: red; font-weight: bold;")

    def get_allocations(self):
        """Return the allocation map"""
        return self.allocations


class VendorInvoiceManager(QWidget):
    """
    Main vendor invoice management interface
    """

    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.conn = db_connection
        self.current_vendor = None
        self.current_invoices = []
        self.editing_receipt_id = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header with instructions
        header = QLabel("📋 Vendor Invoice & Payment Manager")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        instructions = QLabel(
            "💡 Search for vendor → View all invoices → Add missing invoices → Apply payments")
        instructions.setStyleSheet(
            "color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-left: 3px solid #007bff;")
        layout.addWidget(instructions)

        # TOP ROW: Vendor search (left) + Invoice list with actions (right)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Vendor search and quick actions
        vendor_panel = QWidget()
        vendor_panel.setMaximumWidth(350)  # Prevent excessive width
        vendor_layout = QVBoxLayout(vendor_panel)
        vendor_layout.setContentsMargins(0, 0, 0, 0)
        vendor_layout.setSpacing(5)
        vendor_group = self._create_vendor_search()
        vendor_layout.addWidget(vendor_group)
        quick_actions = self._create_quick_actions()
        vendor_layout.addWidget(quick_actions)
        # No stretch - compact layout
        
        # Right: Invoice list
        invoice_panel = self._create_invoice_list()
        
        top_splitter.addWidget(vendor_panel)
        top_splitter.addWidget(invoice_panel)
        top_splitter.setStretchFactor(0, 0)  # Vendor panel fixed
        top_splitter.setStretchFactor(1, 1)  # Invoice list takes remaining space
        
        layout.addWidget(top_splitter, stretch=4)

        # 3. Expandable details section
        self.details_tabs = QTabWidget()
        self.details_tabs.setMaximumHeight(280)
        self.details_tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #ccc; } QTabBar::tab { padding: 8px 16px; font-size: 11px; font-weight: bold; }")
        self.details_tabs.addTab(self._create_add_invoice_tab(), "➕ Add Invoice")
        self.details_tabs.addTab(self._create_edit_invoice_tab(), "✏️ Edit Invoice")
        self.details_tabs.addTab(self._create_payment_tab(), "💰 Apply Payment")
        self.details_tabs.addTab(self._create_banking_link_tab(), "🏦 Banking Link")
        self.details_tabs.addTab(self._create_account_summary_tab(), "📊 Summary")

        layout.addWidget(self.details_tabs, stretch=1)

    def _create_quick_actions(self):
        """Quick action buttons for common tasks"""
        group = QGroupBox("⚡ Quick Actions")
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 11px;}")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # Add invoice button
        add_invoice_btn = QPushButton("➕ Add Invoice")
        add_invoice_btn.setStyleSheet(
            "background-color: #28a745; color: white; padding: 8px; font-weight: bold; font-size: 11px;")
        add_invoice_btn.setToolTip("Add a new invoice for the selected vendor")
        add_invoice_btn.clicked.connect(self._add_invoice)
        layout.addWidget(add_invoice_btn)

        # Edit selected invoice button
        edit_invoice_btn = QPushButton("✏️ Edit Invoice")
        edit_invoice_btn.setStyleSheet(
            "background-color: #fd7e14; color: white; padding: 8px; font-weight: bold; font-size: 11px;")
        edit_invoice_btn.setToolTip("Select one invoice and edit its details")
        edit_invoice_btn.clicked.connect(self._edit_selected_invoice)
        layout.addWidget(edit_invoice_btn)

        # Pay single button
        pay_single_btn = QPushButton("💵 Pay One")
        pay_single_btn.setStyleSheet(
            "background-color: #17a2b8; color: white; padding: 8px; font-weight: bold; font-size: 11px;")
        pay_single_btn.setToolTip("Select one invoice from table, fill payment details in 'Apply Payment' tab, then click here")
        pay_single_btn.clicked.connect(self._quick_pay_single)
        layout.addWidget(pay_single_btn)

        # Pay multiple button
        pay_multi_btn = QPushButton("💰 Pay Multiple")
        pay_multi_btn.setStyleSheet(
            "background-color: #6f42c1; color: white; padding: 8px; font-weight: bold; font-size: 11px;")
        pay_multi_btn.setToolTip(
            "Select multiple invoices (Ctrl+Click), fill payment in 'Apply Payment' tab, then click here")
        pay_multi_btn.clicked.connect(self._quick_pay_multiple)
        layout.addWidget(pay_multi_btn)

        # View summary button
        summary_btn = QPushButton("📊 Summary")
        summary_btn.setStyleSheet(
            "background-color: #ffc107; color: black; padding: 8px; font-weight: bold; font-size: 11px;")
        summary_btn.setToolTip("Show complete account history")
        summary_btn.clicked.connect(self._show_summary_tab)
        layout.addWidget(summary_btn)

        return group

    def _create_vendor_search(self):
        """Vendor search and selection"""
        group = QGroupBox("🔍 Select Vendor")
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px;}")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # Search
        self.vendor_search = QLineEdit()
        self.vendor_search.setPlaceholderText(
            "Type vendor name...")
        self.vendor_search.setStyleSheet("padding: 6px; font-size: 11px;")
        self.vendor_search.textChanged.connect(self._on_vendor_search_changed)
        layout.addWidget(self.vendor_search)

        # Results
        self.vendor_results = QComboBox()
        self.vendor_results.setEditable(True)  # Allow typing new vendor names
        self.vendor_results.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.vendor_results.setMinimumHeight(32)
        self.vendor_results.setStyleSheet("padding: 5px; font-size: 11px;")
        self.vendor_results.currentTextChanged.connect(
            self._on_vendor_selected)
        layout.addWidget(self.vendor_results)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("padding: 8px; font-weight: bold;")
        refresh_btn.clicked.connect(self._refresh_current_vendor)
        layout.addWidget(refresh_btn)

        return group

    def _create_invoice_list(self):
        """Invoice list for selected vendor with inline editing"""
        group = QGroupBox("📋 All Invoices for Vendor")
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px;}")
        layout = QVBoxLayout(group)

        # Vendor info and balance with Save button
        info_layout = QHBoxLayout()

        self.vendor_header = QLabel("No vendor selected")
        self.vendor_header.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 5px;")
        info_layout.addWidget(self.vendor_header, stretch=1)

        self.balance_label = QLabel("")
        self.balance_label.setStyleSheet(
            "font-size: 12px; padding: 5px; font-weight: bold;")
        info_layout.addWidget(self.balance_label)
        
        # Save Changes button for direct edits
        self.save_changes_btn = QPushButton("💾 Save Changes")
        self.save_changes_btn.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        self.save_changes_btn.clicked.connect(self._save_direct_edits)
        self.save_changes_btn.setEnabled(False)
        info_layout.addWidget(self.save_changes_btn)

        layout.addLayout(info_layout)

        # Filters section
        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            "QFrame { background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;}")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(5, 5, 5, 5)

        filter_layout.addWidget(QLabel("🔍 Filters:"))

        # Invoice number filter
        filter_layout.addWidget(QLabel("Invoice #:"))
        self.filter_invoice_num = QLineEdit()
        self.filter_invoice_num.setPlaceholderText("Search invoice #...")
        self.filter_invoice_num.setMaximumWidth(150)
        self.filter_invoice_num.textChanged.connect(
            self._apply_invoice_filters)
        filter_layout.addWidget(self.filter_invoice_num)

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
            self._apply_invoice_filters)
        filter_layout.addWidget(self.filter_year)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["All", "Paid", "Unpaid"])
        self.filter_status.setMaximumWidth(100)
        self.filter_status.currentIndexChanged.connect(
            self._apply_invoice_filters)
        filter_layout.addWidget(self.filter_status)

        # Clear filters button
        clear_filters_btn = QPushButton("❌ Clear")
        clear_filters_btn.setMaximumWidth(70)
        clear_filters_btn.clicked.connect(self._clear_invoice_filters)
        filter_layout.addWidget(clear_filters_btn)

        filter_layout.addStretch()

        layout.addWidget(filter_frame)

        # Invoice table - now includes running balance and is editable
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(8)
        self.invoice_table.setHorizontalHeaderLabels([
            "ID", "Invoice #", "Date", "Amount", "Paid", "Balance", "Running Balance", "Status"])
        # Set specific column widths for better appearance
        header = self.invoice_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # ID
        self.invoice_table.setColumnWidth(0, 60)
        header.setSectionResizeMode(
    1, QHeaderView.ResizeMode.Interactive)  # Invoice # - editable
        self.invoice_table.setColumnWidth(1, 150)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Date
        self.invoice_table.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Amount
        self.invoice_table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Paid
        self.invoice_table.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # Balance
        self.invoice_table.setColumnWidth(5, 110)
        header.setSectionResizeMode(
    6, QHeaderView.ResizeMode.Fixed)  # Running Balance
        self.invoice_table.setColumnWidth(6, 130)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)  # Status
        self.invoice_table.setColumnWidth(7, 80)
        self.invoice_table.setSelectionBehavior(
    QTableWidget.SelectionBehavior.SelectRows)
        self.invoice_table.setSelectionMode(
    QTableWidget.SelectionMode.ExtendedSelection)
        self.invoice_table.setAlternatingRowColors(True)
        self.invoice_table.setStyleSheet("QTableWidget { font-size: 11px;}")
        self.invoice_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.invoice_table.customContextMenuRequested.connect(
            self._show_invoice_context_menu)
        self.invoice_table.itemDoubleClicked.connect(
            self._on_invoice_double_clicked)
        # Enable inline editing
        self.invoice_table.itemChanged.connect(self._on_invoice_item_changed)
        # Enable sorting
        self.invoice_table.setSortingEnabled(True)
        layout.addWidget(self.invoice_table)

        hint = QLabel(
            "💡 Double-click Invoice # or Date to edit • Ctrl+Click for multi-select • Click headers to sort")
        hint.setStyleSheet(
            "font-size: 11px; color: #666; font-style: italic; padding: 5px; background-color: #f8f9fa;")
        layout.addWidget(hint)

        return group

    def _create_add_invoice_tab(self):
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
            "💳 Split Fees (Optional - for WCB overdue fees, CRA adjustments, etc.)")
        split_group.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 10px;} QGroupBox::title { subcontrol-origin: margin; left: 10px;}")
        split_layout = QVBoxLayout()

        # Split checkbox
        self.new_invoice_use_split = QCheckBox(
            "Split this invoice into vendor charge + separate fee")
        self.new_invoice_use_split.setToolTip(
            "Enable to separate base charge from overdue fees or other adjustments")
        self.new_invoice_use_split.stateChanged.connect(
            self._on_split_checkbox_changed)
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
        self.new_invoice_fee_type.addItems([
            "Overdue Fee",
            "Interest Charge",
            "Penalty",
            "Service Charge",
            "Late Payment Fee",
            "CRA Adjustment",
            "Other"])
        self.new_invoice_fee_type.setToolTip(
            "CRA: Fees are NOT included in income calculations - tracked separately for reporting")
        split_details_layout.addRow("Fee Type:", self.new_invoice_fee_type)

        # Info note
        fee_note = QLabel(
            "ℹ️ Overdue fees and penalties are tracked separately for CRA reporting (not counted as income)")
        fee_note.setStyleSheet(
            "font-size: 9px; color: #0066cc; font-style: italic;")
        split_details_layout.addRow("", fee_note)

        self.split_details.setVisible(False)
        split_layout.addWidget(self.split_details)

        split_group.setLayout(split_layout)
        layout.addWidget(split_group)

        # Add button
        add_btn = QPushButton("✅ Add Invoice")
        add_btn.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
        add_btn.clicked.connect(self._add_invoice)
        layout.addWidget(add_btn)

        layout.addStretch()

        return widget

    def _create_edit_invoice_tab(self):
        """Tab for editing selected invoice details"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Selection info with status
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(5, 5, 5, 5)
        info_widget.setStyleSheet("background-color: #d4edda; border-radius: 5px;")
        
        tip_label = QLabel(
            "💡 TIP: Edit Invoice # and Date directly in table! Double-click, then Save.")
        tip_label.setStyleSheet("font-size: 11px; color: #155724; font-weight: bold;")
        info_layout.addWidget(tip_label)
        
        self.edit_status_label = QLabel("No invoice loaded. Select an invoice and click 'Edit Selected Invoice' button.")
        self.edit_status_label.setStyleSheet("font-size: 11px; color: #004085; font-weight: bold; margin-top: 5px;")
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

        # Save button
        save_btn = QPushButton("💾 Save Changes")
        save_btn.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
        save_btn.clicked.connect(self._save_invoice_changes)
        btn_layout.addWidget(save_btn)

        # Delete button
        delete_btn = QPushButton("🗑️ Delete Invoice")
        delete_btn.setStyleSheet(
            "background-color: #dc3545; color: white; font-weight: bold; padding: 10px;")
        delete_btn.clicked.connect(self._delete_invoice)
        btn_layout.addWidget(delete_btn)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_edit_fields)
        btn_layout.addWidget(clear_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        return widget

    def _on_split_checkbox_changed(self, state):
        """Show/hide split fee details"""
        self.split_details.setVisible(state == Qt.CheckState.Checked.value)

    def _create_payment_tab(self):
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
        left_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
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
        
        top_layout.addLayout(left_form, stretch=1)
        
        # RIGHT COLUMN - Date and method
        right_form = QFormLayout()
        right_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.payment_date = StandardDateEdit(prefer_month_text=True)
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setDisplayFormat("MM/dd/yyyy")
        self.payment_date.setMaximumWidth(130)
        right_form.addRow("Date:", self.payment_date)

        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "check",
            "bank_transfer",
            "cash",
            "credit_card",
            "debit_card",
            "trade_of_services",
            "credit_adjustment",
            "unknown"])
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

        # Hint - payment buttons are in Quick Actions on left
        hint = QLabel(
            "💡 Enter payment details above, then use the Quick Action buttons on the LEFT:\n"
            "   • Pay One - Select 1 invoice, click 'Pay One' button\n"
            "   • Pay Multiple - Select multiple invoices (Ctrl+Click), click 'Pay Multiple' button")
        hint.setStyleSheet(
            "font-size: 11px; color: #0066cc; font-weight: bold; "
            "padding: 10px; background-color: #e7f3ff; border-left: 3px solid #0066cc;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()

        return widget

    def _create_banking_link_tab(self):
        """Tab for linking banking transactions"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        info = QLabel("🏦 Search banking transactions and link to invoices")
        info.setStyleSheet("padding: 8px; background-color: #e3f2fd; font-size: 11px; font-weight: bold;")
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
            self._toggle_banking_date_filter)
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
        search_btn.setStyleSheet("background-color: #007bff; color: white; padding: 8px; font-weight: bold;")
        search_btn.clicked.connect(self._search_banking)
        layout.addWidget(search_btn)

        # Results table
        self.banking_table = QTableWidget()
        self.banking_table.setColumnCount(6)
        self.banking_table.setHorizontalHeaderLabels([
            "TX ID", "Date", "Description", "Amount", "Check #", "Linked"])
        self.banking_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.banking_table.itemDoubleClicked.connect(
            self._link_banking_to_invoice)
        layout.addWidget(self.banking_table)

        hint = QLabel(
            "💡 Double-click a transaction to link it to selected invoice(s)")
        hint.setStyleSheet("font-size: 11px; color: #666; padding: 5px;")
        layout.addWidget(hint)

        return widget

    def _create_account_summary_tab(self):
        """Tab showing account summary and payment history"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setStyleSheet(
            "font-family: 'Courier New'; font-size: 11px;")
        layout.addWidget(self.summary_text)

        refresh_btn = QPushButton("🔄 Refresh Summary")
        refresh_btn.setStyleSheet("background-color: #007bff; color: white; padding: 8px; font-weight: bold;")
        refresh_btn.clicked.connect(self._refresh_account_summary)
        layout.addWidget(refresh_btn)

        return widget

    def _load_categories(self, combo_box=None):
        """Load GL account codes into the category combo box(es)"""
        try:
            cur = self.conn.get_cursor()
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
                if hasattr(self, 'new_invoice_category'):
                    self.new_invoice_category.clear()
                    self.new_invoice_category.addItems([""] + gl_entries)
                if hasattr(self, 'edit_invoice_category'):
                    self.edit_invoice_category.clear()
                    self.edit_invoice_category.addItems([""] + gl_entries)
            
            cur.close()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            print(f"Error loading GL codes for categories: {e}")

    def _on_vendor_search_changed(self, text):
        """Search for vendors as user types"""
        if len(text) < 2:
            self.vendor_results.clear()
            return

        try:
            cur = self.conn.get_cursor()
            cur.execute("""
                SELECT DISTINCT vendor_name
                FROM receipts
                WHERE vendor_name ILIKE %s
                ORDER BY vendor_name
                LIMIT 50
            """, (f"%{text}%",))

            vendors = [row[0] for row in cur.fetchall()]
            self.vendor_results.clear()
            
            # If no matches found, suggest creating new vendor
            if not vendors:
                self.vendor_results.addItem(f"📝 Use '{text.upper()}' (new vendor)")
                self.current_vendor = text.upper()  # Set it as current
            else:
                self.vendor_results.addItems(vendors)
            
            cur.close()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(
    self,
    "Search Error",
     f"Error searching vendors: {e}")

    def _on_vendor_selected(self, vendor_name):
        """Load invoices for selected vendor"""
        if not vendor_name:
            return

        # Handle new vendor indicator
        if vendor_name.startswith("📝 Use '"):
            # Extract vendor name from "📝 Use 'VENDOR' (new vendor)"
            vendor_name = vendor_name.split("'")[1].upper()
        
        self.current_vendor = vendor_name
        self._load_vendor_invoices()

    def _toggle_banking_date_filter(self, checked):
        """Enable/disable date range filter for banking search"""
        self.banking_date_from.setEnabled(checked)
        self.banking_date_to.setEnabled(checked)
        self.banking_preset_label.setEnabled(checked)
        self.banking_preset_year.setEnabled(checked)
        self.banking_preset_lastyear.setEnabled(checked)
        self.banking_preset_all.setEnabled(checked)

    def _set_banking_date_preset(self, preset):
        """Set date range to preset values"""
        today = QDate.currentDate()

        if preset == 'year':
            # This calendar year
            start = QDate(today.year(), 1, 1)
            end = today
        elif preset == 'last_year':
            # Last calendar year
            start = QDate(today.year() - 1, 1, 1)
            end = QDate(today.year() - 1, 12, 31)
        elif preset == 'all':
            # All time (5 years back is reasonable for banking)
            start = QDate(2010, 1, 1)
            end = today
        else:
            return

        self.banking_date_from.setDate(start)
        self.banking_date_to.setDate(end)
        self.banking_use_date_filter.setChecked(True)

    def _apply_invoice_filters(self):
        """Apply filters to invoice table"""
        if not hasattr(self, 'current_invoices') or not self.current_invoices:
            return

        invoice_num_filter = self.filter_invoice_num.text().strip().lower()
        year_filter = self.filter_year.currentData()
        status_filter = self.filter_status.currentText()

        # Store full list if not already stored
        if not hasattr(self, 'unfiltered_invoices'):
            self.unfiltered_invoices = self.current_invoices.copy()

        # Start with all invoices
        filtered = self.unfiltered_invoices.copy()

        # Apply invoice number filter
        if invoice_num_filter:
            filtered = [
    inv for inv in filtered if invoice_num_filter in str(
        inv[1]).lower()]

        # Apply year filter
        if year_filter is not None:
            filtered = [
    inv for inv in filtered if inv[2] and str(
        inv[2]).startswith(
            str(year_filter))]

        # Apply status filter
        if status_filter == "Paid":
            filtered = [inv for inv in filtered if inv[6] == "✅ Paid"]
        elif status_filter == "Unpaid":
            filtered = [inv for inv in filtered if inv[6] == "❌ Unpaid"]

        # Update current_invoices and refresh
        self.current_invoices = filtered
        self._refresh_invoice_table()

        # Show count
        if filtered != self.unfiltered_invoices:
            self.vendor_header.setText(
                f"📋 Invoices for: {self.current_vendor} "
                f"(showing {len(filtered)} of {len(self.unfiltered_invoices)})")

    def _clear_invoice_filters(self):
        """Clear all invoice filters"""
        self.filter_invoice_num.clear()
        self.filter_year.setCurrentIndex(0)
        self.filter_status.setCurrentIndex(0)

        # Restore full list
        if hasattr(self, 'unfiltered_invoices'):
            self.current_invoices = self.unfiltered_invoices.copy()
            self._refresh_invoice_table()
            self.vendor_header.setText(
                f"📋 Invoices for: {self.current_vendor}")

    def _load_vendor_invoices(self):
        """Load all invoices for current vendor"""
        if not self.current_vendor:
            return

        try:
            cur = self.conn.get_cursor()

            # Get all receipts (invoices) for this vendor - even if new vendor with no invoices yet
            cur.execute("""
                SELECT
                    r.receipt_id,
                    r.source_reference,
                    r.receipt_date,
                    r.gross_amount,
                    COALESCE(r.gross_amount, 0) as original_amount,
                    r.banking_transaction_id
                FROM receipts r
                WHERE r.vendor_name = %s
                ORDER BY r.receipt_date, r.receipt_id
            """, (self.current_vendor,))

            invoices = cur.fetchall()
            self.current_invoices = []

            # For each invoice, calculate paid amount from vendor_invoice_payments
            invoice_data = []
            total_invoiced = 0.0
            total_paid = 0.0
            total_balance = 0.0

            # Get all payments for these invoices
            payment_totals = {}
            if invoices:
                receipt_ids = [inv[0] for inv in invoices]
                try:
                    cur.execute("""
                        SELECT receipt_id, SUM(payment_amount) as total_paid
                        FROM vendor_invoice_payments
                        WHERE receipt_id = ANY(%s)
                        GROUP BY receipt_id
                    """, (receipt_ids,))
                    for row in cur.fetchall():
                        payment_totals[row[0]] = float(row[1]) if row[1] else 0.0
                except Exception:
                    # Table might not exist yet - rollback transaction to clear error state
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass

            for inv in invoices:
                receipt_id, ref, date, amount, orig_amt, banking_id = inv

                # Convert Decimal to float to avoid type mismatch
                orig_amt = float(orig_amt) if orig_amt is not None else 0.0

                # Get paid amount from payments table
                paid = payment_totals.get(receipt_id, 0.0)
                balance = orig_amt - paid
                status = "✅ Paid" if balance <= 0.01 else "❌ Unpaid"

                invoice_data.append(
                    (receipt_id, ref, date, orig_amt, paid, balance, status))
                total_invoiced += orig_amt
                total_paid += paid
                total_balance += balance

            self.current_invoices = invoice_data
            self.unfiltered_invoices = invoice_data.copy()  # Store for filtering

            # Update header
            self.vendor_header.setText(
                f"📋 Invoices for: {self.current_vendor}")
            self.balance_label.setText(
                f"Total Invoiced: ${total_invoiced:,.2f} | "
                f"Total Paid: ${total_paid:,.2f} | "
                f"Balance Due: ${total_balance:,.2f}")

            if total_balance > 0:
                self.balance_label.setStyleSheet(
                    "font-size: 12px; padding: 5px; color: red; font-weight: bold;")
            else:
                self.balance_label.setStyleSheet(
                    "font-size: 12px; padding: 5px; color: green;")

            # Update table
            self._refresh_invoice_table()
            cur.close()

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(
    self, "Load Error", f"Error loading invoices: {e}")

    def _refresh_invoice_table(self):
        """Refresh the invoice table display with running balance"""
        self.invoice_table.setRowCount(len(self.current_invoices))

        running_balance = 0.0

        for idx, invoice in enumerate(self.current_invoices):
            receipt_id, ref, date, amount, paid, balance, status = invoice

            # Convert to float to avoid type mismatch
            balance = float(balance) if balance is not None else 0.0
            amount = float(amount) if amount is not None else 0.0
            paid = float(paid) if paid is not None else 0.0

            # Update running balance (cumulative)
            running_balance += balance

            # Check if this row is selected
            is_selected = self.invoice_table.item(
    idx, 0) and self.invoice_table.item(
        idx, 0).isSelected()
            row_color = QColor("#e3f2fd") if is_selected else QColor(
                "white")  # Light blue for selected

            # ID (read-only)
            id_item = QTableWidgetItem(str(receipt_id))
            id_item.setBackground(QBrush(row_color))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make read-only
            self.invoice_table.setItem(idx, 0, id_item)

            # Invoice # (editable)
            inv_item = QTableWidgetItem(str(ref or f"R-{receipt_id}"))
            inv_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 1, inv_item)

            # Date (editable) - standardize format to MM/dd/yyyy
            if isinstance(date, str):
                try:
                                        parsed_date = datetime.strptime(
                                            date, "%Y-%m-%d").strftime("%m/%d/%Y")
                except Exception:
                    parsed_date = date
            else:
                parsed_date = date.strftime(
                    "%m/%d/%Y") if hasattr(date, 'strftime') else str(date)
            date_item = QTableWidgetItem(parsed_date)
            date_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 2, date_item)

            # Amount (read-only)
            amt_item = QTableWidgetItem(f"${amount:,.2f}")
            amt_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amt_item.setBackground(QBrush(row_color))
            amt_item.setFlags(amt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.invoice_table.setItem(idx, 3, amt_item)

            # Paid (read-only)
            paid_item = QTableWidgetItem(f"${paid:,.2f}")
            paid_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            paid_item.setBackground(QBrush(row_color))
            paid_item.setFlags(paid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.invoice_table.setItem(idx, 4, paid_item)

            # Balance (read-only - individual invoice balance)
            bal_item = QTableWidgetItem(f"${balance:,.2f}")
            bal_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bal_item.setBackground(QBrush(row_color))
            bal_item.setFlags(bal_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if balance > 0:
                bal_item.setForeground(QBrush(QColor("red")))
            self.invoice_table.setItem(idx, 5, bal_item)

            # Running Balance (read-only - cumulative - shows what's owed up to this point)
            running_bal_item = QTableWidgetItem(f"${running_balance:,.2f}")
            running_bal_item.setTextAlignment(
    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            running_bal_item.setForeground(QBrush(QColor("darkblue")))
            running_bal_item.setFont(self._get_bold_font())
            running_bal_item.setBackground(QBrush(row_color))
            running_bal_item.setFlags(running_bal_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.invoice_table.setItem(idx, 6, running_bal_item)

            # Status (read-only)
            status_item = QTableWidgetItem(status)
            status_item.setBackground(QBrush(row_color))
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.invoice_table.setItem(idx, 7, status_item)

    def _get_bold_font(self):
        """Get bold font for running balance"""
        font = QFont()
        font.setBold(True)
        return font

    def _add_invoice(self):
        """Add a new invoice for current vendor (with optional fee split)"""
        if not self.current_vendor:
            QMessageBox.warning(
    self, "No Vendor", "Please select a vendor first.")
            return

        invoice_num = self.new_invoice_num.text().strip()
        amount = self.new_invoice_amount.get_value()

        if amount <= 0:
            QMessageBox.warning(
    self,
    "Invalid Amount",
     "Amount must be greater than 0.")
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
                    f"Base ({base_amount:.2f}) + Fee ({fee_amount:.2f}) must equal Total ({amount:.2f})")
                return

        try:
            cur = self.conn.get_cursor()

            # Add main invoice
            sql = """
                INSERT INTO receipts (
                    vendor_name, source_reference, receipt_date,
                    gross_amount, description, category,
                    created_from_banking, source_file) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING receipt_id
            """

            description = self.new_invoice_desc.toPlainText().strip() or None
            if use_split and fee_amount > 0:
                if description:
                    description = f"{description} | Base: ${base_amount:.2f} + {fee_type}: ${fee_amount:.2f}"
                else:
                    description = f"Base: ${base_amount:.2f} + {fee_type}: ${fee_amount:.2f}"

            params = (
                self.current_vendor,
                invoice_num or None,
                self.new_invoice_date.date().toPyDate(),
                amount,
                description,
                self.new_invoice_category.currentText().strip() or None,
                False,
                'VENDOR_INVOICE_MANAGER')

            cur.execute(sql, params)
            receipt_id = cur.fetchone()[0]

            # If split, create fee entry in vendor ledger (if table exists)
            if use_split and fee_amount > 0:
                try:
                    # Try to create a ledger entry for the fee
                    vendor_sql = """
                        INSERT INTO vendor_account_ledger (
                            account_id, entry_date, entry_type, amount,
                            source_table, source_id, notes)
                        -- vendor_accounts table doesn't exist
                        -- Skipping vendor ledger entry
                    """
                except Exception:
                    # vendor_accounts and vendor_account_ledger don't exist
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    pass  # Vendor ledger tables don't exist in current schema

            self.conn.commit()
            cur.close()

            msg = f"✅ Invoice added!\n\nInvoice ID: {receipt_id}\nAmount: ${amount:,.2f}"
            if use_split and fee_amount > 0:
                msg += f"\n\nBreakdown:\n  Base: ${base_amount:,.2f}\n  {fee_type}: ${fee_amount:,.2f}\n\n⚠️ Fee tracked separately for CRA reporting"

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
            self.conn.rollback()
            QMessageBox.critical(
    self, "Add Error", f"Failed to add invoice:\n\n{e}")

    def _edit_selected_invoice(self):
        """Load selected invoice into edit form"""
        selected = self.invoice_table.selectedItems()
        if not selected:
            QMessageBox.warning(
    self,
    "No Selection",
     "Please select an invoice from the list to edit.")
            return

        row = self.invoice_table.currentRow()
        if row < 0 or row >= len(self.available_invoices):
            QMessageBox.warning(
    self,
    "Invalid Selection",
     "Please select a valid invoice.")
            return

        invoice = self.available_invoices[row]
        receipt_id, ref, date, amount, paid, balance = invoice

        # Store the receipt_id for later save
        self.editing_receipt_id = receipt_id

        # Load into form
        self.edit_invoice_num.setText(str(ref or ""))
        self.edit_invoice_amount.setText(f"{amount:.2f}")
        # Description not in the basic invoice tuple
        self.edit_invoice_desc.setPlainText("")
        self.edit_invoice_category.setCurrentText("")

        # Parse and set date
        if isinstance(date, str):
            try:
                parsed_date = datetime.strptime(
                    date, "%Y-%m-%d").date()
                self.edit_invoice_date.setDate(parsed_date)
            except Exception:
                self.edit_invoice_date.setDate(QDate.currentDate())
        else:
            self.edit_invoice_date.setDate(date if date else QDate.currentDate())

        # Switch to edit tab
        parent_tabs = self.sender().parent() if self.sender() else None
        # Find the details_tabs widget and switch to edit tab
        info_label = QMessageBox.information(
            self,
            "Edit Mode",
            f"Invoice {ref} loaded for editing.\n\nMake your changes in the '✏️ Edit Invoice' tab and click 'Save Changes'.")

    def _save_invoice_changes(self):
        """Save edited invoice changes"""
        if not hasattr(self, 'editing_receipt_id') or self.editing_receipt_id is None:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to edit first.")
            return

        receipt_id = self.editing_receipt_id
        invoice_num = self.edit_invoice_num.text().strip()
        amount = self.edit_invoice_amount.get_value()

        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Amount must be greater than 0.")
            return

        try:
            cur = self.conn.get_cursor()

            sql = """
                UPDATE receipts
                SET source_reference = %s,
                    receipt_date = %s,
                    gross_amount = %s,
                    description = %s,
                    category = %s,
                    modified_at = NOW()
                WHERE receipt_id = %s
            """

            description = self.edit_invoice_desc.toPlainText().strip() or None

            params = (
                invoice_num or None,
                self.edit_invoice_date.date().toPyDate(),
                amount,
                description,
                self.edit_invoice_category.currentText().strip() or None,
                receipt_id)

            cur.execute(sql, params)
            self.conn.commit()
            cur.close()

            QMessageBox.information(self, "Success", f"✅ Invoice {receipt_id} updated successfully!")

            # Clear form and refresh
            self._clear_edit_fields()
            self._load_vendor_invoices()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Save Error", f"Failed to save invoice changes:\n\n{e}")

    def _delete_invoice(self):
        """Delete/void the selected invoice with safety checks"""
        if not hasattr(self, 'editing_receipt_id') or self.editing_receipt_id is None:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to delete first.")
            return

        receipt_id = self.editing_receipt_id
        invoice_num = self.edit_invoice_num.text().strip()

        try:
            cur = self.conn.get_cursor()

            # SAFETY CHECK 1: Check if linked to banking transaction
            cur.execute("""
                SELECT banking_transaction_id, gross_amount
                FROM receipts
                WHERE receipt_id = %s
            """, (receipt_id,))
            receipt_info = cur.fetchone()

            if not receipt_info:
                QMessageBox.warning(self, "Not Found", "Invoice not found in database.")
                cur.close()
                return

            banking_id, amount = receipt_info
            has_banking_link = banking_id is not None

            # SAFETY CHECK 2: Check if has payments in ledger
            cur.execute("""
                SELECT COUNT(*)
                FROM vendor_account_ledger
                WHERE source_table = 'receipts' AND source_id = %s
            """, (str(receipt_id),))
            ledger_count = cur.fetchone()[0]
            has_ledger_entries = ledger_count > 0

            # Build warning message
            warning_msg = f"Are you sure you want to delete invoice {invoice_num or receipt_id}?\n"
            warning_msg += f"Amount: ${amount:.2f}\n\n"

            if has_banking_link:
                warning_msg += "⚠️ WARNING: This invoice is linked to banking transaction #{banking_id}\n"
                warning_msg += "   The banking link will be REMOVED (transaction remains)\n\n"

            if has_ledger_entries:
                warning_msg += f"⚠️ WARNING: This invoice has {ledger_count} payment ledger entries\n"
                warning_msg += "   These will be DELETED\n\n"

            warning_msg += "This action CANNOT be undone!\n\nContinue?"

            reply = QMessageBox.question(
                self,
                "⚠️ Confirm Delete",
                warning_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # Default to No
            )

            if reply == QMessageBox.StandardButton.No:
                cur.close()
                return

            # Perform deletion with proper cleanup
            deleted_items = []

            # 1. Remove banking link (but keep transaction)
            if has_banking_link:
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = NULL
                    WHERE receipt_id = %s
                """, (receipt_id,))
                deleted_items.append(f"Unlinked from banking TX #{banking_id}")

            # 2. Delete ledger entries
            if has_ledger_entries:
                cur.execute("""
                    DELETE FROM vendor_account_ledger
                    WHERE source_table = 'receipts' AND source_id = %s
                """, (str(receipt_id),))
                deleted_items.append(f"Deleted {ledger_count} ledger entries")

            # 3. Delete matching ledger links
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE receipt_id = %s
            """, (receipt_id,))

            # 4. Finally delete the receipt itself
            cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
            deleted_items.append(f"Deleted receipt #{receipt_id}")

            self.conn.commit()
            cur.close()

            summary = "\n".join([f"  ✅ {item}" for item in deleted_items])
            QMessageBox.information(
                self,
                "Success",
                f"Invoice {invoice_num or receipt_id} deleted successfully!\n\n{summary}")

            # Clear form and refresh
            self._clear_edit_fields()
            self._load_vendor_invoices()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Delete Error", f"Failed to delete invoice:\n\n{e}")

    def _clear_edit_fields(self):
        """Clear edit form fields"""
        self.edit_invoice_num.clear()
        self.edit_invoice_amount.setText("0.00")
        self.edit_invoice_desc.clear()
        self.edit_invoice_date.setDate(QDate.currentDate())
        self.edit_invoice_category.setCurrentText("")
        self.editing_receipt_id = None

    def _apply_to_single_invoice(self):
        """Apply payment to a single selected invoice"""
        selected = self.invoice_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an invoice from the list.")
            return

        row = self.invoice_table.currentRow()
        if row < 0:
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, date, amount, paid, balance, status = invoice

        payment_amt = self.payment_amount.get_value()
        if payment_amt <= 0:
            QMessageBox.warning(self, "Invalid Payment", "Payment amount must be greater than 0.")
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.get_cursor()

            # Get banking ID if provided
            banking_id = None
            banking_text = self.payment_banking_id.text().strip()
            if banking_text:
                try:
                    banking_id = int(banking_text)
                except ValueError:
                    QMessageBox.warning(self, "Invalid Banking ID", "Banking ID must be a number.")
                    return

            # Get payment reference and date
            payment_ref = self.payment_reference.text().strip() or f"Payment for invoice {ref or receipt_id}"
            payment_date = self.payment_date.date().toPyDate()
            payment_method = self.payment_method.currentText()

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

            # Record the payment
            cur.execute("""
                INSERT INTO vendor_invoice_payments 
                (receipt_id, payment_date, payment_amount, payment_method, reference, banking_transaction_id, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (receipt_id, payment_date, payment_amt, payment_method, payment_ref, banking_id, 
                   f"Payment to {self.current_vendor}"))

            # Update banking transaction link if provided
            if banking_id:
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = %s
                    WHERE receipt_id = %s
                """, (banking_id, receipt_id))

            self.conn.commit()
            cur.close()

            QMessageBox.information(self, "Success", 
                f"✅ Payment of ${payment_amt:,.2f} recorded successfully!\n\n"
                f"Invoice: {ref or receipt_id}\n"
                f"Reference: {payment_ref}")

            # Clear form
            self.payment_amount.setText("0.00")
            self.payment_reference.clear()
            self.payment_banking_id.clear()

            # Refresh
            self._load_vendor_invoices()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Payment Error", f"Failed to apply payment:\n\n{e}")

    def _apply_to_multiple_invoices(self):
        """Apply payment across multiple invoices"""
        if not self.current_vendor:
            QMessageBox.warning(self, "No Vendor", "Please select a vendor first.")
            return

        payment_amt = self.payment_amount.get_value()
        if payment_amt <= 0:
            QMessageBox.warning(self, "Invalid Payment", "Payment amount must be greater than 0.")
            return

        # Get payment method
        payment_method = self.payment_method.currentText()

        # Get invoices with outstanding balances
        unpaid_invoices = [inv for inv in self.current_invoices if inv[5] > 0]  # inv[5] = balance

        if not unpaid_invoices:
            QMessageBox.information(self, "No Outstanding Invoices", "All invoices are paid in full.")
            return

        # Show allocation dialog
        dialog = MultiInvoicePaymentDialog(
            self.conn,
            self.current_vendor,
            payment_amt,
            unpaid_invoices,
            self,
            payment_method)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            allocations = dialog.get_allocations()

            if not allocations:
                QMessageBox.warning(self, "No Allocation", "No invoices were selected for payment.")
                return

            # Apply allocations
            try:
                cur = self.conn.get_cursor()

                # Get payment reference and date
                payment_ref = self.payment_reference.text().strip() or f"Multi-invoice payment to {self.current_vendor}"
                payment_date = self.payment_date.date().toPyDate()
                payment_method = self.payment_method.currentText()
                
                # Get banking ID if provided
                banking_id = None
                banking_text = self.payment_banking_id.text().strip()
                if banking_text:
                    try:
                        banking_id = int(banking_text)
                    except ValueError:
                        pass

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

                # Record payments for each allocated invoice
                for receipt_id, allocated_amt in allocations.items():
                    cur.execute("""
                        INSERT INTO vendor_invoice_payments 
                        (receipt_id, payment_date, payment_amount, payment_method, reference, banking_transaction_id, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (receipt_id, payment_date, allocated_amt, payment_method, payment_ref, banking_id,
                           f"Split payment to {self.current_vendor}"))

                self.conn.commit()
                cur.close()

                alloc_summary = "\n".join([
                    f"Invoice {rid}: ${amt:,.2f}"
                    for rid, amt in allocations.items()])

                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ Payment allocated successfully!\n\n{alloc_summary}")

                # Clear form
                self.payment_amount.setText("0.00")
                self.payment_reference.clear()
                self.payment_banking_id.clear()

                # Refresh
                self._load_vendor_invoices()

            except Exception as e:
                self.conn.rollback()
                QMessageBox.critical(self, "Allocation Error", f"Failed to allocate payment:\n\n{e}")

    def _search_banking(self):
        """Search banking transactions"""
        amount = self.banking_search_amount.get_value()
        desc = self.banking_search_desc.text().strip()

        if amount <= 0 and not desc:
            QMessageBox.warning(self, "No Search Criteria", "Enter amount or description to search.")
            return

        try:
            cur = self.conn.get_cursor()

            sql = """
                SELECT
                    transaction_id,
                    transaction_date,
                    description,
                    debit_amount,
                    check_number,
                    (SELECT COUNT(*) FROM receipts WHERE banking_transaction_id = bt.transaction_id) as linked_count
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

                self.banking_table.setItem(idx, 0, QTableWidgetItem(str(tx_id)))
                # Standardize date format to MM/dd/yyyy
                if isinstance(date, str):
                    try:
                        formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d/%Y")
                    except Exception:
                        formatted_date = date
                else:
                    formatted_date = date.strftime("%m/%d/%Y") if hasattr(date, 'strftime') else str(date)
                self.banking_table.setItem(idx, 1, QTableWidgetItem(formatted_date))
                self.banking_table.setItem(idx, 2, QTableWidgetItem(description[:50]))

                amt_item = QTableWidgetItem(f"${amt:,.2f}")
                amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.banking_table.setItem(idx, 3, amt_item)

                self.banking_table.setItem(idx, 4, QTableWidgetItem(str(check or "")))

                linked_item = QTableWidgetItem("✅ Yes" if linked > 0 else "❌ No")
                self.banking_table.setItem(idx, 5, linked_item)

            # Show info message about results
            if len(results) == 0:
                QMessageBox.information(
                    self,
                    "No Results",
                    "No banking transactions found matching your criteria.\n\n"
                    "💡 Tip: If searching by amount only, uncheck 'Filter by date range' "
                    "or use 'All Time' to search all years.")
            else:
                date_info = ""
                if self.banking_use_date_filter.isChecked():
                    date_info = f"\n📅 Filtered: {self.banking_date_from.date().toString('MM/dd/yyyy')} to {self.banking_date_to.date().toString('MM/dd/yyyy')}"

                QMessageBox.information(
                    self,
                    "Search Results",
                    f"Found {len(results)} transactions{date_info}")

            cur.close()

        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Error searching banking:\n\n{e}")

    def _link_banking_to_invoice(self, item):
        """Link selected banking transaction to selected invoice(s) automatically"""
        row = self.banking_table.currentRow()
        if row < 0:
            return

        # Get banking transaction details
        tx_id = int(self.banking_table.item(row, 0).text())
        tx_amount_text = self.banking_table.item(row, 3).text().replace('$', '').replace(',', '')
        tx_amount = float(tx_amount_text)
        tx_date_text = self.banking_table.item(row, 1).text()

        # Get selected invoices
        selected_rows = set(item.row() for item in self.invoice_table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(
                self,
                "No Invoices Selected",
                "Please select one or more invoices from the table first,\nthen double-click the banking transaction.")
            return

        selected_invoices = [self.current_invoices[row] for row in selected_rows if row < len(self.current_invoices)]

        if not selected_invoices:
            QMessageBox.warning(self, "No Invoices", "No valid invoices selected.")
            return

        # Calculate total needed
        total_to_pay = sum(inv[5] for inv in selected_invoices)  # inv[5] is balance

        # Confirm allocation
        invoice_list = "\n".join([f"  • Invoice {inv[1]}: ${inv[5]:,.2f}" for inv in selected_invoices])

        confirm = QMessageBox.question(
            self,
            "Confirm Payment Allocation",
            f"Apply banking transaction #{tx_id} (${tx_amount:,.2f})\n"
            f"to {len(selected_invoices)} invoice(s):\n\n{invoice_list}\n\n"
            f"Total to allocate: ${min(total_to_pay, tx_amount):,.2f}\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Apply payments via ledger
        try:
            cur = self.conn.get_cursor()

            # vendor_accounts table doesn't exist - skip vendor account lookup
            account_result = None
            if not account_result:
                QMessageBox.information(self, "Info", "Vendor account payments not available in this version")
                return

            account_id = account_result[0] if account_result else None
            remaining = tx_amount
            applied_count = 0

            payment_date = datetime.strptime(tx_date_text, "%m/%d/%Y").date()

            for inv in selected_invoices:
                if remaining <= 0.01:
                    break

                receipt_id = inv[0]
                invoice_balance = inv[5]

                # Apply up to the balance or remaining amount
                apply_amount = min(invoice_balance, remaining)

                if apply_amount > 0.01:
                    # Create ledger entry (negative = payment)
                    cur.execute("""
                        INSERT INTO vendor_account_ledger (
                            account_id, entry_date, entry_type, amount,
                            source_table, source_id, notes) VALUES (%s, %s, 'PAYMENT', %s, 'receipts', %s, %s)
                    """, (
                        account_id,
                        payment_date,
                        -apply_amount,  # Negative for payment
                        str(receipt_id),
                        f"Banking TX #{tx_id} - Auto-allocated payment"))

                    # Also link the banking transaction to the receipt
                    cur.execute("""
                        UPDATE receipts
                        SET banking_transaction_id = %s
                        WHERE receipt_id = %s
                    """, (tx_id, receipt_id))

                    remaining -= apply_amount
                    applied_count += 1

            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "✅ Payment Applied",
                f"Successfully linked banking transaction #{tx_id}\n"
                f"to {applied_count} invoice(s).\n\n"
                f"Total applied: ${tx_amount - remaining:,.2f}\n"
                f"Remaining: ${remaining:,.2f}")

            # Refresh the display
            self._load_vendor_invoices()
            self._search_banking()  # Refresh banking table to show it's linked

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(
                self,
                "Payment Error",
                f"Failed to apply payment:\n\n{e}")

    def _refresh_current_vendor(self):
        """Refresh current vendor's invoices"""
        if self.current_vendor:
            self._load_vendor_invoices()
            self._refresh_account_summary()

    def _refresh_account_summary(self):
        """Generate and display account summary"""
        if not self.current_vendor:
            self.summary_text.setPlainText("Select a vendor to view account summary.")
            return
        
        if not hasattr(self, 'current_invoices') or not self.current_invoices:
            self.summary_text.setPlainText(f"No invoices found for {self.current_vendor}.\n\nThis vendor may not have any invoices yet.")
            return

        summary = f"ACCOUNT SUMMARY: {self.current_vendor}\n"
        summary += "=" * 60 + "\n\n"

        total_invoiced = sum(float(inv[3]) for inv in self.current_invoices)
        total_paid = sum(float(inv[4]) for inv in self.current_invoices)
        total_balance = sum(float(inv[5]) for inv in self.current_invoices)

        summary += f"Total Invoiced:    ${total_invoiced:>12,.2f}\n"
        summary += f"Total Paid:        ${total_paid:>12,.2f}\n"
        summary += f"Balance Due:       ${total_balance:>12,.2f}\n"
        summary += "\n" + "=" * 60 + "\n\n"

        summary += f"INVOICE DETAILS ({len(self.current_invoices)} total):\n"
        summary += "-" * 60 + "\n"

        for inv in self.current_invoices:
            receipt_id, ref, date, amount, paid, balance, status = inv
            summary += f"\nInvoice: {ref or f'R-{receipt_id}':<15} Date: {date}\n"
            summary += f"  Amount:  ${float(amount):>10,.2f}\n"
            summary += f"  Paid:    ${float(paid):>10,.2f}\n"
            summary += f"  Balance: ${float(balance):>10,.2f}  {status}\n"

        self.summary_text.setPlainText(summary)

    def _show_invoice_context_menu(self, pos):
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

    def _on_invoice_double_clicked(self, item):
        """Handle invoice double-click - load into edit form"""
        # Only allow editing Invoice # and Date columns
        if item.column() in [1, 2]:  # Invoice # or Date
            return  # Let inline editing happen
        else:
            # Other columns - load full edit form
            self._edit_selected_invoice()

    def _edit_selected_invoice(self):
        """Edit selected invoice - load into edit form"""
        row = self.invoice_table.currentRow()
        if row < 0 or row >= len(self.current_invoices):
            QMessageBox.warning(self, "No Selection", "Please select an invoice to edit.")
            return
        
        invoice = self.current_invoices[row]
        receipt_id, ref, date, amount, paid, balance, status = invoice
        
        try:
            cur = self.conn.get_cursor()
            cur.execute("""
                SELECT receipt_id, source_reference, receipt_date, gross_amount, description, category
                FROM receipts
                WHERE receipt_id = %s
            """, (receipt_id,))
            
            data = cur.fetchone()
            cur.close()
            
            if data:
                self.editing_receipt_id = data[0]
                self.edit_invoice_num.setText(data[1] or "")
                
                # Parse date
                invoice_date = data[2]
                if isinstance(invoice_date, str):
                    try:
                        from datetime import datetime
                        invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
                    except Exception:
                        pass
                
                if hasattr(invoice_date, 'year'):
                    self.edit_invoice_date.setDate(QDate(invoice_date.year, invoice_date.month, invoice_date.day))
                
                self.edit_invoice_amount.setText(f"{data[3]:.2f}")
                self.edit_invoice_desc.setPlainText(data[4] or "")
                
                # Set category
                category = data[5] or ""
                idx = self.edit_invoice_category.findText(category)
                if idx >= 0:
                    self.edit_invoice_category.setCurrentIndex(idx)
                else:
                    self.edit_invoice_category.setCurrentText(category)
                
                # Switch to edit tab (index 1)
                self.details_tabs.setCurrentIndex(1)
                
                # Update status label
                self.edit_status_label.setText(f"✅ Editing: Invoice {ref or receipt_id} (ID: {receipt_id}) - Make changes and click Save")
                self.edit_status_label.setStyleSheet("font-size: 11px; color: #28a745; font-weight: bold; margin-top: 5px;")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load invoice:\n\n{e}")

    def _delete_selected_invoice(self):
        """Delete selected invoice with safety checks"""
        row = self.invoice_table.currentRow()
        if row < 0 or row >= len(self.current_invoices):
            QMessageBox.warning(self, "No Selection", "Please select an invoice to delete.")
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, date, amount, paid, balance, status = invoice

        try:
            cur = self.conn.get_cursor()

            # SAFETY CHECK: Check if linked to banking transaction
            cur.execute("""
                SELECT banking_transaction_id
                FROM receipts
                WHERE receipt_id = %s
            """, (receipt_id,))
            result = cur.fetchone()

            if not result:
                QMessageBox.warning(self, "Not Found", "Invoice not found in database.")
                cur.close()
                return

            banking_id = result[0]
            has_banking_link = banking_id is not None

            # SAFETY CHECK: Check ledger entries
            cur.execute("""
                SELECT COUNT(*)
                FROM vendor_account_ledger
                WHERE source_table = 'receipts' AND source_id = %s
            """, (str(receipt_id),))
            ledger_count = cur.fetchone()[0]
            has_ledger_entries = ledger_count > 0

            # Build warning
            warning_msg = f"Delete invoice {ref or f'R-{receipt_id}'}?\n"
            warning_msg += f"Date: {date}  Amount: ${amount:.2f}\n\n"

            if has_banking_link:
                warning_msg += f"⚠️ WARNING: Linked to banking TX #{banking_id}\n"
                warning_msg += "   Banking link will be removed\n\n"

            if has_ledger_entries:
                warning_msg += f"⚠️ WARNING: Has {ledger_count} payment entries\n"
                warning_msg += "   Payment records will be deleted\n\n"

            if paid > 0:
                warning_msg += f"⚠️ This invoice has payments totaling ${paid:.2f}\n\n"

            warning_msg += "This CANNOT be undone!\n\nContinue?"

            confirm = QMessageBox.question(
                self,
                "⚠️ Confirm Delete",
                warning_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)

            if confirm != QMessageBox.StandardButton.Yes:
                cur.close()
                return

            # Perform safe deletion
            # 1. Unlink banking (keep transaction)
            if has_banking_link:
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = NULL
                    WHERE receipt_id = %s
                """, (receipt_id,))

            # 2. Delete ledger entries
            if has_ledger_entries:
                cur.execute("""
                    DELETE FROM vendor_account_ledger
                    WHERE source_table = 'receipts' AND source_id = %s
                """, (str(receipt_id),))

            # 3. Delete matching links
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE receipt_id = %s
            """, (receipt_id,))

            # 4. Delete receipt
            cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))

            self.conn.commit()
            cur.close()

            invoice_ref = ref or f"R-{receipt_id}"
            QMessageBox.information(
                self,
                "✅ Deleted",
                f"Invoice {invoice_ref} deleted successfully.",)
            self._load_vendor_invoices()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Delete Error", f"Failed to delete:\n\n{e}")

    def _view_invoice_details(self):
        """View full invoice details"""
        row = self.invoice_table.currentRow()
        if row < 0:
            return

        invoice = self.current_invoices[row]
        receipt_id, ref, date, amount, paid, balance, status = invoice

        try:
            cur = self.conn.get_cursor()
            cur.execute("""
                SELECT
                    receipt_id, vendor_name, source_reference, receipt_date,
                    gross_amount, description, category, payment_method,
                    banking_transaction_id, created_from_banking
                FROM receipts
                WHERE receipt_id = %s
            """, (receipt_id,))

            full_data = cur.fetchone()
            cur.close()

            if full_data:
                details = f"INVOICE DETAILS\n{'='*50}\n\n"
                details += f"Receipt ID:         {full_data[0]}\n"
                details += f"Vendor:             {full_data[1]}\n"
                details += f"Invoice #:          {full_data[2] or 'N/A'}\n"
                details += f"Date:               {full_data[3]}\n"
                details += f"Amount:             ${full_data[4]:,.2f}\n"
                details += f"Description:        {full_data[5] or 'N/A'}\n"
                details += f"Category:           {full_data[6] or 'N/A'}\n"
                details += f"Payment Method:     {full_data[7] or 'N/A'}\n"
                details += f"Banking TX ID:      {full_data[8] or 'Not Linked'}\n"
                details += f"Auto-Created:       {'Yes' if full_data[9] else 'No'}\n"

                QMessageBox.information(self, "Invoice Details", details)

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load details:\n\n{e}")

    def _on_invoice_item_changed(self, item):
        """Track changes to invoice items for inline editing"""
        if not hasattr(self, '_editing_enabled'):
            self._editing_enabled = True
            
        # Only allow editing invoice # (column 1) and date (column 2)
        col = item.column()
        if col not in [1, 2]:
            return
            
        # Enable save button
        self.save_changes_btn.setEnabled(True)
        
        # Mark row as edited
        row = item.row()
        for c in range(self.invoice_table.columnCount()):
            cell_item = self.invoice_table.item(row, c)
            if cell_item:
                cell_item.setBackground(QBrush(QColor("#fff3cd")))  # Light yellow

    def _save_direct_edits(self):
        """Save direct edits made in the invoice table"""
        try:
            cur = self.conn.get_cursor()
            changes_made = 0
            
            # Temporarily disable sorting to preserve row order
            self.invoice_table.setSortingEnabled(False)
            
            for row in range(self.invoice_table.rowCount()):
                # Check if row has yellow background (edited)
                item = self.invoice_table.item(row, 1)
                if not item or item.background().color() != QColor("#fff3cd"):
                    continue
                
                # Get receipt_id from first column
                receipt_id = int(self.invoice_table.item(row, 0).text())
                
                # Get new values
                new_invoice_num = self.invoice_table.item(row, 1).text()
                new_date_str = self.invoice_table.item(row, 2).text()
                
                # Parse date (MM/dd/yyyy format)
                try:
                    from datetime import datetime
                    new_date = datetime.strptime(new_date_str, "%m/%d/%Y").date()
                except Exception:
                    QMessageBox.warning(self, "Invalid Date", 
                        f"Row {row+1}: Invalid date format. Use MM/DD/YYYY")
                    continue
                
                # Update database
                cur.execute("""
                    UPDATE receipts
                    SET source_reference = %s, receipt_date = %s
                    WHERE receipt_id = %s
                """, (new_invoice_num, new_date, receipt_id))
                
                changes_made += 1
            
            if changes_made > 0:
                self.conn.commit()
                QMessageBox.information(self, "Success", 
                    f"✅ Saved {changes_made} invoice change(s)!")
                self.save_changes_btn.setEnabled(False)
                self._load_vendor_invoices()  # Reload to show updated data
            else:
                QMessageBox.information(self, "No Changes", 
                    "No changes detected to save.")
            
            cur.close()
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Save Error", 
                f"Failed to save changes:\n\n{e}")
        finally:
            self.invoice_table.setSortingEnabled(True)

    def _save_invoice_changes(self):
        """Save changes from the edit form"""
        if not hasattr(self, 'editing_receipt_id') or not self.editing_receipt_id:
            QMessageBox.warning(self, "No Invoice", "No invoice loaded for editing.")
            return
        
        try:
            # Get values from form
            invoice_num = self.edit_invoice_num.text().strip()
            invoice_date = self.edit_invoice_date.date().toPyDate()
            amount = self.edit_invoice_amount.get_value()
            description = self.edit_invoice_desc.toPlainText().strip()
            category = self.edit_invoice_category.currentText().strip()
            
            if amount <= 0:
                QMessageBox.warning(self, "Invalid Amount", "Amount must be greater than 0.")
                return
            
            # Update database
            cur = self.conn.get_cursor()
            cur.execute("""
                UPDATE receipts
                SET source_reference = %s,
                    receipt_date = %s,
                    gross_amount = %s,
                    description = %s,
                    category = %s
                WHERE receipt_id = %s
            """, (invoice_num, invoice_date, amount, description, category, self.editing_receipt_id))
            
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(self, "Success", f"✅ Invoice updated successfully!")
            
            # Update status
            self.edit_status_label.setText(f"✅ Saved! Invoice {invoice_num or self.editing_receipt_id} updated.")
            self.edit_status_label.setStyleSheet("font-size: 11px; color: #28a745; font-weight: bold; margin-top: 5px;")
            
            # Reload invoice list
            self._load_vendor_invoices()
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Save Error", f"Failed to save invoice:\n\n{e}")

    def _delete_invoice(self):
        """Delete the currently loaded invoice from edit form"""
        if not hasattr(self, 'editing_receipt_id') or not self.editing_receipt_id:
            QMessageBox.warning(self, "No Invoice", "No invoice loaded for deletion.")
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
        
        QMessageBox.warning(self, "Not Found", "Invoice not found in current list.")

    def _clear_edit_fields(self):
        """Clear all edit form fields"""
        self.editing_receipt_id = None
        self.edit_invoice_num.clear()
        self.edit_invoice_date.setDate(QDate.currentDate())
        self.edit_invoice_amount.setText("0.00")
        self.edit_invoice_desc.clear()
        self.edit_invoice_category.setCurrentIndex(0)
        self.edit_status_label.setText("No invoice loaded. Select an invoice and click 'Edit Selected Invoice' button.")
        self.edit_status_label.setStyleSheet("font-size: 11px; color: #004085; font-weight: bold; margin-top: 5px;")

    def _quick_pay_single(self):
        """Quick pay from left panel - switch to payment tab and call pay single"""
        # Switch to payment tab first
        self.details_tabs.setCurrentIndex(2)  # Apply Payment tab
        # Then call the actual payment function
        self._apply_to_single_invoice()

    def _quick_pay_multiple(self):
        """Quick pay multiple from left panel - switch to payment tab and call pay multiple"""
        # Switch to payment tab first
        self.details_tabs.setCurrentIndex(2)  # Apply Payment tab
        # Then call the actual payment function
        self._apply_to_multiple_invoices()

    def _show_summary_tab(self):
        """Show summary tab and refresh data"""
        # Switch to summary tab
        self.details_tabs.setCurrentIndex(4)  # Summary tab
        # Refresh the summary
        self._refresh_account_summary()

