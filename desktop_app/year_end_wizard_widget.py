"""
Year-End Guided Wizard – Arrow Limousine & Sedan Services Ltd

H&R Block-style step-by-step year-end workflow:

  Step 1  Company Information          – verify legal name, BN, address for the year
  Step 2  Year-End Audit Checks        – run all hard-blocker and advisory checks
  Step 3  T4 / Payroll Readiness       – T4 counts, T4 slips review, PD7A summary
  Step 4  T2 Corporate Return Prep     – schedule 125/1 review, limousine defaults
  Step 5  Accountant Bundle            – one-click export (GL + Trial Balance + T4 summary
                                          + remittances + all reports) as print bundle
  Step 6  Archive & Notes              – close the year, write comments/solutions,
                                          store year_end_archive record

Designed to call existing widgets as embedded panes where possible, so the
wizard is a navigator/guide rather than a reimplementation.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

STEPS = [
    ("1", "🏢 Company Info",          "Verify legal name, BN, and address for this tax year"),
    ("2", "✅ Audit Checks",           "Run all GL, payroll, bank and CRA readiness checks"),
    ("3", "📄 T4 / Payroll",           "Review T4 slips, PD7A remittances, payroll totals"),
    ("4", "📋 T2 Corp Return",         "Review Schedule 125/1 with limousine defaults"),
    ("5", "📦 Accountant Bundle",      "One-click export: GL, Trial Balance, T4, remittances"),
    ("6", "🗂️  Archive & Notes",        "Close year, add notes, log solutions for next year"),
]

LIMO_T2_DEFAULTS = {
    "Industry":               "485310 – Limousine/Taxi service (NAICS)",
    "Revenue account":        "4100 – Charter Revenue",
    "Cost of services":       "5100 – Driver Pay, 5200 – Vehicle Operating",
    "Capital assets (CCA)":   "Class 10 (30%) – Automobiles/Limousines",
    "Business meals (50%)":   "Deductible at 50% per ITA s.67.1",
    "Small business deduction":"Eligible – active income from service business",
    "GST reporting":           "Monthly (>$1.5M revenue) or Quarterly",
    "WCB":                    "Industry code 6611 – Taxi & Limousine",
    "EHT":                    "Not applicable (AB – no provincial payroll tax)",
}

REPORT_LABELS = [
    ("General Ledger",     "Full GL for the fiscal year"),
    ("Trial Balance",      "Closing balances as at Dec 31"),
    ("Income Statement",   "Revenue vs expenses by GL category"),
    ("Balance Sheet",      "Assets / Liabilities / Equity"),
    ("T4 Summary",         "Aggregate T4 box totals for all employees"),
    ("PD7A Remittances",   "Month-by-month CRA remittance history"),
    ("GST Summary",        "GST collected vs ITC claimed"),
    ("Payroll Ledger",     "Per-employee pay detail for the year"),
    ("WCB Annual",         "Workers' Comp premiums and assessment"),
]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _h(text: str, size: int = 13, color: str = "#1e40af") -> QLabel:
    """Styled heading label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: {size}pt; font-weight: bold; color: {color};"
        " padding-bottom: 4px;"
    )
    return lbl


def _info_box(text: str, bg: str = "#dbeafe") -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"background:{bg}; padding:10px; border-radius:5px;"
        " margin-bottom:8px;"
    )
    return lbl


def _separator() -> QLabel:
    sep = QLabel()
    sep.setFixedHeight(2)
    sep.setStyleSheet("background:#bdc3c7; margin:6px 0;")
    return sep


# ──────────────────────────────────────────────────────────────────────────────
# Step widgets
# ──────────────────────────────────────────────────────────────────────────────

class _CompanyInfoStep(QWidget):
    """Step 1 – Company information verification."""

    changed = pyqtSignal()

    # Ordered list of (field_name, display_label, placeholder)
    FIELDS = [
        ("legal_name",            "Legal Name",              "Arrow Limousine & Sedan Services Ltd"),
        ("trade_name",            "Trade / DBA Name",        "Arrow Limousine"),
        ("business_number",       "Business Number (BN)",    "861556827"),
        ("payroll_account",       "Payroll Account",         "861556827RP0001"),
        ("gst_account",           "GST Account",             "861556827RT0001"),
        ("address_line1",         "Street Address",          "3-6841 52 Ave"),
        ("address_city",          "City",                    "Red Deer"),
        ("address_province",      "Province",                "AB"),
        ("address_postal",        "Postal Code",             "T4P 2Z1"),
        ("address_country",       "Country",                 "Canada"),
        ("phone",                 "Phone",                   ""),
        ("email",                 "Email",                   ""),
        ("fiscal_year_end",       "Fiscal Year End",         "December 31"),
        ("incorporation_province","Incorporation Province",  "AB"),
        ("naics_code",            "NAICS Code",              "485310"),
        ("wcb_account",           "WCB Account Number",      ""),
    ]

    def __init__(self, db, tax_year: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.tax_year = tax_year
        self._inputs: dict[str, QLineEdit] = {}
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.addWidget(_h("Company Information Verification"))
        outer.addWidget(_info_box(
            "⚠️  Verify ALL fields every year – the CRA uses the address on file "
            "for correspondence. The address and any contact details can change "
            "year to year. Correct any values and click 'Save Company Info'."
        ))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        for field_name, label, placeholder in self.FIELDS:
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.textChanged.connect(self.changed.emit)
            self._inputs[field_name] = inp
            form.addRow(f"{label}:", inp)

        grp = QGroupBox("CRA-Registered Company Details")
        grp.setLayout(form)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grp)
        outer.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Company Info")
        self.save_btn.setStyleSheet(
            "background:#1d4ed8; color:white; font-weight:bold; padding:6px 20px;"
        )
        self.save_btn.clicked.connect(self._save)
        self.verify_btn = QPushButton("✅ Mark as Verified for This Year")
        self.verify_btn.clicked.connect(self._verify)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.verify_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("color:#16a34a; font-weight:bold;")
        outer.addWidget(self.status_lbl)

    def _load(self):
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT field_name, field_value FROM company_info",
                )
                for field_name, value in cur.fetchall():
                    if field_name in self._inputs:
                        self._inputs[field_name].setText(value or "")
        except Exception as exc:
            self.status_lbl.setText(f"Load error: {exc}")
            self.status_lbl.setStyleSheet("color:#dc2626;")

    def _save(self):
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                for field_name, inp in self._inputs.items():
                    cur.execute(
                        """
                        INSERT INTO company_info (field_name, field_value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (field_name) DO UPDATE
                          SET field_value = EXCLUDED.field_value,
                              updated_at  = NOW()
                        """,
                        (field_name, inp.text().strip()),
                    )
            self.status_lbl.setText("✅ Saved successfully.")
            self.status_lbl.setStyleSheet("color:#16a34a; font-weight:bold;")
        except Exception as exc:
            self.status_lbl.setText(f"❌ Save error: {exc}")
            self.status_lbl.setStyleSheet("color:#dc2626;")

    def _verify(self):
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE company_info SET last_verified_year = %s, updated_at = NOW()",
                    (self.tax_year,),
                )
            self.status_lbl.setText(
                f"✅ All fields marked verified for {self.tax_year}."
            )
            self.status_lbl.setStyleSheet("color:#16a34a; font-weight:bold;")
        except Exception as exc:
            self.status_lbl.setText(f"❌ Verify error: {exc}")
            self.status_lbl.setStyleSheet("color:#dc2626;")

    def get_company_dict(self) -> dict[str, str]:
        return {k: v.text().strip() for k, v in self._inputs.items()}


class _AuditChecksStep(QWidget):
    """Step 2 – Year-end audit / readiness checks."""

    def __init__(self, db, tax_year: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.tax_year = tax_year
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(_h("Year-End Audit & Readiness Checks"))
        lay.addWidget(_info_box(
            "Run all checks to identify hard blockers before filing. "
            "Hard blockers (🔴) must be resolved before closing the year. "
            "Advisories (🟡) should be reviewed but do not prevent filing."
        ))

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("▶  Run All Checks")
        self.run_btn.setStyleSheet(
            "background:#1d4ed8; color:white; font-weight:bold; padding:6px 20px;"
        )
        self.run_btn.clicked.connect(self._run)
        self.export_btn = QPushButton("📥 Export CSV")
        self.export_btn.clicked.connect(self._export)
        self.export_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.summary_lbl = QLabel("Press 'Run All Checks' to start.")
        self.summary_lbl.setStyleSheet("font-weight:bold; padding:4px;")
        lay.addWidget(self.summary_lbl)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Severity", "Category", "Check", "Result"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, 1)

        self._results: list[dict] = []

    def _run(self):
        """Delegate to YearEndManagementWidget logic or run inline checks."""
        self.run_btn.setEnabled(False)
        self.summary_lbl.setText("⏳ Running checks...")
        QApplication.processEvents()

        results = self._execute_checks()
        self._results = results

        self.table.setRowCount(0)
        blockers = 0
        for r in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            sev = r.get("severity", "INFO")
            if sev == "HIGH":
                icon = "🔴 HIGH"
                blockers += 1
                bg = QColor("#fee2e2")
            elif sev == "MEDIUM":
                icon = "🟡 MEDIUM"
                bg = QColor("#fef9c3")
            else:
                icon = "🟢 OK"
                bg = QColor("#dcfce7")
            for col, text in enumerate([icon, r.get("category",""), r.get("title",""), r.get("result","")]):
                item = QTableWidgetItem(text)
                item.setBackground(bg)
                self.table.setItem(row, col, item)

        if blockers:
            self.summary_lbl.setText(
                f"⛔ {blockers} hard blocker(s) found — must fix before filing."
            )
            self.summary_lbl.setStyleSheet("color:#dc2626; font-weight:bold;")
        else:
            self.summary_lbl.setText("✅ All checks passed — ready to proceed.")
            self.summary_lbl.setStyleSheet("color:#16a34a; font-weight:bold;")

        self.run_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

    def _execute_checks(self) -> list[dict]:
        """Run a set of key readiness checks against the DB."""
        results = []
        year = self.tax_year
        jan1 = f"{year}-01-01"
        dec31 = f"{year}-12-31"

        checks = [
            # (key, title, category, severity, sql, success_msg)
            ("gl_unbalanced",
             "GL Unbalanced Transactions",
             "General Ledger", "HIGH",
             f"""SELECT COUNT(*) FROM (
                   SELECT transaction_id, SUM(amount) AS net
                   FROM general_ledger
                   WHERE transaction_date BETWEEN '{jan1}' AND '{dec31}'
                   GROUP BY transaction_id HAVING ABS(SUM(amount)) > 0.005
                 ) t""",
             "All transactions balance"),
            ("receipts_missing_gl",
             "Receipts Missing GL Code",
             "Receipts", "HIGH",
             f"""SELECT COUNT(*) FROM receipts
                 WHERE (gl_account_code IS NULL OR gl_account_code='')
                   AND receipt_date BETWEEN '{jan1}' AND '{dec31}'""",
             "All receipts have GL codes"),
            ("t4_total_match",
             "T4 Gross vs Pay Master Variance",
             "Payroll / T4", "HIGH",
             f"""SELECT ABS(COALESCE(
                   (SELECT SUM(gross_pay) FROM employee_pay_master epm
                    JOIN pay_periods pp ON epm.pay_period_id=pp.pay_period_id
                    WHERE EXTRACT(YEAR FROM pp.pay_date)={year}),0)
                 - COALESCE(
                   (SELECT SUM(employment_income) FROM employee_t4_records
                    WHERE tax_year={year}),0)
                 ) > 1""",
             "T4 totals match pay master"),
            ("missing_sin",
             "Employees Missing SIN",
             "Payroll / T4", "HIGH",
             """SELECT COUNT(*) FROM employees
                WHERE (sin IS NULL OR TRIM(sin)='')
                  AND employment_status='active'""",
             "All active employees have SIN"),
            ("t4_count",
             "T4 Slips Prepared",
             "Payroll / T4", "MEDIUM",
             f"""SELECT COUNT(*) FROM employee_t4_records
                 WHERE tax_year={year}""",
             "T4 slips exist"),
            ("remittance_check",
             "CRA Remittances Recorded",
             "Remittances", "MEDIUM",
             f"""SELECT COUNT(*) FROM cra_pd7a_returns
                 WHERE tax_year={year}""",
             "PD7A records exist"),
            ("bank_unreconciled",
             "Unreconciled Bank Transactions",
             "Banking", "MEDIUM",
             f"""SELECT COUNT(*) FROM banking_transactions
                 WHERE (reconciled IS NULL OR reconciled=false)
                   AND transaction_date BETWEEN '{jan1}' AND '{dec31}'""",
             "All bank transactions reconciled"),
            ("gst_filed",
             "GST Filing Records",
             "GST / HST", "MEDIUM",
             f"""SELECT COUNT(*) FROM tax_remittances
                 WHERE tax_type='GST'
                   AND period_start >= '{jan1}' AND period_end <= '{dec31}'""",
             "GST filings recorded"),
        ]

        for key, title, category, severity, sql, success_msg in checks:
            try:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(sql)
                    val = cur.fetchone()[0]
                # Interpret result: 0 = ok for count-of-problems; >0 = problem
                # Special case: t4_count and remittance_check: 0 = problem
                if key in ("t4_count", "remittance_check", "gst_filed"):
                    ok = val > 0
                    result_text = (
                        f"{val} records found" if ok else "⚠️  None found"
                    )
                    sev = severity if not ok else "INFO"
                else:
                    ok = (val == 0) if isinstance(val, int) else not bool(val)
                    result_text = (
                        success_msg
                        if ok
                        else f"⚠️  {val} issue(s) found"
                    )
                    sev = severity if not ok else "INFO"
                results.append({
                    "key": key,
                    "title": title,
                    "category": category,
                    "severity": sev,
                    "result": result_text,
                })
            except Exception as exc:
                results.append({
                    "key": key,
                    "title": title,
                    "category": category,
                    "severity": "INFO",
                    "result": f"Check skipped: {exc}",
                })
        return results

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Audit Results", f"year_end_audit_{self.tax_year}.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return
        import csv as csv_mod
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv_mod.writer(f)
            w.writerow(["Severity", "Category", "Check", "Result"])
            for r in self._results:
                w.writerow([r["severity"], r["category"], r["title"], r["result"]])
        QMessageBox.information(self, "Exported", f"Audit results saved to:\n{path}")

    def has_blockers(self) -> bool:
        return any(r["severity"] == "HIGH" for r in self._results)


class _T4PayrollStep(QWidget):
    """Step 3 – T4 and payroll readiness."""

    def __init__(self, db, tax_year: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.tax_year = tax_year
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(_h("T4 / Payroll Readiness Review"))
        lay.addWidget(_info_box(
            "Review T4 totals for all employees. "
            "T4 slips must be distributed to employees by the last day of February. "
            "T4 Summary (T4SUM) must be submitted to CRA by the same date."
        ))

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("🔄 Load T4 Summary")
        self.load_btn.setStyleSheet(
            "background:#1d4ed8; color:white; font-weight:bold; padding:6px 20px;"
        )
        self.load_btn.clicked.connect(self._load)
        btn_row.addWidget(self.load_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.summary_lbl = QLabel()
        self.summary_lbl.setStyleSheet("font-weight:bold; padding:4px;")
        lay.addWidget(self.summary_lbl)

        # T4 per-employee table
        t4_grp = QGroupBox("T4 Slip Summary by Employee")
        t4_lay = QVBoxLayout(t4_grp)
        self.t4_table = QTableWidget(0, 7)
        self.t4_table.setHorizontalHeaderLabels([
            "Employee", "SIN", "Box 14\nEmployment Income",
            "Box 16 CPP", "Box 18 EI", "Box 22 Inc Tax",
            "Status"
        ])
        self.t4_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.t4_table.setAlternatingRowColors(True)
        self.t4_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t4_lay.addWidget(self.t4_table)
        lay.addWidget(t4_grp, 1)

        # PD7A remittance summary
        pd_grp = QGroupBox("PD7A Remittance Summary")
        pd_lay = QVBoxLayout(pd_grp)
        self.pd_table = QTableWidget(0, 5)
        self.pd_table.setHorizontalHeaderLabels([
            "Month", "CPP Contributions", "EI Premiums",
            "Income Tax", "Total Remittance"
        ])
        self.pd_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.pd_table.setAlternatingRowColors(True)
        self.pd_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pd_lay.addWidget(self.pd_table)
        lay.addWidget(pd_grp)

    def _load(self):
        year = self.tax_year
        self.load_btn.setEnabled(False)

        # ── T4 slips ──────────────────────────────────────────────────────────
        t4_rows = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT e.full_name, e.sin,
                           COALESCE(t.employment_income,0),
                           COALESCE(t.cpp_contributions,0),
                           COALESCE(t.ei_premiums,0),
                           COALESCE(t.income_tax_deducted,0),
                           COALESCE(t.status,'draft')
                    FROM employee_t4_records t
                    JOIN employees e USING (employee_id)
                    WHERE t.tax_year = %s
                    ORDER BY e.full_name
                    """,
                    (year,),
                )
                t4_rows = cur.fetchall()
        except Exception as exc:
            self.summary_lbl.setText(f"T4 load error: {exc}")

        self.t4_table.setRowCount(0)
        total_income = 0.0
        for r in t4_rows:
            row = self.t4_table.rowCount()
            self.t4_table.insertRow(row)
            name, sin, income, cpp, ei, tax, status = r
            total_income += float(income or 0)
            bg = QColor("#dcfce7") if status == "filed" else QColor("#fef9c3")
            for col, val in enumerate([
                name or "", sin or "⚠️ MISSING",
                f"${float(income):,.2f}", f"${float(cpp):,.2f}",
                f"${float(ei):,.2f}", f"${float(tax):,.2f}", status
            ]):
                item = QTableWidgetItem(val)
                item.setBackground(bg)
                self.t4_table.setItem(row, col, item)

        # ── PD7A ──────────────────────────────────────────────────────────────
        pd_rows = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT month_number,
                           COALESCE(cpp_employee_total,0)+COALESCE(cpp_employer_total,0),
                           COALESCE(ei_employee_total,0)+COALESCE(ei_employer_total,0),
                           COALESCE(income_tax_total,0),
                           COALESCE(total_remittance_due,0)
                    FROM cra_pd7a_returns
                    WHERE tax_year = %s
                    ORDER BY month_number
                    """,
                    (year,),
                )
                pd_rows = cur.fetchall()
        except Exception:
            pass

        import calendar
        self.pd_table.setRowCount(0)
        for r in pd_rows:
            row = self.pd_table.rowCount()
            self.pd_table.insertRow(row)
            month_num, cpp, ei, tax, total = r
            month_name = calendar.month_name[int(month_num)] if month_num else "?"
            for col, val in enumerate([
                month_name,
                f"${float(cpp):,.2f}", f"${float(ei):,.2f}",
                f"${float(tax):,.2f}", f"${float(total):,.2f}"
            ]):
                self.pd_table.setItem(row, col, QTableWidgetItem(val))

        slip_count = len(t4_rows)
        self.summary_lbl.setText(
            f"{'✅' if slip_count > 0 else '⚠️ '}  "
            f"{slip_count} T4 slip(s)  |  "
            f"Total employment income: ${total_income:,.2f}  |  "
            f"{len(pd_rows)} PD7A month(s) on record"
        )
        self.summary_lbl.setStyleSheet(
            "color:#16a34a; font-weight:bold;" if slip_count > 0
            else "color:#dc2626; font-weight:bold;"
        )
        self.load_btn.setEnabled(True)


class _T2PrepStep(QWidget):
    """Step 4 – T2 corporate return preparation with limousine defaults."""

    def __init__(self, db, tax_year: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.tax_year = tax_year
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(_h("T2 Corporate Return Preparation"))
        lay.addWidget(_info_box(
            "Review the limousine-specific T2 defaults and GL-to-GIFI mapping below. "
            "Use the T2 Corporate Tax tab in Accounting & Finance to enter line-by-line "
            "schedule data. This step shows the standard template and pre-populates "
            "key totals from the GL."
        ))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: Limousine T2 defaults ──────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(_h("Limousine T2 Standard Template", 11))
        defaults_table = QTableWidget(len(LIMO_T2_DEFAULTS), 2)
        defaults_table.setHorizontalHeaderLabels(["Item", "Default / Note"])
        defaults_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        defaults_table.verticalHeader().setVisible(False)
        defaults_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        defaults_table.setAlternatingRowColors(True)
        for i, (k, v) in enumerate(LIMO_T2_DEFAULTS.items()):
            defaults_table.setItem(i, 0, QTableWidgetItem(k))
            defaults_table.setItem(i, 1, QTableWidgetItem(v))
        ll.addWidget(defaults_table)
        splitter.addWidget(left)

        # ── Right: GL totals pulled for the year ─────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(_h("Key GL Totals for T2", 11))
        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("🔄 Pull GL Totals")
        self.load_btn.clicked.connect(self._load_gl_totals)
        btn_row.addWidget(self.load_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)
        self.gl_table = QTableWidget(0, 3)
        self.gl_table.setHorizontalHeaderLabels(["GL Code", "Account Name", "Net Amount"])
        self.gl_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.gl_table.setAlternatingRowColors(True)
        self.gl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        rl.addWidget(self.gl_table, 1)
        rl.addWidget(_info_box(
            "Review revenue and expense totals from the GL. "
            "Open the T2 Corporate Tax tab to enter the official Schedule 125 "
            "and Schedule 1 line items. GIFI codes map automatically.",
            "#fef3c7"
        ))
        splitter.addWidget(right)
        splitter.setSizes([400, 400])
        lay.addWidget(splitter, 1)

    def _load_gl_totals(self):
        year = self.tax_year
        jan1 = f"{year}-01-01"
        dec31 = f"{year}-12-31"
        self.gl_table.setRowCount(0)
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT gl_account_code,
                           MAX(gl_account_name) AS acct_name,
                           SUM(amount) AS net
                    FROM general_ledger
                    WHERE transaction_date BETWEEN %s AND %s
                    GROUP BY gl_account_code
                    ORDER BY gl_account_code
                    """,
                    (jan1, dec31),
                )
                rows = cur.fetchall()
            for code, name, net in rows:
                row = self.gl_table.rowCount()
                self.gl_table.insertRow(row)
                net_val = float(net or 0)
                for col, val in enumerate([
                    str(code or ""), str(name or ""),
                    f"${net_val:,.2f}"
                ]):
                    item = QTableWidgetItem(val)
                    if col == 2 and net_val < 0:
                        item.setForeground(QColor("#dc2626"))
                    self.gl_table.setItem(row, col, item)
        except Exception as exc:
            self.gl_table.setRowCount(1)
            self.gl_table.setItem(0, 0, QTableWidgetItem(f"Error: {exc}"))


class _AccountantBundleStep(QWidget):
    """Step 5 – One-click accountant report bundle."""

    def __init__(self, db, tax_year: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.tax_year = tax_year
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(_h("Accountant Report Bundle"))
        lay.addWidget(_info_box(
            "Generate and export all reports the accountant needs in one step. "
            "Each report can be exported to CSV or printed individually, or click "
            "'📦 Export All Reports to CSV Bundle' to get a ZIP of everything."
        ))

        # Report checklist
        grp = QGroupBox("Reports Included in Bundle")
        g_lay = QVBoxLayout(grp)
        from PyQt6.QtWidgets import QCheckBox
        self._report_checks: list[tuple[str, str, QCheckBox]] = []
        for label, desc in REPORT_LABELS:
            cb = QCheckBox(f"  {label}  — {desc}")
            cb.setChecked(True)
            g_lay.addWidget(cb)
            self._report_checks.append((label, desc, cb))
        lay.addWidget(grp)

        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("📦 Export All Reports to CSV Bundle")
        self.export_btn.setStyleSheet(
            "background:#1d4ed8; color:white; font-weight:bold; padding:8px 24px;"
        )
        self.export_btn.clicked.connect(self._export_bundle)

        self.print_btn = QPushButton("🖨️  Print All Reports")
        self.print_btn.clicked.connect(self._print_bundle)

        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.status_lbl = QLabel()
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color:#16a34a; font-weight:bold; padding:6px;")
        lay.addWidget(self.status_lbl)
        lay.addStretch()

    def _export_bundle(self):
        import csv as csv_mod
        import zipfile

        selected = [label for label, _, cb in self._report_checks if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Nothing Selected", "Select at least one report.")
            return

        folder = QFileDialog.getExistingDirectory(
            self, f"Choose folder for {self.tax_year} Accountant Bundle"
        )
        if not folder:
            return

        year = self.tax_year
        jan1 = f"{year}-01-01"
        dec31 = f"{year}-12-31"
        exported: list[str] = []
        errors: list[str] = []

        zip_path = str(Path(folder) / f"accountant_bundle_{year}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for label in selected:
                try:
                    csv_path = str(Path(folder) / f"{year}_{label.replace(' ','_')}.csv")
                    rows, headers = self._fetch_report(label, jan1, dec31)
                    with open(csv_path, "w", newline="", encoding="utf-8") as f:
                        w = csv_mod.writer(f)
                        w.writerow(headers)
                        w.writerows(rows)
                    zf.write(csv_path, Path(csv_path).name)
                    exported.append(label)
                except Exception as exc:
                    errors.append(f"{label}: {exc}")

        msg_parts = [f"✅ Exported {len(exported)} report(s) to:\n{zip_path}"]
        if errors:
            msg_parts.append("⚠️  Skipped (errors):\n" + "\n".join(errors))
        self.status_lbl.setText("\n".join(msg_parts))
        if errors:
            self.status_lbl.setStyleSheet("color:#92400e; font-weight:bold; padding:6px;")

    def _fetch_report(
        self, label: str, jan1: str, dec31: str
    ) -> tuple[list[tuple], list[str]]:
        """Fetch data for a given report label."""
        year = self.tax_year

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if label == "General Ledger":
                cur.execute(
                    """SELECT transaction_date, gl_account_code, gl_account_name,
                              description, amount, reference_number
                       FROM general_ledger
                       WHERE transaction_date BETWEEN %s AND %s
                       ORDER BY transaction_date, transaction_id""",
                    (jan1, dec31),
                )
                return cur.fetchall(), [
                    "Date","GL Code","Account","Description","Amount","Reference"
                ]

            elif label == "Trial Balance":
                cur.execute(
                    """SELECT gl_account_code, MAX(gl_account_name), SUM(amount)
                       FROM general_ledger
                       WHERE transaction_date BETWEEN %s AND %s
                       GROUP BY gl_account_code
                       ORDER BY gl_account_code""",
                    (jan1, dec31),
                )
                return cur.fetchall(), ["GL Code","Account Name","Net Balance"]

            elif label == "Income Statement":
                cur.execute(
                    """SELECT gl_account_code, MAX(gl_account_name),
                              MAX(account_category), SUM(amount)
                       FROM general_ledger
                       WHERE transaction_date BETWEEN %s AND %s
                       GROUP BY gl_account_code
                       ORDER BY gl_account_code""",
                    (jan1, dec31),
                )
                return cur.fetchall(), ["GL Code","Account","Category","Net Amount"]

            elif label == "T4 Summary":
                cur.execute(
                    """SELECT e.full_name, e.sin,
                              COALESCE(t.employment_income,0),
                              COALESCE(t.cpp_contributions,0),
                              COALESCE(t.ei_premiums,0),
                              COALESCE(t.income_tax_deducted,0),
                              COALESCE(t.status,'draft')
                       FROM employee_t4_records t
                       JOIN employees e USING (employee_id)
                       WHERE t.tax_year = %s
                       ORDER BY e.full_name""",
                    (year,),
                )
                return cur.fetchall(), [
                    "Employee","SIN","Box 14 Income","Box 16 CPP",
                    "Box 18 EI","Box 22 Tax","Status"
                ]

            elif label == "PD7A Remittances":
                cur.execute(
                    """SELECT month_number,
                              COALESCE(cpp_employee_total,0)+COALESCE(cpp_employer_total,0),
                              COALESCE(ei_employee_total,0)+COALESCE(ei_employer_total,0),
                              COALESCE(income_tax_total,0),
                              COALESCE(total_remittance_due,0)
                       FROM cra_pd7a_returns
                       WHERE tax_year = %s
                       ORDER BY month_number""",
                    (year,),
                )
                return cur.fetchall(), [
                    "Month","CPP Total","EI Total","Income Tax","Total Due"
                ]

            elif label == "Payroll Ledger":
                cur.execute(
                    """SELECT e.full_name, pp.pay_period_number,
                              COALESCE(epm.gross_pay,0),
                              COALESCE(epm.federal_tax,0),
                              COALESCE(epm.provincial_tax,0),
                              COALESCE(epm.cpp_employee,0),
                              COALESCE(epm.ei_employee,0),
                              COALESCE(epm.net_pay,0)
                       FROM employee_pay_master epm
                       JOIN employees e USING (employee_id)
                       JOIN pay_periods pp ON epm.pay_period_id=pp.pay_period_id
                       WHERE EXTRACT(YEAR FROM pp.pay_date)=%s
                       ORDER BY e.full_name, pp.pay_period_number""",
                    (year,),
                )
                return cur.fetchall(), [
                    "Employee","Period","Gross","Fed Tax","Prov Tax",
                    "CPP","EI","Net Pay"
                ]

            elif label == "GST Summary":
                cur.execute(
                    """SELECT period_start, period_end, tax_type,
                              COALESCE(amount_collected,0),
                              COALESCE(itc_claimed,0),
                              COALESCE(net_remittance,0)
                       FROM tax_remittances
                       WHERE tax_type='GST'
                         AND period_start >= %s AND period_end <= %s
                       ORDER BY period_start""",
                    (jan1, dec31),
                )
                return cur.fetchall(), [
                    "Period Start","Period End","Type",
                    "Collected","ITC Claimed","Net Remittance"
                ]

            elif label == "Balance Sheet":
                cur.execute(
                    """SELECT gl_account_code, MAX(gl_account_name),
                              MAX(account_type), SUM(amount)
                       FROM general_ledger
                       WHERE transaction_date <= %s
                         AND account_type IN ('asset','liability','equity',
                                              'Asset','Liability','Equity')
                       GROUP BY gl_account_code
                       ORDER BY gl_account_code""",
                    (dec31,),
                )
                return cur.fetchall(), ["GL Code","Account","Type","Balance"]

            elif label == "WCB Annual":
                cur.execute(
                    """SELECT year, COALESCE(total_premiums,0),
                              COALESCE(insurable_earnings,0),
                              COALESCE(status,'')
                       FROM wcb_annual_returns
                       WHERE year = %s
                       ORDER BY year""",
                    (year,),
                )
                return cur.fetchall(), ["Year","Premiums","Insurable Earnings","Status"]

        return [], ["No Data"]

    def _print_bundle(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        doc = self._build_print_document()
        doc.print(printer)

    def _build_print_document(self):
        from PyQt6.QtGui import QTextDocument
        doc = QTextDocument()
        year = self.tax_year
        html = [f"<h1>Accountant Bundle – Tax Year {year}</h1>"]
        html.append(f"<p>Prepared: {date.today().strftime('%B %d, %Y')}</p>")
        html.append("<hr/>")
        html.append(
            "<p>This bundle contains the following reports: "
            + ", ".join(label for label, _, cb in self._report_checks if cb.isChecked())
            + "</p>"
        )
        html.append(
            "<p><em>Export to CSV for full detail. "
            "This printed summary is for reference only.</em></p>"
        )
        doc.setHtml("".join(html))
        return doc


class _ArchiveNotesStep(QWidget):
    """Step 6 – Archive year and notes."""

    def __init__(self, db, tax_year: int, auth_user: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.tax_year = tax_year
        self.auth_user = auth_user
        self._build_ui()
        self._load_notes()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(_h("Archive & Year-End Notes"))
        lay.addWidget(_info_box(
            "Record observations, solutions, and suggestions for next year. "
            "These notes are stored permanently in the year_end_notes table "
            "and can be reviewed at the start of the next filing cycle. "
            "Click 'Close Year' to stamp the year_end_archive record."
        ))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: add new note ────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(_h("Add Note / Observation", 11))
        form = QFormLayout()

        self.note_type_cb = QComboBox()
        self.note_type_cb.addItems(["note", "issue", "solution", "suggestion", "action"])
        form.addRow("Type:", self.note_type_cb)

        self.note_cat_cb = QComboBox()
        self.note_cat_cb.addItems([
            "General", "Payroll", "T4", "T2", "GST", "WCB",
            "Banking", "GL", "Remittances", "Company Info", "Next Year Action"
        ])
        form.addRow("Category:", self.note_cat_cb)

        self.note_subject = QLineEdit()
        self.note_subject.setPlaceholderText("Brief subject / title")
        form.addRow("Subject:", self.note_subject)

        self.note_status_cb = QComboBox()
        self.note_status_cb.addItems(["open", "in progress", "resolved", "deferred"])
        form.addRow("Status:", self.note_status_cb)

        ll.addLayout(form)
        self.note_body = QPlainTextEdit()
        self.note_body.setPlaceholderText(
            "Describe the observation, solution steps, or action for next year..."
        )
        self.note_body.setMinimumHeight(120)
        ll.addWidget(QLabel("Notes:"))
        ll.addWidget(self.note_body)

        save_note_btn = QPushButton("💾 Save Note")
        save_note_btn.setStyleSheet(
            "background:#1d4ed8; color:white; font-weight:bold; padding:6px 18px;"
        )
        save_note_btn.clicked.connect(self._save_note)
        ll.addWidget(save_note_btn)
        ll.addStretch()
        splitter.addWidget(left)

        # ── Right: existing notes ─────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(_h("Saved Notes for This Year", 11))
        self.notes_table = QTableWidget(0, 5)
        self.notes_table.setHorizontalHeaderLabels([
            "Type", "Category", "Subject", "Status", "Created"
        ])
        self.notes_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.notes_table.setAlternatingRowColors(True)
        self.notes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.notes_table.doubleClicked.connect(self._view_note)
        rl.addWidget(self.notes_table, 1)
        splitter.addWidget(right)
        splitter.setSizes([420, 420])
        lay.addWidget(splitter, 1)

        # ── Close year row ────────────────────────────────────────────────────
        lay.addWidget(_separator())
        close_row = QHBoxLayout()
        self.close_btn = QPushButton(f"🔒 Close {self.tax_year} – Archive Record")
        self.close_btn.setStyleSheet(
            "background:#dc2626; color:white; font-weight:bold; padding:8px 24px;"
        )
        self.close_btn.clicked.connect(self._close_year)
        close_row.addStretch()
        close_row.addWidget(self.close_btn)
        lay.addLayout(close_row)

        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-weight:bold; padding:4px;")
        lay.addWidget(self.status_lbl)

    def _load_notes(self):
        self.notes_table.setRowCount(0)
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """SELECT note_id, note_type, category, subject, status,
                              TO_CHAR(created_at, 'YYYY-MM-DD')
                       FROM year_end_notes
                       WHERE tax_year = %s
                       ORDER BY created_at DESC""",
                    (self.tax_year,),
                )
                rows = cur.fetchall()
        except Exception as exc:
            self.status_lbl.setText(f"Load error: {exc}")
            return

        for note_id, ntype, cat, subj, status, created in rows:
            row = self.notes_table.rowCount()
            self.notes_table.insertRow(row)
            for col, val in enumerate([ntype, cat, subj or "", status, created or ""]):
                item = QTableWidgetItem(val or "")
                item.setData(Qt.ItemDataRole.UserRole, note_id)
                self.notes_table.setItem(row, col, item)

    def _save_note(self):
        subj = self.note_subject.text().strip()
        body = self.note_body.toPlainText().strip()
        if not subj and not body:
            QMessageBox.warning(self, "Empty Note", "Enter a subject or body.")
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """INSERT INTO year_end_notes
                       (tax_year, note_type, category, subject, body, status, assigned_to)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        self.tax_year,
                        self.note_type_cb.currentText(),
                        self.note_cat_cb.currentText(),
                        subj or "(no subject)",
                        body or None,
                        self.note_status_cb.currentText(),
                        self.auth_user.get("username", ""),
                    ),
                )
            self.note_subject.clear()
            self.note_body.clear()
            self.status_lbl.setText("✅ Note saved.")
            self.status_lbl.setStyleSheet("color:#16a34a; font-weight:bold;")
            self._load_notes()
        except Exception as exc:
            self.status_lbl.setText(f"❌ {exc}")
            self.status_lbl.setStyleSheet("color:#dc2626;")

    def _view_note(self, index):
        row = index.row()
        ntype = self.notes_table.item(row, 0)
        cat = self.notes_table.item(row, 1)
        subj = self.notes_table.item(row, 2)
        note_id = ntype.data(Qt.ItemDataRole.UserRole) if ntype else None
        if not note_id:
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("SELECT body FROM year_end_notes WHERE note_id=%s", (note_id,))
                result = cur.fetchone()
            body = result[0] if result else ""
        except Exception:
            body = ""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{subj.text() if subj else 'Note'}")
        dlg.resize(600, 400)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"<b>{cat.text() if cat else ''} — {subj.text() if subj else ''}</b>"))
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(body or "(no body)")
        v.addWidget(te)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn)
        dlg.exec()

    def _close_year(self):
        year = self.tax_year
        ans = QMessageBox.question(
            self,
            f"Close Year {year}",
            f"Archive {year} as closed?\n\n"
            "This stamps a year_end_archive record. "
            "It does NOT prevent further edits — it is a milestone marker.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        user = self.auth_user.get("username", "system")
        try:
            # Gather summary stats
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """SELECT COUNT(*), COALESCE(SUM(gross_pay),0)
                       FROM employee_pay_master epm
                       JOIN pay_periods pp ON epm.pay_period_id=pp.pay_period_id
                       WHERE EXTRACT(YEAR FROM pp.pay_date)=%s""",
                    (year,),
                )
                pay_row = cur.fetchone()
                cur.execute(
                    "SELECT COALESCE(SUM(total_remittance_due),0) FROM cra_pd7a_returns WHERE tax_year=%s",
                    (year,),
                )
                remit_row = cur.fetchone()
                cur.execute(
                    "SELECT COUNT(*) FROM employee_t4_records WHERE tax_year=%s",
                    (year,),
                )
                t4_row = cur.fetchone()

            pay_count = pay_row[0] if pay_row else 0
            pay_gross = float(pay_row[1]) if pay_row else 0.0
            remit_total = float(remit_row[0]) if remit_row else 0.0
            t4_count = t4_row[0] if t4_row else 0

            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """INSERT INTO year_end_archive
                       (tax_year, closed_at, closed_by, payroll_summary,
                        t4_count, t4_total_gross, remittance_total)
                       VALUES (%s, NOW(), %s, %s, %s, %s, %s)
                       ON CONFLICT (tax_year) DO UPDATE
                         SET closed_at=NOW(), closed_by=EXCLUDED.closed_by,
                             payroll_summary=EXCLUDED.payroll_summary,
                             t4_count=EXCLUDED.t4_count,
                             t4_total_gross=EXCLUDED.t4_total_gross,
                             remittance_total=EXCLUDED.remittance_total""",
                    (
                        year, user,
                        json.dumps({"records": pay_count, "gross": pay_gross}),
                        t4_count, pay_gross, remit_total,
                    ),
                )
            self.status_lbl.setText(
                f"✅ Year {year} archived by {user}. "
                f"T4 slips: {t4_count}  |  Gross payroll: ${pay_gross:,.2f}  |  "
                f"CRA remittances: ${remit_total:,.2f}"
            )
            self.status_lbl.setStyleSheet("color:#16a34a; font-weight:bold;")
            self.close_btn.setText(f"✅ {year} Archived")
            self.close_btn.setEnabled(False)
        except Exception as exc:
            self.status_lbl.setText(f"❌ Archive error: {exc}")
            self.status_lbl.setStyleSheet("color:#dc2626;")


# ──────────────────────────────────────────────────────────────────────────────
# Main Wizard
# ──────────────────────────────────────────────────────────────────────────────

class YearEndWizardWidget(QWidget):
    """
    Year-End Guided Wizard – the central guided workflow for year-end close,
    T4/T2 preparation, accountant bundle export, and notes archiving.
    """

    def __init__(self, db_connection, auth_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.auth_user = auth_user or {"username": "system", "role": "admin"}
        self._current_step = 0
        self._build_ui()
        self._refresh_year()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setStyleSheet("background:#1e3a5f; padding:10px;")
        hb_lay = QHBoxLayout(header_bar)
        hb_lay.setContentsMargins(16, 8, 16, 8)
        title = QLabel("🗓️  Year-End Guided Wizard")
        title.setStyleSheet("color:white; font-size:16pt; font-weight:bold;")
        hb_lay.addWidget(title)
        hb_lay.addStretch()

        self.year_combo = QComboBox()
        self.year_combo.setStyleSheet("background:white; padding:3px; font-size:11pt;")
        current_year = date.today().year - 1  # default: last calendar year
        for y in range(current_year, current_year - 8, -1):
            self.year_combo.addItem(str(y), y)
        self.year_combo.currentIndexChanged.connect(self._refresh_year)
        hb_lay.addWidget(QLabel("<span style='color:white;font-weight:bold'>Tax Year:</span>"))
        hb_lay.addWidget(self.year_combo)
        outer.addWidget(header_bar)

        # Main body: left nav + right stacked content
        body_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left nav panel ──────────────────────────────────────────────────
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background:#f0f4f8;")
        nav_widget.setFixedWidth(220)
        nav_lay = QVBoxLayout(nav_widget)
        nav_lay.setContentsMargins(8, 16, 8, 16)
        nav_lay.setSpacing(4)

        nav_lay.addWidget(QLabel(
            "<b style='color:#1e3a5f; font-size:11pt;'>Steps</b>"
        ))
        nav_lay.addWidget(_separator())

        self.nav_buttons: list[QPushButton] = []
        for i, (num, name, desc) in enumerate(STEPS):
            btn = QPushButton(f"  {num}.  {name}")
            btn.setCheckable(True)
            btn.setToolTip(desc)
            btn.setStyleSheet(
                "QPushButton { text-align:left; padding:8px 10px; border:none;"
                "  border-radius:4px; font-size:10pt; }"
                "QPushButton:checked { background:#1d4ed8; color:white; font-weight:bold; }"
                "QPushButton:hover:!checked { background:#dbeafe; }"
            )
            btn.clicked.connect(lambda _, idx=i: self._goto_step(idx))
            nav_lay.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_lay.addStretch()

        # Progress indicator
        self.progress_lbl = QLabel()
        self.progress_lbl.setWordWrap(True)
        self.progress_lbl.setStyleSheet(
            "color:#1e40af; font-size:9pt; padding:4px;"
        )
        nav_lay.addWidget(self.progress_lbl)
        body_splitter.addWidget(nav_widget)

        # ── Right: stacked step pages ────────────────────────────────────────
        self.stack = QStackedWidget()
        body_splitter.addWidget(self.stack)
        body_splitter.setSizes([220, 900])
        outer.addWidget(body_splitter, 1)

        # Footer nav buttons
        footer = QWidget()
        footer.setStyleSheet("background:#f8fafc; border-top:1px solid #e2e8f0;")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(16, 8, 16, 8)
        self.back_btn = QPushButton("◀  Back")
        self.back_btn.clicked.connect(lambda: self._goto_step(self._current_step - 1))
        self.next_btn = QPushButton("Next  ▶")
        self.next_btn.setStyleSheet(
            "background:#1d4ed8; color:white; font-weight:bold; padding:6px 20px;"
        )
        self.next_btn.clicked.connect(lambda: self._goto_step(self._current_step + 1))
        self.step_lbl = QLabel()
        self.step_lbl.setStyleSheet("color:#64748b; font-size:10pt;")
        f_lay.addWidget(self.back_btn)
        f_lay.addStretch()
        f_lay.addWidget(self.step_lbl)
        f_lay.addStretch()
        f_lay.addWidget(self.next_btn)
        outer.addWidget(footer)

    def _refresh_year(self):
        """Rebuild step widgets for the newly selected tax year."""
        tax_year = self.year_combo.currentData() or (date.today().year - 1)

        # Clear old step widgets
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()

        # Rebuild
        self._company_step = _CompanyInfoStep(self.db, tax_year)
        self._audit_step = _AuditChecksStep(self.db, tax_year)
        self._t4_step = _T4PayrollStep(self.db, tax_year)
        self._t2_step = _T2PrepStep(self.db, tax_year)
        self._bundle_step = _AccountantBundleStep(self.db, tax_year)
        self._archive_step = _ArchiveNotesStep(self.db, tax_year, self.auth_user)

        for step_widget in [
            self._company_step,
            self._audit_step,
            self._t4_step,
            self._t2_step,
            self._bundle_step,
            self._archive_step,
        ]:
            # Wrap in scroll area for safety
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(step_widget)
            self.stack.addWidget(scroll)

        self._goto_step(0)

    def _goto_step(self, idx: int):
        count = len(STEPS)
        idx = max(0, min(idx, count - 1))
        self._current_step = idx
        self.stack.setCurrentIndex(idx)

        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)

        _, name, desc = STEPS[idx]
        self.step_lbl.setText(f"Step {idx + 1} of {count}  —  {name}")
        self.back_btn.setEnabled(idx > 0)
        self.next_btn.setText(
            "Finish  ✓" if idx == count - 1 else "Next  ▶"
        )

        if idx == count - 1:
            self.next_btn.setStyleSheet(
                "background:#16a34a; color:white; font-weight:bold; padding:6px 20px;"
            )
        else:
            self.next_btn.setStyleSheet(
                "background:#1d4ed8; color:white; font-weight:bold; padding:6px 20px;"
            )

        self.progress_lbl.setText(
            f"Step {idx + 1}/{count}\n{name}\n\n{desc}"
        )
