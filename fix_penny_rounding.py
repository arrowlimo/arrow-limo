#!/usr/bin/env python3
"""Fix penny rounding issues (6 charters)."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

try:
    # Get penny rounding charters
    cur.execute('''
        SELECT charter_id, reserve_number, total_amount_due, paid_amount, 
               (total_amount_due - paid_amount) as balance
        FROM charters
        WHERE total_amount_due > 0
          AND ABS(total_amount_due - paid_amount) < 1.00
          AND ABS(total_amount_due - paid_amount) >= 0.10
        ORDER BY charter_id;
    ''')
    charters = cur.fetchall()
    
    print("\n" + "=" * 80)
    print("FIX PENNY ROUNDING ISSUES".center(80))
    print("=" * 80)
    print(f"\nFound {len(charters)} charters with penny rounding issues")
    print(f"Total adjustment: ${sum(abs(c[4]) for c in charters):.2f}\n")
    
    print("Charter  | Reserve  | Due       | Paid      | Balance  ")
    print("-" * 80)
    for c in charters:
        print(f"{c[0]:<8} | {c[1] or 'N/A':<8} | ${c[2]:>8.2f} | ${c[3]:>8.2f} | ${c[4]:>8.2f}")
    
    # Update
    print(f"\n🔧 Updating {len(charters)} charters: SET total_amount_due = paid_amount")
    
    cur.execute('''
        UPDATE charters
        SET total_amount_due = paid_amount
        WHERE total_amount_due > 0
          AND ABS(total_amount_due - paid_amount) < 1.00
          AND ABS(total_amount_due - paid_amount) >= 0.10;
    ''')
    
    updated = cur.rowcount
    conn.commit()
    print(f"✅ Updated {updated} charters")
    
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
    print("\n" + "=" * 80 + "\n")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    raise
finally:
    cur.close()
    conn.close()
