"""Constructor-level smoke test for curated/safe desktop widgets.

- Discovers QWidget subclasses in selected desktop_app modules.
- Instantiates each class in an isolated subprocess with a timeout.
- Produces a runtime fail matrix by module/class.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from datetime import datetime

ROOT = pathlib.Path(r"l:\limo")
DESKTOP = ROOT / "desktop_app"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


# Curated: include widget modules, skip app entrypoints and known non-widget orchestrators.
EXCLUDE_STEMS = {
    "main_widget",
}

# Conservative safety excludes (can be added back later if needed).
EXCLUDE_MODULES = {
    "desktop_app.admin_management_widget",  # can trigger nested heavy tabs/tools
}


def _run_py(code: str, timeout_sec: int = 20) -> tuple[int, str, str, bool]:
    proc = subprocess.run(
        [str(PYTHON), "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    return proc.returncode, proc.stdout, proc.stderr, False


def _run_py_timeout_safe(code: str, timeout_sec: int = 20):
    try:
        return _run_py(code, timeout_sec)
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", e.stderr or "", True


def discover_widget_classes(module_name: str) -> tuple[bool, list[str], str]:
    code = f"""
import inspect, json, pathlib, sys
from PyQt6.QtWidgets import QWidget
root = pathlib.Path(r'{ROOT}')
desktop = root / 'desktop_app'
sys.path.insert(0, str(root))
sys.path.insert(0, str(desktop))
mod = __import__('{module_name}', fromlist=['*'])
classes = []
for name, cls in inspect.getmembers(mod, inspect.isclass):
    if cls.__module__ != mod.__name__:
        continue
    if not issubclass(cls, QWidget):
        continue
    classes.append(name)
print(json.dumps(sorted(classes)))
"""
    rc, out, err, timed_out = _run_py_timeout_safe(code, timeout_sec=20)
    if timed_out:
        return False, [], "discover timeout"
    if rc != 0:
        return False, [], (err.strip() or out.strip() or f"discover failed rc={rc}")
    try:
        return True, json.loads(out.strip() or "[]"), ""
    except Exception as e:
        return False, [], f"discover parse error: {e}"


def run_constructor(module_name: str, class_name: str) -> tuple[bool, str, str]:
    code = f"""
import builtins, getpass, pathlib, sys
builtins.input = lambda *a, **k: ''
getpass.getpass = lambda *a, **k: ''

root = pathlib.Path(r'{ROOT}')
desktop = root / 'desktop_app'
sys.path.insert(0, str(root))
sys.path.insert(0, str(desktop))

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

class DummyDB:
    def get_cursor(self):
        raise RuntimeError('DummyDB no cursor')
    def commit(self):
        return None
    def rollback(self):
        return None

class DummyParent:
    pass

try:
    from db_connection import DatabaseConnection
    db = DatabaseConnection({{
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', '5432')),
        'database': os.environ.get('DB_NAME', 'almsdata'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD', 'ArrowLimousine'),
        'sslmode': os.environ.get('DB_SSLMODE', 'disable'),
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

ok = False
last_error = ''
used = ''
for name, ctor in strategies:
    try:
        obj = ctor()
        used = name
        ok = True
        try:
            obj.deleteLater()
        except Exception:
            pass
        break
    except Exception as e:
        last_error = f"{{type(e).__name__}}: {{e}}"

app.quit()
if ok:
    print('OK|' + used)
    raise SystemExit(0)
print('FAIL|' + (last_error or 'unknown'))
raise SystemExit(2)
"""
    rc, out, err, timed_out = _run_py_timeout_safe(code, timeout_sec=25)
    if timed_out:
        return False, "timeout", ""
    text = (out.strip() or err.strip()).strip()
    if rc == 0 and text.startswith("OK|"):
        return True, "", text.split("|", 1)[1]
    if text.startswith("FAIL|"):
        return False, text.split("|", 1)[1], ""
    return False, text or f"rc={rc}", ""


def main() -> int:
    modules = [
        f"desktop_app.{p.stem}"
        for p in sorted(DESKTOP.glob("*_widget.py"))
        if p.stem not in EXCLUDE_STEMS
    ]
    modules = [m for m in modules if m not in EXCLUDE_MODULES]

    report = {
        "generated_at": datetime.now().isoformat(),
        "modules": [],
        "summary": {},
    }

    total_classes = 0
    passed = 0
    failed = 0
    discover_failed = 0

    for module in modules:
        mrow = {
            "module": module,
            "discover_ok": True,
            "discover_error": "",
            "classes": [],
        }

        ok, classes, derr = discover_widget_classes(module)
        if not ok:
            mrow["discover_ok"] = False
            mrow["discover_error"] = derr
            discover_failed += 1
            report["modules"].append(mrow)
            continue

        for cls_name in classes:
            total_classes += 1
            c_ok, c_err, strategy = run_constructor(module, cls_name)
            if c_ok:
                passed += 1
            else:
                failed += 1
            mrow["classes"].append(
                {
                    "class": cls_name,
                    "ok": c_ok,
                    "error": c_err,
                    "strategy": strategy,
                }
            )

        report["modules"].append(mrow)

    report["summary"] = {
        "modules_total": len(modules),
        "modules_discover_failed": discover_failed,
        "classes_total": total_classes,
        "classes_passed": passed,
        "classes_failed": failed,
    }

    out = ROOT / "tmp" / f"widget_constructor_smoke_safe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
