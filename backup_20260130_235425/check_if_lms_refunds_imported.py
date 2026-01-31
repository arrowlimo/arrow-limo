"""
Check if LMS refund payments are already in charter_refunds table (as linked records).

This will tell us if the LMS refunds we found are:
1. Already imported and linked
2. New data we haven't imported yet
3. Something else entirely
"""

import pyodbc
import psycopg2

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
print("CHECKING IF LMS REFUNDS ARE ALREADY IN CHARTER_REFUNDS")
print("=" * 80)

# Get LMS refund payments
print("\nLoading LMS refund payments (negative amounts)...")
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

lms_cur.execute("""
    SELECT PaymentID, Account_No, Reserve_No, Amount, LastUpdated
    FROM Payment
    WHERE Amount < 0
    ORDER BY Amount ASC
""")

lms_refunds = lms_cur.fetchall()
print(f"Found {len(lms_refunds)} LMS refund payment records")
print(f"Total: ${sum(abs(float(r[3])) for r in lms_refunds):,.2f}")

# Get ALL charter_refunds (linked and unlinked)
print("\nLoading ALL charter_refunds from PostgreSQL (linked + unlinked)...")
pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

pg_cur.execute("""
    SELECT id, refund_date, amount, charter_id, reserve_number, source_file
    FROM charter_refunds
    ORDER BY amount DESC
""")

all_refunds = pg_cur.fetchall()
print(f"Found {len(all_refunds)} charter_refunds records")
print(f"  Linked: {sum(1 for r in all_refunds if r[3])}")
print(f"  Unlinked: {sum(1 for r in all_refunds if not r[3])}")
print(f"Total: ${sum(float(r[2]) for r in all_refunds if r[2]):,.2f}")

# Check source files
sources = {}
for refund in all_refunds:
    source = refund[5] or 'Unknown'
    sources[source] = sources.get(source, 0) + 1

print("\ncharter_refunds by source:")
for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
    print(f"  {source}: {count}")

# Match LMS refunds to charter_refunds by amount
print("\n" + "=" * 80)
print("Matching LMS refunds to charter_refunds by amount (±$0.01)...")
print("=" * 80)

matches_linked = 0
matches_unlinked = 0
no_match = 0

for lms_refund in lms_refunds[:20]:  # Check first 20
    payment_id, account, reserve, lms_amount, lms_date = lms_refund
    lms_abs_amount = abs(float(lms_amount))
    
    # Find matching charter_refunds
    matched = []
    for refund in all_refunds:
        refund_id, refund_date, refund_amount, charter_id, reserve_num, source = refund
        
        if not refund_amount:
            continue
        
        amount_diff = abs(float(refund_amount) - lms_abs_amount)
        if amount_diff <= 0.01:
            matched.append({
                'refund_id': refund_id,
                'amount': refund_amount,
                'linked': bool(charter_id),
                'reserve': reserve_num,
                'source': source
            })
    
    if matched:
        is_linked = any(m['linked'] for m in matched)
        if is_linked:
            matches_linked += 1
            status = "✓ LINKED"
        else:
            matches_unlinked += 1
            status = "✗ UNLINKED"
        
        print(f"\nLMS Payment {payment_id}: ${lms_abs_amount:,.2f} (Reserve: {reserve})")
        print(f"  {status} - Found {len(matched)} match(es) in charter_refunds:")
        for m in matched[:3]:
            print(f"    - Refund #{m['refund_id']}: ${m['amount']:,.2f}, Reserve: {m['reserve']}, Source: {m['source']}")
    else:
        no_match += 1

print(f"\n{'=' * 80}")
print(f"SUMMARY (first 20 LMS refunds)")
print("=" * 80)
print(f"Matched to LINKED charter_refunds: {matches_linked}")
print(f"Matched to UNLINKED charter_refunds: {matches_unlinked}")
print(f"No match in charter_refunds: {no_match}")

# Check if LMS refunds source is 'payments.table'
print("\n" + "=" * 80)
print("Checking if LMS refunds were imported from 'payments.table' source...")
print("=" * 80)

payments_table_refunds = [r for r in all_refunds if r[5] == 'payments.table']
print(f"charter_refunds from 'payments.table': {len(payments_table_refunds)}")
print(f"  Linked: {sum(1 for r in payments_table_refunds if r[3])}")
print(f"  Unlinked: {sum(1 for r in payments_table_refunds if not r[3])}")

# Sample payments.table refunds
print("\nSample 'payments.table' refunds:")
print(f"{'ID':<8} {'Amount':<12} {'Linked':<8} {'Reserve':<12}")
print("-" * 50)
for refund in payments_table_refunds[:10]:
    refund_id, refund_date, refund_amount, charter_id, reserve_num, source = refund
    linked = "Yes" if charter_id else "No"
    reserve = reserve_num or "NULL"
    print(f"{refund_id:<8} ${float(refund_amount):<11,.2f} {linked:<8} {reserve:<12}")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("If LMS refunds match 'payments.table' source:")
print("  → LMS refunds are ALREADY imported into charter_refunds")
print("  → No new data to import from LMS")
print("\nIf LMS refunds don't match:")
print("  → LMS has DIFFERENT refund data not yet imported")
print("  → Need to import LMS refunds as new charter_refunds records")
