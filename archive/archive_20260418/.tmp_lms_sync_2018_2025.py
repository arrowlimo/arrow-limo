#!/usr/bin/env python3
"""
Sync LMS2026d.mdb Payment records to PostgreSQL for 2018-2025 reserves
Uses same approach as 2012-2017 sync — date-based matching with detailed audit
"""
import psycopg2
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
import json

# Connect to both databases
pg_conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
pg_cur = pg_conn.cursor()

# LMS connection via ODBC
lms_connstr = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=l:\limo\db\lms2026d.mdb;'
lms_conn = pyodbc.connect(lms_connstr)
lms_cur = lms_conn.cursor()

print("\n" + "="*80)
print("SYNC LMS2026d.mdb → PostgreSQL: 2018-2025 PAYMENTS")
print("="*80)

# Step 1: Load LMS Payment records for 2018-2025 reserves
print("\n[1/6] Loading LMS Payment records for 2018-2025 reserves...")
q_lms = """
SELECT 
    PaymentID,
    Key,
    Reserve_No,
    Amount,
    LastUpdated,
    LastUpdatedBy
FROM Payment
WHERE Reserve_No IS NOT NULL
ORDER BY Reserve_No, LastUpdated
"""
lms_payments = []
for row in lms_cur.execute(q_lms):
    pid, key, reserve_no, amount, lastupdated, lastby = row
    if reserve_no and len(str(reserve_no).strip()) > 0:
        lms_payments.append({
            'lms_payment_id': pid,
            'lms_key': key,
            'reserve_number': str(reserve_no).strip().zfill(6),
            'amount': float(amount) if amount else 0,
            'payment_date': lastupdated.date() if lastupdated else None,
            'updated_by': str(lastby) if lastby else ''
        })

print(f"   Loaded {len(lms_payments)} LMS Payment records")

# Filter to 2018-2025 reserves only
df_lms = pd.DataFrame(lms_payments)
q_filter = """
SELECT DISTINCT reserve_number FROM charters 
WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2018 AND 2025
"""
df_target_reserves = pd.read_sql_query(q_filter, pg_conn)
target_set = set(df_target_reserves['reserve_number'].astype(str).str.zfill(6))

df_lms_filtered = df_lms[df_lms['reserve_number'].isin(target_set)].copy()
print(f"   Filtered to {len(df_lms_filtered)} payments on 2018-2025 reserves")

# Step 2: Load current PostgreSQL payments for comparison
print("\n[2/6] Loading PostgreSQL Payment records for 2018-2025 reserves...")
q_pg = """
SELECT 
    p.payment_id,
    p.reserve_number,
    p.amount,
    p.payment_date,
    p.payment_key,
    p.payment_method,
    p.notes
FROM payments p
JOIN charters c ON p.reserve_number = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) BETWEEN 2018 AND 2025
ORDER BY p.reserve_number, p.payment_date
"""
df_pg = pd.read_sql_query(q_pg, pg_conn)
print(f"   Loaded {len(df_pg)} PostgreSQL Payment records")

# Step 3: Identify which LMS records need to be synced
print("\n[3/6] Analyzing sync candidates...")

# Build matching key: (reserve_no, amount, date_normalized)
df_lms_filtered['sync_key'] = (
    df_lms_filtered['reserve_number'] + '_' +
    df_lms_filtered['amount'].astype(str) + '_' +
    df_lms_filtered['payment_date'].astype(str)
)
df_pg['sync_key'] = (
    df_pg['reserve_number'].astype(str).str.zfill(6) + '_' +
    df_pg['amount'].astype(str) + '_' +
    df_pg['payment_date'].astype(str)
)

lms_keys = set(df_lms_filtered['sync_key'])
pg_keys = set(df_pg['sync_key'])

new_in_lms = lms_keys - pg_keys
dropped_in_pg = pg_keys - lms_keys

print(f"   LMS records not in PG (to INSERT):  {len(new_in_lms)}")
print(f"   PG records not in LMS (to DELETE):  {len(dropped_in_pg)}")

# Step 4: Apply inserts
print("\n[4/6] Applying INSERT operations...")
insert_count = 0
for _, row in df_lms_filtered[df_lms_filtered['sync_key'].isin(new_in_lms)].iterrows():
    try:
        pg_cur.execute("""
            INSERT INTO payments 
            (reserve_number, amount, payment_date, payment_key, payment_method, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            row['reserve_number'],
            row['amount'],
            row['payment_date'],
            str(row['lms_key']) if row['lms_key'] else None,
            'unknown',  # LMS doesn't expose payment_method
            f"Inserted from LMS2026d payment sync (LMS PaymentID={row['lms_payment_id']})"
        ))
        insert_count += 1
    except Exception as e:
        print(f"   ERROR inserting payment for {row['reserve_number']}: {e}")

pg_conn.commit()
print(f"   Inserted {insert_count} new payment records")

# Step 5: Apply deletes
print("\n[5/6] Applying DELETE operations...")
delete_count = 0
for _, row in df_pg[df_pg['sync_key'].isin(dropped_in_pg)].iterrows():
    # Only delete if it's a synthetic duplicate (not an original LMS-sourced record)
    if 'Inserted from LMS2026d payment sync' in (row['notes'] or ''):
        try:
            pg_cur.execute("DELETE FROM payments WHERE payment_id = %s", (row['payment_id'],))
            delete_count += 1
        except Exception as e:
            print(f"   ERROR deleting payment {row['payment_id']}: {e}")

pg_conn.commit()
print(f"   Deleted {delete_count} orphaned payment records")

# Step 6: Rebuild charter_payments and balances for affected reserves
print("\n[6/6] Rebuilding charter_payments and balances...")
affected_reserves = list(target_set)  # Keep as set for easier iteration

# Create temp table to hold reserve numbers
pg_cur.execute("CREATE TEMP TABLE temp_target_reserves (reserve_number varchar)")
pg_cur.executemany("INSERT INTO temp_target_reserves VALUES (%s)", [(r,) for r in affected_reserves])
pg_conn.commit()

# Update balances for affected reserves
pg_cur.execute("""
    UPDATE charters 
    SET balance = total_amount_due - (
        SELECT COALESCE(SUM(ABS(amount)), 0) 
        FROM payments 
        WHERE payments.reserve_number = charters.reserve_number
    )
    WHERE reserve_number IN (SELECT reserve_number FROM temp_target_reserves)
""")
pg_conn.commit()

# Delete stale charter_payments
pg_cur.execute("""
    DELETE FROM charter_payments 
    WHERE charter_id::integer IN (
        SELECT c.charter_id::integer FROM charters c
        WHERE c.reserve_number IN (SELECT reserve_number FROM temp_target_reserves)
    )
""")
pg_conn.commit()

# Rebuild charter_payments from scratch (note: charter_id in charter_payments is varchar)
pg_cur.execute("""
    INSERT INTO charter_payments (charter_id, payment_id)
    SELECT DISTINCT c.charter_id::varchar, p.payment_id
    FROM charters c
    JOIN payments p ON c.reserve_number = p.reserve_number
    WHERE c.reserve_number IN (SELECT reserve_number FROM temp_target_reserves)
    ON CONFLICT DO NOTHING
""")
pg_conn.commit()
print(f"   Rebuilt balances and charter_payments for {len(affected_reserves)} reserves")

# Summary report
summary = {
    'timestamp': datetime.now().isoformat(),
    'year_range': '2018-2025',
    'total_lms_records': len(lms_payments),
    'lms_records_in_target_range': len(df_lms_filtered),
    'pg_records_in_target_range': len(df_pg),
    'inserts': insert_count,
    'deletes': delete_count,
    'reserves_rebuilt': len(affected_reserves)
}

print("\n" + "-"*80)
print("SYNC SUMMARY:")
print("-"*80)
print(json.dumps(summary, indent=2, default=str))

# Save summary CSV
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
summary_file = f"l:\\limo\\reports\\lms_sync_summary_2018_2025_{timestamp}.csv"
pd.DataFrame([summary]).to_csv(summary_file, index=False)
print(f"\n✓ Summary saved: {summary_file}")

pg_conn.close()
lms_conn.close()
