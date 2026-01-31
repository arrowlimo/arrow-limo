"""
Payment Dialog: Transaction history, add payment, view CC info, Mark NFD
Matches LMSGold payment format with table view and action buttons
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QDoubleSpinBox, QComboBox,
    QDateEdit, QTextEdit, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor
from datetime import datetime, date


class PaymentDialog(QDialog):
    """Payment management dialog with transaction history and payment entry"""
    
    def __init__(self, db, reserve_number, client_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.reserve_number = reserve_number
        self.client_id = client_id
        
        self.setWindowTitle(f"Payment Manager - {reserve_number}")
        self.setGeometry(100, 100, 1200, 700)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # ===== HEADER WITH RESERVE INFO =====
        header_layout = QHBoxLayout()
        
        res_label = QLabel(f"Reserve #: {reserve_number}")
        res_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        res_label.setStyleSheet("color: #1a3d7a;")
        header_layout.addWidget(res_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        layout.addSpacing(10)
        
        # ===== TABS =====
        tabs = QTabWidget()
        
        # Tab 1: Payment History
        history_tab = self.create_history_tab()
        tabs.addTab(history_tab, "📊 Payment History")
        
        # Tab 2: Add Payment
        add_payment_tab = self.create_add_payment_tab()
        tabs.addTab(add_payment_tab, "➕ Add Payment")
        
        # Tab 3: Client CC Info
        cc_info_tab = self.create_cc_info_tab()
        tabs.addTab(cc_info_tab, "💳 Credit Card Info")
        
        layout.addWidget(tabs)
        
        # ===== SUMMARY FOOTER =====
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(30)
        
        total_charges_label = QLabel("Total Charges:")
        self.total_charges_display = QLineEdit()
        self.total_charges_display.setReadOnly(True)
        self.total_charges_display.setMaximumWidth(120)
        summary_layout.addWidget(total_charges_label)
        summary_layout.addWidget(self.total_charges_display)
        
        payments_label = QLabel("Payments:")
        self.payments_display = QLineEdit()
        self.payments_display.setReadOnly(True)
        self.payments_display.setMaximumWidth(120)
        summary_layout.addWidget(payments_label)
        summary_layout.addWidget(self.payments_display)
        
        balance_label = QLabel("Balance Due:")
        self.balance_display = QLineEdit()
        self.balance_display.setReadOnly(True)
        self.balance_display.setMaximumWidth(120)
        self.balance_display.setStyleSheet("background-color: #fff3cd;")
        summary_layout.addWidget(balance_label)
        summary_layout.addWidget(self.balance_display)
        
        summary_layout.addStretch()
        layout.addLayout(summary_layout)
        
        # ===== ACTION BUTTONS =====
        button_layout = QHBoxLayout()
        
        self.mark_nfd_btn = QPushButton("❌ Mark NFD (No Funds)")
        self.mark_nfd_btn.clicked.connect(self.mark_nfd)
        self.mark_nfd_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        button_layout.addWidget(self.mark_nfd_btn)
        
        self.email_receipt_btn = QPushButton("📧 Email Receipt")
        self.email_receipt_btn.clicked.connect(self.email_receipt)
        button_layout.addWidget(self.email_receipt_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Load payment data
        self.load_payment_history()
        self.load_summary()
    
    def create_history_tab(self):
        """Tab 1: Payment history table matching LMSGold format"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("PAYMENT & CHARGE HISTORY")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        layout.addWidget(title)
        
        # Transaction table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)  # Added record_id column (hidden)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Type", "Description", "Amount", "Reference", "Balance", "Status", "ID"
        ])
        self.history_table.setColumnHidden(7, True)  # Hide ID column
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.resizeColumnsToContents()
        layout.addWidget(self.history_table)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self.delete_transaction)
        action_layout.addWidget(delete_btn)
        
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.clicked.connect(self.edit_transaction)
        action_layout.addWidget(edit_btn)
        
        action_layout.addStretch()
        layout.addLayout(action_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_add_payment_tab(self):
        """Tab 2: Add new payment entry"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("ADD PAYMENT")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        layout.addWidget(title)
        
        # Payment form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)
        
        # Row 1: Date and Amount
        row1 = QHBoxLayout()
        
        date_label = QLabel("Payment Date:")
        date_label.setMinimumWidth(100)
        self.payment_date = QDateEdit()
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setMaximumWidth(150)
        row1.addWidget(date_label)
        row1.addWidget(self.payment_date)
        row1.addSpacing(30)
        
        amount_label = QLabel("Amount:")
        amount_label.setMinimumWidth(100)
        self.payment_amount = QDoubleSpinBox()
        self.payment_amount.setMinimum(0)
        self.payment_amount.setMaximum(999999)
        self.payment_amount.setDecimals(2)
        self.payment_amount.setPrefix("$")
        self.payment_amount.setMaximumWidth(150)
        row1.addWidget(amount_label)
        row1.addWidget(self.payment_amount)
        row1.addStretch()
        form_layout.addLayout(row1)
        
        # Row 2: Payment Method
        row2 = QHBoxLayout()
        
        method_label = QLabel("Payment Method:")
        method_label.setMinimumWidth(100)
        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "Credit Card", "Debit Card", "Cash", "Check", "Bank Transfer",
            "Email Money Transfer", "Cryptocurrency", "Other"
        ])
        self.payment_method.setMaximumWidth(200)
        row2.addWidget(method_label)
        row2.addWidget(self.payment_method)
        row2.addStretch()
        form_layout.addLayout(row2)
        
        # Row 3: Reference Number
        row3 = QHBoxLayout()
        
        ref_label = QLabel("Reference/Check #:")
        ref_label.setMinimumWidth(100)
        self.payment_reference = QLineEdit()
        self.payment_reference.setPlaceholderText("e.g., transaction ID, check number")
        self.payment_reference.setMaximumWidth(300)
        row3.addWidget(ref_label)
        row3.addWidget(self.payment_reference)
        row3.addStretch()
        form_layout.addLayout(row3)
        
        # Row 4: Notes
        notes_label = QLabel("Notes:")
        notes_label.setMinimumWidth(100)
        notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.payment_notes = QTextEdit()
        self.payment_notes.setMaximumHeight(80)
        row4 = QHBoxLayout()
        row4.addWidget(notes_label)
        row4.addWidget(self.payment_notes)
        form_layout.addLayout(row4)
        
        layout.addLayout(form_layout)
        layout.addSpacing(10)
        
        # Submit button
        submit_btn = QPushButton("💾 Record Payment")
        submit_btn.clicked.connect(self.record_payment)
        submit_btn.setStyleSheet("background-color: #28a745; color: white; padding: 8px; font-weight: bold;")
        layout.addWidget(submit_btn)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def create_cc_info_tab(self):
        """Tab 3: Credit Card and contact information (for payment entry only)"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("CLIENT PAYMENT INFORMATION")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        layout.addWidget(title)
        
        # CC Info Section
        cc_title = QLabel("CREDIT CARD ON FILE")
        cc_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        cc_title.setStyleSheet("color: #555;")
        layout.addWidget(cc_title)
        
        # Row 1: Card Type and Last 4
        row1 = QHBoxLayout()
        
        card_type_label = QLabel("Card Type:")
        card_type_label.setMinimumWidth(100)
        self.cc_card_type = QLineEdit()
        self.cc_card_type.setReadOnly(True)
        self.cc_card_type.setMaximumWidth(150)
        row1.addWidget(card_type_label)
        row1.addWidget(self.cc_card_type)
        row1.addSpacing(30)
        
        card_last4_label = QLabel("Last 4 Digits:")
        card_last4_label.setMinimumWidth(100)
        self.cc_last4 = QLineEdit()
        self.cc_last4.setReadOnly(True)
        self.cc_last4.setMaximumWidth(150)
        row1.addWidget(card_last4_label)
        row1.addWidget(self.cc_last4)
        row1.addStretch()
        layout.addLayout(row1)
        
        # Row 2: Expiry
        row2 = QHBoxLayout()
        
        expiry_label = QLabel("Expiry Date:")
        expiry_label.setMinimumWidth(100)
        self.cc_expiry = QLineEdit()
        self.cc_expiry.setReadOnly(True)
        self.cc_expiry.setMaximumWidth(150)
        row2.addWidget(expiry_label)
        row2.addWidget(self.cc_expiry)
        row2.addStretch()
        layout.addLayout(row2)
        
        layout.addSpacing(15)
        
        # Email Info Section
        email_title = QLabel("CONTACT INFORMATION")
        email_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        email_title.setStyleSheet("color: #555;")
        layout.addWidget(email_title)
        
        # Row 3: Email
        row3 = QHBoxLayout()
        
        email_label = QLabel("Email:")
        email_label.setMinimumWidth(100)
        self.client_email = QLineEdit()
        self.client_email.setPlaceholderText("client@example.com")
        self.client_email.setMaximumWidth(300)
        row3.addWidget(email_label)
        row3.addWidget(self.client_email)
        row3.addStretch()
        layout.addLayout(row3)
        
        # Row 4: Phone
        row4 = QHBoxLayout()
        
        phone_label = QLabel("Phone:")
        phone_label.setMinimumWidth(100)
        self.client_phone = QLineEdit()
        self.client_phone.setPlaceholderText("(555) 123-4567")
        self.client_phone.setMaximumWidth(300)
        row4.addWidget(phone_label)
        row4.addWidget(self.client_phone)
        row4.addStretch()
        layout.addLayout(row4)
        
        layout.addSpacing(15)
        
        # Save button for contact info
        save_contact_btn = QPushButton("💾 Update Contact Information")
        save_contact_btn.clicked.connect(self.save_contact_info)
        layout.addWidget(save_contact_btn)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def load_payment_history(self):
        """Load payment and charge history for this charter"""
        try:
            cur = self.db.cursor()
            
            # Query payments linked via reserve_number (business key)
            cur.execute("""
                SELECT 
                    DATE(p.payment_date) as payment_date,
                    'PAYMENT' as type,
                    COALESCE(p.payment_method, 'Unknown') as description,
                    p.amount as amount,
                    COALESCE(p.transaction_id, '') as reference,
                    0 as balance,
                    p.payment_status as status,
                    p.payment_id as record_id
                FROM payments p
                WHERE p.reserve_number = %s
                
                UNION ALL
                
                -- Query charges linked via reserve_number
                SELECT
                    DATE(ch.charge_date) as charge_date,
                    'CHARGE' as type,
                    ch.charge_description as description,
                    ch.charge_amount as amount,
                    '' as reference,
                    0 as balance,
                    'Applied' as status,
                    ch.charge_id as record_id
                FROM charges ch
                WHERE ch.reserve_number = %s
                
                ORDER BY payment_date DESC
            """, (self.reserve_number, self.reserve_number))
            
            rows = cur.fetchall()
            cur.close()
            
            # Populate table
            self.history_table.setRowCount(0)
            
            for row_num, row_data in enumerate(rows):
                self.history_table.insertRow(row_num)
                
                for col_num, value in enumerate(row_data):
                    if col_num == 3:  # Amount column
                        text = f"${float(value):.2f}" if value else "$0.00"
                    else:
                        text = str(value) if value else ""
                    
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    # Highlight payments in green, charges in red
                    if col_num == 1:  # Type column
                        if value == "PAYMENT":
                            item.setBackground(QColor(220, 240, 220))
                        elif value == "CHARGE":
                            item.setBackground(QColor(240, 220, 220))
                    
                    self.history_table.setItem(row_num, col_num, item)
            
            self.history_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load payment history: {str(e)}")
    
    def load_summary(self):
        """Load and display payment summary (Total Charges, Payments, Balance)"""
        try:
            cur = self.db.cursor()
            
            # Get total amount due
            cur.execute("""
                SELECT COALESCE(total_amount_due, 0)
                FROM charters
                WHERE reserve_number = %s
            """, (self.reserve_number,))
            
            total_due = cur.fetchone()[0] or 0
            
            # Get total payments
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM payments
                WHERE reserve_number = %s AND payment_status != 'cancelled'
            """, (self.reserve_number,))
            
            total_paid = cur.fetchone()[0] or 0
            
            # Get total charges
            cur.execute("""
                SELECT COALESCE(SUM(charge_amount), 0)
                FROM charges
                WHERE reserve_number = %s
            """, (self.reserve_number,))
            
            total_charges = cur.fetchone()[0] or 0
            
            cur.close()
            
            # Calculate balance
            balance = total_charges - total_paid
            
            # Update displays
            self.total_charges_display.setText(f"${total_charges:.2f}")
            self.payments_display.setText(f"${total_paid:.2f}")
            self.balance_display.setText(f"${balance:.2f}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load summary: {str(e)}")
    
    def record_payment(self):
        """Record a new payment"""
        if self.payment_amount.value() <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid payment amount")
            return
        
        try:
            cur = self.db.cursor()
            
            # Insert payment record using reserve_number (business key)
            cur.execute("""
                INSERT INTO payments (
                    reserve_number,
                    payment_date,
                    amount,
                    payment_method,
                    transaction_id,
                    notes,
                    payment_status,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                self.reserve_number,
                self.payment_date.date().toPyDate(),
                self.payment_amount.value(),
                self.payment_method.currentText(),
                self.payment_reference.text() or None,
                self.payment_notes.toPlainText() or None,
                "recorded"
            ))
            
            self.db.commit()
            
            QMessageBox.information(self, "Success", "Payment recorded successfully")
            
            # Clear form
            self.payment_amount.setValue(0)
            self.payment_reference.clear()
            self.payment_notes.clear()
            
            # Reload history and summary
            self.load_payment_history()
            self.load_summary()
            
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to record payment: {str(e)}")
    
    def mark_nfd(self):
        """Mark payment as No Funds Deposit (NFD)"""
        if QMessageBox.question(self, "Confirm", "Mark this charter as NFD (No Funds)?", 
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db.cursor()
                
                # Record NFD charge
                cur.execute("""
                    INSERT INTO charges (
                        reserve_number,
                        charge_date,
                        charge_description,
                        charge_amount,
                        charge_type,
                        created_at
                    ) VALUES (%s, NOW(), %s, %s, %s, NOW())
                """, (
                    self.reserve_number,
                    "NSF - No Funds Deposit",
                    25.00,  # Standard NSF fee
                    "nfd"
                ))
                
                self.db.commit()
                
                QMessageBox.information(self, "Success", "NFD recorded - $25.00 fee applied")
                
                # Reload
                self.load_payment_history()
                self.load_summary()
                
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to record NFD: {str(e)}")
    
    def email_receipt(self):
        """Email payment receipt to client"""
        email = self.client_email.text().strip()
        
        if not email:
            QMessageBox.warning(self, "Missing Email", "Please enter client email address")
            return
        
        QMessageBox.information(self, "Email Receipt", 
                               f"Receipt would be sent to: {email}\n\n(Email integration not yet implemented)")
    
    def delete_transaction(self):
        """Delete selected payment or charge (admin authority)"""
        selected = self.history_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to delete")
            return
        
        row = selected[0].row()
        transaction_type = self.history_table.item(row, 1).text()
        amount = self.history_table.item(row, 3).text()
        description = self.history_table.item(row, 2).text()
        record_id_item = self.history_table.item(row, 7)  # Hidden column with record_id
        
        if not record_id_item:
            QMessageBox.warning(self, "Error", "Could not identify transaction ID")
            return
        
        record_id = record_id_item.text()
        
        # Confirm deletion with details
        if QMessageBox.question(self, "Confirm Delete", 
                               f"Delete {transaction_type.lower()}?\n\n{description}\nAmount: {amount}\n\nThis cannot be undone.",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db.cursor()
                
                if transaction_type == "PAYMENT":
                    # Delete payment record
                    cur.execute("""
                        DELETE FROM payments
                        WHERE payment_id = %s AND reserve_number = %s
                    """, (record_id, self.reserve_number))
                elif transaction_type == "CHARGE":
                    # Delete charge record
                    cur.execute("""
                        DELETE FROM charges
                        WHERE charge_id = %s AND reserve_number = %s
                    """, (record_id, self.reserve_number))
                else:
                    QMessageBox.warning(self, "Error", "Unknown transaction type")
                    return
                
                if cur.rowcount == 0:
                    QMessageBox.warning(self, "Not Found", "Transaction not found or already deleted")
                    cur.close()
                    return
                
                self.db.commit()
                cur.close()
                
                QMessageBox.information(self, "Deleted", f"{transaction_type.capitalize()} deleted: {amount}")
                
                # Reload history and summary
                self.load_payment_history()
                self.load_summary()
                
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete {transaction_type.lower()}: {str(e)}")
    
    def edit_transaction(self):
        """Edit selected payment (charges cannot be edited - delete and re-add instead)"""
        selected = self.history_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to edit")
            return
        
        row = selected[0].row()
        transaction_type = self.history_table.item(row, 1).text()
        
        if transaction_type != "PAYMENT":
            QMessageBox.warning(self, "Cannot Edit", "Only payments can be edited. To modify a charge, delete it and add a new one.")
            return
        
        record_id_item = self.history_table.item(row, 7)
        if not record_id_item:
            QMessageBox.warning(self, "Error", "Could not identify payment ID")
            return
        
        record_id = record_id_item.text()
        
        # Load payment details into Add Payment tab
        try:
            cur = self.db.cursor()
            cur.execute("""
                SELECT payment_date, amount, payment_method, transaction_id, notes
                FROM payments
                WHERE payment_id = %s
            """, (record_id,))
            
            payment_data = cur.fetchone()
            cur.close()
            
            if not payment_data:
                QMessageBox.warning(self, "Not Found", "Payment not found")
                return
            
            # Populate form fields
            self.payment_date.setDate(QDate(payment_data[0]))
            self.payment_amount.setValue(float(payment_data[1]))
            
            # Set payment method
            method_text = payment_data[2] or "Cash"
            index = self.payment_method.findText(method_text, Qt.MatchFlag.MatchFixedString)
            if index >= 0:
                self.payment_method.setCurrentIndex(index)
            
            self.payment_reference.setText(payment_data[3] or "")
            self.payment_notes.setPlainText(payment_data[4] or "")
            
            # Store the payment_id for update
            self.editing_payment_id = record_id
            
            # Switch to Add Payment tab and notify user
            QMessageBox.information(self, "Edit Mode", 
                                   "Payment loaded for editing. Modify the fields and click 'Record Payment' to save changes.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load payment: {str(e)}")
    
    def save_contact_info(self):
        """Save client contact information"""
        email = self.client_email.text().strip()
        phone = self.client_phone.text().strip()
        
        if not email and not phone:
            QMessageBox.warning(self, "No Data", "Please enter email or phone number")
            return
        
        try:
            cur = self.db.cursor()
            
            # Update account record with contact info
            if self.client_id:
                cur.execute("""
                    UPDATE accounts
                    SET email = %s, phone = %s, updated_at = NOW()
                    WHERE account_id = %s
                """, (email or None, phone or None, self.client_id))
                
                self.db.commit()
                QMessageBox.information(self, "Success", "Contact information saved")
            else:
                QMessageBox.warning(self, "No Client", "Client ID not available")
                
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save contact info: {str(e)}")
