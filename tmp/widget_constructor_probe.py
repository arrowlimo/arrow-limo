from __future__ import annotations

import builtins
import getpass
import os
import pathlib
import sys

builtins.input = lambda *a, **k: ""
getpass.getpass = lambda *a, **k: ""
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if len(sys.argv) < 3:
    print("USAGE: widget_constructor_probe.py <module> <class>")
    raise SystemExit(2)

module_name = sys.argv[1]
class_name = sys.argv[2]

root = pathlib.Path(r"l:\limo")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "desktop_app"))

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class DummyDB:
    def get_cursor(self):
        raise RuntimeError("dummy db")

    def commit(self):
        return None

    def rollback(self):
        return None


class DummyParent:
    pass


try:
    from db_connection import DatabaseConnection

    db = DatabaseConnection(
        {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", "5432")),
            "database": os.environ.get("DB_NAME", "almsdata"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", "ArrowLimousine"),
            "sslmode": os.environ.get("DB_SSLMODE", "disable"),
        }
    )
except Exception:
    db = DummyDB()

mod = __import__(module_name, fromlist=["*"])
cls = getattr(mod, class_name)

try:
    import psycopg2 as _pg2
    raw_conn = _pg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "ArrowLimousine"),
    )
except Exception:
    raw_conn = None

strategies = [
    ("db", lambda: cls(db)),
    ("db_parent", lambda: cls(db, DummyParent())),
    ("conn", lambda: cls(raw_conn)),
    ("conn_parent", lambda: cls(raw_conn, DummyParent())),
    ("parent", lambda: cls(DummyParent())),
    ("no_args", lambda: cls()),
]

last = ""
for strategy, ctor in strategies:
    try:
        obj = ctor()
        try:
            obj.deleteLater()
        except Exception:
            pass
        print(f"PASS|{module_name}:{class_name}|{strategy}")
        app.quit()
        raise SystemExit(0)
    except Exception as e:
        last = f"{type(e).__name__}: {e}"

print(f"FAIL|{module_name}:{class_name}|{last}")
app.quit()
raise SystemExit(1)
