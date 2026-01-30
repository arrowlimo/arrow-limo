#!/usr/bin/env python3
"""
Vendor Payables Dashboard Widget for Desktop App
Shows top outstanding vendor balances with drill-down to ledgers.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import psycopg2
from decimal import Decimal


class VendorPayablesDashboard(QWidget):
    """Dashboard showing top vendor payables with drill-down."""
    
    vendor_selected = pyqtSignal(str, int)  # canonical_vendor, account_id
    
    def __init__(self, db_config: dict, parent=None):
        super().__init__(parent)
        self.db_config = db_config
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Vendor Payables Dashboard")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Summary stats
        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            'Vendor', 'Total Due', '0-30 Days', '31-60 Days', '61-90 Days', '90+ Days'
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_vendor_double_clicked)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        btn_layout.addWidget(self.refresh_btn)
        
        self.view_ledger_btn = QPushButton("View Ledger")
        self.view_ledger_btn.clicked.connect(self.view_selected_ledger)
        btn_layout.addWidget(self.view_ledger_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def load_data(self):
        """Load vendor payables data from database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Get aging data
            from datetime import date, timedelta
            today = date.today()
            days_30 = today - timedelta(days=30)
            days_60 = today - timedelta(days=60)
            days_90 = today - timedelta(days=90)
            
            # vendor_accounts table doesn't exist - using simplified query with receipts
            cur.execute("""
                SELECT 
                    canonical_vendor,
                    COUNT(*) as invoice_count,
                    COALESCE(SUM(gross_amount), 0) as balance,
                    MAX(receipt_date) as last_invoice_date
                FROM receipts
                WHERE canonical_vendor IS NOT NULL
                GROUP BY canonical_vendor
                ORDER BY balance DESC
            """) 
                            ELSE 0 
                        END), 0) as current_0_30,
                        COALESCE(SUM(CASE 
                            WHEN val.entry_type = 'INVOICE' AND val.entry_date BETWEEN %s AND %s THEN val.amount 
                            ELSE 0 
                        END), 0) as days_31_60,
                        COALESCE(SUM(CASE 
                            WHEN val.entry_type = 'INVOICE' AND val.entry_date BETWEEN %s AND %s THEN val.amount 
                            ELSE 0 
                        END), 0) as days_61_90,
                        COALESCE(SUM(CASE 
                            WHEN val.entry_type = 'INVOICE' AND val.entry_date < %s THEN val.amount 
                            ELSE 0 
                        END), 0) as days_90_plus
                    FROM latest_balance lb
                    LEFT JOIN vendor_account_ledger val ON val.account_id = lb.account_id
                    GROUP BY lb.account_id, lb.canonical_vendor, lb.balance
                )
                SELECT * FROM aging_buckets
                ORDER BY balance DESC
                LIMIT 50
            """, (days_30, days_60, days_30, days_90, days_60, days_90))
            
            rows = cur.fetchall()
            
            # Update table
            self.table.setRowCount(len(rows))
            total_due = Decimal('0.00')
            
            for i, row in enumerate(rows):
                account_id, vendor, balance, c30, d60, d90, d90p = row
                balance = Decimal(str(balance))
                total_due += balance
                
                # Store account_id in row
                self.table.setItem(i, 0, QTableWidgetItem(vendor))
                self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, account_id)
                
                # Amounts
                self.table.setItem(i, 1, QTableWidgetItem(f"${balance:,.2f}"))
                self.table.setItem(i, 2, QTableWidgetItem(f"${Decimal(str(c30)):,.2f}"))
                self.table.setItem(i, 3, QTableWidgetItem(f"${Decimal(str(d60)):,.2f}"))
                self.table.setItem(i, 4, QTableWidgetItem(f"${Decimal(str(d90)):,.2f}"))
                self.table.setItem(i, 5, QTableWidgetItem(f"${Decimal(str(d90p)):,.2f}"))
                
                # Highlight 90+ days in red
                if Decimal(str(d90p)) > 0:
                    self.table.item(i, 5).setForeground(QColor(200, 0, 0))
            
            # Update summary
            self.summary_label.setText(
                f"Total Outstanding: ${total_due:,.2f} | Vendors: {len(rows)}"
            )
            
            cur.close()
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load vendor data:\n{e}")
    
    def on_vendor_double_clicked(self, index):
        """Handle double-click on vendor row."""
        self.view_selected_ledger()
    
    def view_selected_ledger(self):
        """Emit signal to view ledger for selected vendor."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a vendor first.")
            return
        
        row = selected[0].row()
        vendor_item = self.table.item(row, 0)
        vendor = vendor_item.text()
        account_id = vendor_item.data(Qt.ItemDataRole.UserRole)
        
        self.vendor_selected.emit(vendor, account_id)


# Example usage / integration point
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    db_config = {
        'host': 'localhost',
        'dbname': 'almsdata',
        'user': 'postgres',
        'password': '***REMOVED***'
    }
    
    widget = VendorPayablesDashboard(db_config)
    widget.vendor_selected.connect(lambda v, a: print(f"Selected: {v} (ID: {a})"))
    widget.show()
    
    sys.exit(app.exec())
