"""
Analyze card number and payment method patterns in receipts table.

This script examines:
1. All receipts (not just banking imports)
2. Card number distribution (3265, 0853, etc.)
3. Payment method patterns (Cash, Debit, Card)
4. Card type usage
5. Receipts that need card categorization
"""

import psycopg2
from collections import defaultdict
import os

# Database connection
conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost",
    port="5432"
)

print("=" * 80)
print("RECEIPT CARD NUMBER AND PAYMENT METHOD ANALYSIS")
print("=" * 80)

cur = conn.cursor()

# Step 1: Check total receipts vs banking receipts
print("\n1. RECEIPT SOURCE DISTRIBUTION")
print("-" * 80)
cur.execute("""
    SELECT 
        CASE 
            WHEN created_from_banking = TRUE THEN 'Banking Import'
            ELSE 'Other Source'
        END as source,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    GROUP BY created_from_banking
    ORDER BY count DESC
""")
for row in cur.fetchall():
    source, count, total = row
    print(f"{source:20} {count:6,} receipts  ${total:15,.2f}")

# Step 2: Check source_system values
print("\n2. SOURCE SYSTEM BREAKDOWN")
print("-" * 80)
cur.execute("""
    SELECT 
        COALESCE(source_system, 'NULL') as source_sys,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    GROUP BY source_system
    ORDER BY count DESC
""")
for row in cur.fetchall():
    source, count, total = row
    print(f"{source:30} {count:6,} receipts  ${total:15,.2f}")

# Step 3: Non-banking receipts with card data
print("\n3. NON-BANKING RECEIPTS - CARD DATA AVAILABILITY")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_non_banking,
        COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card_number,
        COUNT(CASE WHEN card_type IS NOT NULL AND card_type != '' THEN 1 END) as has_card_type,
        COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay_method,
        COUNT(CASE WHEN payment_method IS NOT NULL AND payment_method != '' THEN 1 END) as has_payment_method
    FROM receipts
    WHERE created_from_banking IS NULL OR created_from_banking = FALSE
""")
row = cur.fetchone()
if row and row[0] > 0:
    total, card_num, card_type, pay_meth, payment_meth = row
    print(f"Total non-banking receipts:      {total:6,}")
    print(f"  - With card_number:             {card_num:6,} ({100*card_num/total if total > 0 else 0:5.1f}%)")
    print(f"  - With card_type:               {card_type:6,} ({100*card_type/total if total > 0 else 0:5.1f}%)")
    print(f"  - With pay_method:              {pay_meth:6,} ({100*pay_meth/total if total > 0 else 0:5.1f}%)")
    print(f"  - With payment_method:          {payment_meth:6,} ({100*payment_meth/total if total > 0 else 0:5.1f}%)")
else:
    print("No non-banking receipts found!")

# Step 4: Card number distribution (all receipts)
print("\n4. CARD NUMBER DISTRIBUTION (ALL RECEIPTS)")
print("-" * 80)
cur.execute("""
    SELECT 
        COALESCE(card_number, 'NULL/EMPTY') as card_num,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE card_number IS NOT NULL AND card_number != ''
    GROUP BY card_number
    ORDER BY count DESC
    LIMIT 20
""")
results = cur.fetchall()
if results:
    for row in results:
        card_num, count, total = row
        print(f"{card_num:20} {count:6,} receipts  ${total:15,.2f}")
else:
    print("No card numbers found in any receipts!")

# Step 5: Pay method distribution
print("\n5. PAY METHOD DISTRIBUTION (ALL RECEIPTS)")
print("-" * 80)
cur.execute("""
    SELECT 
        COALESCE(pay_method, 'NULL/EMPTY') as pay_meth,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE pay_method IS NOT NULL AND pay_method != ''
    GROUP BY pay_method
    ORDER BY count DESC
""")
results = cur.fetchall()
if results:
    for row in results:
        pay_meth, count, total = row
        print(f"{pay_meth:20} {count:6,} receipts  ${total:15,.2f}")
else:
    print("No pay_method values found!")

# Step 6: Card type distribution
print("\n6. CARD TYPE DISTRIBUTION (ALL RECEIPTS)")
print("-" * 80)
cur.execute("""
    SELECT 
        COALESCE(card_type, 'NULL/EMPTY') as ctype,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE card_type IS NOT NULL AND card_type != ''
    GROUP BY card_type
    ORDER BY count DESC
""")
results = cur.fetchall()
if results:
    for row in results:
        ctype, count, total = row
        print(f"{ctype:20} {count:6,} receipts  ${total:15,.2f}")
else:
    print("No card_type values found!")

# Step 7: Sample receipts with card data
print("\n7. SAMPLE RECEIPTS WITH CARD NUMBERS")
print("-" * 80)
cur.execute("""
    SELECT 
        id,
        transaction_date,
        vendor_name,
        gross_amount,
        card_number,
        card_type,
        pay_method,
        payment_method
    FROM receipts
    WHERE card_number IS NOT NULL AND card_number != ''
    ORDER BY transaction_date DESC
    LIMIT 10
""")
results = cur.fetchall()
if results:
    print(f"{'ID':6} {'Date':12} {'Vendor':25} {'Amount':12} {'Card#':6} {'Type':10} {'PayMeth':10} {'PaymentMeth':12}")
    print("-" * 110)
    for row in results:
        rid, date, vendor, amount, card_num, card_type, pay_meth, payment_meth = row
        vendor = (vendor or '')[:24]
        card_type = (card_type or '')[:9]
        pay_meth = (pay_meth or '')[:9]
        payment_meth = (payment_meth or '')[:11]
        print(f"{rid:6} {str(date):12} {vendor:25} ${amount:10,.2f} {card_num:6} {card_type:10} {pay_meth:10} {payment_meth:12}")
else:
    print("No receipts with card numbers found!")

# Step 8: Check for CSV import columns that might be different
print("\n8. RECEIPT TABLE COLUMN CHECK")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND column_name ILIKE '%card%' OR column_name ILIKE '%pay%'
    ORDER BY column_name
""")
print("Columns related to card/payment:")
for row in cur.fetchall():
    col_name, data_type = row
    print(f"  {col_name:30} {data_type}")

# Step 9: Check if there are any receipts with description containing card numbers
print("\n9. SEARCHING DESCRIPTIONS FOR CARD NUMBER PATTERNS")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) as count
    FROM receipts
    WHERE description ILIKE '%3265%'
       OR description ILIKE '%card%'
       OR notes ILIKE '%3265%'
       OR notes ILIKE '%card%'
""")
count = cur.fetchone()[0]
print(f"Receipts with '3265' or 'card' in description/notes: {count:,}")

# Step 10: Summary and recommendations
print("\n" + "=" * 80)
print("SUMMARY AND NEXT STEPS")
print("=" * 80)

cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = TRUE")
banking_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking IS NULL OR created_from_banking = FALSE")
non_banking_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE card_number IS NOT NULL AND card_number != ''")
with_card_numbers = cur.fetchone()[0]

print(f"\n1. Total receipts in database:")
print(f"   - Banking imports:     {banking_count:6,} receipts")
print(f"   - Non-banking:         {non_banking_count:6,} receipts")
print(f"   - With card numbers:   {with_card_numbers:6,} receipts")

if with_card_numbers == 0:
    print("\n2. PROBLEM IDENTIFIED: No card numbers found in database!")
    print("   - Original CSV files have 'Card number' column")
    print("   - Database card_number field is empty")
    print("   - Card data was lost during import/migration")
    print("\n3. RECOMMENDED SOLUTION:")
    print("   - Re-import receipts from CSV files")
    print("   - Ensure card_number, card_type, pay_method fields are populated")
    print("   - Map CSV columns correctly to database columns")
else:
    print("\n2. Card data found! Analyzing patterns...")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("Analysis complete!")
print("=" * 80)
