"""
Step 2: Find all receipts marked as personal
Uses is_personal_purchase field and business_personal field
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

# Find receipts marked as personal
print("=" * 90)
print("ALL RECEIPTS MARKED AS PERSONAL")
print("=" * 90)

# Query 1: is_personal_purchase = true
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description,
           business_personal, is_personal_purchase, owner_personal_amount
    FROM receipts
    WHERE is_personal_purchase = true
    ORDER BY receipt_date DESC
""")

personal_by_flag = cur.fetchall()
print(f"\n📌 By is_personal_purchase=true: {len(personal_by_flag)} receipts")
print("-" * 90)

total_personal = Decimal(0)
for rid, date, vendor, gross, desc, bp, is_pers, owner_amt in personal_by_flag[:20]:
    owner_amt = owner_amt or Decimal(0)
    total_personal += gross
    print(f"  #{rid} | {date} | {vendor[:25]:25s} | ${gross:8.2f} | is_personal={is_pers}, bp={bp}")
    if desc and len(desc) < 60:
        print(f"         Description: {desc}")

if len(personal_by_flag) > 20:
    print(f"  ... and {len(personal_by_flag) - 20} more receipts")

# Query 2: business_personal marked as 'personal' or 'owner'
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description,
           business_personal, is_personal_purchase, owner_personal_amount
    FROM receipts
    WHERE business_personal IS NOT NULL AND LOWER(business_personal) IN ('personal', 'owner', 'paul', 'draw')
    ORDER BY receipt_date DESC
""")

personal_by_bp = cur.fetchall()
print(f"\n📌 By business_personal flag: {len(personal_by_bp)} receipts")
print("-" * 90)

for rid, date, vendor, gross, desc, bp, is_pers, owner_amt in personal_by_bp[:20]:
    owner_amt = owner_amt or Decimal(0)
    print(f"  #{rid} | {date} | {vendor[:25]:25s} | ${gross:8.2f} | bp={bp}, is_personal={is_pers}")
    if desc and len(desc) < 60:
        print(f"         Description: {desc}")

if len(personal_by_bp) > 20:
    print(f"  ... and {len(personal_by_bp) - 20} more receipts")

# Summary by vendor for personal receipts
print("\n" + "=" * 90)
print("PERSONAL EXPENSES SUMMARY BY VENDOR (Liquor stores)")
print("=" * 90)

cur.execute("""
    SELECT vendor_name, COUNT(*) as receipt_count, SUM(gross_amount) as total_amount,
           MAX(receipt_date) as last_purchase
    FROM receipts
    WHERE is_personal_purchase = true
       AND (vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%')
    GROUP BY vendor_name
    ORDER BY total_amount DESC
    LIMIT 15
""")

liquor_summary = cur.fetchall()
if liquor_summary:
    print(f"\nLiquor Store Purchases ({len(liquor_summary)} vendors):")
    for vendor, count, total, last_date in liquor_summary:
        print(f"  • {vendor[:35]:35s} | Count: {count:3d} | Total: ${total:8.2f} | Last: {last_date}")
else:
    print("No liquor store purchases marked as personal found")

# Check for etransfers to Barb Peacock in banking_transactions
print("\n" + "=" * 90)
print("BARB PEACOCK ETRANSFERS")
print("=" * 90)

cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           CASE WHEN debit_amount > 0 THEN debit_amount ELSE credit_amount END as amount,
           CASE WHEN debit_amount > 0 THEN 'OUTGOING' ELSE 'INCOMING' END as direction
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
    ORDER BY transaction_date DESC
""")

barb_txns = cur.fetchall()
print(f"\n📌 Etransfers involving Barb Peacock: {len(barb_txns)} transactions")
print("-" * 90)

for txn_id, date, desc, amt, direction in barb_txns:
    print(f"  {direction:8s} | {date} | ${amt:8.2f} | {desc[:60]}")

# Summary totals
print("\n" + "=" * 90)
print("SUMMARY TOTALS")
print("=" * 90)

cur.execute("""
    SELECT COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE is_personal_purchase = true
""")

count, total = cur.fetchone()
print(f"\nTotal receipts marked as personal: {count}")
print(f"Total amount (personal): ${total:.2f}")

cur.execute("""
    SELECT COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE business_personal IS NOT NULL AND LOWER(business_personal) = 'personal'
""")

count2, total2 = cur.fetchone()
print(f"\nTotal receipts with business_personal='personal': {count2}")
print(f"Total amount: ${total2:.2f}")

cur.execute("""
    SELECT SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as outgoing,
           SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as incoming
    FROM banking_transactions
    WHERE description ILIKE '%barb%' OR description ILIKE '%peacock%'
""")

barb_outgoing, barb_incoming = cur.fetchone()
print(f"\nBarb Peacock etransfers:")
print(f"  Outgoing (to Barb): ${barb_outgoing or 0:.2f}")
print(f"  Incoming (from Barb): ${barb_incoming or 0:.2f}")
print(f"  Net difference: ${(barb_outgoing or 0) - (barb_incoming or 0):.2f}")

cur.close()
conn.close()
