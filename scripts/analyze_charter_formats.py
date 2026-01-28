#!/usr/bin/env python3
"""
Charter Format Analysis - Understanding the Two Reserve Number Systems
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import re

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
    print("🔍 CHARTER RESERVE NUMBER FORMAT ANALYSIS")
    print("=" * 50)
    
    # Connect to databases
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        # 1. Analyze PostgreSQL reserve number formats
        print("📊 POSTGRESQL RESERVE NUMBER FORMATS:")
        
        pg_cur.execute("""
            SELECT 
                CASE 
                    WHEN reserve_number ~ '^REF[0-9]+$' THEN 'REF_FORMAT'
                    WHEN reserve_number ~ '^[0-9]+$' THEN 'NUMERIC_FORMAT'
                    ELSE 'OTHER_FORMAT'
                END as format_type,
                COUNT(*) as count,
                MIN(reserve_number) as min_example,
                MAX(reserve_number) as max_example
            FROM charters 
            WHERE reserve_number IS NOT NULL AND reserve_number != ''
            GROUP BY format_type
            ORDER BY count DESC
        """)
        
        formats = pg_cur.fetchall()
        total_pg = sum(f['count'] for f in formats)
        
        for fmt in formats:
            pct = fmt['count'] / total_pg * 100
            print(f"   {fmt['format_type']}: {fmt['count']:,} ({pct:.1f}%)")
            print(f"      Range: {fmt['min_example']} to {fmt['max_example']}")
        
        # 2. Get numeric-only PostgreSQL reserves for comparison
        print(f"\n🔍 NUMERIC POSTGRESQL RESERVES:")
        
        pg_cur.execute("""
            SELECT COUNT(*) as count
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
        """)
        numeric_pg_count = pg_cur.fetchone()['count']
        print(f"   Total numeric reserves in PostgreSQL: {numeric_pg_count:,}")
        
        # Get sample numeric reserves
        pg_cur.execute("""
            SELECT reserve_number
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
            ORDER BY CAST(reserve_number AS INTEGER) DESC
            LIMIT 20
        """)
        pg_numeric_samples = [row['reserve_number'] for row in pg_cur.fetchall()]
        
        # 3. Compare with LMS
        print(f"\n📊 LMS RESERVE COMPARISON:")
        
        lms_cur.execute("SELECT COUNT(*) FROM Reserve")
        lms_count = lms_cur.fetchone()[0]
        print(f"   Total LMS reserves: {lms_count:,}")
        
        # Get LMS samples
        lms_cur.execute("SELECT TOP 20 Reserve_No FROM Reserve ORDER BY Reserve_No DESC")
        lms_samples = [row[0] for row in lms_cur.fetchall()]
        
        print(f"\n🔍 OVERLAP ANALYSIS:")
        print(f"   PostgreSQL numeric samples: {pg_numeric_samples[:10]}")
        print(f"   LMS samples: {lms_samples[:10]}")
        
        # Convert to integers for comparison
        pg_numeric_ints = [int(x) for x in pg_numeric_samples if x.isdigit()]
        lms_ints = [int(x) for x in lms_samples if x.isdigit()]
        
        overlap = set(pg_numeric_ints) & set(lms_ints)
        print(f"   Overlapping reserve numbers: {len(overlap)}")
        if overlap:
            print(f"   Sample overlaps: {sorted(list(overlap), reverse=True)[:10]}")
        
        # 4. Check missing ranges
        if pg_numeric_ints and lms_ints:
            pg_max = max(pg_numeric_ints)
            lms_max = max(lms_ints)
            pg_min = min(pg_numeric_ints)
            lms_min = min(lms_ints)
            
            print(f"\n📊 NUMERIC RANGE ANALYSIS:")
            print(f"   PostgreSQL numeric range: {pg_min:,} to {pg_max:,}")
            print(f"   LMS range: {lms_min:,} to {lms_max:,}")
            
            # Check for gaps
            lms_set = set(lms_ints)
            pg_set = set(pg_numeric_ints)
            
            missing_from_pg = lms_set - pg_set
            extra_in_pg = pg_set - lms_set
            
            print(f"   Missing from PostgreSQL: {len(missing_from_pg):,}")
            print(f"   Extra in PostgreSQL: {len(extra_in_pg):,}")
            
            if missing_from_pg:
                missing_samples = sorted(list(missing_from_pg), reverse=True)[:10]
                print(f"   Sample missing: {missing_samples}")
            
            if extra_in_pg:
                extra_samples = sorted(list(extra_in_pg), reverse=True)[:10]
                print(f"   Sample extra: {extra_samples}")
        
        # 5. Date correlation analysis
        print(f"\n📅 DATE CORRELATION ANALYSIS:")
        
        # Check when REF format started
        pg_cur.execute("""
            SELECT 
                MIN(charter_date) as earliest_ref,
                MAX(charter_date) as latest_ref
            FROM charters 
            WHERE reserve_number ~ '^REF[0-9]+$'
        """)
        ref_dates = pg_cur.fetchone()
        
        pg_cur.execute("""
            SELECT 
                MIN(charter_date) as earliest_numeric,
                MAX(charter_date) as latest_numeric  
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
        """)
        numeric_dates = pg_cur.fetchone()
        
        if ref_dates['earliest_ref']:
            print(f"   REF format date range: {ref_dates['earliest_ref']} to {ref_dates['latest_ref']}")
        if numeric_dates['earliest_numeric']:
            print(f"   Numeric format date range: {numeric_dates['earliest_numeric']} to {numeric_dates['latest_numeric']}")
        
        # 6. Summary
        print(f"\n🎯 CHARTER DATA SYNCHRONIZATION SUMMARY:")
        print(f"   LMS Total: {lms_count:,} reservations")
        print(f"   PostgreSQL Total: {total_pg:,} charters")
        print(f"   PostgreSQL Numeric: {numeric_pg_count:,} (likely from LMS)")
        print(f"   PostgreSQL REF: {total_pg - numeric_pg_count:,} (new system)")
        
        if overlap:
            print(f"   [OK] Found {len(overlap):,} overlapping records")
            print(f"   [WARN]  {len(missing_from_pg):,} LMS records not in PostgreSQL")
            print(f"   📈 {total_pg - numeric_pg_count:,} new REF-format records")
        else:
            print(f"   [FAIL] No overlapping records found - format mismatch")
            
    except Exception as e:
        print(f"[FAIL] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        pg_cur.close()
        pg_conn.close()
        lms_cur.close()
        lms_conn.close()

if __name__ == "__main__":
    main()