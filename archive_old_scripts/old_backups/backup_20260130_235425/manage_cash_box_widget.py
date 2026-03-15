"""
Manage Cash Box - Track Cash Box Deposits and Withdrawals
"""
import psycopg2
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QMessageBox,
    QDoubleSpinBox
)

from desktop_app.common_widgets import StandardDateEdit
from desktop_app.print_export_helper import PrintExportHelper


class ManageCashBoxWidget(QWidget):
    """Browse and manage cash box transactions."""
    
    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._build_ui()
        self._load_transactions()
    
    def _build_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        
        # Filter section
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Transaction Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Deposit", "Withdrawal"])
        self.type_filter.setMaximumWidth(150)
        filter_layout.addWidget(self.type_filter)
        
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
        self.amount_min.setRange(0, 999999)
        self.amount_min.setMaximumWidth(80)
        filter_layout.addWidget(self.amount_min)
        
        filter_layout.addWidget(QLabel("to"))
        self.amount_max = QDoubleSpinBox()
        self.amount_max.setRange(0, 999999)
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
        print_btn.clicked.connect(lambda: PrintExportHelper.print_preview(self.table, "Cash Box Transactions", self))
        results_toolbar.addWidget(print_btn)
        
        export_csv_btn = QPushButton("💾 Export CSV")
        export_csv_btn.clicked.connect(lambda: PrintExportHelper.export_csv(self.table, "Cash Box Transactions", parent=self))
        results_toolbar.addWidget(export_csv_btn)
        
        export_excel_btn = QPushButton("📊 Export Excel")
        export_excel_btn.clicked.connect(lambda: PrintExportHelper.export_excel(self.table, "Cash Box Transactions", parent=self))
        results_toolbar.addWidget(export_excel_btn)
        
        layout.addLayout(results_toolbar)
        
        # Results table
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Type", "Amount", "Description", "Running Balance"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
    
    def _load_transactions(self):
        """Load cash box transactions with applied filters."""
        try:
            txn_type = self.type_filter.currentText()
            desc = (self.desc_filter.text() or "").strip()
            date_from = self.date_from.getDate()
            date_to = self.date_to.getDate()
            amount_min = self.amount_min.value()
            amount_max = self.amount_max.value()
            
            sql = [
                "SELECT id, transaction_date, type, amount, description,",
                "       SUM(CASE WHEN type = 'Deposit' THEN amount ELSE -amount END)",
                "       OVER (ORDER BY transaction_date, id) AS running_balance",
                "FROM cash_box_transactions",
                "WHERE 1=1"
            ]
            params = []
            
            if txn_type != "All":
                sql.append("AND type = %s")
                params.append(txn_type)
            
            if desc:
                sql.append("AND LOWER(description) LIKE LOWER(%s)")
                params.append(f"%{desc}%")
            
            if date_from:
                sql.append("AND transaction_date >= %s")
                params.append(date_from)
            
            if date_to:
                sql.append("AND transaction_date <= %s")
                params.append(date_to)
            
            if amount_min > 0 or amount_max < 999999:
                sql.append("AND amount BETWEEN %s AND %s")
                params.extend([float(amount_min), float(amount_max)])
            
            sql.append("ORDER BY transaction_date DESC, id DESC LIMIT 500")
            
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()
            
            self._populate_table(rows)
            self.results_label.setText(f"Transactions: {len(rows)} rows")
            
        except psycopg2.errors.UndefinedTable:
            QMessageBox.warning(self, "Info", "Cash box transactions table does not exist yet.")
            self.table.setRowCount(0)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load transactions:\n{e}")
    
    def _populate_table(self, rows):
        """Populate the table with cash box transaction data."""
        self.table.setRowCount(len(rows))
        
        for r, row in enumerate(rows):
            txn_id, txn_date, txn_type, amount, desc, balance = row
            
            self.table.setItem(r, 0, QTableWidgetItem(str(txn_id)))
            self.table.setItem(r, 1, QTableWidgetItem(str(txn_date)))
            
            type_item = QTableWidgetItem(txn_type or "")
            if txn_type == "Deposit":
                type_item.setBackground(QColor(200, 255, 200))
            elif txn_type == "Withdrawal":
                type_item.setBackground(QColor(255, 200, 200))
            self.table.setItem(r, 2, type_item)
            
            amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount else "")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 3, amt_item)
            
            self.table.setItem(r, 4, QTableWidgetItem(desc or ""))
            
            balance_item = QTableWidgetItem(f"${balance:,.2f}" if balance else "")
            balance_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 5, balance_item)
    
    def _clear_filters(self):
        """Clear all filter fields."""
        self.type_filter.setCurrentIndex(0)
        self.desc_filter.clear()
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.amount_min.setValue(0)
        self.amount_max.setValue(999999)
        self._load_transactions()
