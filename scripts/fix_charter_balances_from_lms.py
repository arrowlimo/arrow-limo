#!/usr/bin/env python3
"""
Fix charter balances in PostgreSQL by copying correct values from LMS.mdb source.
This repairs the migration data integrity issue.
"""

import psycopg2
import pyodbc
import argparse

parser = argparse.ArgumentParser(description='Fix charter balances from LMS source')
parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
parser.add_argument('--year', type=int, help='Fix specific year only (e.g., 2012)')
args = parser.parse_args()

# Connect to LMS Access database
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

print("=" * 120)
print("FIXING CHARTER BALANCES FROM LMS SOURCE DATABASE")
print("=" * 120)
print(f"Mode: {'WRITE (applying changes)' if args.write else 'DRY-RUN (no changes)'}")
if args.year:
    print(f"Year filter: {args.year}")
print()

lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

# Get all charters from LMS with their balances
year_filter = ""
if args.year:
    year_filter = f"WHERE YEAR(PU_Date) = {args.year}"

print(f"Fetching charter balances from LMS.mdb...")
lms_cur.execute(f"""
    SELECT Reserve_No, Rate, Balance, Deposit
    FROM Reserve
    {year_filter}
    ORDER BY Reserve_No
""")

lms_charters = lms_cur.fetchall()
print(f"Found {len(lms_charters)} charters in LMS")

# Compare and fix balances
print("\n" + "=" * 120)
print("COMPARING BALANCES")
print("=" * 120)
print(f"{'Reserve #':<12} {'LMS Balance':<15} {'PG Balance':<15} {'Difference':<15} {'Action':<20}")
print("-" * 120)

mismatched = 0
matched = 0
not_found = 0
updates = []

for lms_charter in lms_charters:
    reserve_no, lms_rate, lms_balance, lms_deposit = lms_charter
    
    if not reserve_no:
        continue
    
    lms_bal = lms_balance if lms_balance is not None else 0
    
    # Get PostgreSQL balance
    pg_cur.execute("""
        SELECT charter_id, balance, rate
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_no,))
    
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        charter_id, pg_bal, pg_rate = pg_row
        pg_balance = pg_bal if pg_bal is not None else 0
        
        diff = pg_balance - lms_bal
        
        if abs(diff) >= 0.01:
            mismatched += 1
            action = "UPDATE" if args.write else "Would update"
            print(f"{reserve_no:<12} ${lms_bal:>12.2f} ${pg_balance:>12.2f} ${diff:>12.2f} {action:<20}")
            
            if args.write:
                updates.append((lms_bal, charter_id))
        else:
            matched += 1
    else:
        not_found += 1

print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print(f"Total LMS charters: {len(lms_charters)}")
print(f"Balances matching: {matched}")
print(f"Balances mismatched: {mismatched}")
print(f"Not found in PostgreSQL: {not_found}")

if args.write and updates:
    print("\n" + "=" * 120)
    print(f"APPLYING {len(updates)} BALANCE UPDATES...")
    print("=" * 120)
    
    # Batch update
    pg_cur.executemany("""
        UPDATE charters
        SET balance = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE charter_id = %s
    """, updates)
    
    pg_conn.commit()
    print(f"✓ Updated {len(updates)} charter balances")
    
    # Verify a sample
    print("\nVerifying sample updates:")
    pg_cur.execute("""
        SELECT c.reserve_number, c.balance, c.updated_at
        FROM charters c
        WHERE c.updated_at > NOW() - INTERVAL '1 minute'
        ORDER BY c.updated_at DESC
        LIMIT 5
    """)
    
    for reserve, balance, updated in pg_cur.fetchall():
        print(f"  {reserve}: ${balance:.2f} (updated {updated})")
        
elif not args.write:
    print("\n" + "=" * 120)
    print("DRY-RUN MODE - No changes applied")
    print(f"Run with --write flag to apply {mismatched} balance corrections")
    print("=" * 120)

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print("\n" + "=" * 120)
