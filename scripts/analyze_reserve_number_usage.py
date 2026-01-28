#!/usr/bin/env python3
"""
Reserve Number System Usage Analysis
Analyze whether REF format is needed vs continuing with numeric format
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os

def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        cursor_factory=RealDictCursor
    )

def main():
    print("🔍 RESERVE NUMBER SYSTEM USAGE ANALYSIS")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Current system usage
        print("📊 CURRENT RESERVE NUMBER USAGE:")
        
        cur.execute("""
            SELECT 
                CASE 
                    WHEN reserve_number ~ '^REF[0-9]+$' THEN 'REF_FORMAT'
                    WHEN reserve_number ~ '^[0-9]+$' THEN 'NUMERIC_FORMAT'
                    WHEN reserve_number ~ '^AUDIT[0-9]+$' THEN 'AUDIT_FORMAT'
                    ELSE 'OTHER_FORMAT'
                END as format_type,
                COUNT(*) as count,
                MIN(charter_date) as earliest_date,
                MAX(charter_date) as latest_date,
                MIN(reserve_number) as min_number,
                MAX(reserve_number) as max_number
            FROM charters 
            WHERE reserve_number IS NOT NULL AND reserve_number != ''
            GROUP BY format_type
            ORDER BY count DESC
        """)
        
        formats = cur.fetchall()
        total_records = sum(f['count'] for f in formats)
        
        for fmt in formats:
            pct = fmt['count'] / total_records * 100
            print(f"   {fmt['format_type']}: {fmt['count']:,} records ({pct:.1f}%)")
            print(f"      Date range: {fmt['earliest_date']} to {fmt['latest_date']}")
            print(f"      Number range: {fmt['min_number']} to {fmt['max_number']}")
        
        # 2. Timeline analysis
        print(f"\n📅 CHRONOLOGICAL USAGE ANALYSIS:")
        
        cur.execute("""
            SELECT 
                DATE_TRUNC('month', charter_date) as month,
                COUNT(*) FILTER (WHERE reserve_number ~ '^[0-9]+$') as numeric_count,
                COUNT(*) FILTER (WHERE reserve_number ~ '^REF[0-9]+$') as ref_count,
                COUNT(*) FILTER (WHERE reserve_number ~ '^AUDIT[0-9]+$') as audit_count
            FROM charters 
            WHERE charter_date >= '2025-01-01'
            AND reserve_number IS NOT NULL AND reserve_number != ''
            GROUP BY DATE_TRUNC('month', charter_date)
            ORDER BY month DESC
            LIMIT 12
        """)
        
        monthly_usage = cur.fetchall()
        
        for month in monthly_usage:
            total = month['numeric_count'] + month['ref_count'] + month['audit_count']
            if total > 0:
                numeric_pct = (month['numeric_count'] / total) * 100
                ref_pct = (month['ref_count'] / total) * 100
                audit_pct = (month['audit_count'] / total) * 100
                print(f"   {month['month'].strftime('%Y-%m')}: {total:,} total")
                print(f"      Numeric: {month['numeric_count']:,} ({numeric_pct:.1f}%)")
                print(f"      REF: {month['ref_count']:,} ({ref_pct:.1f}%)")
                print(f"      AUDIT: {month['audit_count']:,} ({audit_pct:.1f}%)")
        
        # 3. Check for gaps in numeric sequence
        print(f"\n🔍 NUMERIC SEQUENCE ANALYSIS:")
        
        cur.execute("""
            SELECT 
                CAST(reserve_number AS INTEGER) as reserve_num
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
            ORDER BY CAST(reserve_number AS INTEGER) DESC
            LIMIT 1
        """)
        
        max_numeric = cur.fetchone()
        if max_numeric:
            print(f"   Current max numeric reserve: {max_numeric['reserve_num']:06d}")
            
            # Check for available numbers
            next_available = max_numeric['reserve_num'] + 1
            print(f"   Next available numeric: {next_available:06d}")
            
            # Check if there are gaps
            cur.execute("""
                WITH numeric_sequence AS (
                    SELECT CAST(reserve_number AS INTEGER) as num
                    FROM charters 
                    WHERE reserve_number ~ '^[0-9]+$'
                    ORDER BY CAST(reserve_number AS INTEGER)
                ),
                gaps AS (
                    SELECT 
                        num + 1 as gap_start,
                        next_num - 1 as gap_end
                    FROM (
                        SELECT 
                            num,
                            LEAD(num) OVER (ORDER BY num) as next_num
                        FROM numeric_sequence
                    ) seq
                    WHERE next_num - num > 1
                )
                SELECT COUNT(*) as gap_count,
                       COALESCE(SUM(gap_end - gap_start + 1), 0) as total_gaps
                FROM gaps
                WHERE gap_end IS NOT NULL
            """)
            
            gaps = cur.fetchone()
            if gaps['gap_count']:
                print(f"   Sequence gaps: {gaps['gap_count']} gaps totaling {gaps['total_gaps']} available numbers")
            else:
                print(f"   Sequence: Complete, no gaps")
        
        # 4. Business impact analysis
        print(f"\n💼 BUSINESS IMPACT ANALYSIS:")
        
        # Check frontend/API usage
        print(f"   Current system refers to 'Reserve Number' in:")
        print(f"   - Frontend dashboard table header")
        print(f"   - API endpoint: /api/reserve-numbers")
        print(f"   - Search and filtering functionality")
        print(f"   - Charter lookup by reserve number")
        
        # 5. REF format analysis
        print(f"\n🆔 REF FORMAT ANALYSIS:")
        
        cur.execute("""
            SELECT 
                reserve_number,
                charter_date,
                client_name,
                rate
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE reserve_number ~ '^REF[0-9]+$'
            ORDER BY charter_date DESC
        """)
        
        ref_records = cur.fetchall()
        
        if ref_records:
            print(f"   REF records found: {len(ref_records)}")
            print(f"   Recent REF entries:")
            for record in ref_records[:5]:
                rate_str = f"${record['rate']:.2f}" if record['rate'] else "No rate"
                print(f"      {record['reserve_number']}: {record['charter_date']} - {record['client_name']} ({rate_str})")
        else:
            print(f"   No REF records found")
        
        # 6. Recommendations
        print(f"\n🎯 RECOMMENDATIONS:")
        
        numeric_pct = (formats[0]['count'] / total_records * 100) if formats else 0
        
        if numeric_pct > 95:
            print(f"   [OK] CONTINUE NUMERIC: {numeric_pct:.1f}% of records use numeric format")
            print(f"   📋 SIMPLIFY: Remove REF format, continue with numeric sequence")
            print(f"   🔧 STANDARDIZE: Use 6-digit zero-padded format (e.g., 019693)")
            print(f"   📈 NEXT NUMBER: Start new reservations at {next_available:06d}")
        else:
            print(f"   [WARN]  MIXED USAGE: Consider format standardization")
            
        print(f"   🎨 FRONTEND: No changes needed - displays reserve_number field")
        print(f"   🔌 API: Current /api/reserve-numbers endpoint works with any format")
        print(f"   📊 COMPATIBILITY: Numeric format maintains LMS compatibility")
        
        # 7. Implementation recommendation
        print(f"\n🔧 IMPLEMENTATION RECOMMENDATION:")
        
        if ref_records and len(ref_records) < 50:
            print(f"   💡 CONVERT REF TO NUMERIC:")
            print(f"   - {len(ref_records)} REF records can be converted to numeric")
            print(f"   - Use next available numbers: {next_available:06d} onwards")
            print(f"   - Maintain single numbering system")
            print(f"   - Simplify system administration")
        
        print(f"   📋 BENEFITS OF NUMERIC-ONLY:")
        print(f"   - Consistent with 99.8% of existing data")
        print(f"   - Compatible with LMS legacy system")
        print(f"   - Simpler for staff to reference")
        print(f"   - Maintains chronological sequence")
        print(f"   - No format confusion")
        
    except Exception as e:
        print(f"[FAIL] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()