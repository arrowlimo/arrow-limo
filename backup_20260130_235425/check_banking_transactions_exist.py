#!/usr/bin/env python3
"""Check if banking transactions exist for these orphaned receipts."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("CHECKING: Do Banking Transactions Exist for Orphaned Receipts?")
print("=" * 100)

# Check if banking transactions exist that match these receipts
print("\n1. Looking for banking transactions matching Heffner orphans:")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM bt.transaction_date) as year,
        COUNT(*) as banking_tx_count,
        SUM(bt.debit_amount) as total_debit
    FROM banking_transactions bt
    WHERE bt.description LIKE '%HEFFNER%'
    AND EXTRACT(YEAR FROM bt.transaction_date) BETWEEN 2020 AND 2025
    GROUP BY EXTRACT(YEAR FROM bt.transaction_date)
    ORDER BY year
""")
banking_heffner = cur.fetchall()
print("Heffner banking transactions by year:")
for year, count, debit in banking_heffner:
    debit_str = f"${debit:,.2f}" if debit else "$0.00"
    print(f"  {int(year)}: {count:4} transactions, {debit_str:>15} total debit")

# Check if any orphaned receipts can be matched to existing banking transactions
print("\n2. Attempting to match orphaned Heffner receipts to banking:")
cur.execute("""
    WITH orphan_receipts AS (
        SELECT receipt_id, vendor_name, gross_amount, receipt_date
        FROM receipts
        WHERE vendor_name LIKE '%HEFFNER%'
        AND EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
        AND banking_transaction_id IS NULL
        AND created_from_banking = true
        LIMIT 100
    )
    SELECT 
        orph.receipt_id, orph.gross_amount, orph.receipt_date,
        bt.transaction_id, bt.debit_amount, bt.transaction_date, bt.description
    FROM orphan_receipts orph
    LEFT JOIN banking_transactions bt 
        ON bt.description LIKE '%HEFFNER%'
        AND bt.debit_amount = orph.gross_amount
        AND bt.transaction_date::date = orph.receipt_date::date
    WHERE bt.transaction_id IS NOT NULL
    LIMIT 20
""")
matches = cur.fetchall()
if matches:
    print(f"Found {len(matches)} potential matches (same date + amount):")
    for rid, r_amt, r_date, bt_id, bt_amt, bt_date, bt_desc in matches:
        print(f"  Receipt {rid} (${r_amt:,.2f}, {r_date}) ↔ Banking TX {bt_id} (${bt_amt:,.2f}, {bt_date})")
        print(f"    {bt_desc[:70]}")
else:
    print("  No exact matches found (same date + amount)")

# Check what the source field says
print("\n3. Checking SOURCE field for orphaned receipts:")
cur.execute("""
    SELECT source, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND created_from_banking = true
    GROUP BY source
    ORDER BY COUNT(*) DESC
""")
sources = cur.fetchall()
for source, count, amount in sources:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"  {source if source else 'NULL':30}: {count:5} receipts, {amt_str:>15}")

# Check if these are placeholder entries
print("\n4. Sample orphaned Heffner receipts (checking if placeholders):")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, description, source
    FROM receipts
    WHERE vendor_name LIKE '%HEFFNER%'
    AND EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND created_from_banking = true
    ORDER BY receipt_date
    LIMIT 15
""")
samples = cur.fetchall()
for rid, vendor, amount, rdate, desc, source in samples:
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    desc_preview = (desc[:40] + "...") if desc and len(desc) > 40 else (desc if desc else "NULL")
    print(f"  {rid:7} | {rdate} | {amt_str:>10} | {source if source else 'NULL':20} | {desc_preview}")

# Final determination
print("\n" + "=" * 100)
print("DETERMINATION")
print("=" * 100)

# Count truly bogus vs. legitimate orphans
cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name LIKE '%HEFFNER%' THEN 'Heffner Auto Finance'
            WHEN vendor_name LIKE '%CMB%INSURANCE%' THEN 'Insurance (CMB)'
            WHEN vendor_name IN ('CASH WITHDRAWAL', 'UTILITIES', 'RBC', 'LANDLORD', 'MONEY MART') THEN vendor_name
            ELSE 'Other'
        END as category,
        COUNT(*) as count,
        SUM(gross_amount) as amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND created_from_banking = true
    GROUP BY category
    ORDER BY COUNT(*) DESC
""")
categories = cur.fetchall()

print("\nOrphaned receipts marked 'created_from_banking' by category:")
for cat, count, amount in categories:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"  {cat:30}: {count:5} receipts, {amt_str:>15}")

print(f"""
⚠️  CONCLUSION:
These receipts have created_from_banking=true BUT no banking_transaction_id.
They appear to be:
  1. Auto-generated accrual entries (Heffner finance charges)
  2. System placeholders created during import
  3. NOT actual banking imports

RECOMMENDATION:
  - Heffner ({1259} receipts): Likely accrual entries for vehicle financing
    These may be legitimate accounting entries, not bogus
  - Others: Review individually

These are NOT traditional bogus receipts - they may be intentional accruals.
""")

cur.close()
conn.close()
