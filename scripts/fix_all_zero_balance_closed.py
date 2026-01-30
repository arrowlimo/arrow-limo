#!/usr/bin/env python3
"""
Fix ALL charters with $0 or NULL balance that aren't marked closed.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FIX ALL $0/NULL BALANCE CHARTERS - SET CLOSED FLAG")
    print("="*80)
    
    # Find all charters with $0 or NULL balance not closed
    cur.execute("""
        SELECT charter_id, reserve_number, balance, closed, status
        FROM charters
        WHERE COALESCE(balance, 0) = 0
        AND COALESCE(closed, FALSE) = FALSE
        AND COALESCE(cancelled, FALSE) = FALSE
        ORDER BY charter_id
    """)
    
    charters = cur.fetchall()
    
    print(f"\nFound {len(charters):,} charters to fix")
    
    if not charters:
        print("✓ All charters are properly closed!")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print(f"\nSample (first 10):")
    for charter in charters[:10]:
        charter_id, reserve, balance, closed, status = charter
        print(f"  {reserve}: balance={balance}, closed={closed}, status={status}")
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_zero_balance_fix_{timestamp}'
    
    charter_ids = [str(c[0]) for c in charters]
    charter_ids_str = ','.join(charter_ids)
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM charters
        WHERE charter_id IN ({charter_ids_str})
    """)
    
    print(f"\n✓ Created backup: {backup_table}")
    
    # Update all at once
    cur.execute(f"""
        UPDATE charters
        SET closed = TRUE,
            status = CASE 
                WHEN status IS NULL OR status IN ('N/A', 'UNCLOSED', '') THEN 'Closed'
                ELSE status
            END
        WHERE charter_id IN ({charter_ids_str})
    """)
    
    updated_count = cur.rowcount
    conn.commit()
    
    print(f"✓ Updated {updated_count:,} charters")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE COALESCE(balance, 0) = 0
        AND COALESCE(closed, FALSE) = FALSE
        AND COALESCE(cancelled, FALSE) = FALSE
    """)
    
    remaining = cur.fetchone()[0]
    
    print(f"\n{'='*80}")
    print("COMPLETE!")
    print(f"{'='*80}")
    print(f"✓ Fixed {updated_count:,} charters")
    print(f"✓ Remaining: {remaining:,}")
    print(f"{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
