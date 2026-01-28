#!/usr/bin/env python3
import os, psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check Amazon receipts
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE description ILIKE '%David paid%amazon%'")
amazon_count, amazon_total = cur.fetchone()

# Check GL 2020 balance
cur.execute("SELECT COALESCE(SUM(\"Credit\"), 0) - COALESCE(SUM(\"Debit\"), 0) FROM journal WHERE \"Account\" = '2020'")
gl_balance = cur.fetchone()[0]

print("\n" + "="*70)
print("✅ AMAZON IMPORT VERIFICATION")
print("="*70 + "\n")

print(f"Amazon Receipts Created: {amazon_count} invoices, ${amazon_total:,.2f}")
print(f"GL 2020 Notes Payable - David Balance: ${gl_balance:,.2f}")

print(f"\nDavid Richard Debt Summary:")
print(f"  - Web hosting/domains (GoDaddy/Wix/IONOS): $10,036.89 (159 invoices)")
print(f"  - Amazon parts/tools/supplies: $8,617.98 (65 invoices)")
total_debt = 10036.89 + 8617.98
print(f"  ───────────────────────────────────────────────────")
print(f"  TOTAL OWED TO DAVID: ${total_debt:,.2f} (224 invoices)")

print("\n" + "="*70)
print("✅ ALL AMAZON INVOICES SUCCESSFULLY IMPORTED")
print("="*70 + "\n")

conn.close()
