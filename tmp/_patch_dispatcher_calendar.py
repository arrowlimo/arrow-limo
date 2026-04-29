"""Patch 2 remaining E501 lines in dispatcher_calendar_widget.py."""
import ast
from pathlib import Path

p = Path("desktop_app/dispatcher_calendar_widget.py")
src = p.read_text(encoding="utf-8")

old1 = (
    "                    WHERE charter_date >= %s AND charter_date <= %s\n"
    "                        AND (status IS NULL OR status NOT IN"
    " ('cancelled','no-show'))\n"
    '                """,'
)
new1 = (
    "                    WHERE charter_date >= %s AND charter_date <= %s\n"
    "                        AND (status IS NULL OR status NOT IN\n"
    "                            ('cancelled','no-show'))\n"
    '                """,'
)

old2 = (
    "                    WHERE charter_date BETWEEN %s AND %s\n"
    "                      AND (status IS NULL OR status NOT IN"
    " ('cancelled','no-show'))\n"
    "                    ORDER BY charter_date, pickup_time"
)
new2 = (
    "                    WHERE charter_date BETWEEN %s AND %s\n"
    "                      AND (status IS NULL OR status NOT IN\n"
    "                          ('cancelled','no-show'))\n"
    "                    ORDER BY charter_date, pickup_time"
)

src2 = src.replace(old1, new1, 1)
src3 = src2.replace(old2, new2, 1)

if src2 == src:
    print("WARN: patch1 not applied")
if src3 == src2:
    print("WARN: patch2 not applied")

p.write_text(src3, encoding="utf-8")

try:
    ast.parse(src3)
    print("AST_OK")
except SyntaxError as e:
    print(f"AST_FAIL: {e}")
