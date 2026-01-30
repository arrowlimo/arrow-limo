#!/usr/bin/env python
"""Find all charters with date mismatches between LMS and PostgreSQL."""
import pyodbc
import psycopg2
from datetime import datetime

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

print("Checking for charter date mismatches between LMS and PostgreSQL...")
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
not_in_lms = []

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
            # Convert both to date only (ignore time)
            lms_date_only = lms_date.date() if hasattr(lms_date, 'date') else lms_date
            pg_date_only = pg_date
            
            if lms_date_only != pg_date_only:
                mismatches.append({
                    'reserve': reserve_num,
                    'pg_date': pg_date_only,
                    'lms_date': lms_date_only,
                    'pg_total': pg_total,
                    'lms_total': lms_total,
                    'pg_paid': pg_paid,
                    'lms_paid': lms_deposit,
                    'pg_balance': pg_balance,
                    'lms_balance': lms_balance
                })
    else:
        not_in_lms.append(reserve_num)

# Report mismatches
if mismatches:
    print(f"\nFound {len(mismatches)} charter(s) with date mismatches:\n")
    print(f"{'Reserve':<10} {'PG Date':<12} {'LMS Date':<12} {'PG Total':>12} {'LMS Total':>12} {'PG Paid':>12} {'LMS Paid':>12}")
    print("-" * 100)
    
    for m in mismatches:
        print(f"{m['reserve']:<10} {str(m['pg_date']):<12} {str(m['lms_date']):<12} "
              f"${m['pg_total']:>11.2f} ${m['lms_total']:>11.2f} "
              f"${m['pg_paid']:>11.2f} ${m['lms_paid']:>11.2f}")
else:
    print("\n✓ No date mismatches found in recent 100 charters")

if not_in_lms:
    print(f"\n⚠ {len(not_in_lms)} charter(s) in PostgreSQL but NOT in LMS: {', '.join(not_in_lms[:10])}")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()

print("\n" + "=" * 100)
print(f"Total mismatches found: {len(mismatches)}")
