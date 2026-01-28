"""
Compare LMS negative payment amounts (refunds) to unlinked charter_refunds.

LMS Payment table has 176 negative amounts totaling -$40,740.90
These are likely refund payments with reserve numbers that could link our unlinked charter_refunds.
"""

import pyodbc
import psycopg2
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
        password='***REMOVED***'
    )

print("=" * 80)
print("COMPARING LMS REFUND PAYMENTS TO UNLINKED CHARTER_REFUNDS")
print("=" * 80)

# Step 1: Get LMS refund payments (negative amounts)
print("\nStep 1: Loading LMS refund payments (negative amounts)...")
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

lms_cur.execute("""
    SELECT PaymentID, Account_No, Reserve_No, Amount, LastUpdated, [Key]
    FROM Payment
    WHERE Amount < 0
    ORDER BY Amount ASC
""")

lms_refunds = lms_cur.fetchall()
print(f"Found {len(lms_refunds)} LMS refund payment records")
print(f"Total: ${sum(abs(r[3]) for r in lms_refunds):,.2f}")

# Show sample
print("\nTop 10 LMS refunds by amount:")
print(f"{'PaymentID':<12} {'Account':<12} {'Reserve':<12} {'Amount':<12} {'Date':<12}")
print("-" * 70)
for row in lms_refunds[:10]:
    payment_id = row[0]
    account = row[1] or 'NULL'
    reserve = row[2] or 'NULL'
    amount = abs(row[3])
    date = row[4].strftime('%Y-%m-%d') if row[4] else 'NULL'
    print(f"{payment_id:<12} {account:<12} {reserve:<12} ${amount:<11,.2f} {date:<12}")

# Step 2: Get unlinked charter_refunds
print("\n" + "=" * 80)
print("Step 2: Loading unlinked charter_refunds from PostgreSQL...")
pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

pg_cur.execute("""
    SELECT id, refund_date, amount, description, source_file
    FROM charter_refunds
    WHERE charter_id IS NULL
    ORDER BY amount DESC
""")

unlinked = pg_cur.fetchall()
print(f"Found {len(unlinked)} unlinked charter_refunds")
print(f"Total: ${sum(r[2] for r in unlinked if r[2]):,.2f}")

print("\nUnlinked charter_refunds:")
print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Description':<40}")
print("-" * 80)
for row in unlinked:
    refund_id = row[0]
    date = row[1].strftime('%Y-%m-%d') if row[1] else 'NULL'
    amount = row[2]
    desc = (row[3] or '')[:37] + '...' if row[3] and len(row[3]) > 40 else (row[3] or '')
    print(f"{refund_id:<8} {date:<12} ${amount:<11,.2f} {desc:<40}")

# Step 3: Match by amount
print("\n" + "=" * 80)
print("Step 3: Matching by amount (±$0.01)...")
print("=" * 80)

matches_found = 0

for refund in unlinked:
    refund_id, refund_date, refund_amount, description, source_file = refund
    
    if not refund_amount:
        continue
    
    # Find LMS refunds with matching amount (negative = refund)
    matching_lms = []
    for lms_refund in lms_refunds:
        payment_id, account, reserve, lms_amount, lms_date, key = lms_refund
        
        # LMS amount is negative, so take absolute value
        lms_abs_amount = abs(lms_amount)
        amount_diff = abs(lms_abs_amount - float(refund_amount))
        
        if amount_diff <= 0.01:
            # Check date if both have dates
            date_diff = None
            if refund_date and lms_date:
                date_diff = abs((lms_date - refund_date).days)
            
            matching_lms.append({
                'payment_id': payment_id,
                'account': account,
                'reserve': reserve,
                'amount': lms_abs_amount,
                'date': lms_date,
                'key': key,
                'amount_diff': amount_diff,
                'date_diff': date_diff
            })
    
    if matching_lms:
        matches_found += 1
        print(f"\n{'=' * 80}")
        print(f"✓ MATCH FOUND!")
        print(f"charter_refunds ID #{refund_id}:")
        print(f"  Amount: ${refund_amount:,.2f}")
        print(f"  Date: {refund_date}")
        print(f"  Description: {description[:60]}")
        print(f"  Source: {source_file}")
        print(f"\nMatching LMS Payment(s): {len(matching_lms)}")
        
        for i, match in enumerate(matching_lms, 1):
            print(f"\n  LMS Match {i}:")
            print(f"    Payment ID: {match['payment_id']}")
            print(f"    Reserve No: {match['reserve']} ← USE THIS TO LINK!")
            print(f"    Account: {match['account']}")
            print(f"    Amount: ${match['amount']:,.2f} (diff: ${match['amount_diff']:.2f})")
            print(f"    Date: {match['date']} (diff: {match['date_diff']} days)" if match['date_diff'] is not None else f"    Date: {match['date']}")
            print(f"    Key: {match['key']}")

print(f"\n{'=' * 80}")
print(f"SUMMARY")
print("=" * 80)
print(f"LMS refund payments: 176 records, ${sum(abs(r[3]) for r in lms_refunds):,.2f}")
print(f"Unlinked charter_refunds: {len(unlinked)} records, ${sum(r[2] for r in unlinked if r[2]):,.2f}")
print(f"Matches found: {matches_found}")
print(f"Match rate: {matches_found/len(unlinked)*100:.1f}%")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("If matches were found with Reserve Numbers:")
print("  1. Create script to apply linkages (UPDATE charter_refunds SET reserve_number, charter_id)")
print("  2. Look up charter_id from charters table using reserve_number")
print("  3. Commit linkages and regenerate workbook")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
