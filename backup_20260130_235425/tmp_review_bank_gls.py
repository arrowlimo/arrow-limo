#!/usr/bin/env python3
"""Review GL codes for potential consolidation."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost')
cur = conn.cursor()

# Find bank/fee related GL codes
cur.execute("""
    SELECT account_code, account_name
    FROM chart_of_accounts
    WHERE account_code IN ('5410', '5650', '6100', '6101', '5450', '1135', '1099')
    ORDER BY account_code
""")

print("Current Banking/Fee GL Codes:")
print("=" * 60)
codes = cur.fetchall()
for code, name in codes:
    # Count receipts using each
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(gross_amount) as total
        FROM receipts
        WHERE gl_account_code = %s
    """, (code,))
    cnt, total = cur.fetchone()
    total = total or 0.0
    print(f"{code:6} | {name:40} | {cnt:6,} receipts | ${total:12,.2f}")

conn.close()
