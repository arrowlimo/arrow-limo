"""Patch 19 remaining E501 SQL lines in dashboards_phase4_5_6.py."""
import ast
from pathlib import Path

p = Path("desktop_app/dashboards_phase4_5_6.py")
src = p.read_text(encoding="utf-8")

fixes = [
    # Lines 111-114: COALESCE(SUM(CASE WHEN r.category = '...' ...
    (
        "                        COALESCE(SUM(CASE WHEN r.category = 'Loan Payment' THEN r.gross_amount ELSE 0 END), 0) as loan_pmts,",
        "                        COALESCE(SUM(CASE WHEN r.category = 'Loan Payment'\n                            THEN r.gross_amount ELSE 0 END), 0) as loan_pmts,",
    ),
    (
        "                        COALESCE(SUM(CASE WHEN r.category = 'Insurance' THEN r.gross_amount ELSE 0 END), 0) as insurance,",
        "                        COALESCE(SUM(CASE WHEN r.category = 'Insurance'\n                            THEN r.gross_amount ELSE 0 END), 0) as insurance,",
    ),
    (
        "                        COALESCE(SUM(CASE WHEN r.category = 'Maintenance' THEN r.gross_amount ELSE 0 END), 0) as maintenance,",
        "                        COALESCE(SUM(CASE WHEN r.category = 'Maintenance'\n                            THEN r.gross_amount ELSE 0 END), 0) as maintenance,",
    ),
    (
        "                        COALESCE(SUM(CASE WHEN r.category = 'Fuel' THEN r.gross_amount ELSE 0 END), 0) as fuel,",
        "                        COALESCE(SUM(CASE WHEN r.category = 'Fuel'\n                            THEN r.gross_amount ELSE 0 END), 0) as fuel,",
    ),
    # Lines 258-259
    (
        "                            WHEN ms.next_service_date < CURRENT_DATE THEN 'Overdue'",
        "                            WHEN ms.next_service_date < CURRENT_DATE\n                                THEN 'Overdue'",
    ),
    (
        "                            WHEN ms.next_service_date < CURRENT_DATE + INTERVAL '7 days' THEN 'Due Soon'",
        "                            WHEN ms.next_service_date\n                                < CURRENT_DATE + INTERVAL '7 days'\n                                THEN 'Due Soon'",
    ),
    # Line 383
    (
        "                    LEFT JOIN receipts r ON r.vehicle_id = v.vehicle_id AND r.category = 'Fuel'",
        "                    LEFT JOIN receipts r\n                        ON r.vehicle_id = v.vehicle_id AND r.category = 'Fuel'",
    ),
    # Line 746
    (
        "                    WHERE e.is_chauffeur = true AND e.employment_status = 'active'\n                    GROUP BY e.employee_id, e.full_name\n                    ORDER BY e.full_name",
        "                    WHERE e.is_chauffeur = true\n                        AND e.employment_status = 'active'\n                    GROUP BY e.employee_id, e.full_name\n                    ORDER BY e.full_name",
    ),
    # Line 852
    (
        "                    WHERE e.is_chauffeur = true AND e.employment_status = 'active'\n                    GROUP BY e.employee_id, e.full_name\n                    ORDER BY AVG(c.client_rating) DESC NULLS LAST",
        "                    WHERE e.is_chauffeur = true\n                        AND e.employment_status = 'active'\n                    GROUP BY e.employee_id, e.full_name\n                    ORDER BY AVG(c.client_rating) DESC NULLS LAST",
    ),
    # Lines 1090, 1092
    (
        "                        CASE WHEN {active_expr} THEN 'Active' ELSE 'Inactive' END as status,",
        "                        CASE WHEN {active_expr}\n                            THEN 'Active' ELSE 'Inactive' END as status,",
    ),
    (
        "                        CASE WHEN {active_expr} THEN 'Yes' ELSE 'No' END as available",
        "                        CASE WHEN {active_expr}\n                            THEN 'Yes' ELSE 'No' END as available",
    ),
    # Line 1203
    (
        "                        COALESCE(p.payment_method, 'Pending') as payment_method,",
        "                        COALESCE(p.payment_method,\n                            'Pending') as payment_method,",
    ),
    # Lines 1335-1337
    (
        "                            WHEN (CURRENT_DATE - c.charter_date) <= 30 THEN 'Current'",
        "                            WHEN (CURRENT_DATE - c.charter_date)\n                                <= 30 THEN 'Current'",
    ),
    (
        "                            WHEN (CURRENT_DATE - c.charter_date) <= 60 THEN '31-60 Days'",
        "                            WHEN (CURRENT_DATE - c.charter_date)\n                                <= 60 THEN '31-60 Days'",
    ),
    (
        "                            WHEN (CURRENT_DATE - c.charter_date) <= 90 THEN '61-90 Days'",
        "                            WHEN (CURRENT_DATE - c.charter_date)\n                                <= 90 THEN '61-90 Days'",
    ),
    # Lines 1527-1529
    (
        "                        COALESCE(SUM(CASE WHEN category = 'Fuel' THEN gross_amount ELSE 0 END), 0) as fuel,",
        "                        COALESCE(SUM(CASE WHEN category = 'Fuel'\n                            THEN gross_amount ELSE 0 END), 0) as fuel,",
    ),
    (
        "                        COALESCE(SUM(CASE WHEN category = 'Maintenance' THEN gross_amount ELSE 0 END), 0) as maintenance,",
        "                        COALESCE(SUM(CASE WHEN category = 'Maintenance'\n                            THEN gross_amount ELSE 0 END), 0) as maintenance,",
    ),
    (
        "                        COALESCE(SUM(CASE WHEN category = 'Insurance' THEN gross_amount ELSE 0 END), 0) as insurance",
        "                        COALESCE(SUM(CASE WHEN category = 'Insurance'\n                            THEN gross_amount ELSE 0 END), 0) as insurance",
    ),
    # Line 1655
    (
        "                        SUM(CASE WHEN c.status = 'Cancelled' THEN 1 ELSE 0 END) as cancellations",
        "                        SUM(CASE WHEN c.status = 'Cancelled'\n                            THEN 1 ELSE 0 END) as cancellations",
    ),
]

for old, new in fixes:
    if old not in src:
        print(f"WARN not found: {old[:70]!r}")
    src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")

try:
    ast.parse(src)
    print("AST_OK")
except SyntaxError as e:
    print(f"AST_FAIL: {e}")
