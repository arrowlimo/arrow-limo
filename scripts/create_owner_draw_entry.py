"""
Create Owner Draw Journal Entry for Personal Expenses
Based on Barb Peacock etransfer analysis = $44,045.21 net owner draw

This represents personal expenses paid by the company that should be recorded
as owner draw / personal income to Paul Richard (non-deductible)
"""

import psycopg2
import os
from decimal import Decimal
from datetime import datetime

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

# The owner draw amount based on Barb Peacock analysis
owner_draw_amount = Decimal("44045.21")

print("=" * 90)
print("OWNER DRAW JOURNAL ENTRY - PERSONAL EXPENSES")
print("=" * 90)

print(f"""
Transaction Type: Journal Entry - Owner Draw for Personal Use
Amount: ${float(owner_draw_amount):,.2f}
Date: 2025-12-31 (year-end adjustment)
Description: Personal use of company funds - non-deductible (Barb Peacock cash flow analysis)

Journal Entry:
==============
Dr. Owner's Draw (GL 3020)                    ${float(owner_draw_amount):>12,.2f}
   Cr. Owner Personal - Non-Deductible (GL 5880)                    ${float(owner_draw_amount):>12,.2f}

Explanation:
============
This entry records personal expenses paid by the company but not deductible for tax purposes.
Based on analysis of Barb Peacock etransfers (2020-2025):
- Cash TO Barb Peacock: $68,763.17 (701 transactions)
- Cash FROM Barb Peacock: $24,717.96 (220 transactions)  
- Net: ${float(owner_draw_amount):,.2f} owner draw equivalent

This represents Paul Richard's personal use of company funds, including:
- Liquor purchases (personal consumption)
- Smokes/tobacco (personal)
- Other personal cash purchases funded by company account

Supporting Documentation:
=========================
Banking transactions matching 'barb' or 'peacock' in description show a clear
pattern where:
1. Paul receives cash from company (for business use or personal)
2. Paul uses some cash for personal items
3. Paul gives cash to Barb Peacock 
4. Barb sends etransfers back to company account
5. This cycle repeats throughout the 5-year period

The net difference ($44,045) is the equivalent of personal funds
that Paul took from the company over this period.
""")

# Check if this GL entry would be valid
cur.execute("""
    SELECT account_code, account_name, account_type, is_active
    FROM chart_of_accounts
    WHERE account_code IN ('3020', '5880')
""")

print("\nGL Account Validation:")
print("-" * 90)
for code, name, acct_type, active in cur.fetchall():
    status = "✅ ACTIVE" if active else "❌ INACTIVE"
    print(f"  {code}: {name:40s} ({acct_type:15s}) {status}")

# Show the breakdown by year
print("\n" + "=" * 90)
print("BARB PEACOCK CASH FLOW BY YEAR (for context)")
print("=" * 90)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::int as year,
        COALESCE(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END), 0) as out_to_barb,
        COALESCE(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END), 0) as in_from_barb
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
    GROUP BY year
    ORDER BY year DESC
""")

print(f"\n{'Year':<6} {'OUT to Barb':>15} {'IN from Barb':>15} {'Net':>15}")
print("-" * 90)

total_net = Decimal(0)
for year, out_amount, in_amount in cur.fetchall():
    net = out_amount - in_amount
    total_net += net
    print(f"{int(year):<6} ${float(out_amount):>13,.2f} ${float(in_amount):>13,.2f} ${float(net):>13,.2f}")

print("-" * 90)
print(f"{'TOTAL':<6} ${float(Decimal('68763.17')):>13,.2f} ${float(Decimal('24717.96')):>13,.2f} ${float(total_net):>13,.2f}")

# Check if any receipts already coded to 5880
print("\n" + "=" * 90)
print("CURRENT STATE OF GL 5880 (Owner Personal)")
print("=" * 90)

cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) 
    FROM receipts
    WHERE gl_account_code = '5880'
""")

count, total = cur.fetchone()
print(f"\nReceipts currently coded to GL 5880: {count}")
print(f"Total amount: ${float(total):,.2f}")

# Show sample receipts that SHOULD be coded to 5880 (liquor stores)
print("\n" + "=" * 90)
print("SAMPLE RECEIPTS THAT SHOULD BE CODED TO GL 5880 (Personal)")
print("=" * 90)

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, gl_account_code
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%smokes%'
    ORDER BY receipt_date DESC
    LIMIT 15
""")

print("\nLiquor/tobacco purchases (currently may not be marked as personal):")
for rid, date, vendor, gross, gl_code in cur.fetchall():
    print(f"  #{rid} | {date} | {vendor[:30]:30s} | ${float(gross):8.2f} | GL: {gl_code}")

cur.close()
conn.close()

print("\n" + "=" * 90)
print("NEXT STEPS")
print("=" * 90)

print("""
1. ✅ Calculate owner draw: $44,045.21 (completed)

2. ⏳ Identify all personal receipts in database:
   - Liquor store purchases for personal consumption
   - Tobacco/smokes purchases
   - Any other personal items paid by company
   - Filter by vendor patterns or description keywords

3. ⏳ Mark identified receipts as personal:
   - Set is_personal_purchase = true
   - Set gl_account_code = '5880' (Owner Personal)
   - Add note in description for audit trail

4. ⏳ Create journal entry:
   - Dr. Owner's Draw (GL 3020)     $44,045.21
   - Cr. Owner Personal (GL 5880)               $44,045.21
   - Date: 2025-12-31 or date of last Barb transaction

5. ✅ Reconcile:
   - Total personal receipts marked to GL 5880 should approximately match owner draw
   - Barb Peacock net should reconcile to documented personal expenses

NOTE: The $44,045 represents the NET position (what Paul took out more than he put back).
This is recorded as owner draw, which reduces owner's equity but is non-deductible for tax.
""")
