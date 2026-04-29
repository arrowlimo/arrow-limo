import ast
from pathlib import Path

p = Path("desktop_app/dashboards.py")
src = p.read_text(encoding="utf-8")

src = src.replace(
    "                    WHERE e.is_chauffeur = true AND e.employment_status = 'active'",
    "                    WHERE e.is_chauffeur = true\n"
    "                      AND e.employment_status = 'active'",
    1,
)
src = src.replace(
    "                        CASE WHEN c.balance > 0 THEN 'Outstanding' ELSE 'Paid' END as status",
    "                        CASE WHEN c.balance > 0\n"
    "                            THEN 'Outstanding'\n"
    "                            ELSE 'Paid'\n"
    "                        END as status",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK")
except SyntaxError as e:
    print(f"AST_FAIL: {e}")
