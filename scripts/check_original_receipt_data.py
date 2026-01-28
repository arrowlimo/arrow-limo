"""
Check receipts that have card_type or card_number populated from original CSV imports.
Also check for 'Cash' in Pay method field.
"""

import psycopg2
import pandas as pd

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

print("=" * 80)
print("ANALYZING ORIGINAL RECEIPT DATA WITH CARD INFO")
print("=" * 80)
print()

# First, let's see if there are receipts NOT created from banking
print("Step 1: Checking non-banking receipts...")
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE created_from_banking IS NOT TRUE
    OR created_from_banking IS NULL
""")
non_banking_count, non_banking_amount = cur.fetchone()
print(f"Non-banking receipts: {non_banking_count:,} (${non_banking_amount:,.2f if non_banking_amount else 0})")
print()

# Check what source_system values exist
print("Step 2: Checking source_system values...")
cur.execute("""
    SELECT 
        source_system,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY source_system
    ORDER BY count DESC
""")

for source, count, amount in cur.fetchall():
    if amount:
        print(f"  {source or '(null)':30} {count:6,} receipts  ${amount:12,.2f}")
    else:
        print(f"  {source or '(null)':30} {count:6,} receipts  (no amount)")

print()

# Check for specific card numbers in card_number field
print("Step 3: Checking for populated card_number values...")
cur.execute("""
    SELECT 
        card_number,
        COUNT(*) as count
    FROM receipts
    WHERE card_number IS NOT NULL 
    AND card_number != ''
    GROUP BY card_number
    ORDER BY count DESC
    LIMIT 20
""")

results = cur.fetchall()
if results:
    print(f"Found {len(results)} unique card numbers:")
    for card_num, count in results:
        print(f"  {card_num:20} {count:,} receipts")
else:
    print("  No card_number values found")

print()

# Check card_type field
print("Step 4: Checking for populated card_type values...")
cur.execute("""
    SELECT 
        card_type,
        COUNT(*) as count
    FROM receipts
    WHERE card_type IS NOT NULL 
    AND card_type != ''
    GROUP BY card_type
    ORDER BY count DESC
""")

results = cur.fetchall()
if results:
    print(f"Found {len(results)} unique card types:")
    for card_type, count in results:
        print(f"  {card_type:20} {count:,} receipts")
else:
    print("  No card_type values found")

print()

# Read a sample CSV to see structure
print("=" * 80)
print("CHECKING SAMPLE RECEIPT CSV FILE")
print("=" * 80)
print()

try:
    df = pd.read_csv('l:/limo/receipts new sept.csv', nrows=5)
    print("CSV Columns:")
    for col in df.columns:
        print(f"  - {col}")
    print()
    
    # Show sample rows with card info
    if 'Card number' in df.columns or 'Card type' in df.columns:
        print("Sample data with card fields:")
        cols_to_show = ['Date issued', 'Vendor', 'Total', 'Pay method', 'Card type', 'Card number']
        cols_available = [c for c in cols_to_show if c in df.columns]
        print(df[cols_available].to_string())
        print()
        
        # Check how many have cash/debit
        if 'Pay method' in df.columns:
            full_df = pd.read_csv('l:/limo/receipts new sept.csv')
            pay_methods = full_df['Pay method'].value_counts()
            print("\nPayment methods in CSV:")
            print(pay_methods)
            
except Exception as e:
    print(f"Could not read CSV: {e}")

print()

# Check if there's a mapping issue - maybe the fields were renamed during import
print("=" * 80)
print("CHECKING ALL TEXT COLUMNS FOR CASH/DEBIT INDICATORS")
print("=" * 80)
print()

# Sample some receipts to see all their data
cur.execute("""
    SELECT 
        id,
        receipt_date,
        vendor_name,
        gross_amount,
        payment_method,
        pay_method,
        card_type,
        card_number,
        source_system,
        created_from_banking
    FROM receipts
    WHERE created_from_banking IS NOT TRUE
    OR created_from_banking IS NULL
    LIMIT 10
""")

print("Sample non-banking receipts:")
for row in cur.fetchall():
    print(f"ID: {row[0]:6} | Date: {row[1]} | Vendor: {(row[2] or 'None')[:30]:30} | ${row[3]:8.2f}")
    print(f"  payment_method: {row[4] or 'None'}")
    print(f"  pay_method: {row[5] or 'None'}")
    print(f"  card_type: {row[6] or 'None'}")
    print(f"  card_number: {row[7] or 'None'}")
    print(f"  source: {row[8] or 'None'}, from_banking: {row[9]}")
    print()

cur.close()
conn.close()
