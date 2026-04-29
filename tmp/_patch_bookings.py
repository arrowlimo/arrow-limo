"""Patch 6 remaining E501 SQL lines in bookings.py."""
import ast
from pathlib import Path

p = Path("modern_backend/app/routers/bookings.py")
src = p.read_text(encoding="utf-8")

fixes = [
    (
        "            CASE WHEN c.status = 'cancelled' THEN true ELSE false END AS cancelled,",
        "            CASE WHEN c.status = 'cancelled'\n                THEN true ELSE false END AS cancelled,",
    ),
    (
        "                WHEN c.locked = TRUE AND c.status != 'cancelled' THEN 'Reconciled'",
        "                WHEN c.locked = TRUE AND c.status != 'cancelled'\n                    THEN 'Reconciled'",
    ),
    (
        "                WHEN c.locked = FALSE AND c.status != 'cancelled' THEN 'Not Reconciled'",
        "                WHEN c.locked = FALSE AND c.status != 'cancelled'\n                    THEN 'Not Reconciled'",
    ),
    (
        "                  AND bo.order_date < date_trunc('week', CURRENT_DATE) + interval '7 days') AS beverage_orders_this_week",
        "                  AND bo.order_date < date_trunc('week', CURRENT_DATE)\n                      + interval '7 days') AS beverage_orders_this_week",
    ),
    (
        "                payment_label IN ('NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')",
        "                payment_label IN (\n                    'NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')",
    ),
    (
        "            AND payment_label NOT IN ('Deposit', 'Security Deposit', 'Damage Deposit')",
        "            AND payment_label NOT IN (\n                'Deposit', 'Security Deposit', 'Damage Deposit')",
    ),
]

for old, new in fixes:
    if old not in src:
        print(f"WARN: not found: {old[:60]!r}")
    src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")

try:
    ast.parse(src)
    print("AST_OK")
except SyntaxError as e:
    print(f"AST_FAIL: {e}")
