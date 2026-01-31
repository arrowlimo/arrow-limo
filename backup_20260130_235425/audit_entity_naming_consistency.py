#!/usr/bin/env python3
"""Audit naming consistency for owners and related parties."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("="*80)
print("ENTITY NAMING CONSISTENCY AUDIT")
print("="*80)

# Owner equity accounts
cur.execute("SELECT owner_name, account_type, current_balance FROM owner_equity_accounts ORDER BY owner_name, account_type")
rows = cur.fetchall()
print("\nowner_equity_accounts:")
for r in rows:
    print(f"  {r[0]:20} | {r[1]:20} | ${r[2]:,.2f}")

# Presence of specific tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name IN (
        'david_account_tracking', 'david_richard_vehicle_loans',
        'owner_expense_transactions', 'credit_lines'
    )
    ORDER BY table_name
""")
print("\nKey tables present:")
for (t,) in cur.fetchall():
    print(f"  - {t}")

# Receipt/vendor mentions
def count_like(sql, param):
    cur.execute(sql, (param,))
    c = cur.fetchone()[0]
    return c

print("\nReceipts/vendor mentions:")
sql_vendor = "SELECT COUNT(*) FROM receipts WHERE vendor_name ILIKE %s"
sql_desc = "SELECT COUNT(*) FROM receipts WHERE description ILIKE %s"
for name in ["%Paul Richard%", "%Paul Heffner%", "%David Richard%", "%Will Heffner%", "%Heffner Auto Sales%", "%Heffner%"]:
    v = count_like(sql_vendor, name)
    d = count_like(sql_desc, name)
    print(f"  {name.strip('%'):20}: vendor={v:,} desc={d:,}")

# Linkage between credit_lines and receipts (expected: none)
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN credit_lines cl ON cl.account_id = r.source_reference
""")
linked = cur.fetchone()[0]
print(f"\nReceipts linked to credit_lines via source_reference: {linked}")

cur.close()
conn.close()
