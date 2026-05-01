"""Constructor-level smoke test for a curated desktop widget module list."""

from __future__ import annotations

import json
import pathlib
import subprocess
from datetime import datetime

ROOT = pathlib.Path(r"l:\limo")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

CURATED_MODULES = [
    "desktop_app.mega_menu_widget",
    "desktop_app.report_explorer_widget",
    "desktop_app.employee_management_widget",
    "desktop_app.vehicle_management_widget",
    "desktop_app.dispatch_management_widget",
    "desktop_app.document_management_widget",
    "desktop_app.charter_form_widget",
    "desktop_app.manage_banking_widget",
    "desktop_app.manage_cash_box_widget",
    "desktop_app.report_management_widget",
    "desktop_app.receipt_search_match_widget",
    "desktop_app.t2_data_entry_widget",
    "desktop_app.vendor_invoice_manager",
    "desktop_app.roe_form_widget",
    "desktop_app.dashboard_classes",
]


def run_py(code: str, timeout_sec: int = 12):
    try:
        p = subprocess.run(
            [str(PYTHON), "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", e.stderr or "", True


def discover(module_name: str):
    code = f"""
import inspect, json, pathlib, sys
from PyQt6.QtWidgets import QWidget
root = pathlib.Path(r'{ROOT}')
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'desktop_app'))
mod = __import__('{module_name}', fromlist=['*'])
out = []
for name, cls in inspect.getmembers(mod, inspect.isclass):
    if cls.__module__ == mod.__name__ and issubclass(cls, QWidget):
        out.append(name)
print(json.dumps(sorted(out)))
"""
    rc, out, err, timed_out = run_py(code, timeout_sec=10)
    if timed_out:
        return False, [], "discover timeout"
    if rc != 0:
        return False, [], (err.strip() or out.strip() or f"discover rc={rc}")
    try:
        return True, json.loads(out.strip() or "[]"), ""
    except Exception as e:
        return False, [], f"discover parse: {e}"


def instantiate(module_name: str, class_name: str):
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
strategies = [
    ('db', lambda: cls(db)),
    ('db_parent', lambda: cls(db, DummyParent())),
    ('parent', lambda: cls(DummyParent())),
    ('no_args', lambda: cls()),
]
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
print('FAIL|' + last)
app.quit()
raise SystemExit(2)
"""
    rc, out, err, timed_out = run_py(code, timeout_sec=15)
    text = (out.strip() or err.strip()).strip()
    if timed_out:
        return False, "timeout", ""
    if rc == 0 and text.startswith("OK|"):
        return True, "", text.split("|", 1)[1]
    if text.startswith("FAIL|"):
        return False, text.split("|", 1)[1], ""
    return False, text or f"rc={rc}", ""


def main():
    report = {"generated_at": datetime.now().isoformat(), "modules": [], "summary": {}}

    total = passed = failed = 0
    discover_failed = 0

    for module in CURATED_MODULES:
        row = {"module": module, "discover_ok": True, "discover_error": "", "classes": []}
        ok, classes, derr = discover(module)
        if not ok:
            row["discover_ok"] = False
            row["discover_error"] = derr
            discover_failed += 1
            report["modules"].append(row)
            continue

        for cls in classes:
            total += 1
            c_ok, c_err, strat = instantiate(module, cls)
            if c_ok:
                passed += 1
            else:
                failed += 1
            row["classes"].append({"class": cls, "ok": c_ok, "error": c_err, "strategy": strat})

        report["modules"].append(row)

    report["summary"] = {
        "modules_total": len(CURATED_MODULES),
        "modules_discover_failed": discover_failed,
        "classes_total": total,
        "classes_passed": passed,
        "classes_failed": failed,
    }

    out = ROOT / "tmp" / f"widget_constructor_smoke_curated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("CONSTRUCTOR_SMOKE_SUMMARY", json.dumps(report["summary"], sort_keys=True))
    print("CONSTRUCTOR_SMOKE_REPORT", str(out))

    for m in report["modules"]:
        if not m["discover_ok"]:
            print(f"DISCOVER_FAIL|{m['module']}|{m['discover_error']}")
            continue
        for c in m["classes"]:
            if not c["ok"]:
                print(f"INIT_FAIL|{m['module']}:{c['class']}|{c['error']}")

    return 1 if (discover_failed or failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
