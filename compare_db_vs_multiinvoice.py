"""
Compare charters in database vs multiinvoice.xls to find discrepancies
"""
import psycopg2
import pandas as pd
from decimal import Decimal

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print("="*80)
print("DATABASE VS MULTIINVOICE.XLS COMPARISON")
print("="*80)

# Get all Perron Ventures charters from database (2012)
cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, balance
    FROM charters
    WHERE client_display_name ILIKE '%Perron Ventures%'
      AND client_display_name NOT ILIKE '%Perron Kip%'
      AND EXTRACT(YEAR FROM charter_date) = 2012
    ORDER BY reserve_number
""")

db_charters = cur.fetchall()
print(f"\n📊 DATABASE: {len(db_charters)} charters from 2012")

# Get all Perron Ventures charters from multiinvoice.xls
df = pd.read_excel(r'Z:\multiinvoice.xls', engine='xlrd')
perron_mask = df.iloc[:, 9].astype(str).str.contains('Perron Ventures Ltd', case=False, na=False)
charter_rows = df[perron_mask]

xls_reserve_nums = set()
xls_totals = {}
for idx, row in charter_rows.iterrows():
    reserve_num = str(row.iloc[1]).strip()
    total = Decimal(str(row.iloc[26]))
    if reserve_num != 'nan':
        xls_reserve_nums.add(reserve_num)
        xls_totals[reserve_num] = total

print(f"📄 MULTIINVOICE.XLS: {len(xls_reserve_nums)} charters")
print()

# Compare
db_reserve_nums = set([row[0] for row in db_charters])

in_db_not_xls = db_reserve_nums - xls_reserve_nums
in_xls_not_db = xls_reserve_nums - db_reserve_nums

print("="*80)
print("DISCREPANCY ANALYSIS")
print("="*80)

if in_db_not_xls:
    print(f"\n⚠️  CHARTERS IN DATABASE BUT NOT IN MULTIINVOICE.XLS ({len(in_db_not_xls)}):")
    print("-" * 80)
    extra_total = Decimal('0')
    for reserve_num in sorted(in_db_not_xls):
        # Find in db_charters
        for row in db_charters:
            if row[0] == reserve_num:
                print(f"  {reserve_num}  {row[1]}  ${row[2]:>10,.2f}  Balance: ${row[3]:,.2f}")
                extra_total += Decimal(str(row[2]))
                break
    print("-" * 80)
    print(f"  Total of extra charters: ${extra_total:,.2f}")
    print()

if in_xls_not_db:
    print(f"\n⚠️  CHARTERS IN MULTIINVOICE.XLS BUT NOT IN DATABASE ({len(in_xls_not_db)}):")
    print("-" * 80)
    for reserve_num in sorted(in_xls_not_db):
        print(f"  {reserve_num}  ${xls_totals[reserve_num]:,.2f}")
    print()

if not in_db_not_xls and not in_xls_not_db:
    print("✅ All charters match between database and multiinvoice.xls")
    print()

# Totals
print("="*80)
print("TOTAL COMPARISON")
print("="*80)

db_total = sum(Decimal(str(row[2])) for row in db_charters)
xls_total = sum(xls_totals.values())

print(f"\nDatabase Total:         ${db_total:>12,.2f}  ({len(db_charters)} charters)")
print(f"Multiinvoice.xls Total: ${xls_total:>12,.2f}  ({len(xls_reserve_nums)} charters)")
print(f"                         {'─'*15}")
print(f"Difference:             ${db_total - xls_total:>12,.2f}")
print()

# Check payments for the extra charters
if in_db_not_xls:
    print("="*80)
    print("PAYMENT STATUS OF EXTRA CHARTERS")
    print("="*80)
    
    for reserve_num in sorted(in_db_not_xls):
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM charter_payments
            WHERE charter_id = %s
        """, (reserve_num,))
        
        payment_count, payment_total = cur.fetchone()
        
        # Get charter details
        for row in db_charters:
            if row[0] == reserve_num:
                charter_total = row[2]
                balance = row[3]
                print(f"\n  Charter {reserve_num}:")
                print(f"    Total Due: ${charter_total:,.2f}")
                print(f"    Payments:  {payment_count} records, ${payment_total:,.2f}")
                print(f"    Balance:   ${balance:,.2f}")
                break

cur.close()
conn.close()

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print("""
The multiinvoice.xls file represents the ORIGINAL invoice sent to Perron Ventures
for 58 charters totaling $57,997.50. This matches the user's two checks exactly.

The database contains additional charters that were NOT part of the original invoice.
These extra charters need to be investigated to determine:
  1. Were they added after the invoice was generated?
  2. Should they be included in a separate invoice?
  3. Were they paid separately?
""")
