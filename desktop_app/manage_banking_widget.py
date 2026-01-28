"""
Manage Banking Transactions - Browse, Filter, and Link Banking Records
"""
import psycopg2
from datetime import date

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QMessageBox,
    QDoubleSpinBox
)

from desktop_app.common_widgets import StandardDateEdit
from desktop_app.print_export_helper import PrintExportHelper


class ManageBankingWidget(QWidget):
    """Browse and filter banking transactions with receipt linking."""
    
    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._build_ui()
        self._load_accounts()
        self._load_transactions()
    
    def _build_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        
        # Filter section
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Account:"))
        self.account_filter = QComboBox()
        self.account_filter.setMaximumWidth(200)
        filter_layout.addWidget(self.account_filter)
        
        filter_layout.addWidget(QLabel("Date Range:"))
        self.date_from = StandardDateEdit(allow_blank=True)
        self.date_from.setMaximumWidth(100)
        filter_layout.addWidget(self.date_from)
        
        filter_layout.addWidget(QLabel("to"))
        self.date_to = StandardDateEdit(allow_blank=True)
        self.date_to.setMaximumWidth(100)
        filter_layout.addWidget(self.date_to)
        
        filter_layout.addWidget(QLabel("Description:"))
        self.desc_filter = QLineEdit()
        self.desc_filter.setPlaceholderText("Search description...")
        self.desc_filter.setMaximumWidth(150)
        filter_layout.addWidget(self.desc_filter)
        
        filter_layout.addWidget(QLabel("Amount:"))
        self.amount_min = QDoubleSpinBox()
        self.amount_min.setRange(-999999, 999999)
        self.amount_min.setMaximumWidth(80)
        filter_layout.addWidget(self.amount_min)
        
        filter_layout.addWidget(QLabel("to"))
        self.amount_max = QDoubleSpinBox()
        self.amount_max.setRange(-999999, 999999)
        self.amount_max.setValue(999999)
        self.amount_max.setMaximumWidth(80)
        filter_layout.addWidget(self.amount_max)
        
        filter_layout.addStretch()
        
        search_btn = QPushButton("🔍 Search")
        search_btn.clicked.connect(self._load_transactions)
        filter_layout.addWidget(search_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)
        
        layout.addLayout(filter_layout)
        
        # Results section
        results_toolbar = QHBoxLayout()
        self.results_label = QLabel("Transactions: 0")
        results_toolbar.addWidget(self.results_label)
        results_toolbar.addStretch()
        
        # Print/Export buttons
        print_btn = QPushButton("🖨️ Print Preview")
        print_btn.clicked.connect(lambda: PrintExportHelper.print_preview(self.table, "Banking Transactions", self))
        results_toolbar.addWidget(print_btn)
        
        export_csv_btn = QPushButton("💾 Export CSV")
        export_csv_btn.clicked.connect(lambda: PrintExportHelper.export_csv(self.table, "Banking Transactions", parent=self))
        results_toolbar.addWidget(export_csv_btn)
        
        export_excel_btn = QPushButton("📊 Export Excel")
        export_excel_btn.clicked.connect(lambda: PrintExportHelper.export_excel(self.table, "Banking Transactions", parent=self))
        results_toolbar.addWidget(export_excel_btn)
        
        layout.addLayout(results_toolbar)
        
        # Results table
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Description", "Debit", "Credit", 
            "Balance", "Linked Receipts", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
    
    def _load_accounts(self):
        """Load bank accounts for filter dropdown."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT DISTINCT mapped_bank_account_id, account_name 
                FROM banking_transactions 
                WHERE mapped_bank_account_id IS NOT NULL
                ORDER BY account_name
            """)
            accounts = cur.fetchall()
            cur.close()
            
            self.account_filter.addItem("All Accounts", None)
            for acct_id, acct_name in accounts:
                self.account_filter.addItem(f"{acct_name}", acct_id)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading accounts: {e}")
    
    def _load_transactions(self):
        """Load banking transactions with applied filters."""
        try:
            account_id = self.account_filter.currentData()
            desc = (self.desc_filter.text() or "").strip()
            date_from = self.date_from.getDate()
            date_to = self.date_to.getDate()
            amount_min = self.amount_min.value()
            amount_max = self.amount_max.value()
            
            sql = [
                "SELECT bt.transaction_id, bt.transaction_date, bt.description,",
                "       CASE WHEN bt.debit IS NOT NULL THEN bt.debit ELSE 0 END AS debit,",
                "       CASE WHEN bt.credit IS NOT NULL THEN bt.credit ELSE 0 END AS credit,",
                "       COALESCE(bt.balance, 0) AS balance,",
                "       COUNT(DISTINCT r.receipt_id) AS linked_receipt_count,",
                "       bt.status",
                "FROM banking_transactions bt",
                "LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id",
                "WHERE 1=1"
            ]
            params = []
            
            if account_id:
                sql.append("AND bt.mapped_bank_account_id = %s")
                params.append(account_id)
            
            if desc:
                sql.append("AND LOWER(bt.description) LIKE LOWER(%s)")
                params.append(f"%{desc}%")
            
            if date_from:
                sql.append("AND bt.transaction_date >= %s")
                params.append(date_from)
            
            if date_to:
                sql.append("AND bt.transaction_date <= %s")
                params.append(date_to)
            
            if amount_min != 0 or amount_max != 999999:
                sql.append("AND (bt.debit BETWEEN %s AND %s OR bt.credit BETWEEN %s AND %s)")
                params.extend([float(amount_min), float(amount_max), float(amount_min), float(amount_max)])
            
            sql.extend([
                "GROUP BY bt.transaction_id, bt.transaction_date, bt.description,",
                "         bt.debit, bt.credit, bt.balance, bt.status",
                "ORDER BY bt.transaction_date DESC LIMIT 500"
            ])
            
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()
            
            self._populate_table(rows)
            self.results_label.setText(f"Transactions: {len(rows)} rows")
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load transactions:\n{e}")
    
    def _populate_table(self, rows):
        """Populate the table with banking transaction data."""
        self.table.setRowCount(len(rows))
        
        for r, row in enumerate(rows):
            txn_id, txn_date, desc, debit, credit, balance, linked_count, status = row
            
            self.table.setItem(r, 0, QTableWidgetItem(str(txn_id)))
            self.table.setItem(r, 1, QTableWidgetItem(str(txn_date)))
            self.table.setItem(r, 2, QTableWidgetItem(desc or ""))
            
            debit_item = QTableWidgetItem(f"${debit:,.2f}" if debit else "")
            debit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 3, debit_item)
            
            credit_item = QTableWidgetItem(f"${credit:,.2f}" if credit else "")
            credit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 4, credit_item)
            
            balance_item = QTableWidgetItem(f"${balance:,.2f}")
            balance_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 5, balance_item)
            
            linked_item = QTableWidgetItem(str(int(linked_count)))
            if linked_count > 0:
                linked_item.setBackground(QColor(200, 255, 200))
            self.table.setItem(r, 6, linked_item)
            
            status_item = QTableWidgetItem(status or "")
            self.table.setItem(r, 7, status_item)
    
    def _clear_filters(self):
        """Clear all filter fields."""
        self.account_filter.setCurrentIndex(0)
        self.desc_filter.clear()
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.amount_min.setValue(0)
        self.amount_max.setValue(999999)
        self._load_transactions()
