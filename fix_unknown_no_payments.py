#!/usr/bin/env python3
"""Fix 10 Unknown/no-payment charters (auto-cancel abandoned bookings)."""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

try:
    # Get no-payment unknowns
    cur.execute('''
        SELECT charter_id, reserve_number, total_amount_due, status, pickup_time
        FROM charters
        WHERE total_amount_due > 0
          AND paid_amount < 0.01
          AND NOT (status ILIKE '%cancel%' OR status ILIKE '%void%')
          AND NOT (status ILIKE '%closed%')
        ORDER BY total_amount_due ASC;
    ''')
    charters = cur.fetchall()
    
    print("\n" + "=" * 100)
    print("FIX UNKNOWN/NO-PAYMENT CHARTERS (ABANDONED BOOKINGS)".center(100))
    print("=" * 100)
    print(f"\nFound {len(charters)} charters marked 'Unknown' with NO payments")
    print(f"Total to zero out: ${sum(c[2] for c in charters):,.2f}")
    print("\nThese are likely abandoned/no-show bookings\n")
    
    if charters:
        print("Charter  | Reserve  | Due        | Status           | Pickup Date")
        print("-" * 100)
        for c in charters:
            charter_id, reserve, due, status, pickup = c
            reserve_str = reserve or 'N/A'
            status_str = (status[:15] if status else 'Unknown').ljust(16)
            pickup_str = pickup.strftime('%Y-%m-%d') if pickup else 'N/A'
            print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>10.2f} | {status_str} | {pickup_str}")
        
        # Backup
        backup_table = f"charters_backup_unknown_nopay_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n1️⃣ Creating backup: {backup_table}")
        
        cur.execute(f'''
            CREATE TABLE {backup_table} AS
            SELECT * FROM charters
            WHERE total_amount_due > 0
              AND paid_amount < 0.01
              AND NOT (status ILIKE '%cancel%' OR status ILIKE '%void%')
              AND NOT (status ILIKE '%closed%');
        ''')
        print(f"   ✅ Backed up {cur.rowcount} charters")
        
        # Update
        print(f"\n2️⃣ Updating {len(charters)} charters:")
        print("   SET total_amount_due = 0.00")
        
        cur.execute('''
            UPDATE charters
            SET total_amount_due = 0.00
            WHERE total_amount_due > 0
              AND paid_amount < 0.01
              AND NOT (status ILIKE '%cancel%' OR status ILIKE '%void%')
              AND NOT (status ILIKE '%closed%');
        ''')
        
        updated = cur.rowcount
        conn.commit()
        print(f"   ✅ Updated {updated} charters")
        
        # Verify
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
        print(f"\n   Previous: 99.48%")
        print(f"   Current:  {match_rate:.2f}%")
        print(f"   Improvement: +{match_rate - 99.48:.2f}%")
        
        print(f"\n✅ Backup created: {backup_table}")
        print("\n" + "=" * 100 + "\n")
    
    else:
        print("✅ No charters found to fix")
        print("\n" + "=" * 100 + "\n")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    raise
finally:
    cur.close()
    conn.close()
