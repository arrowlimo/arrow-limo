"""
Rebuild charter_payments 2015-2026 from LMS Payment table (authoritative source)
"""
import pyodbc
import psycopg2
import pandas as pd
from datetime import datetime

print("=" * 80)
print("STEP 1: BACKUP CURRENT charter_payments (2015-2026)")
print("=" * 80)

alms_conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)

alms_cursor = alms_conn.cursor()

# Backup current 2015-2026 charter_payments
alms_cursor.execute("""
DROP TABLE IF EXISTS backup_charter_payments_2015_2026_pre_lms_rebuild_20260410;
CREATE TABLE backup_charter_payments_2015_2026_pre_lms_rebuild_20260410 AS
SELECT cp.* FROM charter_payments cp
JOIN charters c ON c.reserve_number = cp.charter_id
WHERE EXTRACT(YEAR FROM c.charter_date) >= 2015;
""")

alms_cursor.execute("SELECT COUNT(*) FROM backup_charter_payments_2015_2026_pre_lms_rebuild_20260410")
backup_count = alms_cursor.fetchone()[0]
print(f"✓ Backed up {backup_count:,} charter_payments rows for 2015-2026")
alms_conn.commit()

print()
print("=" * 80)
print("STEP 2: LOAD AUTHORITATIVE PAYMENTS FROM LMS")
print("=" * 80)

lms_file = r'L:\lms2026b.mdb'
conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_file};'

try:
    lms_conn = pyodbc.connect(conn_str)
    
    # Query all payments from LMS
    query = """
    SELECT 
      Reserve_No,
      Amount,
      Key AS payment_key,
      LastUpdated AS payment_date,
      PaymentID
    FROM Payment
    WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''
    ORDER BY Reserve_No, LastUpdated
    """
    
    df_lms = pd.read_sql(query, lms_conn)
    print(f"✓ Loaded {len(df_lms):,} payment rows from LMS")
    print(f"  Date range: {df_lms['payment_date'].min()} to {df_lms['payment_date'].max()}")
    print(f"  Total amount: ${df_lms['Amount'].sum():,.2f}")
    lms_conn.close()
    
except Exception as e:
    print(f"ERROR loading LMS: {e}")
    alms_conn.close()
    exit(1)

print()
print("=" * 80)
print("STEP 3: DELETE 2015-2026 charter_payments (keep 2012-2014)")
print("=" * 80)

# Delete 2015+ payments
alms_cursor.execute("""
DELETE FROM charter_payments cp
USING charters c
WHERE c.reserve_number = cp.charter_id
  AND EXTRACT(YEAR FROM c.charter_date) >= 2015;
""")

alms_cursor.execute("SELECT COUNT(*) FROM charter_payments")
remaining = alms_cursor.fetchone()[0]
print(f"✓ Deleted all 2015-2026 charter_payments; remaining: {remaining:,} (2012-2014)")
alms_conn.commit()

print()
print("=" * 80)
print("STEP 4: INSERT CLEAN PAYMENTS FROM LMS FOR 2015-2026")
print("=" * 80)

# Get charter records to link by reserve_number
alms_cursor.execute("""
SELECT reserve_number, charter_id FROM charters 
WHERE EXTRACT(YEAR FROM charter_date) >= 2015
""")

charter_map = {}
for reserve_no, charter_id in alms_cursor.fetchall():
    charter_map[reserve_no] = charter_id

print(f"  Found {len(charter_map):,} charters to link")

# Prepare insert data
insert_rows = []
for idx, row in df_lms.iterrows():
    reserve_no = row['Reserve_No'].strip()
    
    # Only insert if we have a matching charter
    if reserve_no not in charter_map:
        continue
    
    insert_rows.append({
        'charter_id': reserve_no,
        'amount': float(row['Amount']),
        'payment_date': row['payment_date'],
        'payment_method': 'unknown',
        'payment_key': row['payment_key'] if row['payment_key'] else None,
        'source': 'LMS_PAYMENT_TABLE_REBUILD_20260410',
        'imported_at': datetime.now()
    })

print(f"  Prepared {len(insert_rows):,} rows for insert")

# Insert in batches
batch_size = 1000
for i in range(0, len(insert_rows), batch_size):
    batch = insert_rows[i:i+batch_size]
    for row in batch:
        alms_cursor.execute("""
        INSERT INTO charter_payments 
        (charter_id, amount, payment_date, payment_method, payment_key, source, imported_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            row['charter_id'], row['amount'], row['payment_date'], row['payment_method'],
            row['payment_key'], row['source'], row['imported_at']
        ))
    alms_conn.commit()
    print(f"  ✓ Inserted batch {i//batch_size + 1} ({min(batch_size, len(insert_rows)-i)} rows)")

alms_cursor.execute("SELECT COUNT(*) FROM charter_payments")
new_total = alms_cursor.fetchone()[0]
alms_cursor.execute("SELECT COUNT(*) FROM charter_payments WHERE EXTRACT(YEAR FROM payment_date) >= 2015")
new_2015_count = alms_cursor.fetchone()[0]

print(f"✓ Charter_payments now: {new_total:,} total ({new_2015_count:,} from 2015-2026)")

print()
print("=" * 80)
print("STEP 5: RECALCULATE CHARTER BALANCES")
print("=" * 80)

# Recalculate payment_totals and balance for all affected charters
alms_cursor.execute("""
WITH updated_totals AS (
  SELECT 
    charter_id,
    ROUND(SUM(amount)::numeric, 2) AS new_payment_totals
  FROM charter_payments
  WHERE charter_id IS NOT NULL
  GROUP BY charter_id
)
UPDATE charters c
SET payment_totals = ut.new_payment_totals,
    balance = c.grand_total - ut.new_payment_totals,
    updated_at = NOW()
FROM updated_totals ut
WHERE c.reserve_number = ut.charter_id
  AND EXTRACT(YEAR FROM c.charter_date) >= 2015;
""")

alms_conn.commit()

# Check results
alms_cursor.execute("""
SELECT 
  EXTRACT(YEAR FROM charter_date) AS year,
  COUNT(*) AS total_charters,
  SUM(CASE WHEN balance = 0 THEN 1 ELSE 0 END) AS zero_balance,
  SUM(CASE WHEN balance <> 0 THEN 1 ELSE 0 END) AS non_zero_balance,
  ROUND(SUM(balance)::numeric, 2) AS total_balance
FROM charters
WHERE EXTRACT(YEAR FROM charter_date) >= 2015
GROUP BY EXTRACT(YEAR FROM charter_date)
ORDER BY year
""")

print("Recalculated balances by year:")
print(f"{'Year':<6} {'Total':<8} {'Zero':<8} {'Non-Zero':<10} {'Total Balance':<15}")
print("-" * 50)
for year, total, zero, nonzero, balance in alms_cursor.fetchall():
    print(f"{int(year):<6} {total:<8} {zero:<8} {nonzero:<10} ${float(balance):>12,.2f}")

alms_conn.commit()
alms_conn.close()

print()
print("=" * 80)
print("REBUILD COMPLETE")
print("=" * 80)
print(f"✓ charter_payments rebuilt from LMS authoritative source")
print(f"✓ All 2015-2026 balances recalculated")
print(f"✓ Backup saved: backup_charter_payments_2015_2026_pre_lms_rebuild_20260410")
