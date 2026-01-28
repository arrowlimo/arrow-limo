#!/usr/bin/env python3
"""
Verify NSF transactions are NOT marked as duplicates and banking fee receipts
that match banking records are NOT duplicates.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 100)
print("NSF & BANKING FEE DEDUPLICATION VERIFICATION")
print("=" * 100)

# 1. Check NSF receipts linked to banking
print("\n1️⃣  NSF RECEIPTS - BANKING LINKAGE")
print("-" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_nsf,
        COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) as linked_to_banking,
        COUNT(*) FILTER (WHERE potential_duplicate = true) as marked_duplicate
    FROM receipts
    WHERE vendor_name ILIKE '%nsf%' OR description ILIKE '%nsf%'
""")

total_nsf, linked, marked_dup = cur.fetchone()
print(f"Total NSF receipts: {total_nsf:,}")
print(f"Linked to banking: {linked:,}")
print(f"Marked as duplicates: {marked_dup:,}")

if marked_dup > 0:
    print(f"\n⚠️  WARNING: {marked_dup} NSF receipts marked as potential duplicates!")
else:
    print(f"\n✓ No NSF receipts marked as duplicates")

# 2. Check for NSF receipts that match same date+amount
print("\n2️⃣  NSF RECEIPTS - SAME DATE + AMOUNT PATTERN")
print("-" * 100)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.gross_amount,
        COUNT(*) as count,
        STRING_AGG(r.receipt_id::text, ', ') as receipt_ids,
        STRING_AGG(DISTINCT CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'Banking' ELSE 'Manual' END, ', ') as sources
    FROM receipts r
    WHERE (r.vendor_name ILIKE '%nsf%' OR r.description ILIKE '%nsf%')
    GROUP BY r.receipt_date, r.gross_amount
    HAVING COUNT(*) > 1
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

nsf_groups = cur.fetchall()
if nsf_groups:
    print(f"\n⚠️  Found {len(nsf_groups)} date+amount combinations with multiple NSF receipts:")
    print(f"\n{'Date':<12s} | {'Amount':>10s} | Count | Receipt IDs | Sources")
    print("-" * 70)
    for date, amount, count, ids, sources in nsf_groups:
        print(f"{date} | ${amount:>9.2f} | {count:>5d} | {ids[:30]:30s} | {sources}")
else:
    print("\n✓ No NSF receipts share same date+amount")

# 3. Check banking fee receipts (SERVICE CHARGE, ACCOUNT FEE, etc.)
print("\n3️⃣  BANKING FEE RECEIPTS - MULTIPLE SAME AMOUNTS")
print("-" * 100)

cur.execute("""
    SELECT 
        r.gross_amount,
        COUNT(*) as total_count,
        COUNT(DISTINCT r.receipt_date) as unique_dates,
        COUNT(DISTINCT r.banking_transaction_id) FILTER (WHERE r.banking_transaction_id IS NOT NULL) as unique_banking,
        COUNT(*) FILTER (WHERE r.potential_duplicate = true) as marked_duplicate
    FROM receipts r
    WHERE (
        r.vendor_name ILIKE '%bank%charge%' 
        OR r.vendor_name ILIKE '%service%charge%'
        OR r.vendor_name ILIKE '%account%fee%'
        OR r.description ILIKE '%service charge%'
        OR r.description ILIKE '%monthly fee%'
        OR r.gl_account_name ILIKE '%bank%charge%'
    )
    GROUP BY r.gross_amount
    HAVING COUNT(*) > 1
    ORDER BY total_count DESC
    LIMIT 15
""")

fee_results = cur.fetchall()
if fee_results:
    print(f"\nBanking fees with repeated amounts:")
    print(f"\n{'Amount':>10s} | {'Total':>6s} | {'Dates':>6s} | {'Banking':>8s} | Marked Dup")
    print("-" * 60)
    for amount, total, dates, banking, marked_dup in fee_results:
        status = "⚠️ " if marked_dup > 0 else "✓ "
        print(f"{status}${amount:>9.2f} | {total:>6d} | {dates:>6d} | {banking:>8d} | {marked_dup:>10d}")
else:
    print("\n✓ No banking fees with repeated amounts")

# 4. Sample banking fee receipts to verify each is linked
print("\n4️⃣  SAMPLE BANKING FEE RECEIPTS (showing banking linkage)")
print("-" * 100)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.banking_transaction_id,
        bt.description as bank_description,
        r.potential_duplicate
    FROM receipts r
    LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
    WHERE (
        r.vendor_name ILIKE '%bank%charge%' 
        OR r.vendor_name ILIKE '%service%charge%'
        OR r.description ILIKE '%service charge%'
    )
    ORDER BY r.receipt_date DESC
    LIMIT 15
""")

print(f"\n{'Date':<12s} | {'Vendor':<25s} | {'Amount':>10s} | Bank ID | Bank Desc | Dup?")
print("-" * 100)
for date, vendor, amount, bank_id, bank_desc, is_dup in cur.fetchall():
    bank_id_str = str(bank_id) if bank_id else "None"
    dup_str = "DUP" if is_dup else "OK"
    bank_desc_str = (bank_desc[:25] if bank_desc else "N/A")
    print(f"{date} | {vendor[:25]:25s} | ${amount:>9.2f} | {bank_id_str:>7s} | {bank_desc_str:25s} | {dup_str}")

print("\n" + "=" * 100)

cur.close()
conn.close()
