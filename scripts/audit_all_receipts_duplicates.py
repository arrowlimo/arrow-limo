"""
Comprehensive audit of ALL receipts for duplication patterns.
Analyzes duplicates across all years (2007-2025).
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("COMPREHENSIVE RECEIPTS DUPLICATION AUDIT - ALL YEARS")
    print("=" * 100)
    
    # 1. Overall stats
    cur.execute('SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date), SUM(gross_amount) FROM receipts')
    total, min_date, max_date, total_amount = cur.fetchone()
    print(f'\n📊 OVERVIEW:')
    print(f'   Total receipts: {total:,}')
    print(f'   Date range: {min_date} to {max_date}')
    print(f'   Total amount: ${total_amount:,.2f}')
    
    # 2. Exact duplicates (date + vendor + amount)
    print(f'\n{"=" * 100}')
    print('🔴 PATTERN 1: Exact Duplicates (same date + vendor + amount)')
    print("=" * 100)
    
    cur.execute('''
        SELECT 
            EXTRACT(YEAR FROM receipt_date)::int as year,
            COUNT(*) as dup_groups,
            SUM(cnt - 1) as extra_receipts,
            SUM((cnt - 1) * amount) as duplicate_amount
        FROM (
            SELECT receipt_date, vendor_name, gross_amount as amount, COUNT(*) as cnt
            FROM receipts
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) x
        GROUP BY year
        ORDER BY year
    ''')
    
    year_dups = cur.fetchall()
    total_dup_groups = sum(row[1] for row in year_dups)
    total_extra = sum(row[2] for row in year_dups)
    total_dup_amount = sum(row[3] for row in year_dups if row[3])
    
    print(f'\n   Total duplicate groups: {total_dup_groups:,}')
    print(f'   Total extra receipts: {total_extra:,}')
    print(f'   Duplicate amount: ${total_dup_amount:,.2f}')
    print(f'   Percentage of total: {(total_extra/total)*100:.2f}%')
    
    print(f'\n   By year:')
    for row in year_dups:
        year = row[0]
        dup_pct = (row[2] / total) * 100
        print(f'     {year}: {row[1]:4} groups | {row[2]:4} extra receipts ({dup_pct:.2f}%) | ${row[3]:>12,.2f}')
    
    # 3. Top vendors with duplicates
    print(f'\n{"=" * 100}')
    print('🔴 TOP 20 VENDORS WITH MOST DUPLICATE RECEIPTS')
    print("=" * 100)
    
    cur.execute('''
        SELECT vendor_name, COUNT(*) as dup_groups, SUM(cnt - 1) as extra_receipts,
               SUM((cnt - 1) * amount) as dup_amount
        FROM (
            SELECT vendor_name, receipt_date, gross_amount as amount, COUNT(*) as cnt
            FROM receipts
            GROUP BY vendor_name, receipt_date, gross_amount
            HAVING COUNT(*) > 1
        ) x
        GROUP BY vendor_name
        ORDER BY SUM(cnt - 1) DESC
        LIMIT 20
    ''')
    
    print(f'\n   Vendor                                          | Groups | Extra | Dup Amount')
    print(f'   {"-" * 95}')
    for row in cur.fetchall():
        vendor = (row[0][:45] if row[0] else 'None').ljust(45)
        print(f'   {vendor} | {row[1]:6} | {row[2]:5} | ${row[3]:>12,.2f}')
    
    # 4. Largest duplicate amounts
    print(f'\n{"=" * 100}')
    print('🔴 TOP 15 LARGEST DUPLICATE AMOUNTS')
    print("=" * 100)
    
    cur.execute('''
        SELECT receipt_date, vendor_name, gross_amount, COUNT(*) as cnt,
               ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
        FROM receipts
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY gross_amount DESC, COUNT(*) DESC
        LIMIT 15
    ''')
    
    print(f'\n   Date       | Vendor                                    | Amount      | Cnt | IDs')
    print(f'   {"-" * 95}')
    for row in cur.fetchall():
        date = str(row[0])
        vendor = (row[1][:40] if row[1] else 'None').ljust(40)
        ids_str = str(row[4][:3])[:-1] + ',...]' if len(row[4]) > 3 else str(row[4])
        print(f'   {date} | {vendor} | ${row[2]:>10,.2f} | {row[3]:3} | {ids_str}')
    
    # 5. Analyze bank fee duplicates specifically
    print(f'\n{"=" * 100}')
    print('🔴 BANK FEE DUPLICATES (Branch Transaction pattern)')
    print("=" * 100)
    
    cur.execute('''
        SELECT 
            vendor_name,
            COUNT(*) as dup_groups,
            SUM(cnt - 1) as extra_receipts
        FROM (
            SELECT vendor_name, receipt_date, gross_amount, COUNT(*) as cnt
            FROM receipts
            WHERE vendor_name LIKE 'Branch Transaction%'
            GROUP BY vendor_name, receipt_date, gross_amount
            HAVING COUNT(*) > 1
        ) x
        GROUP BY vendor_name
        ORDER BY SUM(cnt - 1) DESC
    ''')
    
    bank_fee_dups = cur.fetchall()
    total_bank_fee_dups = sum(row[2] for row in bank_fee_dups)
    
    print(f'\n   Total bank fee duplicates: {total_bank_fee_dups}')
    print(f'\n   Fee Type                                        | Groups | Extra')
    print(f'   {"-" * 75}')
    for row in bank_fee_dups:
        fee_type = row[0].replace('Branch Transaction ', '')[:45].ljust(45)
        print(f'   {fee_type} | {row[1]:6} | {row[2]:5}')
    
    # 6. David Richard loans analysis
    print(f'\n{"=" * 100}')
    print('🔴 DAVID RICHARD LOAN DUPLICATES')
    print("=" * 100)
    
    cur.execute('''
        SELECT receipt_date, gross_amount, COUNT(*) as cnt,
               ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
        FROM receipts
        WHERE vendor_name = 'David Richard'
        GROUP BY receipt_date, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY receipt_date
    ''')
    
    david_dups = cur.fetchall()
    print(f'\n   David Richard duplicate groups: {len(david_dups)}')
    if david_dups:
        print(f'\n   Date       | Amount      | Count | Receipt IDs')
        print(f'   {"-" * 70}')
        for row in david_dups:
            print(f'   {row[0]} | ${row[1]:>10,.2f} | {row[2]:5} | {row[3]}')
    
    # 7. Cheque duplicates
    print(f'\n{"=" * 100}')
    print('🔴 CHEQUE DUPLICATES')
    print("=" * 100)
    
    cur.execute('''
        SELECT receipt_date, vendor_name, gross_amount, COUNT(*) as cnt,
               ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
        FROM receipts
        WHERE vendor_name LIKE 'CHEQUE%' OR vendor_name LIKE 'Cheque%'
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY gross_amount DESC
    ''')
    
    cheque_dups = cur.fetchall()
    print(f'\n   Cheque duplicate groups: {len(cheque_dups)}')
    if cheque_dups:
        print(f'\n   Date       | Cheque Number                             | Amount      | Cnt')
        print(f'   {"-" * 85}')
        for row in cheque_dups[:10]:
            vendor = (row[1][:40] if row[1] else 'None').ljust(40)
            print(f'   {row[0]} | {vendor} | ${row[2]:>10,.2f} | {row[3]:3}')
    
    # 8. Summary by year with duplicate percentage
    print(f'\n{"=" * 100}')
    print('📊 RECEIPTS SUMMARY BY YEAR (with duplication rate)')
    print("=" * 100)
    
    cur.execute('''
        WITH year_totals AS (
            SELECT 
                EXTRACT(YEAR FROM receipt_date)::int as year,
                COUNT(*) as total_receipts,
                SUM(gross_amount) as total_amount
            FROM receipts
            GROUP BY year
        ),
        year_dups AS (
            SELECT 
                EXTRACT(YEAR FROM receipt_date)::int as year,
                SUM(cnt - 1) as dup_count
            FROM (
                SELECT receipt_date, COUNT(*) as cnt
                FROM receipts
                GROUP BY receipt_date, vendor_name, gross_amount
                HAVING COUNT(*) > 1
            ) x
            GROUP BY year
        )
        SELECT 
            yt.year,
            yt.total_receipts,
            yt.total_amount,
            COALESCE(yd.dup_count, 0) as duplicates,
            CASE WHEN yt.total_receipts > 0 
                 THEN (COALESCE(yd.dup_count, 0)::float / yt.total_receipts * 100)
                 ELSE 0 
            END as dup_pct
        FROM year_totals yt
        LEFT JOIN year_dups yd ON yt.year = yd.year
        ORDER BY yt.year
    ''')
    
    print(f'\n   Year | Total Receipts | Total Amount      | Duplicates | Dup %')
    print(f'   {"-" * 85}')
    for row in cur.fetchall():
        year = row[0]
        print(f'   {year} | {row[1]:>14,} | ${row[2]:>15,.2f} | {row[3]:>10} | {row[4]:>5.2f}%')
    
    # 9. Recommendations
    print(f'\n{"=" * 100}')
    print('📋 RECOMMENDATIONS')
    print("=" * 100)
    
    print(f'\n   1. Bank Fee Duplicates: {total_bank_fee_dups} receipts')
    print(f'      → Likely from dual import sources (QuickBooks + banking CSV)')
    print(f'      → Keep oldest receipt (lowest ID), delete duplicates')
    
    print(f'\n   2. David Richard Loans: {len(david_dups)} duplicate groups')
    print(f'      → Manual review needed - may be legitimate separate transactions')
    
    print(f'\n   3. Cheque Duplicates: {len(cheque_dups)} groups')
    print(f'      → Verify against bank statements before deleting')
    
    print(f'\n   4. 2025 Data: See separate 2025_RECEIPTS_DUPLICATION_REPORT.md')
    print(f'      → Misdated 2025-10-17 batch needs immediate cleanup')
    
    # 10. Hash-based check
    print(f'\n{"=" * 100}')
    print('✓ HASH DUPLICATE CHECK')
    print("=" * 100)
    
    cur.execute('''
        SELECT COUNT(*) as groups, SUM(cnt - 1) as extra
        FROM (
            SELECT source_hash, COUNT(*) as cnt
            FROM receipts
            WHERE source_hash IS NOT NULL
            GROUP BY source_hash
            HAVING COUNT(*) > 1
        ) x
    ''')
    
    hash_groups, hash_extra = cur.fetchone()
    print(f'\n   Hash duplicate groups: {hash_groups if hash_groups else 0:,}')
    print(f'   Extra hash duplicates: {hash_extra if hash_extra else 0:,}')
    
    if hash_groups and hash_groups > 0:
        print(f'\n   ⚠️  WARNING: Found {hash_groups} receipts with duplicate source hashes!')
    else:
        print(f'\n   ✓ No hash duplicates - source_hash field is working correctly')
    
    cur.close()
    conn.close()
    
    print(f'\n{"=" * 100}')
    print(f'AUDIT COMPLETE - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print("=" * 100)

if __name__ == '__main__':
    main()
