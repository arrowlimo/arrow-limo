#!/usr/bin/env python3
"""
Debug Charter Synchronization Issue
Analysis of why PostgreSQL charters don't match LMS Reserve table
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        cursor_factory=RealDictCursor
    )

def get_lms_connection():
    """Get LMS Access database connection"""
    lms_path = r'L:\limo\backups\lms.mdb'
    if not os.path.exists(lms_path):
        lms_path = r'L:\limo\lms.mdb'
    
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    return pyodbc.connect(conn_str)

def main():
    print("🔍 CHARTER SYNCHRONIZATION DEBUG ANALYSIS")
    print("=" * 50)
    
    # Connect to both databases
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        # 1. Check PostgreSQL reserve_number field structure
        print("📊 POSTGRESQL RESERVE_NUMBER ANALYSIS:")
        
        pg_cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                COUNT(DISTINCT reserve_number) as unique_reserve_numbers,
                COUNT(reserve_number) as non_null_reserve_numbers,
                MIN(reserve_number) as min_reserve_number,
                MAX(reserve_number) as max_reserve_number
            FROM charters 
            WHERE reserve_number IS NOT NULL AND reserve_number != ''
        """)
        
        pg_stats = pg_cur.fetchone()
        print(f"   Total charters: {pg_stats['total_charters']:,}")
        print(f"   Unique reserve numbers: {pg_stats['unique_reserve_numbers']:,}")
        print(f"   Non-null reserve numbers: {pg_stats['non_null_reserve_numbers']:,}")
        print(f"   Min reserve number: {pg_stats['min_reserve_number']}")
        print(f"   Max reserve number: {pg_stats['max_reserve_number']}")
        
        # 2. Sample PostgreSQL reserve numbers
        pg_cur.execute("""
            SELECT DISTINCT reserve_number 
            FROM charters 
            WHERE reserve_number IS NOT NULL AND reserve_number != ''
            ORDER BY reserve_number DESC 
            LIMIT 20
        """)
        
        pg_samples = [row['reserve_number'] for row in pg_cur.fetchall()]
        print(f"\n📝 SAMPLE POSTGRESQL RESERVE NUMBERS:")
        for sample in pg_samples:
            print(f"   {sample}")
        
        # 3. Check LMS Reserve_No structure
        print(f"\n📊 LMS RESERVE_NO ANALYSIS:")
        
        lms_cur.execute("SELECT COUNT(*) FROM Reserve")
        total_lms = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT COUNT(*) FROM Reserve WHERE Reserve_No IS NOT NULL")
        non_null_lms = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT MIN(Reserve_No), MAX(Reserve_No) FROM Reserve WHERE Reserve_No IS NOT NULL")
        min_lms, max_lms = lms_cur.fetchone()
        
        print(f"   Total LMS reserves: {total_lms:,}")
        print(f"   Non-null Reserve_No: {non_null_lms:,}")
        print(f"   Min Reserve_No: {min_lms}")
        print(f"   Max Reserve_No: {max_lms}")
        
        # 4. Sample LMS Reserve_No values
        lms_cur.execute("SELECT TOP 20 Reserve_No FROM Reserve WHERE Reserve_No IS NOT NULL ORDER BY Reserve_No DESC")
        lms_samples = [row[0] for row in lms_cur.fetchall()]
        
        print(f"\n📝 SAMPLE LMS RESERVE_NO VALUES:")
        for sample in lms_samples:
            print(f"   {sample}")
        
        # 5. Check for format differences
        print(f"\n🔍 FORMAT COMPARISON:")
        
        # Check if PostgreSQL stores as string vs LMS as number
        pg_cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name = 'charters' AND column_name = 'reserve_number'")
        pg_type = pg_cur.fetchone()['data_type']
        print(f"   PostgreSQL reserve_number type: {pg_type}")
        
        # Check for leading zeros or formatting differences
        if pg_samples and lms_samples:
            print(f"   PostgreSQL sample: '{pg_samples[0]}' (type: {type(pg_samples[0])})")
            print(f"   LMS sample: '{lms_samples[0]}' (type: {type(lms_samples[0])})")
        
        # 6. Look for any overlap by converting to integers
        print(f"\n🔍 NUMERIC COMPARISON ATTEMPT:")
        
        try:
            # Get numeric versions of reserve numbers
            pg_cur.execute("""
                SELECT DISTINCT CAST(reserve_number AS INTEGER) as reserve_num
                FROM charters 
                WHERE reserve_number ~ '^[0-9]+$'
                ORDER BY reserve_num DESC 
                LIMIT 10
            """)
            pg_numeric = [row['reserve_num'] for row in pg_cur.fetchall()]
            print(f"   PostgreSQL numeric reserves (sample): {pg_numeric[:10]}")
            
            lms_cur.execute("SELECT TOP 10 Reserve_No FROM Reserve WHERE Reserve_No IS NOT NULL ORDER BY Reserve_No DESC")
            lms_numeric = [row[0] for row in lms_cur.fetchall()]
            print(f"   LMS numeric reserves (sample): {lms_numeric}")
            
            # Check for overlap
            if pg_numeric and lms_numeric:
                overlap = set(pg_numeric) & set(lms_numeric)
                print(f"   Numeric overlap found: {len(overlap)} records")
                if overlap:
                    print(f"   Sample overlapping numbers: {list(overlap)[:10]}")
                    
        except Exception as e:
            print(f"   Numeric comparison failed: {e}")
        
        # 7. Check account_number matching as alternative
        print(f"\n🔍 ACCOUNT NUMBER CROSS-REFERENCE:")
        
        pg_cur.execute("""
            SELECT COUNT(DISTINCT account_number) as unique_accounts
            FROM charters 
            WHERE account_number IS NOT NULL AND account_number != ''
        """)
        pg_accounts = pg_cur.fetchone()['unique_accounts']
        
        lms_cur.execute("SELECT COUNT(DISTINCT Account_No) FROM Reserve WHERE Account_No IS NOT NULL")
        lms_accounts = lms_cur.fetchone()[0]
        
        print(f"   PostgreSQL unique account numbers: {pg_accounts:,}")
        print(f"   LMS unique account numbers: {lms_accounts:,}")
        
        # 8. Date range validation
        print(f"\n📅 DATE RANGE VALIDATION:")
        
        pg_cur.execute("SELECT MIN(charter_date), MAX(charter_date) FROM charters")
        pg_min_date, pg_max_date = pg_cur.fetchone()
        
        lms_cur.execute("SELECT MIN(PU_Date), MAX(PU_Date) FROM Reserve")
        lms_min_date, lms_max_date = lms_cur.fetchone()
        
        print(f"   PostgreSQL date range: {pg_min_date} to {pg_max_date}")
        print(f"   LMS date range: {lms_min_date} to {lms_max_date}")
        
        # 9. Check for charter_id vs reserve_number mapping
        print(f"\n🔍 CHARTER ID ANALYSIS:")
        
        pg_cur.execute("SELECT MIN(charter_id), MAX(charter_id), COUNT(*) FROM charters")
        pg_id_stats = pg_cur.fetchone()
        print(f"   PostgreSQL charter_id range: {pg_id_stats[0]} to {pg_id_stats[1]} ({pg_id_stats[2]:,} records)")
        
        # 10. Summary assessment
        print(f"\n🎯 SYNCHRONIZATION ASSESSMENT:")
        print(f"   LMS has {total_lms:,} reservations")
        print(f"   PostgreSQL has {pg_stats['total_charters']:,} charters")
        print(f"   Difference: {abs(total_lms - pg_stats['total_charters']):,} records")
        
        if abs(total_lms - pg_stats['total_charters']) <= 10:
            print("   [OK] Record counts are very close - likely mapping issue")
        else:
            print("   [WARN]  Significant record count difference - data migration issue")
            
    except Exception as e:
        print(f"[FAIL] Analysis failed: {e}")
        
    finally:
        pg_cur.close()
        pg_conn.close()
        lms_cur.close()
        lms_conn.close()

if __name__ == "__main__":
    main()