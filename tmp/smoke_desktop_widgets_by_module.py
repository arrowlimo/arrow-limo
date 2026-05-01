"""
Desktop widget smoke test (import + best-effort instantiation) with module-level fail report.
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import pathlib
import sys
import traceback
import builtins
import getpass
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
DESKTOP_APP_DIR = ROOT / "desktop_app"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(DESKTOP_APP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_APP_DIR))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402


# Prevent terminal prompts from blocking smoke runs.
builtins.input = lambda *args, **kwargs: ""
getpass.getpass = lambda *args, **kwargs: ""


SKIP_INIT_MODULES = {
    # Constructs nested tabs that may trigger interactive/long-running code.
    "desktop_app.admin_management_widget",
}


@dataclass
class WidgetResult:
    class_name: str
    init_ok: bool
    init_error: str
    strategy: str


@dataclass
class ModuleResult:
    module: str
    import_ok: bool
    import_error: str
    widget_results: list[WidgetResult]


class DummyDB:
    """Fallback DB object for widgets that only need method presence."""

    def get_cursor(self):
        raise RuntimeError("DummyDB: get_cursor unavailable")

    def commit(self):
        return None

    def rollback(self):
        return None


class DummyParent:
    pass


def _build_db() -> Any:
    try:
        from db_connection import DatabaseConnection

        cfg = {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", "5432")),
            "database": os.environ.get("DB_NAME", "almsdata"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", "ArrowLimousine"),
            "sslmode": os.environ.get("DB_SSLMODE", "disable"),
        }
        return DatabaseConnection(cfg)
    except Exception:
        return DummyDB()


def _iter_widget_modules() -> list[str]:
    modules = []
    for p in sorted(DESKTOP_APP_DIR.glob("*_widget.py")):
        name = p.stem
        if name in {"main_widget"}:
            continue
        modules.append(f"desktop_app.{name}")

    # Include non *_widget files that still host key widgets
    extras = [
        "desktop_app.dashboard_classes",
    ]
    for module in extras:
        if (DESKTOP_APP_DIR / f"{module.split('.')[-1]}.py").exists():
            modules.append(module)
    return modules


def _discover_widget_classes(module_obj: Any) -> list[type]:
    found = []
    for _, cls in inspect.getmembers(module_obj, inspect.isclass):
        if cls.__module__ != module_obj.__name__:
            continue
        if not issubclass(cls, QWidget):
            continue
        found.append(cls)
    return found


def _try_init(cls: type, db: Any) -> WidgetResult:
    strategies = [
        ("db", lambda: cls(db)),
        ("db_parent", lambda: cls(db, DummyParent())),
        ("parent", lambda: cls(DummyParent())),
        ("no_args", lambda: cls()),
    ]
    last_error = ""
    for name, ctor in strategies:
        try:
            obj = ctor()
            if isinstance(obj, QWidget):
                obj.deleteLater()
            return WidgetResult(cls.__name__, True, "", name)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
    return WidgetResult(cls.__name__, False, last_error, "none")


def run_smoke() -> tuple[list[ModuleResult], dict[str, int]]:
    db = _build_db()
    results: list[ModuleResult] = []

    for module_name in _iter_widget_modules():
        try:
            module_obj = importlib.import_module(module_name)
            widget_classes = _discover_widget_classes(module_obj)
            if module_name in SKIP_INIT_MODULES:
                widget_results = [
                    WidgetResult(
                        class_name=cls.__name__,
                        init_ok=False,
                        init_error="skipped: blocked constructor in smoke mode",
                        strategy="skipped",
                    )
                    for cls in widget_classes
                ]
            else:
                widget_results = [_try_init(cls, db) for cls in widget_classes]
            results.append(
                ModuleResult(
                    module=module_name,
                    import_ok=True,
                    import_error="",
                    widget_results=widget_results,
                )
            )
        except Exception as e:
            tb = traceback.format_exc(limit=2)
            results.append(
                ModuleResult(
                    module=module_name,
                    import_ok=False,
                    import_error=f"{type(e).__name__}: {e}\n{tb}",
                    widget_results=[],
                )
            )

    summary = {
        "modules_total": len(results),
        "modules_import_failed": sum(1 for r in results if not r.import_ok),
        "modules_widget_init_failed": sum(
            1
            for r in results
            if r.import_ok and any(not w.init_ok for w in r.widget_results)
        ),
        "widgets_total": sum(len(r.widget_results) for r in results),
        "widgets_failed": sum(
            1 for r in results for w in r.widget_results if not w.init_ok
        ),
    }
    return results, summary


def main() -> int:
    app = QApplication.instance() or QApplication([])

    results, summary = run_smoke()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"desktop_widget_smoke_report_{ts}.json"

    payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "modules": [
            {
                **asdict(m),
                "widget_results": [asdict(w) for w in m.widget_results],
            }
            for m in results
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("WIDGET_SMOKE_SUMMARY", json.dumps(summary, sort_keys=True))
    print("WIDGET_SMOKE_REPORT", str(out_json))

    failed_modules = [m.module for m in results if not m.import_ok]
    failed_widgets = [
        f"{m.module}:{w.class_name}"
        for m in results
        for w in m.widget_results
        if not w.init_ok
    ]

    if failed_modules:
        print("IMPORT_FAIL_MODULES")
        for name in failed_modules:
            print(name)

    if failed_widgets:
        print("INIT_FAIL_WIDGETS")
        for name in failed_widgets:
            print(name)

    app.quit()
    return 1 if (failed_modules or failed_widgets) else 0


if __name__ == "__main__":
    raise SystemExit(main())
