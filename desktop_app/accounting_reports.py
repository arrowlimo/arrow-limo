"""
Accounting-focused report widgets using direct database queries.
Includes: Trial Balance, Journal Explorer, Bank Reconciliation,
Vehicle Performance, Driver Cost, Fleet Maintenance, P&L Summary.
"""

import logging
from typing import Any

from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from multi_date_filter_builder import MultiDateFilterBuilder
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from reporting_base import BaseReportWidget

logger = logging.getLogger(__name__)
_normalized_gl_view_initialized = False


def _ensure_normalized_general_ledger_view(cur) -> bool:
    """Create or refresh a normalized ledger view for reporting."""

    global _normalized_gl_view_initialized

    cur.execute("SELECT to_regclass('public.general_ledger')")
    if cur.fetchone()[0] is None:
        return False

    if _normalized_gl_view_initialized:
        return True

    cur.execute(
        """
        CREATE OR REPLACE VIEW general_ledger_normalized AS
        WITH base AS (
            SELECT
                gl.*,
                COALESCE(gl.transaction_date, gl.date) AS entry_date,
                TRIM(COALESCE(gl.account, '')) AS raw_account,
                CASE
                    WHEN TRIM(COALESCE(gl.account, '')) ~ '^\\d+'
                        THEN SUBSTRING(TRIM(gl.account) FROM '^\\d+')
                    ELSE NULL
                END AS leading_digits,
                CASE
                    WHEN TRIM(COALESCE(gl.account, '')) ~ '^\\d+\\s+'
                        THEN BTRIM(REGEXP_REPLACE(
                            TRIM(gl.account), '^\\d+\\s*', ''))
                    ELSE NULL
                END AS name_after_digits
            FROM general_ledger gl
        ),
        resolved AS (
            SELECT
                b.*,
                COALESCE(
                    coa_code.account_code,
                    coa_bank.account_code,
                    coa_name_after.account_code,
                    coa_name.account_code,
                    CASE
                        WHEN b.raw_account ~ '^\\d+'
                        THEN SUBSTRING(b.raw_account FROM '^\\d+')
                        ELSE NULL
                    END,
                    NULLIF(b.raw_account, ''),
                    'NO-ACCOUNT'
                ) AS normalized_account_code,
                COALESCE(
                    NULLIF(b.name_after_digits, ''),
                    coa_code.account_name,
                    coa_bank.account_name,
                    coa_name_after.account_name,
                    coa_name.account_name,
                    NULLIF(b.raw_account, ''),
                    'Uncategorized'
                ) AS normalized_account_name,
                COALESCE(
                    coa_code.account_name,
                    coa_bank.account_name,
                    coa_name_after.account_name,
                    coa_name.account_name,
                    NULLIF(b.name_after_digits, ''),
                    NULLIF(b.raw_account, ''),
                    'Uncategorized'
                ) AS canonical_account_name,
                COALESCE(
                    NULLIF(TRIM(b.account_type), ''),
                    coa_code.account_type,
                    coa_bank.account_type,
                    coa_name_after.account_type,
                    coa_name.account_type,
                    'Unknown'
                ) AS normalized_account_type
            FROM base b
            LEFT JOIN chart_of_accounts coa_code
                ON coa_code.account_code = b.leading_digits
            LEFT JOIN chart_of_accounts coa_bank
                ON coa_bank.bank_account_number = b.leading_digits
            LEFT JOIN chart_of_accounts coa_name
                ON LOWER(coa_name.account_name) = LOWER(b.raw_account)
            LEFT JOIN chart_of_accounts coa_name_after
                ON b.name_after_digits IS NOT NULL
               AND LOWER(coa_name_after.account_name)
               = LOWER(b.name_after_digits)
        )
        SELECT
            id AS gl_id,
            entry_date,
            raw_account,
            normalized_account_code AS account_code,
            normalized_account_name AS account_name,
            canonical_account_name,
            normalized_account_type AS account_type,
            CASE
                WHEN normalized_account_code ~ '^1' THEN 'Asset'
                WHEN normalized_account_code ~ '^2' THEN 'Liability'
                WHEN normalized_account_code ~ '^3' THEN 'Equity'
                WHEN normalized_account_code ~ '^4' THEN 'Revenue'
                WHEN normalized_account_code ~ '^[5-8]' THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%payable%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%loan%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%visa%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%mastercard%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%gst/hst%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%tax payable%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%bank%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%checking%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%deposit account%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%cash%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%petty cash%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%prepaid%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%receivable%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE 'limousines & busses%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%amort%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%vehicle%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%supplies%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%fuel%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%rent%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%expense%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%travel%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%utilities%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%materials%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%parking%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%hospitality%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name)
                    LIKE '%charter client purchases%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) = 'auto'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name)
                    LIKE '%repair and maintenance%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name)
                    LIKE '%taxes and licenses%'
                    THEN 'Expense'
                WHEN LOWER(normalized_account_type) LIKE '%income%'
                    THEN 'Revenue'
                WHEN LOWER(normalized_account_type) LIKE '%revenue%'
                    THEN 'Revenue'
                WHEN LOWER(normalized_account_type) LIKE '%expense%'
                    THEN 'Expense'
                WHEN LOWER(normalized_account_type) LIKE '%asset%'
                    THEN 'Asset'
                WHEN LOWER(normalized_account_type) LIKE '%liabil%'
                    THEN 'Liability'
                WHEN LOWER(normalized_account_type) LIKE '%equity%'
                    THEN 'Equity'
                ELSE 'Unknown'
            END AS account_class,
            COALESCE(NULLIF(TRIM(num), ''), id::text) AS ref_number,
            COALESCE(
                NULLIF(TRIM(supplier), ''),
                NULLIF(TRIM(customer), ''),
                NULLIF(TRIM(employee), ''),
                NULLIF(TRIM(name), ''),
                ''
            ) AS party_name,
            COALESCE(NULLIF(TRIM(name), ''), '') AS source_name,
            COALESCE(NULLIF(TRIM(memo_description), ''), '') AS memo,
            COALESCE(NULLIF(TRIM(transaction_type), ''),
                     'Journal Entry') AS transaction_type,
            COALESCE(supplier, '') AS supplier,
            COALESCE(employee, '') AS employee,
            COALESCE(customer, '') AS customer,
            COALESCE(debit, 0) AS debit,
            COALESCE(credit, 0) AS credit,
            COALESCE(balance, 0) AS balance,
            imported_at,
            source_file
        FROM resolved
        """
    )
    _normalized_gl_view_initialized = True
    return True


class _DateRangeMixin:
    """Reusable start/end date controls for report widgets."""

    def _init_date_controls(self, months_back: int = 12) -> object:
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Start:"))
        self.start_date = StandardDateEdit(prefer_month_text=True)
        self.start_date.setDate(QDate.currentDate().addMonths(-months_back))
        ctrl.addWidget(self.start_date)
        ctrl.addWidget(QLabel("End:"))
        self.end_date = StandardDateEdit(prefer_month_text=True)
        self.end_date.setDate(QDate.currentDate())
        ctrl.addWidget(self.end_date)
        refresh_btn = QPushButton("Apply")
        refresh_btn.clicked.connect(self.refresh)
        ctrl.addWidget(refresh_btn)
        ctrl.addStretch()
        return ctrl

    def _date_range(self) -> object:
        # Fallback if date controls not initialized yet (e.g., during
        # BaseReportWidget.__init__ refresh)
        if not hasattr(
                self,
                "start_date") or not hasattr(
                self,
                "end_date") or (
                self.start_date is None
                or self.end_date is None):
            start = QDate.currentDate().addMonths(-12).toPyDate()
            end = QDate.currentDate().toPyDate()
            return start, end
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        return start, end


class GSTCollectionWidget(BaseReportWidget, _DateRangeMixin):
    """GST collected vs paid with input tax credits and net GST owed."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "GST Collected", "key": "gst_collected",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Input Tax Credits", "key": "gst_paid",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Net GST", "key": "net_gst",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Status", "key": "status"}
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "GST Collection & ITC", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT DATE_TRUNC('month', receipt_date) AS period,
                       COALESCE(SUM(gst_amount), 0) AS gst_collected
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                  AND gst_amount > 0
                GROUP BY 1
                """,
                (start, end))
            gst_map = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
            cur.execute(
                """
                SELECT DATE_TRUNC('month', receipt_date) AS period,
                       COALESCE(SUM(gst_amount), 0) AS gst_paid
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                  AND category IS NOT NULL
                  AND category != 'personal'
                  AND gst_amount > 0
                GROUP BY 1
                """,
                (start, end))
            itc_map = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
        all_periods = sorted(set(gst_map.keys()) | set(itc_map.keys()))
        data = []
        for period in all_periods:
            collected = gst_map.get(period, 0)
            paid = itc_map.get(period, 0)
            net = collected - paid
            status = "OWE" if net > 0 else ("REFUND" if net < 0 else "NONE")
            data.append({
                "period": (
                    period.date().isoformat()
                    if hasattr(period, "date") else str(period)
                ),
                "gst_collected": round(collected, 2),
                "gst_paid": round(paid, 2),
                "net_gst": round(net, 2),
                "status": status,
            })
        return sorted(data, key=lambda x: x["period"], reverse=True)


class IncomeExpenseGroupedWidget(BaseReportWidget, _DateRangeMixin):
    """Income and expenses grouped by category with subtotals."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Category", "key": "category"},
            {"header": "Type", "key": "type"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Count", "key": "count"},]
        self.db = db
        BaseReportWidget.__init__(
            self, db, "Income & Expense by Category", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            cur.execute(
                """
                SELECT
                    CONCAT(account_code, ' ',
                           canonical_account_name) AS category,
                    account_class,
                    COUNT(*) AS row_count,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN account_class = 'Revenue'
                                    THEN credit - debit
                                WHEN account_class = 'Expense'
                                    THEN debit - credit
                                ELSE 0
                            END
                        ),
                        0
                    ) AS amount
                FROM general_ledger_normalized
                WHERE entry_date BETWEEN %s AND %s
                  AND account_class IN ('Revenue', 'Expense')
                GROUP BY 1, 2
                HAVING ABS(
                    COALESCE(
                        SUM(
                            CASE
                                WHEN account_class = 'Revenue'
                                    THEN credit - debit
                                WHEN account_class = 'Expense'
                                    THEN debit - credit
                                ELSE 0
                            END
                        ),
                        0
                    )
                ) > 0.004
                ORDER BY amount DESC, category
                """,
                (start, end),
            )
            rows = cur.fetchall()

        return [
            {
                "category": row[0] or "Uncategorized",
                "type": row[1],
                "amount": float(row[3] or 0),
                "count": int(row[2] or 0),
            }
            for row in rows
        ]


class PersonalExpenseWidget(BaseReportWidget, _DateRangeMixin):
    """Personal expenses (owner draw) for personal tax reporting."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Date", "key": "receipt_date"},
            {"header": "Vendor", "key": "vendor_name"},
            {"header": "Description", "key": "description"},
            {"header": "Amount", "key": "owner_personal_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Category", "key": "category"}
        ]
        self.db = db
        BaseReportWidget.__init__(
            self, db, "Personal Expenses (Owner Draw)", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT receipt_date, vendor_name, description,
                       owner_personal_amount, category
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                  AND (owner_personal_amount > 0 OR category = 'personal')
                ORDER BY receipt_date DESC LIMIT 1000
                """,
                (start, end))
            return [{"receipt_date": str(r[0]),
                     "vendor_name": r[1] or "",
                     "description": r[2] or "",
                     "owner_personal_amount": float(r[3] or 0),
                     "category": r[4] or "personal"} for r in cur.fetchall()]


class DavidLoanAccountingWidget(BaseReportWidget, _DateRangeMixin):
    """David loan in/out ledger from categorized e-transfers."""

    def __init__(self, db) -> None:
        self.detail_columns = [
            {"header": "Date", "key": "transaction_date"},
            {"header": "Direction", "key": "direction"},
            {"header": "Flow", "key": "david_loan_flow"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Signed", "key": "signed_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Running Balance", "key": "running_balance",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "GL", "key": "gl_account_code"},
            {"header": "Description", "key": "description"},
        ]
        self.monthly_columns = [
            {"header": "Month", "key": "period"},
            {"header": "IN", "key": "in_total",
             "format": lambda v: f"${v:,.2f}"},
            {"header": "OUT", "key": "out_total",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Net", "key": "net_change",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Running Balance", "key": "running_balance",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Txns", "key": "txn_count"},
        ]
        self.db = db
        BaseReportWidget.__init__(
            self,
            db,
            "David Loan Accounting",
            self.detail_columns,
        )
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("View:"))
        self.view_mode = QComboBox()
        self.view_mode.addItem("Detail", "detail")
        self.view_mode.addItem("Monthly Summary", "monthly")
        self.view_mode.currentIndexChanged.connect(self.refresh)
        mode_row.addWidget(self.view_mode)
        mode_row.addStretch()
        layout.insertLayout(2, mode_row)

    def refresh(self) -> None:
        self._update_columns_for_mode()
        super().refresh()

    def _is_monthly_mode(self) -> bool:
        return (hasattr(self, "view_mode")
                and self.view_mode.currentData() == "monthly")

    def _update_columns_for_mode(self) -> None:
        columns = (
            self.monthly_columns if self._is_monthly_mode()
            else self.detail_columns
        )
        if self.columns != columns:
            self.set_columns(columns)

    def _has_required_columns(self, cur) -> bool:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'etransfer_transactions'
              AND column_name IN (
                  'david_loan_flow', 'gl_account_code', 'category')
            """
        )
        cols = {row[0] for row in cur.fetchall()}
        return {"david_loan_flow", "gl_account_code",
                "category"}.issubset(cols)

    def _fetch_detail_rows(self, cur, start, end) -> list[dict[str, Any]]:
        cur.execute(
            """
            SELECT et.etransfer_id,
                   et.transaction_date,
                   et.direction,
                   et.david_loan_flow,
                   COALESCE(et.amount, 0) AS amount,
                   COALESCE(et.gl_account_code, '') AS gl_account_code,
                   COALESCE(bt.description, '') AS description
            FROM etransfer_transactions et
            JOIN banking_transactions bt
            ON bt.transaction_id = et.banking_transaction_id
            WHERE et.transaction_date BETWEEN %s AND %s
              AND et.category = 'loan_payment'
              AND et.gl_account_code = '2550'
              AND et.david_loan_flow IN ('DAVID_LOAN_IN', 'DAVID_LOAN_OUT')
            ORDER BY et.transaction_date ASC, et.etransfer_id ASC
            """,
            (start, end),
        )
        rows = cur.fetchall()

        running_balance = 0.0
        output: list[dict[str, Any]] = []
        for row in rows:
            amount = float(row[4] or 0)
            signed = amount if row[2] == "IN" else -amount
            running_balance += signed
            output.append(
                {
                    "etransfer_id": row[0],
                    "transaction_date": str(row[1]),
                    "direction": row[2],
                    "david_loan_flow": row[3],
                    "amount": amount,
                    "signed_amount": round(signed, 2),
                    "running_balance": round(running_balance, 2),
                    "gl_account_code": row[5],
                    "description": row[6],
                }
            )

        output.reverse()
        return output

    def _fetch_monthly_rows(self, cur, start, end) -> list[dict[str, Any]]:
        cur.execute(
            """
            SELECT DATE_TRUNC('month', et.transaction_date) AS period,
                   COUNT(*) AS txn_count,
                   COALESCE(SUM(
                       CASE WHEN et.direction = 'IN'
                           THEN et.amount ELSE 0
                       END), 0) AS in_total,
                   COALESCE(SUM(
                       CASE WHEN et.direction = 'OUT'
                           THEN et.amount ELSE 0
                       END), 0) AS out_total
            FROM etransfer_transactions et
            WHERE et.transaction_date BETWEEN %s AND %s
              AND et.category = 'loan_payment'
              AND et.gl_account_code = '2550'
              AND et.david_loan_flow IN ('DAVID_LOAN_IN', 'DAVID_LOAN_OUT')
            GROUP BY period
            ORDER BY period ASC
            """,
            (start, end),
        )
        rows = cur.fetchall()

        running_balance = 0.0
        output: list[dict[str, Any]] = []
        for row in rows:
            in_total = float(row[2] or 0)
            out_total = float(row[3] or 0)
            net_change = in_total - out_total
            running_balance += net_change
            output.append(
                {
                    "period": (
                        row[0].date().isoformat()
                        if hasattr(row[0], "date")
                        else str(row[0])
                    ),
                    "txn_count": int(row[1] or 0),
                    "in_total": round(in_total, 2),
                    "out_total": round(out_total, 2),
                    "net_change": round(net_change, 2),
                    "running_balance": round(running_balance, 2),
                }
            )

        output.reverse()
        return output

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not self._has_required_columns(cur):
                return []

            if self._is_monthly_mode():
                return self._fetch_monthly_rows(cur, start, end)
            return self._fetch_detail_rows(cur, start, end)


class ReconciliationStatusWidget(BaseReportWidget, _DateRangeMixin):
    """Banking transactions reconciliation status - matched vs unmatched."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Date", "key": "transaction_date"},
            {"header": "Description", "key": "description"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Status", "key": "reconciliation_status"},
            {"header": "Linked Receipt", "key": "receipt_id"},
            {"header": "Days Unmatched", "key": "days_unmatched"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Reconciliation Status", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=6))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT transaction_id, transaction_date, description,
                    ABS(COALESCE(debit_amount, 0)
                        - COALESCE(credit_amount, 0)) AS amount,
                    COALESCE(reconciliation_status,
                             'unreconciled') AS status,
                    receipt_id,
                    EXTRACT(DAY FROM NOW()
                        - transaction_date)::INT AS days_unmatched
                FROM banking_transactions
                WHERE transaction_date BETWEEN %s AND %s
                ORDER BY transaction_date DESC LIMIT 1000
                """,
                (start, end))
            return [{"transaction_id": r[0],
                     "transaction_date": str(r[1]),
                     "description": r[2] or "",
                     "amount": float(r[3] or 0),
                     "reconciliation_status": r[4] or "unreconciled",
                     "receipt_id": r[5],
                     "days_unmatched": int(r[6] or 0)} for r in cur.fetchall()]


class ReceiptLedgerWidget(BaseReportWidget):
    """Receipt ledger with multi-date, GL, and vendor
    filters plus drill-down editing."""

    def __init__(self, db) -> None:
        self.detail_columns = [
            {"header": "Receipt ID", "key": "receipt_id"},
            {"header": "Date", "key": "receipt_date"},
            {"header": "Vendor", "key": "vendor_name"},
            {"header": "Description", "key": "description"},
            {"header": "Category", "key": "category"},
            {"header": "GL Code", "key": "gl_account_code"},
            {"header": "GL Name", "key": "gl_account_name"},
            {"header": "Gross", "key": "gross_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "GST", "key": "gst_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Net", "key": "net_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Personal", "key": "owner_personal_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "GST Code", "key": "gst_code"},]
        self.vendor_columns = [
            {"header": "Vendor", "key": "vendor_name"},
            {"header": "Receipts", "key": "receipt_count"},
            {"header": "Gross", "key": "gross_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "GST", "key": "gst_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Net", "key": "net_amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Personal", "key": "owner_personal_amount",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        self._init_in_progress = True
        BaseReportWidget.__init__(
            self, db, "Receipt Ledger", self.detail_columns)

        layout: QVBoxLayout = self.layout()

        # Multi-date filter builder
        self.date_filter_builder = MultiDateFilterBuilder()

        # Filter controls
        filter_row = QHBoxLayout()

        self.all_dates_check = QCheckBox("All dates")
        self.all_dates_check.setChecked(True)
        filter_row.addWidget(self.all_dates_check)

        filter_row.addWidget(QLabel("GL Filter:"))
        self.gl_mode = QComboBox()
        self.gl_mode.addItem("All GL codes", "all")
        self.gl_mode.addItem("GL only", "gl_only")
        self.gl_mode.addItem("Non-GL only", "non_gl_only")
        self.gl_mode.addItem("Selected GL codes", "selected")
        filter_row.addWidget(self.gl_mode)

        self.gl_codes_input = QLineEdit()
        self.gl_codes_input.setPlaceholderText("GL codes (comma-separated)")
        self.gl_codes_input.setMaximumWidth(220)
        filter_row.addWidget(self.gl_codes_input)

        filter_row.addWidget(QLabel("Vendor Filter:"))
        self.vendor_mode = QComboBox()
        self.vendor_mode.addItem("All vendors", "all")
        self.vendor_mode.addItem("Selected vendors", "selected")
        filter_row.addWidget(self.vendor_mode)

        self.vendor_input = QLineEdit()
        self.vendor_input.setPlaceholderText("Vendor names (comma-separated)")
        self.vendor_input.setMaximumWidth(260)
        filter_row.addWidget(self.vendor_input)

        self.group_by_vendor_check = QCheckBox("Group by vendor")
        self.group_by_vendor_check.setChecked(True)
        filter_row.addWidget(self.group_by_vendor_check)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.refresh)
        filter_row.addWidget(apply_btn)

        filter_row.addStretch()

        filters_layout = QVBoxLayout()
        filters_layout.addWidget(self.date_filter_builder)
        filters_layout.addLayout(filter_row)

        layout.insertLayout(1, filters_layout)

        self._init_in_progress = False
        self.refresh()

    def refresh(self) -> None:
        self._update_columns_for_grouping()
        super().refresh()

    def _update_columns_for_grouping(self) -> None:
        if not hasattr(self, 'group_by_vendor_check'):
            return
        group_mode = self._should_group_by_vendor()
        columns = self.vendor_columns if group_mode else self.detail_columns
        if self.columns != columns:
            self.set_columns(columns)

    def _should_group_by_vendor(self) -> bool:
        return self.group_by_vendor_check.isChecked(
        ) and self.vendor_mode.currentData() == "all"

    def _parse_csv_list(self, raw: str) -> list[str]:
        if not raw:
            return []
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        return [p for p in parts if p]

    def _build_date_filter(self, params: list[Any]) -> str:
        if self.all_dates_check.isChecked():
            return ""
        date_ranges = self.date_filter_builder.calculate_date_ranges()
        if not date_ranges:
            return ""
        clauses = []
        for start_qdate, end_qdate in date_ranges:
            clauses.append("(receipt_date BETWEEN %s AND %s)")
            params.extend([start_qdate.toPyDate(), end_qdate.toPyDate()])
        return "(" + " OR ".join(clauses) + ")"

    def _build_gl_filter(self, params: list[Any]) -> str:
        mode = self.gl_mode.currentData()
        if mode == "gl_only":
            return "(gl_account_code IS NOT NULL AND gl_account_code <> '')"
        if mode == "non_gl_only":
            return "(gl_account_code IS NULL OR gl_account_code = '')"
        if mode == "selected":
            codes = self._parse_csv_list(self.gl_codes_input.text())
            if not codes:
                return "1=0"
            placeholders = ",".join(["%s"] * len(codes))
            params.extend(codes)
            return f"gl_account_code IN ({placeholders})"
        return ""

    def _build_vendor_filter(self, params: list[Any]) -> str:
        mode = self.vendor_mode.currentData()
        if mode != "selected":
            return ""
        vendors = self._parse_csv_list(self.vendor_input.text())
        if not vendors:
            return "1=0"
        clauses = []
        for vendor in vendors:
            clauses.append("vendor_name ILIKE %s")
            params.append(f"%{vendor}%")
        return "(" + " OR ".join(clauses) + ")"

    def fetch_rows(self) -> list[dict[str, Any]]:
        if getattr(self, "_init_in_progress", False):
            return []

        params: list[Any] = []
        filters = []

        date_filter = self._build_date_filter(params)
        if date_filter:
            filters.append(date_filter)

        gl_filter = self._build_gl_filter(params)
        if gl_filter:
            filters.append(gl_filter)

        vendor_filter = self._build_vendor_filter(params)
        if vendor_filter:
            filters.append(vendor_filter)

        where_sql = " AND ".join(["1=1"] + filters)

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if self._should_group_by_vendor():
                cur.execute(
                    f"""
                    SELECT vendor_name,
                           COUNT(*) AS receipt_count,
                           COALESCE(SUM(gross_amount), 0) AS gross_amount,
                           COALESCE(SUM(gst_amount), 0) AS gst_amount,
                           COALESCE(SUM(COALESCE(
                               net_amount,
                               gross_amount - COALESCE(gst_amount, 0)
                           )), 0) AS net_amount,
                           COALESCE(SUM(owner_personal_amount),
                               0) AS owner_personal_amount
                    FROM receipts
                    WHERE {where_sql}
                    GROUP BY vendor_name
                    ORDER BY vendor_name
                    """,
                    params,)
                rows = cur.fetchall()
                return [
                    {
                        "vendor_name": r[0] or "",
                        "receipt_count": int(r[1] or 0),
                        "gross_amount": float(r[2] or 0),
                        "gst_amount": float(r[3] or 0),
                        "net_amount": float(r[4] or 0),
                        "owner_personal_amount": float(r[5] or 0), }
                    for r in rows]

            cur.execute(
                f"""
                SELECT receipt_id, receipt_date,
                       vendor_name, description, category,
                       COALESCE(gl_account_code, '') AS gl_account_code,
                       COALESCE(gl_account_name, '') AS gl_account_name,
                       COALESCE(gross_amount, 0) AS gross_amount,
                       COALESCE(gst_amount, 0) AS gst_amount,
                       COALESCE(net_amount,
                           gross_amount - COALESCE(gst_amount, 0),
                           0) AS net_amount,
                       COALESCE(gst_code, '') AS gst_code,
                       COALESCE(owner_personal_amount, 0)
                           AS owner_personal_amount
                FROM receipts
                WHERE {where_sql}
                ORDER BY receipt_date DESC, receipt_id DESC
                LIMIT 2000
                """,
                params,)
            rows = cur.fetchall()
        return [
            {
                "receipt_id": r[0],
                "receipt_date": str(r[1]),
                "vendor_name": r[2] or "",
                "description": r[3] or "",
                "category": r[4] or "",
                "gl_account_code": r[5],
                "gl_account_name": r[6],
                "gross_amount": float(r[7]),
                "gst_amount": float(r[8]),
                "net_amount": float(r[9]),
                "gst_code": r[10],
                "owner_personal_amount": float(r[11]), }
            for r in rows]

    def open_drill_down_dialog(self, index) -> None:
        if self._should_group_by_vendor():
            return
        super().open_drill_down_dialog(index)

    def save_row_corrections(self, row_index: int, row_data: dict[str, Any]) -> object:
        receipt_id = row_data.get("receipt_id")
        if not receipt_id:
            return

        def _to_float(val) -> object:
            try:
                return float(val) if val != "" else None
            except Exception:
                return None

        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                UPDATE receipts
                SET receipt_date = %s,
                    vendor_name = %s,
                    description = %s,
                    category = %s,
                    gl_account_code = %s,
                    gl_account_name = %s,
                    gross_amount = %s,
                    gst_amount = %s,
                    net_amount = %s,
                    gst_code = %s,
                    owner_personal_amount = %s
                WHERE receipt_id = %s
                """,
                (
                    row_data.get("receipt_date"),
                    row_data.get("vendor_name"),
                    row_data.get("description"),
                    row_data.get("category"),
                    row_data.get("gl_account_code") or None,
                    row_data.get("gl_account_name") or None,
                    _to_float(row_data.get("gross_amount")),
                    _to_float(row_data.get("gst_amount")),
                    _to_float(row_data.get("net_amount")),
                    row_data.get("gst_code") or None,
                    _to_float(row_data.get("owner_personal_amount")),
                    receipt_id,),)


class VendorReceiptBankingAuditWidget(BaseReportWidget, _DateRangeMixin):
    """Vendor-focused receipt ledger with flagged no-receipt banking items."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Row Type", "key": "row_type"},
            {"header": "Date", "key": "row_date"},
            {"header": "Vendor", "key": "vendor_name"},
            {"header": "Description", "key": "description"},
            {"header": "GL Code", "key": "gl_account_code"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Verified Flags", "key": "verified_flags"},
            {"header": "Banking Link", "key": "banking_link"},
            {"header": "Receipt ID", "key": "receipt_id"},
            {"header": "Bank Txn ID", "key": "banking_transaction_id"},
            {"header": "Review", "key": "review_flag"},
        ]
        self.db = db
        BaseReportWidget.__init__(
            self, db, "Vendor Receipts + Banking Audit", columns)

        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Vendor:"))
        self.vendor_input = QLineEdit()
        self.vendor_input.setPlaceholderText("Select vendor text (required)")
        self.vendor_input.setMaximumWidth(320)
        ctrl.addWidget(self.vendor_input)

        ctrl.addWidget(QLabel("Sort:"))
        self.sort_field = QComboBox()
        self.sort_field.addItem("Date", "date")
        self.sort_field.addItem("Amount", "amount")
        self.sort_field.addItem("GL Code", "gl")
        ctrl.addWidget(self.sort_field)

        self.sort_order = QComboBox()
        self.sort_order.addItem("Descending", "DESC")
        self.sort_order.addItem("Ascending", "ASC")
        ctrl.addWidget(self.sort_order)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.refresh)
        ctrl.addWidget(apply_btn)
        ctrl.addStretch()

        layout.insertLayout(2, ctrl)

    def _has_banking_receipt_id_column(self, cur) -> bool:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'banking_transactions'
              AND column_name = 'receipt_id'
            LIMIT 1
            """
        )
        return cur.fetchone() is not None

    def _receipt_sort_sql(self) -> str:
        direction = self.sort_order.currentData() or "DESC"
        if direction not in ("ASC", "DESC"):
            direction = "DESC"
        sort_map = {
            "date": "r.receipt_date",
            "amount": "r.gross_amount",
            "gl": "COALESCE(r.gl_account_code, '')",
        }
        sort_col = sort_map.get(
            self.sort_field.currentData(), "r.receipt_date")
        return f"{sort_col} {direction}, r.receipt_id {direction}"

    @staticmethod
    def _flags_text(
            is_verified_banking, is_paper_verified, verified_by_edit) -> str:
        flags = []
        if is_verified_banking:
            flags.append("Banking")
        if is_paper_verified:
            flags.append("Paper")
        if verified_by_edit:
            flags.append("Edit")
        return ", ".join(flags) if flags else "Unverified"

    def fetch_rows(self) -> list[dict[str, Any]]:
        if not hasattr(self, 'vendor_input'):
            return []
        vendor_filter = (self.vendor_input.text() or "").strip()
        if not vendor_filter:
            return []

        start, end = self._date_range()
        rows: list[dict[str, Any]] = []

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                f"""
                SELECT
                    r.receipt_id,
                    r.receipt_date,
                    COALESCE(r.vendor_name, ''),
                    COALESCE(r.description, ''),
                    COALESCE(r.gl_account_code, ''),
                    COALESCE(r.gross_amount, 0),
                    COALESCE(r.is_verified_banking, FALSE),
                    COALESCE(r.is_paper_verified, FALSE),
                    COALESCE(r.verified_by_edit, FALSE),
                    r.banking_transaction_id
                FROM receipts r
                WHERE r.receipt_date BETWEEN %s AND %s
                  AND COALESCE(r.vendor_name, '') ILIKE %s
                ORDER BY {self._receipt_sort_sql()}
                """,
                (start, end, f"%{vendor_filter}%"),
            )
            while True:
                receipt_rows = cur.fetchmany(500)
                if not receipt_rows:
                    break
                for rr in receipt_rows:
                    rows.append(
                        {
                            "row_type": "RECEIPT",
                            "row_date": str(rr[1]),
                            "vendor_name": rr[2],
                            "description": rr[3],
                            "gl_account_code": rr[4],
                            "amount": float(rr[5] or 0),
                            "verified_flags": self._flags_text(
                                rr[6], rr[7], rr[8]),
                            "banking_link": (
                                f"Linked #{rr[9]}" if rr[9] else "No Link"),
                            "receipt_id": rr[0],
                            "banking_transaction_id": rr[9] or "",
                            "review_flag": "",
                        }
                    )

            has_receipt_id = self._has_banking_receipt_id_column(cur)
            no_receipt_extra = (
                "AND bt.receipt_id IS NULL" if has_receipt_id else ""
            )

            cur.execute(
                f"""
                SELECT
                    bt.transaction_id,
                    bt.transaction_date,
                    COALESCE(bt.description, ''),
                    ABS(COALESCE(bt.debit_amount, 0)
                        - COALESCE(bt.credit_amount, 0)) AS amount,
                    COALESCE(bt.check_number::text, '')
                FROM banking_transactions bt
                LEFT JOIN receipts r
                ON r.banking_transaction_id = bt.transaction_id
                WHERE bt.transaction_date BETWEEN %s AND %s
                  AND COALESCE(bt.description, '') ILIKE %s
                  AND COALESCE(bt.debit_amount, 0) > 0
                  AND r.receipt_id IS NULL
                  {no_receipt_extra}
                ORDER BY bt.transaction_date DESC,
                    amount DESC, bt.transaction_id DESC
                """,
                (start, end, f"%{vendor_filter}%"),
            )
            while True:
                banking_rows = cur.fetchmany(500)
                if not banking_rows:
                    break
                for br in banking_rows:
                    check_ref = f" | CHQ {br[4]}" if br[4] else ""
                    rows.append(
                        {
                            "row_type": "BANKING_NO_RECEIPT",
                            "row_date": str(br[1]),
                            "vendor_name": vendor_filter,
                            "description": f"{br[2]}{check_ref}",
                            "gl_account_code": "",
                            "amount": float(br[3] or 0),
                            "verified_flags": "N/A",
                            "banking_link": f"Unlinked BT #{br[0]}",
                            "receipt_id": "",
                            "banking_transaction_id": br[0],
                            "review_flag": "REVIEW",
                        }
                    )

        return rows


class GeneralLedgerWidget(BaseReportWidget, _DateRangeMixin):
    """Full general ledger with normalized account codes and names."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "GL Code", "key": "gl_code"},
            {"header": "Account Name", "key": "gl_name"},
            {"header": "Date", "key": "txn_date"},
            {"header": "Ref #", "key": "ref_number"},
            {"header": "Vendor / Client", "key": "party"},
            {"header": "Description", "key": "description"},
            {"header": "Debit", "key": "debit",
                "format": lambda v: f"${v:,.2f}" if v else ""},
            {"header": "Credit", "key": "credit",
                "format": lambda v: f"${v:,.2f}" if v else ""},
            {"header": "GL Balance", "key": "running_balance",
                "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "General Ledger", columns)

        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("GL Filter:"))
        self.gl_filter_input = QLineEdit()
        self.gl_filter_input.setPlaceholderText(
            "GL code(s) comma-sep (blank = all)")
        self.gl_filter_input.setMaximumWidth(300)
        ctrl.addWidget(self.gl_filter_input)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.refresh)
        ctrl.addWidget(apply_btn)
        ctrl.addStretch()
        layout.insertLayout(2, ctrl)

    def _parse_gl_filter(self) -> list:
        raw = getattr(self, "gl_filter_input", None)
        if raw is None:
            return []
        text = (raw.text() or "").strip()
        return (
            [g.strip() for g in text.split(",") if g.strip()]
            if text else []
        )

    def _coa_exists(self, cur) -> bool:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'chart_of_accounts'
            LIMIT 1
            """
        )
        return cur.fetchone() is not None

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        gl_codes = self._parse_gl_filter()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            gl_params: list = [start, end]
            gl_where = ""
            if gl_codes:
                placeholders = ",".join(["%s"] * len(gl_codes))
                gl_where = f"AND gln.account_code IN ({placeholders})"
                gl_params.extend(gl_codes)

            cur.execute(
                f"""
                SELECT
                    gln.account_code AS gl_code,
                    gln.account_name AS gl_name,
                    gln.entry_date AS txn_date,
                    gln.ref_number,
                    gln.party_name AS party,
                    gln.memo AS description,
                    gln.debit,
                    gln.credit,
                    gln.gl_id AS sort_id
                FROM general_ledger_normalized gln
                WHERE gln.entry_date BETWEEN %s AND %s
                  {gl_where}
                ORDER BY 1, 3, 9
                """,
                gl_params,
            )
            all_tuples = [
                (r[0], r[1], r[2], r[3], r[4], r[5], float(
                    r[6] or 0), float(r[7] or 0), int(r[8]))
                for r in cur.fetchall()
            ]

        all_tuples.sort(
            key=lambda x: (x[0], str(x[2]) if x[2] else "", x[8]))

        rows: list[dict[str, Any]] = []
        current_gl: str | None = None
        running = 0.0
        for (
            gl_code, gl_name, txn_date, ref,
            party, desc, debit, credit, _sort_id
        ) in all_tuples:
            if gl_code != current_gl:
                current_gl = gl_code
                running = 0.0
            running += debit - credit
            rows.append(
                {
                    "gl_code": gl_code,
                    "gl_name": gl_name,
                    "txn_date": str(txn_date) if txn_date else "",
                    "ref_number": ref,
                    "party": party,
                    "description": desc,
                    "debit": round(debit, 2) if debit else None,
                    "credit": round(credit, 2) if credit else None,
                    "running_balance": round(running, 2),
                }
            )

        return rows


class TrialBalanceWidget(BaseReportWidget, _DateRangeMixin):
    """Trial balance aggregated by account as of end date."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Account Name", "key": "account_name"},
            {"header": "Account", "key": "account"},
            {"header": "Type", "key": "account_type"},
            {"header": "Debit", "key": "total_debit",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Credit", "key": "total_credit",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Balance", "key": "balance",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Trial Balance", columns)
        # Insert date controls above toolbar
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

    def fetch_rows(self) -> list[dict[str, Any]]:
        _, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            cur.execute(
                """
                SELECT
                    gln.account_code AS account,
                    gln.canonical_account_name AS account_name,
                    gln.account_type,
                    COALESCE(SUM(gln.debit), 0) AS total_debit,
                    COALESCE(SUM(gln.credit), 0) AS total_credit,
                    COALESCE(SUM(gln.debit - gln.credit), 0) AS balance
                FROM general_ledger_normalized gln
                WHERE gln.entry_date <= %s
                GROUP BY 1, 2, 3
                HAVING ABS(COALESCE(SUM(gln.debit - gln.credit), 0)) > 0.004
                    OR ABS(COALESCE(SUM(gln.debit), 0)) > 0.004
                    OR ABS(COALESCE(SUM(gln.credit), 0)) > 0.004
                ORDER BY 1, 2
                """,
                (end,),
            )
            rows = cur.fetchall()

        return [
            {
                "account_name": r[1],
                "account": r[0],
                "account_type": r[2],
                "total_debit": float(r[3] or 0),
                "total_credit": float(r[4] or 0),
                "balance": float(r[5] or 0),
            }
            for r in rows
        ]


class BalanceSheetWidget(BaseReportWidget, _DateRangeMixin):
    """Balance sheet from normalized general ledger balances."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Section", "key": "section"},
            {"header": "Account", "key": "account"},
            {"header": "Account Name", "key": "account_name"},
            {"header": "Type", "key": "account_type"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Balance Sheet", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

    def fetch_rows(self) -> list[dict[str, Any]]:
        _, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            cur.execute(
                """
                SELECT
                    account_class,
                    account_code,
                    canonical_account_name,
                    account_type,
                    COALESCE(SUM(debit), 0) AS total_debit,
                    COALESCE(SUM(credit), 0) AS total_credit
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                  AND account_class IN ('Asset', 'Liability', 'Equity')
                GROUP BY 1, 2, 3, 4
                HAVING ABS(COALESCE(SUM(debit - credit), 0)) > 0.004
                    OR ABS(COALESCE(SUM(debit), 0)) > 0.004
                    OR ABS(COALESCE(SUM(credit), 0)) > 0.004
                ORDER BY
                    CASE account_class
                        WHEN 'Asset' THEN 1
                        WHEN 'Liability' THEN 2
                        WHEN 'Equity' THEN 3
                        ELSE 9
                    END,
                    account_code,
                    canonical_account_name
                """,
                (end,),
            )
            raw_rows = cur.fetchall()

            cur.execute(
                """
                SELECT COALESCE(SUM(credit - debit), 0)
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                  AND account_class = 'Revenue'
                """,
                (end,),
            )
            revenue_total = float(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(debit - credit), 0)
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                  AND account_class = 'Expense'
                """,
                (end,),
            )
            expense_total = float(cur.fetchone()[0] or 0)

        rows: list[dict[str, Any]] = []
        section_totals = {"Asset": 0.0, "Liability": 0.0, "Equity": 0.0}

        for (
            account_class, account_code, account_name,
            account_type, total_debit, total_credit
        ) in raw_rows:
            if account_class == "Asset":
                amount = float(total_debit or 0) - float(total_credit or 0)
                section = "Assets"
            elif account_class == "Liability":
                amount = float(total_credit or 0) - float(total_debit or 0)
                section = "Liabilities"
            else:
                amount = float(total_credit or 0) - float(total_debit or 0)
                section = "Equity"

            if abs(amount) <= 0.004:
                continue

            section_totals[account_class] += amount
            rows.append(
                {
                    "section": section,
                    "account": account_code,
                    "account_name": account_name,
                    "account_type": account_type,
                    "amount": round(amount, 2),
                }
            )

        current_earnings = revenue_total - expense_total
        if abs(current_earnings) > 0.004:
            section_totals["Equity"] += current_earnings
            rows.append(
                {
                    "section": "Equity",
                    "account": "CURR-EARN",
                    "account_name": "Current Period Earnings",
                    "account_type": "Equity",
                    "amount": round(current_earnings, 2),
                }
            )

        rows.extend(
            [
                {
                    "section": "Assets",
                    "account": "TOTAL",
                    "account_name": "Total Assets",
                    "account_type": "Summary",
                    "amount": round(section_totals["Asset"], 2),
                },
                {
                    "section": "Liabilities",
                    "account": "TOTAL",
                    "account_name": "Total Liabilities",
                    "account_type": "Summary",
                    "amount": round(section_totals["Liability"], 2),
                },
                {
                    "section": "Equity",
                    "account": "TOTAL",
                    "account_name": "Total Equity",
                    "account_type": "Summary",
                    "amount": round(section_totals["Equity"], 2),
                },
                {
                    "section": "Balance Check",
                    "account": "L+E",
                    "account_name": "Liabilities + Equity",
                    "account_type": "Summary",
                    "amount": round(
                        section_totals["Liability"]
                        + section_totals["Equity"], 2),
                },
                {
                    "section": "Balance Check",
                    "account": "DIFF",
                    "account_name": "Assets minus Liabilities and Equity",
                    "account_type": "Summary",
                    "amount": round(
                        section_totals["Asset"] - (
                            section_totals["Liability"]
                            + section_totals["Equity"]
                        ), 2),
                },
            ]
        )

        section_order = {"Assets": 1, "Liabilities": 2,
                         "Equity": 3, "Balance Check": 4}
        return sorted(
            rows,
            key=lambda row: (
                section_order.get(row["section"], 9),
                row["account"] == "TOTAL",
                row["account"] == "L+E",
                row["account"] == "DIFF",
                row["account"],
                row["account_name"],
            ),
        )


class YearEndCloseWidget(BaseReportWidget, _DateRangeMixin):
    """Worksheet for preparing year-end close
    and retained earnings rollforward."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Section", "key": "section"},
            {"header": "Line", "key": "line"},
            {"header": "Account", "key": "account"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}" if v is not None else ""},
            {"header": "Detail", "key": "detail"},
        ]
        self.db = db
        BaseReportWidget.__init__(
            self, db, "Year-End Close Worksheet", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))
        action_row = QHBoxLayout()
        post_btn = QPushButton("Post Closing Entry")
        post_btn.clicked.connect(self.post_year_end_close)
        action_row.addWidget(post_btn)
        reverse_btn = QPushButton("Reverse Closing Entry")
        reverse_btn.clicked.connect(self.reverse_year_end_close)
        action_row.addWidget(reverse_btn)
        action_row.addStretch()
        layout.insertLayout(2, action_row)

    def _close_reference(self, start, end) -> str:
        return f"YEAR-END-CLOSE-{start.isoformat()}-{end.isoformat()}"

    def _reverse_reference(self, close_reference: str) -> str:
        return f"{close_reference}-REV"

    def _build_close_plan(self) -> dict[str, Any]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return {
                    "start": start,
                    "end": end,
                    "opening_rows": [],
                    "closing_rows": [],
                    "revenue_total": 0.0,
                    "expense_total": 0.0,
                    "net_income": 0.0,
                    "retained_code": None,
                    "retained_account": None,
                    "posting_lines": [],
                    "already_posted": False,
                    "already_reversed": False,
                    "reference": self._close_reference(start, end),
                    "reverse_reference": self._reverse_reference(
                        self._close_reference(start, end)),
                }

            cur.execute(
                """
                SELECT
                    account_code,
                    canonical_account_name,
                    COALESCE(SUM(credit - debit), 0) AS balance
                FROM general_ledger_normalized
                WHERE entry_date < %s
                  AND account_class = 'Equity'
                GROUP BY 1, 2
                HAVING ABS(COALESCE(SUM(credit - debit), 0)) > 0.004
                ORDER BY 1, 2
                """,
                (start,),
            )
            opening_rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    account_code,
                    canonical_account_name,
                    COALESCE(SUM(credit - debit), 0) AS balance
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                  AND account_class = 'Equity'
                GROUP BY 1, 2
                HAVING ABS(COALESCE(SUM(credit - debit), 0)) > 0.004
                ORDER BY 1, 2
                """,
                (end,),
            )
            closing_rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    account_code,
                    canonical_account_name,
                    COALESCE(SUM(credit - debit), 0) AS balance
                FROM general_ledger_normalized
                WHERE entry_date BETWEEN %s AND %s
                  AND account_class = 'Revenue'
                GROUP BY 1, 2
                HAVING ABS(COALESCE(SUM(credit - debit), 0)) > 0.004
                ORDER BY 1, 2
                """,
                (start, end),
            )
            revenue_rows = [(r[0], r[1], float(r[2] or 0))
                            for r in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    account_code,
                    canonical_account_name,
                    COALESCE(SUM(debit - credit), 0) AS balance
                FROM general_ledger_normalized
                WHERE entry_date BETWEEN %s AND %s
                  AND account_class = 'Expense'
                GROUP BY 1, 2
                HAVING ABS(COALESCE(SUM(debit - credit), 0)) > 0.004
                ORDER BY 1, 2
                """,
                (start, end),
            )
            expense_rows = [(r[0], r[1], float(r[2] or 0))
                            for r in cur.fetchall()]

            cur.execute(
                """
                SELECT account_code, account_name
                FROM chart_of_accounts
                WHERE LOWER(account_name) LIKE '%retained earnings%'
                ORDER BY
                CASE WHEN account_code = '3030' THEN 0 ELSE 1 END,
                account_code
                LIMIT 1
                """
            )
            retained_row = cur.fetchone()

            reference = self._close_reference(start, end)
            reverse_reference = self._reverse_reference(reference)
            cur.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM accounting_entries WHERE reference = %s
                ) OR EXISTS(
                    SELECT 1 FROM general_ledger WHERE num = %s
                )
                """,
                (reference, reference),
            )
            already_posted = bool(cur.fetchone()[0])

            cur.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM accounting_entries WHERE reference = %s
                ) OR EXISTS(
                    SELECT 1 FROM general_ledger WHERE num = %s
                )
                """,
                (reverse_reference, reverse_reference),
            )
            already_reversed = bool(cur.fetchone()[0])

        revenue_total = sum(row[2] for row in revenue_rows)
        expense_total = sum(row[2] for row in expense_rows)
        net_income = revenue_total - expense_total

        posting_lines: list[dict[str, Any]] = []
        for account_code, account_name, balance in revenue_rows:
            posting_lines.append(
                {
                    "account_code": account_code,
                    "account_name": account_name,
                    "debit": round(balance, 2),
                    "credit": 0.0,
                    "detail": f"Close revenue account {account_name}",
                    "account_type": "Revenue",
                }
            )
        for account_code, account_name, balance in expense_rows:
            posting_lines.append(
                {
                    "account_code": account_code,
                    "account_name": account_name,
                    "debit": 0.0,
                    "credit": round(balance, 2),
                    "detail": f"Close expense account {account_name}",
                    "account_type": "Expense",
                }
            )

        retained_code = retained_row[0] if retained_row else None
        retained_account = retained_row[1] if retained_row else None
        if retained_code and abs(net_income) > 0.004:
            posting_lines.append(
                {
                    "account_code": retained_code,
                    "account_name": retained_account,
                    "debit": (
                        round(abs(net_income), 2)
                        if net_income < 0 else 0.0),
                    "credit": (
                        round(abs(net_income), 2)
                        if net_income >= 0 else 0.0),
                    "detail": "Close net income to retained earnings",
                    "account_type": "Equity",
                }
            )

        return {
            "start": start,
            "end": end,
            "opening_rows": opening_rows,
            "closing_rows": closing_rows,
            "revenue_total": revenue_total,
            "expense_total": expense_total,
            "net_income": net_income,
            "retained_code": retained_code,
            "retained_account": retained_account,
            "posting_lines": posting_lines,
            "already_posted": already_posted,
            "already_reversed": already_reversed,
            "reference": reference,
            "reverse_reference": reverse_reference,
        }

    def post_year_end_close(self) -> None:
        """Post the year-end close plan to accounting_entries
    and general_ledger."""
        plan = self._build_close_plan()

        if plan["already_posted"]:
            QMessageBox.information(
                self,
                "Already Posted",
                f"Closing entry {plan['reference']} is already"
                f" present in the books.",
            )
            return

        if not plan["retained_code"]:
            QMessageBox.warning(
                self,
                "Retained Earnings Missing",
                "No retained earnings account was found in"
                " chart_of_accounts. Add one before posting"
                " a close entry.",
            )
            return

        if not plan["posting_lines"]:
            QMessageBox.information(
                self,
                "Nothing To Post",
                "The selected period has no revenue or expense"
                " balances to close.",
            )
            return

        debit_total = round(sum(line["debit"]
                            for line in plan["posting_lines"]), 2)
        credit_total = round(sum(line["credit"]
                             for line in plan["posting_lines"]), 2)
        if abs(debit_total - credit_total) > 0.01:
            QMessageBox.warning(
                self,
                "Unbalanced Close Plan",
                (
                    f"The generated close plan is not balanced."
                    f" Debits ${debit_total:,.2f},"
                    f" credits ${credit_total:,.2f}."
                ),
            )
            return

        reply = QMessageBox.question(
            self,
            "Post Closing Entry",
            (
                f"Post closing entry {plan['reference']}"
                f" for {plan['start']} to {plan['end']}?\n\n"
                f"Lines: {len(plan['posting_lines'])}\n"
                f"Debits: ${debit_total:,.2f}\n"
                f"Credits: ${credit_total:,.2f}\n"
                f"Retained earnings: {plan['retained_code']}"
                f" - {plan['retained_account']}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        description = (
            f"Year-end close for period {plan['start']} to {plan['end']}"
        )
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                for line in plan["posting_lines"]:
                    cur.execute(
                        """
                        INSERT INTO accounting_entries (
                            entry_date,
                            reference,
                            description,
                            account_code,
                            account_name,
                            debit_amount,
                            credit_amount,
                            source_type,
                            import_batch,
                            created_date
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            plan["end"],
                            plan["reference"],
                            description,
                            line["account_code"],
                            line["account_name"],
                            line["debit"],
                            line["credit"],
                            "YEAR_END_CLOSE",
                            plan["reference"],
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO general_ledger (
                            date,
                            transaction_date,
                            transaction_type,
                            num,
                            memo_description,
                            account,
                            account_name,
                            account_type,
                            debit,
                            credit,
                            source_file,
                            imported_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            plan["end"],
                            plan["end"],
                            "Year End Close",
                            plan["reference"],
                            f"{description} | {line['detail']}",
                            line["account_code"],
                            line["account_name"],
                            line["account_type"],
                            line["debit"],
                            line["credit"],
                            "SYSTEM-YEAR-END-CLOSE",
                        ),
                    )

            QMessageBox.information(
                self,
                "Closing Entry Posted",
                f"Posted {len(plan['posting_lines'])} closing lines"
                f" under reference {plan['reference']}.",
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Posting Failed",
                f"Could not post closing entry:\n{e}",
            )

    def reverse_year_end_close(self) -> None:
        """Post a reversal for an existing year-end close entry."""
        plan = self._build_close_plan()

        if not plan["already_posted"]:
            QMessageBox.information(
                self,
                "Nothing To Reverse",
                f"No posted closing entry found for"
                f" reference {plan['reference']}",
            )
            return

        if plan["already_reversed"]:
            QMessageBox.information(
                self,
                "Already Reversed",
                f"A reversal entry already exists under"
                f" reference {plan['reverse_reference']}",
            )
            return

        close_rows: list[tuple] = []
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT account_code, account_name, debit_amount, credit_amount
                FROM accounting_entries
                WHERE reference = %s
                ORDER BY id
                """,
                (plan["reference"],),
            )
            close_rows = cur.fetchall()

        if not close_rows:
            QMessageBox.warning(
                self,
                "Reversal Blocked",
                "No accounting_entries rows were found for"
                " the close reference. Reversal requires"
                " source lines.",
            )
            return

        debit_total = round(sum(float(row[2] or 0) for row in close_rows), 2)
        credit_total = round(sum(float(row[3] or 0) for row in close_rows), 2)
        if abs(debit_total - credit_total) > 0.01:
            QMessageBox.warning(
                self,
                "Reversal Blocked",
                (
                    f"Original close is unbalanced"
                    f" (debits ${debit_total:,.2f},"
                    f" credits ${credit_total:,.2f})."
                ),
            )
            return

        reply = QMessageBox.question(
            self,
            "Reverse Closing Entry",
            (
                f"Post reversal {plan['reverse_reference']}"
                f" for {plan['reference']}?\n\n"
                f"Lines: {len(close_rows)}\n"
                f"Debits: ${debit_total:,.2f}\n"
                f"Credits: ${credit_total:,.2f}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        description = f"Reversal of {plan['reference']}"
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                for (
                    account_code, account_name,
                    debit_amount, credit_amount
                ) in close_rows:
                    debit_val = float(debit_amount or 0)
                    credit_val = float(credit_amount or 0)

                    cur.execute(
                        """
                        INSERT INTO accounting_entries (
                            entry_date,
                            reference,
                            description,
                            account_code,
                            account_name,
                            debit_amount,
                            credit_amount,
                            source_type,
                            import_batch,
                            created_date
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            plan["end"],
                            plan["reverse_reference"],
                            description,
                            account_code,
                            account_name,
                            credit_val,
                            debit_val,
                            "YEAR_END_CLOSE_REVERSAL",
                            plan["reverse_reference"],
                        ),
                    )

                cur.execute(
                    """
                    SELECT account, account_name, account_type,
                           debit, credit, memo_description
                    FROM general_ledger
                    WHERE num = %s
                    ORDER BY id
                    """,
                    (plan["reference"],),
                )
                gl_rows = cur.fetchall()

                for (
                    account, account_name, account_type,
                    debit, credit, memo_description
                ) in gl_rows:
                    debit_val = float(debit or 0)
                    credit_val = float(credit or 0)
                    cur.execute(
                        """
                        INSERT INTO general_ledger (
                            date,
                            transaction_date,
                            transaction_type,
                            num,
                            memo_description,
                            account,
                            account_name,
                            account_type,
                            debit,
                            credit,
                            source_file,
                            imported_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            plan["end"],
                            plan["end"],
                            "Year End Close Reversal",
                            plan["reverse_reference"],
                            f"{description} | {memo_description or ''}",
                            account,
                            account_name,
                            account_type,
                            credit_val,
                            debit_val,
                            "SYSTEM-YEAR-END-CLOSE-REVERSAL",
                        ),
                    )

            QMessageBox.information(
                self,
                "Reversal Posted",
                f"Posted reversal {plan['reverse_reference']}"
                f" for {plan['reference']}",
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Reversal Failed",
                f"Could not reverse closing entry:\n{e}",
            )

    def fetch_rows(self) -> list[dict[str, Any]]:
        plan = self._build_close_plan()
        start = plan["start"]
        end = plan["end"]
        opening_rows = plan["opening_rows"]
        closing_rows = plan["closing_rows"]
        revenue_total = plan["revenue_total"]
        expense_total = plan["expense_total"]
        opening_total = sum(float(row[2] or 0) for row in opening_rows)
        closing_total = sum(float(row[2] or 0) for row in closing_rows)
        net_income = plan["net_income"]
        expected_closing_total = opening_total + net_income
        closing_variance = closing_total - expected_closing_total
        retained_account = (
            plan["retained_account"]
            or "Retained earnings account not explicitly identified"
        )
        retained_code = plan["retained_code"] or "REVIEW"

        rows: list[dict[str, Any]] = [
            {
                "section": "Period",
                "line": "Start Date",
                "account": "",
                "amount": None,
                "detail": str(start),
            },
            {
                "section": "Period",
                "line": "End Date",
                "account": "",
                "amount": None,
                "detail": str(end),
            },
            {
                "section": "Period Activity",
                "line": "Revenue",
                "account": "Revenue",
                "amount": round(revenue_total, 2),
                "detail": (
                    "Credit balances from revenue accounts"
                    " during selected period"),
            },
            {
                "section": "Period Activity",
                "line": "Expenses",
                "account": "Expense",
                "amount": round(expense_total, 2),
                "detail": (
                    "Debit balances from expense accounts"
                    " during selected period"),
            },
            {
                "section": "Period Activity",
                "line": "Net Income",
                "account": "Current Earnings",
                "amount": round(net_income, 2),
                "detail": "Revenue minus expenses for the selected period",
            },
            {
                "section": "Posting Status",
                "line": "Reference",
                "account": plan["reference"],
                "amount": None,
                "detail": (
                    "Existing posting found"
                    if plan["already_posted"]
                    else "Not yet posted"),
            },
            {
                "section": "Posting Status",
                "line": "Reversal Reference",
                "account": plan["reverse_reference"],
                "amount": None,
                "detail": (
                    "Reversal exists"
                    if plan["already_reversed"]
                    else "Not yet reversed"),
            },
            {
                "section": "Posting Status",
                "line": "Close Lines",
                "account": str(len(plan["posting_lines"])),
                "amount": round(sum(
                    line["debit"] or line["credit"]
                    for line in plan["posting_lines"]), 2),
                "detail": (
                    "Number of journal lines that will"
                    " be posted for the close"),
            },
        ]

        for account_code, account_name, balance in opening_rows:
            rows.append(
                {
                    "section": "Opening Equity",
                    "line": account_name,
                    "account": account_code,
                    "amount": round(float(balance or 0), 2),
                    "detail": "Balance before selected period start",
                }
            )

        rows.append(
            {
                "section": "Opening Equity",
                "line": "Total Opening Equity",
                "account": "TOTAL",
                "amount": round(opening_total, 2),
                "detail": "Sum of equity balances before selected period",
            }
        )

        for account_code, account_name, balance in closing_rows:
            rows.append(
                {
                    "section": "Closing Equity",
                    "line": account_name,
                    "account": account_code,
                    "amount": round(float(balance or 0), 2),
                    "detail": (
                        "Balance as of selected period end"
                        " before any additional closing entry"),
                }
            )

        rows.extend(
            [
                {
                    "section": "Closing Equity",
                    "line": "Total Closing Equity",
                    "account": "TOTAL",
                    "amount": round(closing_total, 2),
                    "detail": (
                        "Sum of equity balances as of"
                        " selected period end"),
                },
                {
                    "section": "Close Check",
                    "line": "Expected Closing Equity",
                    "account": "OPEN + NI",
                    "amount": round(expected_closing_total, 2),
                    "detail": "Opening equity plus current period net income",
                },
                {
                    "section": "Close Check",
                    "line": "Actual Closing Equity",
                    "account": "BOOKS",
                    "amount": round(closing_total, 2),
                    "detail": "Current equity balance on the books",
                },
                {
                    "section": "Close Check",
                    "line": "Closing Variance",
                    "account": "VAR",
                    "amount": round(closing_variance, 2),
                    "detail": (
                        "Actual closing equity minus"
                        " expected closing equity"),
                },
                {
                    "section": "Suggested Close Entry",
                    "line": "Transfer current period earnings",
                    "account": retained_code,
                    "amount": round(abs(net_income), 2),
                    "detail": (
                        f"{'Credit' if net_income >= 0 else 'Debit'}"
                        f" {retained_account}; "
                        f"offset revenue/expense close for selected period"
                    ),
                },
            ]
        )

        section_order = {
            "Period": 1,
            "Period Activity": 2,
            "Posting Status": 3,
            "Opening Equity": 4,
            "Closing Equity": 5,
            "Close Check": 6,
            "Suggested Close Entry": 7,
        }
        return sorted(
            rows,
            key=lambda row: (
                section_order.get(row["section"], 9),
                row["account"] == "TOTAL",
                row["account"],
                row["line"],
            ),
        )


class LedgerIntegrityWidget(BaseReportWidget, _DateRangeMixin):
    """Diagnostic report for unresolved ledger mappings and balance issues."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Issue Type", "key": "issue_type"},
            {"header": "Section", "key": "section"},
            {"header": "Account", "key": "account"},
            {"header": "Account Name", "key": "account_name"},
            {"header": "Detail", "key": "detail"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}" if v is not None else ""},
            {"header": "Rows", "key": "row_count"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Ledger Integrity", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

    def fetch_rows(self) -> list[dict[str, Any]]:
        _, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            cur.execute(
                """
                SELECT account_code,
                       canonical_account_name,
                       COUNT(*) AS row_count,
                       COALESCE(SUM(debit), 0) AS total_debit,
                       COALESCE(SUM(credit), 0) AS total_credit
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                  AND account_class = 'Unknown'
                GROUP BY 1, 2
                ORDER BY COUNT(*) DESC, account_code
                LIMIT 50
                """,
                (end,),
            )
            unknown_rows = cur.fetchall()

            cur.execute(
                """
                SELECT account_code,
                       COUNT(DISTINCT canonical_account_name) AS name_count,
                       STRING_AGG(DISTINCT canonical_account_name,
                           ' | ' ORDER BY canonical_account_name) AS names,
                       COUNT(*) AS row_count,
                       COALESCE(SUM(debit - credit), 0) AS net_balance
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                GROUP BY account_code
                HAVING COUNT(DISTINCT canonical_account_name) > 1
                ORDER BY
                    COUNT(DISTINCT canonical_account_name) DESC,
                    COUNT(*) DESC, account_code
                LIMIT 50
                """,
                (end,),
            )
            duplicate_name_rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Asset'
                        THEN debit - credit ELSE 0 END), 0) AS assets,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Liability'
                        THEN credit - debit ELSE 0 END), 0) AS liabilities,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Equity'
                        THEN credit - debit ELSE 0 END), 0) AS equity,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Revenue'
                        THEN credit - debit ELSE 0 END), 0) AS revenue,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Expense'
                        THEN debit - credit ELSE 0 END), 0) AS expenses,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Unknown'
                        THEN debit - credit ELSE 0 END), 0) AS unknown_net
                FROM general_ledger_normalized
                WHERE entry_date <= %s
                """,
                (end,),
            )
            assets, liabilities, equity, revenue, expenses, unknown_net = [
                float(v or 0) for v in cur.fetchone()]

        current_earnings = revenue - expenses
        balance_diff = assets - (liabilities + equity + current_earnings)

        rows: list[dict[str, Any]] = [
            {
                "issue_type": "Balance Check",
                "section": "Summary",
                "account": "ASSETS",
                "account_name": "Total Assets",
                "detail": "Derived from normalized ledger asset balances",
                "amount": round(assets, 2),
                "row_count": None,
            },
            {
                "issue_type": "Balance Check",
                "section": "Summary",
                "account": "LIABILITIES",
                "account_name": "Total Liabilities",
                "detail": "Derived from normalized ledger liability balances",
                "amount": round(liabilities, 2),
                "row_count": None,
            },
            {
                "issue_type": "Balance Check",
                "section": "Summary",
                "account": "EQUITY",
                "account_name": "Total Equity",
                "detail": "Ledger equity before current-period earnings",
                "amount": round(equity, 2),
                "row_count": None,
            },
            {
                "issue_type": "Balance Check",
                "section": "Summary",
                "account": "CURR-EARN",
                "account_name": "Current Period Earnings",
                "detail": "Revenue minus expense through selected end date",
                "amount": round(current_earnings, 2),
                "row_count": None,
            },
            {
                "issue_type": "Balance Check",
                "section": "Summary",
                "account": "UNKNOWN-NET",
                "account_name": "Net Effect of Unknown-Class Rows",
                "detail": "Debit minus credit across unresolved rows",
                "amount": round(unknown_net, 2),
                "row_count": None,
            },
            {
                "issue_type": "Balance Check",
                "section": "Summary",
                "account": "DIFF",
                "account_name": (
                    "Assets minus Liabilities, Equity,"
                    " and Current Earnings"),
                "detail": (
                    "Non-zero means the books still do not"
                    " balance under current normalization rules"),
                "amount": round(balance_diff, 2),
                "row_count": None,
            },
        ]

        for (
            account_code, account_name, row_count,
            total_debit, total_credit
        ) in unknown_rows:
            rows.append(
                {
                    "issue_type": "Unknown Account Class",
                    "section": "Classification",
                    "account": account_code,
                    "account_name": account_name,
                    "detail": (
                        f"Unresolved after normalization;"
                        f" debit={float(total_debit or 0):,.2f},"
                        f" credit={float(total_credit or 0):,.2f}"),
                    "amount": round(
                        float(total_debit or 0)
                        - float(total_credit or 0), 2),
                    "row_count": int(row_count or 0),
                }
            )

        for (
            account_code, name_count, names,
            row_count, net_balance
        ) in duplicate_name_rows:
            rows.append(
                {
                    "issue_type": "Duplicate Canonical Names",
                    "section": "Normalization",
                    "account": account_code,
                    "account_name": names,
                    "detail": (
                        f"{int(name_count or 0)} different names"
                        f" mapped to the same account code"),
                    "amount": round(float(net_balance or 0), 2),
                    "row_count": int(row_count or 0),
                }
            )

        issue_order = {
            "Balance Check": 1,
            "Unknown Account Class": 2,
            "Duplicate Canonical Names": 3,
        }
        return sorted(
            rows,
            key=lambda row: (
                issue_order.get(row["issue_type"], 9),
                row["account"] not in {
                    "ASSETS", "LIABILITIES",
                    "EQUITY", "CURR-EARN", "UNKNOWN-NET", "DIFF"},
                -(row["row_count"] or 0),
                row["account"],
            ),
        )


class JournalExplorerWidget(BaseReportWidget, _DateRangeMixin):
    """Journal listing with date range filter."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Date", "key": "date"},
            {"header": "Type", "key": "transaction_type"},
            {"header": "Number", "key": "num"},
            {"header": "Name", "key": "name"},
            {"header": "Account", "key": "account_name"},
            {"header": "Memo", "key": "memo"},
            {"header": "Debit", "key": "debit",
             "format": lambda v: f"${v:,.2f}"},
            {"header": "Credit", "key": "credit",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Supplier", "key": "supplier"},
            {"header": "Employee", "key": "employee"},
            {"header": "Customer", "key": "customer"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Journal Explorer", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return [{
                    "date": "N/A",
                    "transaction_type": "Info",
                    "num": "N/A",
                    "name": "Missing Table",
                    "account_name": "N/A",
                    "memo": "general_ledger table is missing",
                    "debit": 0.0,
                    "credit": 0.0,
                    "supplier": "",
                    "employee": "",
                    "customer": "",
                }]

            cur.execute(
                """
                SELECT
                    gln.entry_date,
                    gln.transaction_type,
                    gln.ref_number AS num,
                    gln.party_name AS name,
                    gln.account_name,
                    gln.memo,
                    gln.debit,
                    gln.credit,
                    gln.supplier,
                    gln.employee,
                    gln.customer
                FROM general_ledger_normalized gln
                WHERE gln.entry_date BETWEEN %s AND %s
                ORDER BY entry_date DESC, num DESC, account_name
                LIMIT 5000
                """,
                (start, end),
            )
            rows = cur.fetchall()

        return [
            {
                "date": str(r[0]) if r[0] else "",
                "transaction_type": r[1],
                "num": r[2],
                "name": r[3],
                "account_name": r[4],
                "memo": r[5],
                "debit": float(r[6] or 0),
                "credit": float(r[7] or 0),
                "supplier": r[8],
                "employee": r[9],
                "customer": r[10],
            }
            for r in rows
        ]


class BankReconciliationWidget(BaseReportWidget, _DateRangeMixin):
    """Bank reconciliation snapshot by account number."""

    def __init__(self, db, account_number: str = '0228362') -> None:
        self.account_number = account_number
        columns = [
            {"header": "Date", "key": "date"},
            {"header": "Description", "key": "description"},
            {"header": "Debit", "key": "debit",
             "format": lambda v: f"${v:,.2f}"},
            {"header": "Credit", "key": "credit",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Status", "key": "status"},
            {"header": "Receipt", "key": "reconciled_receipt_id"},
            {"header": "Balance After", "key": "balance_after",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Bank Reconciliation", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=6))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT transaction_id, transaction_date, description,
                       debit_amount, credit_amount,
                       reconciliation_status, receipt_id,
                       balance
                FROM banking_transactions
                WHERE account_number = %s
                  AND transaction_date BETWEEN %s AND %s
                ORDER BY transaction_date, transaction_id
                LIMIT 1000
                """,
                (self.account_number, start, end),)
            rows = cur.fetchall()
        return [
            {
                "transaction_id": r[0],
                "date": str(r[1]),
                "description": r[2],
                "debit": float(r[3] or 0),
                "credit": float(r[4] or 0),
                "status": r[5] or "unreconciled",
                "reconciled_receipt_id": r[6],
                "balance_after": float(r[7] or 0), }
            for r in rows]


class PLSummaryWidget(BaseReportWidget, _DateRangeMixin):
    """Profit and Loss summary grouped by month."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "Revenue", "key": "revenue",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Expenses", "key": "expenses",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Profit", "key": "profit",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Profit & Loss", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            cur.execute(
                """
                SELECT
                    DATE_TRUNC('month', entry_date) AS period,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Revenue'
                        THEN credit - debit ELSE 0
                        END), 0) AS revenue,
                    COALESCE(SUM(
                        CASE WHEN account_class = 'Expense'
                        THEN debit - credit ELSE 0
                        END), 0) AS expenses
                FROM general_ledger_normalized
                WHERE entry_date BETWEEN %s AND %s
                  AND account_class IN ('Revenue', 'Expense')
                GROUP BY 1
                ORDER BY 1
                """,
                (start, end),)
            monthly_rows = cur.fetchall()

        data = []
        for period, revenue, expenses in monthly_rows:
            data.append(
                {
                    "period": period.date().isoformat() if hasattr(
                        period, "date") else str(period),
                    "revenue": round(float(revenue or 0), 2),
                    "expenses": round(float(expenses or 0), 2),
                    "profit": round(
                        float((revenue or 0) - (expenses or 0)), 2),
                })
        return data


class PLCategoryWidget(BaseReportWidget, _DateRangeMixin):
    """P&L grouped by account name per period."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "Account Type", "key": "account_type"},
            {"header": "Account", "key": "account_name"},
            {"header": "Net", "key": "net", "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "P&L by Category", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            if not _ensure_normalized_general_ledger_view(cur):
                return []

            cur.execute(
                """
                SELECT
                    DATE_TRUNC('month', entry_date) AS period,
                    account_class AS account_type,
                    CONCAT(account_code, ' ',
                           canonical_account_name) AS account_name,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN account_class = 'Revenue'
                                    THEN credit - debit
                                WHEN account_class = 'Expense'
                                    THEN debit - credit
                                ELSE 0
                            END
                        ),
                        0
                    ) AS net
                FROM general_ledger_normalized
                WHERE entry_date BETWEEN %s AND %s
                  AND account_class IN ('Revenue', 'Expense')
                GROUP BY 1, 2, 3
                HAVING ABS(
                    COALESCE(
                        SUM(
                            CASE
                                WHEN account_class = 'Revenue'
                                    THEN credit - debit
                                WHEN account_class = 'Expense'
                                    THEN debit - credit
                                ELSE 0
                            END
                        ),
                        0
                    )
                ) > 0.004

                ORDER BY 1, 2, 3
                """,
                (start, end),)
            rows = cur.fetchall()
        data = []
        for r in rows:
            data.append(
                {
                    "period": (
                        r[0].date().isoformat()
                        if hasattr(r[0], "date") else str(r[0])),
                    "account_type": r[1],
                    "account_name": r[2],
                    "net": float(r[3] or 0), })
        return data


class VehiclePerformanceWidget(BaseReportWidget, _DateRangeMixin):
    """Vehicle revenue vs expense with trips count."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle #", "key": "vehicle_number"},
            {"header": "Make", "key": "make"},
            {"header": "Model", "key": "model"},
            {"header": "Year", "key": "year"},
            {"header": "Trips", "key": "trips"},
            {"header": "Revenue", "key": "revenue",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Expense", "key": "expense",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Maint", "key": "maintenance",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Insurance", "key": "insurance",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Profit", "key": "profit",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Margin %", "key": "margin_pct",
             "format": lambda v: f"{v:.2f}%"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Vehicle Performance", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            # Revenue by vehicle (requires vehicle_id on charters)
            cur.execute(
                """
                SELECT vehicle_id,
                       COUNT(*) AS trips,
                       COALESCE(SUM(gross_amount), 0) AS revenue
                FROM charters
                WHERE (pickup_date BETWEEN %s AND %s
                   OR charter_date BETWEEN %s AND %s)
                GROUP BY vehicle_id
                """,
                (start, end, start, end),)
            revenue_map = {
                int(v or 0): {"trips": int(t or 0), "revenue": float(
                    r or 0)} for v, t, r in cur.fetchall()}

            cur.execute(
                """
                SELECT vehicle_id,
                       COALESCE(SUM(gross_amount), 0) AS expense,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%maint%'
                           THEN gross_amount ELSE 0
                           END), 0) AS maintenance,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%insur%'
                           THEN gross_amount ELSE 0
                           END), 0) AS insurance
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                GROUP BY vehicle_id
                """,
                (start, end),)
            expense_map = {
                int(v or 0): {
                    "expense": float(e or 0),
                    "maintenance": float(m or 0),
                    "insurance": float(i or 0), }
                for v, e, m, i in cur.fetchall()}

            cur.execute(
                "SELECT vehicle_id, vehicle_number,"
                " make, model, year FROM vehicles ORDER BY vehicle_number")
            rows = cur.fetchall()
        data = []
        for vid, num, make, model, year in rows:
            rev = revenue_map.get(int(vid or 0), {"revenue": 0.0, "trips": 0})
            exp = expense_map.get(
                int(vid or 0), {"expense": 0.0,
                                "maintenance": 0.0, "insurance": 0.0})
            profit = rev.get("revenue", 0.0) - exp.get("expense", 0.0)
            margin = (profit / rev.get("revenue", 1)) * \
                100 if rev.get("revenue", 0) else 0.0
            data.append(
                {
                    "vehicle_number": num,
                    "make": make,
                    "model": model,
                    "year": year,
                    "trips": rev.get("trips", 0),
                    "revenue": round(rev.get("revenue", 0.0), 2),
                    "expense": round(exp.get("expense", 0.0), 2),
                    "maintenance": round(exp.get("maintenance", 0.0), 2),
                    "insurance": round(exp.get("insurance", 0.0), 2),
                    "profit": round(profit, 2),
                    "margin_pct": round(margin, 2), })
        return data


class DriverCostWidget(BaseReportWidget, _DateRangeMixin):
    """Driver payroll cost per driver."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Driver", "key": "name"},
            {"header": "Payruns", "key": "payruns"},
            {"header": "Total Cost", "key": "total_cost",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Gross Total", "key": "gross_total",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Driver Cost", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT dp.employee_id, COALESCE(e.full_name, '') AS name,
                       COUNT(*) AS payruns,
                       COALESCE(SUM(net_pay), 0) AS total_cost,
                       COALESCE(SUM(gross_pay), 0) AS gross_total
                FROM driver_payroll dp
                LEFT JOIN employees e ON e.employee_id = dp.employee_id
                WHERE pay_date BETWEEN %s AND %s
                GROUP BY dp.employee_id, name
                ORDER BY total_cost DESC
                """,
                (start, end),)
            rows = cur.fetchall()
        return [
            {
                "driver_id": r[0],
                "name": r[1],
                "payruns": int(r[2] or 0),
                "total_cost": float(r[3] or 0),
                "gross_total": float(r[4] or 0), }
            for r in rows]


class DriverRevenueVsPayWidget(BaseReportWidget, _DateRangeMixin):
    """Driver revenue (charters) vs payroll cost."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Driver", "key": "driver_name"},
            {"header": "Trips", "key": "trips"},
            {"header": "Revenue", "key": "revenue",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Profit After Pay", "key": "profit_after_pay",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Margin %", "key": "margin_pct",
             "format": lambda v: f"{v:.2f}%"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Driver Revenue vs Pay", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            # Revenue from charters
            cur.execute(
                """
                SELECT assigned_driver_id,
                       COALESCE(SUM(total_amount_due), 0) AS revenue,
                       COUNT(*) AS trips
                FROM charters
                WHERE charter_date BETWEEN %s AND %s
                  AND assigned_driver_id IS NOT NULL
                GROUP BY assigned_driver_id
                """,
                (start, end),)
            rev_map = {int(r[0] or 0): {"revenue": float(r[1] or 0),
                                        "trips": int(r[2] or 0)}
                       for r in cur.fetchall()}
            cur.execute(
                """
                SELECT employee_id, employee_name
                FROM employees
                WHERE employee_id > 0
                ORDER BY employee_id
                """,)
            rows = cur.fetchall()

        data = []
        for emp_id, emp_name in rows:
            rev = rev_map.pop(int(emp_id or 0), {"revenue": 0.0, "trips": 0})
            profit = rev.get("revenue", 0.0)
            data.append(
                {
                    "driver_id": emp_id,
                    "driver_name": emp_name or f"Driver {emp_id}",
                    "trips": rev.get(
                        "trips",
                        0),
                    "revenue": round(
                        rev.get(
                            "revenue",
                            0.0),
                        2),
                    "profit_after_pay": round(
                        profit,
                        2),
                    "margin_pct": round(
                        (profit /
                         rev.get(
                             "revenue",
                             1)) *
                        100,
                        2) if rev.get(
                        "revenue",
                        0) else 0.0, })

        for did, rev in rev_map.items():
            profit = rev.get("revenue", 0.0)
            data.append(
                {
                    "driver_id": did,
                    "driver_name": f"Driver {did}",
                    "trips": rev.get("trips", 0),
                    "revenue": round(rev.get("revenue", 0.0), 2),
                    "profit_after_pay": round(profit, 2),
                    "margin_pct": 100.0, })
        return data


class FleetMaintenanceWidget(BaseReportWidget, _DateRangeMixin):
    """Maintenance/repairs/insurance/damage costs by vehicle."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle_id"},
            {"header": "Maintenance", "key": "maintenance",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Repairs", "key": "repairs",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Insurance", "key": "insurance",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Damage", "key": "damage",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Total", "key": "total_expense",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Fleet Maintenance", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT vehicle_id,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%maint%'
                           THEN gross_amount ELSE 0
                           END), 0) AS maintenance,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%repair%'
                           THEN gross_amount ELSE 0
                           END), 0) AS repairs,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%insur%'
                           THEN gross_amount ELSE 0
                           END), 0) AS insurance,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%damage%'
                           OR description ILIKE '%claim%'
                           THEN gross_amount ELSE 0
                           END), 0) AS damage,
                       COALESCE(SUM(gross_amount), 0) AS total_expense
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                GROUP BY vehicle_id
                ORDER BY total_expense DESC
                LIMIT 500
                """,
                (start, end),)
            rows = cur.fetchall()
        return [
            {
                "vehicle_id": r[0],
                "maintenance": float(r[1] or 0),
                "repairs": float(r[2] or 0),
                "insurance": float(r[3] or 0),
                "damage": float(r[4] or 0),
                "total_expense": float(r[5] or 0), }
            for r in rows]


class BankRecSuggestionsWidget(BaseReportWidget):
    """Banking vs receipts amount/date suggestions."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Txn ID", "key": "transaction_id"},
            {"header": "Txn Date", "key": "transaction_date"},
            {"header": "Amount", "key": "amount",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Description", "key": "description"},
            {"header": "Candidates", "key": "candidate_summary"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Bank Rec Suggestions", columns)

    def fetch_rows(self) -> list[dict[str, Any]]:
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT bt.transaction_id, bt.transaction_date, bt.description,
                       COALESCE(bt.debit_amount, 0)
                       - COALESCE(bt.credit_amount, 0) AS amount,
                       (
                           SELECT STRING_AGG(
                               CONCAT(
                                   'Receipt ', r.id, ' ',
                                   r.receipt_date, ' $', r.gross_amount),
                               '\\n')
                           FROM receipts r
                           WHERE ABS(r.gross_amount) = ABS(
                               COALESCE(bt.debit_amount,0)
                               - COALESCE(bt.credit_amount,0))
                             AND r.receipt_date BETWEEN
                                 bt.transaction_date - INTERVAL '1 day'
                                 AND bt.transaction_date + INTERVAL '1 day'
                           ) AS candidates
                FROM banking_transactions bt
                WHERE 1=1
                ORDER BY bt.transaction_date DESC
                LIMIT 300
                """)
            rows = cur.fetchall()
        return [
            {
                "transaction_id": r[0],
                "transaction_date": str(r[1]),
                "description": r[2],
                "amount": float(r[3] or 0),
                "candidate_summary": r[4] or "", }
            for r in rows]


class VehicleInsuranceWidget(BaseReportWidget):
    """Insurance cost per vehicle per year."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle_id"},
            {"header": "Year", "key": "year"},
            {"header": "Insurance", "key": "insurance_cost",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(
            self, db, "Vehicle Insurance (Yearly)", columns)

    def fetch_rows(self) -> list[dict[str, Any]]:
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT vehicle_id,
                       EXTRACT(YEAR FROM receipt_date) AS yr,
                       COALESCE(SUM(
                           CASE WHEN description ILIKE '%insur%'
                           THEN gross_amount ELSE 0
                           END), 0) AS insurance_cost
                FROM receipts
                WHERE receipt_date BETWEEN
                    (CURRENT_DATE - INTERVAL '5 years') AND CURRENT_DATE
                GROUP BY vehicle_id, yr
                ORDER BY yr DESC, vehicle_id
                """)
            rows = cur.fetchall()
        return [
            {
                "vehicle_id": r[0],
                "year": int(r[1]) if r[1] is not None else None,
                "insurance_cost": float(r[2] or 0), }
            for r in rows]


class VehicleDamageWidget(BaseReportWidget, _DateRangeMixin):
    """Damage/claim counts and totals per vehicle."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Vehicle", "key": "vehicle_id"},
            {"header": "Damage Count", "key": "damage_count"},
            {"header": "Damage Total", "key": "damage_total",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Vehicle Damage Summary", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT vehicle_id,
                       COUNT(*) AS damage_count,
                       COALESCE(SUM(gross_amount), 0) AS damage_total
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                  AND (description ILIKE '%damage%'
                       OR description ILIKE '%claim%'
                       OR description ILIKE '%collision%'
                       OR description ILIKE '%accident%')
                GROUP BY vehicle_id
                ORDER BY damage_total DESC
                """,
                (start, end),)
            rows = cur.fetchall()
        return [
            {
                "vehicle_id": r[0],
                "damage_count": int(r[1] or 0),
                "damage_total": float(r[2] or 0), }
            for r in rows]


class DriverMonthlyCostWidget(BaseReportWidget, _DateRangeMixin):
    """Driver payroll cost grouped monthly."""

    def __init__(self, db) -> None:
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "Driver", "key": "name"},
            {"header": "Payruns", "key": "payruns"},
            {"header": "Total Cost", "key": "total_cost",
                "format": lambda v: f"${v:,.2f}"},
            {"header": "Gross Total", "key": "gross_total",
             "format": lambda v: f"${v:,.2f}"},]
        self.db = db
        BaseReportWidget.__init__(self, db, "Driver Monthly Cost", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> list[dict[str, Any]]:
        start, end = self._date_range()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT DATE_TRUNC('month', pay_date) AS period,
                       dp.employee_id,
                       COALESCE(e.full_name, '') AS name,
                       COUNT(*) AS payruns,
                       COALESCE(SUM(net_pay), 0) AS total_cost,
                       COALESCE(SUM(gross_pay), 0) AS gross_total
                FROM driver_payroll dp
                LEFT JOIN employees e ON e.employee_id = dp.employee_id
                WHERE pay_date BETWEEN %s AND %s
                GROUP BY period, dp.employee_id, name
                ORDER BY period DESC, name
                """,
                (start, end),)
            rows = cur.fetchall()
        return [
            {
                "period": r[0].date().isoformat() if hasattr(
                    r[0], "date") else str(
                    r[0]), "driver_id": r[1], "name": r[2], "payruns": int(
                    r[3] or 0), "total_cost": float(
                        r[4] or 0), "gross_total": float(
                            r[5] or 0), } for r in rows]


class GIFIMappingWidget(QWidget):
    """
    Manage GL->GIFI code mappings used by T2 auto-fill.

    Displays each GL account from chart_of_accounts
    with its suggested GIFI code.
    Users can override assignments and save them to the gifi_mapping DB table.
    """

    INFO_STYLE = (
        "background:#dbeafe;padding:10px;"
        "border-radius:5px;margin-bottom:8px;"
    )

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._init_ui()
        self.load_mappings()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(
            "GIFI Mapping (Schedule 125 Auto-Fill)\n"
            "Assign a GIFI code and tax treatment to each GL account.\n"
            "Revenue (4xxx) and balance-sheet accounts"
            " are excluded from Schedule 125."
        )
        info.setStyleSheet(self.INFO_STYLE)
        layout.addWidget(info)

        from accounting_gifi import GIFI_DESCRIPTIONS
        self._gifi_options = sorted(
            [f"{code} - {desc}" for code, desc in GIFI_DESCRIPTIONS.items()]
        )

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "GL Code", "GL Account Name",
            "GIFI Code", "GIFI Description", "Tax Treatment"
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(450)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.load_mappings)
        btn_row.addWidget(reload_btn)
        btn_row.addStretch()
        save_btn = QPushButton("Save All Overrides")
        save_btn.setStyleSheet(
            "background:#10b981;color:white;font-weight:bold;")
        save_btn.clicked.connect(self._save_mappings)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)
        self.status = QLabel("")
        layout.addWidget(self.status)

    def load_mappings(self) -> None:
        """Load GL accounts and their saved GIFI overrides."""
        from accounting_gifi import (
            GIFI_DESCRIPTIONS,
            NON_DEDUCTIBLE_GL_CODES,
            SCH125_FIELD_TO_GIFI,
            gl_to_sch125_field,
        )
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT account_code, account_name"
                    " FROM chart_of_accounts ORDER BY account_code"
                )
                gl_rows = cur.fetchall()
                overrides = {}
                cur.execute("SELECT to_regclass('gifi_mapping')")
                if cur.fetchone()[0] is not None:
                    cur.execute(
                        "SELECT gl_code, gifi_code,"
                        " tax_treatment FROM gifi_mapping")
                    for gl, gifi, treatment in cur.fetchall():
                        overrides[str(gl)] = (
                            str(gifi or ""), str(treatment or ""))
        except Exception as e:
            self.status.setText(f"Error loading: {e}")
            return

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for gl_code, gl_name in gl_rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(gl_code)))
            self.table.setItem(row, 1, QTableWidgetItem(str(gl_name or "")))
            if str(gl_code) in overrides:
                gifi_code, treatment = overrides[str(gl_code)]
            else:
                field_name = gl_to_sch125_field(
                    str(gl_code), str(gl_name or ""))
                gifi_code = SCH125_FIELD_TO_GIFI.get(
                    field_name, "") if field_name else ""
                if str(gl_code) in NON_DEDUCTIBLE_GL_CODES:
                    treatment = "NON-DEDUCTIBLE"
                elif gifi_code:
                    treatment = "DEDUCTIBLE"
                else:
                    treatment = "OTHER"
            gifi_combo = QComboBox()
            gifi_combo.addItem("")
            for opt in self._gifi_options:
                gifi_combo.addItem(opt)
            for i in range(gifi_combo.count()):
                if gifi_combo.itemText(i).startswith(str(gifi_code)):
                    gifi_combo.setCurrentIndex(i)
                    break
            treatment_combo = QComboBox()
            treatment_combo.addItems(
                ["DEDUCTIBLE", "NON-DEDUCTIBLE", "50% DEDUCTIBLE", "OTHER"])
            valid = ("DEDUCTIBLE", "NON-DEDUCTIBLE", "50% DEDUCTIBLE", "OTHER")
            treatment_combo.setCurrentText(
                treatment if treatment in valid else "OTHER")
            self.table.setCellWidget(row, 2, gifi_combo)
            self.table.setItem(row, 3, QTableWidgetItem(
                GIFI_DESCRIPTIONS.get(gifi_code, "")))
            self.table.setCellWidget(row, 4, treatment_combo)
        self.table.blockSignals(False)
        self.status.setText(f"Loaded {self.table.rowCount()} GL accounts")

    def _save_mappings(self) -> None:
        """Upsert user overrides to gifi_mapping table."""
        rows = []
        for row in range(self.table.rowCount()):
            gl_item = self.table.item(row, 0)
            if not gl_item:
                continue
            gl_code = gl_item.text().strip()
            gifi_combo = self.table.cellWidget(row, 2)
            treatment_combo = self.table.cellWidget(row, 4)
            gifi_text = gifi_combo.currentText() if gifi_combo else ""
            gifi_code = gifi_text.split(
                " - ")[0].strip() if " - " in gifi_text else gifi_text.strip()
            treatment = (
                treatment_combo.currentText()
                if treatment_combo else "OTHER")
            rows.append((gl_code, gifi_code, treatment))
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS gifi_mapping (
                        gl_code TEXT PRIMARY KEY,
                        gifi_code TEXT,
                        tax_treatment TEXT DEFAULT 'DEDUCTIBLE',
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                for gl_code, gifi_code, treatment in rows:
                    cur.execute("""
                        INSERT INTO gifi_mapping
                        (gl_code, gifi_code, tax_treatment, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (gl_code)
                        DO UPDATE SET gifi_code = EXCLUDED.gifi_code,
                                      tax_treatment = EXCLUDED.tax_treatment,
                                      updated_at = NOW()
                    """, (gl_code, gifi_code, treatment))
            self.status.setText(f"Saved {len(rows)} GL->GIFI mappings")
        except Exception as e:
            self.status.setText(f"Save failed: {e}")


__all__ = [
    "BalanceSheetWidget",
    "BankRecSuggestionsWidget",
    "BankReconciliationWidget",
    "DavidLoanAccountingWidget",
    "DriverCostWidget",
    "DriverMonthlyCostWidget",
    "DriverRevenueVsPayWidget",
    "FleetMaintenanceWidget",
    "GIFIMappingWidget",
    "GSTCollectionWidget",
    "GeneralLedgerWidget",
    "IncomeExpenseGroupedWidget",
    "JournalExplorerWidget",
    "LedgerIntegrityWidget",
    "PLCategoryWidget",
    "PLSummaryWidget",
    "PersonalExpenseWidget",
    "ReceiptLedgerWidget",
    "ReconciliationStatusWidget",
    "TrialBalanceWidget",
    "VehicleDamageWidget",
    "VehicleInsuranceWidget",
    "VehiclePerformanceWidget",
    "VendorReceiptBankingAuditWidget",
    "YearEndCloseWidget",
]
