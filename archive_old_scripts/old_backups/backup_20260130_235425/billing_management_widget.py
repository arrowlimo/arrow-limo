"""
Billing Management Widget for Charter Operations
Features:
- NRP (Non-Refundable Deposit) tracking
- Refundable deposit management  
- Payment completion and tracking
- Invoice printing (separate from beverage)
- Multi-invoice management for linked charters
- Split payments across multiple charters
- Corporate payment search and linking
- Banking transaction search
- Square payment lookup integration
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QDateEdit,
    QTextEdit, QCheckBox, QSpinBox, QMessageBox, QTabWidget, QHeaderView,
    QFormLayout, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from decimal import Decimal
import psycopg2
from datetime import datetime


class CurrencyInput(QLineEdit):
    """Currency input field with validation"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("$0.00")
        self.setMaximumWidth(120)
        self.textChanged.connect(self._format_currency)
    
    def _format_currency(self, text):
        # Remove non-numeric characters except decimal
        cleaned = ''.join(c for c in text if c.isdigit() or c == '.')
        if cleaned and cleaned != self.text():
            self.setText(cleaned)
    
    def get_value(self) -> Decimal:
        """Get decimal value"""
        try:
            return Decimal(self.text() or "0")
        except:
            return Decimal("0")
    
    def set_value(self, value: Decimal):
        """Set decimal value"""
        self.setText(f"{value:.2f}")


class BillingManagementWidget(QWidget):
    """Comprehensive billing management for charters"""
    
    payment_added = pyqtSignal(str, Decimal)  # reserve_number, amount
    invoice_printed = pyqtSignal(str)  # reserve_number
    
    def __init__(self, db_connection, parent_charter_widget=None):
        super().__init__()
        self.db = db_connection
        self.parent_charter = parent_charter_widget
        self.current_reserve_number = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the billing management UI"""
        layout = QVBoxLayout()
        
        # === HEADER: CHARTER SELECTION ===
        header_group = QGroupBox("Charter Selection")
        header_layout = QHBoxLayout()
        
        header_layout.addWidget(QLabel("<b>Reserve Number:</b>"))
        self.reserve_input = QLineEdit()
        self.reserve_input.setPlaceholderText("Enter reserve number (e.g., 019233)")
        self.reserve_input.setMaximumWidth(150)
        self.reserve_input.returnPressed.connect(self.load_charter_billing)
        header_layout.addWidget(self.reserve_input)
        
        load_btn = QPushButton("🔍 Load Charter")
        load_btn.clicked.connect(self.load_charter_billing)
        header_layout.addWidget(load_btn)
        
        header_layout.addSpacing(20)
        
        self.charter_info_label = QLabel("")
        self.charter_info_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        header_layout.addWidget(self.charter_info_label)
        
        header_layout.addStretch()
        header_group.setLayout(header_layout)
        layout.addWidget(header_group)
        
        # === MAIN CONTENT: SPLIT INTO LEFT (BILLING) AND RIGHT (SEARCH) ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # LEFT SIDE: Deposits & Payments
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Charter Summary
        summary_group = self.create_charter_summary_section()
        left_layout.addWidget(summary_group)
        
        # Deposits Section
        deposits_group = self.create_deposits_section()
        left_layout.addWidget(deposits_group)
        
        # Payments Section
        payments_group = self.create_payments_section()
        left_layout.addWidget(payments_group)
        
        # Balance Summary
        balance_group = self.create_balance_section()
        left_layout.addWidget(balance_group)
        
        # Invoice Controls
        invoice_group = self.create_invoice_controls()
        left_layout.addWidget(invoice_group)
        
        left_widget.setLayout(left_layout)
        
        # RIGHT SIDE: Search & Link Tools
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Multi-Charter Linking
        link_group = self.create_multi_charter_section()
        right_layout.addWidget(link_group)
        
        # Banking Search
        banking_group = self.create_banking_search_section()
        right_layout.addWidget(banking_group)
        
        # Square Payment Search
        square_group = self.create_square_search_section()
        right_layout.addWidget(square_group)
        
        right_widget.setLayout(right_layout)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter, 1)
        
        self.setLayout(layout)
    
    def create_charter_summary_section(self) -> QGroupBox:
        """Charter financial summary"""
        group = QGroupBox("Charter Financial Summary")
        layout = QFormLayout()
        
        self.total_charges_label = QLabel("$0.00")
        self.total_charges_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addRow("Total Charges:", self.total_charges_label)
        
        self.total_deposits_label = QLabel("$0.00")
        layout.addRow("Total Deposits:", self.total_deposits_label)
        
        self.total_payments_label = QLabel("$0.00")
        layout.addRow("Total Payments:", self.total_payments_label)
        
        self.balance_due_label = QLabel("$0.00")
        self.balance_due_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #cc0000;")
        layout.addRow("Balance Due:", self.balance_due_label)
        
        group.setLayout(layout)
        return group
    
    def create_deposits_section(self) -> QGroupBox:
        """NRP and refundable deposit tracking"""
        group = QGroupBox("Deposits (Pre-Service)")
        layout = QVBoxLayout()
        
        # Deposit Controls
        controls = QHBoxLayout()
        
        self.deposit_type_combo = QComboBox()
        self.deposit_type_combo.addItems([
            "NRP (Non-Refundable Deposit)",
            "Refundable Deposit",
            "Partial Payment"
        ])
        controls.addWidget(self.deposit_type_combo)
        
        self.deposit_amount = CurrencyInput()
        controls.addWidget(QLabel("Amount:"))
        controls.addWidget(self.deposit_amount)
        
        self.deposit_date = QDateEdit()
        self.deposit_date.setDate(QDate.currentDate())
        self.deposit_date.setCalendarPopup(True)
        self.deposit_date.setMaximumWidth(120)
        controls.addWidget(QLabel("Date:"))
        controls.addWidget(self.deposit_date)
        
        add_deposit_btn = QPushButton("+ Add Deposit")
        add_deposit_btn.clicked.connect(self.add_deposit)
        controls.addWidget(add_deposit_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Deposits Table
        self.deposits_table = QTableWidget()
        self.deposits_table.setColumnCount(6)
        self.deposits_table.setHorizontalHeaderLabels([
            "Date", "Type", "Amount", "Payment Method", "Notes", "Delete"
        ])
        self.deposits_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.deposits_table.setMaximumHeight(150)
        layout.addWidget(self.deposits_table)
        
        group.setLayout(layout)
        return group
    
    def create_payments_section(self) -> QGroupBox:
        """Payment completion tracking"""
        group = QGroupBox("Payments (Balance Settlement)")
        layout = QVBoxLayout()
        
        # Payment Controls
        controls = QHBoxLayout()
        
        self.payment_amount = CurrencyInput()
        controls.addWidget(QLabel("Amount:"))
        controls.addWidget(self.payment_amount)
        
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItems([
            "cash", "check", "credit_card", "debit_card",
            "bank_transfer", "trade_of_services"
        ])
        controls.addWidget(QLabel("Method:"))
        controls.addWidget(self.payment_method_combo)
        
        self.payment_date = QDateEdit()
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setMaximumWidth(120)
        controls.addWidget(QLabel("Date:"))
        controls.addWidget(self.payment_date)
        
        add_payment_btn = QPushButton("+ Add Payment")
        add_payment_btn.clicked.connect(self.add_payment)
        controls.addWidget(add_payment_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Payments Table
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(6)
        self.payments_table.setHorizontalHeaderLabels([
            "Date", "Amount", "Method", "Reference", "Notes", "Delete"
        ])
        self.payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.payments_table.setMaximumHeight(200)
        layout.addWidget(self.payments_table)
        
        group.setLayout(layout)
        return group
    
    def create_balance_section(self) -> QGroupBox:
        """Balance summary and status"""
        group = QGroupBox("Balance Status")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("<b>Outstanding Balance:</b>"))
        self.outstanding_balance_label = QLabel("$0.00")
        self.outstanding_balance_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #cc0000;")
        layout.addWidget(self.outstanding_balance_label)
        
        layout.addStretch()
        
        self.paid_in_full_label = QLabel("❌ NOT PAID")
        self.paid_in_full_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #cc0000;")
        layout.addWidget(self.paid_in_full_label)
        
        group.setLayout(layout)
        return group
    
    def create_invoice_controls(self) -> QGroupBox:
        """Invoice printing and management"""
        group = QGroupBox("Invoice & Document Printing")
        layout = QVBoxLayout()
        
        # Single Charter Invoice
        single_row = QHBoxLayout()
        single_row.addWidget(QLabel("<b>Single Charter:</b>"))
        
        print_invoice_btn = QPushButton("🖨️ Print Invoice")
        print_invoice_btn.clicked.connect(self.print_invoice)
        single_row.addWidget(print_invoice_btn)
        
        print_beverage_btn = QPushButton("🍷 Print Beverage Order")
        print_beverage_btn.clicked.connect(self.print_beverage_order)
        single_row.addWidget(print_beverage_btn)
        
        single_row.addStretch()
        layout.addLayout(single_row)
        
        # Multi-Charter Invoice
        multi_row = QHBoxLayout()
        multi_row.addWidget(QLabel("<b>Linked Charters:</b>"))
        
        print_combined_btn = QPushButton("🖨️ Print Combined Invoice")
        print_combined_btn.setToolTip("Print invoice combining this charter with all linked charters")
        print_combined_btn.clicked.connect(self.print_combined_invoice)
        multi_row.addWidget(print_combined_btn)
        
        self.linked_charters_label = QLabel("No linked charters")
        self.linked_charters_label.setStyleSheet("color: #666;")
        multi_row.addWidget(self.linked_charters_label)
        
        multi_row.addStretch()
        layout.addLayout(multi_row)
        
        group.setLayout(layout)
        return group
    
    def create_multi_charter_section(self) -> QGroupBox:
        """Multi-charter linking and split payments"""
        group = QGroupBox("Multi-Charter Management")
        layout = QVBoxLayout()
        
        # Link Charters
        link_row = QHBoxLayout()
        link_row.addWidget(QLabel("Link Charter:"))
        
        self.link_reserve_input = QLineEdit()
        self.link_reserve_input.setPlaceholderText("Reserve #")
        self.link_reserve_input.setMaximumWidth(120)
        link_row.addWidget(self.link_reserve_input)
        
        link_btn = QPushButton("🔗 Link")
        link_btn.clicked.connect(self.link_charter)
        link_row.addWidget(link_btn)
        
        unlink_btn = QPushButton("❌ Unlink Selected")
        unlink_btn.clicked.connect(self.unlink_charter)
        link_row.addWidget(unlink_btn)
        
        link_row.addStretch()
        layout.addLayout(link_row)
        
        # Linked Charters Table
        self.linked_charters_table = QTableWidget()
        self.linked_charters_table.setColumnCount(5)
        self.linked_charters_table.setHorizontalHeaderLabels([
            "Reserve #", "Date", "Total Charges", "Paid", "Balance"
        ])
        self.linked_charters_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.linked_charters_table.setMaximumHeight(150)
        layout.addWidget(self.linked_charters_table)
        
        # Split Payment
        split_row = QHBoxLayout()
        split_row.addWidget(QLabel("<b>Split Payment Across Charters:</b>"))
        
        self.split_amount = CurrencyInput()
        split_row.addWidget(QLabel("Amount:"))
        split_row.addWidget(self.split_amount)
        
        split_btn = QPushButton("💰 Split Evenly")
        split_btn.setToolTip("Split the amount evenly across all linked charters")
        split_btn.clicked.connect(self.split_payment_evenly)
        split_row.addWidget(split_btn)
        
        split_row.addStretch()
        layout.addLayout(split_row)
        
        group.setLayout(layout)
        return group
    
    def create_banking_search_section(self) -> QGroupBox:
        """Banking transaction search and link"""
        group = QGroupBox("Banking Transaction Search")
        layout = QVBoxLayout()
        
        # Search Criteria
        search_form = QFormLayout()
        
        self.bank_amount = CurrencyInput()
        search_form.addRow("Amount:", self.bank_amount)
        
        self.bank_date_from = QDateEdit()
        self.bank_date_from.setDate(QDate.currentDate().addDays(-30))
        self.bank_date_from.setCalendarPopup(True)
        self.bank_date_from.setMaximumWidth(120)
        search_form.addRow("Date From:", self.bank_date_from)
        
        self.bank_date_to = QDateEdit()
        self.bank_date_to.setDate(QDate.currentDate())
        self.bank_date_to.setCalendarPopup(True)
        self.bank_date_to.setMaximumWidth(120)
        search_form.addRow("Date To:", self.bank_date_to)
        
        self.bank_description = QLineEdit()
        self.bank_description.setPlaceholderText("Search description...")
        search_form.addRow("Description:", self.bank_description)
        
        layout.addLayout(search_form)
        
        # Search Button
        search_btn = QPushButton("🔍 Search Banking")
        search_btn.clicked.connect(self.search_banking)
        layout.addWidget(search_btn)
        
        # Results Table
        self.banking_results_table = QTableWidget()
        self.banking_results_table.setColumnCount(5)
        self.banking_results_table.setHorizontalHeaderLabels([
            "Date", "Amount", "Description", "Account", "Link"
        ])
        self.banking_results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.banking_results_table.setMaximumHeight(200)
        layout.addWidget(self.banking_results_table)
        
        group.setLayout(layout)
        return group
    
    def create_square_search_section(self) -> QGroupBox:
        """Square payment lookup (web integration)"""
        group = QGroupBox("Square Payment Lookup")
        layout = QVBoxLayout()
        
        info = QLabel("Search Square dashboard for card payments not in database")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        search_row = QHBoxLayout()
        
        self.square_amount = CurrencyInput()
        search_row.addWidget(QLabel("Amount:"))
        search_row.addWidget(self.square_amount)
        
        self.square_last4 = QLineEdit()
        self.square_last4.setPlaceholderText("Last 4 digits")
        self.square_last4.setMaximumWidth(100)
        search_row.addWidget(QLabel("Last 4:"))
        search_row.addWidget(self.square_last4)
        
        square_btn = QPushButton("🔍 Open Square Dashboard")
        square_btn.clicked.connect(self.open_square_dashboard)
        search_row.addWidget(square_btn)
        
        search_row.addStretch()
        layout.addLayout(search_row)
        
        # Manual Entry
        manual_group = QGroupBox("Manual Entry from Square")
        manual_layout = QFormLayout()
        
        self.square_manual_amount = CurrencyInput()
        manual_layout.addRow("Amount:", self.square_manual_amount)
        
        self.square_manual_date = QDateEdit()
        self.square_manual_date.setDate(QDate.currentDate())
        self.square_manual_date.setCalendarPopup(True)
        self.square_manual_date.setMaximumWidth(120)
        manual_layout.addRow("Date:", self.square_manual_date)
        
        self.square_manual_ref = QLineEdit()
        self.square_manual_ref.setPlaceholderText("Transaction ID")
        manual_layout.addRow("Reference:", self.square_manual_ref)
        
        add_square_btn = QPushButton("+ Add Square Payment")
        add_square_btn.clicked.connect(self.add_square_payment)
        manual_layout.addRow("", add_square_btn)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        group.setLayout(layout)
        return group
    
    # === DATA OPERATIONS ===
    
    def load_charter_billing(self):
        """Load charter and all billing information"""
        reserve_number = self.reserve_input.text().strip()
        if not reserve_number:
            QMessageBox.warning(self, "Input Required", "Please enter a reserve number")
            return
        
        try:
            cur = self.db.conn.cursor()
            
            # Load charter
            cur.execute("""
                SELECT c.charter_id, c.reserve_number, c.charter_date,
                       cl.company_name, cl.contact_name,
                       c.total_amount_due, c.paid_amount, c.balance_due
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE c.reserve_number = %s
            """, (reserve_number,))
            
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "Not Found", f"Charter {reserve_number} not found")
                return
            
            charter_id, reserve, charter_date, company, contact, total, paid, balance = row
            self.current_reserve_number = reserve
            
            # Update header
            client_name = company or contact or "Unknown Client"
            date_str = charter_date.strftime("%Y-%m-%d") if charter_date else "No Date"
            self.charter_info_label.setText(f"{reserve} | {client_name} | {date_str}")
            
            # Update summary
            self.total_charges_label.setText(f"${total:,.2f}")
            self.total_payments_label.setText(f"${paid:,.2f}")
            self.balance_due_label.setText(f"${balance:,.2f}")
            
            if balance <= 0:
                self.paid_in_full_label.setText("✅ PAID IN FULL")
                self.paid_in_full_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #00cc00;")
            else:
                self.paid_in_full_label.setText("❌ NOT PAID")
                self.paid_in_full_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #cc0000;")
            
            # Load deposits and payments
            self.load_deposits()
            self.load_payments()
            self.load_linked_charters()
            
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error loading charter: {e}")
    
    def load_deposits(self):
        """Load deposit history"""
        if not self.current_reserve_number:
            return
        
        try:
            cur = self.db.conn.cursor()
            cur.execute("""
                SELECT payment_date, amount, payment_method, notes
                FROM payments
                WHERE reserve_number = %s
                  AND payment_date < (SELECT charter_date FROM charters WHERE reserve_number = %s)
                ORDER BY payment_date
            """, (self.current_reserve_number, self.current_reserve_number))
            
            deposits = cur.fetchall()
            self.deposits_table.setRowCount(len(deposits))
            
            total_deposits = Decimal("0")
            for i, (date, amount, method, notes) in enumerate(deposits):
                self.deposits_table.setItem(i, 0, QTableWidgetItem(date.strftime("%Y-%m-%d")))
                
                deposit_type = "NRP" if "NRP" in (notes or "").upper() else "Deposit"
                self.deposits_table.setItem(i, 1, QTableWidgetItem(deposit_type))
                self.deposits_table.setItem(i, 2, QTableWidgetItem(f"${amount:,.2f}"))
                self.deposits_table.setItem(i, 3, QTableWidgetItem(method or ""))
                self.deposits_table.setItem(i, 4, QTableWidgetItem(notes or ""))
                
                delete_btn = QPushButton("🗑️")
                delete_btn.setMaximumWidth(40)
                self.deposits_table.setCellWidget(i, 5, delete_btn)
                
                total_deposits += amount
            
            self.total_deposits_label.setText(f"${total_deposits:,.2f}")
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error loading deposits: {e}")
    
    def load_payments(self):
        """Load payment history"""
        if not self.current_reserve_number:
            return
        
        try:
            cur = self.db.conn.cursor()
            cur.execute("""
                SELECT payment_date, amount, payment_method, notes
                FROM payments
                WHERE reserve_number = %s
                  AND payment_date >= (SELECT charter_date FROM charters WHERE reserve_number = %s)
                ORDER BY payment_date
            """, (self.current_reserve_number, self.current_reserve_number))
            
            payments = cur.fetchall()
            self.payments_table.setRowCount(len(payments))
            
            for i, (date, amount, method, notes) in enumerate(payments):
                self.payments_table.setItem(i, 0, QTableWidgetItem(date.strftime("%Y-%m-%d")))
                self.payments_table.setItem(i, 1, QTableWidgetItem(f"${amount:,.2f}"))
                self.payments_table.setItem(i, 2, QTableWidgetItem(method or ""))
                self.payments_table.setItem(i, 3, QTableWidgetItem(notes or ""))
                
                delete_btn = QPushButton("🗑️")
                delete_btn.setMaximumWidth(40)
                self.payments_table.setCellWidget(i, 4, delete_btn)
            
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error loading payments: {e}")
    
    def load_linked_charters(self):
        """Load linked charters for multi-invoice"""
        # Placeholder - implement charter linking logic
        self.linked_charters_table.setRowCount(0)
        self.linked_charters_label.setText("No linked charters")
    
    def add_deposit(self):
        """Add a deposit to the charter"""
        if not self.current_reserve_number:
            QMessageBox.warning(self, "No Charter", "Please load a charter first")
            return
        
        amount = self.deposit_amount.get_value()
        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid deposit amount")
            return
        
        try:
            cur = self.db.conn.cursor()
            
            deposit_type = self.deposit_type_combo.currentText()
            notes = f"Deposit: {deposit_type}"
            
            cur.execute("""
                INSERT INTO payments (
                    reserve_number, amount, payment_date, payment_method, notes
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                self.current_reserve_number,
                amount,
                self.deposit_date.date().toPyDate(),
                "deposit",
                notes
            ))
            
            self.db.conn.commit()
            cur.close()
            
            self.deposit_amount.clear()
            self.load_charter_billing()
            
            QMessageBox.information(self, "Success", f"Deposit of ${amount:.2f} added")
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, "Database Error", f"Error adding deposit: {e}")
    
    def add_payment(self):
        """Add a payment to the charter"""
        if not self.current_reserve_number:
            QMessageBox.warning(self, "No Charter", "Please load a charter first")
            return
        
        amount = self.payment_amount.get_value()
        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid payment amount")
            return
        
        try:
            cur = self.db.conn.cursor()
            
            cur.execute("""
                INSERT INTO payments (
                    reserve_number, amount, payment_date, payment_method, notes
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                self.current_reserve_number,
                amount,
                self.payment_date.date().toPyDate(),
                self.payment_method_combo.currentText(),
                "Payment"
            ))
            
            self.db.conn.commit()
            cur.close()
            
            self.payment_amount.clear()
            self.load_charter_billing()
            self.payment_added.emit(self.current_reserve_number, amount)
            
            QMessageBox.information(self, "Success", f"Payment of ${amount:.2f} added")
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, "Database Error", f"Error adding payment: {e}")
    
    def print_invoice(self):
        """Print invoice for current charter"""
        if not self.current_reserve_number:
            QMessageBox.warning(self, "No Charter", "Please load a charter first")
            return
        
        # Call parent widget's print invoice if available
        if self.parent_charter and hasattr(self.parent_charter, 'print_invoice'):
            self.parent_charter.print_invoice()
            self.invoice_printed.emit(self.current_reserve_number)
        else:
            QMessageBox.information(self, "Print Invoice", 
                f"Printing invoice for charter {self.current_reserve_number}...")
    
    def print_beverage_order(self):
        """Print beverage order separately"""
        if not self.current_reserve_number:
            QMessageBox.warning(self, "No Charter", "Please load a charter first")
            return
        
        if self.parent_charter and hasattr(self.parent_charter, 'print_beverage_order'):
            self.parent_charter.print_beverage_order()
        else:
            QMessageBox.information(self, "Print Beverage", 
                f"Printing beverage order for charter {self.current_reserve_number}...")
    
    def print_combined_invoice(self):
        """Print combined invoice for linked charters"""
        QMessageBox.information(self, "Combined Invoice", 
            "Combined invoice printing coming soon...")
    
    def link_charter(self):
        """Link another charter for combined billing"""
        QMessageBox.information(self, "Link Charter", 
            "Charter linking coming soon...")
    
    def unlink_charter(self):
        """Unlink a charter"""
        QMessageBox.information(self, "Unlink Charter", 
            "Charter unlinking coming soon...")
    
    def split_payment_evenly(self):
        """Split payment evenly across linked charters"""
        QMessageBox.information(self, "Split Payment", 
            "Split payment functionality coming soon...")
    
    def search_banking(self):
        """Search banking transactions"""
        amount = self.bank_amount.get_value()
        desc = self.bank_description.text().strip()
        date_from = self.bank_date_from.date().toPyDate()
        date_to = self.bank_date_to.date().toPyDate()
        
        try:
            cur = self.db.conn.cursor()
            
            query = """
                SELECT transaction_date, amount, description, mapped_bank_account_id
                FROM banking_transactions
                WHERE transaction_date BETWEEN %s AND %s
            """
            params = [date_from, date_to]
            
            if amount > 0:
                query += " AND ABS(amount - %s) < 0.01"
                params.append(amount)
            
            if desc:
                query += " AND description ILIKE %s"
                params.append(f"%{desc}%")
            
            query += " ORDER BY transaction_date DESC LIMIT 50"
            
            cur.execute(query, params)
            results = cur.fetchall()
            
            self.banking_results_table.setRowCount(len(results))
            for i, (date, amt, desc_text, account) in enumerate(results):
                self.banking_results_table.setItem(i, 0, QTableWidgetItem(date.strftime("%Y-%m-%d")))
                self.banking_results_table.setItem(i, 1, QTableWidgetItem(f"${amt:,.2f}"))
                self.banking_results_table.setItem(i, 2, QTableWidgetItem(desc_text or ""))
                
                account_name = "CIBC" if account == 1 else "Scotia" if account == 2 else "Unknown"
                self.banking_results_table.setItem(i, 3, QTableWidgetItem(account_name))
                
                link_btn = QPushButton("🔗 Link")
                link_btn.setMaximumWidth(60)
                self.banking_results_table.setCellWidget(i, 4, link_btn)
            
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error searching banking: {e}")
    
    def open_square_dashboard(self):
        """Open Square dashboard in browser"""
        import webbrowser
        webbrowser.open("https://squareup.com/dashboard/sales/transactions")
        QMessageBox.information(self, "Square Dashboard", 
            "Square dashboard opened in browser. Search for the transaction and add it manually below.")
    
    def add_square_payment(self):
        """Add payment from Square manually"""
        if not self.current_reserve_number:
            QMessageBox.warning(self, "No Charter", "Please load a charter first")
            return
        
        amount = self.square_manual_amount.get_value()
        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid amount")
            return
        
        try:
            cur = self.db.conn.cursor()
            
            cur.execute("""
                INSERT INTO payments (
                    reserve_number, amount, payment_date, payment_method, notes
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                self.current_reserve_number,
                amount,
                self.square_manual_date.date().toPyDate(),
                "credit_card",
                f"Square: {self.square_manual_ref.text()}"
            ))
            
            self.db.conn.commit()
            cur.close()
            
            self.square_manual_amount.clear()
            self.square_manual_ref.clear()
            self.load_charter_billing()
            
            QMessageBox.information(self, "Success", f"Square payment of ${amount:.2f} added")
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, "Database Error", f"Error adding Square payment: {e}")
