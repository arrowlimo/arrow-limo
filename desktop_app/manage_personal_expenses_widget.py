"""
Manage Personal Expenses - Track Employee Personal Expenses and Reimbursements
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


class ManagePersonalExpensesWidget(QWidget):
    """Browse and manage employee personal expenses."""
    
    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._build_ui()
        self._load_employees()
        self._load_expenses()
    
    def _build_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        
        # Filter section
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Employee:"))
        self.employee_filter = QComboBox()
        self.employee_filter.setMaximumWidth(200)
        filter_layout.addWidget(self.employee_filter)
        
        filter_layout.addWidget(QLabel("Category:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.setMaximumWidth(150)
        filter_layout.addWidget(self.category_filter)
        
        filter_layout.addWidget(QLabel("Date Range:"))
        self.date_from = StandardDateEdit(allow_blank=True)
        self.date_from.setMaximumWidth(100)
        filter_layout.addWidget(self.date_from)
        
        filter_layout.addWidget(QLabel("to"))
        self.date_to = StandardDateEdit(allow_blank=True)
        self.date_to.setMaximumWidth(100)
        filter_layout.addWidget(self.date_to)
        
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Pending", "Approved", "Reimbursed"])
        self.status_filter.setMaximumWidth(120)
        filter_layout.addWidget(self.status_filter)
        
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
        search_btn.clicked.connect(self._load_expenses)
        filter_layout.addWidget(search_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)
        
        layout.addLayout(filter_layout)
        
        # Results section
        results_toolbar = QHBoxLayout()
        self.results_label = QLabel("Expenses: 0")
        results_toolbar.addWidget(self.results_label)
        results_toolbar.addStretch()
        
        # Print/Export buttons
        print_btn = QPushButton("🖨️ Print Preview")
        print_btn.clicked.connect(lambda: PrintExportHelper.print_preview(self.table, "Personal Expenses", self))
        results_toolbar.addWidget(print_btn)
        
        export_csv_btn = QPushButton("💾 Export CSV")
        export_csv_btn.clicked.connect(lambda: PrintExportHelper.export_csv(self.table, "Personal Expenses", parent=self))
        results_toolbar.addWidget(export_csv_btn)
        
        export_excel_btn = QPushButton("📊 Export Excel")
        export_excel_btn.clicked.connect(lambda: PrintExportHelper.export_excel(self.table, "Personal Expenses", parent=self))
        results_toolbar.addWidget(export_excel_btn)
        
        layout.addLayout(results_toolbar)
        
        # Results table
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Employee", "Category", "Amount", "Status", "Description", "Notes"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
    
    def _load_employees(self):
        """Load employees for filter dropdown."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT DISTINCT pe.employee_id, e.first_name, e.last_name
                FROM personal_expenses pe
                LEFT JOIN employees e ON e.employee_id = pe.employee_id
                WHERE pe.employee_id IS NOT NULL
                ORDER BY COALESCE(e.first_name, '') || ' ' || COALESCE(e.last_name, '')
            """)
            employees = cur.fetchall()
            cur.close()
            
            self.employee_filter.addItem("All Employees", None)
            for emp_id, first, last in employees:
                name = f"{first} {last}".strip() if first or last else f"ID: {emp_id}"
                self.employee_filter.addItem(name, emp_id)
        except psycopg2.errors.UndefinedTable:
            self.employee_filter.addItem("Table not found", None)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading employees: {e}")
    
    def _load_expenses(self):
        """Load personal expenses with applied filters."""
        try:
            emp_id = self.employee_filter.currentData()
            category = self.category_filter.currentText()
            status = self.status_filter.currentText()
            desc = (self.desc_filter.text() if hasattr(self, 'desc_filter') else "").strip()
            date_from = self.date_from.getDate()
            date_to = self.date_to.getDate()
            amount_min = self.amount_min.value()
            amount_max = self.amount_max.value()
            
            sql = [
                "SELECT pe.id, pe.expense_date, COALESCE(e.first_name || ' ' || e.last_name, 'Unknown') AS employee,",
                "       COALESCE(pe.category, '') AS category, pe.amount,",
                "       COALESCE(pe.status, 'Pending') AS status,",
                "       COALESCE(pe.description, '') AS description,",
                "       COALESCE(pe.notes, '') AS notes",
                "FROM personal_expenses pe",
                "LEFT JOIN employees e ON e.employee_id = pe.employee_id",
                "WHERE 1=1"
            ]
            params = []
            
            if emp_id:
                sql.append("AND pe.employee_id = %s")
                params.append(emp_id)
            
            if category and category != "All Categories":
                sql.append("AND pe.category = %s")
                params.append(category)
            
            if status != "All":
                sql.append("AND pe.status = %s")
                params.append(status)
            
            if date_from:
                sql.append("AND pe.expense_date >= %s")
                params.append(date_from)
            
            if date_to:
                sql.append("AND pe.expense_date <= %s")
                params.append(date_to)
            
            if amount_min > 0 or amount_max < 999999:
                sql.append("AND pe.amount BETWEEN %s AND %s")
                params.extend([float(amount_min), float(amount_max)])
            
            sql.append("ORDER BY pe.expense_date DESC LIMIT 500")
            
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()
            
            self._populate_table(rows)
            self.results_label.setText(f"Expenses: {len(rows)} rows")
            
        except psycopg2.errors.UndefinedTable:
            QMessageBox.warning(self, "Info", "Personal expenses table does not exist yet.")
            self.table.setRowCount(0)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load expenses:\n{e}")
    
    def _populate_table(self, rows):
        """Populate the table with expense data."""
        self.table.setRowCount(len(rows))
        
        for r, row in enumerate(rows):
            exp_id, exp_date, employee, category, amount, status, desc, notes = row
            
            self.table.setItem(r, 0, QTableWidgetItem(str(exp_id)))
            self.table.setItem(r, 1, QTableWidgetItem(str(exp_date)))
            self.table.setItem(r, 2, QTableWidgetItem(employee or ""))
            self.table.setItem(r, 3, QTableWidgetItem(category or ""))
            
            amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount else "")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(r, 4, amt_item)
            
            status_item = QTableWidgetItem(status or "")
            if status == "Reimbursed":
                status_item.setBackground(QColor(200, 255, 200))
            elif status == "Pending":
                status_item.setBackground(QColor(255, 255, 200))
            self.table.setItem(r, 5, status_item)
            
            self.table.setItem(r, 6, QTableWidgetItem(desc or ""))
            self.table.setItem(r, 7, QTableWidgetItem(notes or ""))
    
    def _clear_filters(self):
        """Clear all filter fields."""
        self.employee_filter.setCurrentIndex(0)
        self.category_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        if hasattr(self, 'desc_filter'):
            self.desc_filter.clear()
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.amount_min.setValue(0)
        self.amount_max.setValue(999999)
        self._load_expenses()
