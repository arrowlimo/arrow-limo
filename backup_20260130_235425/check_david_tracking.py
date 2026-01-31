#!/usr/bin/env python3
"""Check what tables track David Richard's personal transactions."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("="*80)
print("OWNER/SHAREHOLDER TRACKING TABLES")
print("="*80)

# Check owner_equity_accounts
try:
    cur.execute("SELECT COUNT(*) FROM owner_equity_accounts")
    count = cur.fetchone()[0]
    cur.execute("SELECT owner_name, account_type, current_balance, ytd_business_expenses FROM owner_equity_accounts")
    rows = cur.fetchall()
    print(f"\nowner_equity_accounts: {count} rows")
    for r in rows:
        print(f"  {r[0]:40} | {r[1]:20} | Balance: ${r[2]:,.2f} | YTD Biz: ${r[3]:,.2f}")
except Exception as e:
    print(f"\nowner_equity_accounts: {e}")

# Check receipts paid by David (not reimbursed)
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name ILIKE '%david%richard%'
       OR description ILIKE '%david%richard%'
""")
david_receipts = cur.fetchone()
print(f"\nReceipts mentioning David Richard: {david_receipts[0]} (${david_receipts[1] or 0:,.2f})")

# Check if there's a shareholder loan tracking
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
      AND (table_name ILIKE '%shareholder%' 
           OR table_name ILIKE '%owner%' 
           OR table_name ILIKE '%david%')
    ORDER BY table_name
""")
related_tables = cur.fetchall()
print(f"\nRelated tables:")
for t in related_tables:
    print(f"  - {t[0]}")

# Check credit_lines usage
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    WHERE r.payment_method ILIKE '%credit%line%'
       OR r.source_reference IN (SELECT account_id FROM credit_lines)
""")
credit_line_usage = cur.fetchone()[0]
print(f"\nReceipts linked to credit_lines: {credit_line_usage}")

cur.close()
conn.close()
