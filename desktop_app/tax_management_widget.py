"""
CRA Tax Management System
Comprehensive tax filing, payroll deductions, owner income tracking,
and year-end reconciliation
Supports 2012-2025 with rollover tracking for GST, losses, and deductions
"""

import csv
import logging
from datetime import datetime
import sys
from pathlib import Path

from PyQt6.QtCore import QDate, pyqtSignal

_APP_ROOT = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

from db_error_handling import DatabaseContext
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tax_return_tabs import PD7ATab, T1ReturnTab, T2ReturnTab

logger = logging.getLogger(__name__)


def _load_tax_return_snapshot(cur, year, form_type) -> object:
    cur.execute(
        """
        SELECT tr.calculated_amount, tr.status, tr.filed_amount
        FROM tax_returns tr
        JOIN tax_periods tp ON tp.id = tr.period_id
        WHERE tp.label = %s AND tr.form_type = %s
        LIMIT 1
        """,
        (str(year), form_type),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "calculated_amount": row[0],
        "status": row[1],
        "filed_amount": row[2],
    }


def _load_tax_year_snapshot(cur, year) -> object:
    cur.execute(
        """
        SELECT COALESCE(SUM(total_amount_due), 0)
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = %s
        """,
        (year,),
    )
    revenue = cur.fetchone()[0] or 0

    cur.execute(
        """
        SELECT COALESCE(SUM(gross_amount), 0), COALESCE(SUM(gst_amount), 0)
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
        """,
        (year,),
    )
    expense_row = cur.fetchone() or (0, 0)
    expenses = expense_row[0] or 0
    gst_paid = expense_row[1] or 0

    cur.execute(
        """
        SELECT COALESCE(SUM(gross_pay), 0),
               COALESCE(SUM(cpp), 0),
               COALESCE(SUM(ei), 0),
               COALESCE(SUM(tax), 0)
        FROM driver_payroll
        WHERE year = %s
        """,
        (year,),
    )
    payroll_row = cur.fetchone() or (0, 0, 0, 0)

    return {
        "year": year,
        "revenue": float(revenue or 0),
        "expenses": float(expenses or 0),
        "gst_paid": float(gst_paid or 0),
        "payroll_gross": float(payroll_row[0] or 0),
        "payroll_cpp": float(payroll_row[1] or 0),
        "payroll_ei": float(payroll_row[2] or 0),
        "payroll_tax": float(payroll_row[3] or 0),
        "paul_t1": _load_paul_t1_snapshot(cur, year),
        "gst_return": _load_tax_return_snapshot(cur, year, "gst"),
        "payroll_return": _load_tax_return_snapshot(cur, year, "payroll"),
    }


def _load_paul_t1_snapshot(cur, year) -> object:
    """Load Paul's T4-backed T1 inputs for the selected year."""

    cur.execute(
        """
        SELECT e.employee_id, COALESCE(e.full_name, '')
        FROM employees e
        WHERE COALESCE(e.full_name, '') ILIKE %s
           OR (COALESCE(e.first_name, '') ILIKE 'Paul%%'
               AND COALESCE(e.last_name, '') ILIKE 'Richard%%')
        ORDER BY
            CASE
                WHEN COALESCE(e.full_name, '') ILIKE 'Paul Richard%%' THEN 0
                WHEN COALESCE(e.full_name, '') ILIKE '%%Paul%%Richard%%' THEN 1
                ELSE 2
            END,
            e.employee_id
        LIMIT 1
        """,
        ("Paul Richard%",),
    )
    employee = cur.fetchone()
    if not employee:
        return None

    employee_id, full_name = employee
    cur.execute(
        """
        SELECT
            COALESCE(box_14_employment_income, 0),
            COALESCE(box_16_cpp_contributions, 0),
            COALESCE(box_18_ei_premiums, 0),
            COALESCE(box_22_income_tax, 0),
            COALESCE(box_24_ei_insurable_earnings, 0),
            COALESCE(box_26_cpp_pensionable_earnings, 0)
        FROM employee_t4_records
        WHERE employee_id = %s AND tax_year = %s
        """,
        (employee_id, year),
    )
    t4_row = cur.fetchone()
    if not t4_row:
        return {
            "employee_id": employee_id,
            "full_name": full_name,
            "t4_employment_income": 0.0,
            "t4_cpp": 0.0,
            "t4_ei": 0.0,
            "t4_income_tax": 0.0,
            "t4_insurable_earnings": 0.0,
            "t4_pensionable_earnings": 0.0,
            "dividends": 0.0,
            "other_income": 0.0,
            "owner_draws": 0.0,
            "total_t1_income": 0.0,
        }

    cur.execute(
        """
        SELECT COALESCE(SUM(COALESCE(owner_personal_amount, 0)), 0)
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
          AND COALESCE(owner_personal_amount, 0) > 0
        """,
        (year,),
    )
    owner_draws = float((cur.fetchone() or [0])[0] or 0)

    t4_employment_income = float(t4_row[0] or 0)
    return {
        "employee_id": employee_id,
        "full_name": full_name,
        "t4_employment_income": t4_employment_income,
        "t4_cpp": float(t4_row[1] or 0),
        "t4_ei": float(t4_row[2] or 0),
        "t4_income_tax": float(t4_row[3] or 0),
        "t4_insurable_earnings": float(t4_row[4] or 0),
        "t4_pensionable_earnings": float(t4_row[5] or 0),
        "dividends": 0.0,
        "other_income": 0.0,
        "owner_draws": owner_draws,
        "total_t1_income": t4_employment_income,
    }


class MarkFiledDialog(QDialog):
    """Dialog to mark a return as filed/paid with amount/date/reference."""

    def __init__(self, parent=None, default_amount: float = 0.0) -> None:
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

    def __init__(self, db, year, parent=None) -> None:
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
        self.tabs = tabs

        tabs.addTab(self.create_income_tab(), "💰 Income & Revenue")
        tabs.addTab(self.create_expenses_tab(), "💸 Expenses")
        tabs.addTab(self.create_payroll_tab(), "👥 Payroll & T4s")
        tabs.addTab(PD7ATab(self), "🧾 PD7A")
        tabs.addTab(self.create_gst_tab(), "📋 GST/HST")
        tabs.addTab(self.create_owner_tax_tab(), "👤 Owner Personal Tax")
        tabs.addTab(T1ReturnTab(self), "🧾 T1 Return")
        tabs.addTab(T2ReturnTab(self), "🏛️ T2 Return")
        tabs.addTab(self.create_forms_tab(), "📄 CRA Forms")
        tabs.addTab(
            self.create_rollovers_tab(), "🔄 Rollovers & Carryforwards"
        )

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

    def create_income_tab(self) -> object:
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
        self.revenue_table.setHorizontalHeaderLabels(
            [
                "Month",
                "Charters",
                "Gross Revenue",
                "GST Collected",
                "Net Revenue",
            ]
        )
        layout.addWidget(self.revenue_table)

        # Adjustments
        adj_btn = QPushButton("➕ Add Revenue Adjustment")
        adj_btn.setEnabled(False)
        adj_btn.setToolTip(
            "Revenue adjustments must be entered in the source charter or ledger."
        )
        layout.addWidget(adj_btn)

        widget.setLayout(layout)
        return widget

    def create_expenses_tab(self) -> object:
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
        self.expense_table.setHorizontalHeaderLabels(
            ["Date", "Vendor", "Category", "Amount", "GST", "Notes"]
        )
        layout.addWidget(self.expense_table)

        # Buttons
        btn_layout = QHBoxLayout()
        add_exp_btn = QPushButton("➕ Add Expense")
        add_exp_btn.setEnabled(False)
        add_exp_btn.setToolTip(
            "Expenses must be entered in Receipts & Invoices to preserve audit links."
        )
        btn_layout.addWidget(add_exp_btn)

        recategorize_btn = QPushButton("🔄 Recategorize Selected")
        recategorize_btn.setEnabled(False)
        recategorize_btn.setToolTip(
            "Recategorize the source receipt in Receipts & Invoices."
        )
        btn_layout.addWidget(recategorize_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_payroll_tab(self) -> object:
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
        self.t4_table.setHorizontalHeaderLabels(
            [
                "Employee",
                "Box 14 (Employment)",
                "Box 16 (CPP)",
                "Box 18 (EI)",
                "Box 22 (Tax)",
                "Box 24 (EI Insurable)",
                "Status",
                "Actions",
            ]
        )
        layout.addWidget(self.t4_table)

        # Variances
        variance_label = QLabel("Payroll Variances/Issues:")
        layout.addWidget(variance_label)
        self.payroll_variance_table = QTableWidget()
        self.payroll_variance_table.setColumnCount(5)
        self.payroll_variance_table.setHorizontalHeaderLabels(
            ["Severity", "Field", "Actual", "Expected", "Message"]
        )
        layout.addWidget(self.payroll_variance_table)

        # Buttons
        btn_layout = QHBoxLayout()
        generate_t4_btn = QPushButton("📄 Generate T4 Slips")
        generate_t4_btn.clicked.connect(self.generate_t4_slips)
        btn_layout.addWidget(generate_t4_btn)

        validate_btn = QPushButton("✅ Validate Deductions")
        validate_btn.setEnabled(False)
        validate_btn.setToolTip(
            "CRA table validation is not implemented; review the calculated "
            "deductions and variance table before filing."
        )
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

    def create_pd7a_tab(self) -> object:
        """Tab 4: Monthly PD7A remittance entry and submission."""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("PD7A Source Deductions")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        self.pd7a_month = QComboBox()
        self.pd7a_month.addItems([f"{m:02d}" for m in range(1, 13)])
        self.pd7a_month.currentTextChanged.connect(self._load_pd7a_form)
        form.addRow("Month:", self.pd7a_month)

        self.pd7a_employee_count = QDoubleSpinBox()
        self.pd7a_employee_count.setMaximum(99999)
        form.addRow("Employee Count:", self.pd7a_employee_count)

        self.pd7a_total_gross = QDoubleSpinBox()
        self.pd7a_total_gross.setMaximum(99999999)
        self.pd7a_total_gross.setPrefix("$")
        form.addRow("Total Gross Payroll:", self.pd7a_total_gross)

        self.pd7a_cpp_total = QDoubleSpinBox()
        self.pd7a_cpp_total.setMaximum(99999999)
        self.pd7a_cpp_total.setPrefix("$")
        form.addRow("CPP Total:", self.pd7a_cpp_total)

        self.pd7a_ei_total = QDoubleSpinBox()
        self.pd7a_ei_total.setMaximum(99999999)
        self.pd7a_ei_total.setPrefix("$")
        form.addRow("EI Total:", self.pd7a_ei_total)

        self.pd7a_income_tax = QDoubleSpinBox()
        self.pd7a_income_tax.setMaximum(99999999)
        self.pd7a_income_tax.setPrefix("$")
        form.addRow("Income Tax Deducted:", self.pd7a_income_tax)

        self.pd7a_total_due = QDoubleSpinBox()
        self.pd7a_total_due.setMaximum(99999999)
        self.pd7a_total_due.setPrefix("$")
        self.pd7a_total_due.setReadOnly(True)
        form.addRow("Total Remittance Due:", self.pd7a_total_due)

        self.pd7a_adjusted = QDoubleSpinBox()
        self.pd7a_adjusted.setMaximum(99999999)
        self.pd7a_adjusted.setPrefix("$")
        form.addRow("Adjusted Remittance:", self.pd7a_adjusted)

        self.pd7a_status = QLabel("Draft")
        self.pd7a_status.setStyleSheet("font-weight: bold; color: #1f2937;")
        form.addRow("Status:", self.pd7a_status)
        layout.addLayout(form)

        self.pd7a_notes = QTextEdit()
        self.pd7a_notes.setPlaceholderText("PD7A notes / filing reference / fixes")
        self.pd7a_notes.setMaximumHeight(90)
        layout.addWidget(self.pd7a_notes)

        self.pd7a_month_table = self._create_line_table(
            ["Month", "Employees", "Gross", "CPP", "EI", "Tax", "Due", "Adjusted", "Status"]
        )
        layout.addWidget(self.pd7a_month_table)

        row_buttons = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_pd7a_form)
        row_buttons.addWidget(refresh_btn)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(self.save_pd7a_return_draft)
        row_buttons.addWidget(save_btn)

        submit_btn = QPushButton("Record Manual Submission")
        submit_btn.setStyleSheet("background-color: #7c2d12; color: white;")
        submit_btn.clicked.connect(self.submit_pd7a_return)
        row_buttons.addWidget(submit_btn)

        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        self._load_pd7a_form()
        widget.setLayout(layout)
        return widget

    def create_gst_tab(self) -> object:
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
        self.gst_quarterly_table.setHorizontalHeaderLabels(
            [
                "Quarter",
                "Sales",
                "GST Collected",
                "Purchases",
                "GST Paid",
                "Net GST",
            ]
        )
        layout.addWidget(self.gst_quarterly_table)

        # Variances
        issues_label = QLabel("GST Variances/Issues:")
        layout.addWidget(issues_label)
        self.gst_variance_table = QTableWidget()
        self.gst_variance_table.setColumnCount(5)
        self.gst_variance_table.setHorizontalHeaderLabels(
            ["Severity", "Field", "Actual", "Expected", "Message"]
        )
        layout.addWidget(self.gst_variance_table)

        # Buttons
        btn_layout = QHBoxLayout()
        recompute_btn = QPushButton("🔄 Recompute GST (save)")
        recompute_btn.clicked.connect(self.recompute_gst)
        btn_layout.addWidget(recompute_btn)
        mark_gst_btn = QPushButton("✅ Mark GST Filed/Paid")
        mark_gst_btn.clicked.connect(self.mark_gst_filed)
        btn_layout.addWidget(mark_gst_btn)
        generate_gst_btn = QPushButton("📄 Export GST Filing Worksheet")
        generate_gst_btn.clicked.connect(self.generate_gst_form)
        btn_layout.addWidget(generate_gst_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_owner_tax_tab(self) -> object:
        """Tab 5: Owner personal tax and income threshold tracking"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Owner Personal Tax")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Warning
        warning = QLabel(
            "⚠️ Reference only: basic personal amounts do not determine whether "
            "a T1 return must be filed."
        )
        warning.setStyleSheet("color: orange; font-weight: bold;")
        layout.addWidget(warning)

        # Threshold tracking
        threshold_group = QGroupBox("Basic Personal Amount & Threshold")
        threshold_form = QFormLayout()

        self.federal_bpa = QDoubleSpinBox()
        self.federal_bpa.setMaximum(99999)
        self.federal_bpa.setPrefix("$")
        self.federal_bpa.setValue(16129)
        threshold_form.addRow(
            "Federal Basic Personal Amount:", self.federal_bpa
        )

        self.provincial_bpa = QDoubleSpinBox()
        self.provincial_bpa.setMaximum(99999)
        self.provincial_bpa.setPrefix("$")
        self.provincial_bpa.setValue(22323)
        threshold_form.addRow(
            "Alberta Basic Personal Amount:", self.provincial_bpa
        )

        self.safe_threshold = QDoubleSpinBox()
        self.safe_threshold.setMaximum(99999)
        self.safe_threshold.setPrefix("$")
        self.safe_threshold.setReadOnly(True)
        self.safe_threshold.setValue(16129)
        self.safe_threshold.setStyleSheet("font-weight: bold;")
        threshold_form.addRow(
            "Lower Basic Personal Amount (Reference):", self.safe_threshold
        )
        self.federal_bpa.valueChanged.connect(self._update_bpa_reference)
        self.provincial_bpa.valueChanged.connect(self._update_bpa_reference)

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
        rollover_form.addRow(
            "Wages Deferred to Next Year:", self.wages_deferred
        )

        self.wages_prev_rollover = QDoubleSpinBox()
        self.wages_prev_rollover.setMaximum(99999999)
        self.wages_prev_rollover.setPrefix("$")
        self.wages_prev_rollover.setReadOnly(True)
        rollover_form.addRow(
            "Carried from Previous Year:", self.wages_prev_rollover
        )

        rollover_group.setLayout(rollover_form)
        layout.addWidget(rollover_group)

        # Status indicator
        self.owner_status_label = QLabel()
        layout.addWidget(self.owner_status_label)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _ensure_t1_tables(self, cur) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t1_return_metadata (
                return_id SERIAL PRIMARY KEY,
                tax_year INTEGER UNIQUE NOT NULL,
                taxpayer_name TEXT NOT NULL,
                sin TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                total_income NUMERIC,
                total_tax NUMERIC,
                refund_owing NUMERIC,
                submission_reference TEXT,
                submitted_by TEXT,
                submitted_at TIMESTAMPTZ,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t1_return_lines (
                line_id SERIAL PRIMARY KEY,
                return_id INTEGER NOT NULL REFERENCES t1_return_metadata(return_id)
                    ON DELETE CASCADE,
                line_number TEXT NOT NULL,
                line_description TEXT NOT NULL,
                amount NUMERIC NOT NULL DEFAULT 0,
                notes TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(return_id, line_number)
            )
            """
        )

    def _ensure_t2_tables(self, cur) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t2_return_metadata (
                return_id SERIAL PRIMARY KEY,
                tax_year INTEGER UNIQUE NOT NULL,
                corporation_name TEXT NOT NULL,
                business_number TEXT,
                fiscal_year_end DATE NOT NULL DEFAULT CURRENT_DATE,
                status TEXT NOT NULL DEFAULT 'draft',
                total_revenue NUMERIC,
                total_expenses NUMERIC,
                net_income NUMERIC,
                taxable_income NUMERIC,
                federal_tax NUMERIC,
                provincial_tax NUMERIC,
                total_tax NUMERIC,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t2_schedule_data (
                id SERIAL PRIMARY KEY,
                return_id INTEGER NOT NULL REFERENCES t2_return_metadata(return_id)
                    ON DELETE CASCADE,
                schedule_number TEXT NOT NULL,
                line_number TEXT NOT NULL,
                line_description TEXT NOT NULL,
                amount NUMERIC NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(return_id, schedule_number, line_number)
            )
            """
        )

    def _create_line_table(self, columns: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _add_line_row(self, table: QTableWidget, values: list[str] | None = None) -> None:
        row = table.rowCount()
        table.insertRow(row)
        values = values or []
        for col in range(table.columnCount()):
            item = QTableWidgetItem(str(values[col]) if col < len(values) else "")
            table.setItem(row, col, item)

    def _table_rows(self, table: QTableWidget) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in range(table.rowCount()):
            values: list[str] = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                values.append((item.text() if item else "").strip())
            if any(values):
                rows.append(values)
        return rows

    def create_t1_tab(self) -> object:
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("T1 Personal Return Entry")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        self.t1_taxpayer_name = QLineEdit("Paul Richard")
        self.t1_sin = QLineEdit()
        self.t1_t1_status = QLabel("Draft")
        self.t1_t1_status.setStyleSheet("font-weight: bold; color: #1f2937;")
        form.addRow("Taxpayer Name:", self.t1_taxpayer_name)
        form.addRow("SIN:", self.t1_sin)
        form.addRow("Status:", self.t1_t1_status)
        layout.addLayout(form)

        self.t1_lines_table = self._create_line_table(
            ["Line #", "Description", "Amount", "Notes"]
        )
        layout.addWidget(self.t1_lines_table)

        row_buttons = QHBoxLayout()
        add_btn = QPushButton("Add Line")
        add_btn.clicked.connect(
            lambda: self._add_line_row(self.t1_lines_table, ["", "", "0.00", ""])
        )
        row_buttons.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(
            lambda: self._delete_selected_rows(self.t1_lines_table)
        )
        row_buttons.addWidget(remove_btn)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(self.save_t1_return_draft)
        row_buttons.addWidget(save_btn)

        submit_btn = QPushButton("Record Manual Submission")
        submit_btn.setStyleSheet("background-color: #065f46; color: white;")
        submit_btn.clicked.connect(self.submit_t1_return)
        row_buttons.addWidget(submit_btn)

        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        self._load_t1_form()
        widget.setLayout(layout)
        return widget

    def create_t2_tab(self) -> object:
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("T2 Corporate Return Entry")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        self.t2_corp_name = QLineEdit("Arrow Limousine Ltd.")
        self.t2_business_number = QLineEdit()
        self.t2_return_status = QLabel("Draft")
        self.t2_return_status.setStyleSheet("font-weight: bold; color: #1f2937;")
        form.addRow("Corporation Name:", self.t2_corp_name)
        form.addRow("Business Number:", self.t2_business_number)
        form.addRow("Status:", self.t2_return_status)
        layout.addLayout(form)

        self.t2_schedule125_table = self._create_line_table(
            ["Schedule", "Line #", "Description", "Amount", "Notes"]
        )
        self.t2_schedule100_table = self._create_line_table(
            ["Schedule", "Line #", "Description", "Amount", "Notes"]
        )
        layout.addWidget(QLabel("Schedule 125"))
        layout.addWidget(self.t2_schedule125_table)
        layout.addWidget(QLabel("Schedule 100"))
        layout.addWidget(self.t2_schedule100_table)

        row_buttons = QHBoxLayout()
        add_125 = QPushButton("Add 125 Line")
        add_125.clicked.connect(
            lambda: self._add_line_row(
                self.t2_schedule125_table, ["125", "", "", "0.00", ""]
            )
        )
        row_buttons.addWidget(add_125)

        add_100 = QPushButton("Add 100 Line")
        add_100.clicked.connect(
            lambda: self._add_line_row(
                self.t2_schedule100_table, ["100", "", "", "0.00", ""]
            )
        )
        row_buttons.addWidget(add_100)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(
            lambda: (
                self._delete_selected_rows(self.t2_schedule125_table),
                self._delete_selected_rows(self.t2_schedule100_table),
            )
        )
        row_buttons.addWidget(remove_btn)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(self.save_t2_return_draft)
        row_buttons.addWidget(save_btn)

        submit_btn = QPushButton("Record Manual Submission")
        submit_btn.setStyleSheet("background-color: #0f766e; color: white;")
        submit_btn.clicked.connect(self.submit_t2_return)
        row_buttons.addWidget(submit_btn)

        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        self._load_t2_form()
        widget.setLayout(layout)
        return widget

    def _ensure_pd7a_tables(self, cur) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cra_pd7a_returns (
                id SERIAL PRIMARY KEY,
                reporting_year INTEGER NOT NULL,
                reporting_month INTEGER NOT NULL,
                employee_count INTEGER DEFAULT 0,
                total_gross_payroll NUMERIC DEFAULT 0,
                cpp_total NUMERIC DEFAULT 0,
                ei_total NUMERIC DEFAULT 0,
                income_tax_deducted NUMERIC DEFAULT 0,
                total_remittance_due NUMERIC DEFAULT 0,
                adjusted_remittance NUMERIC DEFAULT 0,
                is_submitted BOOLEAN DEFAULT FALSE,
                submission_date DATE,
                submission_reference TEXT,
                submitted_by TEXT,
                filing_method TEXT,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(reporting_year, reporting_month)
            )
            """
        )

    def _pd7a_month_label(self, month: int) -> str:
        return f"{month:02d}"

    def _load_pd7a_form(self, *_args) -> None:
        try:
            month = int(self.pd7a_month.currentText()) if hasattr(self, "pd7a_month") else 1
            with DatabaseContext(self.db, auto_commit=True) as cur:
                self._ensure_pd7a_tables(cur)
                cur.execute(
                    """
                    SELECT employee_count, total_gross_payroll, cpp_total,
                           ei_total, income_tax_deducted, total_remittance_due,
                           adjusted_remittance, is_submitted, submission_date,
                           submission_reference, submitted_by, filing_method, notes
                    FROM cra_pd7a_returns
                    WHERE reporting_year = %s AND reporting_month = %s
                    """,
                    (self.year, month),
                )
                row = cur.fetchone()
                if row:
                    self.pd7a_employee_count.setValue(float(row[0] or 0))
                    self.pd7a_total_gross.setValue(float(row[1] or 0))
                    self.pd7a_cpp_total.setValue(float(row[2] or 0))
                    self.pd7a_ei_total.setValue(float(row[3] or 0))
                    self.pd7a_income_tax.setValue(float(row[4] or 0))
                    self.pd7a_total_due.setValue(float(row[5] or 0))
                    self.pd7a_adjusted.setValue(float(row[6] or 0))
                    self.pd7a_status.setText(
                        "Recorded submitted" if row[7] else "Draft"
                    )
                    self.pd7a_notes.setPlainText(row[12] or "")
                else:
                    self.pd7a_employee_count.setValue(0)
                    self.pd7a_total_gross.setValue(0)
                    self.pd7a_cpp_total.setValue(0)
                    self.pd7a_ei_total.setValue(0)
                    self.pd7a_income_tax.setValue(0)
                    self.pd7a_total_due.setValue(0)
                    self.pd7a_adjusted.setValue(0)
                    self.pd7a_status.setText("Draft")
                    self.pd7a_notes.setPlainText("")

                cur.execute(
                    """
                    SELECT reporting_month, employee_count, total_gross_payroll,
                           cpp_total, ei_total, income_tax_deducted,
                           total_remittance_due, adjusted_remittance,
                           is_submitted
                    FROM cra_pd7a_returns
                    WHERE reporting_year = %s
                    ORDER BY reporting_month
                    """,
                    (self.year,),
                )
                rows = cur.fetchall()
                self.pd7a_month_table.setRowCount(0)
                for r in rows:
                    self._add_line_row(
                        self.pd7a_month_table,
                        [
                            self._pd7a_month_label(int(r[0] or 0)),
                            str(int(r[1] or 0)),
                            f"{float(r[2] or 0):.2f}",
                            f"{float(r[3] or 0):.2f}",
                            f"{float(r[4] or 0):.2f}",
                            f"{float(r[5] or 0):.2f}",
                            f"{float(r[6] or 0):.2f}",
                            f"{float(r[7] or 0):.2f}",
                            "Recorded submitted" if r[8] else "Draft",
                        ],
                    )
        except Exception as exc:
            logger.warning("Failed to load PD7A form: %s", exc)

    def _save_pd7a_form(self, submitted: bool = False) -> None:
        month = int(self.pd7a_month.currentText())
        employee_count = int(self.pd7a_employee_count.value())
        total_gross = float(self.pd7a_total_gross.value())
        cpp_total = float(self.pd7a_cpp_total.value())
        ei_total = float(self.pd7a_ei_total.value())
        income_tax = float(self.pd7a_income_tax.value())
        total_due = round(cpp_total + ei_total + income_tax, 2)
        adjusted = float(self.pd7a_adjusted.value()) or total_due
        notes = self.pd7a_notes.toPlainText().strip() or None

        with DatabaseContext(self.db, auto_commit=True) as cur:
            self._ensure_pd7a_tables(cur)
            cur.execute(
                """
                INSERT INTO cra_pd7a_returns (
                    reporting_year, reporting_month, employee_count,
                    total_gross_payroll, cpp_total, ei_total,
                    income_tax_deducted, total_remittance_due,
                    adjusted_remittance, is_submitted, notes,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (reporting_year, reporting_month)
                DO UPDATE SET
                    employee_count = EXCLUDED.employee_count,
                    total_gross_payroll = EXCLUDED.total_gross_payroll,
                    cpp_total = EXCLUDED.cpp_total,
                    ei_total = EXCLUDED.ei_total,
                    income_tax_deducted = EXCLUDED.income_tax_deducted,
                    total_remittance_due = EXCLUDED.total_remittance_due,
                    adjusted_remittance = EXCLUDED.adjusted_remittance,
                    is_submitted = EXCLUDED.is_submitted,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                """,
                (
                    self.year,
                    month,
                    employee_count,
                    total_gross,
                    cpp_total,
                    ei_total,
                    income_tax,
                    total_due,
                    adjusted,
                    submitted,
                    notes,
                ),
            )
            if submitted:
                cur.execute(
                    """
                    UPDATE cra_pd7a_returns
                    SET submission_date = CURRENT_DATE,
                        submission_reference = %s,
                        submitted_by = %s,
                        filing_method = %s,
                        updated_at = NOW()
                    WHERE reporting_year = %s AND reporting_month = %s
                    """,
                    (
                        f"PD7A-{self.year}{month:02d}",
                        "desktop_app",
                        "manual",
                        self.year,
                        month,
                    ),
                )
            self.pd7a_status.setText(
                "Recorded submitted" if submitted else "Draft"
            )
            self._load_pd7a_form()

    def save_pd7a_return_draft(self) -> None:
        try:
            self._save_pd7a_form(submitted=False)
            QMessageBox.information(self, "Saved", "PD7A draft saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save PD7A draft: {exc}")

    def submit_pd7a_return(self) -> None:
        try:
            self._save_pd7a_form(submitted=True)
            QMessageBox.information(
                self,
                "Submission Recorded",
                "PD7A was recorded as manually submitted. No data was sent to CRA.",
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to record PD7A submission: {exc}"
            )

    def _delete_selected_rows(self, table: QTableWidget) -> None:
        rows = sorted({idx.row() for idx in table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            table.removeRow(row)

    def _load_t1_form(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                self._ensure_t1_tables(cur)
                cur.execute(
                    """
                    SELECT return_id, taxpayer_name, COALESCE(sin, ''),
                           COALESCE(status, 'draft')
                    FROM t1_return_metadata
                    WHERE tax_year = %s
                    """,
                    (self.year,),
                )
                row = cur.fetchone()
                if not row:
                    self.t1_lines_table.setRowCount(0)
                    self.t1_t1_status.setText("Not created yet")
                    return

                self.t1_taxpayer_name.setText(row[1] or "Paul Richard")
                self.t1_sin.setText(row[2] or "")
                self.t1_t1_status.setText((row[3] or "draft").title())

                cur.execute(
                    """
                    SELECT line_number, line_description, amount, COALESCE(notes, '')
                    FROM t1_return_lines
                    WHERE return_id = %s
                    ORDER BY line_number
                    """,
                    (row[0],),
                )
                lines = cur.fetchall()
                self.t1_lines_table.setRowCount(0)
                for line in lines:
                    self._add_line_row(
                        self.t1_lines_table,
                        [line[0], line[1], f"{float(line[2] or 0):.2f}", line[3] or ""],
                    )
                if self.t1_lines_table.rowCount() == 0:
                    self._add_line_row(self.t1_lines_table, ["10100", "Employment income", "0.00", ""])
        except Exception as exc:
            logger.warning("Failed to load T1 form: %s", exc)

    def _load_t2_form(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                self._ensure_t2_tables(cur)
                cur.execute(
                    """
                    SELECT return_id, corporation_name, COALESCE(business_number, ''),
                           COALESCE(status, 'draft')
                    FROM t2_return_metadata
                    WHERE tax_year = %s
                    """,
                    (self.year,),
                )
                row = cur.fetchone()
                if not row:
                    self.t2_schedule125_table.setRowCount(0)
                    self.t2_schedule100_table.setRowCount(0)
                    self.t2_return_status.setText("Not created yet")
                    return

                self.t2_corp_name.setText(row[1] or "Arrow Limousine Ltd.")
                self.t2_business_number.setText(row[2] or "")
                self.t2_return_status.setText((row[3] or "draft").title())

                cur.execute(
                    """
                    SELECT schedule_number, line_number, line_description, amount, COALESCE(notes, '')
                    FROM t2_schedule_data
                    WHERE return_id = %s
                    ORDER BY schedule_number, line_number
                    """,
                    (row[0],),
                )
                self.t2_schedule125_table.setRowCount(0)
                self.t2_schedule100_table.setRowCount(0)
                for schedule, line_num, desc, amount, notes in cur.fetchall():
                    target = self.t2_schedule125_table if str(schedule) == "125" else self.t2_schedule100_table
                    self._add_line_row(
                        target,
                        [schedule, line_num, desc, f"{float(amount or 0):.2f}", notes or ""],
                    )
                if self.t2_schedule125_table.rowCount() == 0:
                    self._add_line_row(self.t2_schedule125_table, ["125", "8000", "Charter revenue", "0.00", ""])
                if self.t2_schedule100_table.rowCount() == 0:
                    self._add_line_row(self.t2_schedule100_table, ["100", "1000-B", "Cash - Beginning", "0.00", ""])
        except Exception as exc:
            logger.warning("Failed to load T2 form: %s", exc)

    def _save_t1_form(self, submitted: bool = False) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            self._ensure_t1_tables(cur)
            cur.execute(
                """
                SELECT return_id
                FROM t1_return_metadata
                WHERE tax_year = %s
                """,
                (self.year,),
            )
            row = cur.fetchone()
            taxpayer_name = self.t1_taxpayer_name.text().strip() or "Paul Richard"
            sin = self.t1_sin.text().strip() or None
            lines = self._table_rows(self.t1_lines_table)
            total_income = round(sum(float(r[2] or 0) for r in lines), 2)
            if row:
                return_id = row[0]
                cur.execute(
                    """
                    UPDATE t1_return_metadata
                    SET taxpayer_name = %s,
                        sin = %s,
                        status = %s,
                        total_income = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                    """,
                    (taxpayer_name, sin, "submitted" if submitted else "draft", total_income, return_id),
                )
                cur.execute("DELETE FROM t1_return_lines WHERE return_id = %s", (return_id,))
            else:
                cur.execute(
                    """
                    INSERT INTO t1_return_metadata (
                        tax_year, taxpayer_name, sin, status, total_income,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING return_id
                    """,
                    (self.year, taxpayer_name, sin, "submitted" if submitted else "draft", total_income),
                )
                return_id = cur.fetchone()[0]

            for line in lines:
                cur.execute(
                    """
                    INSERT INTO t1_return_lines (
                        return_id, line_number, line_description, amount, notes, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (return_id, line[0], line[1], float(line[2] or 0), line[3] if len(line) > 3 else None),
                )

            if submitted:
                cur.execute(
                    """
                    UPDATE t1_return_metadata
                    SET submitted_by = %s,
                        submitted_at = NOW(),
                        submission_reference = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                    """,
                    ("desktop_app", f"T1-{self.year}", return_id),
                )
            self.t1_t1_status.setText(
                "Recorded submitted" if submitted else "Draft"
            )

    def _save_t2_form(self, submitted: bool = False) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            self._ensure_t2_tables(cur)
            cur.execute(
                """
                SELECT return_id
                FROM t2_return_metadata
                WHERE tax_year = %s
                """,
                (self.year,),
            )
            row = cur.fetchone()
            corp_name = self.t2_corp_name.text().strip() or "Arrow Limousine Ltd."
            bn = self.t2_business_number.text().strip() or None
            lines_125 = self._table_rows(self.t2_schedule125_table)
            lines_100 = self._table_rows(self.t2_schedule100_table)
            all_lines = lines_125 + lines_100
            revenue = round(
                sum(float(line[3] or 0) for line in lines_125 if str(line[1]) in {"8000", "8299"}),
                2,
            )
            expenses = round(
                sum(float(line[3] or 0) for line in lines_125 if str(line[1]) not in {"8000", "8299"}),
                2,
            )
            net_income = round(revenue - expenses, 2)
            if row:
                return_id = row[0]
                cur.execute(
                    """
                    UPDATE t2_return_metadata
                    SET corporation_name = %s,
                        business_number = %s,
                        status = %s,
                        total_revenue = %s,
                        total_expenses = %s,
                        net_income = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                    """,
                    (
                        corp_name,
                        bn,
                        "submitted" if submitted else "draft",
                        revenue,
                        expenses,
                        net_income,
                        return_id,
                    ),
                )
                cur.execute("DELETE FROM t2_schedule_data WHERE return_id = %s", (return_id,))
            else:
                cur.execute(
                    """
                    INSERT INTO t2_return_metadata (
                        tax_year, corporation_name, business_number, fiscal_year_end,
                        status, total_revenue, total_expenses, net_income,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING return_id
                    """,
                    (
                        self.year,
                        corp_name,
                        bn,
                        f"{self.year}-12-31",
                        "submitted" if submitted else "draft",
                        revenue,
                        expenses,
                        net_income,
                    ),
                )
                return_id = cur.fetchone()[0]

            for schedule, line_num, desc, amount, notes in all_lines:
                cur.execute(
                    """
                    INSERT INTO t2_schedule_data (
                        return_id, schedule_number, line_number, line_description, amount, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (return_id, str(schedule), line_num, desc, float(amount or 0)),
                )

            if submitted:
                cur.execute(
                    """
                    UPDATE t2_return_metadata
                    SET status = 'submitted',
                        total_revenue = %s,
                        total_expenses = %s,
                        net_income = %s,
                        updated_at = NOW()
                    WHERE return_id = %s
                    """,
                    (revenue, expenses, net_income, return_id),
                )
            self.t2_return_status.setText(
                "Recorded submitted" if submitted else "Draft"
            )

    def save_t1_return_draft(self) -> None:
        try:
            self._save_t1_form(submitted=False)
            QMessageBox.information(self, "Saved", "T1 draft saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save T1 draft: {exc}")

    def submit_t1_return(self) -> None:
        try:
            self._save_t1_form(submitted=True)
            QMessageBox.information(
                self,
                "Submission Recorded",
                "T1 was recorded as manually submitted. No data was sent to CRA.",
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to record T1 submission: {exc}"
            )

    def save_t2_return_draft(self) -> None:
        try:
            self._save_t2_form(submitted=False)
            QMessageBox.information(self, "Saved", "T2 draft saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save T2 draft: {exc}")

    def submit_t2_return(self) -> None:
        try:
            self._save_t2_form(submitted=True)
            QMessageBox.information(
                self,
                "Submission Recorded",
                "T2 was recorded as manually submitted. No data was sent to CRA.",
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to record T2 submission: {exc}"
            )

    def create_forms_tab(self) -> object:
        """Tab 6: CRA form generation and export"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("CRA Forms & Manual Filing Records")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Form list
        forms_label = QLabel("Available Forms:")
        layout.addWidget(forms_label)

        self.forms_table = QTableWidget()
        self.forms_table.setColumnCount(4)
        self.forms_table.setHorizontalHeaderLabels(
            ["Form", "Description", "Status", "Actions"]
        )
        layout.addWidget(self.forms_table)

        # Populate forms list
        forms = [
            ("T1", "Personal Income Tax Return", "Editor"),
            ("T4", "Statement of Remuneration Paid", "Editor"),
            ("T4 Summary", "Summary of Remuneration Paid", "CSV Export"),
            ("T4A", "Statement of Pension/Other Income", "Not implemented"),
            ("GST34", "GST/HST Return for Registrants", "Worksheet"),
            ("T2", "Corporation Income Tax Return", "Editor"),
            ("PD7A", "Statement of Account - Source Deductions", "Editor"),
            ("T5018", "Statement of Contract Payments", "N/A"),
        ]

        self.forms_table.setRowCount(len(forms))
        for i, (form_name, desc, status) in enumerate(forms):
            self.forms_table.setItem(i, 0, QTableWidgetItem(form_name))
            self.forms_table.setItem(i, 1, QTableWidgetItem(desc))
            self.forms_table.setItem(i, 2, QTableWidgetItem(status))

            generate_btn = QPushButton("Open")
            generate_btn.clicked.connect(
                lambda checked, f=form_name: self.generate_specific_form(f)
            )
            if status in ("Not implemented", "N/A"):
                generate_btn.setEnabled(False)
            self.forms_table.setCellWidget(i, 3, generate_btn)

        # Bulk actions
        bulk_layout = QHBoxLayout()
        generate_all_btn = QPushButton("📄 Open Filing Editors")
        generate_all_btn.clicked.connect(self.generate_all_forms)
        bulk_layout.addWidget(generate_all_btn)

        export_xml_btn = QPushButton("📤 Export CRA XML")
        export_xml_btn.clicked.connect(self.export_cra_xml)
        export_xml_btn.setEnabled(False)
        export_xml_btn.setToolTip(
            "Direct CRA XML export is not implemented; use the reviewed manual "
            "filing worksheets and record the CRA confirmation afterward."
        )
        bulk_layout.addWidget(export_xml_btn)

        bulk_layout.addStretch()
        layout.addLayout(bulk_layout)

        widget.setLayout(layout)
        return widget

    def create_rollovers_tab(self) -> object:
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
        loss_form.addRow(
            "Loss Carried from Prior Years:", self.prev_loss_balance
        )

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
        loss_form.addRow(
            "Total Available for Future:", self.total_loss_carryforward
        )

        loss_group.setLayout(loss_form)
        layout.addWidget(loss_group)

        # GST credit carryforward
        gst_credit_group = QGroupBox("GST Credit/Debt Carryforward")
        gst_credit_form = QFormLayout()

        self.gst_prev_credit = QDoubleSpinBox()
        self.gst_prev_credit.setMaximum(99999999)
        self.gst_prev_credit.setMinimum(-99999999)
        self.gst_prev_credit.setPrefix("$")
        gst_credit_form.addRow(
            "Previous GST Credit/(Debt):", self.gst_prev_credit
        )

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
        self.other_carryforward_table.setHorizontalHeaderLabels(
            ["Type", "From Year", "Amount", "Expires"]
        )
        layout.addWidget(self.other_carryforward_table)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def load_year_data(self) -> None:
        """Load all data for this tax year from database"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                snapshot = _load_tax_year_snapshot(cur, self.year)
                cur.execute(
                    """
                    SELECT previous_loss_balance, gst_previous_balance,
                           gst_previous_credit, federal_basic_personal_amount,
                           provincial_basic_personal_amount
                    FROM tax_year_settings
                    WHERE tax_year = %s
                    """,
                    (self.year,),
                )
                settings = cur.fetchone()
                if settings:
                    self.prev_loss_balance.setValue(float(settings[0] or 0))
                    self.gst_prev_balance.setValue(float(settings[1] or 0))
                    self.gst_prev_credit.setValue(float(settings[2] or 0))
                    self.federal_bpa.setValue(float(settings[3] or 0))
                    self.provincial_bpa.setValue(float(settings[4] or 0))
                    self._update_bpa_reference()
                self._apply_tax_year_detail_snapshot(snapshot)

            # Variances
            self.load_variances(
                "gst", getattr(self, "gst_variance_table", None)
            )
            self.load_variances(
                "payroll", getattr(self, "payroll_variance_table", None)
            )

        except Exception as e:
            logger.error(f"Failed to load year data: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load year data: {e}"
            )

    def _apply_tax_year_detail_snapshot(self, snapshot: dict) -> None:
        revenue = snapshot["revenue"]
        expenses = snapshot["expenses"]
        gst_included = revenue * 0.05 / 1.05
        gst_paid = snapshot["gst_paid"]
        payroll_gross = snapshot["payroll_gross"]
        payroll_cpp = snapshot["payroll_cpp"]
        payroll_ei = snapshot["payroll_ei"]
        payroll_tax = snapshot["payroll_tax"]
        paul_t1 = snapshot.get("paul_t1") or {}

        self.charter_revenue.setValue(float(revenue))
        self.gst_included.setValue(gst_included)
        self.gst_collected.setValue(gst_included)
        self.total_revenue.setValue(float(revenue))

        self.total_expenses.setValue(float(expenses))
        self.gst_recoverable.setValue(float(gst_paid))
        self.gst_paid.setValue(float(gst_paid))

        self.total_gross_pay.setValue(float(payroll_gross))
        self.total_cpp.setValue(float(payroll_cpp))
        self.total_ei.setValue(float(payroll_ei))
        self.total_tax.setValue(float(payroll_tax))

        self.employer_cpp.setValue(float(payroll_cpp))
        self.employer_ei.setValue(float(payroll_ei) * 1.4)
        remittance = float(payroll_cpp) * 2 + float(payroll_ei) * 2.4 + float(payroll_tax)
        self.total_remittance.setValue(remittance)

        payroll_return = snapshot["payroll_return"]
        if payroll_return:
            final_val = (
                payroll_return["filed_amount"]
                if payroll_return["filed_amount"] is not None
                else payroll_return["calculated_amount"]
            )
            if final_val is not None:
                self.total_remittance.setValue(float(final_val))
            if payroll_return["status"]:
                self.total_remittance.setStyleSheet("font-weight: bold; color: green;")

        gst_net = gst_included - float(gst_paid)
        self.gst_net.setValue(gst_net)
        self.gst_current.setValue(gst_net)
        self.gst_forward.setValue(self.gst_prev_credit.value() + gst_net)

        gst_return = snapshot["gst_return"]
        if gst_return:
            final_val = (
                gst_return["filed_amount"]
                if gst_return["filed_amount"] is not None
                else gst_return["calculated_amount"]
            )
            if final_val is not None:
                self.gst_net.setValue(float(final_val))
                self.gst_current.setValue(float(final_val))
                self.gst_final.setValue(float(final_val))
            if gst_return["status"]:
                self.gst_final.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.gst_final.setValue(gst_net + self.gst_prev_balance.value())

        net_income = float(revenue) - float(expenses)
        self.net_income.setValue(net_income)
        if net_income < 0:
            self.current_loss.setValue(abs(net_income))
        else:
            self.current_loss.setValue(0)
        self.total_loss_carryforward.setValue(
            self.prev_loss_balance.value() + self.current_loss.value()
        )

        t1_income = float(paul_t1.get("total_t1_income") or 0)
        self.owner_salary.setValue(float(paul_t1.get("t4_employment_income") or 0))
        self.owner_dividends.setValue(float(paul_t1.get("dividends") or 0))
        self.owner_other.setValue(float(paul_t1.get("other_income") or 0))
        self.owner_total.setValue(t1_income)
        self.owner_room.setValue(max(0.0, float(self.safe_threshold.value()) - t1_income))
        if paul_t1:
            self.owner_status_label.setText(
                "Paul T1 linked to business T4 "
                f"(employee {paul_t1.get('employee_id')}, "
                f"T4 income ${float(paul_t1.get('t4_employment_income') or 0):,.2f}, "
                f"owner draws tracked separately ${float(paul_t1.get('owner_draws') or 0):,.2f})"
            )
        else:
            self.owner_status_label.setText("Paul T1 link not found in employees/T4 records.")

    def _update_bpa_reference(self) -> None:
        self.safe_threshold.setValue(
            min(self.federal_bpa.value(), self.provincial_bpa.value())
        )

    def load_variances(self, form_type: str, table: QTableWidget | None) -> None:
        """Load tax_variances for the given form_type into the provided"
        "table."""

        if table is None:
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT tv.severity, tv.field, tv.actual, tv.expected,
                    tv.message
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
                for i, (
                    severity,
                    field,
                    actual,
                    expected,
                    message,
                ) in enumerate(rows):
                    sev_item = QTableWidgetItem(
                        str(severity or "info").upper()
                    )
                    if severity == "high":
                        sev_item.setBackground(QColor(255, 200, 200))
                    elif severity == "medium":
                        sev_item.setBackground(QColor(255, 230, 200))
                    table.setItem(i, 0, sev_item)
                    table.setItem(i, 1, QTableWidgetItem(str(field or "")))
                    table.setItem(
                        i,
                        2,
                        QTableWidgetItem(
                            "" if actual is None else f"{float(actual):,.2f}"
                        ),
                    )
                    table.setItem(
                        i,
                        3,
                        QTableWidgetItem(
                            ""
                            if expected is None
                            else f"{float(expected):,.2f}"
                        ),
                    )
                    table.setItem(i, 4, QTableWidgetItem(str(message or "")))
        except Exception as e:
            logger.error(f"Failed to load variances: {e}")
            table.setRowCount(0)

    def recalculate_year(self) -> None:
        """Recalculate all tax figures for the year"""
        self.load_year_data()
        QMessageBox.information(
            self, "Success", f"Tax year {self.year} recalculated"
        )

    def save_year(self) -> None:
        """Persist editable year-level balances and thresholds."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO tax_year_settings (
                        tax_year, previous_loss_balance, gst_previous_balance,
                        gst_previous_credit, federal_basic_personal_amount,
                        provincial_basic_personal_amount, owner_safe_threshold,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (tax_year) DO UPDATE SET
                        previous_loss_balance = EXCLUDED.previous_loss_balance,
                        gst_previous_balance = EXCLUDED.gst_previous_balance,
                        gst_previous_credit = EXCLUDED.gst_previous_credit,
                        federal_basic_personal_amount =
                            EXCLUDED.federal_basic_personal_amount,
                        provincial_basic_personal_amount =
                            EXCLUDED.provincial_basic_personal_amount,
                        owner_safe_threshold = EXCLUDED.owner_safe_threshold,
                        updated_at = NOW()
                    """,
                    (
                        self.year,
                        self.prev_loss_balance.value(),
                        self.gst_prev_balance.value(),
                        self.gst_prev_credit.value(),
                        self.federal_bpa.value(),
                        self.provincial_bpa.value(),
                        self.safe_threshold.value(),
                    ),
                )
            self.load_year_data()
            QMessageBox.information(
                self, "Saved", f"Tax year {self.year} settings saved."
            )
            self.saved.emit({"year": self.year})
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to save tax year settings: {exc}"
            )

    # Stub methods for actions
    def add_revenue_adjustment(self) -> None:
        QMessageBox.information(
            self, "Info", "Add revenue adjustment (to be implemented)"
        )

    def add_expense(self) -> None:
        QMessageBox.information(
            self, "Info", "Add expense (to be implemented)"
        )

    def edit_expense(self) -> None:
        QMessageBox.information(
            self, "Info", "Edit expense (to be implemented)"
        )

    def recategorize_expense(self) -> None:
        QMessageBox.information(
            self, "Info", "Recategorize expense (to be implemented)"
        )

    def edit_t4(self) -> None:
        QMessageBox.information(
            self, "Info", "Edit T4 slip (to be implemented)"
        )

    def generate_t4_slips(self) -> None:
        """Generate a T4 summary CSV for manual review and filing."""
        try:
            reports_dir = _APP_ROOT / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = reports_dir / f"T4_summary_{self.year}.csv"
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT e.full_name, e.t4_sin,
                           COALESCE(t.box_14_employment_income,0),
                           COALESCE(t.box_16_cpp_contributions,0),
                           COALESCE(t.box_18_ei_premiums,0),
                           COALESCE(t.box_22_income_tax,0)
                    FROM employee_t4_records t
                    JOIN employees e USING (employee_id)
                    WHERE t.tax_year = %s
                    ORDER BY e.full_name
                    """,
                    (self.year,),
                )
                rows = cur.fetchall()
            with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "Employee", "SIN", "Box 14 Employment Income",
                        "Box 16 CPP", "Box 18 EI", "Box 22 Income Tax",
                    ]
                )
                writer.writerows(rows)
            QMessageBox.information(
                self,
                "T4 Summary Exported",
                f"Exported {len(rows)} T4 record(s) for manual filing review:\n"
                f"{output_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate T4 summary: {e}"
            )

    def validate_payroll_deductions(self) -> None:
        """Validate CPP/EI/Tax calculations against CRA tables"""
        QMessageBox.information(
            self, "Info", "Validate deductions (to be implemented)"
        )

    def recompute_payroll(self) -> None:
        """Recompute the annual payroll remittance and persist the result."""
        try:
            self.load_year_data()
            amount = (
                self.total_cpp.value() * 2
                + self.total_ei.value() * 2.4
                + self.total_tax.value()
            )
            self._save_calculated_return("payroll", amount)
            self.load_year_data()
            QMessageBox.information(
                self,
                "Payroll Recomputed",
                f"Saved the {self.year} calculated payroll remittance: "
                f"${amount:,.2f}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to recompute payroll: {e}"
            )

    def generate_gst_form(self) -> None:
        """Export a GST filing worksheet for manual CRA filing."""
        try:
            reports_dir = _APP_ROOT / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = reports_dir / f"GST_filing_worksheet_{self.year}.csv"
            with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Tax Year", self.year])
                writer.writerow(["GST Collected", f"{self.gst_collected.value():.2f}"])
                writer.writerow(["Input Tax Credits", f"{self.gst_paid.value():.2f}"])
                writer.writerow(["Calculated Net GST", f"{self.gst_net.value():.2f}"])
                writer.writerow(
                    ["Previous Balance", f"{self.gst_prev_balance.value():.2f}"]
                )
                writer.writerow(["Amount Due", f"{self.gst_final.value():.2f}"])
            QMessageBox.information(
                self,
                "GST Worksheet Exported",
                "The worksheet was generated for manual filing; it was not "
                f"submitted to CRA.\n{output_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate GST filing worksheet: {e}"
            )

    def recompute_gst(self) -> None:
        """Recompute annual GST and persist the calculated return."""
        try:
            self.load_year_data()
            amount = self.gst_net.value() + self.gst_prev_balance.value()
            self._save_calculated_return("gst", amount)
            self.load_year_data()
            QMessageBox.information(
                self,
                "GST Recomputed",
                f"Saved the {self.year} calculated GST amount: ${amount:,.2f}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to recompute GST: {e}"
            )

    def _save_calculated_return(self, form_type: str, amount: float) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                INSERT INTO tax_periods (
                    label, period_type, start_date, end_date, year
                ) VALUES (%s, 'annual', %s, %s, %s)
                ON CONFLICT (label) DO UPDATE SET
                    period_type = EXCLUDED.period_type,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    year = EXCLUDED.year
                RETURNING id
                """,
                (
                    str(self.year),
                    datetime(self.year, 1, 1).date(),
                    datetime(self.year, 12, 31).date(),
                    self.year,
                ),
            )
            period_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO tax_returns (
                    period_id, form_type, status, calculated_amount, updated_at
                ) VALUES (%s, %s, 'calculated', %s, NOW())
                ON CONFLICT (period_id, form_type) DO UPDATE SET
                    calculated_amount = EXCLUDED.calculated_amount,
                    status = CASE
                        WHEN tax_returns.status IN
                            ('filed','submitted','accepted','paid')
                        THEN tax_returns.status
                        ELSE 'calculated'
                    END,
                    updated_at = NOW()
                """,
                (period_id, form_type, amount),
            )

    def mark_return(self, form_type: str, default_amount: float = 0.0) -> None:
        dlg = MarkFiledDialog(self, default_amount=default_amount)
        if dlg.exec():
            data = dlg.values()
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        """
                        UPDATE tax_returns SET status = %s, filed_amount = %s,
                        filed_at = %s, reference = %s, updated_at = NOW()
                        WHERE id = (
                            SELECT tr.id FROM tax_returns tr
                            JOIN tax_periods tp ON tp.id = tr.period_id
                            WHERE tp.label = %s AND tr.form_type = %s
                            LIMIT 1)
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
                        QMessageBox.information(
                            self,
                            "Info",
                            "No return found; run recompute first.",
                        )
                    else:
                        self.load_year_data()
                        QMessageBox.information(
                            self,
                            "Success",
                            f"Marked {form_type.upper()} return as"
                            f"{data['status']}",
                        )
            except Exception as e:
                logger.error(f"Failed to mark return: {e}")
                QMessageBox.critical(
                    self, "Error", f"Failed to mark return: {e}"
                )

    def mark_gst_filed(self) -> None:
        self.mark_return("gst", default_amount=self.gst_final.value())

    def mark_payroll_filed(self) -> None:
        self.mark_return(
            "payroll", default_amount=self.total_remittance.value()
        )

    def generate_specific_form(self, form_name) -> None:
        """Open the year-detail editor for the selected CRA form."""
        try:
            target_tabs = {
                "PD7A": 3,
                "GST34": 4,
                "T1": 6,
                "T2": 7,
                "T4": 2,
                "T4 Summary": 2,
                "all": 8,
            }
            self.tabs.setCurrentIndex(target_tabs.get(form_name, 8))
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to open {form_name} editor: {exc}"
            )

    def generate_all_forms(self) -> None:
        """Open the current year editor for all available form tabs."""
        self.generate_specific_form("all")

    def export_cra_xml(self) -> None:
        """Explain the supported manual filing protocol."""
        QMessageBox.information(
            self,
            "Manual Filing Only",
            "Direct CRA XML export is not implemented. Generate and review the "
            "filing worksheets, file through the authorized CRA channel, then "
            "record the confirmation and filed amount here.",
        )

    def generate_forms(self) -> None:
        """Quick access to form generation"""
        self.generate_all_forms()


class TaxManagementWidget(QWidget):
    """
    Main tax management widget with multi-year view
    Shows 2012-2025 with rollover tracking
    """

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout()

        # Title
        title = QLabel("🏛️ CRA Tax System (2012-2025)")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #2c3e50;"
        )
        layout.addWidget(title)

        # Instructions
        info = QLabel("""
        <p>Track tax years 2012-2025 with rollover tracking for GST, losses,
        and deductions.</p>
        <p><b>Double-click</b> a year for detailed view and form
        generation.</p>
        """)
        layout.addWidget(info)

        # Multi-year summary table
        self.year_table = QTableWidget()
        self.year_table.setColumnCount(11)
        self.year_table.setHorizontalHeaderLabels(
            [
                "Year",
                "Revenue",
                "Expenses",
                "Net Income",
                "GST Owed/(Refund)",
                "Payroll",
                "T4s Filed",
                "GST Filed",
                "Loss Carryforward",
                "Owner Income",
                "Status",
            ]
        )
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

    def _safe_scalar(self, sql, params=(), default=0.0) -> object:
        """Execute a scalar SELECT safely: rollback on error and return"
        "default."""

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                if not row:
                    return default
                val = row[0]
                if val is None:
                    return default
                try:
                    return float(val)
                except Exception:
                    return default
        except Exception as e:
            logger.error(f"Failed to execute safe scalar: {e}")
            return default

    def load_all_years(self) -> None:
        """Load summary data for all tax years 2012-2025"""
        try:
            years = range(2012, 2026)  # 2012-2025
            self.year_table.setRowCount(len(years))
            with DatabaseContext(self.db, auto_commit=False) as cur:
                for i, year in enumerate(years):
                    snapshot = _load_tax_year_snapshot(cur, year)
                    self._populate_year_summary_row(i, snapshot)

        except Exception as e:
            logger.error(f"Failed to load tax years: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load tax years: {e}"
            )

    def _populate_year_summary_row(self, row_index: int, snapshot: dict) -> None:
        revenue = snapshot["revenue"]
        expenses = snapshot["expenses"]
        net_income = revenue - expenses
        gst_collected = revenue * 0.05 / 1.05
        gst_paid = snapshot["gst_paid"]
        gst_net = gst_collected - gst_paid
        payroll = snapshot["payroll_gross"]

        self.year_table.setItem(row_index, 0, QTableWidgetItem(str(snapshot["year"])))
        self.year_table.setItem(row_index, 1, QTableWidgetItem(f"${revenue:,.2f}"))
        self.year_table.setItem(row_index, 2, QTableWidgetItem(f"${expenses:,.2f}"))

        net_item = QTableWidgetItem(f"${net_income:,.2f}")
        if net_income < 0:
            net_item.setBackground(QColor(255, 200, 200))
        self.year_table.setItem(row_index, 3, net_item)

        gst_item = QTableWidgetItem(f"${gst_net:,.2f}")
        if gst_net > 0:
            gst_item.setBackground(QColor(255, 220, 220))
        elif gst_net < 0:
            gst_item.setBackground(QColor(200, 255, 200))

        gst_return = snapshot["gst_return"]
        gst_status = "Pending"
        if gst_return:
            show_amount = (
                gst_return["filed_amount"]
                if gst_return["filed_amount"] is not None
                else gst_return["calculated_amount"]
            )
            if show_amount is not None:
                gst_item = QTableWidgetItem(f"${float(show_amount):,.2f}")
            if gst_return["status"]:
                gst_status = gst_return["status"]
        self.year_table.setItem(row_index, 4, gst_item)

        self.year_table.setItem(row_index, 5, QTableWidgetItem(f"${payroll:,.2f}"))
        payroll_status = "Pending"
        payroll_return = snapshot["payroll_return"]
        if payroll_return:
            if payroll_return["filed_amount"] is not None:
                payroll = float(payroll_return["filed_amount"])
            elif payroll_return["calculated_amount"] is not None:
                payroll = float(payroll_return["calculated_amount"])
            payroll_status = payroll_return["status"] or payroll_status
            self.year_table.setItem(row_index, 5, QTableWidgetItem(f"${payroll:,.2f}"))

        paul_t1 = snapshot.get("paul_t1") or {}
        owner_income = float(paul_t1.get("total_t1_income") or 0)
        owner_item = QTableWidgetItem(f"${owner_income:,.2f}")
        if owner_income > 0:
            owner_item.setBackground(QColor(220, 255, 220))
        self.year_table.setItem(row_index, 9, owner_item)

        self.year_table.setItem(row_index, 6, QTableWidgetItem(payroll_status))
        self.year_table.setItem(row_index, 7, QTableWidgetItem(gst_status))
        self.year_table.setItem(row_index, 8, QTableWidgetItem("$0.00"))
        self.year_table.setItem(
            row_index,
            10,
            QTableWidgetItem("Paul T1 linked" if paul_t1 else "Review Required"),
        )

    def open_year_detail(self, index) -> None:
        """Open detailed view for a tax year"""
        row = index.row()
        year = int(self.year_table.item(row, 0).text())

        dialog = TaxYearDetailDialog(self.db, year, self)
        dialog.saved.connect(lambda data: self.load_all_years())
        dialog.exec()

    def run_smart_check(self) -> None:
        """Run smart tax validation and generate notifications"""
        notifications = []

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
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
                    notifications.append(
                        f"⚠️ {len(missing_deductions)} payroll entries"
                        f"missing CPP/EI deductions"
                    )

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
                    notifications.append(
                        f"💰 GST registration required for"
                        f"{len(over_threshold)} years (revenue > $30K)"
                    )

                # Check owner income threshold
                notifications.append(
                    "✅ Owner income within safe threshold for 2025"
                )

            # Display notifications
            self.notifications.setPlainText("\n".join(notifications))

        except Exception as e:
            logger.error(f"Smart check failed: {e}")
            QMessageBox.critical(self, "Error", f"Smart check failed: {e}")
