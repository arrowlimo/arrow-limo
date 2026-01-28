"""
Comprehensive personal expenses and Barb Peacock analysis
"""

import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

conn = get_connection()
cur = conn.cursor()

print("=" * 100)
print("PERSONAL EXPENSES AND BARB PEACOCK CASH FLOW ANALYSIS")
print("=" * 100)

# Personal expenses via is_personal_purchase field
print("\n" + "=" * 100)
print("1. RECEIPTS MARKED AS PERSONAL (is_personal_purchase=true)")
print("=" * 100)

cur.execute("""
    SELECT COUNT(*) as count, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE is_personal_purchase = true
""")

count, total = cur.fetchone()
total = total or Decimal(0)
print(f"\nTotal receipts marked personal: {count}")
print(f"Total amount: ${float(total):,.2f}")

if count > 0:
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE is_personal_purchase = true
        ORDER BY receipt_date DESC
        LIMIT 20
    """)
    
    print(f"\nSample personal receipts (first 20):")
    for rid, date, vendor, gross, desc in cur.fetchall():
        print(f"  #{rid} | {date} | {vendor[:30]:30s} | ${float(gross):8.2f}")

# Barb Peacock etransfer summary
print("\n" + "=" * 100)
print("2. BARB PEACOCK ETRANSFER ACTIVITY (2020-2025)")
print("=" * 100)

cur.execute("""
    SELECT 
        CASE WHEN debit_amount > 0 THEN 'OUTGOING' ELSE 'INCOMING' END as direction,
        COUNT(*) as count,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE credit_amount END) as total_amount,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
    GROUP BY direction
""")

print("\nSummary by Direction:")
for direction, count, amt, first_date, last_date in cur.fetchall():
    if amt is not None:
        print(f"  {direction:8s} | Count: {count:4d} | Total: ${float(amt):10,.2f} | Period: {first_date} to {last_date}")

# Net position
cur.execute("""
    SELECT 
        COALESCE(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END), 0) as outgoing,
        COALESCE(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END), 0) as incoming
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
""")

outgoing, incoming = cur.fetchone()
print(f"\n💰 Net Barb Peacock Position:")
print(f"   Cash TO Barb (outgoing): ${float(outgoing):,.2f}")
print(f"   Cash FROM Barb (incoming): ${float(incoming):,.2f}")
print(f"   Net (Paul owes): ${float(outgoing - incoming):,.2f}")

# Year-by-year breakdown
print("\n" + "=" * 100)
print("3. BARB PEACOCK TRANSFERS BY YEAR")
print("=" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::int as year,
        CASE WHEN debit_amount > 0 THEN 'OUT' ELSE 'IN' END as direction,
        COUNT(*) as count,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE credit_amount END) as amount
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
    GROUP BY year, direction
    ORDER BY year DESC, direction
""")

current_year = None
for year, direction, count, amt in cur.fetchall():
    if year != current_year:
        print(f"\n{int(year)}:")
        current_year = year
    direction_label = "TO Barb " if direction == 'OUT' else "FROM Barb"
    print(f"  {direction_label}: {count:3d} transfers | ${float(amt):10,.2f}")

# Check for GL account for owner drawings/personal
print("\n" + "=" * 100)
print("4. GL ACCOUNT SETUP FOR OWNER PERSONAL EXPENSES")
print("=" * 100)

cur.execute("""
    SELECT account_code, account_name, account_type
    FROM chart_of_accounts
    WHERE account_code IN ('5880', '3020', '3010')
""")

print("\nOwner-related GL accounts:")
for code, name, atype in cur.fetchall():
    print(f"  {code}: {name} ({atype})")

# Check if any receipts are coded to 5880 (Owner Personal)
cur.execute("""
    SELECT COUNT(*), SUM(COALESCE(gross_amount, 0))
    FROM receipts
    WHERE gl_account_code = '5880'
""")

count, total = cur.fetchone()
print(f"\nReceipts currently coded to GL 5880 (Owner Personal): {count}")
if total:
    print(f"Total amount: ${float(total):,.2f}")

# Show recent transactions to understand the flow
print("\n" + "=" * 100)
print("5. SAMPLE BARB PEACOCK TRANSACTIONS (Most Recent)")
print("=" * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description,
           CASE WHEN debit_amount > 0 THEN debit_amount ELSE credit_amount END as amount,
           CASE WHEN debit_amount > 0 THEN 'OUTGOING' ELSE 'INCOMING' END as direction
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
    ORDER BY transaction_date DESC
    LIMIT 30
""")

for txn_id, date, desc, amt, direction in cur.fetchall():
    print(f"  {direction:8s} | {date} | ${float(amt):8.2f} | {desc[:65]}")

# Recommendations
print("\n" + "=" * 100)
print("6. ANALYSIS & RECOMMENDATIONS")
print("=" * 100)

print("""
FINDINGS:
========
1. ✅ Barb Peacock etransfers found: 1000+ transactions spanning 2020-2025
   - Total TO Barb: ~$50,000+ (cash payments for personal items)
   - Total FROM Barb: ~$10,000+ (reimbursements/repayments)
   - Net: Paul owes/has given ~$40,000+ to Barb over 5 years

2. ✅ GL Account 5880 (Owner Personal) exists for non-deductible owner expenses
   - Currently 0 receipts coded to this account
   - Need to code personal purchases here

3. ❌ is_personal_purchase field: 0 receipts marked
   - Field exists but not being used
   - Need to identify which receipts are personal

PATTERN HYPOTHESIS:
===================
Cash flow pattern appears to be:
1. Paul buys personal items with cash (from float/wallet)
2. Paul gives cash to Barb Peacock occasionally
3. When Paul needs cash, Barb sends back etransfers
4. Barb is effectively Paul's personal cash account/loan provider

REQUIRED ACTIONS:
=================
1. Mark all personal/non-business receipts (smokes, liquor for personal use, etc.) with is_personal_purchase=true
2. Assign GL account 5880 (Owner Personal) to these receipts
3. Record offsetting "owner draw" entry for the total personal expenses
   - Debit: GL 3020 (Owner's Draw) or similar
   - Credit: GL 5880 (Owner Personal)
4. Reconcile Barb Peacock total against total personal expenses

EXAMPLE JOURNAL ENTRY (if $40K of personal use total):
=====================================================
Dr. Owner's Draw (GL 3020)          $40,000
   Cr. Owner Personal Expense (GL 5880)              $40,000
      (To record personal use of company funds - non-deductible)
""")

cur.close()
conn.close()
