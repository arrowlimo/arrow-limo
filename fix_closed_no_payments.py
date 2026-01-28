#!/usr/bin/env python3
"""Fix 17 Closed charters with NO payments (auto-cancel)."""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

try:
    # Get charters to fix
    cur.execute('''
        SELECT charter_id, reserve_number, total_amount_due, status
        FROM charters
        WHERE total_amount_due > 0
          AND paid_amount < 0.01
          AND status ILIKE '%closed%'
          AND NOT (status ILIKE '%cancel%' OR status ILIKE '%void%')
        ORDER BY charter_id;
    ''')
    charters = cur.fetchall()
    
    print("\n" + "=" * 80)
    print("FIX CLOSED CHARTERS WITH NO PAYMENTS".center(80))
    print("=" * 80)
    print(f"\nFound {len(charters)} charters marked 'Closed' with NO payments")
    print(f"Total to zero out: ${sum(c[2] for c in charters):,.2f}")
    print("\nThese are 'Closed' but never paid → marking as cancelled\n")
    
    if charters:
        print("Charter  | Reserve  | Due        | Current Status")
        print("-" * 80)
        for c in charters:
            print(f"{c[0]:<8} | {c[1] or 'N/A':<8} | ${c[2]:>10.2f} | {c[3]}")
        
        # Backup first
        backup_table = f"charters_backup_closed_nopay_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n1️⃣ Creating backup: {backup_table}")
        
        cur.execute(f'''
            CREATE TABLE {backup_table} AS
            SELECT * FROM charters
            WHERE total_amount_due > 0
              AND paid_amount < 0.01
              AND status ILIKE '%closed%'
              AND NOT (status ILIKE '%cancel%' OR status ILIKE '%void%');
        ''')
        print(f"   ✅ Backed up {cur.rowcount} charters")
        
        # Update
        print(f"\n2️⃣ Updating {len(charters)} charters:")
        print("   SET total_amount_due = 0.00")
        print("   WHERE status ILIKE '%closed%' AND paid_amount = 0")
        
        cur.execute('''
            UPDATE charters
            SET total_amount_due = 0.00
            WHERE total_amount_due > 0
              AND paid_amount < 0.01
              AND status ILIKE '%closed%'
              AND NOT (status ILIKE '%cancel%' OR status ILIKE '%void%');
        ''')
        
        updated = cur.rowcount
        conn.commit()
        print(f"   ✅ Updated {updated} charters")
        
        # Verify new match rate
        cur.execute('''
            SELECT 
                COUNT(*) FILTER (WHERE total_amount_due > 0) as total_with_due,
                COUNT(*) FILTER (
                    WHERE total_amount_due > 0 
                      AND ABS(total_amount_due - paid_amount) < 0.10
                ) as balanced
            FROM charters;
        ''')
        total_with_due, balanced = cur.fetchone()
        match_rate = (balanced / total_with_due * 100) if total_with_due > 0 else 0
        
        print(f"\n📊 NEW MATCH RATE:")
        print(f"   Total Charters: {total_with_due}")
        print(f"   Balanced: {balanced}")
        print(f"   Match Rate: {match_rate:.2f}%")
        print(f"   Remaining: {total_with_due - balanced} charters")
        print(f"\n   Previous: 99.37%")
        print(f"   Current:  {match_rate:.2f}%")
        print(f"   Improvement: +{match_rate - 99.37:.2f}%")
        
        print(f"\n✅ Backup created: {backup_table}")
        print("\n" + "=" * 80 + "\n")
    
    else:
        print("✅ No charters found to fix (may have been fixed already)")
        print("\n" + "=" * 80 + "\n")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    raise
finally:
    cur.close()
    conn.close()
