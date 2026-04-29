import os
import sys
from dataclasses import dataclass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "almsdata")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "ArrowLimousine")

ROOT = r"l:\\limo"
DESKTOP = os.path.join(ROOT, "desktop_app")
if DESKTOP not in sys.path:
    sys.path.insert(0, DESKTOP)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication
from db_connection import DatabaseConnection
from accounting_receipts_widget import AccountingReceiptsWidget
from enhanced_banking_manager import EnhancedBankingManager
from payroll_entry_widget import PayrollEntryWidget
from payroll_remittances_widget import PayrollRemittancesWidget
from charter_form_widget import CharterFormWidget
from year_end_management_widget import YearEndManagementWidget


@dataclass
class CaseResult:
    type_name: str
    test_id: str
    data_exists: bool
    route_target: str
    hook_present: bool
    result: str
    notes: str


def fetch_one(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def load_test_ids(db):
    cur = db.conn.cursor()
    ids = {}

    row = fetch_one(cur, "SELECT receipt_id FROM receipts ORDER BY receipt_id DESC LIMIT 1")
    ids["receipt_id"] = int(row[0]) if row and row[0] is not None else None

    row = fetch_one(cur, "SELECT transaction_id FROM banking_transactions ORDER BY transaction_id DESC LIMIT 1")
    ids["transaction_id"] = int(row[0]) if row and row[0] is not None else None

    row = fetch_one(cur, "SELECT employee_id FROM employees ORDER BY employee_id DESC LIMIT 1")
    ids["employee_id"] = int(row[0]) if row and row[0] is not None else None

    row = fetch_one(cur, "SELECT remittance_id FROM payroll_remittances ORDER BY remittance_id DESC LIMIT 1")
    ids["remittance_id"] = int(row[0]) if row and row[0] is not None else None

    row = fetch_one(cur, "SELECT charter_id FROM charters ORDER BY charter_id DESC LIMIT 1")
    ids["charter_id"] = int(row[0]) if row and row[0] is not None else None

    row = fetch_one(
        cur,
        """
        SELECT income_id, charter_id
        FROM income_ledger
        WHERE charter_id IS NOT NULL
        ORDER BY income_id DESC
        LIMIT 1
        """,
    )
    ids["income_id"] = int(row[0]) if row and row[0] is not None else None
    ids["income_charter_id"] = int(row[1]) if row and row[1] is not None else None

    cur.close()
    return ids


def bool_sql(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return bool(row and row[0])


def run_smoke():
    app = QApplication([])
    db = DatabaseConnection(
        {
            "host": "localhost",
            "port": 5432,
            "database": "almsdata",
            "user": "postgres",
            "password": "ArrowLimousine",
            "sslmode": None,
        }
    )

    ids = load_test_ids(db)

    cur = db.conn.cursor()
    data_exists = {
        "receipt": ids["receipt_id"] is not None
        and bool_sql(cur, "SELECT EXISTS(SELECT 1 FROM receipts WHERE receipt_id=%s)", (ids["receipt_id"],)),
        "transaction": ids["transaction_id"] is not None
        and bool_sql(
            cur,
            "SELECT EXISTS(SELECT 1 FROM banking_transactions WHERE transaction_id=%s)",
            (ids["transaction_id"],),
        ),
        "employee": ids["employee_id"] is not None
        and bool_sql(cur, "SELECT EXISTS(SELECT 1 FROM employees WHERE employee_id=%s)", (ids["employee_id"],)),
        "remittance": ids["remittance_id"] is not None
        and bool_sql(
            cur,
            "SELECT EXISTS(SELECT 1 FROM payroll_remittances WHERE remittance_id=%s)",
            (ids["remittance_id"],),
        ),
        "charter": ids["charter_id"] is not None
        and bool_sql(cur, "SELECT EXISTS(SELECT 1 FROM charters WHERE charter_id=%s)", (ids["charter_id"],)),
        "income": ids["income_id"] is not None
        and bool_sql(cur, "SELECT EXISTS(SELECT 1 FROM income_ledger WHERE income_id=%s)", (ids["income_id"],)),
    }
    cur.close()

    results = []

    # Receipt
    receipt_hook = hasattr(AccountingReceiptsWidget, "open_receipt_by_id")
    receipt_ok = False
    receipt_notes = ""
    receipt_widget = None
    try:
        receipt_widget = AccountingReceiptsWidget(db)
        app.processEvents()
        if receipt_hook and ids["receipt_id"] is not None:
            receipt_ok = bool(receipt_widget.open_receipt_by_id(ids["receipt_id"]))
    except Exception as exc:
        receipt_notes = str(exc)
    results.append(
        CaseResult(
            "receipt",
            str(ids["receipt_id"]),
            data_exists["receipt"],
            "accounting.receipts",
            receipt_hook,
            "PASS" if (data_exists["receipt"] and receipt_hook and receipt_ok) else "FAIL",
            receipt_notes or ("opened" if receipt_ok else "open returned false"),
        )
    )

    # Transaction
    txn_hook = hasattr(EnhancedBankingManager, "focus_transaction_id")
    txn_ok = False
    txn_notes = ""
    banking_widget = None
    try:
        banking_widget = EnhancedBankingManager(db)
        app.processEvents()
        if txn_hook and ids["transaction_id"] is not None:
            txn_ok = bool(banking_widget.focus_transaction_id(ids["transaction_id"]))
    except Exception as exc:
        txn_notes = str(exc)
    results.append(
        CaseResult(
            "transaction",
            str(ids["transaction_id"]),
            data_exists["transaction"],
            "accounting.banking",
            txn_hook,
            "PASS" if (data_exists["transaction"] and txn_hook and txn_ok) else "FAIL",
            txn_notes or ("focused" if txn_ok else "focus returned false"),
        )
    )

    # Employee
    emp_hook = hasattr(PayrollEntryWidget, "focus_employee_id")
    emp_ok = False
    emp_notes = ""
    payroll_widget = None
    try:
        payroll_widget = PayrollEntryWidget(db)
        app.processEvents()
        if emp_hook and ids["employee_id"] is not None:
            emp_ok = bool(payroll_widget.focus_employee_id(ids["employee_id"], None))
    except Exception as exc:
        emp_notes = str(exc)
    results.append(
        CaseResult(
            "employee",
            str(ids["employee_id"]),
            data_exists["employee"],
            "accounting.payroll_entry",
            emp_hook,
            "PASS" if (data_exists["employee"] and emp_hook and emp_ok) else "FAIL",
            emp_notes or ("focused" if emp_ok else "focus returned false"),
        )
    )

    # Remittance
    rem_hook = hasattr(PayrollRemittancesWidget, "focus_remittance_id")
    rem_ok = False
    rem_notes = ""
    rem_widget = None
    try:
        rem_widget = PayrollRemittancesWidget(db)
        app.processEvents()
        if rem_hook and ids["remittance_id"] is not None:
            rem_ok = bool(rem_widget.focus_remittance_id(ids["remittance_id"]))
    except Exception as exc:
        rem_notes = str(exc)
    results.append(
        CaseResult(
            "remittance",
            str(ids["remittance_id"]),
            data_exists["remittance"],
            "accounting.payroll_remittances",
            rem_hook,
            "PASS" if (data_exists["remittance"] and rem_hook and rem_ok) else "FAIL",
            rem_notes or ("focused" if rem_ok else "focus returned false"),
        )
    )

    # Charter
    char_hook = hasattr(CharterFormWidget, "load_charter")
    char_ok = False
    char_notes = ""
    charter_widget = None
    try:
        charter_widget = CharterFormWidget(db)
        app.processEvents()
        if char_hook and ids["charter_id"] is not None:
            charter_widget.load_charter(ids["charter_id"])
            char_ok = True
    except Exception as exc:
        char_notes = str(exc)
    results.append(
        CaseResult(
            "charter",
            str(ids["charter_id"]),
            data_exists["charter"],
            "operations.dispatch",
            char_hook,
            "PASS" if (data_exists["charter"] and char_hook and char_ok) else "FAIL",
            char_notes or ("loaded" if char_ok else "load not executed"),
        )
    )

    # Income -> charter
    income_hook = hasattr(YearEndManagementWidget, "_resolve_charter_id_from_income_id")
    income_ok = False
    income_notes = ""
    resolved_charter = None
    try:
        year_end = YearEndManagementWidget(db)
        app.processEvents()
        if income_hook and ids["income_id"] is not None:
            resolved_charter = year_end._resolve_charter_id_from_income_id(ids["income_id"])
            if resolved_charter:
                if charter_widget is None:
                    charter_widget = CharterFormWidget(db)
                charter_widget.load_charter(int(resolved_charter))
                income_ok = True
    except Exception as exc:
        income_notes = str(exc)
    results.append(
        CaseResult(
            "income",
            str(ids["income_id"]),
            data_exists["income"],
            "operations.dispatch(via income->charter)",
            income_hook,
            "PASS" if (data_exists["income"] and income_hook and income_ok and bool(resolved_charter)) else "FAIL",
            income_notes or f"resolved_charter={resolved_charter}",
        )
    )

    print("TYPE | TEST_ID | DATA_EXISTS | ROUTE_TARGET | CODE_HOOK_PRESENT | RESULT | NOTES")
    fail_count = 0
    for r in results:
        if r.result != "PASS":
            fail_count += 1
        print(
            f"{r.type_name} | {r.test_id} | {'YES' if r.data_exists else 'NO'} | {r.route_target} | "
            f"{'YES' if r.hook_present else 'NO'} | {r.result} | {r.notes}"
        )

    try:
        db.conn.close()
    except Exception:
        pass
    app.quit()

    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(run_smoke())
