"""
Split Receipt Manager Widget - CRA audit-compliant split receipt allocation UI
Shows side-by-side splits with real-time validation and bank/cashbox reconciliation
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QSpinBox, QComboBox, QMessageBox,
    QHeaderView, QDoubleSpinBox, QCheckBox, QTabWidget, QWidget,
    QFormLayout, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont
import psycopg2
from typing import List, Dict, Tuple
from decimal import Decimal
from desktop_app.banking_transaction_picker_dialog import BankingTransactionPickerDialog

class SplitReceiptManagerDialog(QDialog):
    """Popup dialog for managing receipt splits with real-time validation."""
    
    splits_saved = pyqtSignal(int)  # receipt_id
    
    def __init__(self, conn: psycopg2.extensions.connection, receipt_id: int, receipt_data: Dict = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.receipt_id = receipt_id
        self.setWindowTitle(f"Split Receipt Manager - Receipt #{receipt_id}")
        self.setGeometry(100, 100, 1400, 800)
        self.setModal(True)
        
        # Use provided receipt_data or load it
        if receipt_data:
            self.receipt_data = receipt_data
        else:
            self.receipt_data = self._load_receipt()
        
        if not self.receipt_data:
            QMessageBox.critical(self, "Error", f"Receipt #{receipt_id} not found")
            self.reject()
            return
        
        try:
            self._build_ui()
            self._load_splits()
        except Exception as e:
            print(f"Error building split manager UI: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to initialize split manager: {e}")
            self.reject()
    
    def _load_receipt(self) -> Dict:
        """Load receipt details."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
                       payment_method, gl_account_code, description
                FROM receipts WHERE receipt_id = %s
            """, (self.receipt_id,))
            row = cur.fetchone()
            cur.close()
            if row:
                return {
                    'id': row[0], 'date': row[1], 'vendor': row[2], 'amount': row[3],
                    'payment_method': row[4], 'gl_code': row[5], 'desc': row[6]
                }
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading receipt: {e}")
        return None
    
    def _build_ui(self):
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
        save_all_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
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
        form.addRow("Date:", QLabel(str(self.receipt_data['date'])))
        form.addRow("Vendor:", QLabel(self.receipt_data['vendor']))
        
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
        
        info = QLabel("Allocate receipt to GL codes. Amounts must sum to receipt total. ✅ = valid")
        layout.addWidget(info)
        
        # Splits table
        self.splits_table = QTableWidget()
        self.splits_table.setColumnCount(5)
        self.splits_table.setHorizontalHeaderLabels([
            "GL Code", "Amount", "Payment Method", "Notes", "Actions"
        ])
        self.splits_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.splits_table)
        
        # Add split button
        add_btn = QPushButton("➕ Add Split")
        add_btn.clicked.connect(self._add_split_row)
        layout.addWidget(add_btn)
        
        # Validation message
        self.splits_validation_label = QLabel("🔴 Splits do not sum to receipt total")
        self.splits_validation_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.splits_validation_label)
        
        return widget
    
    def _build_banking_tab(self) -> QWidget:
        """Build banking transaction linking tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Link receipt to banking transactions. Total must match receipt amount.")
        layout.addWidget(info)
        
        # Banking links table
        self.banking_table = QTableWidget()
        self.banking_table.setColumnCount(5)
        self.banking_table.setHorizontalHeaderLabels([
            "Transaction Date", "Description", "Amount", "Status", "Actions"
        ])
        self.banking_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.banking_table)
        
        # Link banking button
        link_btn = QPushButton("🔗 Link Banking Transaction")
        link_btn.clicked.connect(self._link_banking)
        layout.addWidget(link_btn)
        
        # Validation
        self.banking_validation_label = QLabel("🔴 Not matched to banking")
        self.banking_validation_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.banking_validation_label)
        
        return widget
    
    def _build_cashbox_tab(self) -> QWidget:
        """Build cash box tracking tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Track cash portions. Driver name required for float/reimbursement entries.")
        layout.addWidget(info)
        
        form = QFormLayout()
        
        # Cash amount
        form.addRow("Cash Amount:", QLabel(f"${self.receipt_data['amount']:.2f}"))
        
        # Driver dropdown
        self.cashbox_driver = QComboBox()
        self._load_drivers_for_cashbox()
        form.addRow("Driver:", self.cashbox_driver)
        
        # Float/Reimbursement type
        self.cashbox_type = QComboBox()
        self.cashbox_type.addItems(["float_out", "reimbursed", "cash_received", "other"])
        form.addRow("Type:", self.cashbox_type)
        
        # Notes
        self.cashbox_notes = QLineEdit()
        self.cashbox_notes.setPlaceholderText("Driver notes, float purpose, etc.")
        form.addRow("Notes:", self.cashbox_notes)
        
        layout.addLayout(form)
        
        # Confirmation checkbox
        self.cashbox_confirmed = QCheckBox("Confirmed - Driver signed off")
        layout.addWidget(self.cashbox_confirmed)
        
        # Validation
        self.cashbox_validation_label = QLabel("🔴 Cash not confirmed")
        self.cashbox_validation_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.cashbox_validation_label)
        
        layout.addStretch()
        return widget
    
    def _load_splits(self):
        """Load existing splits from database."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT split_id, split_order, gl_code, amount, payment_method, notes
                FROM receipt_splits
                WHERE receipt_id = %s
                ORDER BY split_order
            """, (self.receipt_id,))
            rows = cur.fetchall()
            cur.close()
            
            self.splits_table.setRowCount(len(rows))
            for r, (split_id, order, gl, amt, method, notes) in enumerate(rows):
                self.splits_table.setItem(r, 0, QTableWidgetItem(str(order)))
                self.splits_table.setItem(r, 1, QTableWidgetItem(gl or ""))
                self.splits_table.setItem(r, 2, QTableWidgetItem(f"{amt:.2f}"))
                self.splits_table.setItem(r, 3, QTableWidgetItem(method or ""))
                self.splits_table.setItem(r, 4, QTableWidgetItem(notes or ""))
                
                del_btn = QPushButton("🗑")
                del_btn.clicked.connect(lambda checked, rid=split_id: self._delete_split(rid))
                self.splits_table.setCellWidget(r, 5, del_btn)
            
            self._validate_splits()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading splits: {e}")
    
    def _load_drivers_for_cashbox(self):
        """Load drivers dropdown."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT employee_id, first_name || ' ' || last_name FROM employees ORDER BY first_name")
            self.cashbox_driver.addItem("", None)
            for emp_id, name in cur.fetchall():
                self.cashbox_driver.addItem(name, emp_id)
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading drivers: {e}")
    
    def _validate_splits(self):
        """Validate that splits sum to receipt total."""
        total_split = 0.0
        for r in range(self.splits_table.rowCount()):
            amt_item = self.splits_table.item(r, 2)
            if amt_item:
                try:
                    total_split += float(amt_item.text())
                except:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    pass
        
        receipt_amt = float(self.receipt_data['amount'])
        variance = abs(total_split - receipt_amt)
        
        if variance < 0.01:
            self.splits_validation_label.setText(f"✅ Splits validated (${total_split:.2f} = ${receipt_amt:.2f})")
            self.splits_validation_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.splits_validation_label.setText(f"🔴 Variance: ${variance:.2f} (Need ${ receipt_amt - total_split:.2f})")
            self.splits_validation_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _add_split_row(self):
        """Add a new split row."""
        row = self.splits_table.rowCount()
        self.splits_table.insertRow(row)
        
        # Column 0: GL Code (dropdown)
        gl_combo = QComboBox()
        gl_codes = self._get_gl_codes()
        gl_combo.addItems(gl_codes)
        self.splits_table.setCellWidget(row, 0, gl_combo)
        
        # Column 1: Amount (text field)
        self.splits_table.setItem(row, 1, QTableWidgetItem(""))
        
        # Column 2: Payment Method (dropdown with choices)
        method_combo = QComboBox()
        payment_methods = ["cash", "check", "debit/credit_card", "bank_transfer", "gift_card", "personal", "trade_of_services", "unknown"]
        method_combo.addItems(payment_methods)
        current_method = self.receipt_data.get('payment_method', 'cash') if self.receipt_data else 'cash'
        # Map database values to combined option
        if current_method in ('debit_card', 'credit_card'):
            current_method = 'debit/credit_card'
        if method_combo.findText(current_method) >= 0:
            method_combo.setCurrentText(current_method)
        else:
            method_combo.setCurrentText('cash')
        self.splits_table.setCellWidget(row, 2, method_combo)
        
        # Column 3: Notes (text field)
        self.splits_table.setItem(row, 3, QTableWidgetItem(""))
        
        # Column 4: Delete button
        del_btn = QPushButton("🗑")
        del_btn.clicked.connect(lambda checked, r=row: self._delete_split_row(r))
        self.splits_table.setCellWidget(row, 4, del_btn)
    
    def _get_gl_codes(self) -> list:
        """Get list of available GL codes from database with descriptions."""
        try:
            cur = self.conn.cursor()
            # Get GL codes with their descriptions from gl_transactions
            cur.execute("""
                SELECT DISTINCT r.gl_account_code, g.account_name
                FROM receipts r
                LEFT JOIN gl_transactions g ON r.gl_account_code = g.account_name
                WHERE r.gl_account_code IS NOT NULL 
                ORDER BY r.gl_account_code
            """)
            codes = cur.fetchall()
            cur.close()
            
            if codes:
                # Format as "CODE - Description" for display
                formatted = [f"{code[0]} - {code[1] if code[1] else ''}" for code in codes]
                return formatted
            else:
                return ["-- Select GL Code --"]
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading GL codes: {e}")
            return ["-- Select GL Code --"]
    
    def _delete_split_row(self, row: int):
        """Delete a split row."""
        self.splits_table.removeRow(row)
        self._validate_splits()
    
    def _delete_split(self, split_id: int):
        """Delete a split from database."""
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM receipt_splits WHERE split_id = %s", (split_id,))
            self.conn.commit()
            cur.close()
            self._load_splits()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Could not delete split: {e}")
    
    def _link_banking(self):
        """Link to banking transaction using the picker dialog."""
        try:
            # Launch banking transaction picker
            picker = BankingTransactionPickerDialog(
                self.conn,
                self.receipt_id,
                self.receipt_data['amount']
            )
            
            if picker.exec() == QDialog.DialogCode.Accepted:
                result = picker.get_result()
                if result:
                    txn_id, linked_amount = result
                    
                    # Add to banking table display
                    cur = self.conn.cursor()
                    cur.execute("""
                        SELECT transaction_date, description, debit, credit
                        FROM banking_transactions WHERE transaction_id = %s
                    """, (txn_id,))
                    txn_row = cur.fetchone()
                    cur.close()
                    
                    if txn_row:
                        row = self.banking_table.rowCount()
                        self.banking_table.insertRow(row)
                        
                        self.banking_table.setItem(row, 0, QTableWidgetItem(str(txn_row[0])))
                        self.banking_table.setItem(row, 1, QTableWidgetItem(txn_row[1] or ""))
                        self.banking_table.setItem(row, 2, QTableWidgetItem(f"${linked_amount:,.2f}"))
                        self.banking_table.setItem(row, 3, QTableWidgetItem("✅ Linked"))
                        
                        # Unlink button
                        unlink_btn = QPushButton("🔌 Unlink")
                        unlink_btn.clicked.connect(lambda: self._unlink_banking_transaction(txn_id, row))
                        self.banking_table.setCellWidget(row, 4, unlink_btn)
                        
                        # Update validation
                        self._validate_banking_amounts()
                        QMessageBox.information(self, "Success", f"Banking transaction #{txn_id} linked!")
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Could not link banking transaction:\n{e}")
    
    def _unlink_banking_transaction(self, txn_id: int, row: int):
        """Unlink a banking transaction."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                DELETE FROM receipt_banking_links
                WHERE receipt_id = %s AND transaction_id = %s
            """, (self.receipt_id, txn_id))
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = NULL, reconciliation_status = NULL
                WHERE transaction_id = %s
            """, (txn_id,))
            self.conn.commit()
            cur.close()
            
            self.banking_table.removeRow(row)
            self._validate_banking_amounts()
            QMessageBox.information(self, "Success", "Banking transaction unlinked!")
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Could not unlink transaction:\n{e}")
    
    def _save_single_split(self):
        """Save all splits (same as 'Save All & Reconcile')."""
        self._save_all_splits()
    
    def _save_all_splits(self):
        """Save all splits by deleting parent, creating child receipts with same split_group_id."""
        try:
            # Validate first
            self._validate_splits()
            if "green" not in self.splits_validation_label.styleSheet():
                QMessageBox.warning(self, "Validation Error", "Splits must sum to receipt total before saving")
                return
            
            cur = self.conn.cursor()
            
            # Original receipt will be used as the split_group_id
            # All children get the same split_group_id = original receipt_id
            split_group_id = self.receipt_id
            original_total = self.receipt_data['amount']
            
            # Create child receipts for each split
            child_count = 0
            child_ids = []
            
            for r in range(self.splits_table.rowCount()):
                # Column 0 is now GL Code (ComboBox)
                gl_widget = self.splits_table.cellWidget(r, 0)
                gl_display = gl_widget.currentText().strip() if gl_widget else ""
                # Extract GL code from "CODE - Description" format
                gl = gl_display.split(" - ")[0].strip() if " - " in gl_display else gl_display
                
                # Column 1 is Amount
                amt_text = self.splits_table.item(r, 1).text().strip()
                
                # Column 2 is Payment Method (ComboBox)
                method_widget = self.splits_table.cellWidget(r, 2)
                payment_method = method_widget.currentText() if method_widget else self.receipt_data.get('payment_method', 'cash')
                
                # Column 3 is Notes/Category
                category = self.splits_table.item(r, 3).text().strip() or None
                
                if gl and amt_text and gl != "-- Select GL Code --":
                    try:
                        amt = float(amt_text)
                        
                        # Create new child receipt with same split_group_id and is_split_receipt=true
                        cur.execute("""
                            INSERT INTO receipts 
                            (receipt_date, vendor_name, gross_amount, gl_account_code, 
                             description, payment_method, split_group_id, is_split_receipt,
                             split_group_total)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING receipt_id
                        """, (
                            self.receipt_data['date'],
                            self.receipt_data['vendor'],
                            amt,
                            gl,
                            f"Split portion (GL: {gl})",
                            payment_method,
                            split_group_id,  # All children get original receipt_id
                            True,             # Mark as split receipt
                            original_total    # Store original combined amount for searching
                        ))
                        
                        child_id = cur.fetchone()[0]
                        child_count += 1
                        child_ids.append(child_id)
                        
                        # Also create entry in receipt_splits for tracking
                        cur.execute("""
                            INSERT INTO receipt_splits 
                            (parent_id, child_id, child_amount, child_category)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            self.receipt_id,
                            child_id,
                            amt,
                            category
                        ))
                        
                    except Exception as e:
                        try:
                            self.db.rollback()
                        except:
                            pass
                        print(f"Error creating child receipt: {e}")
                        raise
            
            # Now DELETE the original parent receipt (was causing accounting issues)
            cur.execute("""
                DELETE FROM receipt_splits WHERE parent_id = %s OR child_id = %s
            """, (self.receipt_id, self.receipt_id))
            
            cur.execute("""
                DELETE FROM receipts WHERE receipt_id = %s
            """, (self.receipt_id,))
            
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(
                self, "Success", 
                f"✅ Receipt #{self.receipt_id} split into {child_count} linked receipts!\n\n"
                f"Child receipts: {', '.join(f'#{cid}' for cid in child_ids)}\n"
                f"All share Group ID {split_group_id}\n\n"
                f"Original receipt #{self.receipt_id} has been deleted (no longer confuses accounting)\n"
                "Click any child receipt to see the full group."
            )
            self.splits_saved.emit(self.receipt_id)
            self.accept()
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Error", f"Could not save splits: {e}")
            print(f"Split save error: {e}")
            import traceback
            traceback.print_exc()
