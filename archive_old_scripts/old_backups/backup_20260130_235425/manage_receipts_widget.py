"""
Manage Receipts - Browse, Filter, and Sort All Receipts
"""
import psycopg2
from decimal import Decimal
from datetime import date
from typing import List

from PyQt6.QtCore import Qt, QDate, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QMessageBox,
    QDateEdit, QDoubleSpinBox, QCheckBox, QSpinBox
)

from desktop_app.common_widgets import StandardDateEdit
from desktop_app.print_export_helper import PrintExportHelper


class ManageReceiptsWidget(QWidget):
    """Browse and filter all receipts with multi-column sorting."""
    
    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.current_sort_col = 1  # Default: Date
        self.sort_descending = True
        self._build_ui()
        self._load_receipts()
    
    def _build_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        
        # Filter section
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Vendor:"))
        self.vendor_filter = QLineEdit()
        self.vendor_filter.setPlaceholderText("Type vendor name...")
        self.vendor_filter.setMaximumWidth(150)
        filter_layout.addWidget(self.vendor_filter)
        
        filter_layout.addWidget(QLabel("Date Range:"))
        self.date_from = StandardDateEdit(allow_blank=True)
        self.date_from.setMaximumWidth(100)
        filter_layout.addWidget(self.date_from)
        
        filter_layout.addWidget(QLabel("to"))
        self.date_to = StandardDateEdit(allow_blank=True)
        self.date_to.setMaximumWidth(100)
        filter_layout.addWidget(self.date_to)
        
        filter_layout.addWidget(QLabel("GL:"))
        self.gl_filter = QLineEdit()
        self.gl_filter.setPlaceholderText("GL code or category...")
        self.gl_filter.setMaximumWidth(120)
        filter_layout.addWidget(self.gl_filter)
        
        filter_layout.addWidget(QLabel("Amount Range:"))
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
        
        filter_layout.addWidget(QLabel("Verified:"))
        self.verified_filter = QComboBox()
        self.verified_filter.addItems(["All", "Verified", "Unverified"])
        self.verified_filter.setMaximumWidth(100)
        filter_layout.addWidget(self.verified_filter)
        
        filter_layout.addStretch()
        
        search_btn = QPushButton("🔍 Search")
        search_btn.clicked.connect(self._load_receipts)
        filter_layout.addWidget(search_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)
        
        layout.addLayout(filter_layout)
        
        # Results section
        results_toolbar = QHBoxLayout()
        self.results_label = QLabel("Receipts: 0")
        results_toolbar.addWidget(self.results_label)
        results_toolbar.addStretch()
        
        # Print/Export buttons
        print_btn = QPushButton("🖨️ Print Preview")
        print_btn.clicked.connect(lambda: PrintExportHelper.print_preview(self.table, "Receipts", self))
        results_toolbar.addWidget(print_btn)
        
        export_csv_btn = QPushButton("💾 Export CSV")
        export_csv_btn.clicked.connect(lambda: PrintExportHelper.export_csv(self.table, "Receipts", parent=self))
        results_toolbar.addWidget(export_csv_btn)
        
        export_excel_btn = QPushButton("📊 Export Excel")
        export_excel_btn.clicked.connect(lambda: PrintExportHelper.export_excel(self.table, "Receipts", parent=self))
        results_toolbar.addWidget(export_excel_btn)
        
        layout.addLayout(results_toolbar)
        
        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Vendor", "Amount", "GL Account", 
            "Category", "Banking ID", "Matched", "Verified", "Verified At", "Description", "Fiscal Year"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        
        # Enable multi-column sorting
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_changed)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
    
    def _load_receipts(self):
        """Load receipts with applied filters."""
        try:
            vendor = (self.vendor_filter.text() or "").strip()
            gl = (self.gl_filter.text() or "").strip()
            date_from = self.date_from.getDate()
            date_to = self.date_to.getDate()
            amount_min = self.amount_min.value()
            amount_max = self.amount_max.value()
            
            sql = [
                "SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,",
                "       COALESCE(r.gl_account_name, r.gl_account_code, '') AS gl_name,",
                "       COALESCE(r.category, '') AS category,",
                "       COALESCE(r.banking_transaction_id::TEXT, '') AS banking_id,",
                "       CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'Yes' ELSE 'No' END AS matched,",
                "       COALESCE(r.verified_by_edit, FALSE) AS verified,",
                "       r.verified_at,",
                "       COALESCE(r.description, '') AS description,",
                "       COALESCE(r.fiscal_year::TEXT, '') AS fiscal_year",
                "FROM receipts r",
                "WHERE 1=1"
            ]
            params = []
            
            if vendor:
                sql.append("AND LOWER(r.vendor_name) LIKE LOWER(%s)")
                params.append(f"%{vendor}%")
            
            if gl:
                sql.append("AND (LOWER(r.gl_account_name) LIKE LOWER(%s) OR LOWER(r.gl_account_code) LIKE LOWER(%s))")
                params.extend([f"%{gl}%", f"%{gl}%"])
            
            if date_from:
                sql.append("AND r.receipt_date >= %s")
                params.append(date_from)
            
            if date_to:
                sql.append("AND r.receipt_date <= %s")
                params.append(date_to)
            
            if amount_min > 0 or amount_max < 999999:
                sql.append("AND r.gross_amount BETWEEN %s AND %s")
                params.extend([float(amount_min), float(amount_max)])
            
            verified_status = self.verified_filter.currentText()
            if verified_status == "Verified":
                sql.append("AND r.verified_by_edit = TRUE")
            elif verified_status == "Unverified":
                sql.append("AND (r.verified_by_edit = FALSE OR r.verified_by_edit IS NULL)")
            
            sql.append("ORDER BY r.receipt_date DESC, r.receipt_id DESC LIMIT 500")
            
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()
            
            # Calculate verification stats
            verified_count = sum(1 for row in rows if row[8])  # verified is column 8
            unverified_count = len(rows) - verified_count
            
            self._populate_table(rows)
            self.results_label.setText(
                f"Receipts: {len(rows)} rows | ✅ Verified: {verified_count} | ⚠️ Unverified: {unverified_count}"
            )
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load receipts:\n{e}")
    
    def _populate_table(self, rows):
        """Populate the table with receipt data."""
        self.table.setRowCount(len(rows))
        
        for r, row in enumerate(rows):
            rid, rdate, vendor, amount, gl_name, category, banking_id, matched, verified, verified_at, desc, fiscal_yr = row
            
            self.table.setItem(r, 0, QTableWidgetItem(str(rid)))
            self.table.setItem(r, 1, QTableWidgetItem(str(rdate)))
            self.table.setItem(r, 2, QTableWidgetItem(vendor or ""))
            
            amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount else "")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 3, amt_item)
            
            self.table.setItem(r, 4, QTableWidgetItem(gl_name or ""))
            self.table.setItem(r, 5, QTableWidgetItem(category or ""))
            self.table.setItem(r, 6, QTableWidgetItem(banking_id or ""))
            
            matched_item = QTableWidgetItem(matched)
            if matched == "Yes":
                matched_item.setBackground(QColor(200, 255, 200))
            self.table.setItem(r, 7, matched_item)
            
            # Verified status
            verified_text = "✅ Yes" if verified else "⚠️ No"
            verified_item = QTableWidgetItem(verified_text)
            if verified:
                verified_item.setBackground(QColor(220, 255, 220))  # Light green
            else:
                verified_item.setBackground(QColor(255, 255, 220))  # Light yellow
            self.table.setItem(r, 8, verified_item)
            
            # Verified timestamp
            verified_at_text = str(verified_at)[:19] if verified_at else ""
            self.table.setItem(r, 9, QTableWidgetItem(verified_at_text))
            
            self.table.setItem(r, 10, QTableWidgetItem(desc or ""))
            self.table.setItem(r, 11, QTableWidgetItem(fiscal_yr or ""))
    
    def _clear_filters(self):
        """Clear all filter fields."""
        self.vendor_filter.clear()
        self.gl_filter.clear()
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.amount_min.setValue(0)
        self.amount_max.setValue(999999)
        self.verified_filter.setCurrentIndex(0)
        self._load_receipts()
    
    def _on_sort_changed(self, col, order):
        """Handle column header sort click."""
        self._load_receipts()  # Reload with current sort
