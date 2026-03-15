"""
Comprehensive audit of charter dates across entire database.
Extends beyond the 100 recent charters to check for date discrepancies in all records.
"""
import psycopg2
import pyodbc

def get_db_connection():
    """Connect to PostgreSQL."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def get_lms_connection():
    """Connect to LMS Access database."""
    lms_path = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    return pyodbc.connect(conn_str)

def main():
    pg_conn = get_db_connection()
    lms_conn = get_lms_connection()
    
    pg_cur = pg_conn.cursor()
    lms_cur = lms_conn.cursor()
    
    print("="*100)
    print("COMPREHENSIVE CHARTER DATE AUDIT - ALL RECORDS")
    print("="*100)
    print()
    
    # Get all PostgreSQL charters with dates
    print("Querying PostgreSQL charters...")
    pg_cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount
        FROM charters
        WHERE charter_date IS NOT NULL
        AND reserve_number IS NOT NULL
        ORDER BY reserve_number DESC
    """)
    
    pg_charters = pg_cur.fetchall()
    print(f"Found {len(pg_charters)} charters with dates in PostgreSQL")
    print()
    
    # Get all LMS reserves
    print("Querying LMS reserves...")
    lms_cur.execute("""
        SELECT Reserve_No, PU_Date, Est_Charge, Deposit
        FROM Reserve
        WHERE PU_Date IS NOT NULL
        AND Reserve_No IS NOT NULL
    """)
    
    lms_reserves = {str(row[0]): row for row in lms_cur.fetchall()}
    print(f"Found {len(lms_reserves)} reserves with PU_Date in LMS")
    print()
    
    # Compare all records
    print("Comparing dates...")
    mismatches = []
    matched = 0
    not_in_lms = 0
    
    for reserve_number, pg_date, pg_total, pg_paid in pg_charters:
        reserve_str = str(reserve_number)
        
        if reserve_str not in lms_reserves:
            not_in_lms += 1
            continue
        
        lms_reserve, lms_pu_date, lms_charge, lms_deposit = lms_reserves[reserve_str]
        
        # Convert LMS datetime to date for comparison
        lms_date = lms_pu_date.date() if lms_pu_date else None
        
        if pg_date != lms_date:
            mismatches.append({
                'reserve': reserve_str,
                'pg_date': pg_date,
                'lms_date': lms_date,
                'pg_total': pg_total,
                'lms_total': lms_charge,
                'pg_paid': pg_paid,
                'lms_paid': lms_deposit
            })
        else:
            matched += 1
    
    # Summary
    print("="*100)
    print("AUDIT RESULTS SUMMARY")
    print("="*100)
    print()
    print(f"Total PostgreSQL charters checked: {len(pg_charters)}")
    print(f"Matched dates (PostgreSQL = LMS): {matched}")
    print(f"Mismatched dates: {len(mismatches)}")
    print(f"Not found in LMS: {not_in_lms}")
    print()
    
    if matched > 0:
        match_rate = (matched / len(pg_charters)) * 100
        print(f"Match rate: {match_rate:.1f}%")
        print()
    
    if mismatches:
        print("="*100)
        print(f"DATE MISMATCHES FOUND: {len(mismatches)} charters")
        print("="*100)
        print()
        
        # Analyze patterns in mismatches
        pg_dates = {}
        for m in mismatches:
            pg_date = m['pg_date']
            if pg_date:
                pg_dates[pg_date] = pg_dates.get(pg_date, 0) + 1
        
        if pg_dates:
            print("PostgreSQL date patterns in mismatches:")
            for date, count in sorted(pg_dates.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {date}: {count} charters")
            print()
        
        # Show first 50 mismatches
        print("DETAILED MISMATCH LIST (first 50):")
        print("-" * 100)
        print(f"{'Reserve':<10} {'PG Date':<12} {'LMS Date':<12} {'PG Total':<12} {'LMS Total':<12} {'PG Paid':<12} {'LMS Paid':<12}")
        print("-" * 100)
        
        for m in mismatches[:50]:
            pg_date_str = m['pg_date'].strftime('%Y-%m-%d') if m['pg_date'] else 'NULL'
            lms_date_str = m['lms_date'].strftime('%Y-%m-%d') if m['lms_date'] else 'NULL'
            print(f"{m['reserve']:<10} {pg_date_str:<12} {lms_date_str:<12} "
                  f"${m['pg_total'] or 0:>10,.2f} ${m['lms_total'] or 0:>10,.2f} "
                  f"${m['pg_paid'] or 0:>10,.2f} ${m['lms_paid'] or 0:>10,.2f}")
        
        if len(mismatches) > 50:
            print(f"... ({len(mismatches) - 50} more mismatches not shown)")
        print()
        
        # Group by date ranges
        print("MISMATCH ANALYSIS BY RESERVE NUMBER RANGE:")
        print("-" * 100)
        
        ranges = {
            '000000-004999': [],
            '005000-009999': [],
            '010000-014999': [],
            '015000-019999': []
        }
        
        for m in mismatches:
            reserve_num = int(m['reserve'])
            if reserve_num < 5000:
                ranges['000000-004999'].append(m)
            elif reserve_num < 10000:
                ranges['005000-009999'].append(m)
            elif reserve_num < 15000:
                ranges['010000-014999'].append(m)
            else:
                ranges['015000-019999'].append(m)
        
        for range_name, range_mismatches in ranges.items():
            if range_mismatches:
                print(f"{range_name}: {len(range_mismatches)} mismatches")
        print()
        
        # Check if we need to create a fix script
        print("RECOMMENDATION:")
        print("-" * 100)
        if len(mismatches) > 0:
            print(f"Found {len(mismatches)} date mismatches across the entire database.")
            print()
            print("To fix all mismatches, you can:")
            print("1. Review the detailed list above")
            print("2. Run fix_charter_dates_from_lms.py without LIMIT to fix all")
            print("3. Or create a targeted fix for specific reserve number ranges")
            print()
            print(f"Command to fix all: python L:\\limo\\scripts\\fix_all_charter_dates.py --write")
        else:
            print("✓ No date mismatches found! All charter dates match LMS.")
        print()
        
    else:
        print("✓ SUCCESS: All charter dates match between PostgreSQL and LMS!")
        print()
        print("Database integrity verified - no date correction needed.")
        print()
    
    # Additional statistics
    print("="*100)
    print("ADDITIONAL STATISTICS")
    print("="*100)
    print()
    
    # Date range coverage
    pg_cur.execute("""
        SELECT 
            MIN(charter_date) as earliest,
            MAX(charter_date) as latest,
            COUNT(*) as total
        FROM charters
        WHERE charter_date IS NOT NULL
    """)
    
    earliest, latest, total = pg_cur.fetchone()
    if earliest and latest:
        print(f"PostgreSQL date range: {earliest} to {latest} ({total} charters)")
    
    # LMS date range
    lms_cur.execute("""
        SELECT 
            MIN(PU_Date) as earliest,
            MAX(PU_Date) as latest,
            COUNT(*) as total
        FROM Reserve
        WHERE PU_Date IS NOT NULL
    """)
    
    earliest, latest, total = lms_cur.fetchone()
    if earliest and latest:
        print(f"LMS date range: {earliest.date()} to {latest.date()} ({total} reserves)")
    print()
    
    pg_cur.close()
    lms_cur.close()
    pg_conn.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
