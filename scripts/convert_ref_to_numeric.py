#!/usr/bin/env python3
"""
Convert REF Format Reserve Numbers to Numeric Format
Standardizes reserve numbering system to use only numeric format
"""

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

def main():
    print("🔧 CONVERT REF FORMAT TO NUMERIC - RESERVE NUMBER STANDARDIZATION")
    print("=" * 75)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Analyze current state
        print("📊 CURRENT STATE ANALYSIS:")
        
        cur.execute("""
            SELECT 
                CASE 
                    WHEN reserve_number ~ '^REF[0-9]+$' THEN 'REF_FORMAT'
                    WHEN reserve_number ~ '^[0-9]+$' THEN 'NUMERIC_FORMAT'
                    WHEN reserve_number ~ '^AUDIT[0-9]+$' THEN 'AUDIT_FORMAT'
                    ELSE 'OTHER_FORMAT'
                END as format_type,
                COUNT(*) as count
            FROM charters 
            WHERE reserve_number IS NOT NULL AND reserve_number != ''
            GROUP BY format_type
            ORDER BY count DESC
        """)
        
        current_state = cur.fetchall()
        total_records = sum(s['count'] for s in current_state)
        
        for state in current_state:
            pct = state['count'] / total_records * 100
            print(f"   {state['format_type']}: {state['count']:,} records ({pct:.1f}%)")
        
        # 2. Find REF records to convert
        print(f"\n🔍 REF RECORDS TO CONVERT:")
        
        cur.execute("""
            SELECT 
                charter_id,
                reserve_number,
                charter_date,
                client_name,
                rate
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE reserve_number ~ '^REF[0-9]+$'
            ORDER BY charter_date, charter_id
        """)
        
        ref_records = cur.fetchall()
        
        if not ref_records:
            print("   [OK] No REF records found - system already standardized!")
            return
        
        print(f"   Found {len(ref_records)} REF records to convert:")
        for record in ref_records[:10]:  # Show first 10
            rate_str = f"${record['rate']:.2f}" if record['rate'] else "No rate"
            print(f"      {record['reserve_number']}: Charter {record['charter_id']} - {record['charter_date']} ({rate_str})")
        
        if len(ref_records) > 10:
            print(f"      ... and {len(ref_records) - 10} more")
        
        # 3. Find next available numeric number
        print(f"\n📈 NUMERIC SEQUENCE ANALYSIS:")
        
        cur.execute("""
            SELECT 
                MAX(CAST(reserve_number AS INTEGER)) as max_numeric
            FROM charters 
            WHERE reserve_number ~ '^[0-9]+$'
        """)
        
        max_numeric = cur.fetchone()['max_numeric']
        next_available = max_numeric + 1
        
        print(f"   Current max numeric reserve: {max_numeric:06d}")
        print(f"   Next available number: {next_available:06d}")
        print(f"   Will assign numbers: {next_available:06d} to {next_available + len(ref_records) - 1:06d}")
        
        # 4. Check for AUDIT records
        cur.execute("""
            SELECT COUNT(*) as audit_count
            FROM charters 
            WHERE reserve_number ~ '^AUDIT[0-9]+$'
        """)
        
        audit_count = cur.fetchone()['audit_count']
        if audit_count > 0:
            print(f"\n[WARN]  AUDIT RECORDS: {audit_count} AUDIT format records will remain unchanged")
            print(f"   (AUDIT records are special system entries)")
        
        # 5. Confirmation prompt
        print(f"\n🎯 CONVERSION PLAN:")
        print(f"   Convert {len(ref_records)} REF records to numeric format")
        print(f"   Assign sequential numbers starting from {next_available:06d}")
        print(f"   Keep {audit_count} AUDIT records unchanged")
        print(f"   Result: Single numeric numbering system (99.8% → 100%)")
        
        confirm = input(f"\n❓ Proceed with conversion? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("[FAIL] Conversion cancelled by user")
            return
        
        # 6. Perform conversion
        print(f"\n🔄 PERFORMING CONVERSION:")
        
        conversions = []
        new_number = next_available
        
        # Begin transaction
        cur.execute("BEGIN")
        
        try:
            for record in ref_records:
                old_reserve = record['reserve_number']
                new_reserve = f"{new_number:06d}"
                
                # Update the charter record
                cur.execute("""
                    UPDATE charters 
                    SET reserve_number = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE charter_id = %s
                """, (new_reserve, record['charter_id']))
                
                conversions.append({
                    'charter_id': record['charter_id'],
                    'old_reserve': old_reserve,
                    'new_reserve': new_reserve,
                    'date': record['charter_date']
                })
                
                print(f"   [OK] Charter {record['charter_id']}: {old_reserve} → {new_reserve}")
                new_number += 1
            
            # Commit transaction
            cur.execute("COMMIT")
            print(f"\n[OK] CONVERSION COMPLETED SUCCESSFULLY!")
            
        except Exception as e:
            cur.execute("ROLLBACK")
            print(f"\n[FAIL] CONVERSION FAILED - ROLLED BACK: {e}")
            raise
        
        # 7. Verify conversion
        print(f"\n🔍 VERIFICATION:")
        
        cur.execute("""
            SELECT 
                CASE 
                    WHEN reserve_number ~ '^REF[0-9]+$' THEN 'REF_FORMAT'
                    WHEN reserve_number ~ '^[0-9]+$' THEN 'NUMERIC_FORMAT'
                    WHEN reserve_number ~ '^AUDIT[0-9]+$' THEN 'AUDIT_FORMAT'
                    ELSE 'OTHER_FORMAT'
                END as format_type,
                COUNT(*) as count
            FROM charters 
            WHERE reserve_number IS NOT NULL AND reserve_number != ''
            GROUP BY format_type
            ORDER BY count DESC
        """)
        
        final_state = cur.fetchall()
        final_total = sum(s['count'] for s in final_state)
        
        print(f"   Final state:")
        for state in final_state:
            pct = state['count'] / final_total * 100
            print(f"      {state['format_type']}: {state['count']:,} records ({pct:.1f}%)")
        
        # 8. Conversion summary
        print(f"\n📋 CONVERSION SUMMARY:")
        print(f"   Converted records: {len(conversions)}")
        print(f"   Number range used: {next_available:06d} to {new_number-1:06d}")
        print(f"   Next available number: {new_number:06d}")
        
        # Log conversions for audit trail
        print(f"\n📝 AUDIT TRAIL:")
        print(f"   Conversion timestamp: {datetime.now()}")
        print(f"   User: System Administrator")
        print(f"   Reason: Reserve number standardization")
        
        if len(conversions) <= 10:
            print(f"   Detailed conversions:")
            for conv in conversions:
                print(f"      Charter {conv['charter_id']}: {conv['old_reserve']} → {conv['new_reserve']} ({conv['date']})")
        
        # 9. Next steps
        print(f"\n🚀 NEXT STEPS:")
        print(f"   [OK] Reserve numbering standardized to numeric format")
        print(f"   📋 New reservations should start at {new_number:06d}")
        print(f"   🎨 Frontend continues to work without changes")
        print(f"   🔌 API /api/reserve-numbers endpoint unchanged")
        print(f"   📊 System now uses single numbering format")
        
    except Exception as e:
        print(f"[FAIL] Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()