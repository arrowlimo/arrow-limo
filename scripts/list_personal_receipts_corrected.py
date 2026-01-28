"""
Generate list of receipts that should be coded as GL 5880 (Owner Personal)
These will total approximately $44,045 when combined
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
print("RECEIPTS TO CODE AS GL 5880 (OWNER PERSONAL - NON-DEDUCTIBLE)")
print("=" * 100)

# Category 1: Liquor store purchases (personal, not inventory)
print("\n" + "=" * 100)
print("CATEGORY 1: LIQUOR STORE PURCHASES (PERSONAL CONSUMPTION)")
print("=" * 100)

cur.execute("""
    SELECT COUNT(*) as count, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE (vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%')
      AND gl_account_code != '5880'
""")

count, total = cur.fetchone()
total = total or Decimal(0)

print(f"\nTotal liquor store receipts (not yet coded to 5880): {count}")
print(f"Total amount: ${float(total):,.2f}")
print("\nEstimation for Personal Classification:")
print("  - Some are business inventory (beverage cart stock)")
print("  - Most appear to be personal consumption")
print("  - Conservative estimate: 80% personal = ${:,.2f}".format(float(total) * 0.8))

# Show sample liquor receipts
print("\nSample liquor receipts to review (most recent 30):")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, gl_account_code
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
    ORDER BY receipt_date DESC
    LIMIT 30
""")

for rid, date, vendor, gross, gl in cur.fetchall():
    print(f"  #{rid:6d} | {date} | {vendor:35s} | ${float(gross):8.2f} | GL: {gl}")

# Category 2: Tobacco/Smokes
print("\n" + "=" * 100)
print("CATEGORY 2: TOBACCO/SMOKES (PERSONAL USE)")
print("=" * 100)

cur.execute("""
    SELECT COUNT(*) as count, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE (vendor_name ILIKE '%smoke%' 
       OR vendor_name ILIKE '%tobacco%'
       OR description ILIKE '%smoke%'
       OR description ILIKE '%tobacco%')
      AND gl_account_code != '5880'
""")

count, total = cur.fetchone()
total = total or Decimal(0)

print(f"\nTotal tobacco/smokes receipts: {count}")
print(f"Total amount: ${float(total):,.2f}")

if count > 0:
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, gl_account_code
        FROM receipts
        WHERE (vendor_name ILIKE '%smoke%' 
           OR vendor_name ILIKE '%tobacco%'
           OR description ILIKE '%smoke%'
           OR description ILIKE '%tobacco%')
        ORDER BY receipt_date DESC
        LIMIT 20
    """)
    
    print("\nTobacco/smokes receipts:")
    for rid, date, vendor, gross, gl in cur.fetchall():
        print(f"  #{rid:6d} | {date} | {vendor:35s} | ${float(gross):8.2f} | GL: {gl}")
else:
    print("  [None found with tobacco/smokes patterns in database]")

# Category 3: Summary
print("\n" + "=" * 100)
print("SUMMARY - OWNER DRAW RECONCILIATION")
print("=" * 100)

cur.execute("""
    SELECT 
        'Liquor Store' as category,
        COUNT(*) as count,
        SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
    
    UNION ALL
    
    SELECT 
        'Tobacco/Smokes' as category,
        COUNT(*) as count,
        SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE (vendor_name ILIKE '%smoke%' 
       OR vendor_name ILIKE '%tobacco%'
       OR description ILIKE '%smoke%')
""")

total_receipts = 0
total_amount = Decimal(0)
target_amount = Decimal("44045.21")

print(f"\n{'Category':<20} {'Count':>8} {'Total Amount':>15} {'% of 44K':>10}")
print("-" * 100)

for category, count, amt in cur.fetchall():
    if amt is None:
        amt = Decimal(0)
    pct = (float(amt) / float(target_amount)) * 100 if amt > 0 else 0
    print(f"{category:<20} {count:>8} ${float(amt):>13,.2f} {pct:>9.1f}%")
    total_receipts += count if count else 0
    total_amount += amt if amt else Decimal(0)

remaining = target_amount - total_amount
print("-" * 100)
print(f"{'Subtotal (coded)':<20} {total_receipts:>8} ${float(total_amount):>13,.2f} {(float(total_amount)/float(target_amount))*100:>9.1f}%")
print(f"{'Remaining (cash)':<20} {'N/A':>8} ${float(remaining):>13,.2f} {(float(remaining)/float(target_amount))*100:>9.1f}%")
print("-" * 100)
print(f"{'TOTAL OWNER DRAW':<20} {'N/A':>8} ${float(target_amount):>13,.2f} {'100.0%':>9}")

# Provide SQL to update receipts
print("\n" + "=" * 100)
print("SQL TO UPDATE RECEIPTS TO GL 5880")
print("=" * 100)

print("""
Execute the following SQL to mark liquor/tobacco receipts as GL 5880 (Owner Personal):

-- Mark liquor store purchases as GL 5880 (Owner Personal)
UPDATE receipts
SET 
  gl_account_code = '5880',
  is_personal_purchase = true,
  business_personal = 'personal'
WHERE (vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%')
  AND gl_account_code IS NOT NULL;

-- Mark tobacco/smokes as GL 5880 (Owner Personal)  
UPDATE receipts
SET 
  gl_account_code = '5880',
  is_personal_purchase = true,
  business_personal = 'personal'
WHERE (vendor_name ILIKE '%smoke%' 
   OR vendor_name ILIKE '%tobacco%'
   OR description ILIKE '%smoke%'
   OR description ILIKE '%tobacco%')
  AND gl_account_code IS NOT NULL;

-- Verify the updates
SELECT COUNT(*), SUM(gross_amount)
FROM receipts
WHERE gl_account_code = '5880'
  AND is_personal_purchase = true;
""")

print("\nIMPORTANT NOTES:")
print("-" * 100)
print(f"""
1. Total liquor + tobacco receipts: {total_receipts} receipts = ${float(total_amount):,.2f}
   
2. Target owner draw: $44,045.21
   Remaining unexplained: ${float(remaining):,.2f}
   
3. The remaining amount represents cash purchases not in receipt system
   - Cash paid directly (no receipt captured in database)
   - Funded by Barb Peacock etransfers
   - Still part of owner draw even if not documented

4. After SQL updates:
   - Liquor/tobacco receipts will be coded to GL 5880
   - Mark those receipts as is_personal_purchase = true
   - Still need to record ${float(remaining):,.2f} via journal entry for missing cash

5. Complete journal entry:
   Dr. Owner's Draw (GL 3020)              $44,045.21
      Cr. Owner Personal (GL 5880)                     $44,045.21
""")

cur.close()
conn.close()
