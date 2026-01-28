#!/usr/bin/env python3
"""
Drop 5 empty staging tables that are safe to remove.
All have 0 rows and no foreign key references.
"""

import psycopg2
from datetime import datetime

def main():
    print(f"\n{'='*80}")
    print("DROP EMPTY STAGING TABLES")
    print(f"{'='*80}\n")
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    tables_to_drop = [
        'ocr_documents_staging',
        'pre_inspection_templates',
        'qb_excel_staging',
        'receipts_gst_staging',
        'staging_t4_validation'
    ]
    
    try:
        # Verify they're still empty
        print("Verifying tables are empty...")
        for table in tables_to_drop:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))")
            size = cur.fetchone()[0]
            print(f"  {table:<40} {count} rows, {size}")
            
            if count > 0:
                print(f"⚠️  WARNING: {table} now has {count} rows. Skipping!")
                tables_to_drop.remove(table)
        
        if not tables_to_drop:
            print("\n✅ All tables now have data. No cleanup needed.")
            return
        
        # Drop tables
        print(f"\nDropping {len(tables_to_drop)} empty tables...")
        dropped = []
        for table in tables_to_drop:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"  ✅ Dropped: {table}")
            dropped.append(table)
        
        conn.commit()
        
        print(f"\n{'='*80}")
        print("✅ CLEANUP COMPLETE")
        print(f"{'='*80}\n")
        print(f"Dropped {len(dropped)} empty staging tables:")
        for table in dropped:
            print(f"  - {table}")
        
        print(f"\nSpace reclaimed: ~{len(dropped) * 16}kB (minimal)")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
