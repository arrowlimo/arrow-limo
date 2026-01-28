import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("HASH DEDUPLICATION ANALYSIS")
print("="*70)

# Check AUTO_GENERATED hashes
cur.execute("""
    SELECT receipt_source, COUNT(*) 
    FROM receipts 
    WHERE source_hash LIKE 'AUTO_GENERATED%' 
      AND exclude_from_reports = FALSE
    GROUP BY receipt_source 
    ORDER BY COUNT(*) DESC
""")

print("\nReceipts with AUTO_GENERATED hash (not properly hashed):")
for src, cnt in cur.fetchall():
    print(f"  {src if src else 'NULL'}: {cnt:,}")

# Get total
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE source_hash LIKE 'AUTO_GENERATED%'
      AND exclude_from_reports = FALSE
""")
auto_gen_total = cur.fetchone()[0]

# Get properly hashed
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE source_hash NOT LIKE 'AUTO_GENERATED%'
      AND exclude_from_reports = FALSE
""")
properly_hashed = cur.fetchone()[0]

print(f"\n{'='*70}")
print(f"AUTO_GENERATED (not hashed): {auto_gen_total:,}")
print(f"Properly hashed: {properly_hashed:,}")
print(f"Total: {auto_gen_total + properly_hashed:,}")

# Check for hash-based duplicates in properly hashed receipts
cur.execute("""
    SELECT source_hash, COUNT(*), 
           (ARRAY_AGG(receipt_id ORDER BY receipt_id))[1:3] as ids,
           ARRAY_AGG(DISTINCT receipt_source) as sources
    FROM receipts
    WHERE exclude_from_reports = FALSE 
      AND source_hash NOT LIKE 'AUTO_GENERATED%'
    GROUP BY source_hash
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")

hash_dups = cur.fetchall()

print(f"\n{'='*70}")
print(f"REAL HASH DUPLICATES (same source imported twice): {len(hash_dups)}")
print("="*70)

if hash_dups:
    total_dup_inflation = 0
    for hash_val, count, ids, sources in hash_dups:
        print(f"\nHash {hash_val[:20]}... ({count} copies)")
        print(f"  Receipt IDs: {ids}")
        print(f"  Sources: {sources}")
        
        # Get first receipt details
        cur.execute("""
            SELECT receipt_date, vendor_name, gross_amount
            FROM receipts
            WHERE receipt_id = %s
        """, (ids[0],))
        
        date, vendor, amount = cur.fetchone()
        print(f"  {date} | {vendor} | ${amount}")
        
        total_dup_inflation += float(amount) * (count - 1)
    
    print(f"\nTotal inflation from hash duplicates: ${total_dup_inflation:,.2f}")
else:
    print("\n✅ No hash duplicates found in properly hashed receipts")

print(f"\n{'='*70}")
print("RECOMMENDATION:")
print("="*70)
print("""
✅ USE THIS STRATEGY:

1. HASH-BASED DEDUPLICATION (source_hash):
   - Prevents same source data from being imported twice
   - Should be calculated as SHA256(date + vendor + amount + source)
   - AUTO_GENERATED means hash wasn't calculated (import error)

2. BANKING_TRANSACTION_ID ONE-TO-ONE:
   - Each banking transaction should link to EXACTLY ONE receipt
   - We just fixed this (deleted 355 duplicates)

3. UNLINKED RECEIPTS (no banking_transaction_id):
   - Square payments (aggregated in banking, individual TXs in receipts)
   - Cash expenses (no banking record)
   - Depreciation (calculated, not a real transaction)
   - Invoices/bills (not yet paid)

❌ DON'T USE:
   - Matching only on date/vendor/amount (recurring payments look duplicate)
""")

cur.close()
conn.close()
