#!/usr/bin/env python3
"""
LMS Charter Data Completeness Summary Report
Final analysis of charter/reservation data synchronization
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os

def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
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
    print("🎯 LMS CHARTER DATA COMPLETENESS - FINAL SUMMARY")
    print("=" * 60)
    
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        # 1. System Overview
        print("📊 SYSTEM DATA OVERVIEW:")
        
        lms_cur.execute("SELECT COUNT(*) FROM Reserve")
        lms_total = lms_cur.fetchone()[0]
        
        pg_cur.execute("SELECT COUNT(*) FROM charters")
        pg_total = pg_cur.fetchone()['count']
        
        print(f"   LMS Reserve table: {lms_total:,} records")
        print(f"   PostgreSQL charters table: {pg_total:,} records")
        print(f"   Difference: {abs(lms_total - pg_total):,} records")
        
        # 2. Reserve Number Format Analysis
        print(f"\n📋 RESERVE NUMBER FORMATS:")
        
        pg_cur.execute("""
            SELECT 
                COUNT(*) as numeric_count
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
        """)
        pg_numeric = pg_cur.fetchone()['numeric_count']
        
        pg_cur.execute("""
            SELECT 
                COUNT(*) as ref_count
            FROM charters 
            WHERE reserve_number ~ '^REF[0-9]+$'
        """)
        pg_ref = pg_cur.fetchone()['ref_count']
        
        print(f"   LMS Format (numeric): {lms_total:,} records")
        print(f"   PostgreSQL Numeric: {pg_numeric:,} records ({pg_numeric/pg_total*100:.1f}%)")
        print(f"   PostgreSQL REF Format: {pg_ref:,} records ({pg_ref/pg_total*100:.1f}%)")
        
        # 3. Data Completeness Analysis
        print(f"\n🔍 DATA COMPLETENESS ANALYSIS:")
        
        # Check the gap between LMS and PostgreSQL numeric
        gap = lms_total - pg_numeric
        print(f"   LMS records: {lms_total:,}")
        print(f"   PostgreSQL numeric records: {pg_numeric:,}")
        print(f"   Missing from PostgreSQL: {gap:,} records")
        
        # 4. Range Analysis
        print(f"\n📊 RESERVE NUMBER RANGES:")
        
        lms_cur.execute("SELECT MIN(Reserve_No), MAX(Reserve_No) FROM Reserve WHERE Reserve_No IS NOT NULL")
        lms_min, lms_max = lms_cur.fetchone()
        
        pg_cur.execute("""
            SELECT 
                MIN(CAST(reserve_number AS INTEGER)) as min_num,
                MAX(CAST(reserve_number AS INTEGER)) as max_num
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
        """)
        pg_range = pg_cur.fetchone()
        
        print(f"   LMS range: {lms_min} to {lms_max}")
        print(f"   PostgreSQL numeric range: {pg_range['min_num']:06d} to {pg_range['max_num']:06d}")
        
        # 5. Missing Range Analysis
        lms_min_int = int(lms_min)
        lms_max_int = int(lms_max)
        pg_min_int = pg_range['min_num']
        pg_max_int = pg_range['max_num']
        
        print(f"\n[WARN]  MISSING DATA ANALYSIS:")
        
        if pg_max_int < lms_max_int:
            missing_recent = lms_max_int - pg_max_int
            print(f"   Missing recent records: {missing_recent:,} (Reserve {pg_max_int+1:06d} to {lms_max_int:06d})")
        
        # 6. Date Analysis
        print(f"\n📅 DATE RANGE ANALYSIS:")
        
        lms_cur.execute("SELECT MIN(PU_Date), MAX(PU_Date) FROM Reserve")
        lms_date_min, lms_date_max = lms_cur.fetchone()
        
        pg_cur.execute("SELECT MIN(charter_date), MAX(charter_date) FROM charters")
        pg_date_min, pg_date_max = pg_cur.fetchone()
        
        print(f"   LMS date range: {lms_date_min} to {lms_date_max}")
        print(f"   PostgreSQL date range: {pg_date_min} to {pg_date_max}")
        
        # 7. Financial Impact
        print(f"\n💰 FINANCIAL IMPACT ANALYSIS:")
        
        # Check financial data in missing range
        if pg_max_int < lms_max_int:
            lms_cur.execute(f"""
                SELECT 
                    COUNT(*) as missing_count,
                    SUM(IIF(Rate IS NOT NULL, Rate, 0)) as missing_revenue,
                    SUM(IIF(Balance IS NOT NULL, Balance, 0)) as missing_balance
                FROM Reserve 
                WHERE Reserve_No > '{pg_max_int:06d}'
            """)
            missing_data = lms_cur.fetchone()
            
            if missing_data[0] > 0:
                print(f"   Missing records: {missing_data[0]:,}")
                print(f"   Missing revenue: ${missing_data[1]:,.2f}" if missing_data[1] else "   Missing revenue: $0.00")
                print(f"   Missing balance: ${missing_data[2]:,.2f}" if missing_data[2] else "   Missing balance: $0.00")
        
        # 8. Recommendations
        print(f"\n🎯 RECOMMENDATIONS:")
        
        if gap > 0:
            print(f"   [WARN]  CRITICAL: {gap:,} LMS records missing from PostgreSQL")
            print(f"   📋 ACTION: Import missing Reserve records {pg_max_int+1:06d} to {lms_max_int:06d}")
            print(f"   🔄 UPDATE: Implement incremental sync for ongoing LMS updates")
        else:
            print(f"   [OK] All LMS records appear to be imported")
            
        print(f"   📊 MONITOR: REF-format records represent new system growth")
        print(f"   🔄 MAINTAIN: Regular sync between LMS and PostgreSQL systems")
        
        # 9. Final Status
        print(f"\n🏁 FINAL CHARTER DATA STATUS:")
        
        completeness_pct = (pg_numeric / lms_total) * 100 if lms_total > 0 else 100
        
        print(f"   Data Completeness: {completeness_pct:.1f}%")
        
        if completeness_pct >= 99.5:
            print(f"   Status: [OK] EXCELLENT - Minimal data gap")
        elif completeness_pct >= 95.0:
            print(f"   Status: [WARN]  GOOD - Minor sync needed")
        else:
            print(f"   Status: 🔴 CRITICAL - Major sync required")
            
        print(f"   System Evolution: Legacy LMS → PostgreSQL + New REF system")
        
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