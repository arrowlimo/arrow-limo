#!/usr/bin/env python3
"""
Check for duplicate expense receipts in 2012.
Look for same date, vendor, and amount which could indicate duplicates.
"""

import psycopg2
from collections import defaultdict

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
    
    print("="*80)
    print("CHECKING FOR DUPLICATE 2012 EXPENSES")
    print("="*80)
    
    # Find potential duplicates by (date, vendor, amount)
    cur.execute("""
        SELECT 
            receipt_date,
            COALESCE(vendor_name, 'Unknown') as vendor,
            gross_amount,
            COUNT(*) as duplicate_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            ARRAY_AGG(gl_account_code ORDER BY receipt_id) as gl_codes,
            ARRAY_AGG(COALESCE(description, '') ORDER BY receipt_id) as descriptions
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code IS NOT NULL
        GROUP BY receipt_date, COALESCE(vendor_name, 'Unknown'), gross_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, gross_amount DESC
    """)
    
    duplicates = cur.fetchall()
    
    if not duplicates:
        print("\n✓ No duplicates found - all receipts are unique")
        conn.close()
        return
    
    print(f"\nFound {len(duplicates)} potential duplicate groups")
    
    # Analyze duplicates
    total_duplicate_amount = 0
    total_duplicate_count = 0
    
    by_gl_code = defaultdict(lambda: {'count': 0, 'amount': 0})
    
    for dup in duplicates:
        date = dup[0]
        vendor = dup[1]
        amount = float(dup[2])
        count = dup[3]
        receipt_ids = dup[4]
        gl_codes = dup[5]
        descriptions = dup[6]
        
        # How many extra copies?
        extras = count - 1
        total_duplicate_count += extras
        total_duplicate_amount += amount * extras
        
        # Track by GL code
        for gl_code in set(gl_codes):
            by_gl_code[gl_code]['count'] += extras
            by_gl_code[gl_code]['amount'] += amount * extras
    
    print(f"\n{'='*80}")
    print(f"DUPLICATE SUMMARY")
    print(f"{'='*80}")
    print(f"Total duplicate receipts: {total_duplicate_count:,}")
    print(f"Total duplicate amount: ${total_duplicate_amount:,.2f}")
    
    print(f"\n{'='*80}")
    print(f"BY GL ACCOUNT")
    print(f"{'='*80}")
    
    for gl_code in sorted(by_gl_code.keys()):
        count = by_gl_code[gl_code]['count']
        amount = by_gl_code[gl_code]['amount']
        print(f"{gl_code}: {count:4d} duplicates = ${amount:12,.2f}")
    
    # Show top 20 duplicate groups
    print(f"\n{'='*80}")
    print(f"TOP 20 DUPLICATE GROUPS")
    print(f"{'='*80}")
    
    for i, dup in enumerate(duplicates[:20], 1):
        date = dup[0]
        vendor = dup[1][:40]
        amount = float(dup[2])
        count = dup[3]
        receipt_ids = dup[4]
        gl_codes = dup[5]
        descriptions = dup[6]
        
        print(f"\n{i}. {date} | {vendor:40s} | ${amount:10,.2f} x{count}")
        print(f"   Receipt IDs: {receipt_ids}")
        print(f"   GL Codes: {gl_codes}")
        if any(descriptions):
            print(f"   Descriptions: {[d[:60] for d in descriptions if d]}")
    
    # Check if these are truly duplicates or legitimate multiple transactions
    print(f"\n{'='*80}")
    print(f"DUPLICATE ANALYSIS")
    print(f"{'='*80}")
    
    # Same date/vendor/amount could be:
    # 1. True duplicates (import errors)
    # 2. Multiple legitimate transactions (e.g., multiple fuel stops same day)
    # 3. Split payments for same expense
    
    cur.execute("""
        SELECT 
            COUNT(*) as groups_with_diff_descriptions,
            SUM(CASE WHEN same_source THEN 1 ELSE 0 END) as same_source_hash
        FROM (
            SELECT 
                receipt_date,
                vendor_name,
                gross_amount,
                COUNT(DISTINCT COALESCE(description, '')) as desc_count,
                COUNT(DISTINCT COALESCE(source_hash, '')) > 1 as same_source
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND gl_account_code IS NOT NULL
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) x
    """)
    
    result = cur.fetchone()
    diff_desc = result[0] if result[0] else 0
    
    print(f"\nGroups with different descriptions: {diff_desc}")
    print(f"(These may be legitimate separate transactions)")
    
    # Check for exact duplicates via source_hash
    cur.execute("""
        SELECT 
            COUNT(*) as exact_duplicates
        FROM (
            SELECT source_hash
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND gl_account_code IS NOT NULL
            AND source_hash IS NOT NULL
            GROUP BY source_hash
            HAVING COUNT(*) > 1
        ) x
    """)
    
    exact_dups = cur.fetchone()[0]
    print(f"\nExact duplicates (same source_hash): {exact_dups}")
    print(f"(These are TRUE duplicates from import errors)")
    
    if exact_dups > 0:
        print(f"\n⚠️  WARNING: {exact_dups} exact duplicates detected!")
        print(f"These should be removed to avoid double-counting expenses.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
