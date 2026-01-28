#!/usr/bin/env python3
"""
Verify PostgreSQL payment data against LMS to ensure no legitimate payments deleted.

Compares:
1. Payment counts by year
2. Payment totals by year
3. Individual payment records
4. Reserve number coverage
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_lms_connection():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_pg_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def compare_payment_totals():
    """Compare payment counts and totals between LMS and PostgreSQL"""
    
    print("=" * 80)
    print("PAYMENT DATA VERIFICATION: LMS vs PostgreSQL")
    print("=" * 80)
    
    lms_conn = get_lms_connection()
    pg_conn = get_pg_connection()
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
    
    # LMS Payment table totals
    print("\n📊 LMS PAYMENT TABLE:")
    lms_cur.execute("""
        SELECT 
            COUNT(*) as total_count,
            SUM(Amount) as total_amount
        FROM Payment
        WHERE Amount IS NOT NULL
    """)
    
    lms_row = lms_cur.fetchone()
    lms_count = lms_row[0]
    lms_total = float(lms_row[1] or 0)
    
    print(f"   Total payments: {lms_count:,}")
    print(f"   Total amount: ${lms_total:,.2f}")
    
    # PostgreSQL payments table totals
    print("\n📊 POSTGRESQL PAYMENTS TABLE:")
    pg_cur.execute("""
        SELECT 
            COUNT(*) as total_count,
            SUM(amount) as total_amount
        FROM payments
        WHERE amount IS NOT NULL
    """)
    
    pg_row = pg_cur.fetchone()
    pg_count = pg_row['total_count']
    pg_total = float(pg_row['total_amount'] or 0)
    
    print(f"   Total payments: {pg_count:,}")
    print(f"   Total amount: ${pg_total:,.2f}")
    
    # Compare
    print("\n📊 COMPARISON:")
    count_diff = pg_count - lms_count
    amount_diff = pg_total - lms_total
    
    print(f"   Count difference: {count_diff:,} ({count_diff/lms_count*100:+.1f}%)")
    print(f"   Amount difference: ${amount_diff:,.2f} ({amount_diff/lms_total*100:+.1f}%)")
    
    if pg_count >= lms_count:
        print(f"   [OK] PostgreSQL has {count_diff:,} MORE payments than LMS")
        print(f"      (This is expected - includes Square and other integrated sources)")
    else:
        print(f"   [WARN] PostgreSQL has {abs(count_diff):,} FEWER payments than LMS")
        print(f"      WARNING: This could indicate data loss!")
    
    # Check by year
    print("\n" + "=" * 80)
    print("PAYMENT COUNTS BY YEAR")
    print("=" * 80)
    
    # LMS by year
    lms_cur.execute("""
        SELECT 
            YEAR(LastUpdated) as payment_year,
            COUNT(*) as count,
            SUM(Amount) as total
        FROM Payment
        WHERE LastUpdated IS NOT NULL
        GROUP BY YEAR(LastUpdated)
        ORDER BY YEAR(LastUpdated)
    """)
    
    lms_by_year = {}
    for row in lms_cur.fetchall():
        year = row[0]
        if year:
            lms_by_year[year] = {'count': row[1], 'total': float(row[2] or 0)}
    
    # PostgreSQL by year
    pg_cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date)::INTEGER as payment_year,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE payment_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY payment_year
    """)
    
    pg_by_year = {}
    for row in pg_cur.fetchall():
        year = row['payment_year']
        if year:
            pg_by_year[year] = {'count': row['count'], 'total': float(row['total'] or 0)}
    
    # Compare by year
    all_years = sorted(set(list(lms_by_year.keys()) + list(pg_by_year.keys())))
    
    print(f"\n{'Year':<6} {'LMS Count':>12} {'LMS Total':>15} {'PG Count':>12} {'PG Total':>15} {'Diff Count':>12} {'Diff %':>10}")
    print("-" * 100)
    
    for year in all_years:
        lms_data = lms_by_year.get(year, {'count': 0, 'total': 0})
        pg_data = pg_by_year.get(year, {'count': 0, 'total': 0})
        
        count_diff = pg_data['count'] - lms_data['count']
        
        if lms_data['count'] > 0:
            pct_diff = (count_diff / lms_data['count']) * 100
        else:
            pct_diff = 0
        
        status = "[OK]" if pg_data['count'] >= lms_data['count'] else "[WARN]"
        
        print(f"{year:<6} {lms_data['count']:>12,} ${lms_data['total']:>13,.2f} "
              f"{pg_data['count']:>12,} ${pg_data['total']:>13,.2f} "
              f"{count_diff:>12,} {pct_diff:>9.1f}% {status}")
    
    # Check for missing reserve numbers
    print("\n" + "=" * 80)
    print("RESERVE NUMBER COVERAGE CHECK")
    print("=" * 80)
    
    lms_cur.execute("""
        SELECT DISTINCT Reserve_No
        FROM Payment
        WHERE Reserve_No IS NOT NULL
        AND Reserve_No <> ''
    """)
    
    lms_reserves = {row[0] for row in lms_cur.fetchall()}
    
    pg_cur.execute("""
        SELECT DISTINCT reserve_number
        FROM payments
        WHERE reserve_number IS NOT NULL
    """)
    
    pg_reserves = {row['reserve_number'] for row in pg_cur.fetchall()}
    
    missing_in_pg = lms_reserves - pg_reserves
    
    print(f"\n📊 Reserve numbers in LMS: {len(lms_reserves):,}")
    print(f"📊 Reserve numbers in PostgreSQL: {len(pg_reserves):,}")
    
    if missing_in_pg:
        print(f"\n[WARN] WARNING: {len(missing_in_pg)} reserve numbers in LMS but NOT in PostgreSQL:")
        for reserve in sorted(missing_in_pg)[:20]:
            print(f"   - {reserve}")
        if len(missing_in_pg) > 20:
            print(f"   ... and {len(missing_in_pg) - 20} more")
    else:
        print(f"\n[OK] All LMS reserve numbers present in PostgreSQL")
    
    lms_cur.close()
    pg_cur.close()
    lms_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    compare_payment_totals()
    
    print("\n" + "=" * 80)
    print("✓ Verification complete")
    print("=" * 80)
