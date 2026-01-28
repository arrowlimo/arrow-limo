#!/usr/bin/env python3
"""Execute: Zero out cancelled charters to reach 99.35% match rate."""
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
    # Backup affected charters first
    backup_table = f"charters_backup_cancelled_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("\n" + "=" * 120)
    print("EXECUTING: ZERO OUT CANCELLED CHARTERS".center(120))
    print("=" * 120)
    
    print(f"\n1️⃣ Creating backup table: {backup_table}")
    cur.execute(f'''
        CREATE TABLE {backup_table} AS
        SELECT * FROM charters
        WHERE total_amount_due > 0
          AND paid_amount < 0.01
          AND (status ILIKE '%cancel%' OR status ILIKE '%void%');
    ''')
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"   ✅ Backed up {backup_count} charters to {backup_table}")
    
    print(f"\n2️⃣ Executing UPDATE to zero out cancelled charters...")
    cur.execute('''
        UPDATE charters
        SET total_amount_due = 0.00
        WHERE total_amount_due > 0
          AND paid_amount < 0.01
          AND (status ILIKE '%cancel%' OR status ILIKE '%void%');
    ''')
    
    updated_count = cur.rowcount
    print(f"   ✅ Updated {updated_count} charters")
    
    print(f"\n3️⃣ Committing transaction...")
    conn.commit()
    print(f"   ✅ Changes committed to database")
    
    # Verify new match rate
    print(f"\n4️⃣ Verifying new match rate...")
    cur.execute('''
        SELECT COUNT(*) as total_charters
        FROM charters
        WHERE total_amount_due > 0;
    ''')
    total_charters = cur.fetchone()[0]
    
    cur.execute('''
        SELECT COUNT(*) as balanced_count
        FROM charters c
        WHERE c.total_amount_due > 0
          AND ABS(c.total_amount_due - c.paid_amount) < 0.10;
    ''')
    balanced_count = cur.fetchone()[0]
    
    match_rate = 100 * balanced_count / total_charters if total_charters > 0 else 0
    
    print(f"\n" + "=" * 120)
    print("RESULTS".center(120))
    print("=" * 120)
    print(f"\n✅ Successfully zeroed out {updated_count} cancelled charters")
    print(f"✅ Backup table created: {backup_table}")
    print(f"\n📊 NEW MATCH RATE:")
    print(f"   Total Charters (with amount due): {total_charters:,}")
    print(f"   Balanced Charters: {balanced_count:,}")
    print(f"   Match Rate: {match_rate:.2f}%")
    print(f"\n   Previous: 97.91%")
    print(f"   Current:  {match_rate:.2f}%")
    print(f"   Improvement: +{match_rate - 97.91:.2f}%")
    
    print("\n" + "=" * 120 + "\n")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print(f"   Rolling back transaction...")
    conn.rollback()
    print(f"   ✅ Rollback complete - no changes made")
    
finally:
    cur.close()
    conn.close()
