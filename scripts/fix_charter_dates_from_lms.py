#!/usr/bin/env python
"""Fix charter dates by syncing from LMS to PostgreSQL."""
import pyodbc
import psycopg2
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description='Fix charter dates from LMS')
parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
args = parser.parse_args()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***',
    host='localhost'
)
pg_cur = pg_conn.cursor()

# Connect to LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("=" * 100)
print("FIXING CHARTER DATES FROM LMS")
print("=" * 100)

# Get all charters from PostgreSQL with dates
pg_cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE charter_date IS NOT NULL
    AND reserve_number IS NOT NULL
    ORDER BY reserve_number DESC
    LIMIT 100
""")
pg_charters = {row[0]: row for row in pg_cur.fetchall()}

mismatches = []

for reserve_num, pg_data in pg_charters.items():
    pg_reserve, pg_date, pg_total, pg_paid, pg_balance = pg_data
    
    # Check LMS
    lms_cur.execute("""
        SELECT Reserve_No, PU_Date, Est_Charge, Deposit, Balance
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve_num,))
    
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        lms_reserve, lms_date, lms_total, lms_deposit, lms_balance = lms_row
        
        # Compare dates
        if lms_date and pg_date:
            lms_date_only = lms_date.date() if hasattr(lms_date, 'date') else lms_date
            pg_date_only = pg_date
            
            if lms_date_only != pg_date_only:
                mismatches.append({
                    'reserve': reserve_num,
                    'pg_date': pg_date_only,
                    'lms_date': lms_date_only
                })

if not mismatches:
    print("\n✓ No date mismatches found!")
    pg_cur.close()
    pg_conn.close()
    lms_cur.close()
    lms_conn.close()
    exit(0)

print(f"\nFound {len(mismatches)} charter(s) with incorrect dates\n")

if args.write:
    print("APPLYING FIXES...")
    
    # Create backup first
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_date_backup_{timestamp}'
    
    pg_cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM charters
        WHERE reserve_number IN ({','.join([f"'{m['reserve']}'" for m in mismatches])})
    """)
    print(f"✓ Created backup table: {backup_table} ({len(mismatches)} rows)")
    
    # Fix each charter
    fixed_count = 0
    for m in mismatches:
        pg_cur.execute("""
            UPDATE charters
            SET charter_date = %s
            WHERE reserve_number = %s
        """, (m['lms_date'], m['reserve']))
        
        fixed_count += 1
        print(f"  Fixed {m['reserve']}: {m['pg_date']} → {m['lms_date']}")
    
    pg_conn.commit()
    print(f"\n✓ Fixed {fixed_count} charter dates")
    print(f"✓ Backup saved to: {backup_table}")
    
else:
    print("DRY RUN - showing what would be fixed:\n")
    print(f"{'Reserve':<10} {'Current (PG)':<15} {'Correct (LMS)':<15}")
    print("-" * 50)
    for m in mismatches:
        print(f"{m['reserve']:<10} {str(m['pg_date']):<15} {str(m['lms_date']):<15}")
    
    print(f"\nRun with --write to apply these {len(mismatches)} fixes")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()

print("=" * 100)
