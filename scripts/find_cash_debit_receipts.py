"""
Find cash/debit receipts using card number field.
User mentioned card_number or card_type field has values like "3265" for debit/cash.
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

print("=" * 80)
print("FINDING CASH/DEBIT RECEIPTS BY CARD FIELD")
print("=" * 80)
print()

# Check card_number and card_type fields
print("Step 1: Checking card_number field...")
cur.execute("""
    SELECT 
        card_number,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE card_number IS NOT NULL
    AND card_number != ''
    GROUP BY card_number
    ORDER BY count DESC
    LIMIT 20
""")

results = cur.fetchall()
print(f"\nFound {len(results)} unique card numbers:")
for card, count, amount in results:
    if amount:
        print(f"  {card:20} {count:6,} receipts  ${amount:12,.2f}")
    else:
        print(f"  {card:20} {count:6,} receipts  (no amount)")

print()

# Check card_type field  
print("Step 2: Checking card_type field...")
cur.execute("""
    SELECT 
        card_type,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE card_type IS NOT NULL
    AND card_type != ''
    GROUP BY card_type
    ORDER BY count DESC
""")

results = cur.fetchall()
print(f"\nFound {len(results)} unique card types:")
for card_type, count, amount in results:
    if amount:
        print(f"  {card_type:20} {count:6,} receipts  ${amount:12,.2f}")
    else:
        print(f"  {card_type:20} {count:6,} receipts  (no amount)")

print()

# Look for receipts with "3265" specifically
print("Step 3: Looking for card number '3265'...")
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE card_number LIKE '%3265%'
    OR card_type LIKE '%3265%'
""")
count, amount = cur.fetchone()
if count and count > 0:
    print(f"  Found {count:,} receipts with '3265': ${amount:,.2f}")
else:
    print("  No receipts found with '3265'")

print()

# Get sample receipts with card numbers
print("=" * 80)
print("SAMPLE RECEIPTS WITH CARD NUMBERS")
print("=" * 80)
print()

cur.execute("""
    SELECT 
        id,
        receipt_date,
        vendor_name,
        description,
        gross_amount,
        card_number,
        card_type,
        payment_method
    FROM receipts
    WHERE (card_number IS NOT NULL AND card_number != '')
       OR (card_type IS NOT NULL AND card_type != '')
    ORDER BY receipt_date DESC
    LIMIT 20
""")

for row in cur.fetchall():
    rec_id, date, vendor, desc, amount, card_num, card_type, pay_method = row
    print(f"ID: {rec_id:8} | Date: {date} | Amount: ${amount:10,.2f}")
    print(f"  Vendor: {vendor or 'None'}")
    print(f"  Card Number: {card_num or 'None':20} Card Type: {card_type or 'None'}")
    print(f"  Payment Method: {pay_method or 'None'}")
    if desc:
        print(f"  Desc: {desc[:60]}")
    print()

# Check pay_method field too
print("=" * 80)
print("CHECKING pay_method FIELD")
print("=" * 80)
print()

cur.execute("""
    SELECT 
        pay_method,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE pay_method IS NOT NULL
    AND pay_method != ''
    GROUP BY pay_method
    ORDER BY count DESC
    LIMIT 20
""")

results = cur.fetchall()
print(f"\nFound {len(results)} unique pay_method values:")
for method, count, amount in results:
    if amount:
        print(f"  {method:30} {count:6,} receipts  ${amount:12,.2f}")
    else:
        print(f"  {method:30} {count:6,} receipts  (no amount)")

print()

# Check for debit/cash in any text field
print("=" * 80)
print("SEARCHING FOR 'DEBIT' OR 'CASH' IN ALL TEXT FIELDS")
print("=" * 80)
print()

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(payment_method) LIKE '%debit%'
       OR LOWER(pay_method) LIKE '%debit%'
       OR LOWER(canonical_pay_method) LIKE '%debit%'
       OR LOWER(card_type) LIKE '%debit%'
       OR LOWER(description) LIKE '%debit%'
""")
count, amount = cur.fetchone()
print(f"Receipts with 'debit': {count:,} (${amount:,.2f})")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(payment_method) LIKE '%cash%'
       OR LOWER(pay_method) LIKE '%cash%'
       OR LOWER(canonical_pay_method) LIKE '%cash%'
       OR LOWER(card_type) LIKE '%cash%'
""")
count, amount = cur.fetchone()
if amount:
    print(f"Receipts with 'cash': {count:,} (${amount:,.2f})")
else:
    print(f"Receipts with 'cash': {count:,} (no amount)")

cur.close()
conn.close()
