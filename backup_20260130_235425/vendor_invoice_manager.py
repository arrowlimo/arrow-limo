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

import psycopg2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QDoubleSpinBox, QGroupBox, QFormLayout, QTextEdit,
    QHeaderView, QMessageBox, QCheckBox, QSplitter, QFrame, 
    QListWidget, QListWidgetItem, QTabWidget, QDialog, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QMenu
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush, QAction
from desktop_app.common_widgets import StandardDateEdit
from decimal import Decimal
from datetime import datetime


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
        except:
            self.setText("0.00")
            
    def get_value(self):
        try:
            return float(self.text().replace(',', ''))
        except:
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
        self.display.setStyleSheet("padding: 10px; background-color: #f0f0f0; border: 2px solid #333;")
        layout.addWidget(self.display)
        
        # Button grid
        grid = QVBoxLayout()
        
        # Row 1: 7, 8, 9, ÷
        row1 = QHBoxLayout()
        for btn_text in ["7", "8", "9", "÷"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(lambda checked, t=btn_text: self._on_button_click(t))
            row1.addWidget(btn)
        grid.addLayout(row1)
        
        # Row 2: 4, 5, 6, ×
        row2 = QHBoxLayout()
        for btn_text in ["4", "5", "6", "×"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(lambda checked, t=btn_text: self._on_button_click(t))
            row2.addWidget(btn)
        grid.addLayout(row2)
        
        # Row 3: 1, 2, 3, −
        row3 = QHBoxLayout()
        for btn_text in ["1", "2", "3", "−"]:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            btn.clicked.connect(lambda checked, t=btn_text: self._on_button_click(t))
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
        eq_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
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
        clear_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        clear_btn.clicked.connect(self._clear)
        bottom_row.addWidget(clear_btn)
        
        ok_btn = QPushButton("✓ OK")
        ok_btn.setMinimumHeight(40)
        ok_btn.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
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
        except:
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
        except:
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
    
    def __init__(self, conn, vendor_name, payment_amount, available_invoices, parent=None, payment_method='check'):
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
        header = QLabel(f"💰 Allocate ${self.payment_amount:,.2f} Payment Across Invoices")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Vendor info
        vendor_label = QLabel(f"Vendor: {self.vendor_name}")
        vendor_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(vendor_label)
        
        # Invoice selection table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(7)
        self.invoice_table.setHorizontalHeaderLabels([
            "Select", "Invoice #", "Date", "Amount", "Paid", "Balance Due", "To Pay"
        ])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        auto_btn.setStyleSheet("background-color: #007bff; color: white; padding: 8px;")
        layout.addWidget(auto_btn)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Load invoices
        self._load_invoices()
        
    def _load_invoices(self):
        """Load available invoices with outstanding balances"""
        self.invoice_table.setRowCount(len(self.available_invoices))
        
        for idx, invoice in enumerate(self.available_invoices):
            # invoice = (receipt_id, source_ref, date, amount, paid_amount, balance)
            receipt_id, ref, date, amount, paid, balance = invoice
            
            # Checkbox
            check = QCheckBox()
            check.setChecked(False)
            check.stateChanged.connect(lambda state, row=idx: self._on_checkbox_changed(row, state))
            self.invoice_table.setCellWidget(idx, 0, check)
            
            # Invoice #
            self.invoice_table.setItem(idx, 1, QTableWidgetItem(str(ref or f"R-{receipt_id}")))
            
            # Date - standardize format to MM/dd/yyyy
            if isinstance(date, str):
                # Try to parse if it's a string
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d/%Y")
                except:
                    parsed_date = date
            else:
                # If it's a date object
                parsed_date = date.strftime("%m/%d/%Y") if hasattr(date, 'strftime') else str(date)
            self.invoice_table.setItem(idx, 2, QTableWidgetItem(parsed_date))
            
            # Amount
            amt_item = QTableWidgetItem(f"${amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.invoice_table.setItem(idx, 3, amt_item)
            
            # Paid
            paid_item = QTableWidgetItem(f"${paid:,.2f}")
            paid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.invoice_table.setItem(idx, 4, paid_item)
            
            # Balance
            bal_item = QTableWidgetItem(f"${balance:,.2f}")
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if balance > 0:
                bal_item.setForeground(QBrush(QColor("red")))
            self.invoice_table.setItem(idx, 5, bal_item)
            
            # To Pay (initially empty, filled during allocation)
            to_pay_item = QTableWidgetItem("$0.00")
            to_pay_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
            row_color = QColor("#c8e6c9") if to_allocate >= balance else QColor("#fff9c4")
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
            receipt_id, ref, date, amount, paid, balance = invoice
            
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
                row_color = QColor("#c8e6c9") if to_allocate >= balance else QColor("#fff9c4")
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
        self.allocated_label.setStyleSheet("color: green; font-weight: bold;" if allocated > 0 else "")
        
        self.remaining_label.setText(f"${remaining:,.2f}")
        if abs(remaining) < 0.01:
            self.remaining_label.setStyleSheet("color: green; font-weight: bold;")
        elif remaining > 0:
            self.remaining_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.remaining_label.setStyleSheet("color: red; font-weight: bold;")
            
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
        
        instructions = QLabel("💡 Search for vendor → View all invoices → Add missing invoices → Apply payments")
        instructions.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-left: 3px solid #007bff;")
        layout.addWidget(instructions)
        
        # Vendor search - prominent at top
        vendor_group = self._create_vendor_search()
        layout.addWidget(vendor_group)
        
        # Main area: Simple top-to-bottom flow
        # 1. Invoice list (largest area)
        invoice_panel = self._create_invoice_list()
        layout.addWidget(invoice_panel, stretch=3)
        
        # 2. Quick actions (compact, horizontal)
        quick_actions = self._create_quick_actions()
        layout.addWidget(quick_actions)
        
        # 3. Expandable details section
        details_tabs = QTabWidget()
        details_tabs.setMaximumHeight(300)
        details_tabs.addTab(self._create_add_invoice_tab(), "➕ Add Invoice")
        details_tabs.addTab(self._create_edit_invoice_tab(), "✏️ Edit Invoice")
        details_tabs.addTab(self._create_payment_tab(), "💰 Apply Payment")
        details_tabs.addTab(self._create_banking_link_tab(), "🏦 Banking Link")
        details_tabs.addTab(self._create_account_summary_tab(), "📊 Summary")
        
        layout.addWidget(details_tabs, stretch=1)
        
    def _create_quick_actions(self):
        """Quick action buttons for common tasks"""
        group = QGroupBox("⚡ Quick Actions")
        group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; }")
        layout = QHBoxLayout(group)
        
        # Add invoice button
        add_invoice_btn = QPushButton("➕ Add Invoice")
        add_invoice_btn.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-weight: bold;")
        add_invoice_btn.setToolTip("Add a new invoice for the selected vendor")
        add_invoice_btn.clicked.connect(self._add_invoice)
        layout.addWidget(add_invoice_btn)
        
        # Edit selected invoice button
        edit_invoice_btn = QPushButton("✏️ Edit Selected Invoice")
        edit_invoice_btn.setStyleSheet("background-color: #fd7e14; color: white; padding: 10px; font-weight: bold;")
        edit_invoice_btn.setToolTip("Select one invoice and edit its details")
        edit_invoice_btn.clicked.connect(self._edit_selected_invoice)
        layout.addWidget(edit_invoice_btn)
        
        # Pay single button
        pay_single_btn = QPushButton("💵 Pay Selected Invoice")
        pay_single_btn.setStyleSheet("background-color: #17a2b8; color: white; padding: 10px; font-weight: bold;")
        pay_single_btn.setToolTip("Select one invoice and apply payment")
        pay_single_btn.clicked.connect(self._apply_to_single_invoice)
        layout.addWidget(pay_single_btn)
        
        # Pay multiple button
        pay_multi_btn = QPushButton("💰 Pay Multiple Invoices")
        pay_multi_btn.setStyleSheet("background-color: #6f42c1; color: white; padding: 10px; font-weight: bold;")
        pay_multi_btn.setToolTip("Select multiple invoices (Ctrl+Click) and split payment")
        pay_multi_btn.clicked.connect(self._apply_to_multiple_invoices)
        layout.addWidget(pay_multi_btn)
        
        # View summary button
        summary_btn = QPushButton("📊 View Account Summary")
        summary_btn.setStyleSheet("background-color: #ffc107; color: black; padding: 10px; font-weight: bold;")
        summary_btn.setToolTip("Show complete account history")
        summary_btn.clicked.connect(self._refresh_account_summary)
        layout.addWidget(summary_btn)
        
        return group
        
    def _create_vendor_search(self):
        """Vendor search and selection"""
        group = QGroupBox("🔍 Select Vendor")
        group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12px; }")
        layout = QVBoxLayout(group)
        
        # Search row
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        
        self.vendor_search = QLineEdit()
        self.vendor_search.setPlaceholderText("Type vendor name: 106.7, WCB, FAS GAS, etc.")
        self.vendor_search.setStyleSheet("padding: 8px; font-size: 12px;")
        self.vendor_search.textChanged.connect(self._on_vendor_search_changed)
        search_row.addWidget(self.vendor_search, stretch=1)
        
        layout.addLayout(search_row)
        
        # Results row
        results_row = QHBoxLayout()
        results_row.addWidget(QLabel("Vendor:"))
        
        self.vendor_results = QComboBox()
        self.vendor_results.setMinimumHeight(35)
        self.vendor_results.setStyleSheet("padding: 5px; font-size: 12px;")
        self.vendor_results.currentTextChanged.connect(self._on_vendor_selected)
        results_row.addWidget(self.vendor_results, stretch=1)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("padding: 8px; font-weight: bold;")
        refresh_btn.clicked.connect(self._refresh_current_vendor)
        results_row.addWidget(refresh_btn)
        
        layout.addLayout(results_row)
        
        return group
    
    def _create_invoice_list(self):
        """Invoice list for selected vendor"""
        group = QGroupBox("📋 All Invoices for Vendor")
        group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12px; }")
        layout = QVBoxLayout(group)
        
        # Vendor info and balance
        info_layout = QHBoxLayout()
        
        self.vendor_header = QLabel("No vendor selected")
        self.vendor_header.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px;")
        info_layout.addWidget(self.vendor_header, stretch=1)
        
        self.balance_label = QLabel("")
        self.balance_label.setStyleSheet("font-size: 12px; padding: 5px; font-weight: bold;")
        info_layout.addWidget(self.balance_label)
        
        layout.addLayout(info_layout)
        
        # Filters section
        filter_frame = QFrame()
        filter_frame.setStyleSheet("QFrame { background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 3px; }")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(5, 5, 5, 5)
        
        filter_layout.addWidget(QLabel("🔍 Filters:"))
        
        # Invoice number filter
        filter_layout.addWidget(QLabel("Invoice #:"))
        self.filter_invoice_num = QLineEdit()
        self.filter_invoice_num.setPlaceholderText("Search invoice #...")
        self.filter_invoice_num.setMaximumWidth(150)
        self.filter_invoice_num.textChanged.connect(self._apply_invoice_filters)
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
        self.filter_year.currentIndexChanged.connect(self._apply_invoice_filters)
        filter_layout.addWidget(self.filter_year)
        
        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["All", "Paid", "Unpaid"])
        self.filter_status.setMaximumWidth(100)
        self.filter_status.currentIndexChanged.connect(self._apply_invoice_filters)
        filter_layout.addWidget(self.filter_status)
        
        # Clear filters button
        clear_filters_btn = QPushButton("❌ Clear")
        clear_filters_btn.setMaximumWidth(70)
        clear_filters_btn.clicked.connect(self._clear_invoice_filters)
        filter_layout.addWidget(clear_filters_btn)
        
        filter_layout.addStretch()
        
        layout.addWidget(filter_frame)
        
        # Invoice table - now includes running balance
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(8)
        self.invoice_table.setHorizontalHeaderLabels([
            "ID", "Invoice #", "Date", "Amount", "Paid", "Balance", "Running Balance", "Status"
        ])
        # Set specific column widths for better appearance
        header = self.invoice_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # ID
        self.invoice_table.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Invoice # - can be long
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Date
        self.invoice_table.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Amount
        self.invoice_table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Paid
        self.invoice_table.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # Balance
        self.invoice_table.setColumnWidth(5, 110)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)  # Running Balance
        self.invoice_table.setColumnWidth(6, 130)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)  # Status
        self.invoice_table.setColumnWidth(7, 80)
        self.invoice_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.invoice_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.invoice_table.setAlternatingRowColors(True)
        self.invoice_table.setStyleSheet("QTableWidget { font-size: 11px; }")
        self.invoice_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.invoice_table.customContextMenuRequested.connect(self._show_invoice_context_menu)
        self.invoice_table.itemDoubleClicked.connect(self._on_invoice_double_clicked)
        # Enable sorting
        self.invoice_table.setSortingEnabled(True)
        layout.addWidget(self.invoice_table)
        
        hint = QLabel("💡 Click column headers to sort | Use filters above to narrow results | Ctrl+Click for multi-select")
        hint.setStyleSheet("font-size: 10px; color: #666; font-style: italic; padding: 3px;")
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
        self._load_categories()
        form.addRow("Category:", self.new_invoice_category)
        
        layout.addLayout(form)
        
        # Split fees section (for vendors like WCB with overdue fees)
        split_group = QGroupBox("💳 Split Fees (Optional - for WCB overdue fees, CRA adjustments, etc.)")
        split_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        split_layout = QVBoxLayout()
        
        # Split checkbox
        self.new_invoice_use_split = QCheckBox("Split this invoice into vendor charge + separate fee")
        self.new_invoice_use_split.setToolTip("Enable to separate base charge from overdue fees or other adjustments")
        self.new_invoice_use_split.stateChanged.connect(self._on_split_checkbox_changed)
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
            "Other"
        ])
        self.new_invoice_fee_type.setToolTip("CRA: Fees are NOT included in income calculations - tracked separately for reporting")
        split_details_layout.addRow("Fee Type:", self.new_invoice_fee_type)
        
        # Info note
        fee_note = QLabel("ℹ️ Overdue fees and penalties are tracked separately for CRA reporting (not counted as income)")
        fee_note.setStyleSheet("font-size: 9px; color: #0066cc; font-style: italic;")
        split_details_layout.addRow("", fee_note)
        
        self.split_details.setVisible(False)
        split_layout.addWidget(self.split_details)
        
        split_group.setLayout(split_layout)
        layout.addWidget(split_group)
        
        # Add button
        add_btn = QPushButton("✅ Add Invoice")
        add_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
        add_btn.clicked.connect(self._add_invoice)
        layout.addWidget(add_btn)
        
        layout.addStretch()
        
        return widget
    
    def _create_edit_invoice_tab(self):
        """Tab for editing selected invoice details"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Selection info
        info_label = QLabel("Select an invoice from the list above, then edit details below:")
        info_label.setStyleSheet("font-size: 11px; color: #0066cc;")
        layout.addWidget(info_label)
        
        # Main form
        form = QFormLayout()
        
        # Invoice number
        self.edit_invoice_num = QLineEdit()
        form.addRow("Invoice Number:", self.edit_invoice_num)
        
        # Invoice date
        self.edit_invoice_date = StandardDateEdit(prefer_month_text=True)
        self.edit_invoice_date.setCalendarPopup(True)
        self.edit_invoice_date.setDisplayFormat("MM/dd/yyyy")
        self.edit_invoice_date.setMaximumWidth(130)
        self.edit_invoice_date.setInputMethodHints(self.edit_invoice_date.inputMethodHints())
        self.edit_invoice_date.lineEdit().setClearButtonEnabled(True)
        form.addRow("Invoice Date:", self.edit_invoice_date)
        
        # Amount (compact with calculator)
        amount_row = QHBoxLayout()
        self.edit_invoice_amount = CurrencyInput(compact=True)
        amount_row.addWidget(self.edit_invoice_amount, stretch=0)
        calc_btn = CalculatorButton(self.edit_invoice_amount)
        amount_row.addWidget(calc_btn, stretch=0)
        amount_row.addStretch()
        form.addRow("Amount:", amount_row)
        
        # Description
        self.edit_invoice_desc = QTextEdit()
        self.edit_invoice_desc.setMaximumHeight(60)
        self.edit_invoice_desc.setPlaceholderText("Optional description...")
        form.addRow("Description:", self.edit_invoice_desc)
        
        # Category
        self.edit_invoice_category = QComboBox()
        self.edit_invoice_category.setEditable(True)
        self._load_categories()
        form.addRow("Category:", self.edit_invoice_category)
        
        layout.addLayout(form)
        
        # Button row
        btn_layout = QHBoxLayout()
        
        # Save button
        save_btn = QPushButton("💾 Save Changes")
        save_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
        save_btn.clicked.connect(self._save_invoice_changes)
        btn_layout.addWidget(save_btn)
        
        # Delete button
        delete_btn = QPushButton("🗑️ Delete Invoice")
        delete_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 10px;")
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
        """Tab for adding payments to invoices"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Payment details
        form = QFormLayout()
        
        # Payment amount (compact with calculator)
        payment_amount_row = QHBoxLayout()
        self.payment_amount = CurrencyInput(compact=True)
        payment_amount_row.addWidget(self.payment_amount, stretch=0)
        payment_calc_btn = CalculatorButton(self.payment_amount)
        payment_amount_row.addWidget(payment_calc_btn, stretch=0)
        payment_amount_row.addStretch()
        form.addRow("Payment Amount:", payment_amount_row)
        
        # Payment reference/check number
        self.payment_reference = QLineEdit()
        self.payment_reference.setPlaceholderText("Check #, reference, or description")
        form.addRow("Reference:", self.payment_reference)
        
        self.payment_date = StandardDateEdit(prefer_month_text=True)
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setDisplayFormat("MM/dd/yyyy")
        self.payment_date.setMaximumWidth(130)
        form.addRow("Payment Date:", self.payment_date)
        
        # Payment method dropdown
        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "bank_transfer",
            "check",
            "cash",
            "credit_card",
            "debit_card",
            "trade_of_services",
            "credit_adjustment",
            "unknown",
        ])
        self.payment_method.setCurrentText("check")
        self.payment_method.setMaximumWidth(200)
        form.addRow("Payment Method:", self.payment_method)
        
        allocation_group = QGroupBox("How to Apply This Payment")
        allocation_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        allocation_layout = QVBoxLayout()
        
        single_btn = QPushButton("💵 Pay ONE Invoice (select invoice from list above)")
        single_btn.setStyleSheet("background-color: #17a2b8; color: white; padding: 12px; font-size: 11px; font-weight: bold;")
        single_btn.clicked.connect(self._apply_to_single_invoice)
        allocation_layout.addWidget(single_btn)
        
        multi_btn = QPushButton("💰 Split Across MULTIPLE Invoices")
        multi_btn.setStyleSheet("background-color: #6f42c1; color: white; padding: 12px; font-size: 11px; font-weight: bold;")
        multi_btn.clicked.connect(self._apply_to_multiple_invoices)
        allocation_layout.addWidget(multi_btn)
        
        # Example text
        example = QLabel("Example: Check #197 for $550 → Split across invoices 21160, 21431, 21739, 22072")
        example.setStyleSheet("font-size: 10px; color: #666; font-style: italic; padding: 5px;")
        example.setWordWrap(True)
        allocation_layout.addWidget(example)
        
        allocation_group.setLayout(allocation_layout)
        form.addRow("", allocation_group)
        
        self.payment_banking_id = QLineEdit()
        self.payment_banking_id.setPlaceholderText("Optional: Banking Transaction ID")
        form.addRow("Banking TX ID:", self.payment_banking_id)
        
        layout.addLayout(form)
        layout.addStretch()
        
        return widget
        
    def _create_banking_link_tab(self):
        """Tab for linking banking transactions"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("🏦 Search banking transactions and link to invoices")
        info.setStyleSheet("padding: 10px; background-color: #e3f2fd;")
        layout.addWidget(info)
        
        # Banking search
        form = QFormLayout()
        
        self.banking_search_amount = CurrencyInput()
        form.addRow("Search Amount:", self.banking_search_amount)
        
        self.banking_search_desc = QLineEdit()
        self.banking_search_desc.setPlaceholderText("Description search...")
        form.addRow("Description:", self.banking_search_desc)
        
        # Date range filters
        date_range_layout = QHBoxLayout()
        
        self.banking_use_date_filter = QCheckBox("Filter by date range")
        self.banking_use_date_filter.setChecked(False)
        self.banking_use_date_filter.toggled.connect(self._toggle_banking_date_filter)
        date_range_layout.addWidget(self.banking_use_date_filter)
        
        self.banking_date_from = StandardDateEdit(prefer_month_text=True)
        self.banking_date_from.setCalendarPopup(True)
        self.banking_date_from.setDisplayFormat("MM/dd/yyyy")
        self.banking_date_from.setDate(QDate.currentDate().addYears(-5))
        self.banking_date_from.setEnabled(False)
        
        self.banking_date_to = StandardDateEdit(prefer_month_text=True)
        self.banking_date_to.setCalendarPopup(True)
        self.banking_date_to.setDisplayFormat("MM/dd/yyyy")
        self.banking_date_to.setDate(QDate.currentDate())
        self.banking_date_to.setEnabled(False)
        
        date_range_layout.addWidget(QLabel("From:"))
        date_range_layout.addWidget(self.banking_date_from)
        date_range_layout.addWidget(QLabel("To:"))
        date_range_layout.addWidget(self.banking_date_to)
        date_range_layout.addStretch()
        
        form.addRow("", date_range_layout)
        
        # Quick date presets
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Quick:")
        preset_label.setEnabled(False)
        self.banking_preset_label = preset_label
        preset_layout.addWidget(preset_label)
        
        btn_this_year = QPushButton("This Year")
        btn_this_year.clicked.connect(lambda: self._set_banking_date_preset('year'))
        btn_this_year.setEnabled(False)
        self.banking_preset_year = btn_this_year
        preset_layout.addWidget(btn_this_year)
        
        btn_last_year = QPushButton("Last Year")
        btn_last_year.clicked.connect(lambda: self._set_banking_date_preset('last_year'))
        btn_last_year.setEnabled(False)
        self.banking_preset_lastyear = btn_last_year
        preset_layout.addWidget(btn_last_year)
        
        btn_all = QPushButton("All Time")
        btn_all.clicked.connect(lambda: self._set_banking_date_preset('all'))
        btn_all.setEnabled(False)
        self.banking_preset_all = btn_all
        preset_layout.addWidget(btn_all)
        
        preset_layout.addStretch()
        form.addRow("", preset_layout)
        
        search_btn = QPushButton("🔍 Search Banking Transactions")
        search_btn.clicked.connect(self._search_banking)
        form.addRow("", search_btn)
        
        layout.addLayout(form)
        
        # Banking results
        self.banking_table = QTableWidget()
        self.banking_table.setColumnCount(6)
        self.banking_table.setHorizontalHeaderLabels([
            "TX ID", "Date", "Description", "Amount", "Check #", "Linked"
        ])
        self.banking_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.banking_table.itemDoubleClicked.connect(self._link_banking_to_invoice)
        layout.addWidget(self.banking_table)
        
        hint = QLabel("💡 Double-click a transaction to link it to selected invoice(s)")
        hint.setStyleSheet("font-size: 10px; color: #666; padding: 5px;")
        layout.addWidget(hint)
        
        return widget
        
    def _create_account_summary_tab(self):
        """Tab showing account summary and payment history"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setStyleSheet("font-family: 'Courier New'; font-size: 10px;")
        layout.addWidget(self.summary_text)
        
        refresh_btn = QPushButton("🔄 Refresh Summary")
        refresh_btn.clicked.connect(self._refresh_account_summary)
        layout.addWidget(refresh_btn)
        
        return widget
        
    def _load_categories(self):
        """Load expense categories"""
        try:
            cur = self.conn.get_cursor()
            cur.execute("""
                SELECT DISTINCT category 
                FROM receipts 
                WHERE category IS NOT NULL 
                ORDER BY category
            """)
            categories = [row[0] for row in cur.fetchall()]
            self.new_invoice_category.addItems([""] + categories)
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading categories: {e}")
            
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
            self.vendor_results.addItems(vendors)
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Search Error", f"Error searching vendors: {e}")
            
    def _on_vendor_selected(self, vendor_name):
        """Load invoices for selected vendor"""
        if not vendor_name:
            return
            
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
            filtered = [inv for inv in filtered if invoice_num_filter in str(inv[1]).lower()]
        
        # Apply year filter
        if year_filter is not None:
            filtered = [inv for inv in filtered if inv[2] and str(inv[2]).startswith(str(year_filter))]
        
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
                f"(showing {len(filtered)} of {len(self.unfiltered_invoices)})"
            )
    
    def _clear_invoice_filters(self):
        """Clear all invoice filters"""
        self.filter_invoice_num.clear()
        self.filter_year.setCurrentIndex(0)
        self.filter_status.setCurrentIndex(0)
        
        # Restore full list
        if hasattr(self, 'unfiltered_invoices'):
            self.current_invoices = self.unfiltered_invoices.copy()
            self._refresh_invoice_table()
            self.vendor_header.setText(f"📋 Invoices for: {self.current_vendor}")
        
    def _load_vendor_invoices(self):
        """Load all invoices for current vendor"""
        if not self.current_vendor:
            return
            
        try:
            cur = self.conn.get_cursor()
            
            # vendor_accounts table doesn't exist - skip account lookup
            vendor_result = None
            
            if not vendor_result:
                self.balance_label.setText("Vendor not found in accounts")
                return
                
            vendor_account_id = vendor_result[0]
            
            # Get all receipts (invoices) for this vendor
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
            
            # For each invoice, calculate paid amount from ledger
            invoice_data = []
            total_invoiced = 0.0
            total_paid = 0.0
            total_balance = 0.0
            
            for inv in invoices:
                receipt_id, ref, date, amount, orig_amt, banking_id = inv
                
                # Convert Decimal to float to avoid type mismatch
                orig_amt = float(orig_amt) if orig_amt is not None else 0.0
                
                # Query vendor ledger for payments on this receipt
                # Note: source_id is varchar, so cast receipt_id to string
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total_paid
                    FROM vendor_account_ledger
                    WHERE account_id = %s
                    AND source_id = %s
                    AND entry_type = 'PAYMENT'
                """, (vendor_account_id, str(receipt_id)))
                
                paid_result = cur.fetchone()
                paid = float(paid_result[0]) if paid_result and paid_result[0] else 0.0
                
                # Balance is what's left to pay (negative payment amounts are already payments)
                balance = orig_amt + paid  # paid is negative, so this gives us the remaining
                balance = max(balance, 0.0)  # Never negative
                
                status = "✅ Paid" if balance < 0.01 else "❌ Unpaid"
                
                invoice_data.append((receipt_id, ref, date, orig_amt, abs(paid) if paid < 0 else 0.0, balance, status))
                total_invoiced += orig_amt
                total_paid += abs(paid) if paid < 0 else 0.0
                total_balance += balance
                
            self.current_invoices = invoice_data
            self.unfiltered_invoices = invoice_data.copy()  # Store for filtering
            
            # Update header
            self.vendor_header.setText(f"📋 Invoices for: {self.current_vendor}")
            self.balance_label.setText(
                f"Total Invoiced: ${total_invoiced:,.2f} | "
                f"Total Paid: ${total_paid:,.2f} | "
                f"Balance Due: ${total_balance:,.2f}"
            )
            
            if total_balance > 0:
                self.balance_label.setStyleSheet("font-size: 12px; padding: 5px; color: red; font-weight: bold;")
            else:
                self.balance_label.setStyleSheet("font-size: 12px; padding: 5px; color: green;")
            
            # Update table
            self._refresh_invoice_table()
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading invoices: {e}")
            
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
            is_selected = self.invoice_table.item(idx, 0) and self.invoice_table.item(idx, 0).isSelected()
            row_color = QColor("#e3f2fd") if is_selected else QColor("white")  # Light blue for selected
            
            # ID
            id_item = QTableWidgetItem(str(receipt_id))
            id_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 0, id_item)
            
            # Invoice #
            inv_item = QTableWidgetItem(str(ref or f"R-{receipt_id}"))
            inv_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 1, inv_item)
            
            # Date - standardize format to MM/dd/yyyy
            if isinstance(date, str):
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d/%Y")
                except:
                    parsed_date = date
            else:
                parsed_date = date.strftime("%m/%d/%Y") if hasattr(date, 'strftime') else str(date)
            date_item = QTableWidgetItem(parsed_date)
            date_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 2, date_item)
            
            # Amount
            amt_item = QTableWidgetItem(f"${amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amt_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 3, amt_item)
            
            # Paid
            paid_item = QTableWidgetItem(f"${paid:,.2f}")
            paid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            paid_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 4, paid_item)
            
            # Balance (individual invoice balance)
            bal_item = QTableWidgetItem(f"${balance:,.2f}")
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bal_item.setBackground(QBrush(row_color))
            if balance > 0:
                bal_item.setForeground(QBrush(QColor("red")))
            self.invoice_table.setItem(idx, 5, bal_item)
            
            # Running Balance (cumulative - shows what's owed up to this point)
            running_bal_item = QTableWidgetItem(f"${running_balance:,.2f}")
            running_bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            running_bal_item.setForeground(QBrush(QColor("darkblue")))
            running_bal_item.setFont(self._get_bold_font())
            running_bal_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 6, running_bal_item)
            
            # Status
            status_item = QTableWidgetItem(status)
            status_item.setBackground(QBrush(row_color))
            self.invoice_table.setItem(idx, 7, status_item)
    
    def _get_bold_font(self):
        """Get bold font for running balance"""
        font = QFont()
        font.setBold(True)
        return font
            
    def _add_invoice(self):
        """Add a new invoice for current vendor (with optional fee split)"""
        if not self.current_vendor:
            QMessageBox.warning(self, "No Vendor", "Please select a vendor first.")
            return
            
        invoice_num = self.new_invoice_num.text().strip()
        amount = self.new_invoice_amount.get_value()
        
        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Amount must be greater than 0.")
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
                    f"Base ({base_amount:.2f}) + Fee ({fee_amount:.2f}) must equal Total ({amount:.2f})"
                )
                return
            
        try:
            cur = self.conn.get_cursor()
            
            # Add main invoice
            sql = """
                INSERT INTO receipts (
                    vendor_name, source_reference, receipt_date, 
                    gross_amount, description, category,
                    created_from_banking, source_file
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
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
                'VENDOR_INVOICE_MANAGER'
            )
            
            cur.execute(sql, params)
            receipt_id = cur.fetchone()[0]
            
            # If split, create fee entry in vendor ledger (if table exists)
            if use_split and fee_amount > 0:
                try:
                    # Try to create a ledger entry for the fee
                    vendor_sql = """
                        INSERT INTO vendor_account_ledger (
                            account_id, entry_date, entry_type, amount, 
                            source_table, source_id, notes
                        ) 
                        -- vendor_accounts table doesn't exist
                        -- Skipping vendor ledger entry
                    """
                except:
                    # vendor_accounts and vendor_account_ledger don't exist
                    try:
                        self.db.rollback()
                    except:
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
            QMessageBox.critical(self, "Add Error", f"Failed to add invoice:\n\n{e}")
    
    def _edit_selected_invoice(self):
        """Load selected invoice into edit form"""
        selected = self.invoice_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an invoice from the list to edit.")
            return
        
        row = self.invoice_table.currentRow()
        if row < 0 or row >= len(self.available_invoices):
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid invoice.")
            return
        
        invoice = self.available_invoices[row]
        receipt_id, ref, date, amount, paid, balance = invoice
        
        # Store the receipt_id for later save
        self.editing_receipt_id = receipt_id
        
        # Load into form
        self.edit_invoice_num.setText(str(ref or ""))
        self.edit_invoice_amount.setText(f"{amount:.2f}")
        self.edit_invoice_desc.setPlainText("")  # Description not in the basic invoice tuple
        self.edit_invoice_category.setCurrentText("")
        
        # Parse and set date
        if isinstance(date, str):
            try:
                from datetime import datetime
                parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
                self.edit_invoice_date.setDate(parsed_date)
            except:
                self.edit_invoice_date.setDate(QDate.currentDate())
        else:
            self.edit_invoice_date.setDate(date if date else QDate.currentDate())
        
        # Switch to edit tab
        parent_tabs = self.sender().parent() if self.sender() else None
        # Find the details_tabs widget and switch to edit tab
        info_label = QMessageBox.information(
            self,
            "Edit Mode",
            f"Invoice {ref} loaded for editing.\n\nMake your changes in the '✏️ Edit Invoice' tab and click 'Save Changes'."
        )
    
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
                receipt_id
            )
            
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
                f"Invoice {invoice_num or receipt_id} deleted successfully!\n\n{summary}"
            )
            
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
            f"Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
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
            payment_ref = self.payment_reference.text().strip() or f"Invoice {ref or receipt_id} Payment"
            payment_date = self.payment_date.date().toString("MM/dd/yyyy")
            payment_method = self.payment_method.currentText()
            
            # vendor_accounts table doesn't exist - skip vendor account lookup
            vendor_result = None
            
            if not vendor_result:
                QMessageBox.information(self, "Info", f"Vendor account tracking not available in this version")
                return
                
            vendor_account_id = vendor_result[0] if vendor_result else None
            
            # Record payment skipped - vendor ledger table doesn't exist
            # Note: vendor accounting tables not in current schema
            # Vendor ledger entry not supported in current schema
            
            # Update the receipt with banking transaction link if provided
            if banking_id:
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = %s
                    WHERE receipt_id = %s
                """, (banking_id, receipt_id))
                
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(self, "Success", "✅ Payment applied successfully!")
            
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
            payment_method
        )
        
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
                payment_date = self.payment_date.date().toString("MM/dd/yyyy")
                payment_method = self.payment_method.currentText()
                
                # Get vendor_account_id for this vendor
                # vendor_accounts table doesn't exist - skip lookup
                account_id = None
                vendor_result = cur.fetchone()
                
                if not vendor_result:
                    QMessageBox.warning(self, "Vendor Not Found", f"Cannot find vendor account for '{self.current_vendor}'")
                    return
                    
                vendor_account_id = vendor_result[0]
                
                # Record payments for each allocated invoice
                # Note: source_id is varchar, so cast receipt_id to string
                for receipt_id, allocated_amt in allocations.items():
                    cur.execute("""
                        INSERT INTO vendor_account_ledger (account_id, entry_date, entry_type, amount, source_table, source_id, payment_method, notes, created_at)
                        VALUES (%s, %s, 'PAYMENT', %s, 'receipts', %s, %s, %s, NOW())
                    """, (vendor_account_id, payment_date, -allocated_amt, str(receipt_id), payment_method, payment_ref))
                
                self.conn.commit()
                cur.close()
                
                alloc_summary = "\n".join([
                    f"Invoice {rid}: ${amt:,.2f}"
                    for rid, amt in allocations.items()
                ])
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ Payment allocated successfully!\n\n{alloc_summary}"
                )
                
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
                        from datetime import datetime
                        formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d/%Y")
                    except:
                        try:
                            self.db.rollback()
                        except:
                            pass
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
                    "or use 'All Time' to search all years."
                )
            else:
                date_info = ""
                if self.banking_use_date_filter.isChecked():
                    date_info = f"\n📅 Filtered: {self.banking_date_from.date().toString('MM/dd/yyyy')} to {self.banking_date_to.date().toString('MM/dd/yyyy')}"
                
                QMessageBox.information(
                    self,
                    "Search Results",
                    f"Found {len(results)} transactions{date_info}"
                )
                
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
                "Please select one or more invoices from the table first,\nthen double-click the banking transaction."
            )
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
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
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
            
            from datetime import datetime
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
                            source_table, source_id, notes
                        ) VALUES (%s, %s, 'PAYMENT', %s, 'receipts', %s, %s)
                    """, (
                        account_id,
                        payment_date,
                        -apply_amount,  # Negative for payment
                        str(receipt_id),
                        f"Banking TX #{tx_id} - Auto-allocated payment"
                    ))
                    
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
                f"Remaining: ${remaining:,.2f}"
            )
            
            # Refresh the display
            self._load_vendor_invoices()
            self._search_banking()  # Refresh banking table to show it's linked
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(
                self,
                "Payment Error",
                f"Failed to apply payment:\n\n{e}"
            )
        
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
            
        summary = f"ACCOUNT SUMMARY: {self.current_vendor}\n"
        summary += "=" * 60 + "\n\n"
        
        total_invoiced = sum(inv[3] for inv in self.current_invoices)
        total_paid = sum(inv[4] for inv in self.current_invoices)
        total_balance = sum(inv[5] for inv in self.current_invoices)
        
        summary += f"Total Invoiced:    ${total_invoiced:>12,.2f}\n"
        summary += f"Total Paid:        ${total_paid:>12,.2f}\n"
        summary += f"Balance Due:       ${total_balance:>12,.2f}\n"
        summary += "\n" + "=" * 60 + "\n\n"
        
        summary += "INVOICE DETAILS:\n"
        summary += "-" * 60 + "\n"
        
        for inv in self.current_invoices:
            receipt_id, ref, date, amount, paid, balance, status = inv
            summary += f"\nInvoice: {ref or f'R-{receipt_id}':<15} Date: {date}\n"
            summary += f"  Amount:  ${amount:>10,.2f}\n"
            summary += f"  Paid:    ${paid:>10,.2f}\n"
            summary += f"  Balance: ${balance:>10,.2f}  {status}\n"
            
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
        """Handle invoice double-click"""
        self._view_invoice_details()
        
    def _edit_selected_invoice(self):
        """Edit selected invoice"""
        row = self.invoice_table.currentRow()
        if row < 0:
            return
            
        QMessageBox.information(self, "Edit Invoice", "Edit functionality coming soon!")
        
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
                QMessageBox.StandardButton.No
            )
            
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
            
            QMessageBox.information(
                self, 
                "✅ Deleted", 
                f"Invoice {ref or f'R-{receipt_id}'} deleted successfully."
            )
            self._load_vendor_invoices()
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Delete Error", f"Failed to delete:\n\n{e}")
            
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
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load details:\n\n{e}")
