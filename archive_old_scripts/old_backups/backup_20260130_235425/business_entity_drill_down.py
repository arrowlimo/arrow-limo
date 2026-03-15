"""
Business Entity Drill-Down Detail View
Overall business/company management - financials, taxes, licenses, insurance, assets, vendors
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
    QComboBox, QDialog, QTabWidget, QMessageBox, QSpinBox, QCheckBox,
    QFormLayout, QGroupBox, QScrollArea, QFileDialog, QListWidget, QHeaderView
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from desktop_app.common_widgets import StandardDateEdit
from datetime import datetime, timedelta


class BusinessEntityDialog(QDialog):
    """
    Complete business entity view with:
    - Company information and registration
    - Financial overview (P&L summary, balance sheet)
    - Tax filings and deadlines
    - Business licenses and permits
    - Insurance policies (general liability, fleet, property)
    - Bank accounts and credit facilities
    - Loans, liabilities, and debt schedule
    - Asset inventory (vehicles, property, equipment)
    - Vendor relationships and terms
    - Regulatory compliance tracking
    - Business documents (articles, contracts, leases)
    - Strategic planning and goals
    """
    
    saved = pyqtSignal(dict)
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        
        self.setWindowTitle("Business Entity Management - Arrow Limousine")
        self.setGeometry(50, 50, 1500, 950)
        
        layout = QVBoxLayout()
        
        # ===== COMPANY HEADER =====
        header = QLabel("🏢 Arrow Limousine Management System")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)
        
        # ===== TABS =====
        tabs = QTabWidget()
        
        tabs.addTab(self.create_company_info_tab(), "🏢 Company Info")
        tabs.addTab(self.create_financials_tab(), "💰 Financials")
        tabs.addTab(self.create_taxes_tab(), "📊 Tax Filings")
        tabs.addTab(self.create_licenses_tab(), "📜 Licenses & Permits")
        tabs.addTab(self.create_insurance_tab(), "🛡️ Insurance")
        tabs.addTab(self.create_banking_tab(), "🏦 Banking")
        tabs.addTab(self.create_liabilities_tab(), "💳 Loans & Liabilities")
        tabs.addTab(self.create_assets_tab(), "🏛️ Assets")
        tabs.addTab(self.create_vendors_tab(), "🤝 Vendors")
        tabs.addTab(self.create_compliance_tab(), "✅ Compliance")
        tabs.addTab(self.create_documents_tab(), "📄 Documents")
        tabs.addTab(self.create_planning_tab(), "🎯 Strategic Planning")
        
        layout.addWidget(tabs)
        
        # ===== ACTION BUTTONS =====
        button_layout = QHBoxLayout()
        
        self.generate_report_btn = QPushButton("📊 Generate Business Report")
        self.generate_report_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(self.generate_report_btn)
        
        button_layout.addStretch()
        
        self.save_btn = QPushButton("💾 Save All Changes")
        self.save_btn.clicked.connect(self.save_business)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.load_business_data()
    
    def create_company_info_tab(self):
        """Tab 1: Company registration and basic info"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Company Information")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout()
        
        # Registration info
        self.legal_name = QLineEdit()
        self.legal_name.setText("Arrow Limousine Ltd.")
        form.addRow("Legal Name:", self.legal_name)
        
        self.dba_name = QLineEdit()
        self.dba_name.setText("Arrow Limousine")
        form.addRow("DBA/Trade Name:", self.dba_name)
        
        self.business_number = QLineEdit()
        self.business_number.setPlaceholderText("BN or CRA Number")
        form.addRow("Business Number:", self.business_number)
        
        self.gst_number = QLineEdit()
        form.addRow("GST Registration #:", self.gst_number)
        
        self.incorporation_date = StandardDateEdit(prefer_month_text=True)
        self.incorporation_date.setCalendarPopup(True)
        form.addRow("Incorporation Date:", self.incorporation_date)
        
        self.incorporation_province = QComboBox()
        self.incorporation_province.addItems(["Alberta", "British Columbia", "Federal", "Other"])
        self.incorporation_province.setCurrentText("Alberta")
        form.addRow("Incorporation Province:", self.incorporation_province)
        
        # Contact info
        contact_group = QGroupBox("Contact Information")
        contact_form = QFormLayout()
        
        self.business_address = QTextEdit()
        self.business_address.setMaximumHeight(80)
        contact_form.addRow("Business Address:", self.business_address)
        
        self.business_phone = QLineEdit()
        contact_form.addRow("Phone:", self.business_phone)
        
        self.business_email = QLineEdit()
        contact_form.addRow("Email:", self.business_email)
        
        self.website = QLineEdit()
        contact_form.addRow("Website:", self.website)
        
        contact_group.setLayout(contact_form)
        form.addRow(contact_group)
        
        # Ownership
        owner_group = QGroupBox("Ownership")
        owner_form = QFormLayout()
        
        self.owner_name = QLineEdit()
        owner_form.addRow("Primary Owner:", self.owner_name)
        
        self.owner_percentage = QDoubleSpinBox()
        self.owner_percentage.setMaximum(100)
        self.owner_percentage.setSuffix("%")
        self.owner_percentage.setValue(100)
        owner_form.addRow("Ownership %:", self.owner_percentage)
        
        owner_group.setLayout(owner_form)
        form.addRow(owner_group)
        
        form_widget.setLayout(form)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_financials_tab(self):
        """Tab 2: Financial overview and metrics"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Financial Overview")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Key metrics
        metrics_group = QGroupBox("Key Financial Metrics (Current Year)")
        metrics_form = QFormLayout()
        
        self.total_revenue = QDoubleSpinBox()
        self.total_revenue.setMaximum(99999999)
        self.total_revenue.setReadOnly(True)
        self.total_revenue.setPrefix("$")
        metrics_form.addRow("Total Revenue:", self.total_revenue)
        
        self.total_expenses = QDoubleSpinBox()
        self.total_expenses.setMaximum(99999999)
        self.total_expenses.setReadOnly(True)
        self.total_expenses.setPrefix("$")
        metrics_form.addRow("Total Expenses:", self.total_expenses)
        
        self.net_profit = QDoubleSpinBox()
        self.net_profit.setMaximum(99999999)
        self.net_profit.setMinimum(-99999999)
        self.net_profit.setReadOnly(True)
        self.net_profit.setPrefix("$")
        metrics_form.addRow("Net Profit:", self.net_profit)
        
        self.profit_margin = QDoubleSpinBox()
        self.profit_margin.setMaximum(100)
        self.profit_margin.setReadOnly(True)
        self.profit_margin.setSuffix("%")
        metrics_form.addRow("Profit Margin:", self.profit_margin)
        
        metrics_group.setLayout(metrics_form)
        layout.addWidget(metrics_group)
        
        # Balance sheet
        balance_group = QGroupBox("Balance Sheet Snapshot")
        balance_form = QFormLayout()
        
        self.total_assets = QDoubleSpinBox()
        self.total_assets.setMaximum(99999999)
        self.total_assets.setReadOnly(True)
        self.total_assets.setPrefix("$")
        balance_form.addRow("Total Assets:", self.total_assets)
        
        self.total_liabilities = QDoubleSpinBox()
        self.total_liabilities.setMaximum(99999999)
        self.total_liabilities.setReadOnly(True)
        self.total_liabilities.setPrefix("$")
        balance_form.addRow("Total Liabilities:", self.total_liabilities)
        
        self.equity = QDoubleSpinBox()
        self.equity.setMaximum(99999999)
        self.equity.setMinimum(-99999999)
        self.equity.setReadOnly(True)
        self.equity.setPrefix("$")
        balance_form.addRow("Owner's Equity:", self.equity)
        
        balance_group.setLayout(balance_form)
        layout.addWidget(balance_group)
        
        # Monthly trend
        trend_label = QLabel("Monthly Revenue Trend:")
        layout.addWidget(trend_label)
        
        self.revenue_table = QTableWidget()
        self.revenue_table.setColumnCount(4)
        self.revenue_table.setHorizontalHeaderLabels(["Month", "Revenue", "Expenses", "Profit"])
        header = self.revenue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(1, 110)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.revenue_table.setMaximumHeight(200)
        layout.addWidget(self.revenue_table)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def create_taxes_tab(self):
        """Tab 3: Tax filings and deadlines"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Tax Filings & Deadlines")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Upcoming deadlines
        deadline_label = QLabel("⚠️ Upcoming Tax Deadlines:")
        deadline_label.setStyleSheet("color: orange; font-weight: bold;")
        layout.addWidget(deadline_label)
        
        self.deadline_table = QTableWidget()
        self.deadline_table.setColumnCount(5)
        self.deadline_table.setHorizontalHeaderLabels([
            "Type", "Period", "Due Date", "Days Until Due", "Status"
        ])
        header = self.deadline_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(4, 80)
        self.deadline_table.setMaximumHeight(150)
        layout.addWidget(self.deadline_table)
        
        # Filing history
        history_label = QLabel("Filing History:")
        layout.addWidget(history_label)
        
        self.tax_table = QTableWidget()
        self.tax_table.setColumnCount(6)
        self.tax_table.setHorizontalHeaderLabels([
            "Year", "Type", "Filed Date", "Amount Paid/Refund", "Status", "Confirmation #"
        ])
        header = self.tax_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(4, 80)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tax_table)
        
        # Tax buttons
        btn_layout = QHBoxLayout()
        file_tax_btn = QPushButton("➕ Log Tax Filing")
        file_tax_btn.clicked.connect(self.log_tax_filing)
        btn_layout.addWidget(file_tax_btn)
        
        remittance_btn = QPushButton("💵 GST Remittance")
        remittance_btn.clicked.connect(self.gst_remittance)
        btn_layout.addWidget(remittance_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_licenses_tab(self):
        """Tab 4: Business licenses and permits"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Licenses & Permits")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Licenses table
        self.license_table = QTableWidget()
        self.license_table.setColumnCount(6)
        self.license_table.setHorizontalHeaderLabels([
            "License Type", "Number", "Issue Date", "Expiry Date", "Status", "Renewal Cost"
        ])
        header = self.license_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(4, 80)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.license_table)
        
        # License buttons
        btn_layout = QHBoxLayout()
        add_license_btn = QPushButton("➕ Add License")
        add_license_btn.clicked.connect(self.add_license)
        btn_layout.addWidget(add_license_btn)
        
        renew_btn = QPushButton("🔄 Renew Selected")
        renew_btn.clicked.connect(self.renew_license)
        btn_layout.addWidget(renew_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_insurance_tab(self):
        """Tab 5: Business insurance policies"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Business Insurance Policies")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Insurance table
        self.insurance_table = QTableWidget()
        self.insurance_table.setColumnCount(7)
        self.insurance_table.setHorizontalHeaderLabels([
            "Policy Type", "Insurer", "Policy #", "Coverage", "Premium", "Expiry", "Status"
        ])
        header = self.insurance_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(6, 80)
        layout.addWidget(self.insurance_table)
        
        # Insurance buttons
        btn_layout = QHBoxLayout()
        add_policy_btn = QPushButton("➕ Add Policy")
        add_policy_btn.clicked.connect(self.add_insurance_policy)
        btn_layout.addWidget(add_policy_btn)
        
        claim_btn = QPushButton("📋 File Claim")
        claim_btn.clicked.connect(self.file_insurance_claim)
        btn_layout.addWidget(claim_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_banking_tab(self):
        """Tab 6: Bank accounts and credit facilities"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Banking Relationships")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Bank accounts table
        accounts_label = QLabel("Bank Accounts:")
        layout.addWidget(accounts_label)
        
        self.bank_account_table = QTableWidget()
        self.bank_account_table.setColumnCount(6)
        self.bank_account_table.setHorizontalHeaderLabels([
            "Bank", "Account Type", "Account #", "Current Balance", "Status", "Purpose"
        ])
        header = self.bank_account_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(4, 80)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.bank_account_table)
        
        # Credit facilities
        credit_label = QLabel("Credit Facilities:")
        layout.addWidget(credit_label)
        
        self.credit_table = QTableWidget()
        self.credit_table.setColumnCount(5)
        self.credit_table.setHorizontalHeaderLabels([
            "Type", "Limit", "Used", "Available", "Interest Rate"
        ])
        header = self.credit_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.credit_table.setMaximumHeight(150)
        layout.addWidget(self.credit_table)
        
        # Banking buttons
        btn_layout = QHBoxLayout()
        add_account_btn = QPushButton("➕ Add Account")
        add_account_btn.clicked.connect(self.add_bank_account)
        btn_layout.addWidget(add_account_btn)
        
        reconcile_btn = QPushButton("🔄 Reconcile Account")
        reconcile_btn.clicked.connect(self.reconcile_account)
        btn_layout.addWidget(reconcile_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_liabilities_tab(self):
        """Tab 7: Loans, debts, and payment schedules"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Loans & Liabilities")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Summary
        summary_layout = QHBoxLayout()
        self.total_debt = QLabel("Total Debt: $0.00")
        self.monthly_payments = QLabel("Monthly Payments: $0.00")
        summary_layout.addWidget(self.total_debt)
        summary_layout.addWidget(self.monthly_payments)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)
        
        # Loans table
        self.loan_table = QTableWidget()
        self.loan_table.setColumnCount(8)
        self.loan_table.setHorizontalHeaderLabels([
            "Lender", "Type", "Original Amount", "Current Balance", "Interest Rate", "Monthly Payment", "Maturity Date", "Status"
        ])
        header = self.loan_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(7, 80)
        layout.addWidget(self.loan_table)
        
        # Loan buttons
        btn_layout = QHBoxLayout()
        add_loan_btn = QPushButton("➕ Add Loan")
        add_loan_btn.clicked.connect(self.add_loan)
        btn_layout.addWidget(add_loan_btn)
        
        payment_btn = QPushButton("💵 Record Payment")
        payment_btn.setToolTip("Record a manually received payment against this loan; no online processing.")
        payment_btn.clicked.connect(self.record_loan_payment)
        btn_layout.addWidget(payment_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_assets_tab(self):
        """Tab 8: Asset inventory"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Asset Inventory")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Asset summary
        summary_layout = QHBoxLayout()
        self.vehicle_assets = QLabel("Vehicles: $0")
        self.property_assets = QLabel("Property: $0")
        self.equipment_assets = QLabel("Equipment: $0")
        self.total_asset_value = QLabel("Total: $0")
        summary_layout.addWidget(self.vehicle_assets)
        summary_layout.addWidget(self.property_assets)
        summary_layout.addWidget(self.equipment_assets)
        summary_layout.addWidget(self.total_asset_value)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)
        
        # Assets table
        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(7)
        self.asset_table.setHorizontalHeaderLabels([
            "Asset Type", "Description", "Purchase Date", "Original Cost", "Current Value", "Depreciation", "Status"
        ])
        header = self.asset_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(1, 200)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(6, 80)
        layout.addWidget(self.asset_table)
        
        # Asset buttons
        btn_layout = QHBoxLayout()
        add_asset_btn = QPushButton("➕ Add Asset")
        add_asset_btn.clicked.connect(self.add_asset)
        btn_layout.addWidget(add_asset_btn)
        
        dispose_btn = QPushButton("🗑️ Dispose Asset")
        dispose_btn.clicked.connect(self.dispose_asset)
        btn_layout.addWidget(dispose_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_vendors_tab(self):
        """Tab 9: Vendor relationships"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Vendor Relationships")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Vendors table
        self.vendor_table = QTableWidget()
        self.vendor_table.setColumnCount(7)
        self.vendor_table.setHorizontalHeaderLabels([
            "Vendor Name", "Category", "Contact", "Payment Terms", "YTD Spend", "Outstanding", "Status"
        ])
        header = self.vendor_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(6, 80)
        layout.addWidget(self.vendor_table)
        
        # Vendor buttons
        btn_layout = QHBoxLayout()
        add_vendor_btn = QPushButton("➕ Add Vendor")
        add_vendor_btn.clicked.connect(self.add_vendor)
        btn_layout.addWidget(add_vendor_btn)
        
        view_transactions_btn = QPushButton("📊 View Transactions")
        view_transactions_btn.clicked.connect(self.view_vendor_transactions)
        btn_layout.addWidget(view_transactions_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_compliance_tab(self):
        """Tab 10: Regulatory compliance tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Regulatory Compliance")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Compliance table
        self.compliance_table = QTableWidget()
        self.compliance_table.setColumnCount(5)
        self.compliance_table.setHorizontalHeaderLabels([
            "Requirement", "Category", "Last Review", "Next Review", "Status"
        ])
        header = self.compliance_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(4, 80)
        layout.addWidget(self.compliance_table)
        
        # Compliance buttons
        btn_layout = QHBoxLayout()
        add_requirement_btn = QPushButton("➕ Add Requirement")
        add_requirement_btn.clicked.connect(self.add_compliance_requirement)
        btn_layout.addWidget(add_requirement_btn)
        
        review_btn = QPushButton("✅ Mark Reviewed")
        review_btn.clicked.connect(self.mark_reviewed)
        btn_layout.addWidget(review_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_documents_tab(self):
        """Tab 11: Business documents"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Business Documents")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Document list
        self.doc_list = QListWidget()
        self.doc_list.doubleClicked.connect(self.open_business_document)
        layout.addWidget(self.doc_list)
        
        # Document buttons
        btn_layout = QHBoxLayout()
        upload_btn = QPushButton("📤 Upload Document")
        upload_btn.clicked.connect(self.upload_business_doc)
        btn_layout.addWidget(upload_btn)
        
        view_btn = QPushButton("👁️ View Selected")
        view_btn.clicked.connect(self.view_business_doc)
        btn_layout.addWidget(view_btn)
        
        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.clicked.connect(self.delete_business_doc)
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_planning_tab(self):
        """Tab 12: Strategic planning and goals"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Strategic Planning")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Goals table
        goals_label = QLabel("Business Goals:")
        layout.addWidget(goals_label)
        
        self.goal_table = QTableWidget()
        self.goal_table.setColumnCount(6)
        self.goal_table.setHorizontalHeaderLabels([
            "Goal", "Category", "Target Date", "Progress", "Status", "Notes"
        ])
        header = self.goal_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setColumnWidth(4, 80)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.goal_table)
        
        # Goal buttons
        btn_layout = QHBoxLayout()
        add_goal_btn = QPushButton("➕ Add Goal")
        add_goal_btn.clicked.connect(self.add_goal)
        btn_layout.addWidget(add_goal_btn)
        
        update_progress_btn = QPushButton("📊 Update Progress")
        update_progress_btn.clicked.connect(self.update_goal_progress)
        btn_layout.addWidget(update_progress_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def load_business_data(self):
        """Load business data from database"""
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
            
            # Load revenue data
            cur.execute("""
                SELECT SUM(total_amount_due) as revenue
                FROM charters
                WHERE EXTRACT(YEAR FROM charter_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """)
            revenue_row = cur.fetchone()
            if revenue_row and revenue_row[0]:
                self.total_revenue.setValue(float(revenue_row[0]))
            
            # Load expenses data
            cur.execute("""
                SELECT SUM(gross_amount) as expenses
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """)
            expense_row = cur.fetchone()
            if expense_row and expense_row[0]:
                self.total_expenses.setValue(float(expense_row[0]))
            
            # Calculate profit
            profit = self.total_revenue.value() - self.total_expenses.value()
            self.net_profit.setValue(profit)
            if self.total_revenue.value() > 0:
                margin = (profit / self.total_revenue.value()) * 100
                self.profit_margin.setValue(margin)
            
            # Load bank accounts
            cur.execute("""
                SELECT DISTINCT account_number
                FROM banking_transactions
                WHERE account_number IS NOT NULL
            """)
            bank_rows = cur.fetchall()
            self.bank_account_table.setRowCount(len(bank_rows) if bank_rows else 0)
            if bank_rows:
                for i, (acct_num,) in enumerate(bank_rows):
                    bank_name = "CIBC" if acct_num == '0228362' else ("Scotia" if acct_num == '903990106011' else "Unknown")
                    acct_type = "Primary" if acct_num == '0228362' else "Secondary"
                    self.bank_account_table.setItem(i, 0, QTableWidgetItem(bank_name))
                    self.bank_account_table.setItem(i, 1, QTableWidgetItem("Operating"))
                    self.bank_account_table.setItem(i, 2, QTableWidgetItem(str(acct_num)))
                    self.bank_account_table.setItem(i, 3, QTableWidgetItem("$0.00"))
                    self.bank_account_table.setItem(i, 4, QTableWidgetItem("Active"))
                    self.bank_account_table.setItem(i, 5, QTableWidgetItem(acct_type))
            
            # Load documents
            self.doc_list.addItem("📄 Articles of Incorporation.pdf")
            self.doc_list.addItem("📄 Business License.pdf")
            self.doc_list.addItem("📄 GST Registration.pdf")
            self.doc_list.addItem("📄 Insurance Policies.pdf")
            
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load business data: {e}")
    
    def save_business(self):
        """Save business changes"""
        QMessageBox.information(self, "Success", "Business information saved successfully")
    
    # ===== STUB METHODS =====
    def generate_report(self):
        QMessageBox.information(self, "Info", "Generate business report (to be implemented)")
    
    def log_tax_filing(self):
        QMessageBox.information(self, "Info", "Log tax filing (to be implemented)")
    
    def gst_remittance(self):
        QMessageBox.information(self, "Info", "GST remittance (to be implemented)")
    
    def add_license(self):
        QMessageBox.information(self, "Info", "Add license (to be implemented)")
    
    def renew_license(self):
        QMessageBox.information(self, "Info", "Renew license (to be implemented)")
    
    def add_insurance_policy(self):
        QMessageBox.information(self, "Info", "Add insurance policy (to be implemented)")
    
    def file_insurance_claim(self):
        QMessageBox.information(self, "Info", "File insurance claim (to be implemented)")
    
    def add_bank_account(self):
        QMessageBox.information(self, "Info", "Add bank account (to be implemented)")
    
    def reconcile_account(self):
        QMessageBox.information(self, "Info", "Reconcile account (to be implemented)")
    
    def add_loan(self):
        QMessageBox.information(self, "Info", "Add loan (to be implemented)")
    
    def record_loan_payment(self):
        QMessageBox.information(self, "Info", "Record loan payment (to be implemented)")
    
    def add_asset(self):
        QMessageBox.information(self, "Info", "Add asset (to be implemented)")
    
    def dispose_asset(self):
        QMessageBox.information(self, "Info", "Dispose asset (to be implemented)")
    
    def add_vendor(self):
        QMessageBox.information(self, "Info", "Add vendor (to be implemented)")
    
    def view_vendor_transactions(self):
        QMessageBox.information(self, "Info", "View vendor transactions (to be implemented)")
    
    def add_compliance_requirement(self):
        QMessageBox.information(self, "Info", "Add compliance requirement (to be implemented)")
    
    def mark_reviewed(self):
        QMessageBox.information(self, "Info", "Mark reviewed (to be implemented)")
    
    def upload_business_doc(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document")
        if file_path:
            QMessageBox.information(self, "Info", f"Document uploaded: {file_path}")
    
    def view_business_doc(self):
        item = self.doc_list.currentItem()
        if item:
            QMessageBox.information(self, "Info", f"Opening: {item.text()}")
    
    def delete_business_doc(self):
        item = self.doc_list.currentItem()
        if item:
            self.doc_list.takeItem(self.doc_list.row(item))
    
    def open_business_document(self, index):
        self.view_business_doc()
    
    def add_goal(self):
        QMessageBox.information(self, "Info", "Add goal (to be implemented)")
    
    def update_goal_progress(self):
        QMessageBox.information(self, "Info", "Update goal progress (to be implemented)")
