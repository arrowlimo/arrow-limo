"""
Accounting-focused report widgets using direct database queries.
Includes: Trial Balance, Journal Explorer, Bank Reconciliation,
Vehicle Performance, Driver Cost, Fleet Maintenance, P&L Summary.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import QDate

from desktop_app.common_widgets import StandardDateEdit

from reporting_base import BaseReportWidget


class _DateRangeMixin:
    """Reusable start/end date controls for report widgets."""

    def _init_date_controls(self, months_back: int = 12):
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

    def _date_range(self):
        # Fallback if date controls not initialized yet (e.g., during BaseReportWidget.__init__ refresh)
        if not hasattr(self, "start_date") or not hasattr(self, "end_date") or self.start_date is None or self.end_date is None:
            start = QDate.currentDate().addMonths(-12).toPyDate()
            end = QDate.currentDate().toPyDate()
            return start, end
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        return start, end


class TrialBalanceWidget(BaseReportWidget, _DateRangeMixin):
    """Trial balance aggregated by account as of end date."""

    def __init__(self, db):
        columns = [
            {"header": "Account Name", "key": "account_name"},
            {"header": "Account", "key": "account"},
            {"header": "Type", "key": "account_type"},
            {"header": "Debit", "key": "total_debit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Credit", "key": "total_credit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Balance", "key": "balance", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Trial Balance", columns)
        # Insert date controls above toolbar
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=24))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        _, end = self._date_range()
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
        
        data = []
        
        # Revenue from charters (credit balance)
        cur.execute(
            """
            SELECT COALESCE(SUM(total_amount_due), 0)
            FROM charters
            WHERE charter_date <= %s
            """,
            (end,),
        )
        revenue = float(cur.fetchone()[0] or 0)
        if revenue != 0:
            data.append({
                "account_name": "Charter Revenue",
                "account": "4000",
                "account_type": "Revenue",
                "total_debit": 0.0,
                "total_credit": revenue,
                "balance": -revenue,
            })
        
        # Expenses from receipts (debit balance)
        cur.execute(
            """
            SELECT category, COALESCE(SUM(gross_amount), 0)
            FROM receipts
            WHERE receipt_date <= %s AND category IS NOT NULL AND category != 'personal'
            GROUP BY category
            ORDER BY category
            """,
            (end,),
        )
        for category, amount in cur.fetchall():
            amount_float = float(amount or 0)
            if amount_float != 0:
                data.append({
                    "account_name": f"Expense - {category}",
                    "account": "5000",
                    "account_type": "Expense",
                    "total_debit": amount_float,
                    "total_credit": 0.0,
                    "balance": amount_float,
                })
        
        # Bank accounts (asset - debit balance)
        cur.execute(
            """
            SELECT account_number, description, balance
            FROM (
                SELECT account_number, description, balance,
                       ROW_NUMBER() OVER (PARTITION BY account_number ORDER BY transaction_date DESC) as rn
                FROM banking_transactions
                WHERE transaction_date <= %s
            ) sub
            WHERE rn = 1
            ORDER BY account_number
            """,
            (end,),
        )
        for acct_num, desc, balance in cur.fetchall():
            balance_float = float(balance or 0)
            bank_name = "CIBC" if acct_num == '0228362' else ("Scotia" if acct_num == '903990106011' else f"Account {acct_num}")
            data.append({
                "account_name": f"Bank - {bank_name}",
                "account": "1000",
                "account_type": "Asset",
                "total_debit": balance_float if balance_float > 0 else 0.0,
                "total_credit": abs(balance_float) if balance_float < 0 else 0.0,
                "balance": balance_float,
            })
        
        # Accounts Receivable (unpaid charters)
        cur.execute(
            """
            SELECT COALESCE(SUM(total_amount_due - COALESCE(paid_amount, 0)), 0)
            FROM charters
            WHERE charter_date <= %s 
              AND (total_amount_due - COALESCE(paid_amount, 0)) > 0.01
              AND COALESCE(cancelled, false) = false
            """,
            (end,),
        )
        ar_balance = float(cur.fetchone()[0] or 0)
        if ar_balance > 0:
            data.append({
                "account_name": "Accounts Receivable",
                "account": "1200",
                "account_type": "Asset",
                "total_debit": ar_balance,
                "total_credit": 0.0,
                "balance": ar_balance,
            })
        
        return data


class JournalExplorerWidget(BaseReportWidget, _DateRangeMixin):
    """Journal listing with date range filter."""

    def __init__(self, db):
        columns = [
            {"header": "Date", "key": "date"},
            {"header": "Type", "key": "transaction_type"},
            {"header": "Number", "key": "num"},
            {"header": "Name", "key": "name"},
            {"header": "Account", "key": "account_name"},
            {"header": "Memo", "key": "memo"},
            {"header": "Debit", "key": "debit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Credit", "key": "credit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Supplier", "key": "supplier"},
            {"header": "Employee", "key": "employee"},
            {"header": "Customer", "key": "customer"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Journal Explorer", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        # Journal Explorer report not yet implemented - general_ledger table does not exist
        return [
            {
                "date": "N/A",
                "transaction_type": "Info",
                "num": "N/A",
                "name": "Not Implemented",
                "account_name": "N/A",
                "memo": "Journal Explorer requires general ledger implementation",
                "debit": 0.0,
                "credit": 0.0,
                "supplier": "",
                "employee": "",
                "customer": "",
            }
        ]


class BankReconciliationWidget(BaseReportWidget, _DateRangeMixin):
    """Bank reconciliation snapshot by account number."""

    def __init__(self, db, account_number: str = '0228362'):
        self.account_number = account_number
        columns = [
            {"header": "Date", "key": "date"},
            {"header": "Description", "key": "description"},
            {"header": "Debit", "key": "debit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Credit", "key": "credit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Status", "key": "status"},
            {"header": "Receipt", "key": "reconciled_receipt_id"},
            {"header": "Balance After", "key": "balance_after", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Bank Reconciliation", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=6))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
            SELECT transaction_id, transaction_date, description,
                   debit_amount, credit_amount,
                   reconciliation_status, receipt_id,
                   balance
            FROM banking_transactions
            WHERE account_number = %s AND transaction_date BETWEEN %s AND %s
            ORDER BY transaction_date, transaction_id
            LIMIT 1000
            """,
            (self.account_number, start, end),
        )
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
                "balance_after": float(r[7] or 0),
            }
            for r in rows
        ]


class PLSummaryWidget(BaseReportWidget, _DateRangeMixin):
    """Profit and Loss summary grouped by month."""

    def __init__(self, db):
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "Revenue", "key": "revenue", "format": lambda v: f"${v:,.2f}"},
            {"header": "Expenses", "key": "expenses", "format": lambda v: f"${v:,.2f}"},
            {"header": "Profit", "key": "profit", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Profit & Loss", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
        
        # Get revenue from charters
        cur.execute(
            """
            SELECT 
                DATE_TRUNC('month', charter_date) AS period,
                COALESCE(SUM(total_amount_due), 0) AS revenue
            FROM charters
            WHERE charter_date BETWEEN %s AND %s
            GROUP BY 1
            ORDER BY 1
            """,
            (start, end),
        )
        revenue_rows = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
        
        # Get expenses from receipts
        cur.execute(
            """
            SELECT 
                DATE_TRUNC('month', receipt_date) AS period,
                COALESCE(SUM(gross_amount), 0) AS expenses
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s AND category != 'personal'
            GROUP BY 1
            ORDER BY 1
            """,
            (start, end),
        )
        expense_rows = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
        
        # Combine all periods
        all_periods = sorted(set(revenue_rows.keys()) | set(expense_rows.keys()))
        
        data = []
        for period in all_periods:
            revenue = revenue_rows.get(period, 0)
            expenses = expense_rows.get(period, 0)
            data.append(
                {
                    "period": period.date().isoformat() if hasattr(period, "date") else str(period),
                    "revenue": round(revenue, 2),
                    "expenses": round(expenses, 2),
                    "profit": round(revenue - expenses, 2),
                }
            )
        return data


class PLCategoryWidget(BaseReportWidget, _DateRangeMixin):
    """P&L grouped by account name per period."""

    def __init__(self, db):
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "Account Type", "key": "account_type"},
            {"header": "Account", "key": "account_name"},
            {"header": "Net", "key": "net", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "P&L by Category", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
        
        # Get revenue (from charters) - no category breakdown
        cur.execute(
            """
            SELECT 
                DATE_TRUNC('month', charter_date) AS period,
                'Revenue' AS account_type,
                'Charter Revenue' AS account_name,
                COALESCE(SUM(total_amount_due), 0) AS net
            FROM charters
            WHERE charter_date BETWEEN %s AND %s
            GROUP BY 1
            
            UNION ALL
            
            SELECT 
                DATE_TRUNC('month', receipt_date) AS period,
                'Expense' AS account_type,
                COALESCE(category, 'Uncategorized') AS account_name,
                COALESCE(SUM(gross_amount), 0) AS net
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s AND category != 'personal'
            GROUP BY 1, category
            
            ORDER BY 1, 2, 3
            """,
            (start, end, start, end),
        )
        rows = cur.fetchall()
        data = []
        for r in rows:
            data.append(
                {
                    "period": r[0].date().isoformat() if hasattr(r[0], "date") else str(r[0]),
                    "account_type": r[1],
                    "account_name": r[2],
                    "net": float(r[3] or 0),
                }
            )
        return data


class VehiclePerformanceWidget(BaseReportWidget, _DateRangeMixin):
    """Vehicle revenue vs expense with trips count."""

    def __init__(self, db):
        columns = [
            {"header": "Vehicle #", "key": "vehicle_number"},
            {"header": "Make", "key": "make"},
            {"header": "Model", "key": "model"},
            {"header": "Year", "key": "year"},
            {"header": "Trips", "key": "trips"},
            {"header": "Revenue", "key": "revenue", "format": lambda v: f"${v:,.2f}"},
            {"header": "Expense", "key": "expense", "format": lambda v: f"${v:,.2f}"},
            {"header": "Maint", "key": "maintenance", "format": lambda v: f"${v:,.2f}"},
            {"header": "Insurance", "key": "insurance", "format": lambda v: f"${v:,.2f}"},
            {"header": "Profit", "key": "profit", "format": lambda v: f"${v:,.2f}"},
            {"header": "Margin %", "key": "margin_pct", "format": lambda v: f"{v:.2f}%"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Vehicle Performance", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
        # Revenue by vehicle (requires vehicle_id on charters)
        cur.execute(
            """
            SELECT vehicle_id, COUNT(*) AS trips, COALESCE(SUM(gross_amount), 0) AS revenue
            FROM charters
            WHERE (pickup_date BETWEEN %s AND %s OR charter_date BETWEEN %s AND %s)
            GROUP BY vehicle_id
            """,
            (start, end, start, end),
        )
        revenue_map = {int(v or 0): {"trips": int(t or 0), "revenue": float(r or 0)} for v, t, r in cur.fetchall()}

        cur.execute(
            """
            SELECT vehicle_id,
                   COALESCE(SUM(gross_amount), 0) AS expense,
                   COALESCE(SUM(CASE WHEN description ILIKE '%maint%' THEN gross_amount ELSE 0 END), 0) AS maintenance,
                   COALESCE(SUM(CASE WHEN description ILIKE '%insur%' THEN gross_amount ELSE 0 END), 0) AS insurance
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
            GROUP BY vehicle_id
            """,
            (start, end),
        )
        expense_map = {
            int(v or 0): {
                "expense": float(e or 0),
                "maintenance": float(m or 0),
                "insurance": float(i or 0),
            }
            for v, e, m, i in cur.fetchall()
        }

        cur.execute("SELECT vehicle_id, vehicle_number, make, model, year FROM vehicles ORDER BY vehicle_number")
        rows = cur.fetchall()
        data = []
        for vid, num, make, model, year in rows:
            rev = revenue_map.get(int(vid or 0), {"revenue": 0.0, "trips": 0})
            exp = expense_map.get(int(vid or 0), {"expense": 0.0, "maintenance": 0.0, "insurance": 0.0})
            profit = rev.get("revenue", 0.0) - exp.get("expense", 0.0)
            margin = (profit / rev.get("revenue", 1)) * 100 if rev.get("revenue", 0) else 0.0
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
                    "margin_pct": round(margin, 2),
                }
            )
        return data


class DriverCostWidget(BaseReportWidget, _DateRangeMixin):
    """Driver payroll cost per driver."""

    def __init__(self, db):
        columns = [
            {"header": "Driver", "key": "name"},
            {"header": "Payruns", "key": "payruns"},
            {"header": "Total Cost", "key": "total_cost", "format": lambda v: f"${v:,.2f}"},
            {"header": "Gross Total", "key": "gross_total", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Driver Cost", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
            (start, end),
        )
        rows = cur.fetchall()
        return [
            {
                "driver_id": r[0],
                "name": r[1],
                "payruns": int(r[2] or 0),
                "total_cost": float(r[3] or 0),
                "gross_total": float(r[4] or 0),
            }
            for r in rows
        ]


class DriverRevenueVsPayWidget(BaseReportWidget, _DateRangeMixin):
    """Driver revenue (charters) vs payroll cost."""

    def __init__(self, db):
        columns = [
            {"header": "Driver", "key": "driver_name"},
            {"header": "Trips", "key": "trips"},
            {"header": "Revenue", "key": "revenue", "format": lambda v: f"${v:,.2f}"},
            {"header": "Profit After Pay", "key": "profit_after_pay", "format": lambda v: f"${v:,.2f}"},
            {"header": "Margin %", "key": "margin_pct", "format": lambda v: f"{v:.2f}%"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Driver Revenue vs Pay", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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

        # Revenue from charters
        cur.execute(
            """
            SELECT assigned_driver_id, COALESCE(SUM(total_amount_due), 0) AS revenue, COUNT(*) AS trips
            FROM charters
            WHERE charter_date BETWEEN %s AND %s AND assigned_driver_id IS NOT NULL
            GROUP BY assigned_driver_id
            """,
            (start, end),
        )
        rev_map = {int(r[0] or 0): {"revenue": float(r[1] or 0), "trips": int(r[2] or 0)} for r in cur.fetchall()}

        # Driver/employee info from employees table
        cur.execute(
            """
            SELECT employee_id, employee_name
            FROM employees
            WHERE employee_id > 0
            ORDER BY employee_id
            """,
        )
        rows = cur.fetchall()

        data = []
        for emp_id, emp_name in rows:
            rev = rev_map.pop(int(emp_id or 0), {"revenue": 0.0, "trips": 0})
            profit = rev.get("revenue", 0.0)
            data.append(
                {
                    "driver_id": emp_id,
                    "driver_name": emp_name or f"Driver {emp_id}",
                    "trips": rev.get("trips", 0),
                    "revenue": round(rev.get("revenue", 0.0), 2),
                    "profit_after_pay": round(profit, 2),
                    "margin_pct": round((profit / rev.get("revenue", 1)) * 100, 2) if rev.get("revenue", 0) else 0.0,
                }
            )

        for did, rev in rev_map.items():
            profit = rev.get("revenue", 0.0)
            data.append(
                {
                    "driver_id": did,
                    "driver_name": f"Driver {did}",
                    "trips": rev.get("trips", 0),
                    "revenue": round(rev.get("revenue", 0.0), 2),
                    "profit_after_pay": round(profit, 2),
                    "margin_pct": 100.0,
                }
            )
        return data


class FleetMaintenanceWidget(BaseReportWidget, _DateRangeMixin):
    """Maintenance/repairs/insurance/damage costs by vehicle."""

    def __init__(self, db):
        columns = [
            {"header": "Vehicle", "key": "vehicle_id"},
            {"header": "Maintenance", "key": "maintenance", "format": lambda v: f"${v:,.2f}"},
            {"header": "Repairs", "key": "repairs", "format": lambda v: f"${v:,.2f}"},
            {"header": "Insurance", "key": "insurance", "format": lambda v: f"${v:,.2f}"},
            {"header": "Damage", "key": "damage", "format": lambda v: f"${v:,.2f}"},
            {"header": "Total", "key": "total_expense", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Fleet Maintenance", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
            SELECT vehicle_id,
                   COALESCE(SUM(CASE WHEN description ILIKE '%maint%' THEN gross_amount ELSE 0 END), 0) AS maintenance,
                   COALESCE(SUM(CASE WHEN description ILIKE '%repair%' THEN gross_amount ELSE 0 END), 0) AS repairs,
                   COALESCE(SUM(CASE WHEN description ILIKE '%insur%' THEN gross_amount ELSE 0 END), 0) AS insurance,
                   COALESCE(SUM(CASE WHEN description ILIKE '%damage%' OR description ILIKE '%claim%' THEN gross_amount ELSE 0 END), 0) AS damage,
                   COALESCE(SUM(gross_amount), 0) AS total_expense
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
            GROUP BY vehicle_id
            ORDER BY total_expense DESC
            LIMIT 500
            """,
            (start, end),
        )
        rows = cur.fetchall()
        return [
            {
                "vehicle_id": r[0],
                "maintenance": float(r[1] or 0),
                "repairs": float(r[2] or 0),
                "insurance": float(r[3] or 0),
                "damage": float(r[4] or 0),
                "total_expense": float(r[5] or 0),
            }
            for r in rows
        ]


class BankRecSuggestionsWidget(BaseReportWidget):
    """Banking vs receipts amount/date suggestions."""

    def __init__(self, db):
        columns = [
            {"header": "Txn ID", "key": "transaction_id"},
            {"header": "Txn Date", "key": "transaction_date"},
            {"header": "Amount", "key": "amount", "format": lambda v: f"${v:,.2f}"},
            {"header": "Description", "key": "description"},
            {"header": "Candidates", "key": "candidate_summary"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Bank Rec Suggestions", columns)

    def fetch_rows(self) -> List[Dict[str, Any]]:
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
            SELECT bt.transaction_id, bt.trans_date, bt.trans_description,
                   COALESCE(bt.debit_amount, 0) - COALESCE(bt.credit_amount, 0) AS amount,
                   (
                       SELECT STRING_AGG(
                           CONCAT('Receipt ', r.receipt_id, ' ', r.receipt_date, ' $', r.gross_amount), '\n'
                       )
                       FROM receipts r
                       WHERE ABS(r.gross_amount) = ABS(COALESCE(bt.debit_amount,0) - COALESCE(bt.credit_amount,0))
                         AND r.receipt_date BETWEEN bt.trans_date - INTERVAL '1 day' AND bt.trans_date + INTERVAL '1 day'
                   ) AS candidates
            FROM banking_transactions bt
            WHERE bt.reconciliation_status IS NULL OR bt.reconciliation_status IN ('unreconciled','ignored')
            ORDER BY bt.trans_date DESC
            LIMIT 300
            """
        )
        rows = cur.fetchall()
        return [
            {
                "transaction_id": r[0],
                "transaction_date": str(r[1]),
                "description": r[2],
                "amount": float(r[3] or 0),
                "candidate_summary": r[4] or "",
            }
            for r in rows
        ]


class VehicleInsuranceWidget(BaseReportWidget):
    """Insurance cost per vehicle per year."""

    def __init__(self, db):
        columns = [
            {"header": "Vehicle", "key": "vehicle_id"},
            {"header": "Year", "key": "year"},
            {"header": "Insurance", "key": "insurance_cost", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Vehicle Insurance (Yearly)", columns)

    def fetch_rows(self) -> List[Dict[str, Any]]:
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
            SELECT vehicle_id,
                   EXTRACT(YEAR FROM receipt_date) AS yr,
                   COALESCE(SUM(CASE WHEN description ILIKE '%insur%' THEN gross_amount ELSE 0 END), 0) AS insurance_cost
            FROM receipts
            WHERE receipt_date BETWEEN (CURRENT_DATE - INTERVAL '5 years') AND CURRENT_DATE
            GROUP BY vehicle_id, yr
            ORDER BY yr DESC, vehicle_id
            """
        )
        rows = cur.fetchall()
        return [
            {
                "vehicle_id": r[0],
                "year": int(r[1]) if r[1] is not None else None,
                "insurance_cost": float(r[2] or 0),
            }
            for r in rows
        ]


class VehicleDamageWidget(BaseReportWidget, _DateRangeMixin):
    """Damage/claim counts and totals per vehicle."""

    def __init__(self, db):
        columns = [
            {"header": "Vehicle", "key": "vehicle_id"},
            {"header": "Damage Count", "key": "damage_count"},
            {"header": "Damage Total", "key": "damage_total", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Vehicle Damage Summary", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
            SELECT vehicle_id,
                   COUNT(*) AS damage_count,
                   COALESCE(SUM(gross_amount), 0) AS damage_total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (description ILIKE '%damage%' OR description ILIKE '%claim%' OR description ILIKE '%collision%' OR description ILIKE '%accident%')
            GROUP BY vehicle_id
            ORDER BY damage_total DESC
            """,
            (start, end),
        )
        rows = cur.fetchall()
        return [
            {
                "vehicle_id": r[0],
                "damage_count": int(r[1] or 0),
                "damage_total": float(r[2] or 0),
            }
            for r in rows
        ]


class DriverMonthlyCostWidget(BaseReportWidget, _DateRangeMixin):
    """Driver payroll cost grouped monthly."""

    def __init__(self, db):
        columns = [
            {"header": "Period", "key": "period"},
            {"header": "Driver", "key": "name"},
            {"header": "Payruns", "key": "payruns"},
            {"header": "Total Cost", "key": "total_cost", "format": lambda v: f"${v:,.2f}"},
            {"header": "Gross Total", "key": "gross_total", "format": lambda v: f"${v:,.2f}"},
        ]
        self.db = db
        BaseReportWidget.__init__(self, db, "Driver Monthly Cost", columns)
        layout: QVBoxLayout = self.layout()
        layout.insertLayout(1, self._init_date_controls(months_back=12))

    def fetch_rows(self) -> List[Dict[str, Any]]:
        start, end = self._date_range()
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
            (start, end),
        )
        rows = cur.fetchall()
        return [
            {
                "period": r[0].date().isoformat() if hasattr(r[0], "date") else str(r[0]),
                "driver_id": r[1],
                "name": r[2],
                "payruns": int(r[3] or 0),
                "total_cost": float(r[4] or 0),
                "gross_total": float(r[5] or 0),
            }
            for r in rows
        ]


__all__ = [
    "TrialBalanceWidget",
    "JournalExplorerWidget",
    "BankReconciliationWidget",
    "PLSummaryWidget",
    "PLCategoryWidget",
    "VehiclePerformanceWidget",
    "DriverCostWidget",
    "FleetMaintenanceWidget",
    "VehicleInsuranceWidget",
    "VehicleDamageWidget",
    "DriverMonthlyCostWidget",
    "DriverRevenueVsPayWidget",
    "BankRecSuggestionsWidget",
]
