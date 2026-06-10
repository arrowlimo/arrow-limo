"""
T2 Corporation Tax Return - Historical Data Entry Widget
Enter T2 data line-by-line from paper forms (2007-2025)
"""

import logging
import os

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class T2DataEntryWidget(QWidget):
    """
    T2 Corporation Income Tax Return Data Entry

    Allows direct entry of historical T2 data from paper forms without
    needing to enter individual receipts/banking transactions.

    Features:
    - Enter by tax year (2007-2025)
    - Line-by-line schedule entry
    - Auto-calculate taxable income and tax owing
    - Store in database for audit trail
    """

    # Constants for duplicated literals
    INFO_BOX_STYLE = (
        "background: #dbeafe; padding: 10px; border-radius: 5px; "
        "margin-bottom: 10px;"
    )
    PAPER_INFO_STYLE = (
        "background: #fef3c7; padding: 10px; border-radius: 5px; "
        "margin-bottom: 10px;"
    )
    DEFAULT_CURRENCY = "$0.00"
    NO_RETURN_TITLE = "No Return"
    NO_RETURN_MESSAGE = "Please create or load a T2 return first."

    def __init__(self, db_connection, parent=None) -> None:
        super().__init__(parent)
        self.db = db_connection
        self.current_return_id = None
        self.latest_deductibility_analysis = None
        self.init_ui()
        self.load_tax_years()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel(
            "T2 Corporation Income Tax Return - Historical Data Entry"
        )
        header.setStyleSheet(
            "font-size: 16pt; font-weight: bold; color: #1e40af; padding:"
            "10px;"

        )
        layout.addWidget(header)

        # Year selection group
        year_group = self._build_year_selection()
        layout.addWidget(year_group)

        # Tabs for different schedules
        self.tabs = QTabWidget()
        self.tabs.addTab(
            self._build_schedule_1_tab(), "Schedule 1 - Net Income"
        )
        self.tabs.addTab(
            self._build_schedule_125_tab(), "Schedule 125 - Income Statement"
        )
        self.tabs.addTab(
            self._build_schedule_100_tab(), "Schedule 100 - Balance Sheet"
        )
        self.tabs.addTab(self._build_tax_calculation_tab(), "Tax Calculation")
        self.tabs.addTab(self._build_adjustments_tab(), "Adjustments")
        self.tabs.addTab(self._build_summary_tab(), "Summary & Filing")
        self.tabs.addTab(self._build_cca_schedule_tab(), "Schedule 8 - CCA")
        self.tabs.addTab(
            self._build_shareholders_tab(), "Schedule 50 - Shareholders"
        )

        layout.addWidget(self.tabs)

        # Status bar
        self.status_label = QLabel("Select a tax year to begin")
        self.status_label.setStyleSheet(
            "padding: 5px; background: #f3f4f6; border-radius: 3px;"
        )
        layout.addWidget(self.status_label)

    def _build_year_selection(self) -> QGroupBox:
        group = QGroupBox("Tax Year Selection")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Tax Year:"))
        self.year_combo = QComboBox()
        self.year_combo.setMinimumWidth(120)
        self.year_combo.currentTextChanged.connect(self.load_return_data)
        layout.addWidget(self.year_combo)

        layout.addWidget(QLabel("Fiscal Year End:"))
        self.fiscal_year_end = QDateEdit()
        self.fiscal_year_end.setCalendarPopup(True)
        self.fiscal_year_end.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.fiscal_year_end)

        layout.addWidget(QLabel("Business Number:"))
        self.business_number = QLineEdit()
        self.business_number.setPlaceholderText("123456789 RC 0001")
        self.business_number.setMaximumWidth(150)
        layout.addWidget(self.business_number)

        self.new_btn = QPushButton("📄 New Return")
        self.new_btn.clicked.connect(self.create_new_return)
        layout.addWidget(self.new_btn)

        self.save_btn = QPushButton("💾 Save All")
        self.save_btn.clicked.connect(self.save_all_data)
        self.save_btn.setStyleSheet(
            "background: #10b981; color: white; font-weight: bold;"
        )
        layout.addWidget(self.save_btn)

        layout.addStretch()
        return group

    def _build_schedule_1_tab(self) -> QWidget:
        """Schedule 1 - Net Income for Income Tax Purposes"""
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)

        info = QLabel(
            "📋 Schedule 1: Net Income for Income Tax Purposes\nEnter line"
            "items from your paper T2 Schedule 1"

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        # Create table for schedule lines
        self.schedule1_table = QTableWidget()
        self.schedule1_table.setColumnCount(5)
        self.schedule1_table.setHorizontalHeaderLabels(
            ["Line #", "Description", "Amount", "Notes", "Actions"]
        )
        self.schedule1_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.schedule1_table.setMinimumHeight(400)

        # Common Schedule 1 lines
        common_lines = [
            (
                "100",
                "Net income (loss) before income tax and extraordinary items"
                "per financial statements",

            ),
            ("200", "Total additions (lines 201-298)"),
            ("300", "Total deductions (lines 301-398)"),
            ("400", "Net income for income tax purposes"),
        ]

        self.schedule1_table.setRowCount(len(common_lines))
        for row, (line_num, desc) in enumerate(common_lines):
            self.schedule1_table.setItem(row, 0, QTableWidgetItem(line_num))
            self.schedule1_table.setItem(row, 1, QTableWidgetItem(desc))
            self.schedule1_table.setItem(row, 2, QTableWidgetItem("0.00"))
            self.schedule1_table.setItem(row, 3, QTableWidgetItem(""))

        layout.addWidget(self.schedule1_table)

        btn_layout = QHBoxLayout()
        add_line_btn = QPushButton("➕ Add Line")
        add_line_btn.clicked.connect(
            lambda: self.add_schedule_line(self.schedule1_table, "1")
        )
        btn_layout.addWidget(add_line_btn)

        save_btn = QPushButton("💾 Save Schedule 1")
        save_btn.clicked.connect(lambda: self.save_schedule_data("1"))
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        return container

    def _build_schedule_125_tab(self) -> QWidget:
        """Schedule 125 - Income Statement"""
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)

        info = QLabel(
            "📊 Schedule 125: Income Statement Information\nEnter your P&L"
            "line items from the paper T2 form"

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        # Revenue section
        revenue_group = QGroupBox("Revenue")
        revenue_layout = QFormLayout(revenue_group)

        self.sch125_revenue = self._money_spin()
        self.sch125_other_income = self._money_spin()
        self.sch125_total_revenue = self._money_spin(read_only=True)

        revenue_layout.addRow(
            "8000 - Sales, commissions, and fees:", self.sch125_revenue
        )
        revenue_layout.addRow("8089 - Other income:", self.sch125_other_income)
        revenue_layout.addRow(
            "<b>Total Revenue:</b>", self.sch125_total_revenue
        )

        self.sch125_revenue.valueChanged.connect(self._calc_sch125_totals)
        self.sch125_other_income.valueChanged.connect(self._calc_sch125_totals)

        layout.addWidget(revenue_group)

        # Expenses section
        expenses_group = QGroupBox("Expenses")
        expenses_layout = QFormLayout(expenses_group)

        self.sch125_cost_of_sales = self._money_spin()
        self.sch125_salaries = self._money_spin()
        self.sch125_benefits = self._money_spin()
        self.sch125_rent = self._money_spin()
        self.sch125_repairs = self._money_spin()
        self.sch125_bad_debts = self._money_spin()
        self.sch125_interest = self._money_spin()
        self.sch125_insurance = self._money_spin()
        self.sch125_office = self._money_spin()
        self.sch125_professional_fees = self._money_spin()
        self.sch125_property_tax = self._money_spin()
        self.sch125_travel = self._money_spin()
        self.sch125_vehicle = self._money_spin()
        self.sch125_other_expenses = self._money_spin()
        self.sch125_total_expenses = self._money_spin(read_only=True)

        expenses_layout.addRow(
            "8518 - Cost of sales:", self.sch125_cost_of_sales
        )
        expenses_layout.addRow(
            "8513 - Salaries, wages, and benefits:", self.sch125_salaries
        )
        expenses_layout.addRow(
            "8523 - Employee benefits:", self.sch125_benefits
        )
        expenses_layout.addRow("8690 - Rent:", self.sch125_rent)
        expenses_layout.addRow(
            "8690 - Repairs and maintenance:", self.sch125_repairs
        )
        expenses_layout.addRow("8590 - Bad debts:", self.sch125_bad_debts)
        expenses_layout.addRow(
            "8711 - Interest and bank charges:", self.sch125_interest
        )
        expenses_layout.addRow("9270 - Insurance:", self.sch125_insurance)
        expenses_layout.addRow("8810 - Office expenses:", self.sch125_office)
        expenses_layout.addRow(
            "8860 - Professional fees:", self.sch125_professional_fees
        )
        expenses_layout.addRow(
            "9180 - Property taxes:", self.sch125_property_tax
        )
        expenses_layout.addRow("9200 - Travel:", self.sch125_travel)
        expenses_layout.addRow("9281 - Vehicle expenses:", self.sch125_vehicle)
        expenses_layout.addRow(
            "9923 - Other expenses:", self.sch125_other_expenses
        )
        expenses_layout.addRow(
            "<b>Total Expenses:</b>", self.sch125_total_expenses
        )

        # Connect all expense fields to recalculation
        for field in [
            self.sch125_cost_of_sales,
            self.sch125_salaries,
            self.sch125_benefits,
            self.sch125_rent,
            self.sch125_repairs,
            self.sch125_bad_debts,
            self.sch125_interest,
            self.sch125_insurance,
            self.sch125_office,
            self.sch125_professional_fees,
            self.sch125_property_tax,
            self.sch125_travel,
            self.sch125_vehicle,
            self.sch125_other_expenses,
        ]:
            field.valueChanged.connect(self._calc_sch125_totals)

        layout.addWidget(expenses_group)

        # Net income
        net_group = QGroupBox("Net Income")
        net_layout = QFormLayout(net_group)
        self.sch125_net_income = self._money_spin(read_only=True)
        net_layout.addRow(
            "<b>Net Income Before Tax:</b>", self.sch125_net_income
        )
        layout.addWidget(net_group)

        # Button row
        btn_row_125 = QHBoxLayout()
        autofill_btn_125 = QPushButton("🔄 Auto-Fill from DB")
        autofill_btn_125.setStyleSheet(
            "background: #3b82f6; color: white; font-weight: bold;"
        )
        autofill_btn_125.clicked.connect(self._auto_fill_schedule_125)
        btn_row_125.addWidget(autofill_btn_125)
        autofill_btn_125_info = QLabel(
            "← pulls revenue & deductible expenses from receipts/payments"
        )
        autofill_btn_125_info.setStyleSheet(
            "color: #6b7280; font-style: italic;"
        )
        btn_row_125.addWidget(autofill_btn_125_info)
        btn_row_125.addStretch()
        save_btn_125 = QPushButton("💾 Save Schedule 125")
        save_btn_125.clicked.connect(lambda: self.save_schedule_125())
        btn_row_125.addWidget(save_btn_125)
        layout.addLayout(btn_row_125)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        return container

    def _build_schedule_100_tab(self) -> QWidget:
        """Schedule 100 - Balance Sheet"""
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)

        info = QLabel(
            "📑 Schedule 100: Balance Sheet Information\nEnter beginning and"
            "ending balances from your paper T2"

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        # Assets
        assets_group = QGroupBox("Assets")
        assets_layout = QFormLayout(assets_group)

        self.sch100_cash_begin = self._money_spin()
        self.sch100_cash_end = self._money_spin()
        self.sch100_ar_begin = self._money_spin()
        self.sch100_ar_end = self._money_spin()
        self.sch100_inventory_begin = self._money_spin()
        self.sch100_inventory_end = self._money_spin()
        self.sch100_ppe_begin = self._money_spin()
        self.sch100_ppe_end = self._money_spin()

        assets_layout.addRow("Cash - Beginning:", self.sch100_cash_begin)
        assets_layout.addRow("Cash - Ending:", self.sch100_cash_end)
        assets_layout.addRow(
            "Accounts Receivable - Beginning:", self.sch100_ar_begin
        )
        assets_layout.addRow(
            "Accounts Receivable - Ending:", self.sch100_ar_end
        )
        assets_layout.addRow(
            "Inventory - Beginning:", self.sch100_inventory_begin
        )
        assets_layout.addRow("Inventory - Ending:", self.sch100_inventory_end)
        assets_layout.addRow(
            "Property, Plant & Equipment - Beginning:", self.sch100_ppe_begin
        )
        assets_layout.addRow(
            "Property, Plant & Equipment - Ending:", self.sch100_ppe_end
        )

        layout.addWidget(assets_group)

        # Liabilities
        liabilities_group = QGroupBox("Liabilities")
        liabilities_layout = QFormLayout(liabilities_group)

        self.sch100_ap_begin = self._money_spin()
        self.sch100_ap_end = self._money_spin()
        self.sch100_loans_begin = self._money_spin()
        self.sch100_loans_end = self._money_spin()

        liabilities_layout.addRow(
            "Accounts Payable - Beginning:", self.sch100_ap_begin
        )
        liabilities_layout.addRow(
            "Accounts Payable - Ending:", self.sch100_ap_end
        )
        liabilities_layout.addRow(
            "Loans/Debt - Beginning:", self.sch100_loans_begin
        )
        liabilities_layout.addRow(
            "Loans/Debt - Ending:", self.sch100_loans_end
        )

        layout.addWidget(liabilities_group)

        # Equity
        equity_group = QGroupBox("Equity")
        equity_layout = QFormLayout(equity_group)

        self.sch100_retained_earnings_begin = self._money_spin()
        self.sch100_retained_earnings_end = self._money_spin()

        equity_layout.addRow(
            "Retained Earnings - Beginning:",
            self.sch100_retained_earnings_begin,
        )
        equity_layout.addRow(
            "Retained Earnings - Ending:", self.sch100_retained_earnings_end
        )

        layout.addWidget(equity_group)

        # Save button
        # Button row
        btn_row_100 = QHBoxLayout()
        autofill_btn_100 = QPushButton("🔄 Auto-Fill from DB")
        autofill_btn_100.setStyleSheet(
            "background: #3b82f6; color: white; font-weight: bold;"
        )
        autofill_btn_100.clicked.connect(self._auto_fill_schedule_100)
        btn_row_100.addWidget(autofill_btn_100)
        autofill_btn_100_info = QLabel(
            "← pulls cash, AR, and PPE from banking/charter data"
        )
        autofill_btn_100_info.setStyleSheet(
            "color: #6b7280; font-style: italic;"
        )
        btn_row_100.addWidget(autofill_btn_100_info)
        btn_row_100.addStretch()
        save_btn_100 = QPushButton("💾 Save Schedule 100")
        save_btn_100.clicked.connect(lambda: self.save_schedule_100())
        btn_row_100.addWidget(save_btn_100)
        layout.addLayout(btn_row_100)

        layout.addStretch()

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        return container

    def _build_tax_calculation_tab(self) -> QWidget:
        """Tax calculation from Schedule 2"""
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)

        info = QLabel(
            "🧮 Tax Calculation\nEnter tax calculation from Schedule 2 or let"
            "it auto-calculate"

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        calc_group = QGroupBox("Tax Calculation")
        calc_layout = QFormLayout(calc_group)

        self.tax_net_income = self._money_spin(read_only=True)
        self.tax_taxable_income = self._money_spin()
        self.tax_small_business_income = self._money_spin()
        self.tax_general_income = self._money_spin(read_only=True)

        self.tax_federal_sbd = self._money_spin(read_only=True)
        self.tax_federal_general = self._money_spin(read_only=True)
        self.tax_provincial_sbd = self._money_spin(read_only=True)
        self.tax_provincial_general = self._money_spin(read_only=True)

        self.tax_total_federal = self._money_spin(read_only=True)
        self.tax_total_provincial = self._money_spin(read_only=True)
        self.tax_total_owing = self._money_spin(read_only=True)

        calc_layout.addRow(
            "Net Income (Schedule 1 Line 400):", self.tax_net_income
        )
        calc_layout.addRow("Taxable Income:", self.tax_taxable_income)
        calc_layout.addRow(
            "Small Business Income (≤ $500K):", self.tax_small_business_income
        )
        calc_layout.addRow("General Income:", self.tax_general_income)
        calc_layout.addRow("", QLabel(""))
        calc_layout.addRow("<b>Federal Tax:</b>", QLabel(""))
        calc_layout.addRow("  Small Business Deduction:", self.tax_federal_sbd)
        calc_layout.addRow("  General Rate:", self.tax_federal_general)
        calc_layout.addRow("  <b>Total Federal</b>:", self.tax_total_federal)
        calc_layout.addRow("", QLabel(""))
        calc_layout.addRow("<b>Provincial Tax (Alberta):</b>", QLabel(""))
        calc_layout.addRow("  Small Business:", self.tax_provincial_sbd)
        calc_layout.addRow("  General Rate:", self.tax_provincial_general)
        calc_layout.addRow(
            "  <b>Total Provincial:</b>", self.tax_total_provincial
        )
        calc_layout.addRow("", QLabel(""))
        calc_layout.addRow("<b>TOTAL TAX OWING:</b>", self.tax_total_owing)

        self.tax_small_business_income.valueChanged.connect(self._calc_tax)
        self.tax_taxable_income.valueChanged.connect(self._calc_tax)

        layout.addWidget(calc_group)

        calc_btn = QPushButton("🔄 Auto-Calculate from Schedule 1")
        calc_btn.clicked.connect(self.auto_calculate_tax)
        layout.addWidget(calc_btn)

        # GL deductibility review panel
        deduct_group = QGroupBox(
            "GL Deductibility Review (Schedule 1 Add-backs)"
        )
        deduct_layout = QVBoxLayout(deduct_group)

        deduct_info = QLabel(
            "Uses receipt-level T2 deductibility rules to calculate add-backs"
            "and flag risky wording."

        )
        deduct_info.setStyleSheet("color: #1f2937;")
        deduct_layout.addWidget(deduct_info)

        self.run_deductibility_btn = QPushButton(
            "📊 Analyze Deductibility for Selected Year"
        )
        self.run_deductibility_btn.clicked.connect(
            self.run_gl_deductibility_analysis
        )
        deduct_layout.addWidget(self.run_deductibility_btn)

        deduct_totals_layout = QFormLayout()
        self.deduct_book_expenses = QLabel(self.DEFAULT_CURRENCY)
        self.deduct_deductible_expenses = QLabel(self.DEFAULT_CURRENCY)
        self.deduct_total_addback = QLabel(self.DEFAULT_CURRENCY)
        self.deduct_warning_count = QLabel("0 warnings")
        deduct_totals_layout.addRow(
            "Book Expenses:", self.deduct_book_expenses
        )
        deduct_totals_layout.addRow(
            "Deductible Expenses:", self.deduct_deductible_expenses
        )
        deduct_totals_layout.addRow(
            "Schedule 1 Add-backs:", self.deduct_total_addback
        )
        deduct_totals_layout.addRow(
            "Audit Warnings:", self.deduct_warning_count
        )
        deduct_layout.addLayout(deduct_totals_layout)

        self.deduct_gl_table = QTableWidget()
        self.deduct_gl_table.setColumnCount(5)
        self.deduct_gl_table.setHorizontalHeaderLabels(
            ["GL Code", "Account", "Book", "Deductible", "Add-back"]
        )
        self.deduct_gl_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.deduct_gl_table.setMinimumHeight(220)
        deduct_layout.addWidget(self.deduct_gl_table)

        self.deduct_warning_details = QTextEdit()
        self.deduct_warning_details.setReadOnly(True)
        self.deduct_warning_details.setPlaceholderText(
            "Warnings will appear after analysis."
        )
        self.deduct_warning_details.setMaximumHeight(120)
        deduct_layout.addWidget(self.deduct_warning_details)

        layout.addWidget(deduct_group)

        save_btn = QPushButton("💾 Save Tax Calculation")
        save_btn.clicked.connect(lambda: self.save_tax_calculation())
        layout.addWidget(save_btn)

        layout.addStretch()

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        return container

    def _build_adjustments_tab(self) -> QWidget:
        """Manual adjustments tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "✏️ Adjustments\nEnter manual adjustments, reconciling items, or"
            "accountant entries"

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        self.adjustments_table = QTableWidget()
        self.adjustments_table.setColumnCount(5)
        self.adjustments_table.setHorizontalHeaderLabels(
            ["Type", "Description", "Amount", "Schedule/Line", "Notes"]
        )
        self.adjustments_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.adjustments_table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add Adjustment")
        add_btn.clicked.connect(self.add_adjustment)
        btn_layout.addWidget(add_btn)

        save_btn = QPushButton("💾 Save Adjustments")
        save_btn.clicked.connect(self.save_adjustments)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _build_summary_tab(self) -> QWidget:
        """Summary and filing status"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        summary_group = QGroupBox("T2 Return Summary")
        summary_layout = QFormLayout(summary_group)

        self.summary_revenue = QLabel(self.DEFAULT_CURRENCY)
        self.summary_expenses = QLabel(self.DEFAULT_CURRENCY)
        self.summary_net_income = QLabel(self.DEFAULT_CURRENCY)
        self.summary_taxable_income = QLabel(self.DEFAULT_CURRENCY)
        self.summary_tax_owing = QLabel(self.DEFAULT_CURRENCY)
        self.summary_status = QLabel("Draft")

        summary_layout.addRow("<b>Total Revenue:</b>", self.summary_revenue)
        summary_layout.addRow("<b>Total Expenses:</b>", self.summary_expenses)
        summary_layout.addRow("<b>Net Income:</b>", self.summary_net_income)
        summary_layout.addRow(
            "<b>Taxable Income:</b>", self.summary_taxable_income
        )
        summary_layout.addRow(
            "<b>Total Tax Owing:</b>", self.summary_tax_owing
        )
        summary_layout.addRow("<b>Status:</b>", self.summary_status)

        layout.addWidget(summary_group)

        # Filing information
        filing_group = QGroupBox("Filing Information")
        filing_layout = QFormLayout(filing_group)

        self.filing_status = QComboBox()
        self.filing_status.addItems(
            ["Draft", "Calculated", "Filed", "Amended"]
        )

        self.filing_date = QDateEdit()
        self.filing_date.setCalendarPopup(True)
        self.filing_date.setDisplayFormat("yyyy-MM-dd")

        self.filing_confirmation = QLineEdit()
        self.filing_confirmation.setPlaceholderText("CRA confirmation number")

        filing_layout.addRow("Status:", self.filing_status)
        filing_layout.addRow("Filed Date:", self.filing_date)
        filing_layout.addRow("Confirmation #:", self.filing_confirmation)
        self.filing_status.currentTextChanged.connect(self.refresh_summary)

        layout.addWidget(filing_group)

        paper_group = QGroupBox("Paper Submission Procedure")
        paper_layout = QVBoxLayout(paper_group)

        self.paper_filing_guidance = QLabel()
        self.paper_filing_guidance.setWordWrap(True)
        self.paper_filing_guidance.setStyleSheet(self.PAPER_INFO_STYLE)
        paper_layout.addWidget(self.paper_filing_guidance)

        self.paper_validation_summary = QLabel("Validation not run")
        self.paper_validation_summary.setWordWrap(True)
        self.paper_validation_summary.setStyleSheet(
            "background: #f3f4f6; padding: 8px; border-radius: 5px;"
        )
        paper_layout.addWidget(self.paper_validation_summary)

        paper_btn_layout = QHBoxLayout()

        validate_package_btn = QPushButton("Validate Package")
        validate_package_btn.clicked.connect(
            self.validate_paper_filing_package
        )
        paper_btn_layout.addWidget(validate_package_btn)

        preview_package_btn = QPushButton("Preview Paper Package")
        preview_package_btn.clicked.connect(self.preview_paper_filing_package)
        paper_btn_layout.addWidget(preview_package_btn)

        export_package_btn = QPushButton("Export Package")
        export_package_btn.clicked.connect(self.export_paper_filing_package)
        paper_btn_layout.addWidget(export_package_btn)

        print_package_btn = QPushButton("Print Package")
        print_package_btn.clicked.connect(self.print_paper_filing_package)
        paper_btn_layout.addWidget(print_package_btn)

        paper_btn_layout.addStretch()
        paper_layout.addLayout(paper_btn_layout)
        layout.addWidget(paper_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Add notes about this return...")
        self.notes_edit.setMaximumHeight(100)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group)

        # Buttons
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 Refresh Summary")
        refresh_btn.clicked.connect(self.refresh_summary)
        btn_layout.addWidget(refresh_btn)

        mark_filed_btn = QPushButton("✓ Mark as Filed")
        mark_filed_btn.setStyleSheet("background: #10b981; color: white;")
        mark_filed_btn.clicked.connect(self.mark_as_filed)
        btn_layout.addWidget(mark_filed_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        self._update_paper_filing_guidance()
        return widget

    def _money_spin(self, read_only=False) -> QDoubleSpinBox:
        """Create a currency spinbox"""
        spin = QDoubleSpinBox()
        spin.setMaximum(999999999.99)
        spin.setMinimum(-999999999.99)
        spin.setPrefix("$")
        spin.setGroupSeparatorShown(True)
        spin.setDecimals(2)
        spin.setReadOnly(read_only)
        if read_only:
            spin.setStyleSheet("background: #f3f4f6;")
        return spin

    def load_tax_years(self) -> None:
        """Load available tax years (2007-2025)"""
        current_year = QDate.currentDate().year()
        for year in range(2007, current_year + 1):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(
            str(current_year - 1)
        )  # Default to previous year

    def load_return_data(self) -> None:
        """Load existing T2 return data for selected year"""
        if not self.year_combo.currentText():
            return

        tax_year = int(self.year_combo.currentText())

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT return_id, corporation_name, business_number,
                    fiscal_year_end,
                           total_revenue, total_expenses, net_income,
                           taxable_income,
                           total_tax, status, filed_date
                    FROM t2_return_metadata
                    WHERE tax_year = %s
                """,
                    (tax_year,),
                )

                row = cur.fetchone()
                if row:
                    self.current_return_id = row[0]
                    # Set fiscal year end
                    if row[3]:
                        self.fiscal_year_end.setDate(QDate(row[3]))
                    # Set business number
                    if row[2]:
                        self.business_number.setText(row[2])
                    if row[10]:
                        status_text = str(row[10]).strip().title()
                        status_index = self.filing_status.findText(status_text)
                        if status_index >= 0:
                            self.filing_status.setCurrentIndex(status_index)
                    else:
                        self.filing_status.setCurrentText("Draft")
                    if row[11]:
                        self.filing_date.setDate(QDate(row[11]))

                    self.load_schedule_data()
                    self.refresh_summary()
                    self.set_status(
                        f"Loaded T2 return for {tax_year}", error=False
                    )
                else:
                    self.current_return_id = None
                    self.clear_all_fields()
                    self.set_status(
                        f"No existing T2 return for {tax_year}. Click 'New"
                        f"Return' to create one.",

                        error=False,
                    )

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error loading return: {e}", error=True)

    def create_new_return(self) -> None:
        """Create a new T2 return for the selected year"""
        if not self.year_combo.currentText():
            QMessageBox.warning(
                self, "No Year Selected", "Please select a tax year first."
            )
            return

        tax_year = int(self.year_combo.currentText())

        # Check if return already exists
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "SELECT return_id FROM t2_return_metadata WHERE tax_year"
                    "= %s",

                    (tax_year,),
                )
                if cur.fetchone():
                    reply = QMessageBox.question(
                        self,
                        "Return Exists",
                        f"A T2 return for {tax_year} already exists. Load it"
                        f"instead?",

                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.load_return_data()
                    return

                # Create new return
                fiscal_year_end = self.fiscal_year_end.date().toPyDate()
                business_number = self.business_number.text() or None

                cur.execute(
                    """
                    INSERT INTO t2_return_metadata (
                        tax_year, corporation_name, business_number,
                        fiscal_year_end,
                        status, created_by, created_at
                    )
                    VALUES (%s, %s, %s, %s, 'draft', 'desktop_app', NOW())
                    RETURNING return_id
                """,
                    (
                        tax_year,
                        "Arrow Limousine Ltd.",
                        business_number,
                        fiscal_year_end,
                    ),
                )

                self.current_return_id = cur.fetchone()[0]

                self.clear_all_fields()
                self.set_status(
                    f"Created new T2 return for {tax_year}", error=False
                )
                QMessageBox.information(
                    self, "Success", f"Created new T2 return for {tax_year}"
                )

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error creating return: {e}", error=True)
            QMessageBox.critical(
                self, "Error", f"Failed to create return: {e}"
            )

    def _extract_table_row_data(self, table, row) -> tuple[str, str, float, str] | None:
        """Extract and parse data from a table row"""
        line_num = table.item(row, 0).text() if table.item(row, 0) else ""
        desc = table.item(row, 1).text() if table.item(row, 1) else ""
        amount_text = table.item(row, 2).text() if table.item(row, 2) else "0"
        notes = table.item(row, 3).text() if table.item(row, 3) else ""

        if not line_num:
            return None

        try:
            amount = float(amount_text.replace(",", "").replace("$", ""))
        except (ValueError, AttributeError):
            amount = 0.0

        return line_num, desc, amount, notes

    def _find_schedule1_row(self, line_number) -> int | None:
        """Find the row index for a Schedule 1 line number."""
        for row in range(self.schedule1_table.rowCount()):
            item = self.schedule1_table.item(row, 0)
            if item and item.text().strip() == str(line_number):
                return row
        return None

    def _set_schedule1_line(self, line_number, amount, notes="") -> None:
        """Update a Schedule 1 line in the table if it exists."""
        row = self._find_schedule1_row(line_number)
        if row is None:
            return

        self.schedule1_table.setItem(
            row, 2, QTableWidgetItem(f"{float(amount):.2f}")
        )
        if notes:
            self.schedule1_table.setItem(row, 3, QTableWidgetItem(notes))

    def save_schedule_data(self, schedule_number) -> None:
        """Save schedule data from table"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if schedule_number == "1":
                    table = self.schedule1_table
                else:
                    return

                for row in range(table.rowCount()):
                    row_data = self._extract_table_row_data(table, row)
                    if row_data is None:
                        continue

                    line_num, desc, amount, notes = row_data

                    cur.execute(
                        """
                        INSERT INTO t2_schedule_data (
                            return_id, schedule_number, line_number,
                            line_description,
                            amount, calculation_notes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (return_id, schedule_number, line_number)
                        DO UPDATE SET
                            amount = EXCLUDED.amount,
                            line_description = EXCLUDED.line_description,
                            calculation_notes = EXCLUDED.calculation_notes,
                            updated_at = NOW()
                    """,
                        (
                            self.current_return_id,
                            schedule_number,
                            line_num,
                            desc,
                            amount,
                            notes,
                        ),
                    )

            self.set_status(
                f"Saved Schedule {schedule_number} data", error=False
            )

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error saving schedule: {e}", error=True)

    def save_schedule_125(self) -> None:
        """Save Schedule 125 income statement data"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Save each line
                lines = [
                    (
                        "8000",
                        "Sales, commissions, and fees",
                        self.sch125_revenue.value(),
                    ),
                    ("8089", "Other income", self.sch125_other_income.value()),
                    (
                        "8518",
                        "Cost of sales",
                        self.sch125_cost_of_sales.value(),
                    ),
                    (
                        "8513",
                        "Salaries and wages",
                        self.sch125_salaries.value(),
                    ),
                    (
                        "8523",
                        "Employee benefits",
                        self.sch125_benefits.value(),
                    ),
                    ("8690", "Rent", self.sch125_rent.value()),
                    (
                        "8690",
                        "Repairs and maintenance",
                        self.sch125_repairs.value(),
                    ),
                    ("8590", "Bad debts", self.sch125_bad_debts.value()),
                    (
                        "8711",
                        "Interest and bank charges",
                        self.sch125_interest.value(),
                    ),
                    ("9270", "Insurance", self.sch125_insurance.value()),
                    ("8810", "Office expenses", self.sch125_office.value()),
                    (
                        "8860",
                        "Professional fees",
                        self.sch125_professional_fees.value(),
                    ),
                    (
                        "9180",
                        "Property taxes",
                        self.sch125_property_tax.value(),
                    ),
                    ("9200", "Travel", self.sch125_travel.value()),
                    ("9281", "Vehicle expenses", self.sch125_vehicle.value()),
                    (
                        "9923",
                        "Other expenses",
                        self.sch125_other_expenses.value(),
                    ),
                ]

                for line_num, desc, amount in lines:
                    cur.execute(
                        """
                        INSERT INTO t2_schedule_data (
                            return_id, schedule_number, line_number,
                            line_description, amount
                        )
                        VALUES (%s, '125', %s, %s, %s)
                        ON CONFLICT (return_id, schedule_number, line_number)
                        DO UPDATE SET
                            amount = EXCLUDED.amount,
                            updated_at = NOW()
                    """,
                        (self.current_return_id, line_num, desc, amount),
                    )

                # Update metadata
                total_revenue = self.sch125_total_revenue.value()
                total_expenses = self.sch125_total_expenses.value()
                net_income = self.sch125_net_income.value()

                cur.execute(
                    """
                    UPDATE t2_return_metadata
                    SET total_revenue = %s,
                        total_expenses = %s,
                        net_income = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                """,
                    (
                        total_revenue,
                        total_expenses,
                        net_income,
                        self.current_return_id,
                    ),
                )

            self.set_status("Saved Schedule 125 data", error=False)
            QMessageBox.information(
                self, "Success", "Schedule 125 data saved successfully"
            )

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error saving Schedule 125: {e}", error=True)

    def save_schedule_100(self) -> None:
        """Save Schedule 100 balance sheet data"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Save balance sheet lines
                lines = [
                    (
                        "CASH_BEGIN",
                        "Cash - Beginning",
                        self.sch100_cash_begin.value(),
                    ),
                    (
                        "CASH_END",
                        "Cash - Ending",
                        self.sch100_cash_end.value(),
                    ),
                    (
                        "AR_BEGIN",
                        "Accounts Receivable - Beginning",
                        self.sch100_ar_begin.value(),
                    ),
                    (
                        "AR_END",
                        "Accounts Receivable - Ending",
                        self.sch100_ar_end.value(),
                    ),
                    (
                        "INV_BEGIN",
                        "Inventory - Beginning",
                        self.sch100_inventory_begin.value(),
                    ),
                    (
                        "INV_END",
                        "Inventory - Ending",
                        self.sch100_inventory_end.value(),
                    ),
                    (
                        "PPE_BEGIN",
                        "Property, Plant & Equipment - Beginning",
                        self.sch100_ppe_begin.value(),
                    ),
                    (
                        "PPE_END",
                        "Property, Plant & Equipment - Ending",
                        self.sch100_ppe_end.value(),
                    ),
                    (
                        "AP_BEGIN",
                        "Accounts Payable - Beginning",
                        self.sch100_ap_begin.value(),
                    ),
                    (
                        "AP_END",
                        "Accounts Payable - Ending",
                        self.sch100_ap_end.value(),
                    ),
                    (
                        "LOANS_BEGIN",
                        "Loans/Debt - Beginning",
                        self.sch100_loans_begin.value(),
                    ),
                    (
                        "LOANS_END",
                        "Loans/Debt - Ending",
                        self.sch100_loans_end.value(),
                    ),
                    (
                        "RE_BEGIN",
                        "Retained Earnings - Beginning",
                        self.sch100_retained_earnings_begin.value(),
                    ),
                    (
                        "RE_END",
                        "Retained Earnings - Ending",
                        self.sch100_retained_earnings_end.value(),
                    ),
                ]

                for line_num, desc, amount in lines:
                    cur.execute(
                        """
                        INSERT INTO t2_schedule_data (
                            return_id, schedule_number, line_number,
                            line_description, amount
                        )
                        VALUES (%s, '100', %s, %s, %s)
                        ON CONFLICT (return_id, schedule_number, line_number)
                        DO UPDATE SET
                            amount = EXCLUDED.amount,
                            updated_at = NOW()
                    """,
                        (self.current_return_id, line_num, desc, amount),
                    )

            self.set_status("Saved Schedule 100 data", error=False)
            QMessageBox.information(
                self, "Success", "Schedule 100 data saved successfully"
            )

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error saving Schedule 100: {e}", error=True)

    def save_tax_calculation(self) -> None:
        """Save tax calculation"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE t2_return_metadata
                    SET taxable_income = %s,
                        federal_tax = %s,
                        provincial_tax = %s,
                        total_tax = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                """,
                    (
                        self.tax_taxable_income.value(),
                        self.tax_total_federal.value(),
                        self.tax_total_provincial.value(),
                        self.tax_total_owing.value(),
                        self.current_return_id,
                    ),
                )

            self.set_status("Saved tax calculation", error=False)

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error saving tax: {e}", error=True)

    def _calc_sch125_totals(self) -> None:
        """Calculate Schedule 125 totals"""
        total_revenue = (
            self.sch125_revenue.value() + self.sch125_other_income.value()
        )
        self.sch125_total_revenue.setValue(total_revenue)

        total_expenses = (
            self.sch125_cost_of_sales.value()
            + self.sch125_salaries.value()
            + self.sch125_benefits.value()
            + self.sch125_rent.value()
            + self.sch125_repairs.value()
            + self.sch125_bad_debts.value()
            + self.sch125_interest.value()
            + self.sch125_insurance.value()
            + self.sch125_office.value()
            + self.sch125_professional_fees.value()
            + self.sch125_property_tax.value()
            + self.sch125_travel.value()
            + self.sch125_vehicle.value()
            + self.sch125_other_expenses.value()
        )
        self.sch125_total_expenses.setValue(total_expenses)

        net_income = total_revenue - total_expenses
        self.sch125_net_income.setValue(net_income)

        # Update tax calculation net income
        self.tax_net_income.setValue(net_income)

    def _calc_tax(self) -> None:
        """Calculate tax based on taxable income and tax rates"""
        taxable_income = self.tax_taxable_income.value()
        sbd_income = self.tax_small_business_income.value()
        general_income = max(0, taxable_income - sbd_income)

        self.tax_general_income.setValue(general_income)

        # Get tax rates for the year
        tax_year = (
            int(self.year_combo.currentText())
            if self.year_combo.currentText()
            else 2024
        )

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT federal_small_business_rate, federal_general_rate,
                           alberta_small_business_rate, alberta_general_rate
                    FROM corporate_tax_rates
                    WHERE tax_year = %s
                """,
                    (tax_year,),
                )

                row = cur.fetchone()
                if row:
                    fed_sbd_rate, fed_gen_rate, ab_sbd_rate, ab_gen_rate = row

                    fed_sbd_tax = sbd_income * fed_sbd_rate
                    fed_gen_tax = general_income * fed_gen_rate
                    ab_sbd_tax = sbd_income * ab_sbd_rate
                    ab_gen_tax = general_income * ab_gen_rate

                    self.tax_federal_sbd.setValue(fed_sbd_tax)
                    self.tax_federal_general.setValue(fed_gen_tax)
                    self.tax_provincial_sbd.setValue(ab_sbd_tax)
                    self.tax_provincial_general.setValue(ab_gen_tax)

                    total_federal = fed_sbd_tax + fed_gen_tax
                    total_provincial = ab_sbd_tax + ab_gen_tax
                    total_tax = total_federal + total_provincial

                    self.tax_total_federal.setValue(total_federal)
                    self.tax_total_provincial.setValue(total_provincial)
                    self.tax_total_owing.setValue(total_tax)

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error calculating tax: {e}", error=True)

    def auto_calculate_tax(self) -> None:
        """Auto-calculate tax from Schedule 1 and 125 data"""
        # Use net income from Schedule 125 as starting point
        net_income = self.sch125_net_income.value()

        tax_year = (
            int(self.year_combo.currentText())
            if self.year_combo.currentText()
            else None
        )
        add_back_total = 0.0
        if tax_year:
            analysis = self.latest_deductibility_analysis
            if not analysis or analysis.get("tax_year") != tax_year:
                analysis = self._fetch_deductibility_analysis(
                    tax_year, show_errors=False
                )
                if analysis:
                    self._apply_deductibility_to_ui(analysis)

            if analysis:
                add_back_total = float(analysis.get("total_add_back", 0) or 0)

        # Apply Schedule 1 add-backs from deductibility analysis to arrive at
        # taxable income.
        self.tax_taxable_income.setValue(net_income + add_back_total)

        # Assume all income qualifies for small business deduction (up to
        # $500K)
        small_business_limit = 500000
        sbd_income = min(net_income, small_business_limit)
        self.tax_small_business_income.setValue(sbd_income)

        # Trigger tax calculation
        self._calc_tax()

        if add_back_total > 0:
            self.set_status(
                f"Auto-calculated tax from net income +"
                f"${add_back_total:,.2f} add-backs",

                error=False,
            )
        else:
            self.set_status("Auto-calculated tax from net income", error=False)

    def _get_connection_params_for_analysis(self) -> dict[str, object]:
        """Resolve DB connection params for backend T2 analysis helper."""
        cfg = getattr(self.db, "config", None)
        if isinstance(cfg, dict):
            return cfg

        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", "almsdata"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
        }

    def _fetch_deductibility_analysis(self, tax_year, show_errors=True) -> dict | None:
        """Call shared T2 deductibility engine and return analysis payload."""
        try:
            from modern_backend.app.tax.t2_data_extraction import (
                T2DataExtractor,
            )

            extractor = T2DataExtractor(
                self._get_connection_params_for_analysis()
            )
            return extractor.extract_t2_deductibility_analysis(tax_year)
        except Exception as e:
            logger.error(f"Failed to run deductibility analysis: {e}")
            if show_errors:
                self.set_status(
                    f"Deductibility analysis failed: {e}", error=True
                )
                QMessageBox.critical(
                    self,
                    "Analysis Error",
                    f"Failed to run deductibility analysis:\n{e}",
                )
            return None

    def _save_deductibility_snapshot(self, analysis) -> None:
        """Persist the latest deductibility analysis for this T2 return."""
        if not self.current_return_id or not analysis:
            return

        warnings = analysis.get("audit_warnings", []) or []
        high_warning_count = sum(
            1
            for warning in warnings
            if (warning.get("severity") or "").upper() == "HIGH"
        )

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO t2_deductibility_audit (
                        return_id, tax_year, total_book_expenses,
                        total_deductible_expenses,
                        total_add_back, warning_count, high_warning_count,
                        analysis_version,
                        created_by, updated_at
                    )
                        VALUES (%s, %s, %s, %s, %s, %s, %s,
                            'v1', 'desktop_app', NOW())
                    ON CONFLICT (return_id)
                    DO UPDATE SET
                        tax_year = EXCLUDED.tax_year,
                        total_book_expenses = EXCLUDED.total_book_expenses,
                        total_deductible_expenses =
                        EXCLUDED.total_deductible_expenses,
                        total_add_back = EXCLUDED.total_add_back,
                        warning_count = EXCLUDED.warning_count,
                        high_warning_count = EXCLUDED.high_warning_count,
                        analysis_version = EXCLUDED.analysis_version,
                        updated_at = NOW()
                    RETURNING audit_id
                    """,
                    (
                        self.current_return_id,
                        analysis.get("tax_year"),
                        float(analysis.get("total_book_expenses", 0) or 0),
                        float(
                            analysis.get("total_deductible_expenses", 0) or 0
                        ),
                        float(analysis.get("total_add_back", 0) or 0),
                        len(warnings),
                        high_warning_count,
                    ),
                )
                audit_id = cur.fetchone()[0]

                cur.execute(
                    "DELETE FROM t2_deductibility_audit_gl "
                    "WHERE audit_id = %s",
                    (audit_id,),
                )
                cur.execute(
                    "DELETE FROM t2_deductibility_audit_warning "
                    "WHERE audit_id = %s",

                    (audit_id,),
                )

                for row in analysis.get("by_gl_code", []) or []:
                    cur.execute(
                        """
                        INSERT INTO t2_deductibility_audit_gl (
                            audit_id, gl_code, account_name, transaction_count,
                            book_amount, deductible_amount, add_back_amount,
                            notes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            audit_id,
                            row.get("gl_code"),
                            row.get("account_name"),
                            int(row.get("count", 0) or 0),
                            float(row.get("book_amount", 0) or 0),
                            float(row.get("deductible_amount", 0) or 0),
                            float(row.get("add_back_amount", 0) or 0),
                            row.get("notes", ""),
                        ),
                    )

                for warning in warnings:
                    cur.execute(
                        """
                        INSERT INTO t2_deductibility_audit_warning (
                            audit_id, severity, receipt_id, gl_code, vendor,
                            message
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            audit_id,
                            warning.get("severity", ""),
                            warning.get("receipt_id"),
                            warning.get("gl_code", ""),
                            warning.get("vendor", ""),
                            warning.get("message", ""),
                        ),
                    )
        except Exception as e:
            logger.error(f"Failed to save deductibility snapshot: {e}")
            self.set_status(
                f"Error saving deductibility snapshot: {e}", error=True
            )

    def _load_deductibility_snapshot(self) -> dict | None:
        """Load a saved deductibility snapshot for the active return, if"
        "present."""

        if not self.current_return_id:
            return None

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT audit_id, tax_year, total_book_expenses,
                    total_deductible_expenses,
                           total_add_back
                    FROM t2_deductibility_audit
                    WHERE return_id = %s
                    """,
                    (self.current_return_id,),
                )
                audit_row = cur.fetchone()
                if not audit_row:
                    return None

                (
                    audit_id,
                    tax_year,
                    total_book,
                    total_deductible,
                    total_add_back,
                ) = audit_row

                cur.execute(
                    """
                    SELECT gl_code, account_name, transaction_count,
                    book_amount,
                           deductible_amount, add_back_amount,
                           COALESCE(notes, '')
                    FROM t2_deductibility_audit_gl
                    WHERE audit_id = %s
                    ORDER BY add_back_amount DESC, gl_code
                    """,
                    (audit_id,),
                )
                gl_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT severity, receipt_id, gl_code, vendor, message
                    FROM t2_deductibility_audit_warning
                    WHERE audit_id = %s
                    ORDER BY severity DESC, audit_warning_id
                    """,
                    (audit_id,),
                )
                warning_rows = cur.fetchall()

                return {
                    "tax_year": int(tax_year),
                    "total_book_expenses": float(total_book or 0),
                    "total_deductible_expenses": float(total_deductible or 0),
                    "total_add_back": float(total_add_back or 0),
                    "by_gl_code": [
                        {
                            "gl_code": row[0],
                            "account_name": row[1],
                            "count": row[2],
                            "book_amount": float(row[3] or 0),
                            "deductible_amount": float(row[4] or 0),
                            "add_back_amount": float(row[5] or 0),
                            "notes": row[6],
                        }
                        for row in gl_rows
                    ],
                    "audit_warnings": [
                        {
                            "severity": row[0],
                            "receipt_id": row[1],
                            "gl_code": row[2],
                            "vendor": row[3],
                            "message": row[4],
                        }
                        for row in warning_rows
                    ],
                }
        except Exception as e:
            logger.error(f"Failed to load deductibility snapshot: {e}")
            return None

    def _apply_deductibility_to_ui(self, analysis) -> None:
        """Render deductibility totals, top GL add-backs, and warning"
        "details."""

        self.latest_deductibility_analysis = analysis

        book = float(analysis.get("total_book_expenses", 0) or 0)
        deductible = float(analysis.get("total_deductible_expenses", 0) or 0)
        add_back = float(analysis.get("total_add_back", 0) or 0)
        warnings = analysis.get("audit_warnings", []) or []

        self.deduct_book_expenses.setText(f"${book:,.2f}")
        self.deduct_deductible_expenses.setText(f"${deductible:,.2f}")
        self.deduct_total_addback.setText(f"${add_back:,.2f}")

        # Keep Schedule 1 additions synchronized with the computed T2 add-back
        # total.
        self._set_schedule1_line(
            "200",
            add_back,
            "Auto-populated from GL deductibility analysis",
        )

        high_count = sum(
            1 for w in warnings if (w.get("severity") or "").upper() == "HIGH"
        )
        med_count = sum(
            1
            for w in warnings
            if (w.get("severity") or "").upper() == "MEDIUM"
        )
        self.deduct_warning_count.setText(
            f"{len(warnings)} warnings (HIGH: {high_count}, MEDIUM:"
            f"{med_count})"

        )

        rows = analysis.get("by_gl_code", []) or []
        rows = [r for r in rows if float(r.get("add_back_amount", 0) or 0) > 0]
        rows = rows[:20]
        self.deduct_gl_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.deduct_gl_table.setItem(
                i, 0, QTableWidgetItem(str(row.get("gl_code", "")))
            )
            self.deduct_gl_table.setItem(
                i, 1, QTableWidgetItem(str(row.get("account_name", "")))
            )
            self.deduct_gl_table.setItem(
                i,
                2,
                QTableWidgetItem(
                    f"${float(row.get('book_amount', 0) or 0):,.2f}"
                ),
            )
            self.deduct_gl_table.setItem(
                i,
                3,
                QTableWidgetItem(
                    f"${float(row.get('deductible_amount', 0) or 0):,.2f}"
                ),
            )
            self.deduct_gl_table.setItem(
                i,
                4,
                QTableWidgetItem(
                    f"${float(row.get('add_back_amount', 0) or 0):,.2f}"
                ),
            )

        warning_lines = []
        for warning in warnings[:25]:
            severity = warning.get("severity", "UNKNOWN")
            receipt_id = warning.get("receipt_id", "")
            gl_code = warning.get("gl_code", "")
            vendor = warning.get("vendor", "")
            message = warning.get("message", "")
            warning_lines.append(
                f"[{severity}] Receipt {receipt_id} | GL {gl_code} | {vendor}"
                f"| {message}"

            )

        if warnings and len(warnings) > 25:
            warning_lines.append(
                f"... plus {len(warnings) - 25} more warnings."
            )

        self.deduct_warning_details.setPlainText("\n".join(warning_lines))

    def run_gl_deductibility_analysis(self) -> None:
        """Run T2 deductibility analysis for selected year and update panel."""
        if not self.year_combo.currentText():
            QMessageBox.warning(
                self, "No Year Selected", "Please select a tax year first."
            )
            return

        tax_year = int(self.year_combo.currentText())
        analysis = self._fetch_deductibility_analysis(
            tax_year, show_errors=True
        )
        if not analysis:
            return

        self._apply_deductibility_to_ui(analysis)
        self._save_deductibility_snapshot(analysis)
        self.set_status(
            f"Loaded GL deductibility analysis for {tax_year}", error=False
        )

    def load_schedule_data(self) -> None:
        """Load schedule data from database"""
        if not self.current_return_id:
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Load Schedule 1 table data
                cur.execute(
                    """
                          SELECT line_number, line_description, amount,
                              COALESCE(calculation_notes, '')
                    FROM t2_schedule_data
                    WHERE return_id = %s AND schedule_number = '1'
                """,
                    (self.current_return_id,),
                )

                schedule1_rows = {row[0]: row for row in cur.fetchall()}
                for table_row in range(self.schedule1_table.rowCount()):
                    line_item = self.schedule1_table.item(table_row, 0)
                    if not line_item:
                        continue

                    line_number = line_item.text().strip()
                    saved_row = schedule1_rows.get(line_number)
                    if not saved_row:
                        continue

                    _, description, amount, notes = saved_row
                    self.schedule1_table.setItem(
                        table_row, 1, QTableWidgetItem(description or "")
                    )
                    self.schedule1_table.setItem(
                        table_row,
                        2,
                        QTableWidgetItem(f"{float(amount or 0): .2f} "),
                    )
                    self.schedule1_table.setItem(
                        table_row, 3, QTableWidgetItem(notes or "")
                    )

                # Load Schedule 125 data
                cur.execute(
                    """
                    SELECT line_number, amount
                    FROM t2_schedule_data
                    WHERE return_id = %s AND schedule_number = '125'
                """,
                    (self.current_return_id,),
                )

                sch125_map = {
                    "8000": self.sch125_revenue,
                    "8089": self.sch125_other_income,
                    "8518": self.sch125_cost_of_sales,
                    "8513": self.sch125_salaries,
                    "8523": self.sch125_benefits,
                    "8690": self.sch125_rent,  # First 8690
                    "8590": self.sch125_bad_debts,
                    "8711": self.sch125_interest,
                    "9270": self.sch125_insurance,
                    "8810": self.sch125_office,
                    "8860": self.sch125_professional_fees,
                    "9180": self.sch125_property_tax,
                    "9200": self.sch125_travel,
                    "9281": self.sch125_vehicle,
                    "9923": self.sch125_other_expenses,
                }

                for row in cur.fetchall():
                    line_num, amount = row
                    if line_num in sch125_map:
                        sch125_map[line_num].setValue(float(amount or 0))

                # Load tax data from metadata
                cur.execute(
                    """
                    SELECT taxable_income, federal_tax, provincial_tax,
                    total_tax
                    FROM t2_return_metadata
                    WHERE return_id = %s
                """,
                    (self.current_return_id,),
                )

                row = cur.fetchone()
                if row:
                    taxable, _fed, _prov, total = row
                    if taxable:
                        self.tax_taxable_income.setValue(float(taxable))
                    if total:
                        self.tax_total_owing.setValue(float(total))

            saved_analysis = self._load_deductibility_snapshot()
            if saved_analysis:
                self._apply_deductibility_to_ui(saved_analysis)

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error loading schedule data: {e}", error=True)

            self._load_cca_schedule()
            self._load_shareholders()

    def add_schedule_line(self, table, _schedule_num) -> None:
        """Add a new line to schedule table"""
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(""))
        table.setItem(row, 1, QTableWidgetItem(""))
        table.setItem(row, 2, QTableWidgetItem("0.00"))
        table.setItem(row, 3, QTableWidgetItem(""))

    def add_adjustment(self) -> None:
        """Add new adjustment row"""
        row = self.adjustments_table.rowCount()
        self.adjustments_table.insertRow(row)

        type_combo = QComboBox()
        type_combo.addItems(
            [
                "Manual",
                "CCA",
                "Meals & Entertainment",
                "Non-Deductible",
                "Other",
            ]
        )
        self.adjustments_table.setCellWidget(row, 0, type_combo)

    def save_adjustments(self) -> None:
        """Save adjustments to database"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Delete existing adjustments
                cur.execute(
                    "DELETE FROM t2_adjustments WHERE return_id = %s",
                    (self.current_return_id,),
                )

                # Insert new adjustments
                for row in range(self.adjustments_table.rowCount()):
                    type_widget = self.adjustments_table.cellWidget(row, 0)
                    adj_type = (
                        type_widget.currentText() if type_widget else "Manual"
                    )

                    desc_item = self.adjustments_table.item(row, 1)
                    description = desc_item.text() if desc_item else ""

                    amt_item = self.adjustments_table.item(row, 2)
                    amount = (
                        float(
                            amt_item.text().replace(",", "").replace("$", "")
                        )
                        if amt_item
                        else 0
                    )

                    if description:  # Only save if there's a description
                        cur.execute(
                            """
                            INSERT INTO t2_adjustments (
                                return_id, adjustment_type, description,
                                amount, created_by
                            )
                            VALUES (%s, %s, %s, %s, 'desktop_app')
                        """,
                            (
                                self.current_return_id,
                                adj_type,
                                description,
                                amount,
                            ),
                        )

            self.set_status("Saved adjustments", error=False)

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error saving adjustments: {e}", error=True)

    def refresh_summary(self) -> None:
        """Refresh summary tab with latest data"""
        self.summary_revenue.setText(
            f"${self.sch125_total_revenue.value():,.2f}"
        )
        self.summary_expenses.setText(
            f"${self.sch125_total_expenses.value():,.2f}"
        )
        self.summary_net_income.setText(
            f"${self.sch125_net_income.value():,.2f}"
        )
        self.summary_taxable_income.setText(
            f"${self.tax_taxable_income.value():,.2f}"
        )
        self.summary_tax_owing.setText(f"${self.tax_total_owing.value():,.2f}")
        self.summary_status.setText(self.filing_status.currentText())
        self._update_paper_filing_guidance()

    def mark_as_filed(self) -> None:
        """Mark return as filed"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        selected_status = self.filing_status.currentText()
        if selected_status == "Filed":
            if not self._ensure_paper_filing_ready():
                self.set_status(
                    "Filing blocked by paper filing validation", error=True
                )
                return

            tax_year = (
                int(self.year_combo.currentText())
                if self.year_combo.currentText()
                else None
            )
            analysis = self.latest_deductibility_analysis

            if tax_year and (
                not analysis or analysis.get("tax_year") != tax_year
            ):
                analysis = self._fetch_deductibility_analysis(
                    tax_year, show_errors=True
                )
                if not analysis:
                    return
                self._apply_deductibility_to_ui(analysis)

            warnings = analysis.get("audit_warnings", []) if analysis else []
            high_warnings = [
                warning
                for warning in warnings
                if (warning.get("severity") or "").upper() == "HIGH"
            ]

            if high_warnings:
                preview = []
                for warning in high_warnings[:5]:
                    preview.append(
                        f"Receipt {warning.get('receipt_id', '')} | GL"
                        f"{warning.get('gl_code', '')} | "

                        f"{warning.get('vendor', '')} |"
                        f"{warning.get('message', '')}"

                    )

                message = (
                    "Cannot mark this T2 return as filed while HIGH "
                    "deductibility warnings remain.\n\n"
                )
                message += "Review these items first:\n"
                message += "\n".join(preview)
                if len(high_warnings) > 5:
                    message += (
                        f"\n... plus {len(high_warnings) - 5} "
                        "more HIGH warnings."
                    )

                QMessageBox.warning(self, "Filing Blocked", message)
                self.set_status(
                    "Filing blocked by HIGH deductibility warnings", error=True
                )
                return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE t2_return_metadata
                    SET status = %s,
                        filed_date = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                """,
                    (
                        selected_status,
                        (
                            self.filing_date.date().toPyDate()
                            if selected_status == "Filed"
                            else None
                        ),
                        self.current_return_id,
                    ),
                )

            self.set_status("Updated filing status", error=False)
            QMessageBox.information(self, "Success", "Filing status updated")

        except Exception as e:
            logger.error(f"Failed: {e}")
            self.set_status(f"Error updating status: {e}", error=True)

    def save_all_data(self) -> None:
        """Save all tabs"""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        self.save_schedule_125()
        self.save_schedule_100()
        self.save_tax_calculation()
        self.save_adjustments()
        self.mark_as_filed()
        self._save_cca_schedule()
        self._save_shareholders()

        self.refresh_summary()
        QMessageBox.information(
            self, "Success", "All T2 data saved successfully!"
        )

    def clear_all_fields(self) -> None:
        """Clear all input fields"""
        # Schedule 125
        for field in [
            self.sch125_revenue,
            self.sch125_other_income,
            self.sch125_cost_of_sales,
            self.sch125_salaries,
            self.sch125_benefits,
            self.sch125_rent,
            self.sch125_repairs,
            self.sch125_bad_debts,
            self.sch125_interest,
            self.sch125_insurance,
            self.sch125_office,
            self.sch125_professional_fees,
            self.sch125_property_tax,
            self.sch125_travel,
            self.sch125_vehicle,
            self.sch125_other_expenses,
        ]:
            field.setValue(0)

        # Tax
        self.tax_taxable_income.setValue(0)
        self.tax_small_business_income.setValue(0)

        self.latest_deductibility_analysis = None
        self.deduct_book_expenses.setText(self.DEFAULT_CURRENCY)
        self.deduct_deductible_expenses.setText(self.DEFAULT_CURRENCY)
        self.deduct_total_addback.setText(self.DEFAULT_CURRENCY)
        self.deduct_warning_count.setText("0 warnings")
        self.deduct_gl_table.setRowCount(0)
        self.deduct_warning_details.clear()
        self.summary_revenue.setText(self.DEFAULT_CURRENCY)
        self.summary_expenses.setText(self.DEFAULT_CURRENCY)
        self.summary_net_income.setText(self.DEFAULT_CURRENCY)
        self.summary_taxable_income.setText(self.DEFAULT_CURRENCY)
        self.summary_tax_owing.setText(self.DEFAULT_CURRENCY)
        self.summary_status.setText("Draft")
        self.filing_status.setCurrentText("Draft")
        self.filing_date.setDate(QDate.currentDate())
        self.filing_confirmation.clear()
        self.notes_edit.clear()
        self._update_paper_filing_guidance()

    def set_status(self, message, error=False) -> None:
        """Set status bar message"""
        self.status_label.setText(message)
        if error:
            self.status_label.setStyleSheet(
                "padding: 5px; background: #fee2e2; color: #dc2626;"
                "border-radius: 3px;"

            )
        else:
            self.status_label.setStyleSheet(
                "padding: 5px; background: #d1fae5; color: #065f46;"
                "border-radius: 3px;"

            )

    def _update_paper_filing_guidance(self) -> None:
        """Update the paper filing guidance block for the selected year."""
        due_date = self.fiscal_year_end.date().addMonths(6)
        due_text = (
            due_date.toString("yyyy-MM-dd")
            if due_date.isValid()
            else "Unknown"
        )
        tax_year = self.year_combo.currentText() or "selected year"
        status = self.filing_status.currentText()
        self.paper_filing_guidance.setText(
            "CRA paper workflow: if this return cannot be transmitted"
            "electronically, print the official "

            "T2/T2 Short and required schedules, sign the return, and mail it"
            "to the correct CRA tax centre. "

            f"This package summarizes the values entered for tax year"
            f"{tax_year}, shows what to print, and helps "

            f"track the paper filing. Filing due date: {due_text}. Current"
            f"status: {status}."

        )

    def _set_paper_validation_summary(self, blocking_issues, warnings) -> None:
        """Update the validation summary banner."""
        if blocking_issues:
            summary = (
                f"Blocking issues: {len(blocking_issues)} | "
                f"Warnings: {len(warnings)}"
            )
            style = (
                "background: #fee2e2; color: #991b1b; padding: 8px; "
                "border-radius: 5px;"
            )
        elif warnings:
            summary = f"Ready with warnings: {len(warnings)}"
            style = (
                "background: #fef3c7; color: #92400e; padding: 8px; "
                "border-radius: 5px;"
            )
        else:
            summary = "Paper filing package validated: no blocking issues"
            style = (
                "background: #d1fae5; color: #065f46; padding: 8px; "
                "border-radius: 5px;"
            )

        self.paper_validation_summary.setText(summary)
        self.paper_validation_summary.setStyleSheet(style)

    def _validate_paper_filing_inputs(self) -> tuple[list[str], list[str]]:
        """Return blocking issues and warnings for the paper filing package."""
        blocking_issues = []
        warnings = []

        business_number = self.business_number.text().strip()
        if not business_number:
            blocking_issues.append("Business number is missing.")

        fiscal_year_end = self.fiscal_year_end.date()
        if not fiscal_year_end.isValid():
            blocking_issues.append("Fiscal year end is missing or invalid.")

        schedule1_lines = self._schedule1_lines_for_package()
        if (
            not schedule1_lines
            and self.sch125_total_revenue.value() == 0
            and self.sch125_total_expenses.value() == 0
        ):
            blocking_issues.append(
                "No Schedule 1 lines or Schedule 125 totals have been entered."
            )

        expected_net_income = (
            self.sch125_total_revenue.value()
            - self.sch125_total_expenses.value()
        )
        if abs(expected_net_income - self.sch125_net_income.value()) > 0.01:
            blocking_issues.append(
                "Schedule 125 net income does not match revenue minus"
                "expenses."

            )

        if (
            self.tax_taxable_income.value() == 0
            and abs(self.sch125_net_income.value()) > 0.01
        ):
            warnings.append(
                "Taxable income is zero while net income is non-zero. Review"
                "tax calculation and Schedule 1 adjustments."

            )

        if (
            self.tax_total_owing.value() == 0
            and self.tax_taxable_income.value() > 0
        ):
            warnings.append(
                "Total tax owing is zero while taxable income is positive."
                "Confirm rates, deductions, and credits."

            )

        if not self.notes_edit.toPlainText().strip():
            warnings.append("No return notes entered.")

        due_date = fiscal_year_end.addMonths(6)
        if due_date.isValid() and due_date < QDate.currentDate():
            warnings.append(
                f"The filing due date {due_date.toString('yyyy-MM-dd')} has"
                f"already passed."

            )

        if (
            hasattr(self, "cca_table")
            and self.sch100_ppe_end.value() > 0
            and not self._cca_rows_for_package()
        ):
            warnings.append(
                "Schedule 100 shows ending PPE but Schedule 8 has no CCA rows."
            )

        if (
            hasattr(self, "shareholders_table")
            and not self._shareholder_rows_for_package()
        ):
            warnings.append("Schedule 50 has no shareholder rows.")

        if (
            self.filing_status.currentText() in {"Filed", "Amended"}
            and not self.filing_confirmation.text().strip()
        ):
            warnings.append("Filing confirmation/reference is blank.")

        self._set_paper_validation_summary(blocking_issues, warnings)
        return blocking_issues, warnings

    def validate_paper_filing_package(self, show_dialog=True) -> bool:
        """Validate the paper filing package and optionally show a dialog."""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return False

        blocking_issues, warnings = self._validate_paper_filing_inputs()

        if show_dialog:
            lines = []
            if blocking_issues:
                lines.append("Blocking issues:")
                lines.extend(f"- {issue}" for issue in blocking_issues)
            if warnings:
                if lines:
                    lines.append("")
                lines.append("Warnings:")
                lines.extend(f"- {warning}" for warning in warnings)
            if not lines:
                lines.append("No blocking issues or warnings.")

            dialog_title = "Paper Filing Validation"
            if blocking_issues:
                QMessageBox.warning(self, dialog_title, "\n".join(lines))
            else:
                QMessageBox.information(self, dialog_title, "\n".join(lines))

        return not blocking_issues

    def _ensure_paper_filing_ready(self) -> bool:
        """Validate the package before export, print, or filing."""
        return self.validate_paper_filing_package(show_dialog=True)

    def _parse_table_amount(self, item) -> float:
        """Parse a numeric amount from a table cell."""
        if not item:
            return 0.0

        text = (item.text() or "").strip()
        if not text:
            return 0.0

        try:
            return float(text.replace(",", "").replace("$", ""))
        except ValueError:
            return 0.0

    def _schedule1_lines_for_package(self) -> list[tuple[str, str, float, str]]:
        """Return Schedule 1 lines worth showing in the paper package."""
        lines = []
        for row in range(self.schedule1_table.rowCount()):
            line_item = self.schedule1_table.item(row, 0)
            if not line_item or not (line_item.text() or "").strip():
                continue

            amount = self._parse_table_amount(
                self.schedule1_table.item(row, 2)
            )
            notes = (
                self.schedule1_table.item(row, 3).text().strip()
                if self.schedule1_table.item(row, 3)
                else ""
            )
            description = (
                self.schedule1_table.item(row, 1).text().strip()
                if self.schedule1_table.item(row, 1)
                else ""
            )
            if abs(amount) < 0.005 and not notes:
                continue

            lines.append(
                (line_item.text().strip(), description, amount, notes)
            )
        return lines

    def _cca_rows_for_package(self) -> list[tuple[str, str, str, float, float, float, float, float]]:
        """Return non-empty CCA rows for the package."""
        if not hasattr(self, "cca_table"):
            return []

        rows = []
        for row in range(self.cca_table.rowCount()):
            description = (
                self.cca_table.item(row, 0).text().strip()
                if self.cca_table.item(row, 0)
                else ""
            )
            if not description:
                continue

            cca_class = (
                self.cca_table.item(row, 1).text().strip()
                if self.cca_table.item(row, 1)
                else ""
            )
            rate = (
                self.cca_table.item(row, 2).text().strip()
                if self.cca_table.item(row, 2)
                else ""
            )
            opening = self._parse_table_amount(self.cca_table.item(row, 3))
            additions = self._parse_table_amount(self.cca_table.item(row, 4))
            disposals = self._parse_table_amount(self.cca_table.item(row, 5))
            cca_claim = self._parse_table_amount(self.cca_table.item(row, 7))
            closing = self._parse_table_amount(self.cca_table.item(row, 8))
            rows.append(
                (
                    description,
                    cca_class,
                    rate,
                    opening,
                    additions,
                    disposals,
                    cca_claim,
                    closing,
                )
            )
        return rows

    def _shareholder_rows_for_package(self) -> list[tuple[str, str, str, str, str, str]]:
        """Return non-empty Schedule 50 rows for the package."""
        if not hasattr(self, "shareholders_table"):
            return []

        rows = []
        for row in range(self.shareholders_table.rowCount()):
            name = (
                self.shareholders_table.item(row, 0).text().strip()
                if self.shareholders_table.item(row, 0)
                else ""
            )
            if not name:
                continue

            address = (
                self.shareholders_table.item(row, 2).text().strip()
                if self.shareholders_table.item(row, 2)
                else ""
            )
            share_class = (
                self.shareholders_table.item(row, 3).text().strip()
                if self.shareholders_table.item(row, 3)
                else ""
            )
            num_shares = (
                self.shareholders_table.item(row, 4).text().strip()
                if self.shareholders_table.item(row, 4)
                else ""
            )
            pct = (
                self.shareholders_table.item(row, 5).text().strip()
                if self.shareholders_table.item(row, 5)
                else ""
            )
            director_widget = self.shareholders_table.cellWidget(row, 6)
            is_director = (
                director_widget.currentText() if director_widget else ""
            )
            rows.append(
                (name, address, share_class, num_shares, pct, is_director)
            )
        return rows

    def _build_paper_filing_package(self) -> str:
        """Build a text package for paper T2 filing and workpapers."""
        tax_year = self.year_combo.currentText() or "Unknown"
        fiscal_year_end = self.fiscal_year_end.date().toString("yyyy-MM-dd")
        filing_due = (
            self.fiscal_year_end.date().addMonths(6).toString("yyyy-MM-dd")
        )
        business_number = self.business_number.text().strip() or "Not entered"
        status = self.filing_status.currentText()
        confirmation = self.filing_confirmation.text().strip() or "N/A"
        notes = self.notes_edit.toPlainText().strip()

        schedule1_lines = self._schedule1_lines_for_package()
        cca_rows = self._cca_rows_for_package()
        shareholder_rows = self._shareholder_rows_for_package()

        required_forms = [
            "T2 Corporation Income Tax Return or T2 Short Return, as"
            "applicable",

            "Schedule 1 - Net Income (Loss) for Income Tax Purposes",
            "Schedule 100 - Balance Sheet Information",
            "Schedule 125 - Income Statement Information",
        ]
        if cca_rows:
            required_forms.append("Schedule 8 - Capital Cost Allowance (CCA)")
        if shareholder_rows:
            required_forms.append("Schedule 50 - Shareholder Information")

        lines = [
            "ARROW LIMO T2 PAPER FILING PACKAGE",
            "=" * 72,
            "",
            "This is an internal paper-filing package generated from the"
            "desktop app.",

            "Use it to prepare and review the official CRA T2/T2 Short and"
            "schedules.",

            "It is not a CRA-certified 2D barcode return.",
            "",
            "RETURN COVER",
            f"Tax year: {tax_year}",
            "Corporation: Arrow Limousine Ltd.",
            f"Business number: {business_number}",
            f"Fiscal year end: {fiscal_year_end}",
            f"Filing due date: {filing_due}",
            f"Current filing status: {status}",
            f"Confirmation/reference: {confirmation}",
            "",
            "PAPER SUBMISSION CHECKLIST",
            "1. Print the official CRA T2/T2 Short and every required"
            "schedule listed below.",

            "2. Transfer or verify the values from this package against the"
            "official forms.",

            "3. Sign and date the return where required and keep a full copy"
            "for records.",

            "4. Attach supporting schedules and any additional working papers"
            "or elections that must travel with the return.",

            "5. Mail the package to the correct CRA tax centre for the"
            "corporation and keep proof of mailing.",

            "6. If tax is owing, pay separately using CRA payment channels;"
            "mailing the return does not make payment automatically.",

            "",
            "FORMS AND SCHEDULES TO PRINT",
        ]

        for form_name in required_forms:
            lines.append(f"- {form_name}")

        lines.extend(
            [
                "",
                "VALIDATION SUMMARY",
            ]
        )

        blocking_issues, warnings = self._validate_paper_filing_inputs()
        if blocking_issues:
            lines.append("Blocking issues present:")
            lines.extend(f"- {issue}" for issue in blocking_issues)
        else:
            lines.append("No blocking issues.")

        if warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in warnings)
        else:
            lines.append("No warnings.")

        lines.extend(
            [
                "",
                "SUMMARY TOTALS",
                f"Total revenue: ${self.sch125_total_revenue.value():,.2f}",
                f"Total expenses: ${self.sch125_total_expenses.value():,.2f}",
                f"Net income: ${self.sch125_net_income.value():,.2f}",
                f"Taxable income: ${self.tax_taxable_income.value():,.2f}",
                f"Federal tax: ${self.tax_total_federal.value():,.2f}",
                f"Provincial tax: ${self.tax_total_provincial.value():,.2f}",
                f"Total tax owing: ${self.tax_total_owing.value():,.2f}",
                "",
                "SCHEDULE 125 SNAPSHOT",
                f"Line 8000 Sales, commissions, fees:"
                f"${self.sch125_revenue.value():,.2f}",

                f"Line 8089 Other income:"
                f"${self.sch125_other_income.value():,.2f}",

                f"Line 8518 Cost of sales:"
                f"${self.sch125_cost_of_sales.value():,.2f}",

                f"Line 8513 Salaries and wages:"
                f"${self.sch125_salaries.value():,.2f}",

                f"Line 8523 Employee benefits:"
                f"${self.sch125_benefits.value():,.2f}",

                f"Line 8690 Rent: ${self.sch125_rent.value():,.2f}",
                f"Repairs and maintenance: "
                f"${self.sch125_repairs.value():,.2f}",
                f"Line 8590 Bad debts: ${self.sch125_bad_debts.value():,.2f}",
                f"Line 8711 Interest and bank charges:"
                f"${self.sch125_interest.value():,.2f}",

                f"Line 9270 Insurance: ${self.sch125_insurance.value():,.2f}",
                f"Line 8810 Office expenses:"
                f"${self.sch125_office.value():,.2f}",

                f"Line 8860 Professional fees:"
                f"${self.sch125_professional_fees.value():,.2f}",

                f"Line 9180 Property taxes:"
                f"${self.sch125_property_tax.value():,.2f}",

                f"Line 9200 Travel: ${self.sch125_travel.value():,.2f}",
                f"Line 9281 Vehicle expenses:"
                f"${self.sch125_vehicle.value():,.2f}",

                f"Line 9923 Other expenses:"
                f"${self.sch125_other_expenses.value():,.2f}",

                "",
                "SCHEDULE 100 SNAPSHOT",
                f"Cash beginning/end: ${self.sch100_cash_begin.value():,.2f}"
                f"/ ${self.sch100_cash_end.value():,.2f}",

                f"Accounts receivable beginning/end:"
                f"${self.sch100_ar_begin.value():,.2f} /"
                f"${self.sch100_ar_end.value():,.2f}",


                f"Inventory beginning/end:"
                f"${self.sch100_inventory_begin.value():,.2f} /"
                f"${self.sch100_inventory_end.value():,.2f}",


                f"PPE beginning/end: ${self.sch100_ppe_begin.value():,.2f} /"
                f"${self.sch100_ppe_end.value():,.2f}",

                f"Accounts payable beginning/end:"
                f"${self.sch100_ap_begin.value():,.2f} /"
                f"${self.sch100_ap_end.value():,.2f}",


                f"Loans beginning/end:"
                f"${self.sch100_loans_begin.value():,.2f} /"
                f"${self.sch100_loans_end.value():,.2f}",


                f"Retained earnings beginning/end:"
                f"${self.sch100_retained_earnings_begin.value():,.2f} /"
                f"${self.sch100_retained_earnings_end.value():,.2f}",


                "",
                "SCHEDULE 1 LINES ENTERED",
            ]
        )

        if schedule1_lines:
            for (
                line_number,
                description,
                amount,
                line_notes,
            ) in schedule1_lines:
                line_text = (
                    f"Line {line_number}: {description} = ${amount:,.2f}"
                )
                if line_notes:
                    line_text += f" | Notes: {line_notes}"
                lines.append(line_text)
        else:
            lines.append("No non-zero Schedule 1 lines entered.")

        lines.extend(["", "SCHEDULE 8 CCA"])
        if cca_rows:
            for (
                description,
                cca_class,
                rate,
                opening,
                additions,
                disposals,
                cca_claim,
                closing,
            ) in cca_rows:
                lines.append(
                    f"{description} | Class {cca_class} | Rate {rate}% | "
                    f"Opening ${opening:,.2f} | Additions ${additions:,.2f} | "
                    f"Disposals ${disposals:,.2f} | CCA ${cca_claim:,.2f} |"
                    f"Closing ${closing:,.2f}"

                )
            lines.append(f"Total CCA claimed: {self.cca_total_taken.text()}")
            lines.append(f"Closing UCC: {self.cca_closing_ucc.text()}")
        else:
            lines.append("No Schedule 8 rows entered.")

        lines.extend(["", "SCHEDULE 50 SHAREHOLDERS"])
        if shareholder_rows:
            for (
                name,
                address,
                share_class,
                num_shares,
                pct,
                is_director,
            ) in shareholder_rows:
                lines.append(
                    f"{name} | {share_class} | Shares: {num_shares or 'N/A'}"
                    f"| Ownership: {pct or 'N/A'}% | "

                    f"Director: {is_director or 'N/A'} | "
                    f"Address: {address or 'N/A'}"
                )
        else:
            lines.append("No shareholder rows entered.")

        lines.extend(["", "NOTES"])
        lines.append(notes if notes else "No notes entered.")
        lines.extend(
            [
                "",
                "MAILING NOTE",
                "CRA paper returns go to the corporation's assigned tax"
                "centre. Confirm the address before mailing.",

                "Keep a signed copy of the return, supporting schedules, and"
                "proof of mailing in the corporate records.",

            ]
        )

        return "\n".join(lines)

    def _save_generated_package_path(self, file_path) -> None:
        """Persist the latest generated paper-package path."""
        if not self.current_return_id:
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE t2_return_metadata
                    SET supporting_docs_path = %s,
                        generated_date = NOW(),
                        updated_at = NOW()
                    WHERE return_id = %s
                    """,
                    (file_path, self.current_return_id),
                )
        except Exception as e:
            logger.warning(f"Could not persist generated package path: {e}")

    def preview_paper_filing_package(self) -> None:
        """Open a read-only preview of the paper filing package."""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        self._validate_paper_filing_inputs()
        package_text = self._build_paper_filing_package()

        dialog = QDialog(self)
        dialog.setWindowTitle(
            f"Paper Filing Package Preview - {self.year_combo.currentText()}"
        )
        dialog.resize(900, 700)

        layout = QVBoxLayout(dialog)
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(package_text)
        layout.addWidget(preview)

        btn_layout = QHBoxLayout()

        print_btn = QPushButton("Print")
        print_btn.clicked.connect(
            lambda: self._print_text_document(package_text)
        )
        btn_layout.addWidget(print_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_paper_filing_package)
        btn_layout.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        dialog.exec()

    def export_paper_filing_package(self) -> None:
        """Export the paper filing package to a text file."""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        if not self._ensure_paper_filing_ready():
            return

        tax_year = self.year_combo.currentText() or "return"
        default_name = f"T2_paper_package_{tax_year}.txt"
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Paper Filing Package",
            os.path.join(os.getcwd(), default_name),
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(self._build_paper_filing_package())

            self._save_generated_package_path(file_path)
            self.set_status(
                f"Exported paper filing package to {file_path}", error=False
            )
            QMessageBox.information(
                self,
                "Export Complete",
                f"Paper filing package exported to:\n{file_path}",
            )
        except Exception as e:
            logger.error(f"Failed to export paper filing package: {e}")
            self.set_status(
                f"Error exporting paper filing package: {e}", error=True
            )
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not export the paper filing package:\n{e}",
            )

    def _print_text_document(self, package_text) -> None:
        """Send a text document to the printer."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        document = QTextDocument()
        document.setPlainText(package_text)
        document.print(printer)
        self.set_status("Sent paper filing package to printer", error=False)

    def print_paper_filing_package(self) -> None:
        """Print the generated paper filing package."""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        if not self._ensure_paper_filing_ready():
            return

        self._print_text_document(self._build_paper_filing_package())

    # -----------------------------------------------------------------------
    # Auto-fill from DB
    # -----------------------------------------------------------------------

    def _auto_fill_schedule_125(self) -> None:
        """Pull revenue + deductible expenses from DB and populate Schedule"
        "125."""

        if not self.year_combo.currentText():
            QMessageBox.warning(
                self, "No Year Selected", "Please select a tax year first."
            )
            return

        tax_year = int(self.year_combo.currentText())

        try:
            from accounting_gifi import gl_to_sch125_field

            from modern_backend.app.tax.t2_data_extraction import (
                T2DataExtractor,
            )

            extractor = T2DataExtractor(
                self._get_connection_params_for_analysis()
            )

            # — Revenue —
            rev_data = extractor.extract_revenue_data(tax_year)
            charter_rev = float(
                (rev_data.get("charter_revenue") or {}).get("amount") or 0
            )
            other_income = float(
                sum(
                    float(v.get("amount") or 0)
                    for k, v in rev_data.items()
                    if k not in ("charter_revenue", "total_revenue")
                    and isinstance(v, dict)
                )
            )
            self.sch125_revenue.setValue(charter_rev)
            self.sch125_other_income.setValue(other_income)

            # — Expenses: run deductibility analysis (50% meals applied,
            # non-ded excluded) —
            analysis = self._fetch_deductibility_analysis(
                tax_year, show_errors=True
            )
            if not analysis:
                return

            # Reset all expense spinboxes
            expense_fields = [
                self.sch125_cost_of_sales,
                self.sch125_salaries,
                self.sch125_benefits,
                self.sch125_rent,
                self.sch125_repairs,
                self.sch125_bad_debts,
                self.sch125_interest,
                self.sch125_insurance,
                self.sch125_office,
                self.sch125_professional_fees,
                self.sch125_property_tax,
                self.sch125_travel,
                self.sch125_vehicle,
                self.sch125_other_expenses,
            ]
            for field in expense_fields:
                field.setValue(0)

            field_map = {
                "sch125_cost_of_sales": self.sch125_cost_of_sales,
                "sch125_salaries": self.sch125_salaries,
                "sch125_benefits": self.sch125_benefits,
                "sch125_rent": self.sch125_rent,
                "sch125_repairs": self.sch125_repairs,
                "sch125_bad_debts": self.sch125_bad_debts,
                "sch125_interest": self.sch125_interest,
                "sch125_insurance": self.sch125_insurance,
                "sch125_office": self.sch125_office,
                "sch125_professional_fees": self.sch125_professional_fees,
                "sch125_property_tax": self.sch125_property_tax,
                "sch125_travel": self.sch125_travel,
                "sch125_vehicle": self.sch125_vehicle,
                "sch125_other_expenses": self.sch125_other_expenses,
            }

            # Accumulate deductible amounts by Sch 125 target field
            accum: dict[str, float] = {}
            skipped_count = 0
            for row in analysis.get("by_gl_code", []) or []:
                gl_code = str(row.get("gl_code") or "")
                account_name = str(row.get("account_name") or "")
                deductible = float(row.get("deductible_amount") or 0)
                if deductible <= 0:
                    skipped_count += 1
                    continue
                target = gl_to_sch125_field(gl_code, account_name)
                if target is None:
                    skipped_count += 1
                    continue
                accum[target] = accum.get(target, 0.0) + deductible

            for field_name, amount in accum.items():
                if field_name in field_map:
                    field_map[field_name].setValue(amount)

            # Keep deductibility panel in sync
            self._apply_deductibility_to_ui(analysis)

            total_ded = float(analysis.get("total_deductible_expenses") or 0)
            total_add = float(analysis.get("total_add_back") or 0)
            self.set_status(
                f"Auto-filled Sch 125 for {tax_year}: revenue"
                f"${charter_rev:,.2f}, "

                f"deductible expenses ${total_ded:,.2f} "
                f"(${total_add:,.2f} add-backs excluded from expenses)",
                error=False,
            )

        except Exception as e:
            logger.error(f"Auto-fill Schedule 125 failed: {e}")
            QMessageBox.critical(
                self,
                "Auto-Fill Failed",
                f"Could not auto-fill Schedule 125:\n{e}",
            )

    def _auto_fill_schedule_100(self) -> None:
        """Pull cash, AR, and PPE from DB and populate Schedule 100 ending"
        "balances."""

        if not self.year_combo.currentText():
            QMessageBox.warning(
                self, "No Year Selected", "Please select a tax year first."
            )
            return

        tax_year = int(self.year_combo.currentText())
        try:
            from modern_backend.app.tax.t2_data_extraction import (
                T2DataExtractor,
            )

            extractor = T2DataExtractor(
                self._get_connection_params_for_analysis()
            )
            fiscal_year_end = self.fiscal_year_end.date().toPyDate()
            bs = extractor.extract_balance_sheet_data(fiscal_year_end)

            cash_end = float((bs.get("cash") or {}).get("ending_balance") or 0)
            ar_end = float(
                (bs.get("accounts_receivable") or {}).get("ending_balance")
                or 0
            )
            ppe_end = float((bs.get("ppe") or {}).get("ending_balance") or 0)

            self.sch100_cash_end.setValue(cash_end)
            self.sch100_ar_end.setValue(ar_end)
            self.sch100_ppe_end.setValue(ppe_end)

            self.set_status(
                f"Auto-filled Sch 100 for {tax_year}: cash ${cash_end:,.2f}, "
                f"AR ${ar_end:,.2f}, PPE ${ppe_end:,.2f}",
                error=False,
            )
        except Exception as e:
            logger.error(f"Auto-fill Schedule 100 failed: {e}")
            QMessageBox.critical(
                self,
                "Auto-Fill Failed",
                f"Could not auto-fill Schedule 100:\n{e}",
            )

    # -----------------------------------------------------------------------
    # Schedule 8 — Capital Cost Allowance (CCA)
    # -----------------------------------------------------------------------

    def _build_cca_schedule_tab(self) -> QWidget:
        """Schedule 8 — CCA for Class 10 / 10.1 vehicles."""
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)

        info = QLabel(
            "🚗 Schedule 8: Capital Cost Allowance\n"
            "Class 10 (30%) — standard vehicles  |  Class 10.1 (30%) — cost >"
            "$36,000 (capped)\n"

            "Half-year rule applied: Available = Opening UCC + 50% × net"
            "additions."

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        # Summary totals
        summary_group = QGroupBox("CCA Summary")
        summary_form = QFormLayout(summary_group)
        self.cca_total_available = QLabel("$0.00")
        self.cca_total_taken = QLabel("$0.00")
        self.cca_closing_ucc = QLabel("$0.00")
        summary_form.addRow(
            "Total Available for CCA:", self.cca_total_available
        )
        summary_form.addRow(
            "Total CCA Deduction (feeds Sch 1 Line 300):", self.cca_total_taken
        )
        summary_form.addRow("Total Closing UCC:", self.cca_closing_ucc)
        layout.addWidget(summary_group)

        # CCA table
        self.cca_table = QTableWidget()
        self.cca_table.setColumnCount(9)
        self.cca_table.setHorizontalHeaderLabels(
            [
                "Vehicle / Asset",
                "Class",
                "Rate %",
                "Opening UCC",
                "Additions",
                "Disposals",
                "Available",
                "CCA Taken",
                "Closing UCC",
            ]
        )
        self.cca_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.cca_table.setMinimumHeight(300)
        self.cca_table.itemChanged.connect(self._recalc_cca_row)
        layout.addWidget(self.cca_table)

        btn_row = QHBoxLayout()
        add_veh_btn = QPushButton("➕ Add Vehicle")
        add_veh_btn.clicked.connect(self._cca_add_row)
        btn_row.addWidget(add_veh_btn)
        load_veh_btn = QPushButton("🚗 Load from Vehicle DB")
        load_veh_btn.clicked.connect(self._cca_load_vehicles)
        btn_row.addWidget(load_veh_btn)
        recalc_btn = QPushButton("🔄 Recalculate All")
        recalc_btn.clicked.connect(self._recalc_all_cca)
        btn_row.addWidget(recalc_btn)
        btn_row.addStretch()
        save_cca_btn = QPushButton("💾 Save Schedule 8")
        save_cca_btn.clicked.connect(self._save_cca_schedule)
        btn_row.addWidget(save_cca_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        return container

    def _cca_add_row(
        self,
        description="",
        cca_class=10,
        rate=30.0,
        opening=0.0,
        additions=0.0,
        disposals=0.0,
    ) -> None:
        """Add a row to the CCA schedule table."""
        row = self.cca_table.rowCount()
        self.cca_table.insertRow(row)
        net = additions - disposals
        available = opening + 0.5 * net
        cca = max(0.0, available * (rate / 100.0))
        closing = opening + net - cca

        self.cca_table.blockSignals(True)
        self.cca_table.setItem(row, 0, QTableWidgetItem(description))
        self.cca_table.setItem(row, 1, QTableWidgetItem(str(cca_class)))
        self.cca_table.setItem(row, 2, QTableWidgetItem(f"{rate:.1f}"))
        self.cca_table.setItem(row, 3, QTableWidgetItem(f"{opening:.2f}"))
        self.cca_table.setItem(row, 4, QTableWidgetItem(f"{additions:.2f}"))
        self.cca_table.setItem(row, 5, QTableWidgetItem(f"{disposals:.2f}"))
        self.cca_table.setItem(row, 6, QTableWidgetItem(f"{available:.2f}"))
        self.cca_table.setItem(row, 7, QTableWidgetItem(f"{cca:.2f}"))
        self.cca_table.setItem(row, 8, QTableWidgetItem(f"{closing:.2f}"))
        self.cca_table.blockSignals(False)
        self._update_cca_summary()

    def _cca_load_vehicles(self) -> None:
        """Load vehicles from DB as CCA additions for the selected year."""
        if not self.year_combo.currentText():
            QMessageBox.warning(self, "No Year", "Select a tax year first.")
            return

        tax_year = int(self.year_combo.currentText())
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT vehicle_number,
                              COALESCE(make,'') || ' ' ||
                              COALESCE(model,'') || ' ' ||
                           COALESCE(CAST(year AS TEXT),''),
                           COALESCE(purchase_cost, 0)
                    FROM vehicles
                    WHERE EXTRACT(
                        YEAR FROM COALESCE(purchase_date, '1900-01-01')
                    ) = %s
                    ORDER BY vehicle_number
                    """,
                    (tax_year,),
                )
                rows = cur.fetchall()

            if not rows:
                QMessageBox.information(
                    self,
                    "No Vehicles",
                    f"No vehicles with purchase_date in {tax_year} found.\n"
                    "Add rows manually with ➕ Add Vehicle.",
                )
                return

            for veh_num, description, cost in rows:
                self._cca_add_row(
                    description=f"{veh_num} — {description.strip()}",
                    cca_class=10,
                    rate=30.0,
                    opening=0.0,
                    additions=float(cost or 0),
                )
            self.set_status(
                f"Loaded {len(rows)} vehicle(s) for {tax_year}", error=False
            )

        except Exception as e:
            logger.error(f"CCA load vehicles failed: {e}")
            QMessageBox.critical(
                self, "Load Failed", f"Failed to load vehicles:\n{e}"
            )

    def _recalc_cca_row(self, item) -> None:
        """Recalculate Available, CCA Taken, Closing UCC when inputs change."""
        if item is None or item.column() > 5:
            return
        self._recalc_single_cca_row(item.row())
        self._update_cca_summary()

    def _recalc_single_cca_row(self, row) -> None:
        """Recompute columns 6-8 for a single row."""

        def _val(col) -> float:
            item = self.cca_table.item(row, col)
            if not item:
                return 0.0
            try:
                return float(item.text().replace(",", "") or 0)
            except ValueError:
                return 0.0

        rate = _val(2) / 100.0
        opening = _val(3)
        additions = _val(4)
        disposals = _val(5)
        net = additions - disposals
        available = opening + 0.5 * net
        cca = max(0.0, available * rate)
        closing = opening + net - cca

        self.cca_table.blockSignals(True)
        self.cca_table.setItem(row, 6, QTableWidgetItem(f"{available:.2f}"))
        self.cca_table.setItem(row, 7, QTableWidgetItem(f"{cca:.2f}"))
        self.cca_table.setItem(row, 8, QTableWidgetItem(f"{closing:.2f}"))
        self.cca_table.blockSignals(False)

    def _recalc_all_cca(self) -> None:
        """Recalculate every row in the CCA table."""
        self.cca_table.blockSignals(True)
        for row in range(self.cca_table.rowCount()):
            self._recalc_single_cca_row(row)
        self.cca_table.blockSignals(False)
        self._update_cca_summary()

    def _update_cca_summary(self) -> None:
        """Refresh summary totals from CCA table."""
        total_avail = total_cca = total_closing = 0.0
        for row in range(self.cca_table.rowCount()):
            for col, attr in [(6, "a"), (7, "c"), (8, "cl")]:
                item = self.cca_table.item(row, col)
                val = 0.0
                if item:
                    try:
                        val = float(item.text().replace(",", "") or 0)
                    except ValueError:
                        pass
                if attr == "a":
                    total_avail += val
                elif attr == "c":
                    total_cca += val
                else:
                    total_closing += val
        self.cca_total_available.setText(f"${total_avail:,.2f}")
        self.cca_total_taken.setText(f"${total_cca:,.2f}")
        self.cca_closing_ucc.setText(f"${total_closing:,.2f}")

    def _save_cca_schedule(self) -> None:
        """Save CCA schedule to t2_cca_schedule table (creates table if"
        "needed)."""

        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        tax_year = (
            int(self.year_combo.currentText())
            if self.year_combo.currentText()
            else None
        )
        if not tax_year:
            QMessageBox.warning(self, "No Year", "Select a tax year first.")
            return

        insert_rows = []
        for row in range(self.cca_table.rowCount()):

            def _cell(col) -> str:
                item = self.cca_table.item(row, col)
                return item.text() if item else ""

            desc = _cell(0).strip()
            if not desc:
                continue

            def _num(col) -> float:
                try:
                    return float(_cell(col).replace(",", "") or 0)
                except ValueError:
                    return 0.0

            try:
                cca_class = int(_cell(1) or 10)
            except ValueError:
                cca_class = 10

            insert_rows.append(
                (
                    self.current_return_id,
                    tax_year,
                    desc,
                    cca_class,
                    _num(2) / 100.0,
                    _num(3),
                    _num(4),
                    _num(5),
                    _num(7),
                    _num(8),
                )
            )

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS t2_cca_schedule (
                        id SERIAL PRIMARY KEY,
                        return_id INTEGER,
                        tax_year INTEGER NOT NULL,
                        vehicle_description TEXT NOT NULL,
                        cca_class INTEGER NOT NULL DEFAULT 10,
                        cca_rate NUMERIC(6,4) NOT NULL DEFAULT 0.30,
                        opening_ucc NUMERIC(12,2) NOT NULL DEFAULT 0,
                        additions NUMERIC(12,2) NOT NULL DEFAULT 0,
                        disposals NUMERIC(12,2) NOT NULL DEFAULT 0,
                        cca_taken NUMERIC(12,2) NOT NULL DEFAULT 0,
                        closing_ucc NUMERIC(12,2) NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "DELETE FROM t2_cca_schedule WHERE return_id = %s",
                    (self.current_return_id,),
                )
                for r in insert_rows:
                    cur.execute(
                        """
                        INSERT INTO t2_cca_schedule
                            (return_id, tax_year, vehicle_description,
                            cca_class, cca_rate,
                             opening_ucc, additions, disposals, cca_taken,
                             closing_ucc)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                        r,
                    )

            self.set_status(
                f"Saved {len(insert_rows)} CCA row(s)", error=False
            )
        except Exception as e:
            logger.error(f"Save CCA schedule failed: {e}")
            QMessageBox.critical(
                self, "Save Failed", f"Failed to save CCA schedule:\n{e}"
            )

    def _load_cca_schedule(self) -> None:
        """Load saved CCA rows for the current return."""
        if not self.current_return_id:
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("SELECT to_regclass('t2_cca_schedule')")
                if cur.fetchone()[0] is None:
                    return
                cur.execute(
                    """
                    SELECT vehicle_description, cca_class, cca_rate * 100,
                           opening_ucc, additions, disposals, cca_taken,
                           closing_ucc
                    FROM t2_cca_schedule WHERE return_id = %s ORDER BY id
                """,
                    (self.current_return_id,),
                )
                self.cca_table.setRowCount(0)
                for (
                    desc,
                    cls,
                    rate,
                    opening,
                    adds,
                    disps,
                    cca,
                    closing,
                ) in cur.fetchall():
                    self._cca_add_row(
                        description=desc or "",
                        cca_class=int(cls or 10),
                        rate=float(rate or 30),
                        opening=float(opening or 0),
                        additions=float(adds or 0),
                        disposals=float(disps or 0),
                    )
        except Exception as e:
            logger.warning(f"Could not load CCA schedule: {e}")

    # -----------------------------------------------------------------------
    # Schedule 50 — Shareholder Information
    # -----------------------------------------------------------------------

    def _build_shareholders_tab(self) -> QWidget:
        """Schedule 50 — Shareholder Information (≥10% ownership)."""
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        layout = QVBoxLayout(widget)

        info = QLabel(
            "👤 Schedule 50: Shareholder Information\n"
            "List shareholders owning 10% or more of any class of shares at"
            "fiscal year-end."

        )
        info.setStyleSheet(self.INFO_BOX_STYLE)
        layout.addWidget(info)

        self.shareholders_table = QTableWidget()
        self.shareholders_table.setColumnCount(7)
        self.shareholders_table.setHorizontalHeaderLabels(
            [
                "Name",
                "SIN / BN",
                "Address",
                "Share Class",
                "# Shares",
                "% Owned",
                "Director/Officer?",
            ]
        )
        self.shareholders_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.shareholders_table.setMinimumHeight(300)
        layout.addWidget(self.shareholders_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Add Shareholder")
        add_btn.clicked.connect(self._add_shareholder_row)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        save_btn = QPushButton("💾 Save Schedule 50")
        save_btn.clicked.connect(self._save_shareholders)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        return container

    def _add_shareholder_row(
        self,
        name="",
        sin="",
        address="",
        share_class="Common",
        num_shares="",
        pct="",
        is_director="Yes",
    ) -> None:
        """Add a row to the shareholders table."""
        row = self.shareholders_table.rowCount()
        self.shareholders_table.insertRow(row)
        self.shareholders_table.setItem(row, 0, QTableWidgetItem(name))
        self.shareholders_table.setItem(row, 1, QTableWidgetItem(sin))
        self.shareholders_table.setItem(row, 2, QTableWidgetItem(address))
        self.shareholders_table.setItem(row, 3, QTableWidgetItem(share_class))
        self.shareholders_table.setItem(row, 4, QTableWidgetItem(num_shares))
        self.shareholders_table.setItem(row, 5, QTableWidgetItem(pct))
        director_combo = QComboBox()
        director_combo.addItems(["Yes", "No"])
        director_combo.setCurrentText(is_director)
        self.shareholders_table.setCellWidget(row, 6, director_combo)

    def _save_shareholders(self) -> None:
        """Persist Schedule 50 to DB (creates table if needed)."""
        if not self.current_return_id:
            QMessageBox.warning(
                self, self.NO_RETURN_TITLE, self.NO_RETURN_MESSAGE
            )
            return

        insert_rows = []
        for row in range(self.shareholders_table.rowCount()):

            def _cell(col) -> str:
                item = self.shareholders_table.item(row, col)
                return (item.text() if item else "").strip()

            name = _cell(0)
            if not name:
                continue
            director_widget = self.shareholders_table.cellWidget(row, 6)
            is_dir = (
                (director_widget.currentText() == "Yes")
                if director_widget
                else False
            )
            try:
                pct_val = float(_cell(5).replace("%", "") or 0)
            except ValueError:
                pct_val = 0.0
            insert_rows.append(
                (
                    self.current_return_id,
                    name,
                    _cell(1),
                    _cell(2),
                    _cell(3),
                    _cell(4) or None,
                    pct_val,
                    is_dir,
                )
            )

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS t2_shareholders (
                        id SERIAL PRIMARY KEY,
                        return_id INTEGER,
                        shareholder_name TEXT NOT NULL,
                        sin_or_bn TEXT,
                        address TEXT,
                        share_class TEXT,
                        num_shares TEXT,
                        pct_owned NUMERIC(6,3),
                        is_director BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "DELETE FROM t2_shareholders WHERE return_id = %s",
                    (self.current_return_id,),
                )
                for r in insert_rows:
                    cur.execute(
                        """
                        INSERT INTO t2_shareholders
                            (return_id, shareholder_name, sin_or_bn, address,
                            share_class,
                             num_shares, pct_owned, is_director)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                        r,
                    )

            self.set_status(
                f"Saved {len(insert_rows)} shareholder(s)", error=False
            )
        except Exception as e:
            logger.error(f"Save shareholders failed: {e}")
            QMessageBox.critical(
                self, "Save Failed", f"Failed to save shareholders:\n{e}"
            )

    def _load_shareholders(self) -> None:
        """Load Schedule 50 rows for the current return."""
        if not self.current_return_id:
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("SELECT to_regclass('t2_shareholders')")
                if cur.fetchone()[0] is None:
                    return
                cur.execute(
                    """
                    SELECT shareholder_name, sin_or_bn, address, share_class,
                           num_shares, pct_owned, is_director
                    FROM t2_shareholders WHERE return_id = %s ORDER BY id
                """,
                    (self.current_return_id,),
                )
                self.shareholders_table.setRowCount(0)
                for name, sin, addr, sc, ns, pct, is_dir in cur.fetchall():
                    self._add_shareholder_row(
                        name=name or "",
                        sin=sin or "",
                        address=addr or "",
                        share_class=sc or "Common",
                        num_shares=str(ns or ""),
                        pct=f"{float(pct or 0):.2f}",
                        is_director="Yes" if is_dir else "No",
                    )
        except Exception as e:
            logger.warning(f"Could not load shareholders: {e}")


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    # Mock database connection
    class MockDB:
        def get_cursor(self) -> None:
            # Mock method - no implementation needed for demo
            pass

        def commit(self) -> None:
            # Mock method - no implementation needed for demo
            pass

        def rollback(self) -> None:
            # Mock method - no implementation needed for demo
            pass

    app = QApplication(sys.argv)
    widget = T2DataEntryWidget(MockDB())
    widget.resize(1200, 800)
    widget.show()
    sys.exit(app.exec())
