#!/usr/bin/env python3
"""
Step 1: Standardize WCB vendor names and categorize fees/penalties
"""

import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*70)
print("WCB VENDOR STANDARDIZATION AND CATEGORIZATION")
print("="*70)

# Step 1: Identify WCB ALBERTA records
print("\nStep 1: WCB ALBERTA → WCB standardization")
print("-" * 70)

cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB ALBERTA'
    ORDER BY receipt_date
""")

wcb_alberta_records = cur.fetchall()
print(f"Found {len(wcb_alberta_records)} WCB ALBERTA records to standardize:")
for receipt_id, ref, date, amount, desc in wcb_alberta_records:
    print(f"  Receipt {receipt_id:6} | {date} | ${amount:>10,.2f} | Ref {ref}")

# Step 2: Identify penalties/fees (look for keywords)
print(f"\nStep 2: Identify fees/penalties for subcategory")
print("-" * 70)

cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, gross_amount, description, vendor_name
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
      AND (
          LOWER(description) LIKE '%penalty%'
          OR LOWER(description) LIKE '%fee%'
          OR LOWER(description) LIKE '%interest%'
          OR LOWER(description) LIKE '%late%'
          OR LOWER(description) LIKE '%overdue%'
          OR LOWER(description) LIKE '%waived%'
      )
    ORDER BY receipt_date
""")

penalty_records = cur.fetchall()
print(f"Found {len(penalty_records)} potential penalty/fee records:")
for receipt_id, ref, date, amount, desc, vendor in penalty_records:
    print(f"  Receipt {receipt_id:6} | {date} | ${amount:>10,.2f} | {desc[:40]}")

# Step 3: Apply changes
print(f"\n{'='*70}")
print("APPLYING CHANGES")
print("="*70)

try:
    # Update WCB ALBERTA → WCB
    cur.execute("""
        UPDATE receipts
        SET vendor_name = 'WCB',
            canonical_vendor = 'WCB'
        WHERE vendor_name = 'WCB ALBERTA'
    """)
    updated_count = cur.rowcount
    print(f"\n✓ Updated {updated_count} records: WCB ALBERTA → WCB")
    
    # Create a category field or use existing classification
    # Check if we need to add a subcategory column
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' AND column_name = 'sub_classification'
    """)
    has_subcat = cur.fetchone() is not None
    
    if has_subcat:
        # Update penalties to WCB-fees/penalties subcategory
        cur.execute("""
            UPDATE receipts
            SET sub_classification = 'WCB-fees/penalties'
            WHERE vendor_name = 'WCB'
              AND (
                  LOWER(description) LIKE '%penalty%'
                  OR LOWER(description) LIKE '%fee%'
                  OR LOWER(description) LIKE '%interest%'
                  OR LOWER(description) LIKE '%late%'
                  OR LOWER(description) LIKE '%overdue%'
                  OR LOWER(description) LIKE '%waived%'
              )
        """)
        penalty_count = cur.rowcount
        print(f"✓ Categorized {penalty_count} records as 'WCB-fees/penalties'")
        
        # Set regular WCB to just 'WCB' subcategory
        cur.execute("""
            UPDATE receipts
            SET sub_classification = 'WCB'
            WHERE vendor_name = 'WCB'
              AND (sub_classification IS NULL OR sub_classification != 'WCB-fees/penalties')
        """)
        regular_count = cur.rowcount
        print(f"✓ Categorized {regular_count} records as 'WCB' (regular premiums)")
    
    conn.commit()
    print("\n✅ All changes committed successfully!")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Show new reconciliation
print(f"\n{'='*70}")
print("2012 WCB RECONCILIATION (After Standardization)")
print("="*70)

cur.execute("""
    SELECT 
        COALESCE(sub_classification, 'Uncategorized') as category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name = 'WCB'
      AND gross_amount > 0
      AND receipt_date >= '2012-01-01'
    GROUP BY sub_classification
    ORDER BY category
""")

total_2012 = Decimal('0')
print("\nInvoices by subcategory:")
for category, count, total in cur.fetchall():
    total = total or Decimal('0')
    total_2012 += total
    print(f"  {category:30} | {count:2} invoices | ${total:>10,.2f}")

print(f"\n  {'TOTAL 2012 INVOICES':30} | {' ':2}          | ${total_2012:>10,.2f}")

# Show payments
cur.execute("""
    SELECT SUM(debit_amount)
    FROM banking_transactions
    WHERE transaction_id IN (69282, 69587)
""")
banking_payments = cur.fetchone()[0] or Decimal('0')

cur.execute("""
    SELECT SUM(gross_amount)
    FROM receipts
    WHERE receipt_id IN (145297, 145305) AND vendor_name = 'WCB'
""")
receipt_payments = cur.fetchone()[0] or Decimal('0')

total_payments = banking_payments + receipt_payments

print(f"\nPayments:")
print(f"  Banking:   ${banking_payments:>10,.2f}")
print(f"  Receipts:  ${receipt_payments:>10,.2f}")
print(f"  TOTAL:     ${total_payments:>10,.2f}")

balance = total_2012 - total_payments
print(f"\n2012 Balance: ${balance:>10,.2f}")
print(f"Target:       $   3,593.83")

conn.close()
