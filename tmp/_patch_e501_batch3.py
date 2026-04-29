"""Patch 4 remaining E501 lines in driver_calendar and vendor_management."""
import ast
from pathlib import Path

patches = {
    "desktop_app/driver_calendar_widget.py": [
        (
            "                           COALESCE(v.vehicle_number, c.vehicle, '') AS vehicle_number,",
            "                           COALESCE(\n"
            "                               v.vehicle_number, c.vehicle, ''\n"
            "                           ) AS vehicle_number,",
        ),
        (
            '                driver_log_text = f"\u2705 Driver Log Found (Submitted: {\n'
            "                                                                    submitted_at\n"
            '                                                                    })\\n"',
            '                driver_log_text = (\n'
            '                    "\u2705 Driver Log Found"\n'
            '                    f" (Submitted: {submitted_at})\\n"\n'
            "                )",
        ),
    ],
    "desktop_app/vendor_management_widget.py": [
        (
            '                    "Use the Merge function in Vendor Standardization instead.",',
            '                    "Use the Merge function in Vendor"\n'
            '                    " Standardization instead.",',
        ),
        (
            '                f"Vendor <b>{self._selected_vendor_name}</b> has been deleted.",',
            '                f"Vendor <b>{self._selected_vendor_name}</b>"\n'
            '                " has been deleted.",',
        ),
    ],
}

for path, fixes in patches.items():
    p = Path(path)
    src = p.read_text(encoding="utf-8")
    for old, new in fixes:
        if old not in src:
            print(f"WARN not found in {path}: {old[:70]!r}")
        src = src.replace(old, new, 1)
    p.write_text(src, encoding="utf-8")
    try:
        ast.parse(src)
        print(f"AST_OK  {path}")
    except SyntaxError as e:
        print(f"AST_FAIL {path}: {e}")
