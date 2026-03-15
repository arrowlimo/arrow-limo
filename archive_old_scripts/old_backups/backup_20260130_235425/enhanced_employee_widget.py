"""
Enhanced Employee List Widget with Comprehensive Drill-Down
Double-click to access full employee details, documents, pay, floats, expenses, lunch tracking
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QComboBox, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from employee_drill_down import EmployeeDetailDialog


class EnhancedEmployeeListWidget(QWidget):
    """
    Employee list with filtering and drill-down access to:
    - All personal data
    - Training & qualifications
    - Documents & forms (view/edit PDFs)
    - Pay advances, vacation, gratuity
    - Tax forms, salary forms
    - Float tracking
    - Expense/receipt accountability
    - Lunch tracking
    """
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._data_loaded = False
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("👥 Employee Management - Enhanced")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Filter by:"))
        
        # Name filter
        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("Name...")
        self.name_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Name:"))
        filter_layout.addWidget(self.name_filter)
        
        # Position filter
        self.position_filter = QComboBox()
        self.position_filter.addItems(["All", "Driver", "Dispatcher", "Manager", "Admin"])
        self.position_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Position:"))
        filter_layout.addWidget(self.position_filter)
        
        # Status filter
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active", "Suspended", "Terminated"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_filter)
        
        # Chauffeur only
        self.chauffeur_only = QCheckBox("Chauffeurs Only")
        self.chauffeur_only.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.chauffeur_only)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Employee table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Employee ID", "Name", "Position", "Hire Date", "Status",
            "Chauffeur", "YTD Pay", "Unreturned Floats", "Missing Receipts"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.on_employee_double_clicked)
        self.table.setSortingEnabled(True)  # ✅ Enable sorting on all columns
        layout.addWidget(self.table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        new_emp_btn = QPushButton("➕ New Employee")
        new_emp_btn.clicked.connect(self.create_new_employee)
        button_layout.addWidget(new_emp_btn)
        
        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.clicked.connect(self.edit_selected)
        button_layout.addWidget(edit_btn)
        
        terminate_btn = QPushButton("❌ Terminate")
        terminate_btn.clicked.connect(self.terminate_selected)
        button_layout.addWidget(terminate_btn)
        
        reports_btn = QPushButton("📊 Generate Reports")
        reports_btn.clicked.connect(self.generate_reports)
        button_layout.addWidget(reports_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_data)
        button_layout.addWidget(refresh_btn)
        
        layout.addLayout(button_layout)
        
        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        # DON'T load data during __init__ - use lazy loading when widget is shown
    
    def showEvent(self, event):
        """Load data when widget is first shown (lazy loading)"""
        super().showEvent(event)
        if not self._data_loaded:
            self.load_data()
            self._data_loaded = True
    
    def load_data(self):
        """Load all employees from database"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
                
            cur = self.db.get_cursor()
            
            # Load employees with aggregated data
            # Filter out garbage records: LEGACY metadata, pure placeholders, etc.
            # Keep only those with real names (not text fragments like PDF captions)
            cur.execute("""
                SELECT 
                    e.employee_id,
                    e.full_name,
                    e.position,
                    e.hire_date,
                    'Active' as status,
                    e.is_chauffeur,
                    COALESCE(SUM(dp.gross_pay), 0) as ytd_pay,
                    0 as unreturned_floats,
                    0 as missing_receipts
                FROM employees e
                LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
                    AND EXTRACT(YEAR FROM dp.pay_date) = EXTRACT(YEAR FROM CURRENT_DATE)
                WHERE 
                    -- Exclude obvious metadata fragments from QB migration
                    e.full_name NOT ILIKE 'PO Box%'
                    AND e.full_name NOT ILIKE '%@%'  -- Raw email addresses
                    AND e.full_name NOT ILIKE 'Phone%'
                    AND e.full_name NOT ILIKE 'Email%'
                    AND e.full_name NOT ILIKE '%Cheque%'
                    AND e.full_name NOT ILIKE 'PAYROLL%'
                    AND e.full_name NOT ILIKE 'REALIZING%'
                    AND e.full_name NOT ILIKE 'RECOGNIZING%'
                    AND e.full_name NOT ILIKE 'Pay period%'
                    AND e.full_name NOT ILIKE 'Driver D%'  -- Placeholder drivers
                    AND TRIM(COALESCE(e.full_name, '')) != ''  -- Not empty
                    AND LENGTH(TRIM(COALESCE(e.full_name, ''))) > 2  -- Not single letters
                    -- Keep employees with business data
                    AND (
                        e.is_chauffeur = true
                        OR e.employee_id IN (SELECT DISTINCT employee_id FROM driver_payroll)
                        OR e.employee_id IN (SELECT DISTINCT assigned_driver_id FROM charters WHERE assigned_driver_id IS NOT NULL)
                        OR e.employee_id IN (SELECT DISTINCT employee_id FROM employee_expenses)
                        OR e.position IS NOT NULL
                    )
                GROUP BY e.employee_id, e.full_name, e.position, e.hire_date, e.is_chauffeur
                ORDER BY e.full_name
            """)
            
            rows = cur.fetchall()
            self.all_data = rows  # Store for filtering
            
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                emp_id, name, position, hire_date, status, is_chauffeur, ytd_pay, floats, missing = row
                
                self.table.setItem(i, 0, QTableWidgetItem(str(emp_id or "")))
                self.table.setItem(i, 1, QTableWidgetItem(str(name or "")))
                self.table.setItem(i, 2, QTableWidgetItem(str(position or "")))
                self.table.setItem(i, 3, QTableWidgetItem(str(hire_date or "")))
                self.table.setItem(i, 4, QTableWidgetItem(str(status or "")))
                self.table.setItem(i, 5, QTableWidgetItem("✓" if is_chauffeur else ""))
                self.table.setItem(i, 6, QTableWidgetItem(f"${float(ytd_pay or 0):,.2f}"))
                self.table.setItem(i, 7, QTableWidgetItem(f"${float(floats or 0):,.2f}"))
                self.table.setItem(i, 8, QTableWidgetItem(str(int(missing or 0))))
                
                # Highlight rows with issues
                if float(floats or 0) > 0:
                    self.table.item(i, 7).setBackground(QColor(255, 200, 200))  # Red for unreturned floats
                if int(missing or 0) > 0:
                    self.table.item(i, 8).setBackground(QColor(255, 200, 200))  # Red for missing receipts
            
            self.status_label.setText(f"Loaded {len(rows)} employees")
            cur.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load employees: {e}")
            self.status_label.setText(f"Error: {e}")
    
    def apply_filters(self):
        """Apply filters to table"""
        name_filter = self.name_filter.text().lower()
        position_filter = self.position_filter.currentText()
        status_filter = self.status_filter.currentText()
        chauffeur_only = self.chauffeur_only.isChecked()
        
        visible_count = 0
        for i in range(self.table.rowCount()):
            name = self.table.item(i, 1).text().lower()
            position = self.table.item(i, 2).text()
            status = self.table.item(i, 4).text()
            is_chauffeur = bool(self.table.item(i, 5).text())
            
            # Apply filters
            show = True
            
            if name_filter and name_filter not in name:
                show = False
            
            if position_filter != "All" and position_filter.lower() not in position.lower():
                show = False
            
            if status_filter != "All" and status != status_filter:
                show = False
            
            if chauffeur_only and not is_chauffeur:
                show = False
            
            self.table.setRowHidden(i, not show)
            if show:
                visible_count += 1
        
        self.status_label.setText(f"Showing {visible_count} of {self.table.rowCount()} employees")
    
    def on_employee_double_clicked(self, index):
        """Open employee detail on double-click"""
        row = index.row()
        if row >= 0:
            emp_id = self.table.item(row, 0).text()
            self.open_employee_detail(emp_id)
    
    def open_employee_detail(self, employee_id):
        """Open employee detail dialog"""
        dialog = EmployeeDetailDialog(self.db, employee_id, self)
        result = dialog.exec()
        if result:
            self.load_data()  # Refresh after changes
    
    def create_new_employee(self):
        """Create new employee"""
        dialog = EmployeeDetailDialog(self.db, None, self)
        result = dialog.exec()
        if result:
            self.load_data()
    
    def edit_selected(self):
        """Edit selected employee"""
        row = self.table.currentRow()
        if row >= 0:
            emp_id = self.table.item(row, 0).text()
            self.open_employee_detail(emp_id)
        else:
            QMessageBox.warning(self, "Warning", "Please select an employee first")
    
    def terminate_selected(self):
        """Terminate selected employee"""
        row = self.table.currentRow()
        if row >= 0:
            emp_id = self.table.item(row, 0).text()
            emp_name = self.table.item(row, 1).text()
            reply = QMessageBox.question(
                self, "Confirm", 
                f"Terminate employee {emp_name} (ID: {emp_id})?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    cur = self.db.get_cursor()
                    cur.execute("UPDATE employees SET employment_status = 'Terminated' WHERE employee_id = %s",
                               (emp_id,))
                    self.db.commit()
                    QMessageBox.information(self, "Success", f"Employee {emp_name} terminated")
                    self.load_data()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to terminate employee: {e}")
                    self.db.rollback()
        else:
            QMessageBox.warning(self, "Warning", "Please select an employee first")
    
    def generate_reports(self):
        """Generate employee reports"""
        QMessageBox.information(self, "Info", "Report generation (to be implemented)")
