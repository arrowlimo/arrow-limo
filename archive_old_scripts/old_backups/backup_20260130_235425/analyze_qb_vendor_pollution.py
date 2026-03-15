import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("QUICKBOOKS 'Cheque Expense' VENDOR NAME EXTRACTION")
print("="*80)

# Find all "Cheque Expense - [real vendor]" entries
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE 'Cheque Expense -%'
      AND exclude_from_reports = FALSE
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

qb_cheque_entries = cur.fetchall()

print(f"\nFound {len(qb_cheque_entries)} distinct 'Cheque Expense' patterns")
print(f"\nExtracting real vendor names:")
print("-"*80)

extractions = []
for vendor_name, count, amount in qb_cheque_entries:
    # Extract the part after "Cheque Expense - "
    if ' - ' in vendor_name:
        real_vendor = vendor_name.split(' - ', 1)[1].strip()
        extractions.append((real_vendor, vendor_name, count, amount))
        print(f"{count:>4} | ${float(amount):>10,.2f} | '{vendor_name}' → '{real_vendor}'")

total_count = sum(e[2] for e in extractions)
total_amount = sum(float(e[3]) if e[3] else 0 for e in extractions)

print(f"\n{'='*80}")
print(f"TOTAL: {total_count:,} receipts | ${total_amount:,.2f}")

# Check for vendor names with card numbers
print(f"\n{'='*80}")
print("VENDOR NAMES WITH CARD NUMBER FRAGMENTS:")
print("-"*80)

cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE '%4506*%'
      AND exclude_from_reports = FALSE
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

card_fragment_entries = cur.fetchall()
card_total = 0
card_amount = 0

for vendor_name, count, amount in card_fragment_entries:
    card_total += count
    card_amount += float(amount) if amount else 0
    # Extract the part before the card number
    clean_name = vendor_name.split('4506')[0].strip()
    print(f"{count:>4} | ${float(amount) if amount else 0:>10,.2f} | '{vendor_name}' → '{clean_name}'")

print(f"\nTOTAL: {card_total:,} receipts | ${card_amount:,.2f}")

# Check for FGP transaction codes
print(f"\n{'='*80}")
print("FGP TRANSACTION CODES (need merchant lookup):")
print("-"*80)

cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE 'FGP%'
      AND exclude_from_reports = FALSE
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

fgp_entries = cur.fetchall()
fgp_total = 0
fgp_amount = 0

for vendor_name, count, amount in fgp_entries:
    fgp_total += count
    fgp_amount += float(amount) if amount else 0
    # Extract the merchant code after FGP##### and before 4506
    parts = vendor_name.split()
    merchant_hint = parts[1] if len(parts) > 1 else ''
    print(f"{count:>4} | ${float(amount) if amount else 0:>10,.2f} | {vendor_name} → hint: '{merchant_hint}'")

print(f"\nTOTAL: {fgp_total:,} receipts | ${fgp_amount:,.2f}")

# Summary
print(f"\n{'='*80}")
print("SUMMARY OF FIXABLE VENDOR NAMES:")
print("="*80)

print(f"""
QuickBooks 'Cheque Expense' entries: {total_count:,} receipts | ${total_amount:,.2f}
  → Extract vendor name after ' - '

Card number fragments: {card_total:,} receipts | ${card_amount:,.2f}
  → Remove '4506*********534' suffix

FGP transaction codes: {fgp_total:,} receipts | ${fgp_amount:,.2f}
  → Need to cross-reference with banking descriptions

EMAIL TRANSFER (from earlier): 2,852 receipts | $1,211,523.36
  → Extract recipient from banking description

UNKNOWN PAYEE (CHEQUE): 272 receipts | $314,927.21
  → Extract from cheque reference or banking

TOTAL FIXABLE: ~{total_count + card_total + fgp_total + 2852 + 272:,} receipts
""")

cur.close()
conn.close()
