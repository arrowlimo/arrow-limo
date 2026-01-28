#!/usr/bin/env python3
"""Check RBC receipts - are they David's paid purchases?"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("RBC ORPHAN RECEIPTS ANALYSIS")
print("=" * 100)

# Get all RBC orphan receipts
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, description, 
           gl_account_code, created_from_banking
    FROM receipts
    WHERE vendor_name = 'RBC'
    AND EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    ORDER BY receipt_date, receipt_id
""")
rbc_receipts = cur.fetchall()

print(f"\nFound {len(rbc_receipts)} RBC orphan receipts:")
print(f"\n{'Receipt ID':>10} {'Date':<12} {'Amount':>10} {'GL Code':<8} {'From Banking':<12} {'Description'}")
print("-" * 100)

total = 0
for rid, vendor, amount, rdate, desc, gl_code, from_banking in rbc_receipts:
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    desc_preview = (desc[:50] + "...") if desc and len(desc) > 50 else (desc if desc else "NULL")
    from_bank = "YES" if from_banking else "NO"
    print(f"{rid:>10} {str(rdate):<12} {amt_str:>10} {gl_code if gl_code else 'NULL':<8} {from_bank:<12} {desc_preview}")
    total += amount if amount else 0

print(f"\nTotal RBC orphan amount: ${total:,.2f}")

# Check if there are ANY RBC receipts with banking links
print("\n" + "=" * 100)
print("RBC RECEIPTS WITH BANKING LINKS (for comparison)")
print("=" * 100)

cur.execute("""
    SELECT r.receipt_id, r.gross_amount, r.receipt_date, r.description,
           bt.description as banking_desc, bt.debit_amount, bt.credit_amount
    FROM receipts r
    JOIN banking_transactions bt ON bt.receipt_id = r.receipt_id
    WHERE r.vendor_name = 'RBC'
    AND EXTRACT(YEAR FROM r.receipt_date) BETWEEN 2020 AND 2025
    ORDER BY r.receipt_date
    LIMIT 20
""")
rbc_linked = cur.fetchall()

if rbc_linked:
    print(f"\nFound {len(rbc_linked)} RBC receipts WITH banking links:")
    for rid, r_amt, r_date, r_desc, bt_desc, bt_debit, bt_credit in rbc_linked:
        amt_str = f"${r_amt:,.2f}" if r_amt else "NULL"
        print(f"  Receipt {rid} ({amt_str}, {r_date})")
        print(f"    Banking: {bt_desc[:70]}")
else:
    print("  No RBC receipts with banking links found")

# Check for RBC banking transactions
print("\n" + "=" * 100)
print("RBC BANKING TRANSACTIONS (2025)")
print("=" * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, receipt_id
    FROM banking_transactions
    WHERE description LIKE '%RBC%'
    AND EXTRACT(YEAR FROM transaction_date) = 2025
    ORDER BY transaction_date
    LIMIT 20
""")
rbc_banking = cur.fetchall()

if rbc_banking:
    print(f"\nFound {len(rbc_banking)} RBC banking transactions:")
    for tx_id, tx_date, desc, debit, credit, receipt_id in rbc_banking:
        debit_str = f"${debit:,.2f}" if debit else "None"
        credit_str = f"${credit:,.2f}" if credit else "None"
        receipt_link = f"Receipt {receipt_id}" if receipt_id else "NO RECEIPT"
        print(f"  TX {tx_id} | {tx_date} | Debit: {debit_str:>10} Credit: {credit_str:>10} | {receipt_link}")
        print(f"    {desc[:70]}")
else:
    print("  No RBC banking transactions found in 2025")

# Check for 'DAVID' or owner-related payments
print("\n" + "=" * 100)
print("CHECKING: Are these David's personal purchases?")
print("=" * 100)

# Look at the GL codes
cur.execute("""
    SELECT gl_account_code, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'RBC'
    AND banking_transaction_id IS NULL
    GROUP BY gl_account_code
""")
gl_breakdown = cur.fetchall()

print("\nRBC orphan receipts by GL code:")
for gl, count, amount in gl_breakdown:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    gl_display = gl if gl else "NULL"
    print(f"  GL {gl_display:6}: {count:2} receipts, {amt_str:>10}")

# Determine if these are personal (GL 9999) or business
print("\n" + "=" * 100)
print("DETERMINATION")
print("=" * 100)

personal_count = sum(1 for gl, _, _ in gl_breakdown if gl == '9999')
business_count = len(rbc_receipts) - personal_count

if personal_count > 0:
    print(f"✅ YES - {personal_count} RBC receipts are GL 9999 (Personal/David purchases)")
    print(f"   These appear to be David's paid purchases")
    print(f"   KEEP these receipts (legitimate personal expenses)")
else:
    print(f"   No GL 9999 receipts found")

if business_count > 0:
    print(f"\n⚠️  {business_count} RBC receipts have business GL codes")
    print(f"   These should have banking links if they're legitimate")
    print(f"   REVIEW: May be import errors or manual entries")

print(f"""
RECOMMENDATION:
- If GL 9999 (Personal): KEEP (David's purchases, legitimate)
- If other GL codes without banking: VERIFY individually or DELETE
""")

cur.close()
conn.close()
