#!/usr/bin/env python3
import psycopg2, os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
count, total = cur.fetchone()

print(f"Database: {count} invoices = ${total:,.2f}")
print("Excel:    13 invoices = $4,593.00")

diff_count = count - 13
diff_amt = Decimal(str(total)) - Decimal("4593.00")
print(f"Difference: {diff_count:+d} invoices, ${diff_amt:+,.2f}")

if count == 13 and abs(diff_amt) < Decimal("0.01"):
    print("\n🎉 DATABASE MATCHES EXCEL!")

conn.close()
