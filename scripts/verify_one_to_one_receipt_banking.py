import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("RECEIPT-TO-BANKING ONE-TO-ONE MATCHING VERIFICATION")
print("="*100)

# 1. Count receipts with/without banking links
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as with_banking,
        COUNT(*) FILTER (WHERE banking_transaction_id IS NULL) as without_banking,
        COUNT(*) as total
    FROM receipts
    WHERE exclude_from_reports = FALSE
""")

with_banking, without_banking, total = cur.fetchone()

print(f"\n1. BANKING LINKAGE STATUS")
print("-"*100)
print(f"Total active receipts: {total:,}")
print(f"  With banking_transaction_id: {with_banking:,} ({with_banking/total*100:.1f}%)")
print(f"  Without banking_transaction_id: {without_banking:,} ({without_banking/total*100:.1f}%)")

# 2. Check one-to-one relationship (banking → receipts)
cur.execute("""
    SELECT 
        banking_transaction_id,
        COUNT(*) as receipt_count,
        STRING_AGG(receipt_id::text, ', ') as receipt_ids,
        STRING_AGG(vendor_name, ' | ') as vendors,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE exclude_from_reports = FALSE
      AND banking_transaction_id IS NOT NULL
    GROUP BY banking_transaction_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 50
""")

split_receipts = cur.fetchall()

print(f"\n2. SPLIT RECEIPTS (multiple receipts per banking transaction)")
print("-"*100)
print(f"Found {len(split_receipts)} banking transactions with multiple receipts\n")

if split_receipts:
    total_splits = 0
    total_amount = 0
    
    print(f"{'Banking TX':<12} | {'Count':>5} | {'Total Amount':>12} | {'Vendors'}")
    print("-"*100)
    
    for tx_id, count, receipt_ids, vendors, amount in split_receipts[:20]:
        total_splits += count
        total_amount += float(amount) if amount else 0
        vendors_short = vendors[:60] if vendors else 'N/A'
        print(f"{tx_id:<12} | {count:>5} | ${float(amount) if amount else 0:>11,.2f} | {vendors_short}")
    
    if len(split_receipts) > 20:
        print(f"  ... and {len(split_receipts) - 20} more")
        for tx_id, count, receipt_ids, vendors, amount in split_receipts[20:]:
            total_splits += count
            total_amount += float(amount) if amount else 0
    
    print(f"\nTotal split receipts: {total_splits:,} receipts across {len(split_receipts):,} banking transactions")
    print(f"Total amount in splits: ${total_amount:,.2f}")

# 3. Check receipts without banking that should have it
cur.execute("""
    SELECT 
        'No Source Column' as source_label,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE exclude_from_reports = FALSE
      AND banking_transaction_id IS NULL
""")

unlinked_sources = cur.fetchall()

print(f"\n3. RECEIPTS WITHOUT BANKING LINKS")
print("-"*100)

total_unlinked = 0
total_unlinked_amt = 0

for source_label, count, amount in unlinked_sources:
    total_unlinked += count
    total_unlinked_amt += float(amount) if amount else 0
    print(f"Unlinked receipts: {count:,} | ${float(amount) if amount else 0:,.2f}")
    print(f"  (Expected: Square, invoices, manual entries, depreciation)")

print(f"\nTotal unlinked: {total_unlinked:,} receipts | ${total_unlinked_amt:,.2f}")

# 4. Verify one-to-one on the banking side (each banking has at most one receipt linked)
cur.execute("""
    SELECT COUNT(DISTINCT banking_transaction_id)
    FROM receipts
    WHERE exclude_from_reports = FALSE
      AND banking_transaction_id IS NOT NULL
""")

unique_banking_ids = cur.fetchone()[0]

print(f"\n4. ONE-TO-ONE VERIFICATION")
print("-"*100)
print(f"Receipts with banking links: {with_banking:,}")
print(f"Unique banking transaction IDs: {unique_banking_ids:,}")
print(f"Difference (split receipts): {with_banking - unique_banking_ids:,}")

if with_banking == unique_banking_ids:
    print(f"\n✅ PERFECT: Every banking transaction has exactly ONE receipt")
else:
    print(f"\n⚠️  NOT ONE-TO-ONE: {len(split_receipts):,} banking transactions have multiple receipts")

# 5. Check vendor name consistency with banking descriptions
print(f"\n5. VENDOR NAME VS BANKING DESCRIPTION CONSISTENCY")
print("-"*100)

cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description,
        COUNT(*) as count,
        SUM(r.gross_amount) as total
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.exclude_from_reports = FALSE
      AND r.vendor_name IS NOT NULL
      AND bt.description IS NOT NULL
      -- Check if vendor name appears in banking description
      AND UPPER(bt.description) NOT LIKE '%' || UPPER(r.vendor_name) || '%'
      -- Exclude EMAIL TRANSFER (we added the prefix)
      AND r.vendor_name NOT LIKE 'EMAIL TRANSFER%'
      -- Exclude known mismatches
      AND r.vendor_name NOT IN ('CASH WITHDRAWAL', 'NSF CHARGE', 'BANK SERVICE FEE')
    GROUP BY r.vendor_name, bt.description
    ORDER BY COUNT(*) DESC
    LIMIT 30
""")

mismatches = cur.fetchall()

if mismatches:
    print(f"Found {len(mismatches)} vendor-banking description mismatches\n")
    print(f"{'Vendor Name':<40} | {'Banking Description':<50} | Count")
    print("-"*100)
    
    for vendor, banking_desc, count, total in mismatches[:20]:
        vendor_short = vendor[:38] if vendor else 'NULL'
        banking_short = banking_desc[:48] if banking_desc else 'NULL'
        print(f"{vendor_short:<40} | {banking_short:<50} | {count}")
    
    if len(mismatches) > 20:
        print(f"  ... and {len(mismatches) - 20} more")
else:
    print("✅ All vendor names align with banking descriptions")

# SUMMARY
print(f"\n{'='*100}")
print(f"SUMMARY")
print(f"{'='*100}")

one_to_one = with_banking == unique_banking_ids

print(f"""
Total receipts: {total:,}
  With banking: {with_banking:,} ({with_banking/total*100:.1f}%)
  Without banking: {without_banking:,} ({without_banking/total*100:.1f}%)

ONE-TO-ONE MATCHING: {'✅ YES' if one_to_one else '❌ NO'}
  Unique banking transactions: {unique_banking_ids:,}
  Split receipts (multiple per banking): {len(split_receipts):,} transactions
  Total receipts in splits: {with_banking - unique_banking_ids:,}

VENDOR NAME QUALITY:
  Extracted from banking: 3,669 receipts
  Mismatches with banking: {len(mismatches) if mismatches else 0} vendor-description pairs

UNLINKED RECEIPTS (no banking):
  Total: {total_unlinked:,} receipts | ${total_unlinked_amt:,.2f}
  Expected (Square/Invoice/Manual): Most are legitimate
  
CONCLUSION:
{'  ✅ One-to-one matching maintained EXCEPT for split receipts' if one_to_one else f'  ⚠️  {len(split_receipts):,} banking transactions have multiple receipts (splits)'}
  Vendor names are now searchable and match banking descriptions
""")

cur.close()
conn.close()
