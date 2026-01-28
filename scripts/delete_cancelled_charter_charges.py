"""
Delete charter_charges for CANCELLED charters.
Cancelled charters should have NO charges.
"""
import psycopg2
import os
import sys
from datetime import datetime

# Check for --execute flag
DRY_RUN = '--execute' not in sys.argv

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
conn.autocommit = False
cur = conn.cursor()

try:
    print("=" * 80)
    if DRY_RUN:
        print("DRY-RUN MODE: Delete Cancelled Charter Charges")
    else:
        print("EXECUTE MODE: Delete Cancelled Charter Charges")
    print("=" * 80)
    
    # Step 1: Backup charges to delete
    print("\n📝 Step 1: Backing up charges for cancelled charters...")
    
    backup_file = f"L:/limo/reports/legacy_table_backups/charter_charges_CANCELLED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    cur.execute(f"""
        COPY (
            SELECT cc.*
            FROM charter_charges cc
            JOIN charters c ON c.reserve_number = cc.reserve_number
            WHERE c.cancelled = TRUE
        )
        TO '{backup_file}'
        WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8')
    """)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charter_charges cc
        JOIN charters c ON c.reserve_number = cc.reserve_number
        WHERE c.cancelled = TRUE
    """)
    backup_count = cur.fetchone()[0]
    print(f"✅ Backed up {backup_count:,} charges → {backup_file}")
    
    # Step 2: Delete charges for cancelled charters
    print("\n📝 Step 2: Deleting charges for cancelled charters...")
    
    if DRY_RUN:
        cur.execute("""
            SELECT 
                cc.reserve_number,
                COUNT(cc.charge_id) as charge_count,
                SUM(cc.amount) as total_amount
            FROM charter_charges cc
            JOIN charters c ON c.reserve_number = cc.reserve_number
            WHERE c.cancelled = TRUE
            GROUP BY cc.reserve_number
            ORDER BY total_amount DESC
            LIMIT 10
        """)
        
        print("Would delete charges for these cancelled charters (top 10):")
        for reserve, count, total in cur.fetchall():
            print(f"  {reserve}: {count} charges, ${total:.2f}")
        
        print(f"\n⏸️  DRY-RUN: No charges deleted")
        print(f"   Run with --execute flag to delete {backup_count:,} charges")
    else:
        cur.execute("""
            DELETE FROM charter_charges cc
            USING charters c
            WHERE cc.reserve_number = c.reserve_number
            AND c.cancelled = TRUE
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count:,} charges for cancelled charters")
        
        # Commit
        conn.commit()
        print("✅ Changes committed")
    
    # Verification
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charter_charges cc
        JOIN charters c ON c.reserve_number = cc.reserve_number
        WHERE c.cancelled = TRUE
    """)
    remaining = cur.fetchone()[0]
    
    if DRY_RUN:
        print(f"\nCancelled charters still have {remaining:,} charges")
        print("(no changes made in dry-run mode)")
    else:
        print(f"\nCancelled charters now have {remaining:,} charges")
        if remaining == 0:
            print("✅ All charges for cancelled charters removed")
        else:
            print(f"⚠️  {remaining:,} charges still remain for cancelled charters")

except Exception as e:
    if not DRY_RUN:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        print("Changes rolled back")
    raise
finally:
    cur.close()
    conn.close()
