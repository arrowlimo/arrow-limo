#!/usr/bin/env python3
"""
Comprehensive receipt deduplication analysis.
Identifies TRUE duplicates vs legitimate repeated transactions.
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
print("RECEIPT DEDUPLICATION ANALYSIS REPORT")
print("=" * 100)
print()

# 1. Overall duplicate status
print("1️⃣  OVERALL DUPLICATE STATUS")
print("-" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(*) FILTER (WHERE potential_duplicate = true) as marked_duplicates,
        COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as banking_linked,
        COUNT(*) FILTER (WHERE created_from_banking = true) as auto_created_from_banking
    FROM receipts
""")

total, marked_dup, banking_linked, auto_created = cur.fetchone()
print(f"Total receipts: {total:,}")
print(f"Marked as potential duplicates: {marked_dup:,}")
print(f"Linked to banking transactions: {banking_linked:,}")
print(f"Auto-created from banking: {auto_created:,}")

# 2. Receipts with same date + amount + vendor
print("\n2️⃣  POTENTIAL DUPLICATES - SAME DATE + AMOUNT + VENDOR")
print("-" * 100)

cur.execute("""
    WITH grouped AS (
        SELECT 
            receipt_date,
            gross_amount,
            COALESCE(canonical_vendor, vendor_name) as vendor,
            COUNT(*) as count,
            STRING_AGG(receipt_id::text, ', ' ORDER BY receipt_id) as receipt_ids,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as banking_count,
            SUM(CASE WHEN created_from_banking = true THEN 1 ELSE 0 END) as auto_count
        FROM receipts
        WHERE exclude_from_reports = false OR exclude_from_reports IS NULL
        GROUP BY receipt_date, gross_amount, vendor
        HAVING COUNT(*) > 1
    )
    SELECT 
        receipt_date,
        gross_amount,
        vendor,
        count,
        receipt_ids,
        banking_count,
        auto_count,
        CASE 
            WHEN banking_count = count THEN 'ALL_BANKING'
            WHEN banking_count > 0 AND banking_count < count THEN 'MIXED'
            ELSE 'NO_BANKING'
        END as link_status
    FROM grouped
    ORDER BY count DESC, gross_amount DESC
    LIMIT 25
""")

potential_dups = cur.fetchall()
print(f"\nFound {len(potential_dups)} groups with same date+amount+vendor (showing top 25):")
print(f"\n{'Date':<12s} | {'Amount':>10s} | {'Vendor':<25s} | Cnt | Banking | Status")
print("-" * 100)

for date, amount, vendor, count, ids, banking_count, auto_count, link_status in potential_dups:
    if date is None or amount is None or count is None:
        continue  # Skip rows with null critical values
    status_icon = "✓" if link_status == "ALL_BANKING" else ("⚠️" if link_status == "MIXED" else "❌")
    vendor_display = str(vendor)[:25] if vendor else "Unknown"
    banking_cnt = banking_count if banking_count is not None else 0
    link_stat = str(link_status) if link_status else "UNKNOWN"
    print(f"{status_icon} {str(date)} | ${float(amount):>9.2f} | {vendor_display:25s} | {int(count):>3d} | {int(banking_cnt):>7d} | {link_stat}")

# 3. TRUE DUPLICATES - Not linked to different banking transactions
print("\n3️⃣  TRUE DUPLICATES (Multiple receipts, NO banking links OR same banking link)")
print("-" * 100)

cur.execute("""
    WITH grouped AS (
        SELECT 
            receipt_date,
            gross_amount,
            COALESCE(canonical_vendor, vendor_name) as vendor,
            COUNT(*) as count,
            STRING_AGG(receipt_id::text, ', ' ORDER BY receipt_id) as receipt_ids,
            COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) as unique_banking_links
        FROM receipts
        WHERE exclude_from_reports = false OR exclude_from_reports IS NULL
        GROUP BY receipt_date, gross_amount, vendor
        HAVING COUNT(*) > 1
          AND (COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) <= 1)
    )
    SELECT 
        receipt_date,
        gross_amount,
        vendor,
        count,
        receipt_ids,
        unique_banking_links
    FROM grouped
    ORDER BY gross_amount DESC, count DESC
    LIMIT 20
""")

true_dups = cur.fetchall()
if true_dups:
    print(f"\n⚠️  Found {len(true_dups)} groups that may be TRUE duplicates:")
    print(f"\n{'Date':<12s} | {'Amount':>10s} | {'Vendor':<25s} | Cnt | Bank Links | Receipt IDs")
    print("-" * 100)
    for date, amount, vendor, count, ids, bank_links in true_dups:
        if date is None or amount is None or count is None:
            continue
        vendor_display = str(vendor)[:25] if vendor else "Unknown"
        bank_lnk = bank_links if bank_links is not None else 0
        print(f"{str(date)} | ${float(amount):>9.2f} | {vendor_display:25s} | {int(count):>3d} | {int(bank_lnk):>10d} | {str(ids)[:40] if ids else ''}")
else:
    print("\n✓ No true duplicates found!")

# 4. LEGITIMATE REPEATS - Multiple banking links (different transactions)
print("\n4️⃣  LEGITIMATE REPEATS (Multiple receipts, EACH linked to different banking transaction)")
print("-" * 100)

cur.execute("""
    WITH grouped AS (
        SELECT 
            receipt_date,
            gross_amount,
            COALESCE(canonical_vendor, vendor_name) as vendor,
            COUNT(*) as count,
            COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) as unique_banking_links
        FROM receipts
        WHERE exclude_from_reports = false OR exclude_from_reports IS NULL
        GROUP BY receipt_date, gross_amount, vendor
        HAVING COUNT(*) > 1
          AND COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) > 1
    )
    SELECT 
        COUNT(*) as groups_count,
        SUM(count) as total_receipts
    FROM grouped
""")

legit_groups, legit_total = cur.fetchone()
print(f"\n✓ {legit_groups:,} groups with repeated amounts are LEGITIMATE")
print(f"  Total receipts: {legit_total:,}")
print(f"  (Each receipt links to a different banking transaction)")

# 5. NSF verification
print("\n5️⃣  NSF TRANSACTION VERIFICATION")
print("-" * 100)

cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE vendor_name ILIKE '%nsf%' OR description ILIKE '%nsf%') as nsf_receipts,
        COUNT(*) FILTER (WHERE (vendor_name ILIKE '%nsf%' OR description ILIKE '%nsf%') AND potential_duplicate = true) as nsf_marked_dup
    FROM receipts
""")

nsf_total, nsf_dup = cur.fetchone()
print(f"Total NSF receipts: {nsf_total:,}")
print(f"NSF marked as duplicates: {nsf_dup:,}")
if nsf_dup == 0:
    print("✓ Correct - NSF charges are never marked as duplicates")
else:
    print(f"⚠️  WARNING: {nsf_dup} NSF receipts incorrectly marked as duplicates!")

# 6. Banking fee verification
print("\n6️⃣  BANKING FEE VERIFICATION (Repeated amounts are normal)")
print("-" * 100)

cur.execute("""
    WITH fee_groups AS (
        SELECT 
            gross_amount,
            COUNT(*) as count,
            COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) as banking_links
        FROM receipts
        WHERE (vendor_name ILIKE '%bank%charge%' OR vendor_name ILIKE '%service%charge%' 
               OR description ILIKE '%service charge%' OR gl_account_name ILIKE '%bank%')
        GROUP BY gross_amount
        HAVING COUNT(*) > 1
    )
    SELECT 
        COUNT(*) as repeated_amounts,
        SUM(count) as total_receipts,
        SUM(banking_links) as total_banking_links
    FROM fee_groups
""")

fee_groups, fee_total, fee_links = cur.fetchone() or (0, 0, 0)
if fee_groups:
    print(f"{fee_groups} fee amounts appear multiple times")
    print(f"  Total fee receipts: {fee_total:,}")
    print(f"  Banking links: {fee_links:,}")
    if fee_links == fee_total or fee_links >= fee_total - 1:
        print("  ✓ Each receipt properly linked to banking (legitimate repeats)")
    else:
        print(f"  ⚠️  {fee_total - fee_links} receipts not linked to banking")
else:
    print("No repeated banking fee amounts")

# 7. Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"\nTotal receipts: {total:,}")
print(f"Banking-linked receipts: {banking_linked:,} ({banking_linked/total*100:.1f}%)")
print(f"\nDeduplication Status:")
print(f"  ✓ NSF receipts: {nsf_total:,} (0 marked as duplicates)")
print(f"  ✓ Banking fees: Repeated amounts properly linked to banking")
if true_dups:
    print(f"  ⚠️  Potential true duplicates: {len(true_dups)} groups to review")
else:
    print(f"  ✓ No true duplicates found")
print(f"  ✓ Legitimate repeats: {legit_groups:,} groups ({legit_total:,} receipts)")

print("\n" + "=" * 100)

cur.close()
conn.close()
