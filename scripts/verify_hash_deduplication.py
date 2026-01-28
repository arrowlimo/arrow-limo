import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("HASH-BASED DEDUPLICATION CHECK")
print("="*70)

# Check hash usage
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT source_hash) as unique_hashes,
        COUNT(DISTINCT duplicate_check_key) as unique_dup_keys
    FROM receipts 
    WHERE exclude_from_reports = FALSE
""")

total, hash_count, dup_key_count = cur.fetchone()

print(f"\nTotal receipts: {total:,}")
print(f"Unique source_hash values: {hash_count:,}")
print(f"Unique duplicate_check_key values: {dup_key_count:,}")

if hash_count:
    print(f"\nDuplicates by source_hash: {total - hash_count:,}")
else:
    print("\n❌ source_hash column is NULL (not being used!)")

if dup_key_count:
    print(f"Duplicates by duplicate_check_key: {total - dup_key_count:,}")
else:
    print("❌ duplicate_check_key column is NULL (not being used!)")

# Check for hash-based duplicates
cur.execute("""
    SELECT source_hash, COUNT(*), ARRAY_AGG(receipt_id ORDER BY receipt_id LIMIT 3) as sample_ids
    FROM receipts
    WHERE exclude_from_reports = FALSE 
      AND source_hash IS NOT NULL
    GROUP BY source_hash
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

hash_dups = cur.fetchall()

print(f"\n{'='*70}")
print(f"HASH-BASED DUPLICATES FOUND: {len(hash_dups)}")
print("="*70)

if hash_dups:
    print("\nTop 20 hash codes with multiple receipts:")
    for hash_val, count, sample_ids in hash_dups:
        print(f"\n  Hash: {hash_val[:16]}... ({count} copies)")
        print(f"  Sample Receipt IDs: {sample_ids}")
        
        # Get details of first 2 receipts
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
                   banking_transaction_id, receipt_source
            FROM receipts
            WHERE source_hash = %s
            ORDER BY receipt_id
            LIMIT 2
        """, (hash_val,))
        
        for rec in cur.fetchall():
            print(f"    ID {rec[0]}: {rec[1]} | {rec[2]} | ${rec[3]} | Banking:{rec[4]} | {rec[5]}")

# Compare banking_transaction_id matching vs hash matching
print(f"\n{'='*70}")
print("DEDUPLICATION STRATEGY COMPARISON")
print("="*70)

cur.execute("""
    SELECT COUNT(DISTINCT banking_transaction_id)
    FROM receipts
    WHERE banking_transaction_id IS NOT NULL
      AND exclude_from_reports = FALSE
""")
unique_banking_links = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE banking_transaction_id IS NOT NULL
      AND exclude_from_reports = FALSE
""")
receipts_with_banking = cur.fetchone()[0]

print(f"\nReceipts linked to banking: {receipts_with_banking:,}")
print(f"Unique banking transaction IDs: {unique_banking_links:,}")
print(f"One-to-one ratio: {receipts_with_banking/unique_banking_links if unique_banking_links else 'N/A':.2f}:1")

print("\n✅ CORRECT APPROACH:")
print("  - Use source_hash for import deduplication (prevent same source being imported twice)")
print("  - Use banking_transaction_id for one-to-one matching (one banking TX = one receipt)")
print("  - Each banking transaction should have banking_transaction_id linking")
print("\n❌ WRONG APPROACH:")
print("  - Matching on date/vendor/amount only (recurring payments look like duplicates)")
print("  - Multiple receipts per banking_transaction_id (import error)")

cur.close()
conn.close()
