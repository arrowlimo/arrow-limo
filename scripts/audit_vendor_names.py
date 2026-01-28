import psycopg2
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("VENDOR NAME STANDARDIZATION AUDIT")
print("="*80)

# Check for generic vendor names
generic_vendors = [
    'CHEQUE', 'CHECK', 'CHECK PAYMENT', 'CHEQUE PAYMENT',
    'BANKING', 'BANK', 'BANKING - DEPOSIT',
    'CASH', 'CASH WITHDRAWAL', 'BRANCH WITHDRAWAL',
    'EMAIL TRANSFER', 'E-TRANSFER', 'ETRANSFER',
    'POINT OF', 'PURCHASE', 'POS',
    'NSF CHARGE', 'NSF FEE', 'SERVICE CHARGE',
    'INTERAC', 'DEBIT CARD',
    'UNKNOWN', 'UNKNOWN PAYEE', 'MISC'
]

print("\nGeneric/Non-Searchable Vendor Names:")
print("-"*80)

total_generic = 0
total_generic_amount = 0

for generic in generic_vendors:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name ILIKE %s
          AND exclude_from_reports = FALSE
    """, (f'%{generic}%',))
    
    count, amount = cur.fetchone()
    if count and count > 0:
        total_generic += count
        total_generic_amount += float(amount) if amount else 0
        print(f"  {generic:<30} {count:>5,} receipts  ${float(amount) if amount else 0:>12,.2f}")

print(f"\n  TOTAL GENERIC: {total_generic:,} receipts  ${total_generic_amount:,.2f}")

# Check for canonical_vendor usage
cur.execute("""
    SELECT COUNT(*), COUNT(DISTINCT canonical_vendor)
    FROM receipts
    WHERE exclude_from_reports = FALSE
""")
total, unique_canonical = cur.fetchone()

print(f"\n{'='*80}")
print("CANONICAL VENDOR USAGE:")
print("-"*80)
print(f"Total receipts: {total:,}")
print(f"Unique canonical_vendor values: {unique_canonical if unique_canonical else 'NULL (not being used)'}")

# Check if there's a separate vendor table
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
      AND table_name LIKE '%vendor%'
""")
vendor_tables = cur.fetchall()

print(f"\n{'='*80}")
print("VENDOR-RELATED TABLES:")
print("-"*80)
if vendor_tables:
    for table in vendor_tables:
        print(f"  {table[0]}")
        cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
        print(f"    {cur.fetchone()[0]:,} rows")
else:
    print("  ❌ No vendor table found")

# Get top vendors by frequency
print(f"\n{'='*80}")
print("TOP 50 VENDOR NAMES (by frequency):")
print("-"*80)

cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE exclude_from_reports = FALSE
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
    LIMIT 50
""")

for vendor, count, amount in cur.fetchall():
    print(f"{count:>5,} | ${float(amount) if amount else 0:>12,.2f} | {vendor}")

# Check for vendors from banking descriptions
print(f"\n{'='*80}")
print("SAMPLE BANKING DESCRIPTIONS (for vendor extraction):")
print("-"*80)

cur.execute("""
    SELECT DISTINCT bt.description
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('CHEQUE', 'CHECK PAYMENT', 'BANKING', 'PURCHASE', 'POINT OF')
      AND r.exclude_from_reports = FALSE
    LIMIT 20
""")

for desc in cur.fetchall():
    if desc[0]:
        print(f"  {desc[0][:75]}")

print(f"\n{'='*80}")
print("RECOMMENDATIONS:")
print("="*80)
print("""
1. CREATE VENDOR STANDARDIZATION TABLE:
   - Create vendors table with (vendor_id, canonical_name, aliases[], category)
   - Link receipts.canonical_vendor → vendors.canonical_name

2. EXTRACT VENDOR NAMES FROM BANKING DESCRIPTIONS:
   - "CHEQUE 123 PAYEE NAME" → extract "PAYEE NAME"
   - "Point of Sale - MERCHANT NAME" → extract "MERCHANT NAME"
   - "Electronic Funds Transfer COMPANY" → extract "COMPANY"

3. STANDARDIZE COMMON VARIATIONS:
   - "FAS GAS", "FASGAS", "FAS GAS STATION" → "FAS GAS"
   - "MONEY MART", "MONEY MART #120" → "MONEY MART"
   - "GLOBAL VISA DEPOSIT", "GBL VI 41000..." → "GLOBAL PAYMENTS VISA"

4. MARK LEGITIMATE BANKING NAMES:
   - "NSF CHARGE" - legitimate (bank fee, not vendor)
   - "CASH WITHDRAWAL" - legitimate (transaction type, not vendor)
   - "BANKING - DEPOSIT" - needs extraction from banking description

Would you like me to:
a) Extract vendor names from banking descriptions for generic entries
b) Create a vendor standardization table
c) Build a vendor name cleanup script
""")

cur.close()
conn.close()
