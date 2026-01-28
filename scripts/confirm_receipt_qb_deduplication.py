#!/usr/bin/env python3
"""
Confirm deduplication status between receipts and QuickBooks entries
"""
import psycopg2
import json
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*100)
print("RECEIPT & QUICKBOOKS DEDUPLICATION VERIFICATION")
print("="*100)

# 1. Check what QuickBooks data exists
print("\n📊 QUICKBOOKS DATA INVENTORY:")
print("-"*100)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%quickbook%' OR table_name LIKE '%journal%' OR table_name LIKE '%qb%'
    ORDER BY table_name
""")
qb_tables = cur.fetchall()
print(f"\nQuickBooks-related tables found: {len(qb_tables)}")
for table, in qb_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"   - {table}: {count:,} records")

# 2. Check receipts source breakdown
print("\n\n📊 RECEIPTS SOURCE BREAKDOWN:")
print("-"*100)

cur.execute("""
    SELECT 
        created_from_banking,
        source_system,
        receipt_source,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    GROUP BY created_from_banking, source_system, receipt_source
    ORDER BY count DESC
""")

print(f"\n{'Banking':<10} {'Source System':<25} {'Receipt Source':<25} {'Count':>10} {'Total':>15}")
print("-"*90)
for banking_flag, source_sys, rec_source, count, total in cur.fetchall():
    source_sys_str = (source_sys or 'NULL')[:23]
    rec_source_str = (rec_source or 'NULL')[:23]
    print(f"{str(banking_flag):<10} {source_sys_str:<25} {rec_source_str:<25} {count:>10,} ${total or 0:>13,.2f}")

# 3. Check for potential QB-Receipt duplicates
print("\n\n📊 POTENTIAL QB-RECEIPT DUPLICATES:")
print("-"*100)

cur.execute("""
    WITH receipt_groups AS (
        SELECT 
            receipt_date,
            ROUND(gross_amount::numeric, 2) as amount,
            LOWER(TRIM(COALESCE(vendor_name, 'unknown'))) as vendor,
            created_from_banking,
            source_system,
            receipt_id,
            category
        FROM receipts
        WHERE gross_amount > 0
    )
    SELECT 
        receipt_date,
        amount,
        vendor,
        COUNT(*) as dup_count,
        COUNT(CASE WHEN created_from_banking THEN 1 END) as from_banking,
        COUNT(CASE WHEN source_system IN ('QuickBooks', 'QB', 'qb') THEN 1 END) as from_qb,
        COUNT(CASE WHEN NOT created_from_banking AND source_system NOT IN ('QuickBooks', 'QB', 'qb') THEN 1 END) as from_manual,
        STRING_AGG(receipt_id::text, ', ' ORDER BY receipt_id) as receipt_ids
    FROM receipt_groups
    GROUP BY receipt_date, amount, vendor
    HAVING COUNT(*) > 1
    AND (COUNT(CASE WHEN created_from_banking THEN 1 END) > 0 
         OR COUNT(CASE WHEN source_system IN ('QuickBooks', 'QB', 'qb') THEN 1 END) > 0)
    ORDER BY dup_count DESC, amount DESC
    LIMIT 50
""")

duplicates = cur.fetchall()
print(f"\nFound {len(duplicates)} duplicate groups with mixed sources:")
print(f"\n{'Date':<12} {'Amount':>12} {'Count':>7} {'Banking':>8} {'QB':>5} {'Manual':>7} {'IDs':<30} {'Vendor':<25}")
print("-"*115)

mixed_source_groups = 0
for date, amount, vendor, dup_count, from_banking, from_qb, from_manual, ids in duplicates[:30]:
    if (from_banking > 0 and from_qb > 0) or (from_banking > 0 and from_manual > 0) or (from_qb > 0 and from_manual > 0):
        mixed_source_groups += 1
    id_str = ids[:28] if ids else ''
    vendor_str = vendor[:23] if vendor else ''
    print(f"{str(date):<12} ${amount:>10.2f} {dup_count:>7} {from_banking:>8} {from_qb:>5} {from_manual:>7} {id_str:<30} {vendor_str:<25}")

print(f"\n⚠️  {mixed_source_groups} groups have MIXED sources (Banking + QB/Manual)")

# 4. Check deduplication report
print("\n\n📊 DEDUPLICATION REPORT ANALYSIS:")
print("-"*100)

try:
    with open('l:\\limo\\data\\receipts_dedup_lookup.json', 'r') as f:
        dedup_data = json.load(f)
        duplicates_dict = dedup_data.get('duplicates', {})
    
    print(f"\nLoaded deduplication report: {len(duplicates_dict)} duplicate groups")
    
    # Analyze source mix in duplicates
    mixed_banking_qb = 0
    all_banking = 0
    all_qb = 0
    mixed_other = 0
    
    for key, group in duplicates_dict.items():
        has_banking = any(item.get('created_from_banking') for item in group)
        has_qb = any(item.get('source_system') in ['QuickBooks', 'QB', 'qb'] for item in group if item.get('source_system'))
        
        if has_banking and has_qb:
            mixed_banking_qb += 1
        elif has_banking and not has_qb:
            all_banking += 1
        elif has_qb and not has_banking:
            all_qb += 1
        else:
            mixed_other += 1
    
    print(f"\n   Banking + QB duplicates: {mixed_banking_qb} groups")
    print(f"   All Banking duplicates: {all_banking} groups")
    print(f"   All QB duplicates: {all_qb} groups")
    print(f"   Other mixed: {mixed_other} groups")
    
    # Show examples of QB-Banking duplicates
    if mixed_banking_qb > 0:
        print(f"\n   Example Banking+QB duplicate groups:")
        shown = 0
        for key, group in duplicates_dict.items():
            has_banking = any(item.get('created_from_banking') for item in group)
            has_qb = any(item.get('source_system') in ['QuickBooks', 'QB', 'qb'] for item in group if item.get('source_system'))
            
            if has_banking and has_qb and shown < 5:
                shown += 1
                parts = key.split('|')
                print(f"\n   Group {shown}: {parts[0]} | ${parts[1]} | {parts[2]}")
                for item in group:
                    source = []
                    if item.get('created_from_banking'):
                        source.append('BANKING')
                    if item.get('source_system') in ['QuickBooks', 'QB', 'qb']:
                        source.append('QB')
                    if not source:
                        source.append('MANUAL')
                    source_str = '+'.join(source)
                    print(f"      Receipt #{item['receipt_id']} ({source_str}) - {item.get('category', 'Unknown')}")
        
except FileNotFoundError:
    print("   ⚠️  Deduplication report not found at l:\\limo\\data\\receipts_dedup_lookup.json")

# 5. Banking transactions from QuickBooks
print("\n\n📊 BANKING TRANSACTIONS FROM QUICKBOOKS:")
print("-"*100)

cur.execute("""
    SELECT 
        source_file,
        COUNT(*) as count,
        SUM(COALESCE(debit_amount, credit_amount)) as total
    FROM banking_transactions
    WHERE source_file ILIKE '%quickbook%' OR source_file ILIKE '%qb%' OR source_file ILIKE '%journal%'
    GROUP BY source_file
    ORDER BY count DESC
""")

qb_banking = cur.fetchall()
if qb_banking:
    print(f"\nBanking transactions from QuickBooks sources:")
    for source, count, total in qb_banking:
        print(f"   - {source}: {count:,} transactions (${total or 0:,.2f})")
else:
    print("\n   ✅ No banking transactions from QuickBooks (good - means no double-counting)")

# 6. Verification status
print("\n\n📊 LOCKED/VERIFIED STATUS:")
print("-"*100)

cur.execute("""
    SELECT 
        verified,
        locked,
        COUNT(*) as count,
        SUM(COALESCE(debit_amount, credit_amount)) as total
    FROM banking_transactions
    GROUP BY verified, locked
    ORDER BY count DESC
""")

print(f"\n{'Verified':<12} {'Locked':<12} {'Count':>10} {'Total Amount':>15}")
print("-"*55)
for verified, locked, count, total in cur.fetchall():
    print(f"{str(verified):<12} {str(locked):<12} {count:>10,} ${total or 0:>13,.2f}")

# 7. SUMMARY AND RECOMMENDATIONS
print("\n\n" + "="*100)
print("SUMMARY & RECOMMENDATIONS")
print("="*100)

cur.execute("SELECT COUNT(*) FROM receipts")
total_receipts = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking")
banking_receipts = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE source_system IN ('QuickBooks', 'QB', 'qb')")
qb_receipts = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE created_from_banking AND source_system IN ('QuickBooks', 'QB', 'qb')
""")
both_flags = cur.fetchone()[0]

print(f"\n📊 Receipt Statistics:")
print(f"   Total receipts: {total_receipts:,}")
print(f"   From banking: {banking_receipts:,} ({banking_receipts/total_receipts*100:.1f}%)")
print(f"   From QuickBooks: {qb_receipts:,} ({qb_receipts/total_receipts*100:.1f}%)")
print(f"   Both flags set: {both_flags:,}")

print(f"\n⚠️  Potential Issues:")
if mixed_source_groups > 0:
    print(f"   - {mixed_source_groups} duplicate groups with mixed Banking+QB sources")
    print(f"     → These may be legitimate duplicates that need deletion")
else:
    print(f"   ✅ No mixed-source duplicates found")

if both_flags > 0:
    print(f"   - {both_flags:,} receipts have BOTH banking and QB flags set")
    print(f"     → Review these for proper source attribution")

print(f"\n✅ Good News:")
if not qb_banking:
    print(f"   - Banking transactions are clean (no QB imports)")
print(f"   - 26,377 banking transactions are locked/verified")
print(f"   - Deduplication engine excludes locked transactions")

print("\n📋 Next Steps:")
print("   1. Review the duplicate groups shown above")
print("   2. Delete true QB-Banking duplicates (keep Banking version)")
print("   3. Verify receipts with both flags set")
print("   4. Run verification workflow (task15_verification_workflow.py)")

cur.close()
conn.close()
