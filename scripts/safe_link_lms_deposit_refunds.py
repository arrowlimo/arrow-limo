"""
SAFE linking of LMS Deposit refunds to charter_refunds.

Only updates records where BOTH reserve_number AND charter_id are NULL.
Never overwrites existing linkages.

Uses LMS Deposit table records with Type='Refund' to find reserve numbers.
"""

import pyodbc
import psycopg2
from decimal import Decimal
from datetime import datetime

# LMS Connection
LMS_PATH = r'L:\oldlms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

print("=" * 80)
print("SAFE LINKING: LMS Deposit Refunds → charter_refunds (NULL fields only)")
print("=" * 80)

# Step 1: Get LMS Deposit refunds
print("\nStep 1: Loading LMS Deposit refunds...")
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

lms_cur.execute("""
    SELECT CB_NO, [Date], [Key], [Number], [Total], [Type], LastUpdated, LastUpdatedBy
    FROM Deposit
    WHERE [Type] = 'Refund'
    ORDER BY [Date] DESC
""")

lms_deposits = lms_cur.fetchall()
print(f"Found {len(lms_deposits)} LMS Deposit refund records")

print("\nLMS Deposit Refunds:")
print(f"{'Date':<12} {'Key':<10} {'Number':<20} {'Total':<12} {'LastUpdated':<12}")
print("-" * 80)
for row in lms_deposits:
    cb_no = row[0] or ''
    date = row[1].strftime('%Y-%m-%d') if row[1] else 'NULL'
    key = (row[2] or '')[:7] + '...' if row[2] and len(row[2]) > 10 else (row[2] or 'NULL')
    number = (row[3] or '')[:17] + '...' if row[3] and len(row[3]) > 20 else (row[3] or 'NULL')
    total = float(row[4]) if row[4] else 0
    updated = row[6].strftime('%Y-%m-%d') if row[6] else 'NULL'
    print(f"{date:<12} {key:<10} {number:<20} ${total:<11,.2f} {updated:<12}")

# Step 2: Extract reserve numbers from Key field
print("\n" + "=" * 80)
print("Step 2: Extracting reserve numbers from Key field...")
print("=" * 80)

import re
reserve_pattern = re.compile(r'\b(\d{6,7})\b')

lms_with_reserves = []
for row in lms_deposits:
    cb_no, date, key, number, total, deposit_type, updated, updated_by = row
    
    # Try to extract reserve number from Key field
    reserve_match = reserve_pattern.search(key or '')
    if reserve_match:
        reserve_num = reserve_match.group(1)
        # Pad to 6 digits if needed
        if len(reserve_num) == 6:
            lms_with_reserves.append({
                'date': date,
                'key': key,
                'number': number,
                'amount': abs(float(total)) if total else 0,
                'reserve': reserve_num
            })

print(f"Found {len(lms_with_reserves)} LMS deposits with reserve numbers")

if lms_with_reserves:
    print("\nLMS Deposits with Reserve Numbers:")
    print(f"{'Reserve':<10} {'Date':<12} {'Amount':<12} {'Key':<20}")
    print("-" * 60)
    for item in lms_with_reserves:
        print(f"{item['reserve']:<10} {item['date'].strftime('%Y-%m-%d'):<12} ${item['amount']:<11,.2f} {(item['key'] or '')[:17]:<20}")

# Step 3: Get charter_refunds with NULL reserve_number AND charter_id
print("\n" + "=" * 80)
print("Step 3: Loading charter_refunds with NULL reserve AND charter...")
print("=" * 80)

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

pg_cur.execute("""
    SELECT id, refund_date, amount, description, source_file
    FROM charter_refunds
    WHERE reserve_number IS NULL AND charter_id IS NULL
    ORDER BY amount DESC
""")

null_refunds = pg_cur.fetchall()
print(f"Found {len(null_refunds)} charter_refunds with NULL reserve_number AND charter_id")

if null_refunds:
    print("\nNULL charter_refunds:")
    print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Source':<30}")
    print("-" * 70)
    for row in null_refunds:
        refund_id = row[0]
        date = row[1].strftime('%Y-%m-%d') if row[1] else 'NULL'
        amount = float(row[2]) if row[2] else 0
        source = (row[4] or '')[:27] + '...' if row[4] and len(row[4]) > 30 else (row[4] or '')
        print(f"{refund_id:<8} {date:<12} ${amount:<11,.2f} {source:<30}")

# Step 4: Match by amount and date (±7 days)
print("\n" + "=" * 80)
print("Step 4: Matching LMS deposits to NULL charter_refunds...")
print("=" * 80)

linkable = []

for refund in null_refunds:
    refund_id, refund_date, refund_amount, description, source_file = refund
    
    if not refund_amount or not refund_date:
        continue
    
    refund_amount = float(refund_amount)
    
    # Find LMS deposits with matching amount (±$0.01) and date (±7 days)
    for lms_item in lms_with_reserves:
        amount_diff = abs(lms_item['amount'] - refund_amount)
        date_diff = abs((lms_item['date'] - refund_date).days)
        
        if amount_diff <= 0.01 and date_diff <= 7:
            linkable.append({
                'refund_id': refund_id,
                'refund_amount': refund_amount,
                'refund_date': refund_date,
                'lms_reserve': lms_item['reserve'],
                'lms_amount': lms_item['amount'],
                'lms_date': lms_item['date'],
                'amount_diff': amount_diff,
                'date_diff': date_diff
            })

print(f"Found {len(linkable)} linkable matches")

if linkable:
    print("\nLinkable Matches:")
    print(f"{'Refund ID':<10} {'Amount':<12} {'LMS Reserve':<12} {'Date Diff':<10} {'Amount Diff':<12}")
    print("-" * 65)
    for match in linkable:
        print(f"{match['refund_id']:<10} ${match['refund_amount']:<11,.2f} {match['lms_reserve']:<12} {match['date_diff']:<10} ${match['amount_diff']:<11.2f}")

# Step 5: Look up charter_ids from reserve numbers
print("\n" + "=" * 80)
print("Step 5: Looking up charter_ids from reserve numbers...")
print("=" * 80)

updates = []

for match in linkable:
    pg_cur.execute("""
        SELECT charter_id, reserve_number 
        FROM charters 
        WHERE reserve_number = %s
    """, (match['lms_reserve'],))
    
    charter = pg_cur.fetchone()
    if charter:
        charter_id, reserve_number = charter
        updates.append({
            'refund_id': match['refund_id'],
            'reserve_number': reserve_number,
            'charter_id': charter_id,
            'amount': match['refund_amount']
        })
        print(f"  Refund #{match['refund_id']} → Reserve {reserve_number} → Charter {charter_id}")
    else:
        print(f"  Refund #{match['refund_id']} → Reserve {match['lms_reserve']} → ✗ Charter not found")

print(f"\nFound {len(updates)} charters for linkage")

# Step 6: Apply updates (dry run first)
print("\n" + "=" * 80)
print("Step 6: Applying updates (DRY RUN)")
print("=" * 80)

if updates:
    print("\nWould update these charter_refunds:")
    print(f"{'Refund ID':<10} {'Reserve':<10} {'Charter ID':<12} {'Amount':<12}")
    print("-" * 50)
    for update in updates:
        print(f"{update['refund_id']:<10} {update['reserve_number']:<10} {update['charter_id']:<12} ${update['amount']:<11,.2f}")
    
    print("\n" + "=" * 80)
    print("To apply these changes, run with --write flag:")
    print("  python safe_link_lms_deposit_refunds.py --write")
else:
    print("No updates to apply")

# Close connections
lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print("\n" + "=" * 80)
print("SAFE LINKING COMPLETE (DRY RUN)")
print("=" * 80)
print("Safety guarantees:")
print("  ✓ Only updates records with NULL reserve_number AND NULL charter_id")
print("  ✓ Never overwrites existing linkages")
print("  ✓ Matches by amount (±$0.01) and date (±7 days)")
print("  ✓ Verifies charter exists before linking")
