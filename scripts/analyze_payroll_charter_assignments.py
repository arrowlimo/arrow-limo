#!/usr/bin/env python3
"""
Analyze payroll data structure to identify charter assignments, driver roles,
and payment breakdowns (primary driver, trainer, second driver, host, etc.)
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("PAYROLL DATA STRUCTURE ANALYSIS - CHARTER ASSIGNMENTS & ROLES")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Check driver_payroll columns
    print("=" * 80)
    print("1. DRIVER_PAYROLL TABLE SCHEMA")
    print("=" * 80)
    
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = 'driver_payroll'
        ORDER BY ordinal_position
    """)
    
    print("\nColumns in driver_payroll:")
    for row in cur.fetchall():
        col_name = row[0]
        data_type = row[1]
        max_len = f"({row[2]})" if row[2] else ""
        print(f"  {col_name:<30} {data_type}{max_len}")
    
    # 2. Charter linkage
    print("\n" + "=" * 80)
    print("2. CHARTER LINKAGE ANALYSIS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN charter_id IS NOT NULL AND charter_id != '' THEN 1 END) as has_charter_id,
            COUNT(CASE WHEN reserve_number IS NOT NULL AND reserve_number != '' THEN 1 END) as has_reserve_number,
            COUNT(CASE WHEN charter_id IS NULL OR charter_id = '' THEN 1 END) as no_charter_link
        FROM driver_payroll
    """)
    
    row = cur.fetchone()
    print(f"\nPayroll-Charter Linkage:")
    print(f"  Total payroll records: {row[0]:,}")
    print(f"  With charter_id: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"  With reserve_number: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    print(f"  No charter link: {row[3]:,} ({row[3]/row[0]*100:.1f}%)")
    
    # 3. Sample records with charter links
    print("\n" + "=" * 80)
    print("3. SAMPLE PAYROLL RECORDS WITH CHARTER LINKAGE")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            dp.id,
            dp.driver_id,
            dp.charter_id,
            dp.reserve_number,
            dp.pay_date,
            dp.gross_pay,
            c.driver_gratuity,
            c.driver_total,
            c.driver,
            dp.record_notes
        FROM driver_payroll dp
        LEFT JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE dp.reserve_number IS NOT NULL 
        AND dp.charter_id != ''
        ORDER BY dp.pay_date DESC
        LIMIT 10
    """)
    
    print("\nRecent payroll records linked to charters:")
    print(f"{'Payroll ID':<12} {'Driver ID':<12} {'Charter':<10} {'Reserve':<10} {'Gross Pay':<12} {'Charter Grat':<14} {'Notes':<30}")
    print("-" * 110)
    
    for row in cur.fetchall():
        payroll_id = row[0]
        driver_id = row[1] or 'N/A'
        charter_id = row[2] or 'N/A'
        reserve = row[3] or 'N/A'
        gross = f"${row[5]:,.2f}" if row[5] else "$0.00"
        grat = f"${row[6]:,.2f}" if row[6] else "$0.00"
        notes = (row[9][:27] + '...') if row[9] and len(row[9]) > 30 else (row[9] or '')
        
        print(f"{payroll_id:<12} {driver_id:<12} {charter_id:<10} {reserve:<10} {gross:<12} {grat:<14} {notes:<30}")
    
    # 4. Check for role indicators in notes or source fields
    print("\n" + "=" * 80)
    print("4. ROLE INDICATORS IN PAYROLL DATA")
    print("=" * 80)
    
    # Check record_notes for role keywords
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN record_notes ILIKE '%train%' THEN 1 END) as training,
            COUNT(CASE WHEN record_notes ILIKE '%second%driver%' THEN 1 END) as second_driver,
            COUNT(CASE WHEN record_notes ILIKE '%host%' THEN 1 END) as host,
            COUNT(CASE WHEN record_notes ILIKE '%extra%' THEN 1 END) as extra_duties,
            COUNT(CASE WHEN record_notes ILIKE '%assist%' THEN 1 END) as assistant
        FROM driver_payroll
        WHERE record_notes IS NOT NULL
    """)
    
    row = cur.fetchone()
    print(f"\nRole keywords in record_notes:")
    print(f"  Total records with notes: {row[0]:,}")
    print(f"  Training references: {row[1]:,}")
    print(f"  Second driver references: {row[2]:,}")
    print(f"  Host references: {row[3]:,}")
    print(f"  Extra duties references: {row[4]:,}")
    print(f"  Assistant references: {row[5]:,}")
    
    # Sample notes with role keywords
    if row[1] > 0 or row[2] > 0 or row[3] > 0:
        cur.execute("""
            SELECT driver_id, pay_date, gross_pay, record_notes
            FROM driver_payroll
            WHERE record_notes ILIKE ANY(ARRAY['%train%', '%second%driver%', '%host%', '%extra%', '%assist%'])
            LIMIT 10
        """)
        
        print("\nSample records with role indicators:")
        print(f"{'Driver ID':<12} {'Date':<12} {'Gross Pay':<12} {'Notes':<50}")
        print("-" * 90)
        
        for row in cur.fetchall():
            driver = row[0] or 'N/A'
            date = str(row[1]) if row[1] else 'N/A'
            gross = f"${row[2]:,.2f}" if row[2] else "$0.00"
            notes = (row[3][:47] + '...') if row[3] and len(row[3]) > 50 else (row[3] or '')
            
            print(f"{driver:<12} {date:<12} {gross:<12} {notes:<50}")
    
    # 5. Check charters table for multiple drivers
    print("\n" + "=" * 80)
    print("5. CHARTERS WITH MULTIPLE DRIVER ASSIGNMENTS")
    print("=" * 80)
    
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'charters'
        AND column_name ILIKE '%driver%'
        ORDER BY ordinal_position
    """)
    
    driver_columns = [row[0] for row in cur.fetchall()]
    print(f"\nDriver-related columns in charters table:")
    for col in driver_columns:
        print(f"  {col}")
    
    # Check if any charters have multiple driver fields populated
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN driver IS NOT NULL AND driver != '' THEN 1 END) as has_driver,
            COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as has_assigned_driver
        FROM charters
    """)
    
    row = cur.fetchone()
    print(f"\nDriver assignment in charters:")
    print(f"  Total charters: {row[0]:,}")
    print(f"  With driver field: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"  With assigned_driver_id: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    
    # 6. Check for multiple payroll records per charter
    print("\n" + "=" * 80)
    print("6. MULTIPLE PAYROLL ENTRIES PER CHARTER")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            charter_id,
            COUNT(*) as payroll_count,
            STRING_AGG(DISTINCT driver_id, ', ') as drivers,
            SUM(gross_pay) as total_gross
        FROM driver_payroll
        WHERE reserve_number IS NOT NULL 
        AND charter_id != ''
        GROUP BY charter_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    
    rows = cur.fetchall()
    if len(rows) > 0:
        print(f"\nCharters with multiple payroll entries ({len(rows)} found, showing top 20):")
        print(f"{'Charter ID':<12} {'# Entries':<12} {'Total Gross':<14} {'Drivers':<40}")
        print("-" * 80)
        
        for row in rows:
            charter = row[0]
            count = row[1]
            total = f"${row[3]:,.2f}" if row[3] else "$0.00"
            drivers = (row[2][:37] + '...') if row[2] and len(row[2]) > 40 else (row[2] or 'N/A')
            
            print(f"{charter:<12} {count:<12} {total:<14} {drivers:<40}")
        
        # Sample detailed view
        print("\nDetailed view of charter with multiple entries:")
        sample_charter = rows[0][0]
        
        cur.execute("""
            SELECT 
                dp.driver_id,
                dp.pay_date,
                dp.gross_pay,
                dp.record_notes,
                c.driver,
                c.driver_total
            FROM driver_payroll dp
            LEFT JOIN charters c ON dp.charter_id::integer = c.charter_id
            WHERE dp.charter_id = %s
            ORDER BY dp.pay_date
        """, (sample_charter,))
        
        print(f"\nCharter {sample_charter} payroll breakdown:")
        print(f"{'Driver ID':<12} {'Date':<12} {'Gross Pay':<12} {'Charter Driver':<15} {'Notes':<30}")
        print("-" * 90)
        
        for row in cur.fetchall():
            driver = row[0] or 'N/A'
            date = str(row[1]) if row[1] else 'N/A'
            gross = f"${row[2]:,.2f}" if row[2] else "$0.00"
            charter_driver = row[4] or 'N/A'
            notes = (row[3][:27] + '...') if row[3] and len(row[3]) > 30 else (row[3] or '')
            
            print(f"{driver:<12} {date:<12} {gross:<12} {charter_driver:<15} {notes:<30}")
    else:
        print("\nNo charters found with multiple payroll entries")
    
    # 7. Employee pay entries tables
    print("\n" + "=" * 80)
    print("7. RELATED PAY ENTRY TABLES")
    print("=" * 80)
    
    for table in ['chauffeur_pay_entries', 'driver_pay_entries', 'employee_pay_entries']:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        
        if count > 0:
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """)
            columns = [row[0] for row in cur.fetchall()]
            
            print(f"\n{table}: {count:,} records")
            print("  Columns:", ', '.join(columns[:10]))
            if len(columns) > 10:
                print(f"  ... and {len(columns) - 10} more")
            
            # Sample records
            cur.execute(f"SELECT * FROM {table} LIMIT 3")
            rows = cur.fetchall()
            if len(rows) > 0:
                print(f"  Sample record: {dict(zip(columns[:5], rows[0][:5]))}")
    
    # 8. Summary and conclusions
    print("\n" + "=" * 80)
    print("8. SUMMARY: CHARTER ASSIGNMENT & ROLE TRACKING")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT charter_id) as unique_charters,
            COUNT(*) as total_entries,
            COUNT(DISTINCT driver_id) as unique_drivers
        FROM driver_payroll
        WHERE reserve_number IS NOT NULL AND charter_id != ''
    """)
    row = cur.fetchone()
    
    print(f"\nPayroll-Charter Relationships:")
    print(f"  Unique charters with payroll: {row[0]:,}")
    print(f"  Total payroll entries: {row[1]:,}")
    print(f"  Unique drivers: {row[2]:,}")
    
    if row[0] and row[1]:
        avg_entries = row[1] / row[0]
        print(f"  Average payroll entries per charter: {avg_entries:.2f}")
    
    print("\n" + "=" * 80)
    print("CONCLUSIONS:")
    print("=" * 80)
    
    # Determine what tracking exists
    cur.execute("""
        SELECT 
            COUNT(CASE WHEN charter_id IS NOT NULL AND charter_id != '' THEN 1 END) as charter_linked,
            COUNT(CASE WHEN record_notes ILIKE '%train%' THEN 1 END) as training_notes,
            COUNT(CASE WHEN record_notes ILIKE '%second%' THEN 1 END) as second_driver_notes,
            COUNT(*) as total
        FROM driver_payroll
    """)
    row = cur.fetchone()
    
    charter_pct = (row[0] / row[3] * 100) if row[3] > 0 else 0
    
    print(f"\n1. Charter Assignment Tracking:")
    if charter_pct > 80:
        print(f"   ✓ GOOD: {charter_pct:.1f}% of payroll records linked to charters")
        print("   Each payroll entry shows which charter the driver worked")
    elif charter_pct > 50:
        print(f"   [WARN]  PARTIAL: {charter_pct:.1f}% of payroll records linked to charters")
        print("   Some non-charter work (office, maintenance, etc.)")
    else:
        print(f"   [FAIL] LIMITED: Only {charter_pct:.1f}% of payroll linked to charters")
        print("   Significant non-charter payroll or missing linkage")
    
    print(f"\n2. Role/Duty Tracking:")
    if row[1] > 0 or row[2] > 0:
        print(f"   ℹ️  SOME TRACKING: {row[1]} training, {row[2]} second driver notes found")
        print("   Role details appear in record_notes field")
    else:
        print("   [FAIL] NO ROLE TRACKING: No training/second driver indicators found")
        print("   System does not distinguish primary vs training/host roles")
    
    print(f"\n3. Recommendations:")
    print("   - Review charters with multiple payroll entries to understand splits")
    print("   - Check record_notes field for any role/duty documentation")
    print("   - Consider adding structured fields for role tracking if needed")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
