"""
Employee Drill-Down Detail View
Comprehensive employee management with all data, documents, training, pay, floats, expenses
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
    QComboBox, QDialog, QTabWidget, QMessageBox, QSpinBox, QCheckBox,
    QFormLayout, QGroupBox, QScrollArea, QHeaderView, QFileDialog,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QColor, QBrush, QDesktopServices
from desktop_app.common_widgets import StandardDateEdit
import os
import subprocess
from datetime import datetime, timedelta


class EmployeeDetailDialog(QDialog):
    """
    Complete employee master-detail view with:
    - Personal info, qualifications, training
    - Document management (view/edit PDFs)
    - Pay advances, vacation pay, gratuity
    - Tax forms, salary forms
    - Lunch tracking, float tracking
    - Expense/receipt accountability
    """
    
    saved = pyqtSignal(dict)
    
    def __init__(self, db, employee_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.employee_id = employee_id
        self.employee_data = None
        
        self.setWindowTitle(f"Employee Detail - {employee_id or 'New'}")
        self.setGeometry(50, 50, 1400, 900)
        
        layout = QVBoxLayout()
        
        # ===== TOP ACTION BUTTONS (STANDARD LAYOUT) =====
        button_layout = QHBoxLayout()
        
        # Left side: Action-specific buttons (Terminate, Suspend)
        self.terminate_btn = QPushButton("❌ Terminate Employment")
        self.terminate_btn.clicked.connect(self.terminate_employee)
        button_layout.addWidget(self.terminate_btn)
        
        self.suspend_btn = QPushButton("⏸️ Suspend Employee")
        self.suspend_btn.clicked.connect(self.suspend_employee)
        button_layout.addWidget(self.suspend_btn)
        
        button_layout.addStretch()
        
        # Right side: Standard drill-down buttons (Add, Duplicate, Delete, Save, Close)
        self.add_new_btn = QPushButton("➕ Add New")
        self.add_new_btn.clicked.connect(self.add_new_employee)
        button_layout.addWidget(self.add_new_btn)
        
        self.duplicate_btn = QPushButton("📋 Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_employee)
        button_layout.addWidget(self.duplicate_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_employee)
        button_layout.addWidget(self.delete_btn)
        
        self.save_btn = QPushButton("💾 Save All Changes")
        self.save_btn.clicked.connect(self.save_employee)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # ===== COMPLIANCE SUMMARY CARDS =====
        self.summary_layout = self._create_compliance_summary()
        layout.addLayout(self.summary_layout)
        
        # ===== TABS =====
        tabs = QTabWidget()
        
        tabs.addTab(self.create_personal_tab(), "👤 Personal Info")
        tabs.addTab(self.create_employment_tab(), "💼 Employment")
        tabs.addTab(self.create_training_tab(), "🎓 Training & Qualifications")
        tabs.addTab(self.create_documents_tab(), "📄 Documents & Forms")
        tabs.addTab(self.create_pay_tab(), "💰 Pay & Advances")
        tabs.addTab(self.create_deductions_tab(), "🧾 Deductions & Tax")
        tabs.addTab(self.create_floats_tab(), "💵 Floats & Cash")
        tabs.addTab(self.create_expenses_tab(), "🧾 Expenses & Receipts")
        tabs.addTab(self.create_lunch_tab(), "🍔 Lunch Tracking")
        tabs.addTab(self.create_vehicle_qualifications_tab(), "🚗 Vehicle Qualifications")
        tabs.addTab(self.create_provincial_rules_tab(), "📋 Provincial Rules")
        tabs.addTab(self.create_red_deer_bylaws_tab(), "🏛️ Red Deer Bylaws")
        tabs.addTab(self.create_hos_tab(), "⏱️ Hours of Service")
        tabs.addTab(self.create_performance_tab(), "⭐ Performance")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
        
        if employee_id:
            self.load_employee_data()
    
    def _create_compliance_summary(self):
        """Create compliance status summary cards"""
        card_layout = QHBoxLayout()
        
        # Status card
        self.status_card = QLabel("✅ Active\nSince: Loading...")
        self.status_card.setStyleSheet("""
            background-color: #27ae60; color: white; padding: 8px 10px;
            border-radius: 5px; font-weight: bold; font-size: 9pt;
        """)
        self.status_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_card)
        
        # Expiry alerts card
        self.expiry_card = QLabel("⏰ Expiry Status\nChecking...")
        self.expiry_card.setStyleSheet("""
            background-color: #95a5a6; color: white; padding: 8px 10px;
            border-radius: 5px; font-weight: bold; font-size: 9pt;
        """)
        self.expiry_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.expiry_card)
        
        # Training card
        self.training_card = QLabel("🎓 Training\nLoading...")
        self.training_card.setStyleSheet("""
            background-color: #3498db; color: white; padding: 8px 10px;
            border-radius: 5px; font-weight: bold; font-size: 9pt;
        """)
        self.training_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.training_card)
        
        # Financial card
        self.financial_card = QLabel("💵 Financials\nLoading...")
        self.financial_card.setStyleSheet("""
            background-color: #f39c12; color: white; padding: 8px 10px;
            border-radius: 5px; font-weight: bold; font-size: 9pt;
        """)
        self.financial_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.financial_card)
        
        return card_layout
    
    def _update_compliance_cards(self):
        """Update compliance summary cards with real data"""
        if not self.employee_id:
            return
        
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
            
            # Status card
            cur.execute("""
                SELECT status, hire_date 
                FROM employees 
                WHERE employee_id = %s
            """, (self.employee_id,))
            result = cur.fetchone()
            if result:
                status, hire_date = result
                status_emoji = "✅" if status == 'active' else "❌" if status == 'inactive' else "⏸️"
                status_color = "#27ae60" if status == 'active' else "#e74c3c" if status == 'inactive' else "#f39c12"
                hire_text = f"Since: {hire_date}" if hire_date else "No hire date"
                self.status_card.setText(f"{status_emoji} {status.title()}\n{hire_text}")
                self.status_card.setStyleSheet(f"""
                    background-color: {status_color}; color: white; padding: 15px;
                    border-radius: 8px; font-weight: bold; font-size: 11pt;
                """)
            
            # Expiry alerts
            cur.execute("""
                SELECT COUNT(*) 
                FROM driver_documents 
                WHERE employee_id = %s 
                AND expiry_date IS NOT NULL 
                AND expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            """, (self.employee_id,))
            expiring_count = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM driver_documents 
                WHERE employee_id = %s 
                AND expiry_date IS NOT NULL 
                AND expiry_date < CURRENT_DATE
            """, (self.employee_id,))
            expired_count = cur.fetchone()[0] or 0
            
            if expired_count > 0:
                self.expiry_card.setText(f"🔴 {expired_count} EXPIRED\n❗ URGENT ACTION")
                self.expiry_card.setStyleSheet("""
                    background-color: #e74c3c; color: white; padding: 15px;
                    border-radius: 8px; font-weight: bold; font-size: 11pt;
                """)
            elif expiring_count > 0:
                self.expiry_card.setText(f"⚠️ {expiring_count} Expiring\nNext 30 Days")
                self.expiry_card.setStyleSheet("""
                    background-color: #f39c12; color: white; padding: 15px;
                    border-radius: 8px; font-weight: bold; font-size: 11pt;
                """)
            else:
                self.expiry_card.setText(f"✅ All Current\nNo Expiries")
                self.expiry_card.setStyleSheet("""
                    background-color: #27ae60; color: white; padding: 15px;
                    border-radius: 8px; font-weight: bold; font-size: 11pt;
                """)
            
            # Training count
            cur.execute("""
                SELECT COUNT(*) 
                FROM driver_documents 
                WHERE employee_id = %s AND document_type = 'TRAINING'
            """, (self.employee_id,))
            training_count = cur.fetchone()[0] or 0
            self.training_card.setText(f"🎓 {training_count} Training\nRecords")
            
            # Floats outstanding
            cur.execute("""
                SELECT COALESCE(SUM(amount_issued), 0) 
                FROM driver_floats 
                WHERE employee_id = %s AND status = 'Outstanding'
            """, (self.employee_id,))
            float_total = cur.fetchone()[0] or 0
            
            if float_total > 0:
                self.financial_card.setText(f"💵 ${float_total:.2f}\nFloats Out")
                self.financial_card.setStyleSheet("""
                    background-color: #e67e22; color: white; padding: 15px;
                    border-radius: 8px; font-weight: bold; font-size: 11pt;
                """)
            else:
                self.financial_card.setText(f"✅ $0.00\nNo Floats")
            
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error updating compliance cards: {e}")
    
    def create_personal_tab(self):
        """Tab 1: Personal information"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Personal Information")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout()
        
        # Basic info
        self.emp_id = QLineEdit()
        self.emp_id.setReadOnly(True)
        form.addRow("Employee ID:", self.emp_id)
        
        self.full_name = QLineEdit()
        form.addRow("Full Name:", self.full_name)
        
        self.sin = QLineEdit()
        self.sin.setMaxLength(11)
        form.addRow("SIN:", self.sin)
        
        self.dob = StandardDateEdit(prefer_month_text=True)
        self.dob.setCalendarPopup(True)
        form.addRow("Date of Birth:", self.dob)
        
        self.address = QLineEdit()
        form.addRow("Address:", self.address)
        
        self.city = QLineEdit()
        form.addRow("City:", self.city)
        
        self.postal_code = QLineEdit()
        form.addRow("Postal Code:", self.postal_code)
        
        self.phone = QLineEdit()
        form.addRow("Phone:", self.phone)
        
        self.email = QLineEdit()
        form.addRow("Email:", self.email)
        
        self.emergency_contact = QLineEdit()
        form.addRow("Emergency Contact:", self.emergency_contact)
        
        self.emergency_phone = QLineEdit()
        form.addRow("Emergency Phone:", self.emergency_phone)
        
        form_widget.setLayout(form)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_employment_tab(self):
        """Tab 2: Employment details"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Employment Information")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        form = QFormLayout()
        
        self.hire_date = StandardDateEdit(prefer_month_text=True)
        self.hire_date.setCalendarPopup(True)
        form.addRow("Hire Date:", self.hire_date)
        
        self.position = QLineEdit()
        form.addRow("Position:", self.position)
        
        self.is_chauffeur = QCheckBox("Chauffeur/Driver")
        form.addRow("Role:", self.is_chauffeur)
        
        self.employment_status = QComboBox()
        self.employment_status.addItems(["Active", "Suspended", "Terminated", "On Leave"])
        form.addRow("Status:", self.employment_status)
        
        self.hourly_rate = QDoubleSpinBox()
        self.hourly_rate.setMaximum(999.99)
        self.hourly_rate.setDecimals(2)
        form.addRow("Hourly Rate:", self.hourly_rate)
        
        self.salary = QDoubleSpinBox()
        self.salary.setMaximum(999999.99)
        self.salary.setDecimals(2)
        form.addRow("Annual Salary:", self.salary)
        
        self.vacation_days = QSpinBox()
        self.vacation_days.setMaximum(365)
        form.addRow("Vacation Days/Year:", self.vacation_days)
        
        self.vacation_used = QSpinBox()
        self.vacation_used.setMaximum(365)
        self.vacation_used.setReadOnly(True)
        form.addRow("Vacation Days Used:", self.vacation_used)
        
        layout.addLayout(form)
        widget.setLayout(layout)
        return widget
    
    def create_training_tab(self):
        """Tab 3: Training and qualifications"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Training & Qualifications")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Training records table
        training_label = QLabel("Training Records:")
        layout.addWidget(training_label)
        
        self.training_table = QTableWidget()
        self.training_table.setColumnCount(6)
        self.training_table.setHorizontalHeaderLabels([
            "Course Name", "Date Completed", "Expiry Date", "Certificate #", "Status", "Actions"
        ])
        layout.addWidget(self.training_table)
        
        # Add training buttons
        train_btn_layout = QHBoxLayout()
        add_train_btn = QPushButton("➕ Add Training")
        add_train_btn.clicked.connect(self.add_training)
        train_btn_layout.addWidget(add_train_btn)
        
        edit_train_btn = QPushButton("✏️ Edit Selected")
        edit_train_btn.clicked.connect(self.edit_training)
        train_btn_layout.addWidget(edit_train_btn)
        
        train_btn_layout.addStretch()
        layout.addLayout(train_btn_layout)
        
        # Qualifications/Licenses
        qual_label = QLabel("Licenses & Certifications:")
        layout.addWidget(qual_label)
        
        self.qual_table = QTableWidget()
        self.qual_table.setColumnCount(5)
        self.qual_table.setHorizontalHeaderLabels([
            "Type", "License #", "Issue Date", "Expiry Date", "Status"
        ])
        layout.addWidget(self.qual_table)
        
        # Add qualification buttons
        qual_btn_layout = QHBoxLayout()
        add_qual_btn = QPushButton("➕ Add License/Cert")
        add_qual_btn.clicked.connect(self.add_qualification)
        qual_btn_layout.addWidget(add_qual_btn)
        qual_btn_layout.addStretch()
        layout.addLayout(qual_btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_documents_tab(self):
        """Tab 4: Document management - view/edit PDFs"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Documents & Forms")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Search and filter
        search_layout = QHBoxLayout()
        self.doc_search = QLineEdit()
        self.doc_search.setPlaceholderText("🔍 Search documents...")
        self.doc_search.textChanged.connect(self._filter_documents)
        search_layout.addWidget(self.doc_search)
        
        self.doc_type_filter = QComboBox()
        self.doc_type_filter.addItems(["All Types", "LICENSE", "TRAINING", "T4", "Employment", "Police Check", "Other"])
        self.doc_type_filter.currentTextChanged.connect(self._filter_documents)
        search_layout.addWidget(self.doc_type_filter)
        
        self.doc_sort = QComboBox()
        self.doc_sort.addItems(["Sort: Name", "Sort: Upload Date", "Sort: Expiry Date"])
        self.doc_sort.currentTextChanged.connect(self._filter_documents)
        search_layout.addWidget(self.doc_sort)
        
        layout.addLayout(search_layout)
        
        # Document list
        self.doc_list = QListWidget()
        self.doc_list.doubleClicked.connect(self.open_document)
        layout.addWidget(self.doc_list)
        
        # Document buttons
        doc_btn_layout = QHBoxLayout()
        
        upload_doc_btn = QPushButton("📤 Upload Document")
        upload_doc_btn.clicked.connect(self.upload_document)
        doc_btn_layout.addWidget(upload_doc_btn)
        
        view_doc_btn = QPushButton("👁️ View Selected")
        view_doc_btn.clicked.connect(self.view_document)
        doc_btn_layout.addWidget(view_doc_btn)
        
        edit_doc_btn = QPushButton("✏️ Edit PDF (Fill Form)")
        edit_doc_btn.clicked.connect(self.edit_document)
        doc_btn_layout.addWidget(edit_doc_btn)
        
        delete_doc_btn = QPushButton("🗑️ Delete Selected")
        delete_doc_btn.clicked.connect(self.delete_document)
        doc_btn_layout.addWidget(delete_doc_btn)
        
        layout.addLayout(doc_btn_layout)
        
        # Document types available
        form_types = QGroupBox("Generate Forms:")
        form_layout = QHBoxLayout()
        
        t4_btn = QPushButton("T4 Form")
        t4_btn.clicked.connect(lambda: self.generate_form("T4"))
        form_layout.addWidget(t4_btn)
        
        t4a_btn = QPushButton("T4A Form")
        t4a_btn.clicked.connect(lambda: self.generate_form("T4A"))
        form_layout.addWidget(t4a_btn)
        
        td1_btn = QPushButton("TD1 Form")
        td1_btn.clicked.connect(lambda: self.generate_form("TD1"))
        form_layout.addWidget(td1_btn)
        
        employment_btn = QPushButton("Employment Contract")
        employment_btn.clicked.connect(lambda: self.generate_form("Employment"))
        form_layout.addWidget(employment_btn)
        
        roe_btn = QPushButton("ROE (Record of Employment)")
        roe_btn.clicked.connect(lambda: self.generate_form("ROE"))
        form_layout.addWidget(roe_btn)
        
        form_types.setLayout(form_layout)
        layout.addWidget(form_types)
        
        widget.setLayout(layout)
        return widget
    
    def create_pay_tab(self):
        """Tab 5: Pay history and advances"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Pay & Advances")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Pay history
        pay_label = QLabel("Pay History:")
        layout.addWidget(pay_label)
        
        self.pay_table = QTableWidget()
        self.pay_table.setColumnCount(7)
        self.pay_table.setHorizontalHeaderLabels([
            "Pay Date", "Gross Pay", "Deductions", "Net Pay", "Charters", "YTD Gross", "YTD Net"
        ])
        layout.addWidget(self.pay_table)
        
        # Pay advances
        advance_label = QLabel("Pay Advances:")
        layout.addWidget(advance_label)
        
        self.advance_table = QTableWidget()
        self.advance_table.setColumnCount(6)
        self.advance_table.setHorizontalHeaderLabels([
            "Date", "Amount", "Reason", "Repaid", "Balance", "Status"
        ])
        layout.addWidget(self.advance_table)
        
        # Add advance button
        advance_btn_layout = QHBoxLayout()
        add_advance_btn = QPushButton("➕ Record Advance")
        add_advance_btn.clicked.connect(self.add_advance)
        advance_btn_layout.addWidget(add_advance_btn)
        
        repay_advance_btn = QPushButton("💵 Record Repayment")
        repay_advance_btn.clicked.connect(self.repay_advance)
        advance_btn_layout.addWidget(repay_advance_btn)
        
        advance_btn_layout.addStretch()
        layout.addLayout(advance_btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_deductions_tab(self):
        """Tab 6: Deductions, gratuity, tax info"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Deductions & Tax Information")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Standard deductions
        deduct_group = QGroupBox("Standard Deductions")
        deduct_form = QFormLayout()
        
        self.cpp_rate = QDoubleSpinBox()
        self.cpp_rate.setDecimals(2)
        deduct_form.addRow("CPP Rate (%):", self.cpp_rate)
        
        self.ei_rate = QDoubleSpinBox()
        self.ei_rate.setDecimals(2)
        deduct_form.addRow("EI Rate (%):", self.ei_rate)
        
        self.tax_rate = QDoubleSpinBox()
        self.tax_rate.setDecimals(2)
        deduct_form.addRow("Income Tax Rate (%):", self.tax_rate)
        
        deduct_group.setLayout(deduct_form)
        layout.addWidget(deduct_group)
        
        # Gratuity tracking
        grat_label = QLabel("Gratuity/Tips Tracking:")
        layout.addWidget(grat_label)
        
        self.gratuity_table = QTableWidget()
        self.gratuity_table.setColumnCount(5)
        self.gratuity_table.setHorizontalHeaderLabels([
            "Date", "Charter", "Gratuity Amount", "Split %", "Employee Share"
        ])
        layout.addWidget(self.gratuity_table)
        
        # Custom deductions
        custom_deduct_label = QLabel("Custom Deductions:")
        layout.addWidget(custom_deduct_label)
        
        self.custom_deduct_table = QTableWidget()
        self.custom_deduct_table.setColumnCount(5)
        self.custom_deduct_table.setHorizontalHeaderLabels([
            "Type", "Amount", "Frequency", "Start Date", "End Date"
        ])
        layout.addWidget(self.custom_deduct_table)
        
        # Add deduction button
        deduct_btn = QPushButton("➕ Add Custom Deduction")
        deduct_btn.clicked.connect(self.add_custom_deduction)
        layout.addWidget(deduct_btn)
        
        widget.setLayout(layout)
        return widget
    
    def create_floats_tab(self):
        """Tab 7: Cash floats tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Cash Floats Tracking")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Summary
        summary_layout = QHBoxLayout()
        self.total_floats_label = QLabel("Total Floats Out: $0.00")
        self.unreturned_floats_label = QLabel("Unreturned: $0.00")
        summary_layout.addWidget(self.total_floats_label)
        summary_layout.addWidget(self.unreturned_floats_label)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)
        
        # Floats table
        self.float_table = QTableWidget()
        self.float_table.setColumnCount(7)
        self.float_table.setHorizontalHeaderLabels([
            "Date Issued", "Amount", "Purpose", "Date Returned", "Receipts Submitted", "Variance", "Status"
        ])
        layout.addWidget(self.float_table)
        
        # Float buttons
        float_btn_layout = QHBoxLayout()
        
        issue_float_btn = QPushButton("➕ Issue Float")
        issue_float_btn.clicked.connect(self.issue_float)
        float_btn_layout.addWidget(issue_float_btn)
        
        return_float_btn = QPushButton("✅ Return Float")
        return_float_btn.clicked.connect(self.return_float)
        float_btn_layout.addWidget(return_float_btn)
        
        submit_receipts_btn = QPushButton("🧾 Submit Receipts")
        submit_receipts_btn.clicked.connect(self.submit_receipts)
        float_btn_layout.addWidget(submit_receipts_btn)
        
        float_btn_layout.addStretch()
        layout.addLayout(float_btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_expenses_tab(self):
        """Tab 8: Expense claims and receipt tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Expenses & Receipt Accountability")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Expense claims table
        self.expense_table = QTableWidget()
        self.expense_table.setColumnCount(7)
        self.expense_table.setHorizontalHeaderLabels([
            "Date", "Category", "Amount", "Receipt?", "Receipt #", "Approved", "Reimbursed"
        ])
        layout.addWidget(self.expense_table)
        
        # Expense buttons
        expense_btn_layout = QHBoxLayout()
        
        add_expense_btn = QPushButton("➕ Submit Expense")
        add_expense_btn.clicked.connect(self.add_expense)
        expense_btn_layout.addWidget(add_expense_btn)
        
        attach_receipt_btn = QPushButton("📎 Attach Receipt")
        attach_receipt_btn.clicked.connect(self.attach_receipt)
        expense_btn_layout.addWidget(attach_receipt_btn)
        
        approve_expense_btn = QPushButton("✅ Approve Selected")
        approve_expense_btn.clicked.connect(self.approve_expense)
        expense_btn_layout.addWidget(approve_expense_btn)
        
        expense_btn_layout.addStretch()
        layout.addLayout(expense_btn_layout)
        
        # Missing receipts alert
        missing_label = QLabel("⚠️ Expenses Without Receipts:")
        missing_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(missing_label)
        
        self.missing_receipts_table = QTableWidget()
        self.missing_receipts_table.setColumnCount(4)
        self.missing_receipts_table.setHorizontalHeaderLabels([
            "Date", "Category", "Amount", "Days Overdue"
        ])
        layout.addWidget(self.missing_receipts_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_lunch_tab(self):
        """Tab 9: Lunch tracking (what they had)"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Lunch & Meal Tracking")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        info = QLabel("Track employee meals for reimbursement or company-provided lunches")
        layout.addWidget(info)
        
        # Lunch table
        self.lunch_table = QTableWidget()
        self.lunch_table.setColumnCount(6)
        self.lunch_table.setHorizontalHeaderLabels([
            "Date", "Meal Type", "Location/Vendor", "Cost", "Reimbursable", "Notes"
        ])
        layout.addWidget(self.lunch_table)
        
        # Lunch buttons
        lunch_btn_layout = QHBoxLayout()
        
        add_lunch_btn = QPushButton("➕ Add Meal Entry")
        add_lunch_btn.clicked.connect(self.add_lunch)
        lunch_btn_layout.addWidget(add_lunch_btn)
        
        lunch_btn_layout.addStretch()
        layout.addLayout(lunch_btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_vehicle_qualifications_tab(self):
        """Tab: Vehicle type qualifications"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Vehicle Type Qualifications")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        info = QLabel("Select which vehicle types this driver is qualified to operate:")
        layout.addWidget(info)
        
        # Qualification checkboxes
        qual_group = QGroupBox("Qualified Vehicle Types")
        qual_layout = QVBoxLayout()
        
        self.qual_sedan = QCheckBox("🚗 Sedan (Standard passenger cars)")
        self.qual_suv = QCheckBox("🚙 SUV (Sport utility vehicles)")
        self.qual_van = QCheckBox("🚐 Van (Passenger vans, sprinters)")
        self.qual_stretch = QCheckBox("🚖 Stretch Limo (Extended limousines)")
        self.qual_bus = QCheckBox("🚌 Bus (Charter buses, mini-buses)")
        self.qual_specialty = QCheckBox("✨ Specialty (Hummer, exotic vehicles)")
        self.qual_wheelchair = QCheckBox("♿ Wheelchair Accessible (WAV equipped)")
        
        for checkbox in [self.qual_sedan, self.qual_suv, self.qual_van, 
                        self.qual_stretch, self.qual_bus, self.qual_specialty, self.qual_wheelchair]:
            qual_layout.addWidget(checkbox)
        
        qual_group.setLayout(qual_layout)
        layout.addWidget(qual_group)
        
        # Endorsements
        endorse_group = QGroupBox("Special Endorsements")
        endorse_layout = QVBoxLayout()
        
        self.endorse_airbrake = QCheckBox("Air Brake Endorsement")
        self.endorse_hazmat = QCheckBox("Hazardous Materials (if applicable)")
        self.endorse_passenger = QCheckBox("Passenger Endorsement")
        
        for checkbox in [self.endorse_airbrake, self.endorse_hazmat, self.endorse_passenger]:
            endorse_layout.addWidget(checkbox)
        
        endorse_group.setLayout(endorse_layout)
        layout.addWidget(endorse_group)
        
        # Notes
        notes_label = QLabel("Qualification Notes:")
        layout.addWidget(notes_label)
        
        self.qual_notes = QTextEdit()
        self.qual_notes.setPlaceholderText("Special training, restrictions, or comments...")
        self.qual_notes.setMaximumHeight(80)
        layout.addWidget(self.qual_notes)
        
        # Save button
        save_qual_btn = QPushButton("💾 Save Qualifications")
        save_qual_btn.clicked.connect(self._save_vehicle_qualifications)
        layout.addWidget(save_qual_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _save_vehicle_qualifications(self):
        """Save vehicle qualifications to database"""
        if not self.employee_id:
            return
        
        try:
            qualified_types = []
            if self.qual_sedan.isChecked(): qualified_types.append('Sedan')
            if self.qual_suv.isChecked(): qualified_types.append('SUV')
            if self.qual_van.isChecked(): qualified_types.append('Van')
            if self.qual_stretch.isChecked(): qualified_types.append('Stretch Limo')
            if self.qual_bus.isChecked(): qualified_types.append('Bus')
            if self.qual_specialty.isChecked(): qualified_types.append('Specialty')
            if self.qual_wheelchair.isChecked(): qualified_types.append('Wheelchair Accessible')
            
            endorsements = []
            if self.endorse_airbrake.isChecked(): endorsements.append('Air Brake')
            if self.endorse_hazmat.isChecked(): endorsements.append('HazMat')
            if self.endorse_passenger.isChecked(): endorsements.append('Passenger')
            
            # Store as JSON in employee notes or create dedicated table
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
            
            # For now, store in notes field - TODO: create employee_vehicle_qualifications table
            qual_text = f"""\n\n--- VEHICLE QUALIFICATIONS ---\nQualified Types: {', '.join(qualified_types)}\nEndorsements: {', '.join(endorsements)}\nNotes: {self.qual_notes.toPlainText()}\nUpdated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
            
            cur.execute("""
                UPDATE employees 
                SET notes = COALESCE(notes, '') || %s
                WHERE employee_id = %s
            """, (qual_text, self.employee_id))
            
            self.db.commit()
            cur.close()
            QMessageBox.information(self, "Success", "Vehicle qualifications saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            self.db.rollback()
    
    def create_provincial_rules_tab(self):
        """Tab: Alberta Provincial Compliance"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Alberta Provincial Rules & Compliance")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_layout = QVBoxLayout()
        
        # Driver Licensing Requirements
        license_group = QGroupBox("Driver Licensing (Alberta Transportation)")
        license_layout = QVBoxLayout()
        
        self.prov_class4 = QCheckBox("Class 4 License (Required for passenger transport)")
        self.prov_medical = QCheckBox("Medical Examination (every 2-5 years depending on age)")
        self.prov_abstract = QCheckBox("Driver's Abstract (clean record required)")
        self.prov_criminal_check = QCheckBox("Enhanced Criminal Record Check (RCMP)")
        
        for cb in [self.prov_class4, self.prov_medical, self.prov_abstract, self.prov_criminal_check]:
            license_layout.addWidget(cb)
        
        license_group.setLayout(license_layout)
        form_layout.addWidget(license_group)
        
        # Insurance Requirements
        insurance_group = QGroupBox("Insurance & Liability")
        insurance_layout = QVBoxLayout()
        
        self.prov_commercial_insurance = QCheckBox("Commercial Vehicle Insurance (minimum $2M liability)")
        self.prov_insurance_cert = QCheckBox("Insurance Certificate on File")
        self.prov_wcb = QCheckBox("WCB Coverage (if applicable)")
        
        for cb in [self.prov_commercial_insurance, self.prov_insurance_cert, self.prov_wcb]:
            insurance_layout.addWidget(cb)
        
        insurance_group.setLayout(insurance_layout)
        form_layout.addWidget(insurance_group)
        
        # Safety Requirements
        safety_group = QGroupBox("Safety & Training")
        safety_layout = QVBoxLayout()
        
        self.prov_first_aid = QCheckBox("First Aid Training (recommended)")
        self.prov_defensive_driving = QCheckBox("Defensive Driving Course")
        self.prov_fatigue_mgmt = QCheckBox("Fatigue Management Training")
        self.prov_passenger_safety = QCheckBox("Passenger Safety Procedures")
        
        for cb in [self.prov_first_aid, self.prov_defensive_driving, self.prov_fatigue_mgmt, self.prov_passenger_safety]:
            safety_layout.addWidget(cb)
        
        safety_group.setLayout(safety_layout)
        form_layout.addWidget(safety_group)
        
        # Carrier Requirements
        carrier_group = QGroupBox("Carrier Service Rules")
        carrier_layout = QVBoxLayout()
        
        self.prov_nsc = QCheckBox("NSC (National Safety Code) Compliance")
        self.prov_vehicle_inspection = QCheckBox("Daily Vehicle Inspection Reports (DVIR)")
        self.prov_maintenance_records = QCheckBox("Maintenance Records Available")
        self.prov_trip_inspection = QCheckBox("Trip Inspection Requirements Met")
        
        for cb in [self.prov_nsc, self.prov_vehicle_inspection, self.prov_maintenance_records, self.prov_trip_inspection]:
            carrier_layout.addWidget(cb)
        
        carrier_group.setLayout(carrier_layout)
        form_layout.addWidget(carrier_group)
        
        # Save button
        save_btn = QPushButton("💾 Save Provincial Compliance")
        save_btn.clicked.connect(self._save_provincial_compliance)
        form_layout.addWidget(save_btn)
        
        form_widget.setLayout(form_layout)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_red_deer_bylaws_tab(self):
        """Tab: Red Deer Municipal Bylaws"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Red Deer Municipal Bylaw Compliance")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_layout = QVBoxLayout()
        
        # Business License
        license_group = QGroupBox("Business & Operating Licenses")
        license_layout = QVBoxLayout()
        
        self.rd_business_license = QCheckBox("City of Red Deer Business License (Annual Renewal)")
        self.rd_business_license_expiry = StandardDateEdit()
        self.rd_business_license_expiry.setPlaceholderText("Expiry Date")
        lic_layout1 = QHBoxLayout()
        lic_layout1.addWidget(self.rd_business_license)
        lic_layout1.addWidget(QLabel("Expires:"))
        lic_layout1.addWidget(self.rd_business_license_expiry)
        license_layout.addLayout(lic_layout1)
        
        self.rd_chauffeur_permit = QCheckBox("Chauffeur Permit (Red Deer Bylaw 3205/2012)")
        self.rd_chauffeur_permit_expiry = StandardDateEdit()
        self.rd_chauffeur_permit_expiry.setPlaceholderText("Expiry Date")
        lic_layout2 = QHBoxLayout()
        lic_layout2.addWidget(self.rd_chauffeur_permit)
        lic_layout2.addWidget(QLabel("Expires:"))
        lic_layout2.addWidget(self.rd_chauffeur_permit_expiry)
        license_layout.addLayout(lic_layout2)
        
        self.rd_vehicle_license = QCheckBox("Vehicle-for-Hire License (per vehicle)")
        self.rd_vehicle_license_expiry = StandardDateEdit()
        self.rd_vehicle_license_expiry.setPlaceholderText("Expiry Date")
        lic_layout3 = QHBoxLayout()
        lic_layout3.addWidget(self.rd_vehicle_license)
        lic_layout3.addWidget(QLabel("Expires:"))
        lic_layout3.addWidget(self.rd_vehicle_license_expiry)
        license_layout.addLayout(lic_layout3)
        
        self.rd_permit_display = QCheckBox("Permit Displayed in Vehicle (visible to passengers)")
        license_layout.addWidget(self.rd_permit_display)
        
        license_group.setLayout(license_layout)
        form_layout.addWidget(license_group)
        
        # Driver Requirements (Red Deer Specific)
        driver_group = QGroupBox("Red Deer Driver Requirements")
        driver_layout = QVBoxLayout()
        
        self.rd_police_check = QCheckBox("Police Information Check (within 6 months of application)")
        self.rd_police_check_date = StandardDateEdit()
        self.rd_police_check_date.setPlaceholderText("Check Date")
        drv_layout1 = QHBoxLayout()
        drv_layout1.addWidget(self.rd_police_check)
        drv_layout1.addWidget(QLabel("Checked:"))
        drv_layout1.addWidget(self.rd_police_check_date)
        driver_layout.addLayout(drv_layout1)
        
        self.rd_driver_abstract = QCheckBox("Driver's Abstract (less than 30 days old)")
        self.rd_driver_abstract_date = StandardDateEdit()
        self.rd_driver_abstract_date.setPlaceholderText("Abstract Date")
        drv_layout2 = QHBoxLayout()
        drv_layout2.addWidget(self.rd_driver_abstract)
        drv_layout2.addWidget(QLabel("Dated:"))
        drv_layout2.addWidget(self.rd_driver_abstract_date)
        driver_layout.addLayout(drv_layout2)
        
        self.rd_no_criminal = QCheckBox("No Criminal Convictions (as per bylaw)")
        driver_layout.addWidget(self.rd_no_criminal)
        self.rd_clean_record = QCheckBox("Clean Driving Record (no major violations)")
        driver_layout.addWidget(self.rd_clean_record)
        self.rd_age_requirement = QCheckBox("Age 18+ Years Old")
        driver_layout.addWidget(self.rd_age_requirement)
        
        driver_group.setLayout(driver_layout)
        form_layout.addWidget(driver_group)
        
        # Vehicle Requirements
        vehicle_group = QGroupBox("Red Deer Vehicle Requirements")
        vehicle_layout = QVBoxLayout()
        
        self.rd_vehicle_inspection = QCheckBox("Annual Vehicle Inspection (City approved facility)")
        self.rd_vehicle_inspection_date = StandardDateEdit()
        self.rd_vehicle_inspection_date.setPlaceholderText("Inspection Date")
        veh_layout1 = QHBoxLayout()
        veh_layout1.addWidget(self.rd_vehicle_inspection)
        veh_layout1.addWidget(QLabel("Expires:"))
        veh_layout1.addWidget(self.rd_vehicle_inspection_date)
        vehicle_layout.addLayout(veh_layout1)
        
        self.rd_vehicle_age = QCheckBox("Vehicle Age Compliance (typically <10 years)")
        vehicle_layout.addWidget(self.rd_vehicle_age)
        
        self.rd_insurance_proof = QCheckBox("Proof of Insurance (minimum $2M)")
        self.rd_insurance_expiry = StandardDateEdit()
        self.rd_insurance_expiry.setPlaceholderText("Insurance Expiry")
        veh_layout2 = QHBoxLayout()
        veh_layout2.addWidget(self.rd_insurance_proof)
        veh_layout2.addWidget(QLabel("Expires:"))
        veh_layout2.addWidget(self.rd_insurance_expiry)
        vehicle_layout.addLayout(veh_layout2)
        
        self.rd_vehicle_cleanliness = QCheckBox("Vehicle Cleanliness Standards Met")
        vehicle_layout.addWidget(self.rd_vehicle_cleanliness)
        
        self.rd_taximeter = QCheckBox("Taximeter (if applicable) - Calibrated & Sealed")
        self.rd_taximeter_date = StandardDateEdit()
        self.rd_taximeter_date.setPlaceholderText("Calibration Date")
        veh_layout3 = QHBoxLayout()
        veh_layout3.addWidget(self.rd_taximeter)
        veh_layout3.addWidget(QLabel("Calibrated:"))
        veh_layout3.addWidget(self.rd_taximeter_date)
        vehicle_layout.addLayout(veh_layout3)
        
        vehicle_group.setLayout(vehicle_layout)
        form_layout.addWidget(vehicle_group)
        
        # Operational Requirements
        ops_group = QGroupBox("Operational Compliance")
        ops_layout = QVBoxLayout()
        
        self.rd_fare_schedule = QCheckBox("Fare Schedule Posted (if applicable)")
        self.rd_receipt_capability = QCheckBox("Receipt Issuing Capability")
        self.rd_complaint_procedure = QCheckBox("Complaint Procedure Knowledge")
        self.rd_service_standards = QCheckBox("Service Standards Training Completed")
        
        for cb in [self.rd_fare_schedule, self.rd_receipt_capability, self.rd_complaint_procedure, self.rd_service_standards]:
            ops_layout.addWidget(cb)
        
        ops_group.setLayout(ops_layout)
        form_layout.addWidget(ops_group)
        
        # Notes
        notes_label = QLabel("Compliance Notes:")
        form_layout.addWidget(notes_label)
        
        self.rd_notes = QTextEdit()
        self.rd_notes.setPlaceholderText("Permit numbers, renewal dates, inspection notes...")
        self.rd_notes.setMaximumHeight(80)
        form_layout.addWidget(self.rd_notes)
        
        # Save button
        save_btn = QPushButton("💾 Save Red Deer Compliance")
        save_btn.clicked.connect(self._save_red_deer_compliance)
        form_layout.addWidget(save_btn)
        
        form_widget.setLayout(form_layout)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_hos_tab(self):
        """Tab: Hours of Service compliance"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Hours of Service (HOS) Compliance")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Summary cards
        summary_layout = QHBoxLayout()
        
        self.hos_today_label = QLabel("Today: 0h")
        self.hos_today_label.setStyleSheet("""
            background-color: #3498db; color: white; padding: 10px;
            border-radius: 5px; font-weight: bold;
        """)
        summary_layout.addWidget(self.hos_today_label)
        
        self.hos_week_label = QLabel("This Week: 0h")
        self.hos_week_label.setStyleSheet("""
            background-color: #2ecc71; color: white; padding: 10px;
            border-radius: 5px; font-weight: bold;
        """)
        summary_layout.addWidget(self.hos_week_label)
        
        self.hos_limit_label = QLabel("✅ Compliant")
        self.hos_limit_label.setStyleSheet("""
            background-color: #27ae60; color: white; padding: 10px;
            border-radius: 5px; font-weight: bold;
        """)
        summary_layout.addWidget(self.hos_limit_label)
        
        layout.addLayout(summary_layout)
        
        # HOS Regulations
        regs_group = QGroupBox("Alberta HOS Regulations")
        regs_layout = QVBoxLayout()
        regs_layout.addWidget(QLabel("Daily Limits:"))
        regs_layout.addWidget(QLabel("  • Maximum 13 hours driving per day"))
        regs_layout.addWidget(QLabel("  • Maximum 14 hours on-duty per day"))
        regs_layout.addWidget(QLabel("  • Minimum 8 consecutive hours off-duty"))
        regs_layout.addWidget(QLabel("\nWeekly Limits:"))
        regs_layout.addWidget(QLabel("  • Maximum 70 hours on-duty in 7 days"))
        regs_layout.addWidget(QLabel("  • Minimum 24 consecutive hours off in 7 days"))
        regs_group.setLayout(regs_layout)
        layout.addWidget(regs_group)
        
        # Recent hours table
        hours_label = QLabel("Recent Hours (Last 7 Days):")
        layout.addWidget(hours_label)
        
        self.hos_table = QTableWidget()
        self.hos_table.setColumnCount(5)
        self.hos_table.setHorizontalHeaderLabels(["Date", "On-Duty Hours", "Driving Hours", "Off-Duty Hours", "Status"])
        layout.addWidget(self.hos_table)
        
        # Load HOS data button
        load_hos_btn = QPushButton("🔄 Refresh HOS Data")
        load_hos_btn.clicked.connect(self._load_hos_data)
        layout.addWidget(load_hos_btn)
        
        widget.setLayout(layout)
        return widget
    
    def _save_provincial_compliance(self):
        """Save provincial rules compliance"""
        if not self.employee_id:
            return
        
        try:
            compliance_items = []
            if self.prov_class4.isChecked(): compliance_items.append('Class 4 License')
            if self.prov_medical.isChecked(): compliance_items.append('Medical Exam')
            if self.prov_abstract.isChecked(): compliance_items.append('Driver Abstract')
            if self.prov_criminal_check.isChecked(): compliance_items.append('Criminal Check')
            if self.prov_commercial_insurance.isChecked(): compliance_items.append('Commercial Insurance')
            if self.prov_insurance_cert.isChecked(): compliance_items.append('Insurance Certificate')
            if self.prov_wcb.isChecked(): compliance_items.append('WCB Coverage')
            if self.prov_first_aid.isChecked(): compliance_items.append('First Aid')
            if self.prov_defensive_driving.isChecked(): compliance_items.append('Defensive Driving')
            if self.prov_fatigue_mgmt.isChecked(): compliance_items.append('Fatigue Management')
            if self.prov_passenger_safety.isChecked(): compliance_items.append('Passenger Safety')
            if self.prov_nsc.isChecked(): compliance_items.append('NSC Compliance')
            if self.prov_vehicle_inspection.isChecked(): compliance_items.append('DVIR')
            if self.prov_maintenance_records.isChecked(): compliance_items.append('Maintenance Records')
            if self.prov_trip_inspection.isChecked(): compliance_items.append('Trip Inspection')
            
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
            cur.execute("""
                UPDATE employees
                SET notes = COALESCE(notes, '') || %s
                WHERE employee_id = %s
            """, (f"\n\n--- PROVINCIAL COMPLIANCE ---\n{', '.join(compliance_items)}\nUpdated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.employee_id))
            
            self.db.commit()
            cur.close()
            QMessageBox.information(self, "Success", "Provincial compliance saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            self.db.rollback()
    
    def _save_red_deer_compliance(self):
        """Save Red Deer bylaws compliance"""
        if not self.employee_id:
            return
        
        try:
            compliance_items = []
            if self.rd_business_license.isChecked(): compliance_items.append('Business License')
            if self.rd_chauffeur_permit.isChecked(): compliance_items.append('Chauffeur Permit')
            if self.rd_vehicle_license.isChecked(): compliance_items.append('Vehicle License')
            if self.rd_permit_display.isChecked(): compliance_items.append('Permit Displayed')
            if self.rd_police_check.isChecked(): compliance_items.append('Police Check')
            if self.rd_driver_abstract.isChecked(): compliance_items.append('Driver Abstract')
            if self.rd_no_criminal.isChecked(): compliance_items.append('No Convictions')
            if self.rd_clean_record.isChecked(): compliance_items.append('Clean Record')
            if self.rd_age_requirement.isChecked(): compliance_items.append('Age 18+')
            if self.rd_vehicle_inspection.isChecked(): compliance_items.append('Vehicle Inspection')
            if self.rd_vehicle_age.isChecked(): compliance_items.append('Vehicle Age OK')
            if self.rd_insurance_proof.isChecked(): compliance_items.append('Insurance Proof')
            if self.rd_vehicle_cleanliness.isChecked(): compliance_items.append('Cleanliness OK')
            if self.rd_taximeter.isChecked(): compliance_items.append('Taximeter OK')
            if self.rd_fare_schedule.isChecked(): compliance_items.append('Fare Schedule')
            if self.rd_receipt_capability.isChecked(): compliance_items.append('Receipts OK')
            if self.rd_complaint_procedure.isChecked(): compliance_items.append('Complaint Procedure')
            if self.rd_service_standards.isChecked(): compliance_items.append('Service Standards')
            
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
            cur.execute("""
                UPDATE employees
                SET notes = COALESCE(notes, '') || %s
                WHERE employee_id = %s
            """, (f"\n\n--- RED DEER BYLAW COMPLIANCE ---\n{', '.join(compliance_items)}\nNotes: {self.rd_notes.toPlainText()}\nUpdated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.employee_id))
            
            self.db.commit()
            cur.close()
            QMessageBox.information(self, "Success", "Red Deer compliance saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            self.db.rollback()
    
    def _load_hos_data(self):
        """Load hours of service data from database"""
        if not self.employee_id:
            return
        
        try:
            cur = self.db.get_cursor()
            
            # Get recent hours
            cur.execute("""
                SELECT log_date, 
                       COALESCE(on_duty_hours, 0) as on_duty,
                       COALESCE(driving_hours, 0) as driving,
                       COALESCE(off_duty_hours, 0) as off_duty
                FROM driver_hos_log
                WHERE employee_id = %s
                AND log_date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY log_date DESC
            """, (self.employee_id,))
            
            rows = cur.fetchall()
            
            if rows:
                self.hos_table.setRowCount(len(rows))
                total_week = 0
                total_today = 0
                
                for i, (log_date, on_duty, driving, off_duty) in enumerate(rows):
                    self.hos_table.setItem(i, 0, QTableWidgetItem(str(log_date)))
                    self.hos_table.setItem(i, 1, QTableWidgetItem(f"{on_duty:.1f}h"))
                    self.hos_table.setItem(i, 2, QTableWidgetItem(f"{driving:.1f}h"))
                    self.hos_table.setItem(i, 3, QTableWidgetItem(f"{off_duty:.1f}h"))
                    
                    # Status
                    if on_duty > 14 or driving > 13:
                        status = "⚠️ OVER LIMIT"
                        self.hos_table.setItem(i, 4, QTableWidgetItem(status))
                        self.hos_table.item(i, 4).setBackground(QBrush(QColor("#e74c3c")))
                    else:
                        status = "✅ OK"
                        self.hos_table.setItem(i, 4, QTableWidgetItem(status))
                    
                    total_week += on_duty
                    if i == 0:  # Most recent (today)
                        total_today = on_duty
                
                # Update summary cards
                self.hos_today_label.setText(f"Today: {total_today:.1f}h")
                self.hos_week_label.setText(f"This Week: {total_week:.1f}h")
                
                if total_week > 70:
                    self.hos_limit_label.setText("⚠️ OVER 70h")
                    self.hos_limit_label.setStyleSheet("""
                        background-color: #e74c3c; color: white; padding: 10px;
                        border-radius: 5px; font-weight: bold;
                    """)
                else:
                    self.hos_limit_label.setText("✅ Compliant")
            else:
                # No data
                self.hos_table.setRowCount(1)
                self.hos_table.setItem(0, 0, QTableWidgetItem("No HOS data available"))
            
            cur.close()
        except Exception as e:
            QMessageBox.warning(self, "HOS Error", f"Could not load HOS data: {e}")
    
    def create_performance_tab(self):
        """Tab 10: Performance reviews and notes"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Performance & Reviews")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Performance reviews
        self.review_table = QTableWidget()
        self.review_table.setColumnCount(5)
        self.review_table.setHorizontalHeaderLabels([
            "Review Date", "Rating", "Reviewer", "Strengths", "Improvement Areas"
        ])
        layout.addWidget(self.review_table)
        
        # Notes section
        notes_label = QLabel("Manager Notes:")
        layout.addWidget(notes_label)
        
        self.manager_notes = QTextEdit()
        layout.addWidget(self.manager_notes)
        
        widget.setLayout(layout)
        return widget
    
    def _filter_documents(self):
        """Filter document list based on search and filters"""
        search_text = self.doc_search.text().lower()
        type_filter = self.doc_type_filter.currentText()
        
        for i in range(self.doc_list.count()):
            item = self.doc_list.item(i)
            item_text = item.text().lower()
            
            # Check search match
            search_match = search_text in item_text if search_text else True
            
            # Check type filter
            if type_filter == "All Types":
                type_match = True
            else:
                type_match = type_filter.lower() in item_text
            
            # Show/hide item
            item.setHidden(not (search_match and type_match))
    
    def load_employee_data(self):
        """Load all employee data from database"""
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
            
            # Main employee data
            cur.execute("""
                SELECT employee_id, full_name, t4_sin, NULL as date_of_birth, street_address, city, postal_code,
                       phone, email, hire_date, position, is_chauffeur, hourly_rate, salary
                FROM employees
                WHERE employee_id = %s
            """, (self.employee_id,))
            
            emp = cur.fetchone()
            if emp:
                (emp_id, name, sin, dob, addr, city, postal, phone, email, 
                 hire, pos, chauffeur, hourly, salary) = emp
                
                self.emp_id.setText(str(emp_id or ""))
                self.full_name.setText(str(name or ""))
                self.sin.setText(str(sin or ""))
                if dob:
                    self.dob.setDate(QDate.fromString(str(dob), "MM/dd/yyyy"))
                self.address.setText(str(addr or ""))
                self.city.setText(str(city or ""))
                self.postal_code.setText(str(postal or ""))
                self.phone.setText(str(phone or ""))
                self.email.setText(str(email or ""))
                if hire:
                    self.hire_date.setDate(QDate.fromString(str(hire), "MM/dd/yyyy"))
                self.position.setText(str(pos or ""))
                self.is_chauffeur.setChecked(bool(chauffeur))
                self.hourly_rate.setValue(float(hourly or 0))
                self.salary.setValue(float(salary or 0))
            
            # Load pay history
            cur.execute("""
                SELECT pay_date, gross_pay, total_deductions, net_pay
                FROM driver_payroll
                WHERE employee_id = %s
                ORDER BY pay_date DESC
                LIMIT 50
            """, (self.employee_id,))
            
            pay_rows = cur.fetchall()
            self.pay_table.setRowCount(len(pay_rows) if pay_rows else 0)
            ytd_gross = ytd_net = 0
            if pay_rows:
                for i, (p_date, gross, deduct, net) in enumerate(pay_rows):
                    ytd_gross += float(gross or 0)
                    ytd_net += float(net or 0)
                    self.pay_table.setItem(i, 0, QTableWidgetItem(str(p_date)))
                    self.pay_table.setItem(i, 1, QTableWidgetItem(f"${float(gross or 0):,.2f}"))
                    self.pay_table.setItem(i, 2, QTableWidgetItem(f"${float(deduct or 0):,.2f}"))
                    self.pay_table.setItem(i, 3, QTableWidgetItem(f"${float(net or 0):,.2f}"))
                    self.pay_table.setItem(i, 4, QTableWidgetItem(""))  # Charters
                    self.pay_table.setItem(i, 5, QTableWidgetItem(f"${ytd_gross:,.2f}"))
                    self.pay_table.setItem(i, 6, QTableWidgetItem(f"${ytd_net:,.2f}"))
            
            # Load documents from database
            cur.execute("""
                SELECT document_name, document_type, expiry_date
                FROM driver_documents
                WHERE employee_id = %s
                ORDER BY created_at DESC
            """, (self.employee_id,))
            
            docs = cur.fetchall()
            self.doc_list.clear()
            if docs:
                for doc_name, doc_type, expiry in docs:
                    # Color code by expiry status
                    if expiry:
                        days_to_expiry = (expiry - datetime.now().date()).days
                        if days_to_expiry < 0:
                            icon = "🔴"  # Expired
                        elif days_to_expiry <= 30:
                            icon = "🟡"  # Expiring soon
                        else:
                            icon = "🟢"  # Valid
                        display_text = f"{icon} {doc_name} (Exp: {expiry})"
                    else:
                        display_text = f"📄 {doc_name}"
                    
                    self.doc_list.addItem(display_text)
            else:
                # Show samples if no documents
                self.doc_list.addItem("📄 No documents yet - Click Upload")
            
            cur.close()
            
            # Update compliance summary cards
            self._update_compliance_cards()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load employee data: {e}")
    
    def save_employee(self):
        """Save all employee changes"""
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
            cur.execute("""
                UPDATE employees SET
                    full_name = %s,
                    sin = %s,
                    phone = %s,
                    email = %s,
                    position = %s,
                    hourly_rate = %s,
                    annual_salary = %s
                WHERE employee_id = %s
            """, (
                self.full_name.text(),
                self.sin.text(),
                self.phone.text(),
                self.email.text(),
                self.position.text(),
                self.hourly_rate.value(),
                self.salary.value(),
                self.employee_id
            ))
            self.db.commit()
            QMessageBox.information(self, "Success", "Employee saved successfully")
            self.saved.emit({"action": "save", "employee_id": self.employee_id})
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            self.db.rollback()
    
    def add_new_employee(self):
        """Create a new employee - open dialog with no employee_id"""
        reply = QMessageBox.question(
            self,
            "Add New Employee",
            "Create a new employee record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            new_dialog = EmployeeDetailDialog(self.db, employee_id=None, parent=self.parent())
            new_dialog.saved.connect(self.on_employee_saved)
            new_dialog.exec()
    
    def duplicate_employee(self):
        """Duplicate current employee with modified name"""
        if not self.employee_id:
            QMessageBox.warning(self, "Warning", "No employee loaded to duplicate.")
            return
        
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Employee")
            dialog.setGeometry(100, 100, 400, 150)
            
            dlg_layout = QVBoxLayout()
            dlg_layout.addWidget(QLabel("Enter a new name for the duplicate employee:"))
            
            name_input = QLineEdit()
            name_input.setText(self.full_name.text() + " (Copy)")
            dlg_layout.addWidget(name_input)
            
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Duplicate")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            dlg_layout.addLayout(btn_layout)
            
            dialog.setLayout(dlg_layout)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_name = name_input.text().strip()
                if not new_name:
                    QMessageBox.warning(self, "Warning", "Please enter a name for the duplicate employee.")
                    return
                
                # Insert duplicate record
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
                cur.execute("""
                    INSERT INTO employees (full_name, t4_sin, phone, email, position, hourly_rate, salary, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    new_name,
                    self.sin.text(),
                    self.phone.text(),
                    self.email.text(),
                    self.position.text(),
                    self.hourly_rate.value(),
                    self.salary.value()
                ))
                self.db.commit()
                QMessageBox.information(self, "Success", f"Employee duplicated as '{new_name}'.")
                cur.close()
                self.load_employee_data()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to duplicate: {e}")
    
    def delete_employee(self):
        """Delete current employee after confirmation"""
        if not self.employee_id:
            QMessageBox.warning(self, "Warning", "No employee loaded to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete employee '{self.full_name.text()}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
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
                cur.execute("DELETE FROM employees WHERE employee_id = %s", (self.employee_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", "Employee deleted successfully.")
                cur.close()
                self.saved.emit({"action": "delete", "employee_id": self.employee_id})
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
                self.db.rollback()
    
    def on_employee_saved(self, data):
        """Handle child dialog save - refresh current view"""
        if self.employee_id:
            self.load_employee_data()
    
    # ===== STUB METHODS (to be implemented) =====
    
    def terminate_employee(self):
        """Terminate employment with date and reason"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Terminate Employee")
        layout = QFormLayout()
        
        term_date = StandardDateEdit(prefer_month_text=True)

        
        term_date.setDisplayFormat("MM/dd/yyyy")
        term_date.setDate(QDate.currentDate())
        term_date.setCalendarPopup(True)
        
        reason_combo = QComboBox()
        reason_combo.addItems(["Voluntary Resignation", "End of Contract", "Retirement", 
                              "Dismissal - Cause", "Layoff", "Other"])
        
        notes = QTextEdit()
        notes.setPlaceholderText("Enter termination details and notes...")
        notes.setMaximumHeight(100)
        
        layout.addRow("Termination Date:", term_date)
        layout.addRow("Reason:", reason_combo)
        layout.addRow("Notes:", notes)
        
        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("Confirm Termination")
        cancel_btn = QPushButton("Cancel")
        
        def confirm_termination():
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
                cur.execute("""
                    UPDATE employees 
                    SET status = 'inactive',
                        termination_date = %s,
                        termination_reason = %s,
                        notes = COALESCE(notes, '') || '\n\nTermination: ' || %s
                    WHERE employee_id = %s
                """, (
                    term_date.date().toPyDate(),
                    reason_combo.currentText(),
                    notes.toPlainText(),
                    self.employee_id
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", "Employee terminated")
                dialog.accept()
                self.close()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Termination failed: {e}")
                self.db.rollback()
        
        confirm_btn.clicked.connect(confirm_termination)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def suspend_employee(self):
        """Suspend employee"""
        QMessageBox.information(self, "Info", "Suspension process initiated")
    
    def add_training(self):
        """Add training record dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Training Record")
        dialog.setGeometry(200, 200, 500, 400)
        
        layout = QFormLayout()
        
        # Training program selector
        program_combo = QComboBox()
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
            cur.execute("SELECT program_id, program_name FROM training_programs WHERE is_active = true ORDER BY program_name")
            programs = cur.fetchall()
            for prog_id, prog_name in programs:
                program_combo.addItem(prog_name, prog_id)
            cur.close()
        except:
            try:
                self.db.rollback()
            except:
                pass
            program_combo.addItem("OHAS Safety Training")
            program_combo.addItem("Defensive Driving")
            program_combo.addItem("Customer Service")
        
        completed_date = StandardDateEdit(prefer_month_text=True)

        
        completed_date.setDisplayFormat("MM/dd/yyyy")
        completed_date.setDate(QDate.currentDate())
        completed_date.setCalendarPopup(True)
        
        expiry_date = StandardDateEdit(prefer_month_text=True)

        
        expiry_date.setDisplayFormat("MM/dd/yyyy")
        expiry_date.setDate(QDate.currentDate().addYears(1))
        expiry_date.setCalendarPopup(True)
        
        cert_number = QLineEdit()
        
        status_combo = QComboBox()
        status_combo.addItems(["Valid", "Expired", "Pending"])
        
        notes = QTextEdit()
        notes.setMaximumHeight(80)
        
        layout.addRow("Training Program:", program_combo)
        layout.addRow("Date Completed:", completed_date)
        layout.addRow("Expiry Date:", expiry_date)
        layout.addRow("Certificate #:", cert_number)
        layout.addRow("Status:", status_combo)
        layout.addRow("Notes:", notes)
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        
        def save_training():
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
                cur.execute("""
                    INSERT INTO driver_documents 
                    (employee_id, document_type, document_name, issued_date, expiry_date, 
                     document_number, status, notes, created_at)
                    VALUES (%s, 'TRAINING', %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.employee_id,
                    program_combo.currentText(),
                    completed_date.date().toPyDate(),
                    expiry_date.date().toPyDate(),
                    cert_number.text(),
                    status_combo.currentText(),
                    notes.toPlainText()
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", "Training record added")
                dialog.accept()
                self.load_employee_data()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to save: {e}")
                self.db.rollback()
        
        save_btn.clicked.connect(save_training)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def edit_training(self):
        """Edit selected training record"""
        selected = self.training_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a training record to edit")
            return
        
        row = self.training_table.row(selected[0])
        QMessageBox.information(self, "Info", f"Edit training row {row} - Full edit dialog to be enhanced")
    
    def add_qualification(self):
        """Add license/certification dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add License/Certification")
        dialog.setGeometry(200, 200, 500, 350)
        
        layout = QFormLayout()
        
        type_combo = QComboBox()
        type_combo.addItems(["Driver's License", "Chauffeur Permit", "Medical Certificate", 
                            "Criminal Record Check", "Class 1 License", "Class 2 License",
                            "Class 4 License", "Air Brake Endorsement", "Other"])
        
        license_number = QLineEdit()
        
        issue_date = StandardDateEdit(prefer_month_text=True)

        
        issue_date.setDisplayFormat("MM/dd/yyyy")
        issue_date.setDate(QDate.currentDate())
        issue_date.setCalendarPopup(True)
        
        expiry_date = StandardDateEdit(prefer_month_text=True)

        
        expiry_date.setDisplayFormat("MM/dd/yyyy")
        expiry_date.setDate(QDate.currentDate().addYears(2))
        expiry_date.setCalendarPopup(True)
        
        status_combo = QComboBox()
        status_combo.addItems(["Valid", "Expired", "Suspended", "Pending Renewal"])
        
        notes = QTextEdit()
        notes.setMaximumHeight(60)
        
        layout.addRow("Type:", type_combo)
        layout.addRow("License/Certificate #:", license_number)
        layout.addRow("Issue Date:", issue_date)
        layout.addRow("Expiry Date:", expiry_date)
        layout.addRow("Status:", status_combo)
        layout.addRow("Notes:", notes)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        
        def save_qualification():
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
                cur.execute("""
                    INSERT INTO driver_documents 
                    (employee_id, document_type, document_name, issued_date, expiry_date,
                     document_number, status, notes, created_at)
                    VALUES (%s, 'LICENSE', %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.employee_id,
                    type_combo.currentText(),
                    issue_date.date().toPyDate(),
                    expiry_date.date().toPyDate(),
                    license_number.text(),
                    status_combo.currentText(),
                    notes.toPlainText()
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", "Qualification added")
                dialog.accept()
                self.load_employee_data()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to save: {e}")
                self.db.rollback()
        
        save_btn.clicked.connect(save_qualification)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def upload_document(self):
        """Upload document with metadata"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", 
                                                   "PDF Files (*.pdf);;Images (*.jpg *.png);;All Files (*)")
        if not file_path:
            return
        
        # Get document metadata
        dialog = QDialog(self)
        dialog.setWindowTitle("Document Details")
        layout = QFormLayout()
        
        doc_type = QComboBox()
        doc_type.addItems(["Employment Contract", "T4", "T4A", "ROE", "Resume", 
                          "Police Check", "Reference Letter", "License", "Other"])
        
        doc_name = QLineEdit(os.path.basename(file_path))
        
        issue_date = StandardDateEdit(prefer_month_text=True)

        
        issue_date.setDisplayFormat("MM/dd/yyyy")
        issue_date.setDate(QDate.currentDate())
        issue_date.setCalendarPopup(True)
        
        expiry_date = StandardDateEdit(prefer_month_text=True)

        
        expiry_date.setDisplayFormat("MM/dd/yyyy")
        expiry_date.setDate(QDate.currentDate().addYears(1))
        expiry_date.setCalendarPopup(True)
        expiry_date.setEnabled(False)
        
        has_expiry = QCheckBox("Has Expiry Date")
        has_expiry.stateChanged.connect(lambda: expiry_date.setEnabled(has_expiry.isChecked()))
        
        layout.addRow("Document Type:", doc_type)
        layout.addRow("Document Name:", doc_name)
        layout.addRow("Issue Date:", issue_date)
        layout.addRow("", has_expiry)
        layout.addRow("Expiry Date:", expiry_date)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Upload")
        cancel_btn = QPushButton("Cancel")
        
        def save_document():
            try:
                import shutil
                # Create documents directory if needed
                doc_dir = "L:/limo/employee_documents"
                os.makedirs(doc_dir, exist_ok=True)
                
                # Copy file to documents directory
                dest_path = os.path.join(doc_dir, f"emp_{self.employee_id}_{os.path.basename(file_path)}")
                shutil.copy2(file_path, dest_path)
                
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
                cur.execute("""
                    INSERT INTO driver_documents 
                    (employee_id, document_type, document_name, file_path, issued_date, expiry_date,
                     file_size, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active', NOW())
                """, (
                    self.employee_id,
                    doc_type.currentText(),
                    doc_name.text(),
                    dest_path,
                    issue_date.date().toPyDate(),
                    expiry_date.date().toPyDate() if has_expiry.isChecked() else None,
                    os.path.getsize(dest_path)
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", "Document uploaded successfully")
                dialog.accept()
                self.load_employee_data()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Upload failed: {e}")
                self.db.rollback()
        
        save_btn.clicked.connect(save_document)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def view_document(self):
        """Open document in default viewer"""
        item = self.doc_list.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection", "Please select a document to view")
            return
        
        doc_name = item.text().replace("📄 ", "")
        
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
            cur.execute("""
                SELECT file_path FROM driver_documents 
                WHERE employee_id = %s AND document_name LIKE %s
                LIMIT 1
            """, (self.employee_id, f"%{doc_name}%"))
            
            result = cur.fetchone()
            cur.close()
            
            if result and result[0]:
                file_path = result[0]
                if os.path.exists(file_path):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
                else:
                    QMessageBox.warning(self, "File Not Found", f"Document file not found: {file_path}")
            else:
                QMessageBox.information(self, "Sample Document", f"Viewing: {doc_name}\n\nThis is a sample entry. Actual file not yet uploaded.")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to open document: {e}")
    
    def edit_document(self):
        item = self.doc_list.currentItem()
        if item:
            QMessageBox.information(self, "Info", f"PDF editor opening: {item.text()}")
    
    def delete_document(self):
        item = self.doc_list.currentItem()
        if item:
            reply = QMessageBox.question(self, "Confirm", f"Delete {item.text()}?")
            if reply == QMessageBox.StandardButton.Yes:
                self.doc_list.takeItem(self.doc_list.row(item))
    
    def open_document(self, index):
        """Double-click to open document"""
        item = self.doc_list.item(index.row())
        if item:
            self.view_document()
    
    def generate_form(self, form_type):
        """Generate tax forms and documents"""
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
            cur.execute("""
                SELECT full_name, t4_sin, street_address, cell_phone
                FROM employees WHERE employee_id = %s
            """, (self.employee_id,))
            emp_data = cur.fetchone()
            
            if not emp_data:
                QMessageBox.warning(self, "Error", "Employee data not found")
                return
            
            name, sin, address, phone = emp_data
            
            # Get payroll data for tax forms
            cur.execute("""
                SELECT SUM(gross_pay), SUM(total_deductions), SUM(net_pay)
                FROM driver_payroll
                WHERE employee_id = %s AND EXTRACT(YEAR FROM pay_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """, (self.employee_id,))
            payroll = cur.fetchone()
            gross, deductions, net = payroll if payroll else (0, 0, 0)
            
            cur.close()
            
            # Create forms directory
            forms_dir = "L:/limo/employee_documents/generated_forms"
            os.makedirs(forms_dir, exist_ok=True)
            
            if form_type == "T4":
                form_content = f"""
═══════════════════════════════════════════════════════
                    T4 - STATEMENT OF REMUNERATION PAID
                    {datetime.now().year}
═══════════════════════════════════════════════════════

Employer: Arrow Limousine Service Ltd.
Employee: {name}
SIN: {sin}
Address: {address}

═══════════════════════════════════════════════════════
Box 14 - Employment Income: ${gross or 0:.2f}
Box 16 - Employee's CPP contributions: ${(gross or 0) * 0.0595:.2f}
Box 18 - Employee's EI premiums: ${(gross or 0) * 0.0158:.2f}
Box 22 - Income tax deducted: ${deductions or 0:.2f}
═══════════════════════════════════════════════════════

This is a preliminary T4 form. Official CRA-approved forms
must be filed electronically or using official paper forms.
                """
                
            elif form_type == "T4A":
                form_content = f"""
═══════════════════════════════════════════════════════
                    T4A - STATEMENT OF PENSION, RETIREMENT,
                    ANNUITY, AND OTHER INCOME
                    {datetime.now().year}
═══════════════════════════════════════════════════════

Payer: Arrow Limousine Service Ltd.
Recipient: {name}
SIN: {sin}

Box 048 - Fees for services: ${gross or 0:.2f}

This is a preliminary T4A form.
                """
                
            elif form_type == "ROE":
                # Calculate insurable hours from payroll
                cur.execute("""
                    SELECT COUNT(*) * 8, SUM(gross_pay)
                    FROM driver_payroll
                    WHERE employee_id = %s 
                    AND pay_date >= (SELECT termination_date FROM employees WHERE employee_id = %s) - INTERVAL '52 weeks'
                """, (self.employee_id, self.employee_id))
                hours_data = cur.fetchone()
                insurable_hours = hours_data[0] if hours_data and hours_data[0] else 0
                total_earnings = hours_data[1] if hours_data and hours_data[1] else 0
                
                cur.execute("""
                    SELECT termination_date, termination_reason
                    FROM employees WHERE employee_id = %s
                """, (self.employee_id,))
                term_data = cur.fetchone()
                term_date = term_data[0] if term_data else "N/A"
                term_reason = term_data[1] if term_data and term_data[1] else "Unknown"
                
                # Map reason to ROE codes
                roe_code_map = {
                    "Voluntary Resignation": "E - Quit",
                    "End of Contract": "A - Shortage of Work",
                    "Retirement": "E - Quit (Retirement)",
                    "Dismissal - Cause": "M - Dismissal",
                    "Layoff": "A - Shortage of Work"
                }
                roe_code = roe_code_map.get(term_reason, "Other")
                
                form_content = f"""
═════════════════════════════════════════════════════════
        RECORD OF EMPLOYMENT (ROE)
        Service Canada Form
═════════════════════════════════════════════════════════

ROE Serial Number: {self.employee_id}-{datetime.now().year}-001

EMPLOYER INFORMATION:
Name: Arrow Limousine Service Ltd.
Address: Red Deer, Alberta
Business Number: [To be filled]

EMPLOYEE INFORMATION:
Name: {name}
Social Insurance Number: {sin}
Address: {address}

EMPLOYMENT PERIOD:
First Day Worked: [From hire_date]
Last Day Paid: {term_date}

REASON FOR ISSUING ROE:
Code: {roe_code}
Reason: {term_reason}

INSURABLE HOURS AND EARNINGS:
Total Insurable Hours (Last 52 weeks): {insurable_hours}
Total Insurable Earnings: ${total_earnings:.2f}

PAY PERIOD TYPE: Weekly/Bi-weekly
FINAL PAY PERIOD ENDING: {term_date}

═════════════════════════════════════════════════════════
IMPORTANT: This is a preliminary ROE form.
Official ROE must be submitted via Service Canada's 
ROE Web service within 5 calendar days of termination.
═════════════════════════════════════════════════════════

Employer Attestation:
I certify that the information provided is complete 
and accurate.

Signature: _____________________  Date: ___________
                """
                
            elif form_type == "Employment":
                form_content = f"""
═══════════════════════════════════════════════════════
                    EMPLOYMENT CONTRACT
                    Arrow Limousine Service Ltd.
═══════════════════════════════════════════════════════

This Employment Agreement is entered into on {datetime.now().strftime('%B %d, %Y')}

BETWEEN:
Arrow Limousine Service Ltd. ("Employer")

AND:
{name} ("Employee")
SIN: {sin}
Address: {address}
Phone: {phone}

1. POSITION AND DUTIES
The Employee is hired as a Chauffeur/Driver to provide professional
transportation services to clients.

2. COMPENSATION
Current compensation as recorded in payroll system.

3. TERM
This agreement is effective from the hire date and continues until
terminated by either party.

4. CONFIDENTIALITY
Employee agrees to maintain confidentiality of client information.

5. COMPLIANCE
Employee must maintain valid driver's license, insurance, and all
required certifications including OHAS, Red Deer bylaw compliance.

_________________________          _________________________
Employer Signature                 Employee Signature
Date: _______________             Date: _______________
                """
            else:
                form_content = f"Form generation for {form_type} - Template to be created"
            
            # Save to file
            file_path = os.path.join(forms_dir, f"{form_type}_{self.employee_id}_{datetime.now().strftime('%Y%m%d')}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(form_content)
            
            # Record in database
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
            
            # Map form types to valid database document types
            document_type_map = {
                "T4": "other",           # T4 forms -> "other" category
                "T4A": "other",          # T4A forms -> "other" category  
                "ROE": "other",          # ROE -> "other" category
                "TD1": "other",          # TD1 forms -> "other" category
                "Employment": "other"    # Employment contracts -> "other" category
            }
            
            db_document_type = document_type_map.get(form_type, "other")
            
            cur.execute("""
                INSERT INTO driver_documents
                (employee_id, document_type, document_name, file_path, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (self.employee_id, db_document_type, f"{form_type} - {datetime.now().year}", file_path))
            self.db.commit()
            cur.close()
            
            # Show preview
            preview = QDialog(self)
            preview.setWindowTitle(f"{form_type} Form Preview")
            preview.setGeometry(100, 100, 700, 600)
            layout = QVBoxLayout()
            
            text_display = QTextEdit()
            text_display.setPlainText(form_content)
            text_display.setReadOnly(True)
            text_display.setStyleSheet("font-family: Courier; font-size: 10pt;")
            layout.addWidget(text_display)
            
            btn_layout = QHBoxLayout()
            open_btn = QPushButton("Open File")
            open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(file_path)))
            btn_layout.addWidget(open_btn)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(preview.close)
            btn_layout.addWidget(close_btn)
            
            layout.addLayout(btn_layout)
            preview.setLayout(layout)
            preview.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Form generation failed: {e}")
            if 'cur' in locals():
                self.db.rollback()
    
    def add_advance(self):
        """Record pay advance"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Record Pay Advance")
        layout = QFormLayout()
        
        adv_date = StandardDateEdit(prefer_month_text=True)

        
        adv_date.setDisplayFormat("MM/dd/yyyy")
        adv_date.setDate(QDate.currentDate())
        adv_date.setCalendarPopup(True)
        
        amount = QDoubleSpinBox()
        amount.setMaximum(10000.00)
        amount.setDecimals(2)
        amount.setPrefix("$")
        
        reason = QLineEdit()
        reason.setPlaceholderText("Emergency, early payroll, etc.")
        
        notes = QTextEdit()
        notes.setMaximumHeight(60)
        
        layout.addRow("Date:", adv_date)
        layout.addRow("Amount:", amount)
        layout.addRow("Reason:", reason)
        layout.addRow("Notes:", notes)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Record Advance")
        cancel_btn = QPushButton("Cancel")
        
        def save_advance():
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
                # Create employee_expenses record for advance
                cur.execute("""
                    INSERT INTO employee_expenses 
                    (employee_id, expense_date, category, amount, description, status, created_at)
                    VALUES (%s, %s, 'PAY_ADVANCE', %s, %s, 'Outstanding', NOW())
                """, (
                    self.employee_id,
                    adv_date.date().toPyDate(),
                    -abs(amount.value()),  # Negative for advance (owes company)
                    f"{reason.text()} - {notes.toPlainText()}"
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", f"Pay advance of ${amount.value():.2f} recorded")
                dialog.accept()
                self.load_employee_data()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to save: {e}")
                self.db.rollback()
        
        save_btn.clicked.connect(save_advance)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def repay_advance(self):
        QMessageBox.information(self, "Info", "Record advance repayment dialog (to be implemented)")
    
    def add_custom_deduction(self):
        QMessageBox.information(self, "Info", "Add custom deduction dialog (to be implemented)")
    
    def issue_float(self):
        """Issue cash float"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Issue Cash Float")
        layout = QFormLayout()
        
        float_date = StandardDateEdit(prefer_month_text=True)

        
        float_date.setDisplayFormat("MM/dd/yyyy")
        float_date.setDate(QDate.currentDate())
        float_date.setCalendarPopup(True)
        
        amount = QDoubleSpinBox()
        amount.setMaximum(5000.00)
        amount.setDecimals(2)
        amount.setPrefix("$")
        amount.setValue(200.00)  # Common float amount
        
        purpose = QComboBox()
        purpose.addItems(["Daily Float", "Fuel Purchases", "Emergency Expenses", "Supplies", "Other"])
        purpose.setEditable(True)
        
        layout.addRow("Date Issued:", float_date)
        layout.addRow("Amount:", amount)
        layout.addRow("Purpose:", purpose)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Issue Float")
        cancel_btn = QPushButton("Cancel")
        
        def save_float():
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
                cur.execute("""
                    INSERT INTO driver_floats 
                    (employee_id, float_date, amount_issued, purpose, status, created_at)
                    VALUES (%s, %s, %s, %s, 'Outstanding', NOW())
                """, (
                    self.employee_id,
                    float_date.date().toPyDate(),
                    amount.value(),
                    purpose.currentText()
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", f"Float of ${amount.value():.2f} issued")
                dialog.accept()
                self.load_employee_data()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to issue float: {e}")
                self.db.rollback()
        
        save_btn.clicked.connect(save_float)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def return_float(self):
        QMessageBox.information(self, "Info", "Return cash float dialog (to be implemented)")
    
    def submit_receipts(self):
        QMessageBox.information(self, "Info", "Submit receipts for float dialog (to be implemented)")
    
    def add_expense(self):
        """Submit expense claim"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Submit Expense Claim")
        layout = QFormLayout()
        
        exp_date = StandardDateEdit(prefer_month_text=True)

        
        exp_date.setDisplayFormat("MM/dd/yyyy")
        exp_date.setDate(QDate.currentDate())
        exp_date.setCalendarPopup(True)
        
        category = QComboBox()
        category.addItems(["Fuel", "Meals", "Accommodation", "Supplies", "Vehicle Maintenance", "Other"])
        
        amount = QDoubleSpinBox()
        amount.setMaximum(10000.00)
        amount.setDecimals(2)
        amount.setPrefix("$")
        
        has_receipt = QCheckBox("Receipt Attached")
        
        description = QTextEdit()
        description.setPlaceholderText("Describe the expense...")
        description.setMaximumHeight(80)
        
        layout.addRow("Date:", exp_date)
        layout.addRow("Category:", category)
        layout.addRow("Amount:", amount)
        layout.addRow("", has_receipt)
        layout.addRow("Description:", description)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Submit Expense")
        cancel_btn = QPushButton("Cancel")
        
        def save_expense():
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
                cur.execute("""
                    INSERT INTO employee_expenses 
                    (employee_id, expense_date, category, amount, description, 
                     has_receipt, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Pending', NOW())
                """, (
                    self.employee_id,
                    exp_date.date().toPyDate(),
                    category.currentText(),
                    amount.value(),
                    description.toPlainText(),
                    has_receipt.isChecked()
                ))
                self.db.commit()
                cur.close()
                QMessageBox.information(dialog, "Success", "Expense claim submitted")
                dialog.accept()
                self.load_employee_data()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to submit expense: {e}")
                self.db.rollback()
        
        save_btn.clicked.connect(save_expense)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        dialog.setLayout(main_layout)
        
        dialog.exec()
    
    def attach_receipt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Receipt", "", "Images (*.jpg *.png *.pdf);;All Files (*)")
        if file_path:
            QMessageBox.information(self, "Info", f"Receipt attached: {file_path}")
    
    def approve_expense(self):
        QMessageBox.information(self, "Info", "Expense approved")
    
    def add_lunch(self):
        QMessageBox.information(self, "Info", "Add meal entry dialog (to be implemented)")
