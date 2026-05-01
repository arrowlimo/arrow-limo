"""Constructor-level smoke for explicit desktop widget targets."""

from __future__ import annotations

import json
import pathlib
import subprocess
from datetime import datetime

ROOT = pathlib.Path(r"l:\limo")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

TARGETS = [
    ("desktop_app.mega_menu_widget", "MegaMenuWidget"),
    ("desktop_app.report_explorer_widget", "ReportExplorerWidget"),
    ("desktop_app.employee_management_widget", "EmployeeManagementWidget"),
    ("desktop_app.vehicle_management_widget", "VehicleManagementWidget"),
    ("desktop_app.dispatch_management_widget", "DispatchManagementWidget"),
    ("desktop_app.document_management_widget", "DocumentManagementWidget"),
    ("desktop_app.charter_form_widget", "CharterFormWidget"),
    ("desktop_app.manage_banking_widget", "ManageBankingWidget"),
    ("desktop_app.manage_cash_box_widget", "ManageCashBoxWidget"),
    ("desktop_app.report_management_widget", "ReportManagementWidget"),
    ("desktop_app.roe_form_widget", "ROEFormWidget"),
    ("desktop_app.dashboard_classes", "FleetManagementWidget"),
    ("desktop_app.dashboard_classes", "FinancialDashboardWidget"),
]


def run_target(module_name: str, class_name: str):
    code = f"""
import builtins, getpass, pathlib, sys, os
builtins.input=lambda *a,**k: ''
getpass.getpass=lambda *a,**k: ''
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

root = pathlib.Path(r'{ROOT}')
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'desktop_app'))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

class DummyDB:
    def get_cursor(self):
        raise RuntimeError('dummy db')
    def commit(self):
        return None
    def rollback(self):
        return None

class DummyParent:
    pass

try:
    from db_connection import DatabaseConnection
    db = DatabaseConnection({{
        'host': os.environ.get('DB_HOST','localhost'),
        'port': int(os.environ.get('DB_PORT','5432')),
        'database': os.environ.get('DB_NAME','almsdata'),
        'user': os.environ.get('DB_USER','postgres'),
        'password': os.environ.get('DB_PASSWORD','ArrowLimousine'),
        'sslmode': os.environ.get('DB_SSLMODE','disable'),
    }})
except Exception:
    db = DummyDB()

mod = __import__('{module_name}', fromlist=['*'])
cls = getattr(mod, '{class_name}')
try:
    import psycopg2 as _pg2
    raw_conn = _pg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        port=int(os.environ.get('DB_PORT','5432')),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','ArrowLimousine'),
    )
except Exception:
    raw_conn = None
strategies = [
    ('db', lambda: cls(db)),
    ('db_parent', lambda: cls(db, DummyParent())),
    ('conn', lambda: cls(raw_conn)),
    ('conn_parent', lambda: cls(raw_conn, DummyParent())),
    ('parent', lambda: cls(DummyParent())),
    ('no_args', lambda: cls()),
]
last = ''
for s, ctor in strategies:
    try:
        obj = ctor()
        try:
            obj.deleteLater()
        except Exception:
            pass
        print('OK|' + s)
        app.quit()
        raise SystemExit(0)
    except Exception as e:
        last = f"{{type(e).__name__}}: {{e}}"
print('FAIL|' + (last or 'unknown'))
app.quit()
raise SystemExit(2)
"""
    try:
        p = subprocess.run(
            [str(PYTHON), "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = (p.stdout.strip() or p.stderr.strip()).strip()
        if p.returncode == 0 and text.startswith("OK|"):
            return True, "", text.split("|", 1)[1]
        if text.startswith("FAIL|"):
            return False, text.split("|", 1)[1], ""
        return False, text or f"rc={p.returncode}", ""
    except subprocess.TimeoutExpired:
        return False, "timeout", ""


def main():
    rows = []
    passed = failed = 0
    for module, klass in TARGETS:
        ok, err, strategy = run_target(module, klass)
        rows.append(
            {
                "module": module,
                "class": klass,
                "ok": ok,
                "error": err,
                "strategy": strategy,
            }
        )
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"TARGET|{module}:{klass}|{'PASS' if ok else 'FAIL'}")

    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "targets_total": len(TARGETS),
            "targets_passed": passed,
            "targets_failed": failed,
        },
        "results": rows,
    }
    out = ROOT / "tmp" / f"widget_constructor_smoke_targets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("CONSTRUCTOR_SMOKE_SUMMARY", json.dumps(report["summary"], sort_keys=True))
    print("CONSTRUCTOR_SMOKE_REPORT", str(out))
    for r in rows:
        if not r["ok"]:
            print(f"INIT_FAIL|{r['module']}:{r['class']}|{r['error']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
