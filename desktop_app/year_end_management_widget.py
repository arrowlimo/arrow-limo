"""
Year-End Management System

Audit-oriented desktop widget for:
- GL consistency checks
- Receipt and expense completeness checks
- Payroll/T4/T2 readiness checks
- Reconciliation and variance checks

Designed for Arrow Limo (Alberta, Canada) workflows.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

HARD_BLOCKER_KEYS = {
    "gl_unbalanced_txn",
    "receipts_missing_gl",
    "bank_unreconciled",
    "income_unmatched_charters",
    "payroll_t4_variance",
    "payroll_missing_sin",
    "remittance_variance",
}

logger = logging.getLogger(__name__)


@dataclass
class AuditCheck:
    key: str
    title: str
    category: str
    severity: str
    reminder: str
    sql: str


CHECKS: list[AuditCheck] = [
    AuditCheck(
        key="gl_unbalanced_txn",
        title="GL Unbalanced Transactions",
        category="General Ledger",
        severity="HIGH",
        reminder=(
            "Review transaction groups where debits "
            "do not equal credits."
        ),
        sql="""
SELECT
    COALESCE(transaction_id, '[no id]') AS transaction_id,
    COALESCE(date::text, '') AS gl_date,
    ROUND(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))::numeric,
    2) AS imbalance,
    COUNT(*) AS line_count
FROM general_ledger
WHERE EXTRACT(YEAR FROM COALESCE(date, transaction_date)) = :year
GROUP BY COALESCE(transaction_id, '[no id]'), COALESCE(date::text, '')
HAVING ABS(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))) > 0.01
ORDER BY ABS(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))) DESC
LIMIT 500
""",
    ),
    AuditCheck(
        key="gl_plug_entries",
        title="Plug / Suspense Usage",
        category="General Ledger",
        severity="HIGH",
        reminder=(
            "Plug/suspense postings must be justified "
            "or cleared before filing."
        ),
        sql="""
SELECT
    COALESCE(date::text, '') AS gl_date,
    COALESCE(transaction_id, '') AS transaction_id,
    COALESCE(account, '') AS account,
    COALESCE(name, '') AS name,
    ROUND(COALESCE(debit, 0)::numeric, 2) AS debit,
    ROUND(COALESCE(credit, 0)::numeric, 2) AS credit,
    COALESCE(memo_description, '') AS memo
FROM general_ledger
WHERE EXTRACT(YEAR FROM COALESCE(date, transaction_date)) = :year
  AND (
    COALESCE(account, '') ILIKE '%plug%'
    OR COALESCE(account, '') ILIKE '%suspense%'
    OR COALESCE(memo_description, '') ILIKE '%plug%'
  )
ORDER BY COALESCE(date, transaction_date), transaction_id
LIMIT 1000
""",
    ),
    AuditCheck(
        key="receipts_missing_gl",
        title="Receipts Missing GL Codes",
        category="Expenses",
        severity="HIGH",
        reminder=(
            "Map all business receipts to valid GL "
            "codes before year-end close."
        ),
        sql="""
SELECT
    receipt_id,
    COALESCE(receipt_date::text, '') AS receipt_date,
    COALESCE(vendor_name, '') AS vendor_name,
    ROUND(COALESCE(gross_amount, 0)::numeric, 2) AS gross_amount,
    COALESCE(payment_method, '') AS payment_method,
    COALESCE(gl_code, '') AS gl_code,
    COALESCE(gl_account_code, '') AS gl_account_code
FROM receipts
WHERE fiscal_year = :year
  AND COALESCE(is_voided, false) = false
  AND COALESCE(exclude_from_reports, false) = false
  AND COALESCE(is_personal_purchase, false) = false
  AND COALESCE(owner_personal_amount, 0) = 0
  AND (NULLIF(TRIM(COALESCE(gl_code, '')), '') IS NULL)
ORDER BY receipt_date, receipt_id
LIMIT 2000
""",
    ),
    AuditCheck(
        key="receipts_gst_anomalies",
        title="GST Calculation Anomalies",
        category="Expenses",
        severity="MEDIUM",
        reminder="Check GST amounts that look impossible or inconsistent.",
        sql="""
SELECT
    receipt_id,
    COALESCE(receipt_date::text, '') AS receipt_date,
    COALESCE(vendor_name, '') AS vendor_name,
    ROUND(COALESCE(gross_amount, 0)::numeric, 2) AS gross_amount,
    ROUND(COALESCE(gst_amount, 0)::numeric, 2) AS gst_amount,
    ROUND(COALESCE(net_amount, 0)::numeric, 2) AS net_amount,
    COALESCE(gl_code, '') AS gl_code
FROM receipts
WHERE fiscal_year = :year
  AND COALESCE(is_voided, false) = false
  AND (
    COALESCE(gst_amount, 0) < 0
    OR COALESCE(gst_amount, 0) > COALESCE(gross_amount, 0)
    OR (COALESCE(gross_amount, 0) > 0 AND COALESCE(gst_amount,
    0) > COALESCE(gross_amount, 0) * 0.20)
  )
ORDER BY receipt_date, receipt_id
LIMIT 2000
""",
    ),
    AuditCheck(
        key="bank_unreconciled",
        title="Unreconciled Banking Transactions",
        category="Reconciliation",
        severity="HIGH",
        reminder=(
            "Old unreconciled bank rows usually indicate "
            "missing receipts or payment links."
        ),
        sql="""
SELECT
    transaction_id,
    COALESCE(transaction_date::text, '') AS transaction_date,
    COALESCE(description, '') AS description,
    ROUND(COALESCE(debit_amount, 0)::numeric, 2) AS debit_amount,
    ROUND(COALESCE(credit_amount, 0)::numeric, 2) AS credit_amount,
    COALESCE(reconciliation_status, '') AS reconciliation_status,
    receipt_id,
    accounting_entry_id,
    income_ledger_id,
    payment_id
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) = :year
  AND COALESCE(locked, false) = false
  AND COALESCE(reconciled_receipt_id, 0) = 0
  AND COALESCE(reconciled_payment_id, 0) = 0
  AND COALESCE(receipt_id, 0) = 0
  AND COALESCE(accounting_entry_id, 0) = 0
  AND COALESCE(income_ledger_id, 0) = 0
  AND COALESCE(payment_id, 0) = 0
ORDER BY transaction_date, transaction_id
LIMIT 3000
""",
    ),
    AuditCheck(
        key="charter_ar_aging",
        title="A/R Aging Over 90 Days",
        category="Receivables",
        severity="HIGH",
        reminder=(
            "Resolve old receivables with payment, "
            "write-down, or collections notes."
        ),
        sql="""
SELECT
    COALESCE(reserve_number, reserve_no, order_number, '') AS reserve_number,
    COALESCE(charter_date, pickup_date,
    created_at)::date::text AS charter_date,
    COALESCE(client_display_name, client_name, '') AS client_name,
    COALESCE(account_number, '') AS account_number,
    ROUND(COALESCE(total_amount_due, amount, total, 0)::numeric,
    2) AS amount_due,
    ROUND(COALESCE(paid_amount, total_paid, 0)::numeric, 2) AS paid_amount,
    ROUND((COALESCE(total_amount_due, amount, total, 0) - COALESCE(paid_amount,
    total_paid, 0))::numeric, 2) AS balance,
    (CURRENT_DATE - COALESCE(charter_date, pickup_date,
    created_at)::date) AS days_outstanding
FROM charters
WHERE EXTRACT(YEAR FROM COALESCE(charter_date, pickup_date,
created_at)::date) <= :year
  AND (COALESCE(total_amount_due, amount, total, 0) - COALESCE(paid_amount,
  total_paid, 0)) > 0
  AND (CURRENT_DATE - COALESCE(charter_date, pickup_date,
  created_at)::date) > 90
ORDER BY days_outstanding DESC
LIMIT 3000
""",
    ),
    AuditCheck(
        key="income_unmatched_charters",
        title="Income Rows Missing Charter Link",
        category="Revenue",
        severity="HIGH",
        reminder=(
            "Revenue with missing charter_id/reserve_number "
            "can break T2 and reporting."
        ),
        sql="""
SELECT
    income_id,
    COALESCE(transaction_date::text, '') AS transaction_date,
    COALESCE(source_system, '') AS source_system,
    COALESCE(revenue_category, '') AS revenue_category,
    ROUND(COALESCE(gross_amount, 0)::numeric, 2) AS gross_amount,
    ROUND(COALESCE(gst_collected, 0)::numeric, 2) AS gst_collected,
    ROUND(COALESCE(net_amount, 0)::numeric, 2) AS net_amount,
    charter_id,
    COALESCE(reserve_number, '') AS reserve_number,
    COALESCE(payment_reference, '') AS payment_reference
FROM income_ledger
WHERE fiscal_year = :year
  AND (charter_id IS NULL OR COALESCE(reserve_number, '') = '')
ORDER BY transaction_date, income_id
LIMIT 3000
""",
    ),
    AuditCheck(
        key="payroll_t4_variance",
        title="Payroll vs T4 Variance",
        category="Payroll",
        severity="HIGH",
        reminder="T4 values must reconcile to payroll before CRA filing.",
        sql="""
WITH payroll AS (
    SELECT
        employee_id,
        SUM(
            COALESCE(
                t4_box_14,
                GREATEST(
                    COALESCE(gross_pay, 0) - COALESCE(expense_reimbursement, 0),
                    0
                ),
                0
            )
        ) AS p_box14,
        SUM(COALESCE(t4_box_16, cpp, 0)) AS p_box16,
        SUM(COALESCE(t4_box_18, ei, 0)) AS p_box18,
        SUM(COALESCE(t4_box_22, tax, 0)) AS p_box22
    FROM driver_payroll
    WHERE year = :year
    GROUP BY employee_id
),
t4 AS (
    SELECT
        employee_id,
        COALESCE(box_14_employment_income, 0) AS t_box14,
        COALESCE(box_16_cpp_contributions, 0) AS t_box16,
        COALESCE(box_18_ei_premiums, 0) AS t_box18,
        COALESCE(box_22_income_tax, 0) AS t_box22
    FROM employee_t4_records
    WHERE tax_year = :year
)
SELECT
    COALESCE(e.employee_id, p.employee_id, t.employee_id) AS employee_id,
    COALESCE(e.full_name, '') AS full_name,
    ROUND(COALESCE(p.p_box14, 0)::numeric, 2) AS payroll_box14,
    ROUND(COALESCE(t.t_box14, 0)::numeric, 2) AS t4_box14,
    ROUND((COALESCE(p.p_box14, 0) - COALESCE(t.t_box14, 0))::numeric,
    2) AS diff_box14,
    ROUND((COALESCE(p.p_box16, 0) - COALESCE(t.t_box16, 0))::numeric,
    2) AS diff_box16,
    ROUND((COALESCE(p.p_box18, 0) - COALESCE(t.t_box18, 0))::numeric,
    2) AS diff_box18,
    ROUND((COALESCE(p.p_box22, 0) - COALESCE(t.t_box22, 0))::numeric,
    2) AS diff_box22
FROM payroll p
FULL OUTER JOIN t4 t ON t.employee_id = p.employee_id
LEFT JOIN employees e ON e.employee_id = COALESCE(p.employee_id, t.employee_id)
WHERE
    ABS(COALESCE(p.p_box14, 0) - COALESCE(t.t_box14, 0)) > 0.01
    OR ABS(COALESCE(p.p_box16, 0) - COALESCE(t.t_box16, 0)) > 0.01
    OR ABS(COALESCE(p.p_box18, 0) - COALESCE(t.t_box18, 0)) > 0.01
    OR ABS(COALESCE(p.p_box22, 0) - COALESCE(t.t_box22, 0)) > 0.01
ORDER BY ABS(COALESCE(p.p_box14, 0) - COALESCE(t.t_box14, 0)) DESC
LIMIT 1000
""",
    ),
    AuditCheck(
        key="payroll_missing_sin",
        title="Missing SIN for T4 Employees",
        category="Payroll",
        severity="HIGH",
        reminder="Every T4 employee must have a SIN before submission.",
        sql="""
SELECT
    e.employee_id,
    COALESCE(e.full_name, '') AS full_name,
    COALESCE(e.t4_sin, '') AS t4_sin,
    :year AS tax_year
FROM employees e
JOIN employee_t4_records t ON t.employee_id = e.employee_id AND t.tax_year =
:year
WHERE NULLIF(TRIM(COALESCE(e.t4_sin, '')), '') IS NULL
ORDER BY e.employee_id
LIMIT 1000
""",
    ),
    AuditCheck(
        key="remittance_variance",
        title="Payroll Remittance Variance",
        category="Payroll",
        severity="HIGH",
        reminder=(
            "PD7A remittance variances should be resolved "
            "before filing package finalization."
        ),
        sql="""
SELECT
    fiscal_year,
    remittance_month,
    ROUND(COALESCE(calculated_total_remittance, 0)::numeric,
    2) AS calculated_total,
    ROUND(COALESCE(payment_amount, 0)::numeric, 2) AS payment_amount,
    ROUND(COALESCE(pd7a_statement_amount, 0)::numeric, 2) AS pd7a_amount,
    ROUND(COALESCE(variance, 0)::numeric, 2) AS stored_variance,
    ROUND((COALESCE(payment_amount, 0) - COALESCE(calculated_total_remittance,
    0))::numeric, 2) AS payment_vs_calc,
    COALESCE(status, '') AS status,
    COALESCE(due_date::text, '') AS due_date,
    COALESCE(payment_date::text, '') AS payment_date,
    COALESCE(is_late, false) AS is_late
FROM payroll_remittances
WHERE fiscal_year = :year
  AND (
      ABS(COALESCE(payment_amount, 0) - COALESCE(calculated_total_remittance,
      0)) > 0.01
      OR ABS(COALESCE(variance, 0)) > 0.01
      OR COALESCE(reconciled, false) = false
  )
ORDER BY remittance_month
LIMIT 1000
""",
    ),
    AuditCheck(
        key="remittance_late",
        title="Late Payroll Remittances",
        category="Payroll",
        severity="MEDIUM",
        reminder="Late remittances can trigger CRA penalties and interest.",
        sql="""
SELECT
    fiscal_year,
    remittance_month,
    COALESCE(due_date::text, '') AS due_date,
    COALESCE(payment_date::text, '') AS payment_date,
    ROUND(COALESCE(payment_amount, 0)::numeric, 2) AS payment_amount,
    COALESCE(payment_reference, '') AS payment_reference,
    COALESCE(status, '') AS status
FROM payroll_remittances
WHERE fiscal_year = :year
  AND due_date IS NOT NULL
  AND payment_date IS NOT NULL
  AND payment_date > due_date
ORDER BY remittance_month
LIMIT 1000
""",
    ),
    AuditCheck(
        key="owner_draw_review",
        title="Owner Draw Classification Review",
        category="Owner Tax",
        severity="MEDIUM",
        reminder=(
            "Owner-related spend should be consistently "
            "classified for T1/T2 treatment."
        ),
        sql="""
SELECT
    receipt_id,
    COALESCE(receipt_date::text, '') AS receipt_date,
    COALESCE(vendor_name, '') AS vendor_name,
    ROUND(COALESCE(gross_amount, 0)::numeric, 2) AS gross_amount,
    COALESCE(gl_code, '') AS gl_code,
    COALESCE(description, '') AS description,
    COALESCE(business_personal, '') AS business_personal,
    COALESCE(is_personal_purchase, false) AS is_personal_purchase,
    ROUND(COALESCE(owner_personal_amount, 0)::numeric,
    2) AS owner_personal_amount
FROM receipts
WHERE fiscal_year = :year
  AND (
    COALESCE(description, '') ILIKE '%owner%'
    OR COALESCE(description, '') ILIKE '%personal%'
    OR COALESCE(vendor_name, '') ILIKE '%owner%'
    OR COALESCE(gl_code, '') IN ('3020', '5880')
  )
ORDER BY receipt_date, receipt_id
LIMIT 2000
""",
    ),
    AuditCheck(
        key="t2_expense_exclusions",
        title="T2 Deductibility Exclusion Hits",
        category="T2",
        severity="MEDIUM",
        reminder=(
            "Validate personal/non-deductible exclusions "
            "and supporting notes."
        ),
        sql="""
SELECT
    receipt_id,
    COALESCE(receipt_date::text, '') AS receipt_date,
    COALESCE(vendor_name, '') AS vendor_name,
    ROUND(COALESCE(gross_amount, 0)::numeric, 2) AS gross_amount,
    COALESCE(gl_code, '') AS gl_code,
    COALESCE(description, '') AS description,
    COALESCE(is_personal_purchase, false) AS is_personal_purchase,
    ROUND(COALESCE(owner_personal_amount, 0)::numeric,
    2) AS owner_personal_amount,
    COALESCE(exclude_from_reports, false) AS exclude_from_reports,
    COALESCE(business_personal, '') AS business_personal
FROM receipts
WHERE fiscal_year = :year
  AND (
    COALESCE(is_personal_purchase, false) = true
    OR COALESCE(owner_personal_amount, 0) > 0
    OR COALESCE(exclude_from_reports, false) = true
    OR COALESCE(gl_code, '') IN ('3020', '5880', '2910', '2550', '2560')
  )
ORDER BY receipt_date, receipt_id
LIMIT 3000
""",
    ),
]


class AuditRunnerThread(QThread):
    finished_single = pyqtSignal(list, list)
    finished_summary = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(
        self,
        db_conn,
        mode: str,
        year: int,
        sql: str = "",
        checks: list[AuditCheck] | None = None,
    ) -> None:
        super().__init__()
        self.db_conn = db_conn
        self.mode = mode
        self.year = year
        self.sql = sql
        self.checks = checks or []

    @staticmethod
    def _render_sql(sql: str, year: int) -> str:
        return sql.replace(":year", str(year))

    @staticmethod
    def _is_safe_sql(sql: str) -> bool:
        text = (sql or "").strip().lower()
        if not text:
            return False
        return text.startswith("select") or text.startswith("with")

    def run(self) -> None:
        try:
            if self.mode == "single":
                rendered = self._render_sql(self.sql, self.year)
                if not self._is_safe_sql(rendered):
                    raise ValueError(
                        "Only SELECT/CTE queries are allowed in the editor."
                    )
                with self.db_conn.cursor() as cur:
                    cur.execute(rendered)
                    rows = cur.fetchall()
                    columns = [d[0] for d in cur.description]
                self.finished_single.emit(columns, rows)
                return

            if self.mode == "summary":
                summary_rows: list[dict] = []
                with self.db_conn.cursor() as cur:
                    for chk in self.checks:
                        rendered = self._render_sql(chk.sql, self.year)
                        if not self._is_safe_sql(rendered):
                            continue
                        cur.execute(f"SELECT COUNT(*) FROM ({rendered}) q")
                        count = int(cur.fetchone()[0] or 0)
                        summary_rows.append(
                            {
                                "key": chk.key,
                                "title": chk.title,
                                "category": chk.category,
                                "severity": chk.severity,
                                "issue_count": count,
                            }
                        )
                self.finished_summary.emit(summary_rows)
                return

            raise ValueError(f"Unknown runner mode: {self.mode}")
        except Exception as exc:
            self.failed.emit(str(exc))


class YearEndManagementWidget(QWidget):
    """Mass-audit year-end cockpit for T1/T2/T4 and reconciliation"
    "readiness."""

    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self._thread: AuditRunnerThread | None = None
        self._current_columns: list[str] = []
        self._current_rows: list[tuple] = []
        self._summary_by_key: dict[str, dict] = {}
        self._score_state = "PENDING"
        self._score_value = 0
        self._check_index_by_key = {c.key: c for c in CHECKS}
        self._init_ui()
        self._load_checks()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)

        self._build_header(root)
        self._build_control_row(root)

        splitter = QSplitter()
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

    def _build_header(self, root: QVBoxLayout) -> None:
        title = QLabel(
            "Year-End Management System (T1/T2/T4 + Reconciliation)"
        )
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        subtitle = QLabel(
            "Run guided accounting audits, edit SQL checks, and close"
            "findings with reviewer prompts."
        )
        subtitle.setStyleSheet("color: #555;")
        root.addWidget(title)
        root.addWidget(subtitle)

    def _build_control_row(self, root: QVBoxLayout) -> None:
        control_row = QHBoxLayout()
        control_row.addWidget(QLabel("Tax / Fiscal Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2099)
        self.year_spin.setValue(max(2000, date.today().year - 1))
        control_row.addWidget(self.year_spin)

        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["ALL", "HIGH", "MEDIUM", "LOW"])
        self.severity_filter.currentTextChanged.connect(self._apply_filter)
        control_row.addWidget(QLabel("Severity:"))
        control_row.addWidget(self.severity_filter)

        self.run_selected_btn = QPushButton("Run Selected Check")
        self.run_selected_btn.clicked.connect(self._run_selected)
        control_row.addWidget(self.run_selected_btn)

        self.run_summary_btn = QPushButton("Run All Summary")
        self.run_summary_btn.clicked.connect(self._run_summary)
        control_row.addWidget(self.run_summary_btn)

        self.load_default_sql_btn = QPushButton("Reset SQL")
        self.load_default_sql_btn.clicked.connect(self._reset_sql)
        control_row.addWidget(self.load_default_sql_btn)

        self.export_btn = QPushButton("Export Results CSV")
        self.export_btn.clicked.connect(self._export_csv)
        self.export_btn.setEnabled(False)
        control_row.addWidget(self.export_btn)

        self.package_btn = QPushButton("Generate CRA Filing Package")
        self.package_btn.clicked.connect(self._generate_cra_package)
        control_row.addWidget(self.package_btn)

        control_row.addStretch()
        root.addLayout(control_row)

    def _build_left_panel(self) -> QWidget:
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.check_list = QListWidget()
        self.check_list.currentItemChanged.connect(self._on_check_selected)
        left_layout.addWidget(QLabel("Audit Checks"))
        left_layout.addWidget(self.check_list)

        checklist_group = QGroupBox("Year-End Completion Checklist")
        checklist_layout = QFormLayout(checklist_group)
        self.chk_gl = QCheckBox("GL balancing reviewed")
        self.chk_expense = QCheckBox("Expense coding reviewed")
        self.chk_payroll = QCheckBox("Payroll/T4 reconciliation reviewed")
        self.chk_t2 = QCheckBox("T2 deductibility exclusions reviewed")
        self.chk_bank = QCheckBox("Bank reconciliation reviewed")
        checklist_layout.addRow(self.chk_gl)
        checklist_layout.addRow(self.chk_expense)
        checklist_layout.addRow(self.chk_payroll)
        checklist_layout.addRow(self.chk_t2)
        checklist_layout.addRow(self.chk_bank)
        left_layout.addWidget(checklist_group)

        self.progress_label = QLabel("Checklist completion: 0/5")
        self.progress_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(self.progress_label)

        score_group = QGroupBox("Filing Readiness Scorecard")
        score_layout = QFormLayout(score_group)
        self.score_state_label = QLabel("PENDING")
        self.score_value_label = QLabel("0 / 100")
        self.score_blockers_label = QLabel("Hard blockers: not evaluated")
        self.score_hint_label = QLabel(
            "Run All Summary to calculate readiness."
        )
        self.score_hint_label.setWordWrap(True)
        score_layout.addRow("Status:", self.score_state_label)
        score_layout.addRow("Score:", self.score_value_label)
        score_layout.addRow("Blockers:", self.score_blockers_label)
        score_layout.addRow("Action:", self.score_hint_label)
        left_layout.addWidget(score_group)

        for box in (
            self.chk_gl,
            self.chk_expense,
            self.chk_payroll,
            self.chk_t2,
            self.chk_bank,
        ):
            box.stateChanged.connect(self._update_checklist_progress)

        return left_panel

    def _build_right_panel(self) -> QWidget:
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        meta_box = QGroupBox("Selected Check")
        meta_layout = QGridLayout(meta_box)
        self.meta_title = QLabel("-")
        self.meta_cat = QLabel("-")
        self.meta_sev = QLabel("-")
        self.meta_note = QLabel("-")
        self.meta_note.setWordWrap(True)
        meta_layout.addWidget(QLabel("Title:"), 0, 0)
        meta_layout.addWidget(self.meta_title, 0, 1)
        meta_layout.addWidget(QLabel("Category:"), 1, 0)
        meta_layout.addWidget(self.meta_cat, 1, 1)
        meta_layout.addWidget(QLabel("Severity:"), 2, 0)
        meta_layout.addWidget(self.meta_sev, 2, 1)
        meta_layout.addWidget(QLabel("Reminder:"), 3, 0)
        meta_layout.addWidget(self.meta_note, 3, 1)
        right_layout.addWidget(meta_box)

        right_layout.addWidget(QLabel("Editable SQL (SELECT/CTE only):"))
        self.sql_editor = QTextEdit()
        self.sql_editor.setMinimumHeight(220)
        right_layout.addWidget(self.sql_editor)

        self.status_label = QLabel("Select a check and run it.")
        self.status_label.setStyleSheet("color: #555;")
        right_layout.addWidget(self.status_label)

        fix_group = QGroupBox("Guided Fix Workflow")
        fix_layout = QVBoxLayout(fix_group)
        self.fix_steps = QTextEdit()
        self.fix_steps.setReadOnly(True)
        self.fix_steps.setPlaceholderText(
            "Run a check, click a row, then use guided actions to fix issues"
            "quickly."
        )
        self.fix_steps.setMinimumHeight(130)
        fix_layout.addWidget(self.fix_steps)
        fix_btn_row = QHBoxLayout()
        self.fix_suggest_btn = QPushButton("Suggest Fix Steps")
        self.fix_suggest_btn.clicked.connect(self._suggest_fix_steps)
        fix_btn_row.addWidget(self.fix_suggest_btn)
        self.fix_open_btn = QPushButton("Open Linked Record")
        self.fix_open_btn.clicked.connect(self._open_linked_record)
        fix_btn_row.addWidget(self.fix_open_btn)
        self.fix_followup_btn = QPushButton("Copy Follow-Up SQL")
        self.fix_followup_btn.clicked.connect(self._copy_follow_up_sql)
        fix_btn_row.addWidget(self.fix_followup_btn)
        fix_btn_row.addStretch()
        fix_layout.addLayout(fix_btn_row)
        right_layout.addWidget(fix_group)

        self.result_table = QTableWidget()
        self.result_table.itemSelectionChanged.connect(self._suggest_fix_steps)
        right_layout.addWidget(self.result_table)
        return right_panel

    def _load_checks(self) -> None:
        self.check_list.clear()
        for check in CHECKS:
            item = QListWidgetItem(f"[{check.severity}] {check.title}")
            item.setData(32, check.key)
            self.check_list.addItem(item)
        if self.check_list.count() > 0:
            self.check_list.setCurrentRow(0)

    def _apply_filter(self) -> None:
        sev = self.severity_filter.currentText().strip().upper()
        for i in range(self.check_list.count()):
            item = self.check_list.item(i)
            key = item.data(32)
            check = self._check_index_by_key.get(key)
            if not check:
                continue
            hidden = sev != "ALL" and check.severity.upper() != sev
            item.setHidden(hidden)

    def _update_checklist_progress(self) -> None:
        boxes = [
            self.chk_gl,
            self.chk_expense,
            self.chk_payroll,
            self.chk_t2,
            self.chk_bank,
        ]
        done = sum(1 for b in boxes if b.isChecked())
        self.progress_label.setText(f"Checklist completion: {done}/5")
        self._refresh_scorecard()

    def _on_check_selected(self, current, _previous) -> None:
        if not current:
            return
        check = self._check_index_by_key.get(current.data(32))
        if not check:
            return
        self.meta_title.setText(check.title)
        self.meta_cat.setText(check.category)
        self.meta_sev.setText(check.severity)
        self.meta_note.setText(check.reminder)
        self.sql_editor.setPlainText(check.sql.strip())
        self.status_label.setText("Ready to run selected check.")
        self._suggest_fix_steps()

    def _set_busy(self, busy: bool) -> None:
        self.run_selected_btn.setEnabled(not busy)
        self.run_summary_btn.setEnabled(not busy)
        self.load_default_sql_btn.setEnabled(not busy)

    def _run_selected(self) -> None:
        item = self.check_list.currentItem()
        if not item:
            QMessageBox.information(
                self, "Audit", "Select an audit check first."
            )
            return

        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "Audit", "SQL cannot be empty.")
            return

        self._set_busy(True)
        self.status_label.setText("Running selected audit check...")
        self._thread = AuditRunnerThread(
            self.db.conn,
            mode="single",
            year=int(self.year_spin.value()),
            sql=sql,
        )
        self._thread.finished_single.connect(self._on_single_finished)
        self._thread.failed.connect(self._on_thread_error)
        self._thread.start()

    def _run_summary(self) -> None:
        self._set_busy(True)
        self.status_label.setText("Running full summary across all checks...")
        self._thread = AuditRunnerThread(
            self.db.conn,
            mode="summary",
            year=int(self.year_spin.value()),
            checks=CHECKS,
        )
        self._thread.finished_summary.connect(self._on_summary_finished)
        self._thread.failed.connect(self._on_thread_error)
        self._thread.start()

    def _on_single_finished(self, columns: list[str], rows: list[tuple]) -> None:
        self._set_busy(False)
        self._current_columns = columns
        self._current_rows = rows
        self._fill_table(columns, rows)
        self.export_btn.setEnabled(bool(rows))
        self.status_label.setText(f"Returned {len(rows)} row(s).")

        current = self.check_list.currentItem()
        if not current:
            return
        check = self._check_index_by_key.get(current.data(32))
        if not check:
            return

        if len(rows) > 0 and check.severity.upper() == "HIGH":
            QMessageBox.warning(
                self,
                "High-Severity Findings",
                f"{check.title} returned {len(rows)} row(s).\n\n"
                f"Reminder: {check.reminder}\n\n"
                "Action: review these rows before year-end filing.",
            )
        elif len(rows) == 0:
            QMessageBox.information(
                self, "Audit", f"No findings for: {check.title}"
            )

    def _on_summary_finished(self, summary_rows: list[dict]) -> None:
        self._set_busy(False)
        columns = ["key", "title", "category", "severity", "issue_count"]
        rows = [tuple(r[c] for c in columns) for r in summary_rows]
        self._current_columns = columns
        self._current_rows = rows
        self._fill_table(columns, rows)
        self._summary_by_key = {str(r.get("key", "")): r for r in summary_rows}
        self._refresh_scorecard()
        self.export_btn.setEnabled(bool(rows))

        total_issues = sum(int(r.get("issue_count", 0)) for r in summary_rows)
        high_issues = sum(
            int(r.get("issue_count", 0))
            for r in summary_rows
            if str(r.get("severity", "")).upper() == "HIGH"
        )
        self.status_label.setText(
            f"Summary complete. Total issues: {total_issues}. High-severity"
            f"issues: {high_issues}."
        )

        if high_issues > 0:
            QMessageBox.warning(
                self,
                "Summary Alert",
                f"High-severity issues detected: {high_issues}.\n"
                "Open each HIGH check and resolve before T2/T4 submission"
                "package finalization.",
            )
        else:
            QMessageBox.information(
                self, "Summary", "No high-severity issues found."
            )

    def _on_thread_error(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText(f"Error: {message}")
        QMessageBox.critical(self, "Audit Query Error", message)

    def _fill_table(self, columns: list[str], rows: list[tuple]) -> None:
        self.result_table.clear()
        self.result_table.setColumnCount(len(columns))
        self.result_table.setHorizontalHeaderLabels(columns)
        self.result_table.setRowCount(len(rows))

        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row):
                text = "" if value is None else str(value)
                self.result_table.setItem(r_idx, c_idx, QTableWidgetItem(text))

        self.result_table.resizeColumnsToContents()

    def _refresh_scorecard(self) -> None:
        if not self._summary_by_key:
            self._score_state = "PENDING"
            self._score_value = 0
            self.score_state_label.setText("PENDING")
            self.score_value_label.setText("0 / 100")
            self.score_blockers_label.setText("Hard blockers: not evaluated")
            self.score_hint_label.setText(
                "Run All Summary to calculate readiness."
            )
            self.score_state_label.setStyleSheet(
                "font-weight: bold; color: #666;"
            )
            return

        checks_with_findings = sum(
            1
            for r in self._summary_by_key.values()
            if int(r.get("issue_count", 0)) > 0
        )
        high_with_findings = sum(
            1
            for r in self._summary_by_key.values()
            if str(r.get("severity", "")).upper() == "HIGH"
            and int(r.get("issue_count", 0)) > 0
        )
        hard_blockers = [
            key
            for key in HARD_BLOCKER_KEYS
            if int(self._summary_by_key.get(key, {}).get("issue_count", 0)) > 0
        ]

        boxes = [
            self.chk_gl,
            self.chk_expense,
            self.chk_payroll,
            self.chk_t2,
            self.chk_bank,
        ]
        checklist_done = sum(1 for b in boxes if b.isChecked())
        checklist_penalty = max(0, 5 - checklist_done) * 3
        score = max(
            0,
            100
            - (checks_with_findings * 4)
            - (high_with_findings * 5)
            - checklist_penalty,
        )

        if hard_blockers:
            state = "RED"
            color = "#b71c1c"
            hint = (
                "Resolve all hard blockers before filing submission packages."
            )
        elif high_with_findings > 0 or checklist_done < 5:
            state = "YELLOW"
            color = "#b26a00"
            hint = (
                "Address remaining high findings and "
                "complete checklist sign-off."
            )
        else:
            state = "GREEN"
            color = "#1b5e20"
            hint = "Ready for controlled filing package generation and review."

        self._score_state = state
        self._score_value = int(score)
        self.score_state_label.setText(state)
        self.score_state_label.setStyleSheet(
            f"font-weight: bold; color: {color};"
        )
        self.score_value_label.setText(f"{int(score)} / 100")
        self.score_blockers_label.setText(
            f"Hard blockers: {len(hard_blockers)}"
            + (" (" + ", ".join(hard_blockers) + ")" if hard_blockers else "")
        )
        self.score_hint_label.setText(hint)

    def _selected_result_context(self) -> object:
        row = self.result_table.currentRow()
        if row < 0 or not self._current_columns:
            return None, {}
        values = {}
        for i, col in enumerate(self._current_columns):
            item = self.result_table.item(row, i)
            values[col] = item.text() if item else ""
        return row, values

    def _active_check(self) -> object:
        current = self.check_list.currentItem()
        if not current:
            return None
        return self._check_index_by_key.get(current.data(32))

    def _suggest_fix_steps(self) -> None:
        check = self._active_check()
        if not check:
            self.fix_steps.setPlainText("Select an audit check first.")
            return

        _row, values = self._selected_result_context()
        key = check.key
        primary_id = ""
        for candidate in (
            "receipt_id",
            "transaction_id",
            "employee_id",
            "income_id",
            "remittance_id",
            "charter_id",
        ):
            if values.get(candidate):
                primary_id = f"{candidate}={values.get(candidate)}"
                break

        base = [
            f"Check: {check.title}",
            f"Severity: {check.severity}",
            f"Reminder: {check.reminder}",
            "",
            "Workflow:",
            "1) Validate source document / ledger support.",
            "2) Correct mapping/classification at source record.",
            "3) Re-run this check and confirm row cleared.",
            "4) Document reviewer initials and date in filing notes.",
        ]
        if primary_id:
            base.append(f"Target row: {primary_id}")

        if key in {
            "receipts_missing_gl",
            "receipts_gst_anomalies",
            "owner_draw_review",
            "t2_expense_exclusions",
        }:
            base.append(
                "Suggested fix: update receipts GL coding and deductible"
                "flags, then verify T2 treatment."
            )
        elif key in {"bank_unreconciled"}:
            base.append(
                "Suggested fix: attach receipt/payment/accounting linkage and"
                "set reconciliation status."
            )
        elif key in {
            "payroll_t4_variance",
            "payroll_missing_sin",
            "remittance_variance",
            "remittance_late",
        }:
            base.append(
                "Suggested fix: reconcile payroll source rows, T4 boxes, and"
                "remittance evidence."
            )
        elif key in {"gl_unbalanced_txn", "gl_plug_entries"}:
            base.append(
                "Suggested fix: reverse/adjust imbalanced journal lines with"
                "proper memo + approver note."
            )
        elif key == "income_unmatched_charters":
            base.append(
                "Suggested fix: link income row to charter_id/reserve_number"
                "and verify revenue category."
            )

        self.fix_steps.setPlainText("\n".join(base))

    def _main_window(self) -> object:
        win = self.window()
        return win if win is not None else None

    def _navigate_accounting_subtab(self, sub_tab_name: str) -> object:
        win = self._main_window()
        if win and hasattr(win, "navigate_to_accounting_subtab"):
            ok = bool(win.navigate_to_accounting_subtab(sub_tab_name))
            if ok:
                QApplication.processEvents()
            return ok
        return False

    def _navigate_operations_subtab(self, sub_tab_name: str) -> object:
        win = self._main_window()
        if win and hasattr(win, "navigate_to_operations_subtab"):
            ok = bool(win.navigate_to_operations_subtab(sub_tab_name))
            if ok:
                QApplication.processEvents()
            return ok
        return False

    def _resolve_charter_id_from_income_id(self, income_id: int) -> int | None:
        """Resolve an income_ledger row to charter_id for deep-link"
        "navigation."""

        try:
            iid = int(income_id)
        except (TypeError, ValueError):
            return None

        try:
            cur = self.db.conn.cursor()
            cur.execute(
                """
                SELECT charter_id
                FROM income_ledger
                WHERE income_id = %s
                LIMIT 1
                """,
                (iid,),
            )
            row = cur.fetchone()
            cur.close()
            if row and row[0] is not None:
                return int(row[0])
        except Exception as exc:
            logger.warning(
                "Failed to resolve charter id from income_id %s: %s",
                iid,
                exc,
            )
            return None
        return None

    def _open_deep_link(
        self,
        *,
        values: dict,
        value_key: str,
        parse_value,
        navigate,
        loader,
        success_message,
        warning_prefix: str,
    ) -> bool:
        """Run a single deep-link flow and return True on successful open."""

        if not values.get(value_key):
            return False

        try:
            target_value = parse_value(values.get(value_key))
            if not navigate():
                return False
            if loader(target_value):
                self.status_label.setText(success_message(target_value))
                return True
        except Exception as exc:
            logger.warning("%s deep-link failed: %s", warning_prefix, exc)
        return False

    @staticmethod
    def _linkable_keys() -> tuple[str, ...]:
        return (
            "receipt_id",
            "transaction_id",
            "employee_id",
            "income_id",
            "remittance_id",
            "charter_id",
            "reserve_number",
        )

    def _has_linkable_value(self, values: dict) -> bool:
        return any(values.get(candidate) for candidate in self._linkable_keys())

    def _copy_first_navigation_key(self, values: dict) -> None:
        target = ""
        for candidate in self._linkable_keys():
            if values.get(candidate):
                target = f"{candidate}={values.get(candidate)}"
                break
        if target:
            QApplication.clipboard().setText(target)
            QMessageBox.information(
                self,
                "Open Linked Record",
                "Direct open could not be completed for this row.\n"
                "Navigation key copied to clipboard:\n"
                f"{target}",
            )

    def _open_receipt_link(self, values: dict, win) -> bool:
        return self._open_deep_link(
            values=values,
            value_key="receipt_id",
            parse_value=int,
            navigate=lambda: self._navigate_accounting_subtab(
                "💰 Receipts & Invoices"
            ),
            loader=lambda rid: bool(
                win
                and hasattr(win, "accounting_widget")
                and hasattr(win.accounting_widget, "open_receipt_by_id")
                and win.accounting_widget.open_receipt_by_id(rid)
            ),
            success_message=lambda rid: f"Opened receipt #{rid} in Receipts tab.",
            warning_prefix="Receipt",
        )

    def _open_transaction_link(self, values: dict, win) -> bool:
        return self._open_deep_link(
            values=values,
            value_key="transaction_id",
            parse_value=int,
            navigate=lambda: self._navigate_accounting_subtab(
                "🏦 Enhanced Banking Manager"
            ),
            loader=lambda txn_id: bool(
                win
                and hasattr(win, "enhanced_banking_manager")
                and hasattr(
                    win.enhanced_banking_manager,
                    "focus_transaction_id",
                )
                and win.enhanced_banking_manager.focus_transaction_id(txn_id)
            ),
            success_message=lambda txn_id: (
                f"Opened banking transaction #{txn_id}."
            ),
            warning_prefix="Banking transaction",
        )

    def _open_payroll_employee_link(self, values: dict, win) -> bool:
        return self._open_deep_link(
            values=values,
            value_key="employee_id",
            parse_value=int,
            navigate=lambda: self._navigate_accounting_subtab("💵 Payroll Entry"),
            loader=lambda emp_id: bool(
                win
                and hasattr(win, "payroll_entry_widget")
                and hasattr(win.payroll_entry_widget, "focus_employee_id")
                and win.payroll_entry_widget.focus_employee_id(
                    emp_id, int(self.year_spin.value())
                )
            ),
            success_message=lambda emp_id: f"Opened payroll employee #{emp_id}.",
            warning_prefix="Payroll employee",
        )

    def _open_remittance_link(self, values: dict, win) -> bool:
        return self._open_deep_link(
            values=values,
            value_key="remittance_id",
            parse_value=int,
            navigate=lambda: self._navigate_accounting_subtab(
                "🧮 Payroll Remittances"
            ),
            loader=lambda remittance_id: bool(
                win
                and hasattr(win, "payroll_remittances_widget")
                and hasattr(
                    win.payroll_remittances_widget,
                    "focus_remittance_id",
                )
                and win.payroll_remittances_widget.focus_remittance_id(
                    remittance_id
                )
            ),
            success_message=lambda remittance_id: (
                f"Opened payroll remittance #{remittance_id}."
            ),
            warning_prefix="Payroll remittance",
        )

    def _open_charter_link(self, values: dict, win) -> bool:
        charter_candidate = values.get("charter_id")
        if not charter_candidate and values.get("income_id"):
            charter_candidate = self._resolve_charter_id_from_income_id(
                values.get("income_id")
            )

        if not charter_candidate:
            return False

        try:
            charter_id = int(charter_candidate)
            if self._navigate_operations_subtab("📡 Dispatch"):
                if (
                    win
                    and hasattr(win, "charter_form")
                    and hasattr(win.charter_form, "load_charter")
                ):
                    win.charter_form.load_charter(charter_id)
                    self.status_label.setText(f"Opened charter #{charter_id}.")
                    return True
        except Exception as exc:
            logger.warning("Charter deep-link failed: %s", exc)
        return False

    def _open_linked_record(self) -> None:
        check = self._active_check()
        if not check:
            QMessageBox.information(
                self, "Open Linked Record", "Select an audit check first."
            )
            return

        _row, values = self._selected_result_context()
        if not values:
            QMessageBox.information(
                self, "Open Linked Record", "Select a result row first."
            )
            return

        if not self._has_linkable_value(values):
            QMessageBox.information(
                self,
                "Open Linked Record",
                "No linkable id column found on selected row.",
            )
            return

        win = self._main_window()

        if self._open_receipt_link(values, win):
            return

        if self._open_transaction_link(values, win):
            return

        if self._open_payroll_employee_link(values, win):
            return

        if self._open_remittance_link(values, win):
            return

        if self._open_charter_link(values, win):
            return

        self._copy_first_navigation_key(values)

    def _copy_follow_up_sql(self) -> None:
        check = self._active_check()
        if not check:
            return
        follow_up = (
            "-- Paste into SQL tool to verify fix after update\n"
            "-- Uses same fiscal year as wizard\n"
            + check.sql.strip().replace(
                ":year", str(int(self.year_spin.value()))
            )
        )
        QApplication.clipboard().setText(follow_up)
        QMessageBox.information(
            self, "Follow-Up SQL", "Verification SQL copied to clipboard."
        )

    def _run_check_sync(self, check_key: str) -> object:
        check = self._check_index_by_key.get(check_key)
        if not check:
            return [], []
        rendered = check.sql.replace(":year", str(int(self.year_spin.value())))
        with self.db.conn.cursor() as cur:
            cur.execute(rendered)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]
        return columns, rows

    @staticmethod
    def _write_csv(path: Path, columns: list[str], rows: list[tuple]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow(row)

    def _build_cra_package_dir(self, year: int, stamp: str) -> Path:
        package_dir = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "cra"
            / "packages"
            / f"{year}_{stamp}"
        )
        package_dir.mkdir(parents=True, exist_ok=True)
        return package_dir

    def _build_audit_summary_rows(self) -> tuple[list[str], list[tuple]]:
        summary_cols = [
            "key",
            "title",
            "category",
            "severity",
            "issue_count",
        ]
        summary_rows = [
            (
                r.get("key", ""),
                r.get("title", ""),
                r.get("category", ""),
                r.get("severity", ""),
                r.get("issue_count", 0),
            )
            for r in self._summary_by_key.values()
        ]
        return summary_cols, summary_rows

    def _write_cra_check_exports(self, package_dir: Path) -> None:
        check_exports = {
            "remittance_variance": "pd7a_variance.csv",
            "payroll_t4_variance": "t4_variance.csv",
            "t2_expense_exclusions": "t2_deductibility_exclusions.csv",
        }
        for check_key, file_name in check_exports.items():
            columns, rows = self._run_check_sync(check_key)
            self._write_csv(package_dir / file_name, columns, rows)

    def _checklist_completion_count(self) -> int:
        boxes = [
            self.chk_gl,
            self.chk_expense,
            self.chk_payroll,
            self.chk_t2,
            self.chk_bank,
        ]
        return sum(1 for box in boxes if box.isChecked())

    def _hard_blocker_keys(self) -> list[str]:
        return [
            key
            for key in HARD_BLOCKER_KEYS
            if int(self._summary_by_key.get(key, {}).get("issue_count", 0))
            > 0
        ]

    def _build_signoff_payload(
        self, year: int, stamp: str, hard_blockers: list[str]
    ) -> dict:
        checklist_done = self._checklist_completion_count()
        return {
            "generated_on": stamp,
            "fiscal_year": year,
            "readiness": {
                "status": self._score_state,
                "score": self._score_value,
                "hard_blockers": hard_blockers,
            },
            "checklist": {
                "gl_balancing_reviewed": self.chk_gl.isChecked(),
                "expense_coding_reviewed": self.chk_expense.isChecked(),
                "payroll_t4_reviewed": self.chk_payroll.isChecked(),
                "t2_exclusions_reviewed": self.chk_t2.isChecked(),
                "bank_reconciliation_reviewed": self.chk_bank.isChecked(),
                "completion_count": checklist_done,
            },
        }

    def _write_cra_package_readme(
        self, package_dir: Path, year: int, stamp: str, hard_blockers: list[str]
    ) -> None:
        with open(package_dir / "README.txt", "w", encoding="utf-8") as f:
            f.write(
                "Year-End Filing Package\n"
                "=======================\n"
                f"Fiscal Year: {year}\n"
                f"Generated: {stamp}\n"
                f"Readiness: {self._score_state}({self._score_value}/100)\n"
                f"Hard Blockers: {len(hard_blockers)}\n\n"
                "Files:\n"
                "- audit_summary.csv\n"
                "- pd7a_variance.csv\n"
                "- t4_variance.csv\n"
                "- t2_deductibility_exclusions.csv\n"
                "- filing_signoff.json\n"
            )

    def _show_cra_package_status(self, package_dir: Path, hard_blockers: list[str]) -> None:
        if hard_blockers:
            QMessageBox.warning(
                self,
                "CRA Package Generated (Blockers Exist)",
                f"Package created at:\n{package_dir}\n\n"
                f"Hard blockers still open: {len(hard_blockers)}\n"
                "Resolve blockers before final filing submission.",
            )
            return

        QMessageBox.information(
            self,
            "CRA Package Generated",
            f"Package created at:\n{package_dir}\n\nNo hard blockers"
            f"detected.",
        )

    def _generate_cra_package(self) -> None:
        if not self._summary_by_key:
            QMessageBox.warning(
                self,
                "CRA Package",
                "Run All Summary first so readiness and blocker status are"
                "current.",
            )
            return

        year = int(self.year_spin.value())
        stamp = date.today().isoformat()
        package_dir = self._build_cra_package_dir(year, stamp)

        try:
            summary_cols, summary_rows = self._build_audit_summary_rows()
            self._write_csv(
                package_dir / "audit_summary.csv", summary_cols, summary_rows
            )

            self._write_cra_check_exports(package_dir)

            hard_blockers = self._hard_blocker_keys()
            signoff = self._build_signoff_payload(year, stamp, hard_blockers)
            with open(
                package_dir / "filing_signoff.json", "w", encoding="utf-8"
            ) as f:
                json.dump(signoff, f, indent=2)

            self._write_cra_package_readme(package_dir, year, stamp, hard_blockers)
            self._show_cra_package_status(package_dir, hard_blockers)
        except Exception as exc:
            QMessageBox.critical(self, "CRA Package Error", str(exc))

    def _reset_sql(self) -> None:
        item = self.check_list.currentItem()
        if not item:
            return
        check = self._check_index_by_key.get(item.data(32))
        if not check:
            return
        self.sql_editor.setPlainText(check.sql.strip())

    def _export_csv(self) -> None:
        if not self._current_columns or not self._current_rows:
            QMessageBox.information(self, "Export", "No results to export.")
            return

        default_name = (
            f"year_end_audit_{self.year_spin.value()}_"
            f"{date.today().isoformat()}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audit CSV", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._current_columns)
                for row in self._current_rows:
                    writer.writerow(row)

            # Also auto-save a working snapshot under data/audit for audit
            # trail continuity.
            audit_dir = Path(__file__).resolve().parents[1] / "data" / "audit"
            audit_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = audit_dir / (
                f"year_end_snapshot_{self.year_spin.value()}_"
                f"{date.today().isoformat()}.csv"
            )
            with open(snapshot_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._current_columns)
                for row in self._current_rows:
                    writer.writerow(row)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Saved CSV:\n{path}\n\nSnapshot:\n{snapshot_path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
