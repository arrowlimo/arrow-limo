"""
Sync cancelled flags from LMS to PostgreSQL.
LMS is the source of truth - only updates PostgreSQL to match LMS.
"""
import pyodbc
import psycopg2
import os
from datetime import datetime

# LMS Connection
LMS_PATH = r'L:\limo\backups\lms.mdb'
if not os.path.exists(LMS_PATH):
    LMS_PATH = r'L:\limo\lms.mdb'

lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# PostgreSQL Connection
pg_conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
pg_cur = pg_conn.cursor()

print("=" * 100)
print("CANCELLED FLAG AUDIT - LMS → POSTGRESQL")
print("=" * 100)
print(f"LMS Database: {LMS_PATH}")
print()

# Get all charters with their cancelled status from LMS
print("📋 Loading LMS cancelled flags...")
lms_cur.execute("""
    SELECT Reserve_No, Cancelled
    FROM Reserve
    WHERE Reserve_No IS NOT NULL
    ORDER BY Reserve_No
""")
lms_data = {row.Reserve_No.strip(): (row.Cancelled or False) for row in lms_cur.fetchall()}
print(f"   Loaded {len(lms_data)} LMS reserves")

# Get all charters from PostgreSQL
print("📋 Loading PostgreSQL cancelled flags...")
pg_cur.execute("""
    SELECT reserve_number, cancelled, charter_id
    FROM charters
    WHERE reserve_number IS NOT NULL
    ORDER BY reserve_number
""")
pg_data = {row[0]: {'cancelled': (row[1] or False), 'charter_id': row[2]} for row in pg_cur.fetchall()}
print(f"   Loaded {len(pg_data)} PostgreSQL charters")
print()

# Find discrepancies
discrepancies = []
for reserve_num, pg_info in pg_data.items():
    if reserve_num in lms_data:
        lms_cancelled = lms_data[reserve_num]
        pg_cancelled = pg_info['cancelled']
        
        if lms_cancelled != pg_cancelled:
            discrepancies.append({
                'reserve_number': reserve_num,
                'charter_id': pg_info['charter_id'],
                'lms_cancelled': lms_cancelled,
                'pg_cancelled': pg_cancelled
            })

print("=" * 100)
print(f"FOUND {len(discrepancies)} DISCREPANCIES")
print("=" * 100)

if discrepancies:
    print()
    print("MISMATCHED CANCELLED FLAGS:")
    print("-" * 100)
    print(f"{'Reserve':<12} {'Charter ID':<12} {'LMS Status':<20} {'PostgreSQL Status':<20}")
    print("-" * 100)
    
    for disc in discrepancies[:50]:  # Show first 50
        lms_status = "CANCELLED" if disc['lms_cancelled'] else "NOT CANCELLED"
        pg_status = "CANCELLED" if disc['pg_cancelled'] else "NOT CANCELLED"
        print(f"{disc['reserve_number']:<12} {disc['charter_id']:<12} {lms_status:<20} {pg_status:<20}")
    
    if len(discrepancies) > 50:
        print(f"... and {len(discrepancies) - 50} more")
    
    print()
    print("=" * 100)
    print("UPDATE SUMMARY:")
    print("=" * 100)
    
    to_cancel = [d for d in discrepancies if d['lms_cancelled'] and not d['pg_cancelled']]
    to_uncancel = [d for d in discrepancies if not d['lms_cancelled'] and d['pg_cancelled']]
    
    print(f"Charters to CANCEL in PostgreSQL: {len(to_cancel)}")
    print(f"Charters to UNCANCEL in PostgreSQL: {len(to_uncancel)}")
    print()
    
    # Show which ones will be cancelled
    if to_cancel:
        print("WILL BE MARKED AS CANCELLED:")
        for disc in to_cancel[:20]:
            print(f"   {disc['reserve_number']} (charter_id {disc['charter_id']})")
        if len(to_cancel) > 20:
            print(f"   ... and {len(to_cancel) - 20} more")
        print()
    
    # Show which ones will be uncancelled
    if to_uncancel:
        print("WILL BE MARKED AS NOT CANCELLED:")
        for disc in to_uncancel[:20]:
            print(f"   {disc['reserve_number']} (charter_id {disc['charter_id']})")
        if len(to_uncancel) > 20:
            print(f"   ... and {len(to_uncancel) - 20} more")
        print()
    
    print("=" * 100)
    print("DRY RUN - No changes made")
    print("Run with --apply to update PostgreSQL to match LMS")
    print("=" * 100)
    
    # Check for --apply flag
    import sys
    if '--apply' in sys.argv:
        print()
        print("APPLYING UPDATES...")
        print()
        
        # Create backup
        backup_table = f"charters_cancelled_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pg_cur.execute(f"""
            CREATE TABLE {backup_table} AS 
            SELECT charter_id, reserve_number, cancelled 
            FROM charters 
            WHERE charter_id IN ({','.join(str(d['charter_id']) for d in discrepancies)})
        """)
        print(f"✓ Backup created: {backup_table}")
        
        # Apply updates
        updated = 0
        for disc in discrepancies:
            pg_cur.execute("""
                UPDATE charters 
                SET cancelled = %s
                WHERE charter_id = %s
            """, (disc['lms_cancelled'], disc['charter_id']))
            updated += 1
            
            if updated % 100 == 0:
                print(f"   Updated {updated} charters...")
        
        pg_conn.commit()
        print(f"✓ Updated {updated} charters")
        print()
        print("=" * 100)
        print("SUCCESS! PostgreSQL cancelled flags now match LMS")
        print("=" * 100)
        print(f"Backup table: {backup_table}")
        print(f"Rollback: UPDATE charters c SET cancelled = b.cancelled FROM {backup_table} b WHERE c.charter_id = b.charter_id;")
    
else:
    print()
    print("✓ ALL CANCELLED FLAGS MATCH!")
    print("PostgreSQL and LMS are in sync.")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
