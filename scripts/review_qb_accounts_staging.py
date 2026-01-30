#!/usr/bin/env python3
"""
Review qb_accounts_staging to understand why 298 rows have zero overlap with qb_accounts (101 rows).
Determine if these should be merged into chart_of_accounts.
"""

import psycopg2
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("QB ACCOUNTS STAGING ANALYSIS")
    print("="*80)
    
    # 1. Compare schemas
    print("\n1. SCHEMA COMPARISON")
    print("-"*80)
    
    print("\nqb_accounts_staging columns:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'qb_accounts_staging' 
        ORDER BY ordinal_position
    """)
    staging_cols = cur.fetchall()
    for col, dtype in staging_cols:
        print(f"  • {col}: {dtype}")
    
    print("\nqb_accounts columns:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'qb_accounts' 
        ORDER BY ordinal_position
    """)
    qb_cols = cur.fetchall()
    for col, dtype in qb_cols:
        print(f"  • {col}: {dtype}")
    
    # 2. Count unique accounts
    print("\n\n2. UNIQUE ACCOUNT COUNTS")
    print("-"*80)
    
    cur.execute("SELECT COUNT(DISTINCT qb_serial_no) FROM qb_accounts_staging WHERE qb_serial_no IS NOT NULL")
    staging_unique = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT qb_account_number) FROM qb_accounts WHERE qb_account_number IS NOT NULL")
    qb_unique = cur.fetchone()[0]
    
    print(f"\nqb_accounts_staging unique accounts: {staging_unique}")
    print(f"qb_accounts unique accounts: {qb_unique}")
    print(f"Difference: {staging_unique - qb_unique}")
    
    # 3. Sample data from staging
    print("\n\n3. SAMPLE DATA FROM STAGING (First 20)")
    print("-"*80)
    
    cur.execute("""
        SELECT qb_serial_no, qb_name, qb_account_type, qb_account_number
        FROM qb_accounts_staging 
        WHERE qb_serial_no IS NOT NULL
        ORDER BY qb_serial_no::integer
        LIMIT 20
    """)
    
    print(f"\n{'Serial':<10} {'Name':<40} {'Type':<20} {'Number':<10}")
    print("-"*80)
    for row in cur.fetchall():
        serial, name, atype, number = row
        name_short = (name[:37] + '...') if name and len(name) > 40 else (name or '')
        print(f"{serial:<10} {name_short:<40} {atype or '':<20} {number or '':<10}")
    
    # 4. Check for matches with qb_accounts
    print("\n\n4. MATCHING ANALYSIS")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN qa.qb_account_number IS NOT NULL THEN 1 END) as matched_by_number,
            COUNT(CASE WHEN qa2.qb_name IS NOT NULL THEN 1 END) as matched_by_name
        FROM qb_accounts_staging qs
        LEFT JOIN qb_accounts qa ON qa.qb_account_number::text = qs.qb_serial_no::text
        LEFT JOIN qb_accounts qa2 ON LOWER(qa2.qb_name) = LOWER(qs.qb_name)
    """)
    
    total, by_number, by_name = cur.fetchone()
    print(f"\nTotal staging rows: {total}")
    print(f"Matched by serial/account number: {by_number}")
    print(f"Matched by account name: {by_name}")
    print(f"Unmatched: {total - max(by_number, by_name)}")
    
    # 5. Check for matches with chart_of_accounts
    print("\n\n5. MATCH WITH CHART_OF_ACCOUNTS")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN coa.account_code IS NOT NULL THEN 1 END) as matched
        FROM qb_accounts_staging qs
        LEFT JOIN chart_of_accounts coa ON 
            LOWER(coa.account_name) = LOWER(qs.qb_name)
            OR coa.account_code = qs.qb_account_number
    """)
    
    total, matched = cur.fetchone()
    print(f"\nTotal staging rows: {total}")
    print(f"Matched in chart_of_accounts: {matched}")
    print(f"Not in chart: {total - matched}")
    
    # 6. Show unmatched accounts
    print("\n\n6. ACCOUNTS NOT IN CHART_OF_ACCOUNTS (Sample 15)")
    print("-"*80)
    
    cur.execute("""
        SELECT qs.qb_serial_no, qs.qb_name, qs.qb_account_type
        FROM qb_accounts_staging qs
        LEFT JOIN chart_of_accounts coa ON 
            LOWER(coa.account_name) = LOWER(qs.qb_name)
        WHERE coa.account_code IS NULL
        AND qs.qb_name IS NOT NULL
        ORDER BY qs.qb_serial_no::integer
        LIMIT 15
    """)
    
    print(f"\n{'Serial':<10} {'Name':<45} {'Type':<20}")
    print("-"*80)
    for row in cur.fetchall():
        serial, name, atype = row
        name_short = (name[:42] + '...') if len(name) > 45 else name
        print(f"{serial:<10} {name_short:<45} {atype or '':<20}")
    
    # 7. Account type distribution
    print("\n\n7. ACCOUNT TYPE DISTRIBUTION")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            qb_account_type,
            COUNT(*) as count
        FROM qb_accounts_staging
        WHERE qb_account_type IS NOT NULL
        GROUP BY qb_account_type
        ORDER BY count DESC
    """)
    
    print(f"\n{'Type':<30} {'Count':<10}")
    print("-"*80)
    for atype, count in cur.fetchall():
        print(f"{atype:<30} {count:<10}")
    
    # 8. Recommendation
    print("\n\n8. RECOMMENDATION")
    print("="*80)
    
    if by_number == 0 and by_name < 50:
        print("\n⚠️  MINIMAL OVERLAP - These appear to be from a different QB export")
        print("\n   Possible reasons:")
        print("   1. Different time period (older/newer QB data)")
        print("   2. Different company file")
        print("   3. Test/staging data from QB import experiments")
        print("\n   ✓ Safe to keep as historical reference")
        print("   ✓ Do NOT merge into chart_of_accounts (would create duplicates)")
        print("   ✓ Consider renaming to qb_accounts_staging_legacy")
    else:
        print("\n⚠️  REVIEW NEEDED - Some overlap detected")
        print("\n   Next steps:")
        print("   1. Manual review of unmatched accounts")
        print("   2. Determine if missing accounts should be added to chart")
        print("   3. Create migration script if merge is needed")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
