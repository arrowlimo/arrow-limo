import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("VENDOR NAME CLASSIFICATION")
print("="*80)

# Legitimate transaction type names (not vendors)
legitimate_names = [
    'CASH WITHDRAWAL', 'BRANCH WITHDRAWAL',
    'NSF CHARGE', 'NSF FEE', 'NSF Fee',
    'BANK SERVICE FEE', 'SERVICE CHARGE', 'OVERDRAFT FEE', 'OD FEE',
    'EMAIL TRANSFER FEE', 'E-TRANSFER FEE',
    'Overdraft Interest',
    'DEPOSIT'
]

# Names that need extraction/fixing
needs_fixing = [
    'CHEQUE', 'CHECK', 'CHECK PAYMENT', 'CHEQUE PAYMENT',
    'EMAIL TRANSFER', 'E-TRANSFER', 'ETRANSFER',
    'POINT OF', 'PURCHASE', 'POS',
    'BANKING', 'BANK',
    'UNKNOWN', 'UNKNOWN PAYEE', 'UNKNOWN PAYEE (CHEQUE)',
    'INTERAC', 'DEBIT CARD'
]

# Check for other problematic patterns
print("\nLEGITIMATE TRANSACTION TYPE NAMES:")
print("-"*80)
for name in legitimate_names:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name = %s
          AND exclude_from_reports = FALSE
    """, (name,))
    count, amount = cur.fetchone()
    if count and count > 0:
        print(f"  ✅ {name:<35} {count:>5,} | ${float(amount):>12,.2f}")

print(f"\n{'='*80}")
print("VENDOR NAMES THAT NEED REAL NAMES EXTRACTED:")
print("-"*80)

total_needs_fixing = 0
total_amount_needs_fixing = 0

for name in needs_fixing:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name = %s
          AND exclude_from_reports = FALSE
    """, (name,))
    count, amount = cur.fetchone()
    if count and count > 0:
        total_needs_fixing += count
        total_amount_needs_fixing += float(amount) if amount else 0
        print(f"  ❌ {name:<35} {count:>5,} | ${float(amount) if amount else 0:>12,.2f}")

print(f"\n  TOTAL NEEDS FIXING: {total_needs_fixing:,} receipts | ${total_amount_needs_fixing:,.2f}")

# Check for other suspicious patterns
print(f"\n{'='*80}")
print("OTHER SUSPICIOUS VENDOR NAMES:")
print("-"*80)

# Check for vendor names that are transaction codes or fragments
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE exclude_from_reports = FALSE
      AND (
        vendor_name ~ '^[0-9]'  -- Starts with number
        OR vendor_name ~ '^\w{1,3}$'  -- 1-3 characters only
        OR vendor_name LIKE '%- %'  -- Has dash-space (incomplete extraction)
        OR vendor_name LIKE 'CORRECTION%'
        OR vendor_name LIKE 'CREDIT MEMO%'
        OR vendor_name LIKE 'Cheque Expense%'
        OR vendor_name LIKE '%4506*%'  -- Has card number fragment
        OR vendor_name LIKE 'FGP%'  -- Transaction code
      )
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
    LIMIT 30
""")

other_suspicious = cur.fetchall()
if other_suspicious:
    for vendor, count, amount in other_suspicious:
        print(f"  ⚠️  {vendor:<50} {count:>4,} | ${float(amount) if amount else 0:>10,.2f}")

# Check for EMAIL TRANSFER with recipient names (these are OK)
print(f"\n{'='*80}")
print("EMAIL TRANSFER BREAKDOWN:")
print("-"*80)

cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name = 'EMAIL TRANSFER' THEN 'Generic (no recipient)'
            WHEN vendor_name LIKE 'EMAIL TRANSFER %' THEN 'Has recipient name'
            WHEN vendor_name = 'E-TRANSFER' THEN 'Generic (no recipient)'
            ELSE vendor_name
        END as category,
        COUNT(*),
        SUM(gross_amount)
    FROM receipts
    WHERE (vendor_name LIKE '%TRANSFER%' OR vendor_name LIKE '%E-TRANS%')
      AND exclude_from_reports = FALSE
    GROUP BY category
    ORDER BY COUNT(*) DESC
""")

for category, count, amount in cur.fetchall():
    status = "✅" if "recipient" in category.lower() or "FEE" in category else "❌"
    print(f"  {status} {category:<40} {count:>4,} | ${float(amount) if amount else 0:>12,.2f}")

# Check for vendor names from banking that need extraction
print(f"\n{'='*80}")
print("SAMPLE RECEIPTS NEEDING VENDOR EXTRACTION:")
print("-"*80)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('CHEQUE', 'CHECK PAYMENT', 'UNKNOWN PAYEE (CHEQUE)', 
                            'EMAIL TRANSFER', 'E-TRANSFER',
                            'POINT OF', 'PURCHASE', 'POS',
                            'BANKING', 'UNKNOWN')
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
    ORDER BY r.gross_amount DESC
    LIMIT 20
""")

print("\nTop 20 by amount:")
for rec_id, vendor, amount, desc in cur.fetchall():
    print(f"\n  Receipt #{rec_id} | ${float(amount):,.2f} | {vendor}")
    print(f"    Banking: {desc[:75]}")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("SUMMARY:")
print("="*80)
print("""
✅ LEGITIMATE (keep as-is):
   - CASH WITHDRAWAL, BRANCH WITHDRAWAL (cash box)
   - NSF CHARGE, NSF FEE (bank penalties)
   - BANK SERVICE FEE, SERVICE CHARGE, OVERDRAFT FEE (bank fees)
   - DEPOSIT (generic banking)
   - EMAIL TRANSFER FEE (bank fee for e-transfers)

❌ NEED REAL VENDOR NAMES EXTRACTED:
   - CHEQUE, CHECK PAYMENT → extract payee from banking or cheque reference
   - EMAIL TRANSFER, E-TRANSFER → extract recipient name from banking description
   - POINT OF, PURCHASE, POS → extract merchant from banking description
   - BANKING, BANK → extract vendor from banking description
   - UNKNOWN, UNKNOWN PAYEE → extract from banking description
   - INTERAC, DEBIT CARD → extract merchant from banking description

⚠️  OTHER ISSUES TO CHECK:
   - CORRECTION, CREDIT MEMO → may be accounting adjustments, verify
   - Cheque Expense - [category] → QuickBooks format, may need cleanup
   - Vendor names with card numbers (4506*) → incomplete extraction
   - Transaction codes (FGP...) → need merchant name extraction
""")
