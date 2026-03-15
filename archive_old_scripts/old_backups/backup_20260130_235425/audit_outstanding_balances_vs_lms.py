"""
Audit outstanding balances between LMS and PostgreSQL.
Compares Balance field from LMS Reserve table with balance in PostgreSQL charters table.
"""
import pyodbc
import psycopg2
import os
from decimal import Decimal

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

print("=" * 120)
print("OUTSTANDING BALANCE AUDIT - LMS vs POSTGRESQL")
print("=" * 120)
print(f"LMS Database: {LMS_PATH}")
print()

# Get balances from LMS
print("📋 Loading LMS balances...")
lms_cur.execute("""
    SELECT Reserve_No, Balance, Est_Charge, Deposit, Name
    FROM Reserve
    WHERE Reserve_No IS NOT NULL
    ORDER BY Reserve_No
""")
lms_data = {}
for row in lms_cur.fetchall():
    reserve = row.Reserve_No.strip() if row.Reserve_No else None
    if reserve:
        lms_data[reserve] = {
            'balance': Decimal(str(row.Balance or 0)),
            'est_charge': Decimal(str(row.Est_Charge or 0)),
            'deposit': Decimal(str(row.Deposit or 0)),
            'name': row.Name or ''
        }
print(f"   Loaded {len(lms_data)} LMS reserves")

# Get balances from PostgreSQL
print("📋 Loading PostgreSQL balances...")
pg_cur.execute("""
    SELECT c.reserve_number, c.balance, c.total_amount_due, c.paid_amount, 
           COALESCE(cl.client_name, c.client_notes, '') as client_name, c.charter_id
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.reserve_number IS NOT NULL
    ORDER BY c.reserve_number
""")
pg_data = {}
for row in pg_cur.fetchall():
    pg_data[row[0]] = {
        'balance': Decimal(str(row[1] or 0)),
        'total_amount_due': Decimal(str(row[2] or 0)),
        'paid_amount': Decimal(str(row[3] or 0)),
        'client_name': row[4] or '',
        'charter_id': row[5]
    }
print(f"   Loaded {len(pg_data)} PostgreSQL charters")
print()

# Compare balances
discrepancies = []
tolerance = Decimal('0.02')  # 2 cent tolerance for rounding

for reserve_num in pg_data.keys():
    if reserve_num in lms_data:
        lms_bal = lms_data[reserve_num]['balance']
        pg_bal = pg_data[reserve_num]['balance']
        diff = abs(lms_bal - pg_bal)
        
        if diff > tolerance:
            discrepancies.append({
                'reserve_number': reserve_num,
                'charter_id': pg_data[reserve_num]['charter_id'],
                'lms_balance': lms_bal,
                'pg_balance': pg_bal,
                'difference': lms_bal - pg_bal,
                'lms_est_charge': lms_data[reserve_num]['est_charge'],
                'lms_deposit': lms_data[reserve_num]['deposit'],
                'pg_total_due': pg_data[reserve_num]['total_amount_due'],
                'pg_paid': pg_data[reserve_num]['paid_amount'],
                'client_name': pg_data[reserve_num]['client_name']
            })

print("=" * 120)
print(f"FOUND {len(discrepancies)} BALANCE DISCREPANCIES (>{tolerance})")
print("=" * 120)

if discrepancies:
    # Sort by absolute difference (largest first)
    discrepancies.sort(key=lambda x: abs(x['difference']), reverse=True)
    
    print()
    print("TOP 50 LARGEST DISCREPANCIES:")
    print("-" * 120)
    print(f"{'Reserve':<10} {'Charter':<8} {'LMS Balance':<15} {'PG Balance':<15} {'Difference':<15} {'Client Name':<30}")
    print("-" * 120)
    
    total_lms_diff = Decimal('0')
    total_pg_diff = Decimal('0')
    
    for disc in discrepancies[:50]:
        lms_bal_str = f"${disc['lms_balance']:,.2f}"
        pg_bal_str = f"${disc['pg_balance']:,.2f}"
        diff_str = f"${disc['difference']:,.2f}"
        client = disc['client_name'][:28] if len(disc['client_name']) > 28 else disc['client_name']
        
        print(f"{disc['reserve_number']:<10} {disc['charter_id']:<8} {lms_bal_str:<15} {pg_bal_str:<15} {diff_str:<15} {client:<30}")
        
        total_lms_diff += disc['lms_balance']
        total_pg_diff += disc['pg_balance']
    
    if len(discrepancies) > 50:
        print(f"... and {len(discrepancies) - 50} more")
    
    print("-" * 120)
    total_lms_sum = sum(d['lms_balance'] for d in discrepancies)
    total_pg_sum = sum(d['pg_balance'] for d in discrepancies)
    total_diff_sum = sum(d['difference'] for d in discrepancies)
    print(f"{'TOTALS:':<10} {'':<8} ${total_lms_sum:>13,.2f} ${total_pg_sum:>13,.2f} ${total_diff_sum:>13,.2f}")
    print()
    
    # Analyze patterns
    print("=" * 120)
    print("DISCREPANCY ANALYSIS:")
    print("=" * 120)
    
    # Group by size
    large_disc = [d for d in discrepancies if abs(d['difference']) >= 100]
    medium_disc = [d for d in discrepancies if 10 <= abs(d['difference']) < 100]
    small_disc = [d for d in discrepancies if abs(d['difference']) < 10]
    
    print(f"Large discrepancies (≥$100):    {len(large_disc):>6} charters, total difference: ${sum(d['difference'] for d in large_disc):>12,.2f}")
    print(f"Medium discrepancies ($10-$99): {len(medium_disc):>6} charters, total difference: ${sum(d['difference'] for d in medium_disc):>12,.2f}")
    print(f"Small discrepancies (<$10):     {len(small_disc):>6} charters, total difference: ${sum(d['difference'] for d in small_disc):>12,.2f}")
    print()
    
    # Direction analysis
    lms_higher = [d for d in discrepancies if d['difference'] > 0]
    pg_higher = [d for d in discrepancies if d['difference'] < 0]
    
    print(f"LMS balance HIGHER than PG:     {len(lms_higher):>6} charters, net difference: ${sum(d['difference'] for d in lms_higher):>12,.2f}")
    print(f"PG balance HIGHER than LMS:     {len(pg_higher):>6} charters, net difference: ${sum(d['difference'] for d in pg_higher):>12,.2f}")
    print()
    
    print("=" * 120)
    print("DRY RUN - No changes made")
    print("To fix these discrepancies, run: python scripts/fix_balance_discrepancies.py --apply")
    print("=" * 120)
    
else:
    print()
    print("✓ ALL BALANCES MATCH!")
    print(f"PostgreSQL and LMS balances are in sync (within {tolerance} tolerance).")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
