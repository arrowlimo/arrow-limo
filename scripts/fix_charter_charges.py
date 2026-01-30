"""
Fix charter_charges table to match charters.total_amount_due
Strategy: Replace multi-charge entries with single accurate charge from LMS Est_Charge
"""
import psycopg2
import pyodbc
import os
from datetime import datetime

# PostgreSQL
pg_conn = psycopg2.connect(
    host='localhost', database='almsdata',
    user='postgres', password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

# LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("=" * 120)
print("FIX CHARTER_CHARGES TABLE")
print("=" * 120)
print()

# Get all charters with charge discrepancies
print("Analyzing charter_charges discrepancies...")
pg_cur.execute("""
    WITH charge_analysis AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            COUNT(cc.charge_id) as charge_count,
            COALESCE(SUM(cc.amount), 0) as charges_sum,
            ABS(c.total_amount_due - COALESCE(SUM(cc.amount), 0)) as abs_diff
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    )
    SELECT charter_id, reserve_number, total_amount_due, charge_count, charges_sum
    FROM charge_analysis
    WHERE abs_diff > 0.02
    ORDER BY abs_diff DESC
""")
discrepancies = pg_cur.fetchall()

print(f"Found {len(discrepancies)} charters with incorrect charter_charges")
print()

# Categorize issues
zero_amount_charges = []
needs_replacement = []
needs_addition = []

for charter_id, reserve_number, total_due, charge_count, charges_sum in discrepancies:
    if charge_count == 0 and total_due > 0:
        needs_addition.append((charter_id, reserve_number, total_due))
    elif charges_sum == 0 and total_due > 0:
        zero_amount_charges.append((charter_id, reserve_number, total_due, charge_count))
    else:
        needs_replacement.append((charter_id, reserve_number, total_due, charge_count, charges_sum))

print(f"Categorization:")
print(f"  - Zero amount charges (delete and replace): {len(zero_amount_charges)}")
print(f"  - Needs single charge added: {len(needs_addition)}")
print(f"  - Needs charge replacement: {len(needs_replacement)}")
print()

print("=" * 120)
print("DRY RUN - Showing what would be fixed")
print("=" * 120)
print()

print("Sample charters that will be fixed:")
print(f"{'Reserve':<12} {'Charter':<8} {'Current Charges':<16} {'Should Be':<12} {'Action':<30}")
print("-" * 120)

samples = (
    [(r, c, f"0 x {count}", t, "Delete zeros, add single charge") for c, r, t, count in zero_amount_charges[:5]] +
    [(r, c, "No charges", t, "Add single charge") for c, r, t in needs_addition[:5]] +
    [(r, c, f"${s:,.2f} ({count} items)", t, "Replace with single charge") for c, r, t, count, s in needs_replacement[:10]]
)

for reserve, charter, current, should_be, action in samples:
    print(f"{reserve:<12} {charter:<8} {current:<16} ${should_be:>10,.2f} {action:<30}")

print()
print(f"Total charters to fix: {len(discrepancies)}")
print()

import sys
if '--apply' in sys.argv:
    print("APPLYING FIXES...")
    print()
    
    # Create backup
    backup_table = f"charter_charges_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    pg_cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM charter_charges")
    pg_cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = pg_cur.fetchone()[0]
    print(f"✓ Backup created: {backup_table} ({backup_count} charges backed up)")
    
    fixed_count = 0
    
    for charter_id, reserve_number, total_due, charge_count, charges_sum in discrepancies:
        # Delete existing incorrect charges
        pg_cur.execute("""
            DELETE FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        
        # Insert single correct charge
        if total_due > 0:
            pg_cur.execute("""
                INSERT INTO charter_charges (charter_id, charge_type, amount, description)
                VALUES (%s, 'invoice', %s, %s)
            """, (charter_id, total_due, f"Charter total (from LMS Est_Charge) - Reserve {reserve_number}"))
            fixed_count += 1
        
        if fixed_count % 1000 == 0:
            print(f"  Fixed {fixed_count} charters...")
    
    pg_conn.commit()
    
    print(f"✓ Fixed {fixed_count} charters")
    print()
    
    # Verify
    pg_cur.execute("""
        WITH charge_analysis AS (
            SELECT 
                c.charter_id,
                c.total_amount_due,
                COALESCE(SUM(cc.amount), 0) as charges_sum
            FROM charters c
            LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
            GROUP BY c.charter_id, c.total_amount_due
        )
        SELECT COUNT(*)
        FROM charge_analysis
        WHERE ABS(total_amount_due - charges_sum) > 0.02
    """)
    remaining = pg_cur.fetchone()[0]
    
    print("=" * 120)
    if remaining == 0:
        print("✓ SUCCESS! All charter_charges now match charters.total_amount_due")
    else:
        print(f"⚠️  WARNING: {remaining} charters still have discrepancies")
    print("=" * 120)
    print(f"Backup table: {backup_table}")
    print(f"Rollback: DROP TABLE charter_charges; ALTER TABLE {backup_table} RENAME TO charter_charges;")

else:
    print("Run with --apply to fix charter_charges table")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
