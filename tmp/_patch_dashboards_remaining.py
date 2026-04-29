"""Fix remaining stubborn E501 lines in dashboards_phase2_phase3 and phase11."""
import ast
from pathlib import Path

# === dashboards_phase2_phase3.py ===
p = Path("desktop_app/dashboards_phase2_phase3.py")
src = p.read_text(encoding="utf-8")

for kw, col in [("fuel", "fuel_cost"), ("maint", "maint_cost"), ("insur", "insur_cost")]:
    src = src.replace(
        f"                               WHEN r.description ILIKE '%{kw}%'\n"
        f"                               THEN r.gross_amount ELSE 0 END), 0) as {col},",
        f"                               WHEN r.description ILIKE '%{kw}%'\n"
        f"                               THEN r.gross_amount\n"
        f"                               ELSE 0 END), 0) as {col},",
        1,
    )

src = src.replace(
    "                           SUM(CASE WHEN status = 'completed'\n"
    "                               THEN total_amount_due ELSE 0 END) as completed_revenue",
    "                           SUM(CASE WHEN status = 'completed'\n"
    "                               THEN total_amount_due\n"
    "                               ELSE 0 END) as completed_revenue",
    1,
)

p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  dashboards_phase2_phase3.py")
except SyntaxError as e:
    print(f"AST_FAIL dashboards_phase2_phase3.py: {e}")

# === dashboards_phase11.py ===
p2 = Path("desktop_app/dashboards_phase11.py")
src2 = p2.read_text(encoding="utf-8")

src2 = src2.replace(
    "                        COALESCE(SUBSTRING(charter_date::text, 1, 10), 'Local'),",
    "                        COALESCE(\n"
    "                            SUBSTRING(charter_date::text, 1, 10),\n"
    "                            'Local'\n"
    "                        ),",
    1,
)

p2.write_text(src2, encoding="utf-8")
try:
    ast.parse(src2)
    print("AST_OK  dashboards_phase11.py")
except SyntaxError as e:
    print(f"AST_FAIL dashboards_phase11.py: {e}")
