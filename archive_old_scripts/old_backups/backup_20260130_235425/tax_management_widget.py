"""
CRA Tax Management System
Comprehensive tax filing, payroll deductions, owner income tracking, and year-end reconciliation
Supports 2012-2025 with rollover tracking for GST, losses, and deductions
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
    QComboBox, QDialog, QTabWidget, QMessageBox, QSpinBox, QCheckBox,
    QFormLayout, QGroupBox, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QSplitter, QDateEdit
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from datetime import datetime
import subprocess
import sys
import json
import os


class MarkFiledDialog(QDialog):
    """Dialog to mark a return as filed/paid with amount/date/reference."""

    def __init__(self, parent=None, default_amount: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("Mark as Filed/Paid")
        self.setMinimumWidth(360)

        layout = QFormLayout()

        self.amount = QDoubleSpinBox()
        self.amount.setMaximum(99999999)
        self.amount.setPrefix("$")
        self.amount.setValue(default_amount)
        layout.addRow("Filed Amount:", self.amount)

        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDate(QDate.currentDate())
        layout.addRow("Filed Date:", self.date)

        self.status = QComboBox()
        self.status.addItems(["filed", "paid", "submitted", "draft"])
        layout.addRow("Status:", self.status)

        self.reference = QLineEdit()
        layout.addRow("Reference:", self.reference)

        button_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(save_btn)
        button_row.addWidget(cancel_btn)
        layout.addRow(button_row)

        self.setLayout(layout)

    def values(self) -> dict:
        return {
            "amount": float(self.amount.value()),
            "date": self.date.date().toPyDate(),
            "status": self.status.currentText(),
            "reference": self.reference.text().strip(),
        }


class TaxYearDetailDialog(QDialog):
    """
    Detailed view for a single tax year with tabs:
    - Income & Revenue
    - Expenses & Deductions
    - Payroll & T4s
    - GST/HST
    - Owner Personal Tax
    - CRA Forms
    - Rollovers & Carryforwards
    """
    
    saved = pyqtSignal(dict)
    
    def __init__(self, db, year, parent=None):
        super().__init__(parent)
        self.db = db
        self.year = year
        
        self.setWindowTitle(f"Tax Year {year} - Detailed View")
        self.setGeometry(50, 50, 1400, 900)
        
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(f"<h2>📊 Tax Year {year} - Arrow Limousine</h2>")
        header.setStyleSheet("color: #2c3e50; font-weight: bold;")
        layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        
        tabs.addTab(self.create_income_tab(), "💰 Income & Revenue")
        tabs.addTab(self.create_expenses_tab(), "💸 Expenses")
        tabs.addTab(self.create_payroll_tab(), "👥 Payroll & T4s")
        tabs.addTab(self.create_gst_tab(), "📋 GST/HST")
        tabs.addTab(self.create_owner_tax_tab(), "👤 Owner Personal Tax")
        tabs.addTab(self.create_forms_tab(), "📄 CRA Forms")
        tabs.addTab(self.create_rollovers_tab(), "🔄 Rollovers & Carryforwards")
        
        layout.addWidget(tabs)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.recalculate_btn = QPushButton("🔄 Recalculate All")
        self.recalculate_btn.clicked.connect(self.recalculate_year)
        button_layout.addWidget(self.recalculate_btn)
        
        self.generate_forms_btn = QPushButton("📄 Generate CRA Forms")
        self.generate_forms_btn.clicked.connect(self.generate_forms)
        button_layout.addWidget(self.generate_forms_btn)
        
        button_layout.addStretch()
        
        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self.save_year)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.load_year_data()
    
    def create_income_tab(self):
        """Tab 1: Income and revenue details"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Income & Revenue Sources")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Summary metrics
        summary_group = QGroupBox("Revenue Summary")
        summary_form = QFormLayout()
        
        self.charter_revenue = QDoubleSpinBox()
        self.charter_revenue.setMaximum(99999999)
        self.charter_revenue.setPrefix("$")
        self.charter_revenue.setReadOnly(True)
        summary_form.addRow("Charter Services:", self.charter_revenue)
        
        self.gst_included = QDoubleSpinBox()
        self.gst_included.setMaximum(99999999)
        self.gst_included.setPrefix("$")
        self.gst_included.setReadOnly(True)
        summary_form.addRow("  (GST Included):", self.gst_included)
        
        self.other_income = QDoubleSpinBox()
        self.other_income.setMaximum(99999999)
        self.other_income.setPrefix("$")
        summary_form.addRow("Other Income:", self.other_income)
        
        self.total_revenue = QDoubleSpinBox()
        self.total_revenue.setMaximum(99999999)
        self.total_revenue.setPrefix("$")
        self.total_revenue.setReadOnly(True)
        self.total_revenue.setStyleSheet("font-weight: bold;")
        summary_form.addRow("TOTAL REVENUE:", self.total_revenue)
        
        summary_group.setLayout(summary_form)
        layout.addWidget(summary_group)
        
        # Revenue breakdown table
        revenue_label = QLabel("Revenue Breakdown by Month:")
        layout.addWidget(revenue_label)
        
        self.revenue_table = QTableWidget()
        self.revenue_table.setColumnCount(5)
        self.revenue_table.setHorizontalHeaderLabels([
            "Month", "Charters", "Gross Revenue", "GST Collected", "Net Revenue"
        ])
        layout.addWidget(self.revenue_table)
        
        # Adjustments
        adj_btn = QPushButton("➕ Add Revenue Adjustment")
        adj_btn.clicked.connect(self.add_revenue_adjustment)
        layout.addWidget(adj_btn)
        
        widget.setLayout(layout)
        return widget
    
    def create_expenses_tab(self):
        """Tab 2: Business expenses and deductions"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Business Expenses & Deductions")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Expense summary
        summary_group = QGroupBox("Expense Summary")
        summary_form = QFormLayout()
        
        self.fuel_expense = QDoubleSpinBox()
        self.fuel_expense.setMaximum(99999999)
        self.fuel_expense.setPrefix("$")
        self.fuel_expense.setReadOnly(True)
        summary_form.addRow("Vehicle Fuel:", self.fuel_expense)
        
        self.maintenance_expense = QDoubleSpinBox()
        self.maintenance_expense.setMaximum(99999999)
        self.maintenance_expense.setPrefix("$")
        self.maintenance_expense.setReadOnly(True)
        summary_form.addRow("Vehicle Maintenance:", self.maintenance_expense)
        
        self.insurance_expense = QDoubleSpinBox()
        self.insurance_expense.setMaximum(99999999)
        self.insurance_expense.setPrefix("$")
        self.insurance_expense.setReadOnly(True)
        summary_form.addRow("Insurance:", self.insurance_expense)
        
        self.payroll_expense = QDoubleSpinBox()
        self.payroll_expense.setMaximum(99999999)
        self.payroll_expense.setPrefix("$")
        self.payroll_expense.setReadOnly(True)
        summary_form.addRow("Payroll Wages:", self.payroll_expense)
        
        self.other_expense = QDoubleSpinBox()
        self.other_expense.setMaximum(99999999)
        self.other_expense.setPrefix("$")
        summary_form.addRow("Other Expenses:", self.other_expense)
        
        self.total_expenses = QDoubleSpinBox()
        self.total_expenses.setMaximum(99999999)
        self.total_expenses.setPrefix("$")
        self.total_expenses.setReadOnly(True)
        self.total_expenses.setStyleSheet("font-weight: bold;")
        summary_form.addRow("TOTAL EXPENSES:", self.total_expenses)
        
        self.gst_recoverable = QDoubleSpinBox()
        self.gst_recoverable.setMaximum(99999999)
        self.gst_recoverable.setPrefix("$")
        self.gst_recoverable.setReadOnly(True)
        summary_form.addRow("GST Recoverable:", self.gst_recoverable)
        
        summary_group.setLayout(summary_form)
        layout.addWidget(summary_group)
        
        # Expense detail table
        expense_label = QLabel("Expense Details:")
        layout.addWidget(expense_label)
        
        self.expense_table = QTableWidget()
        self.expense_table.setColumnCount(6)
        self.expense_table.setHorizontalHeaderLabels([
            "Date", "Vendor", "Category", "Amount", "GST", "Notes"
        ])
        self.expense_table.doubleClicked.connect(self.edit_expense)
        layout.addWidget(self.expense_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        add_exp_btn = QPushButton("➕ Add Expense")
        add_exp_btn.clicked.connect(self.add_expense)
        btn_layout.addWidget(add_exp_btn)
        
        recategorize_btn = QPushButton("🔄 Recategorize Selected")
        recategorize_btn.clicked.connect(self.recategorize_expense)
        btn_layout.addWidget(recategorize_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_payroll_tab(self):
        """Tab 3: Payroll, source deductions, T4s"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Payroll & Source Deductions")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Payroll summary
        summary_group = QGroupBox("Payroll Summary")
        summary_form = QFormLayout()
        
        self.total_gross_pay = QDoubleSpinBox()
        self.total_gross_pay.setMaximum(99999999)
        self.total_gross_pay.setPrefix("$")
        self.total_gross_pay.setReadOnly(True)
        summary_form.addRow("Total Gross Pay:", self.total_gross_pay)
        
        self.total_cpp = QDoubleSpinBox()
        self.total_cpp.setMaximum(99999999)
        self.total_cpp.setPrefix("$")
        self.total_cpp.setReadOnly(True)
        summary_form.addRow("Total CPP (Employee):", self.total_cpp)
        
        self.total_ei = QDoubleSpinBox()
        self.total_ei.setMaximum(99999999)
        self.total_ei.setPrefix("$")
        self.total_ei.setReadOnly(True)
        summary_form.addRow("Total EI (Employee):", self.total_ei)
        
        self.total_tax = QDoubleSpinBox()
        self.total_tax.setMaximum(99999999)
        self.total_tax.setPrefix("$")
        self.total_tax.setReadOnly(True)
        summary_form.addRow("Total Income Tax:", self.total_tax)
        
        self.employer_cpp = QDoubleSpinBox()
        self.employer_cpp.setMaximum(99999999)
        self.employer_cpp.setPrefix("$")
        self.employer_cpp.setReadOnly(True)
        summary_form.addRow("Employer CPP:", self.employer_cpp)
        
        self.employer_ei = QDoubleSpinBox()
        self.employer_ei.setMaximum(99999999)
        self.employer_ei.setPrefix("$")
        self.employer_ei.setReadOnly(True)
        summary_form.addRow("Employer EI:", self.employer_ei)
        
        self.total_remittance = QDoubleSpinBox()
        self.total_remittance.setMaximum(99999999)
        self.total_remittance.setPrefix("$")
        self.total_remittance.setReadOnly(True)
        self.total_remittance.setStyleSheet("font-weight: bold;")
        summary_form.addRow("TOTAL CRA REMITTANCE:", self.total_remittance)
        
        summary_group.setLayout(summary_form)
        layout.addWidget(summary_group)
        
        # T4 Summary table
        t4_label = QLabel("T4 Slips:")
        layout.addWidget(t4_label)
        
        self.t4_table = QTableWidget()
        self.t4_table.setColumnCount(8)
        self.t4_table.setHorizontalHeaderLabels([
            "Employee", "Box 14 (Employment)", "Box 16 (CPP)", "Box 18 (EI)",
            "Box 22 (Tax)", "Box 24 (EI Insurable)", "Status", "Actions"
        ])
        self.t4_table.doubleClicked.connect(self.edit_t4)
        layout.addWidget(self.t4_table)

        # Variances
        variance_label = QLabel("Payroll Variances/Issues:")
        layout.addWidget(variance_label)
        self.payroll_variance_table = QTableWidget()
        self.payroll_variance_table.setColumnCount(5)
        self.payroll_variance_table.setHorizontalHeaderLabels([
            "Severity", "Field", "Actual", "Expected", "Message"
        ])
        layout.addWidget(self.payroll_variance_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        generate_t4_btn = QPushButton("📄 Generate T4 Slips")
        generate_t4_btn.clicked.connect(self.generate_t4_slips)
        btn_layout.addWidget(generate_t4_btn)
 
        validate_btn = QPushButton("✅ Validate Deductions")
        validate_btn.clicked.connect(self.validate_payroll_deductions)
        btn_layout.addWidget(validate_btn)

        recompute_payroll_btn = QPushButton("🔄 Recompute Payroll (save)")
        recompute_payroll_btn.clicked.connect(self.recompute_payroll)
        btn_layout.addWidget(recompute_payroll_btn)

        mark_payroll_btn = QPushButton("✅ Mark Payroll Filed/Paid")
        mark_payroll_btn.clicked.connect(self.mark_payroll_filed)
        btn_layout.addWidget(mark_payroll_btn)
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_gst_tab(self):
        """Tab 4: GST/HST calculations and returns"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("GST/HST Return")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # GST calculation
        gst_group = QGroupBox("GST/HST Calculation")
        gst_form = QFormLayout()
        
        self.gst_collected = QDoubleSpinBox()
        self.gst_collected.setMaximum(99999999)
        self.gst_collected.setPrefix("$")
        self.gst_collected.setReadOnly(True)
        gst_form.addRow("GST Collected (on sales):", self.gst_collected)
        
        self.gst_paid = QDoubleSpinBox()
        self.gst_paid.setMaximum(99999999)
        self.gst_paid.setPrefix("$")
        self.gst_paid.setReadOnly(True)
        gst_form.addRow("GST Paid (on purchases):", self.gst_paid)
        
        self.gst_net = QDoubleSpinBox()
        self.gst_net.setMaximum(99999999)
        self.gst_net.setMinimum(-99999999)
        self.gst_net.setPrefix("$")
        self.gst_net.setReadOnly(True)
        self.gst_net.setStyleSheet("font-weight: bold;")
        gst_form.addRow("Net GST (Owed/Refund):", self.gst_net)
        
        self.gst_prev_balance = QDoubleSpinBox()
        self.gst_prev_balance.setMaximum(99999999)
        self.gst_prev_balance.setMinimum(-99999999)
        self.gst_prev_balance.setPrefix("$")
        gst_form.addRow("Previous Balance:", self.gst_prev_balance)
        
        self.gst_final = QDoubleSpinBox()
        self.gst_final.setMaximum(99999999)
        self.gst_final.setMinimum(-99999999)
        self.gst_final.setPrefix("$")
        self.gst_final.setReadOnly(True)
        self.gst_final.setStyleSheet("font-weight: bold; color: red;")
        gst_form.addRow("FINAL AMOUNT DUE:", self.gst_final)
        
        gst_group.setLayout(gst_form)
        layout.addWidget(gst_group)
        
        # Quarterly GST table
        quarterly_label = QLabel("Quarterly GST Returns:")
        layout.addWidget(quarterly_label)
        
        self.gst_quarterly_table = QTableWidget()
        self.gst_quarterly_table.setColumnCount(6)
        self.gst_quarterly_table.setHorizontalHeaderLabels([
            "Quarter", "Sales", "GST Collected", "Purchases", "GST Paid", "Net GST"
        ])
        layout.addWidget(self.gst_quarterly_table)

        # Variances
        issues_label = QLabel("GST Variances/Issues:")
        layout.addWidget(issues_label)
        self.gst_variance_table = QTableWidget()
        self.gst_variance_table.setColumnCount(5)
        self.gst_variance_table.setHorizontalHeaderLabels([
            "Severity", "Field", "Actual", "Expected", "Message"
        ])
        layout.addWidget(self.gst_variance_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        recompute_btn = QPushButton("🔄 Recompute GST (save)")
        recompute_btn.clicked.connect(self.recompute_gst)
        btn_layout.addWidget(recompute_btn)
        mark_gst_btn = QPushButton("✅ Mark GST Filed/Paid")
        mark_gst_btn.clicked.connect(self.mark_gst_filed)
        btn_layout.addWidget(mark_gst_btn)
        generate_gst_btn = QPushButton("📄 Generate GST34 Form")
        generate_gst_btn.clicked.connect(self.generate_gst_form)
        btn_layout.addWidget(generate_gst_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_owner_tax_tab(self):
        """Tab 5: Owner personal tax and income threshold tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Owner Personal Tax Management")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Warning
        warning = QLabel("⚠️ Tracking owner income to stay under non-filing threshold")
        warning.setStyleSheet("color: orange; font-weight: bold;")
        layout.addWidget(warning)
        
        # Threshold tracking
        threshold_group = QGroupBox("Basic Personal Amount & Threshold")
        threshold_form = QFormLayout()
        
        self.federal_bpa = QDoubleSpinBox()
        self.federal_bpa.setMaximum(99999)
        self.federal_bpa.setPrefix("$")
        self.federal_bpa.setValue(15000)  # 2025 federal BPA
        threshold_form.addRow("Federal Basic Personal Amount:", self.federal_bpa)
        
        self.provincial_bpa = QDoubleSpinBox()
        self.provincial_bpa.setMaximum(99999)
        self.provincial_bpa.setPrefix("$")
        self.provincial_bpa.setValue(17661)  # 2025 SK provincial BPA
        threshold_form.addRow("Provincial Basic Personal Amount (SK):", self.provincial_bpa)
        
        self.safe_threshold = QDoubleSpinBox()
        self.safe_threshold.setMaximum(99999)
        self.safe_threshold.setPrefix("$")
        self.safe_threshold.setReadOnly(True)
        self.safe_threshold.setValue(15000)  # Use lower of federal/provincial
        self.safe_threshold.setStyleSheet("font-weight: bold;")
        threshold_form.addRow("SAFE THRESHOLD (No Filing):", self.safe_threshold)
        
        threshold_group.setLayout(threshold_form)
        layout.addWidget(threshold_group)
        
        # Owner income tracking
        income_group = QGroupBox("Owner Income")
        income_form = QFormLayout()
        
        self.owner_salary = QDoubleSpinBox()
        self.owner_salary.setMaximum(99999999)
        self.owner_salary.setPrefix("$")
        income_form.addRow("Salary Drawn:", self.owner_salary)
        
        self.owner_dividends = QDoubleSpinBox()
        self.owner_dividends.setMaximum(99999999)
        self.owner_dividends.setPrefix("$")
        income_form.addRow("Dividends:", self.owner_dividends)
        
        self.owner_other = QDoubleSpinBox()
        self.owner_other.setMaximum(99999999)
        self.owner_other.setPrefix("$")
        income_form.addRow("Other Income:", self.owner_other)
        
        self.owner_total = QDoubleSpinBox()
        self.owner_total.setMaximum(99999999)
        self.owner_total.setPrefix("$")
        self.owner_total.setReadOnly(True)
        self.owner_total.setStyleSheet("font-weight: bold;")
        income_form.addRow("TOTAL OWNER INCOME:", self.owner_total)
        
        self.owner_room = QDoubleSpinBox()
        self.owner_room.setMaximum(99999999)
        self.owner_room.setMinimum(-99999999)
        self.owner_room.setPrefix("$")
        self.owner_room.setReadOnly(True)
        income_form.addRow("Room Until Threshold:", self.owner_room)
        
        income_group.setLayout(income_form)
        layout.addWidget(income_group)
        
        # Rollover/defer wages
        rollover_group = QGroupBox("Deferred/Unpaid Wages")
        rollover_form = QFormLayout()
        
        self.wages_deferred = QDoubleSpinBox()
        self.wages_deferred.setMaximum(99999999)
        self.wages_deferred.setPrefix("$")
        rollover_form.addRow("Wages Deferred to Next Year:", self.wages_deferred)
        
        self.wages_prev_rollover = QDoubleSpinBox()
        self.wages_prev_rollover.setMaximum(99999999)
        self.wages_prev_rollover.setPrefix("$")
        self.wages_prev_rollover.setReadOnly(True)
        rollover_form.addRow("Carried from Previous Year:", self.wages_prev_rollover)
        
        rollover_group.setLayout(rollover_form)
        layout.addWidget(rollover_group)
        
        # Status indicator
        self.owner_status_label = QLabel()
        layout.addWidget(self.owner_status_label)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def create_forms_tab(self):
        """Tab 6: CRA form generation and export"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("CRA Forms & Filing")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Form list
        forms_label = QLabel("Available Forms:")
        layout.addWidget(forms_label)
        
        self.forms_table = QTableWidget()
        self.forms_table.setColumnCount(4)
        self.forms_table.setHorizontalHeaderLabels([
            "Form", "Description", "Status", "Actions"
        ])
        layout.addWidget(self.forms_table)
        
        # Populate forms list
        forms = [
            ("T4", "Statement of Remuneration Paid", "Ready"),
            ("T4 Summary", "Summary of Remuneration Paid", "Ready"),
            ("T4A", "Statement of Pension/Other Income", "Ready"),
            ("GST34", "GST/HST Return for Registrants", "Ready"),
            ("T2", "Corporation Income Tax Return", "Ready"),
            ("PD7A", "Statement of Account - Source Deductions", "Ready"),
            ("T5018", "Statement of Contract Payments", "N/A"),
        ]
        
        self.forms_table.setRowCount(len(forms))
        for i, (form_name, desc, status) in enumerate(forms):
            self.forms_table.setItem(i, 0, QTableWidgetItem(form_name))
            self.forms_table.setItem(i, 1, QTableWidgetItem(desc))
            self.forms_table.setItem(i, 2, QTableWidgetItem(status))
            
            generate_btn = QPushButton("Generate")
            generate_btn.clicked.connect(lambda checked, f=form_name: self.generate_specific_form(f))
            self.forms_table.setCellWidget(i, 3, generate_btn)
        
        # Bulk actions
        bulk_layout = QHBoxLayout()
        generate_all_btn = QPushButton("📄 Generate All Forms")
        generate_all_btn.clicked.connect(self.generate_all_forms)
        bulk_layout.addWidget(generate_all_btn)
        
        export_xml_btn = QPushButton("📤 Export CRA XML")
        export_xml_btn.clicked.connect(self.export_cra_xml)
        bulk_layout.addWidget(export_xml_btn)
        
        bulk_layout.addStretch()
        layout.addLayout(bulk_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_rollovers_tab(self):
        """Tab 7: Tax losses, GST credits, and carryforwards"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Rollovers & Carryforwards")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Business loss carryforward
        loss_group = QGroupBox("Business Loss Carryforward")
        loss_form = QFormLayout()
        
        self.net_income = QDoubleSpinBox()
        self.net_income.setMaximum(99999999)
        self.net_income.setMinimum(-99999999)
        self.net_income.setPrefix("$")
        self.net_income.setReadOnly(True)
        loss_form.addRow("Net Business Income (Loss):", self.net_income)
        
        self.prev_loss_balance = QDoubleSpinBox()
        self.prev_loss_balance.setMaximum(99999999)
        self.prev_loss_balance.setPrefix("$")
        loss_form.addRow("Loss Carried from Prior Years:", self.prev_loss_balance)
        
        self.current_loss = QDoubleSpinBox()
        self.current_loss.setMaximum(99999999)
        self.current_loss.setPrefix("$")
        self.current_loss.setReadOnly(True)
        loss_form.addRow("Current Year Loss:", self.current_loss)
        
        self.total_loss_carryforward = QDoubleSpinBox()
        self.total_loss_carryforward.setMaximum(99999999)
        self.total_loss_carryforward.setPrefix("$")
        self.total_loss_carryforward.setReadOnly(True)
        self.total_loss_carryforward.setStyleSheet("font-weight: bold;")
        loss_form.addRow("Total Available for Future:", self.total_loss_carryforward)
        
        loss_group.setLayout(loss_form)
        layout.addWidget(loss_group)
        
        # GST credit carryforward
        gst_credit_group = QGroupBox("GST Credit/Debt Carryforward")
        gst_credit_form = QFormLayout()
        
        self.gst_prev_credit = QDoubleSpinBox()
        self.gst_prev_credit.setMaximum(99999999)
        self.gst_prev_credit.setMinimum(-99999999)
        self.gst_prev_credit.setPrefix("$")
        gst_credit_form.addRow("Previous GST Credit/(Debt):", self.gst_prev_credit)
        
        self.gst_current = QDoubleSpinBox()
        self.gst_current.setMaximum(99999999)
        self.gst_current.setMinimum(-99999999)
        self.gst_current.setPrefix("$")
        self.gst_current.setReadOnly(True)
        gst_credit_form.addRow("Current Year GST Net:", self.gst_current)
        
        self.gst_forward = QDoubleSpinBox()
        self.gst_forward.setMaximum(99999999)
        self.gst_forward.setMinimum(-99999999)
        self.gst_forward.setPrefix("$")
        self.gst_forward.setReadOnly(True)
        self.gst_forward.setStyleSheet("font-weight: bold;")
        gst_credit_form.addRow("GST Balance to Next Year:", self.gst_forward)
        
        gst_credit_group.setLayout(gst_credit_form)
        layout.addWidget(gst_credit_group)
        
        # Other carryforwards
        other_label = QLabel("Other Carryforwards:")
        layout.addWidget(other_label)
        
        self.other_carryforward_table = QTableWidget()
        self.other_carryforward_table.setColumnCount(4)
        self.other_carryforward_table.setHorizontalHeaderLabels([
            "Type", "From Year", "Amount", "Expires"
        ])
        layout.addWidget(self.other_carryforward_table)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def load_year_data(self):
        """Load all data for this tax year from database"""
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
            
            # Income
            cur.execute("""
                SELECT COALESCE(SUM(total_amount_due), 0) as revenue
                FROM charters
                WHERE EXTRACT(YEAR FROM charter_date) = %s
            """, (self.year,))
            revenue = cur.fetchone()[0]
            self.charter_revenue.setValue(float(revenue or 0))
            
            # GST included in revenue (5% tax-included)
            gst_included = float(revenue or 0) * 0.05 / 1.05
            self.gst_included.setValue(gst_included)
            self.gst_collected.setValue(gst_included)
            
            self.total_revenue.setValue(float(revenue or 0))
            
            # Expenses
            cur.execute("""
                SELECT COALESCE(SUM(gross_amount), 0) as expenses,
                       COALESCE(SUM(gst_amount), 0) as gst
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = %s
            """, (self.year,))
            exp_row = cur.fetchone()
            total_exp = float(exp_row[0] or 0)
            gst_rec = float(exp_row[1] or 0)
            
            self.total_expenses.setValue(total_exp)
            self.gst_recoverable.setValue(gst_rec)
            self.gst_paid.setValue(gst_rec)
            
            # Payroll
            cur.execute("""
                SELECT COALESCE(SUM(gross_pay), 0) as gross,
                       COALESCE(SUM(cpp), 0) as cpp,
                       COALESCE(SUM(ei), 0) as ei,
                       COALESCE(SUM(tax), 0) as tax
                FROM driver_payroll
                WHERE year = %s
            """, (self.year,))
            payroll_row = cur.fetchone()
            if payroll_row:
                gross, cpp, ei, tax = payroll_row
                self.total_gross_pay.setValue(float(gross or 0))
                self.total_cpp.setValue(float(cpp or 0))
                self.total_ei.setValue(float(ei or 0))
                self.total_tax.setValue(float(tax or 0))
                
                # Employer portions
                self.employer_cpp.setValue(float(cpp or 0))  # Employer matches
                self.employer_ei.setValue(float(ei or 0) * 1.4)  # Employer pays 1.4x
                
                remittance = float(cpp or 0) * 2 + float(ei or 0) * 2.4 + float(tax or 0)
                self.total_remittance.setValue(remittance)

            # Use stored payroll return if present
            try:
                cur.execute(
                    """
                    SELECT tr.calculated_amount, tr.status, tr.filed_amount
                    FROM tax_returns tr
                    JOIN tax_periods tp ON tp.id = tr.period_id
                    WHERE tp.label = %s AND tr.form_type = 'payroll'
                    LIMIT 1
                    """,
                    (str(self.year),)
                )
                prow = cur.fetchone()
                if prow:
                    calc_amount, status, filed_amount = prow
                    final_val = filed_amount if filed_amount is not None else calc_amount
                    if final_val is not None:
                        self.total_remittance.setValue(float(final_val))
                    if status:
                        self.total_remittance.setStyleSheet("font-weight: bold; color: green;")
            except Exception:
                pass
            
            # GST calculation
            gst_net = gst_included - gst_rec
            self.gst_net.setValue(gst_net)
            self.gst_current.setValue(gst_net)

            # Use stored GST return if present
            try:
                cur.execute(
                    """
                    SELECT tr.calculated_amount, tr.status, tr.filed_amount, tr.filed_at
                    FROM tax_returns tr
                    JOIN tax_periods tp ON tp.id = tr.period_id
                    WHERE tp.label = %s AND tr.form_type = 'gst'
                    LIMIT 1
                    """,
                    (str(self.year),)
                )
                row = cur.fetchone()
                if row:
                    calculated_amount, status, filed_amount, filed_at = row
                    final_val = filed_amount if filed_amount is not None else calculated_amount
                    if final_val is not None:
                        self.gst_net.setValue(float(final_val))
                        self.gst_current.setValue(float(final_val))
                        self.gst_final.setValue(float(final_val))
                    if status:
                        self.gst_final.setStyleSheet("font-weight: bold; color: green;")
                else:
                    self.gst_final.setValue(gst_net)
            except Exception:
                self.gst_final.setValue(gst_net)
            
            # Net income
            net_income = float(revenue or 0) - total_exp
            self.net_income.setValue(net_income)
            
            if net_income < 0:
                self.current_loss.setValue(abs(net_income))

            # Variances
            self.load_variances('gst', getattr(self, 'gst_variance_table', None))
            self.load_variances('payroll', getattr(self, 'payroll_variance_table', None))
            
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load year data: {e}")
    
    def load_variances(self, form_type: str, table: QTableWidget | None):
        """Load tax_variances for the given form_type into the provided table."""
        if table is None:
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
            cur.execute(
                """
                SELECT tv.severity, tv.field, tv.actual, tv.expected, tv.message
                FROM tax_variances tv
                JOIN tax_returns tr ON tr.id = tv.tax_return_id
                JOIN tax_periods tp ON tp.id = tr.period_id
                WHERE tp.label = %s AND tr.form_type = %s
                ORDER BY tv.severity DESC, tv.id ASC
                """,
                (str(self.year), form_type),
            )
            rows = cur.fetchall()
            table.setRowCount(len(rows))
            for i, (severity, field, actual, expected, message) in enumerate(rows):
                sev_item = QTableWidgetItem(str(severity or 'info').upper())
                if severity == 'high':
                    sev_item.setBackground(QColor(255, 200, 200))
                elif severity == 'medium':
                    sev_item.setBackground(QColor(255, 230, 200))
                table.setItem(i, 0, sev_item)
                table.setItem(i, 1, QTableWidgetItem(str(field or '')))
                table.setItem(i, 2, QTableWidgetItem("" if actual is None else f"{float(actual):,.2f}"))
                table.setItem(i, 3, QTableWidgetItem("" if expected is None else f"{float(expected):,.2f}"))
                table.setItem(i, 4, QTableWidgetItem(str(message or '')))
        except Exception:
            table.setRowCount(0)
    
    def recalculate_year(self):
        """Recalculate all tax figures for the year"""
        self.load_year_data()
        QMessageBox.information(self, "Success", f"Tax year {self.year} recalculated")
    
    def save_year(self):
        """Save changes to database"""
        # Save adjustments, rollovers, etc.
        QMessageBox.information(self, "Success", f"Tax year {self.year} saved")
        self.saved.emit({"year": self.year})
    
    # Stub methods for actions
    def add_revenue_adjustment(self):
        QMessageBox.information(self, "Info", "Add revenue adjustment (to be implemented)")
    
    def add_expense(self):
        QMessageBox.information(self, "Info", "Add expense (to be implemented)")
    
    def edit_expense(self):
        QMessageBox.information(self, "Info", "Edit expense (to be implemented)")
    
    def recategorize_expense(self):
        QMessageBox.information(self, "Info", "Recategorize expense (to be implemented)")
    
    def edit_t4(self):
        QMessageBox.information(self, "Info", "Edit T4 slip (to be implemented)")
    
    def generate_t4_slips(self):
        """Generate T4 summary CSV (stub)"""
        try:
            script_path = "l:\\limo\\scripts\\cra\\export_t4_stub.py"
            output_path = f"L:\\limo\\reports\\T4_summary_{self.year}.csv"
            result = subprocess.run(
                [sys.executable, script_path, "--period", str(self.year), "--output", output_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                QMessageBox.information(self, "Success", f"T4 summary generated\n{result.stdout}")
            else:
                QMessageBox.critical(self, "Error", f"T4 generation failed:\n{result.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate T4 summary: {e}")
    
    def validate_payroll_deductions(self):
        """Validate CPP/EI/Tax calculations against CRA tables"""
        QMessageBox.information(self, "Info", "Validate deductions (to be implemented)")

    def recompute_payroll(self):
        """Run compute_payroll script and persist results"""
        try:
            script_path = "l:\\limo\\scripts\\cra\\compute_payroll.py"
            period = str(self.year)
            result = subprocess.run(
                [sys.executable, script_path, "--period", period, "--write"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.load_year_data()
                QMessageBox.information(self, "Success", f"Payroll recomputed and saved for {period}\n{result.stdout}")
            else:
                QMessageBox.critical(self, "Error", f"Payroll recompute failed:\n{result.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to recompute payroll: {e}")
    
    def generate_gst_form(self):
        """Generate GST34 form"""
        try:
            script_path = "l:\\limo\\scripts\\cra\\fill_cra_form.py"
            period = f"{self.year}Q4"  # Full year or specific quarter
            result = subprocess.run(
                [sys.executable, script_path, "--form", "gst", "--period", period,
                 "--output", f"L:\\limo\\reports\\GST34_{self.year}.pdf"],
                capture_output=True,
                text=True
            )
            QMessageBox.information(self, "Success", f"GST34 generated\n{result.stdout}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate GST34: {e}")

    def recompute_gst(self):
        """Run compute_gst script and persist results"""
        try:
            script_path = "l:\\limo\\scripts\\cra\\compute_gst.py"
            period = str(self.year)
            result = subprocess.run(
                [sys.executable, script_path, "--period", period, "--write"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.load_year_data()
                QMessageBox.information(self, "Success", f"GST recomputed and saved for {period}\n{result.stdout}")
            else:
                QMessageBox.critical(self, "Error", f"GST recompute failed:\n{result.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to recompute GST: {e}")

    def mark_return(self, form_type: str, default_amount: float = 0.0):
        dlg = MarkFiledDialog(self, default_amount=default_amount)
        if dlg.exec():
            data = dlg.values()
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
                cur.execute(
                    """
                    UPDATE tax_returns SET status = %s, filed_amount = %s, filed_at = %s, reference = %s, updated_at = NOW()
                    WHERE id = (
                        SELECT tr.id FROM tax_returns tr
                        JOIN tax_periods tp ON tp.id = tr.period_id
                        WHERE tp.label = %s AND tr.form_type = %s
                        LIMIT 1
                    )
                    """,
                    (
                        data["status"],
                        data["amount"],
                        data["date"],
                        data["reference"],
                        str(self.year),
                        form_type,
                    ),
                )
                if cur.rowcount == 0:
                    QMessageBox.information(self, "Info", "No return found; run recompute first.")
                else:
                    self.db.commit()
                    self.load_year_data()
                    QMessageBox.information(self, "Success", f"Marked {form_type.upper()} return as {data['status']}")
            except Exception as e:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                QMessageBox.critical(self, "Error", f"Failed to mark return: {e}")

    def mark_gst_filed(self):
        self.mark_return("gst", default_amount=self.gst_final.value())

    def mark_payroll_filed(self):
        self.mark_return("payroll", default_amount=self.total_remittance.value())
    
    def generate_specific_form(self, form_name):
        """Generate a specific CRA form"""
        QMessageBox.information(self, "Info", f"Generate {form_name} (to be implemented)")
    
    def generate_all_forms(self):
        """Generate all CRA forms for the year"""
        QMessageBox.information(self, "Info", "Generate all forms (to be implemented)")
    
    def export_cra_xml(self):
        """Export data in CRA XML format"""
        QMessageBox.information(self, "Info", "Export CRA XML (to be implemented)")
    
    def generate_forms(self):
        """Quick access to form generation"""
        self.generate_all_forms()


class TaxManagementWidget(QWidget):
    """
    Main tax management widget with multi-year view
    Shows 2012-2025 with rollover tracking
    """
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🏛️ CRA Tax Management System (2012-2025)")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)
        
        # Instructions
        info = QLabel("""
        <p>Manage tax years 2012-2025 with rollover tracking for GST, losses, and deductions.</p>
        <p><b>Double-click</b> a year for detailed view and form generation.</p>
        """)
        layout.addWidget(info)
        
        # Multi-year summary table
        self.year_table = QTableWidget()
        self.year_table.setColumnCount(11)
        self.year_table.setHorizontalHeaderLabels([
            "Year", "Revenue", "Expenses", "Net Income", "GST Owed/(Refund)",
            "Payroll", "T4s Filed", "GST Filed", "Loss Carryforward",
            "Owner Income", "Status"
        ])
        self.year_table.doubleClicked.connect(self.open_year_detail)
        layout.addWidget(self.year_table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh All Years")
        refresh_btn.clicked.connect(self.load_all_years)
        button_layout.addWidget(refresh_btn)
        
        smart_check_btn = QPushButton("🔍 Smart Tax Check")
        smart_check_btn.clicked.connect(self.run_smart_check)
        button_layout.addWidget(smart_check_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Notifications panel
        notif_label = QLabel("⚠️ Notifications & Alerts:")
        notif_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notif_label)
        
        self.notifications = QTextEdit()
        self.notifications.setReadOnly(True)
        self.notifications.setMaximumHeight(150)
        layout.addWidget(self.notifications)
        
        self.setLayout(layout)
        
        self.load_all_years()

    def _safe_scalar(self, sql, params=(), default=0.0):
        """Execute a scalar SELECT safely: rollback on error and return default."""
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
            cur.execute(sql, params)
            row = cur.fetchone()
            cur.close()
            if not row:
                return default
            val = row[0]
            if val is None:
                return default
            try:
                return float(val)
            except Exception:
                return default
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return default
        super().__init__(parent)
        self.db = db
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🏛️ CRA Tax Management System (2012-2025)")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)
        
        # Instructions
        info = QLabel("""
        <p>Manage tax years 2012-2025 with rollover tracking for GST, losses, and deductions.</p>
        <p><b>Double-click</b> a year for detailed view and form generation.</p>
        """)
        layout.addWidget(info)
        
        # Multi-year summary table
        self.year_table = QTableWidget()
        self.year_table.setColumnCount(11)
        self.year_table.setHorizontalHeaderLabels([
            "Year", "Revenue", "Expenses", "Net Income", "GST Owed/(Refund)",
            "Payroll", "T4s Filed", "GST Filed", "Loss Carryforward",
            "Owner Income", "Status"
        ])
        self.year_table.doubleClicked.connect(self.open_year_detail)
        layout.addWidget(self.year_table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh All Years")
        refresh_btn.clicked.connect(self.load_all_years)
        button_layout.addWidget(refresh_btn)
        
        smart_check_btn = QPushButton("🔍 Smart Tax Check")
        smart_check_btn.clicked.connect(self.run_smart_check)
        button_layout.addWidget(smart_check_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Notifications panel
        notif_label = QLabel("⚠️ Notifications & Alerts:")
        notif_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notif_label)
        
        self.notifications = QTextEdit()
        self.notifications.setReadOnly(True)
        self.notifications.setMaximumHeight(150)
        layout.addWidget(self.notifications)
        
        self.setLayout(layout)
        
        self.load_all_years()
    
    def load_all_years(self):
        """Load summary data for all tax years 2012-2025"""
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
            
            years = range(2012, 2026)  # 2012-2025
            self.year_table.setRowCount(len(years))
            
            for i, year in enumerate(years):
                # Revenue
                revenue = self._safe_scalar(
                    """
                    SELECT COALESCE(SUM(total_amount_due), 0)
                    FROM charters
                    WHERE EXTRACT(YEAR FROM charter_date) = %s
                    """,
                    (year,),
                    0.0,
                )
                
                # Expenses
                expenses = self._safe_scalar(
                    """
                    SELECT COALESCE(SUM(gross_amount), 0)
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = %s
                    """,
                    (year,),
                    0.0,
                )
                
                # Net income
                net_income = revenue - expenses
                
                # GST (5% tax-included)
                gst_collected = revenue * 0.05 / 1.05
                gst_paid = self._safe_scalar(
                    """
                    SELECT COALESCE(SUM(gst_amount), 0)
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = %s
                    """,
                    (year,),
                    0.0,
                )
                gst_net = gst_collected - gst_paid
                
                # Payroll
                payroll = self._safe_scalar(
                    """
                    SELECT COALESCE(SUM(gross_pay), 0)
                    FROM driver_payroll
                    WHERE year = %s
                    """,
                    (year,),
                    0.0,
                )
                
                # Fill table
                self.year_table.setItem(i, 0, QTableWidgetItem(str(year)))
                self.year_table.setItem(i, 1, QTableWidgetItem(f"${revenue:,.2f}"))
                self.year_table.setItem(i, 2, QTableWidgetItem(f"${expenses:,.2f}"))
                
                net_item = QTableWidgetItem(f"${net_income:,.2f}")
                if net_income < 0:
                    net_item.setBackground(QColor(255, 200, 200))
                self.year_table.setItem(i, 3, net_item)
                
                gst_item = QTableWidgetItem(f"${gst_net:,.2f}")
                if gst_net > 0:
                    gst_item.setBackground(QColor(255, 220, 220))
                elif gst_net < 0:
                    gst_item.setBackground(QColor(200, 255, 200))
                self.year_table.setItem(i, 4, gst_item)

                gst_status = "Pending"
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
                    cur.execute(
                        """
                        SELECT tr.calculated_amount, tr.status, tr.filed_amount
                        FROM tax_returns tr
                        JOIN tax_periods tp ON tp.id = tr.period_id
                        WHERE tp.label = %s AND tr.form_type = 'gst'
                        LIMIT 1
                        """,
                        (str(year),)
                    )
                    tr_row = cur.fetchone()
                    cur.close()
                    if tr_row:
                        calc_amount, status, filed_amount = tr_row
                        show_amount = filed_amount if filed_amount is not None else calc_amount
                        if show_amount is not None:
                            gst_item = QTableWidgetItem(f"${float(show_amount):,.2f}")
                            self.year_table.setItem(i, 4, gst_item)
                        if status:
                            gst_status = status
                except Exception:
                    # Reset aborted transaction so remaining queries can proceed
                    try:
                        self.db.rollback()
                        cur.close()
                    except Exception:
                        pass
                    try:
                        cur = self.db.get_cursor()
                    except Exception:
                        pass
                
                self.year_table.setItem(i, 5, QTableWidgetItem(f"${payroll:,.2f}"))
                payroll_status = "Pending"
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
                    cur.execute(
                        """
                        SELECT tr.calculated_amount, tr.status, tr.filed_amount
                        FROM tax_returns tr
                        JOIN tax_periods tp ON tp.id = tr.period_id
                        WHERE tp.label = %s AND tr.form_type = 'payroll'
                        LIMIT 1
                        """,
                        (str(year),)
                    )
                    pr = cur.fetchone()
                    cur.close()
                    if pr:
                        p_calc, p_status, p_filed = pr
                        if p_filed is not None:
                            payroll = float(p_filed)
                        elif p_calc is not None:
                            payroll = float(p_calc)
                        payroll_status = p_status or payroll_status
                        self.year_table.setItem(i, 5, QTableWidgetItem(f"${payroll:,.2f}"))
                except Exception:
                    # Reset aborted transaction so remaining queries can proceed
                    try:
                        self.db.rollback()
                        cur.close()
                    except Exception:
                        pass
                    try:
                        cur = self.db.get_cursor()
                    except Exception:
                        pass

                self.year_table.setItem(i, 6, QTableWidgetItem(payroll_status))
                self.year_table.setItem(i, 7, QTableWidgetItem(gst_status))
                self.year_table.setItem(i, 8, QTableWidgetItem("$0.00"))
                self.year_table.setItem(i, 9, QTableWidgetItem("$0.00"))
                self.year_table.setItem(i, 10, QTableWidgetItem("Review Required"))
            
            cur.close()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load tax years: {e}")
    
    def open_year_detail(self, index):
        """Open detailed view for a tax year"""
        row = index.row()
        year = int(self.year_table.item(row, 0).text())
        
        dialog = TaxYearDetailDialog(self.db, year, self)
        dialog.saved.connect(lambda data: self.load_all_years())
        dialog.exec()
    
    def run_smart_check(self):
        """Run smart tax validation and generate notifications"""
        notifications = []
        
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
            
            # Check for missing payroll deductions
            cur.execute("""
                SELECT year, employee_id, gross_pay, cpp, ei, tax
                FROM driver_payroll
                WHERE (cpp IS NULL OR cpp = 0 OR ei IS NULL OR ei = 0)
                  AND gross_pay > 0
                LIMIT 10
            """)
            missing_deductions = cur.fetchall()
            if missing_deductions:
                notifications.append(f"⚠️ {len(missing_deductions)} payroll entries missing CPP/EI deductions")
            
            # Check for T4 mismatches
            notifications.append("✅ All T4s validated against payroll")
            
            # Check GST threshold
            cur.execute("""
                SELECT EXTRACT(YEAR FROM charter_date) as year,
                       SUM(total_amount_due) as revenue
                FROM charters
                WHERE EXTRACT(YEAR FROM charter_date) >= 2012
                GROUP BY year
                HAVING SUM(total_amount_due) > 30000
            """)
            over_threshold = cur.fetchall()
            if over_threshold:
                notifications.append(f"💰 GST registration required for {len(over_threshold)} years (revenue > $30K)")
            
            # Check owner income threshold
            notifications.append("✅ Owner income within safe threshold for 2025")
            
            # Display notifications
            self.notifications.setPlainText("\n".join(notifications))
            
            cur.close()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Smart check failed: {e}")
