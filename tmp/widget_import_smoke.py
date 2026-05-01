import importlib
import pathlib
import sys

root = pathlib.Path(r"l:\limo")
desktop = root / "desktop_app"
sys.path.insert(0, str(root))
sys.path.insert(0, str(desktop))

mods = [
    f"desktop_app.{p.stem}"
    for p in sorted(desktop.glob("*_widget.py"))
    if p.stem != "main_widget"
]
if (desktop / "dashboard_classes.py").exists():
    mods.append("desktop_app.dashboard_classes")

fails = []
ok = []
for m in mods:
    try:
        importlib.import_module(m)
        ok.append(m)
    except Exception as e:
        fails.append((m, f"{type(e).__name__}: {e}"))

print("WIDGET_IMPORT_TOTAL", len(mods))
print("WIDGET_IMPORT_OK", len(ok))
print("WIDGET_IMPORT_FAIL", len(fails))
for module, error in fails:
    print(f"FAIL|{module}|{error}")
