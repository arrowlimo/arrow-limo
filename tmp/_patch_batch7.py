"""Patch function_executor.py, roe_form_widget.py, and ai_functions.py residuals."""
import ast
from pathlib import Path


def ok(path, src):
    try:
        ast.parse(src)
        print(f"AST_OK  {Path(path).name}")
    except SyntaxError as e:
        print(f"AST_FAIL {Path(path).name}: {e}")


# ── function_executor.py ───────────────────────────────────────────────────
p = Path("desktop_app/function_executor.py")
src = p.read_text(encoding="utf-8")
src = src.replace(
    "                f\"WCB estimate for {payload.get('period', 'selected period')}: gross payroll \"\n",
    "                f\"WCB estimate for \"\n"
    "                f\"{payload.get('period', 'selected period')}: \"\n"
    "                f\"gross payroll \"\n",
    1,
)
src = src.replace(
    "                f\"Unpaid charters for {payload.get('period', 'selected period')}: \"\n",
    "                f\"Unpaid charters for \"\n"
    "                f\"{payload.get('period', 'selected period')}: \"\n",
    1,
)
p.write_text(src, encoding="utf-8")
ok(p, src)

# ── roe_form_widget.py ─────────────────────────────────────────────────────
p2 = Path("desktop_app/roe_form_widget.py")
src2 = p2.read_text(encoding="utf-8")

src2 = src2.replace(
    "                        SELECT employee_id, COALESCE(employee_number, ''), COALESCE(full_name, ''), COALESCE(sin, '')\n"
    "                        FROM employees\n"
    "                        WHERE employment_status IS NULL OR employment_status != 'inactive'",
    "                        SELECT employee_id,\n"
    "                               COALESCE(employee_number, ''),\n"
    "                               COALESCE(full_name, ''),\n"
    "                               COALESCE(sin, '')\n"
    "                        FROM employees\n"
    "                        WHERE employment_status IS NULL\n"
    "                           OR employment_status != 'inactive'",
    1,
)
src2 = src2.replace(
    "                        SELECT employee_id, COALESCE(employee_number, ''), COALESCE(full_name, ''), ''\n"
    "                        FROM employees\n"
    "                        WHERE employment_status IS NULL OR employment_status != 'inactive'",
    "                        SELECT employee_id,\n"
    "                               COALESCE(employee_number, ''),\n"
    "                               COALESCE(full_name, ''),\n"
    "                               ''\n"
    "                        FROM employees\n"
    "                        WHERE employment_status IS NULL\n"
    "                           OR employment_status != 'inactive'",
    1,
)
# filename lines – extract date portion
src2 = src2.replace(
    "                f\"ROE_{self.employee_name_edit.text()}_{date.today():%Y%m%d}.pd\",",
    "                \"ROE_\"\n"
    "                + self.employee_name_edit.text()\n"
    "                + f\"_{date.today():%Y%m%d}.pd\",",
    1,
)
src2 = src2.replace(
    "                f\"ROE_{self.employee_name_edit.text()}_{date.today():%Y%m%d}.csv\",",
    "                \"ROE_\"\n"
    "                + self.employee_name_edit.text()\n"
    "                + f\"_{date.today():%Y%m%d}.csv\",",
    1,
)
src2 = src2.replace(
    "                f\"ROE_{self.employee_name_edit.text()}_{date.today():%Y%m%d}.docx\",",
    "                \"ROE_\"\n"
    "                + self.employee_name_edit.text()\n"
    "                + f\"_{date.today():%Y%m%d}.docx\",",
    1,
)
# log_line split
src2 = src2.replace(
    "                log_line = f\"{date.today():%Y-%m-%d} {last_day} | emp_id={emp_id} | employee={employee} | reason={reason} | hours={hours:.2f} | earnings={earnings:.2f}\\n\"",
    "                log_line = (\n"
    "                    f\"{date.today():%Y-%m-%d} {last_day} | \"\n"
    "                    f\"emp_id={emp_id} | employee={employee} | \"\n"
    "                    f\"reason={reason} | hours={hours:.2f} | \"\n"
    "                    f\"earnings={earnings:.2f}\\n\"\n"
    "                )",
    1,
)
p2.write_text(src2, encoding="utf-8")
ok(p2, src2)

# ── ai_functions.py ────────────────────────────────────────────────────────
p3 = Path("desktop_app/ai_functions.py")
src3 = p3.read_text(encoding="utf-8")

src3 = src3.replace(
    '                "accounts": [{"account": str, "debit": Decimal, "credit": Decimal}],',
    '                "accounts": [\n'
    '                    {"account": str, "debit": Decimal, "credit": Decimal}\n'
    '                ],',
    1,
)
src3 = src3.replace(
    '                    {"receipt_id": int, "amount": Decimal, "vendor": str, "suggested_category": str}]}',
    '                    {\n'
    '                        "receipt_id": int,\n'
    '                        "amount": Decimal,\n'
    '                        "vendor": str,\n'
    '                        "suggested_category": str,\n'
    '                    }\n'
    '                ]}',
    1,
)
src3 = src3.replace(
    "                WHERE EXTRACT(YEAR FROM receipt_date) = %s\n"
    "                    AND (category IS NULL OR category = 'Uncategorized' OR category = '')",
    "                WHERE EXTRACT(YEAR FROM receipt_date) = %s\n"
    "                    AND (category IS NULL\n"
    "                         OR category = 'Uncategorized'\n"
    "                         OR category = '')",
    1,
)
src3 = src3.replace(
    "                \"error\": f\"Field '{field}' not allowed. Only: {', '.join(sorted(allowed_fields))}\",",
    "                \"error\": (\n"
    "                    f\"Field '{field}' not allowed. Only: \"\n"
    "                    + ', '.join(sorted(allowed_fields))\n"
    "                ),",
    1,
)
p3.write_text(src3, encoding="utf-8")
ok(p3, src3)
