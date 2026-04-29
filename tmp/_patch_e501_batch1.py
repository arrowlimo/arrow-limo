"""Patch 12 remaining E501 lines across 3 files."""
import ast
from pathlib import Path

patches = {
    "modern_backend/app/tax/t2_data_extraction.py": [
        (
            "            f\"  Other Income:           ${sum(i['amount'] for i in package['revenue']['other_income']):>15,.2f}\"",
            "            f\"  Other Income:           $\"\n"
            "            f\"{sum(i['amount'] for i in package['revenue']['other_income']):>15,.2f}\"",
        ),
        (
            "            f\"${package['balance_sheet']['assets']['accounts_receivable']:>15,.2f}\"",
            "            f\"${package['balance_sheet']['assets']\n"
            "             ['accounts_receivable']:>15,.2f}\"",
        ),
        (
            "            f\"${package['balance_sheet']['liabilities']['accounts_payable']:>15,.2f}\"",
            "            f\"${package['balance_sheet']['liabilities']\n"
            "             ['accounts_payable']:>15,.2f}\"",
        ),
        (
            "            f\"${package['balance_sheet']['equity']['retained_earnings']:>15,.2f}\"",
            "            f\"${package['balance_sheet']['equity']\n"
            "             ['retained_earnings']:>15,.2f}\"",
        ),
    ],
    "desktop_app/employee_management_widget.py": [
        (
            "                      AND pp.period_start_date >= CURRENT_DATE - INTERVAL '7 days'",
            "                      AND pp.period_start_date\n"
            "                          >= CURRENT_DATE - INTERVAL '7 days'",
        ),
        (
            "                           pp.period_start_date || ' to ' || pp.period_end_date as period,",
            "                           pp.period_start_date || ' to '\n"
            "                               || pp.period_end_date as period,",
        ),
        (
            "                           epm.gross_pay, epm.total_deductions, epm.net_pay, 'paid' as status",
            "                           epm.gross_pay, epm.total_deductions,\n"
            "                           epm.net_pay, 'paid' as status",
        ),
        (
            "                        OR LOWER(TRIM(REGEXP_REPLACE(COALESCE(full_name, ''), '\\\\s+', ' ', 'g')))",
            "                        OR LOWER(TRIM(REGEXP_REPLACE(\n"
            "                            COALESCE(full_name, ''), '\\\\s+', ' ', 'g')))",
        ),
        (
            "                           = LOWER(TRIM(REGEXP_REPLACE(COALESCE(%s, ''), '\\\\s+', ' ', 'g')))",
            "                           = LOWER(TRIM(REGEXP_REPLACE(\n"
            "                               COALESCE(%s, ''), '\\\\s+', ' ', 'g')))",
        ),
        (
            "                    WHERE is_chauffeur = TRUE AND employment_status <> 'inactive'",
            "                    WHERE is_chauffeur = TRUE\n"
            "                        AND employment_status <> 'inactive'",
        ),
        (
            "                sql = f\"UPDATE employees SET employment_status='active' WHERE employee_id IN ({placeholders})\"",
            "                sql = (\n"
            "                    \"UPDATE employees SET employment_status='active'\"\n"
            "                    f\" WHERE employee_id IN ({placeholders})\"\n"
            "                )",
        ),
    ],
    "modern_backend/app/routers/t2_returns.py": [
        (
            "            SET status = CASE WHEN status = 'filed' THEN 'amended' ELSE status END,",
            "            SET status = CASE WHEN status = 'filed'\n"
            "                THEN 'amended' ELSE status END,",
        ),
    ],
}

for path, fixes in patches.items():
    p = Path(path)
    src = p.read_text(encoding="utf-8")
    for old, new in fixes:
        if old not in src:
            print(f"WARN not found in {path}: {old[:60]!r}")
        src = src.replace(old, new, 1)
    p.write_text(src, encoding="utf-8")
    try:
        ast.parse(src)
        print(f"AST_OK  {path}")
    except SyntaxError as e:
        print(f"AST_FAIL {path}: {e}")
