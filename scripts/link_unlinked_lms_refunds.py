"""
Link the 2 unlinked LMS refunds.

Based on analysis:
- Refund #1047 ($100.00, 2025-06-20) - LMS Deposit 0022254 "Credit"
- Refund #1048 ($400.00, 2025-07-28) - LMS Deposit 0022368

Need to find the correct charters for these refunds.
"""
import os
import psycopg2
import argparse

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

parser = argparse.ArgumentParser()
parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("LINKING UNLINKED LMS REFUNDS")
print("="*80)

# First, let's check these refunds and find matching charters
REFUNDS_TO_CHECK = [
    (1047, 100.00, '2025-06-20', '0022254', 'Credit'),
    (1048, 400.00, '2025-07-28', '0022368', ''),
]

for refund_id, amount, refund_date, deposit_num, description in REFUNDS_TO_CHECK:
    print(f"\n{'*'*60}")
    print(f"Refund #{refund_id}: ${amount} on {refund_date}")
    print(f"  LMS Deposit: {deposit_num} - {description}")
    
    # Get current state
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id, 
               description, square_payment_id
        FROM charter_refunds
        WHERE id = %s
    """, (refund_id,))
    refund = cur.fetchone()
    
    if not refund:
        print(f"  [FAIL] Refund not found!")
        continue
    
    print(f"  Current: Reserve={refund[3]}, Charter={refund[4]}")
    print(f"  Description: {refund[5]}")
    
    # Look for charters near this date with matching amounts
    # Search for payments matching this amount around the refund date
    cur.execute("""
        SELECT p.payment_id, p.payment_date, p.amount, p.reserve_number, 
               p.charter_id, c.charter_date, p.notes
        FROM payments p
        LEFT JOIN charters c ON c.charter_id = p.charter_id
        WHERE ABS(p.amount) = %s
          AND p.payment_date BETWEEN %s::date - INTERVAL '30 days' 
                                 AND %s::date + INTERVAL '30 days'
        ORDER BY ABS(p.payment_date - %s::date)
        LIMIT 5
    """, (amount, refund_date, refund_date, refund_date))
    matching_payments = cur.fetchall()
    
    if matching_payments:
        print(f"\n  💰 Found {len(matching_payments)} payment(s) with matching amount:")
        for p in matching_payments:
            pay_id, pay_date, pay_amt, reserve, charter, charter_date, notes = p
            print(f"    Payment #{pay_id}: ${pay_amt} on {pay_date}")
            print(f"      Reserve: {reserve}, Charter: {charter}, Charter Date: {charter_date}")
            if notes:
                print(f"      Notes: {notes[:80]}")
        
        # Use the first match if charter exists
        if matching_payments[0][4]:  # Has charter_id
            suggested_reserve = matching_payments[0][3]
            suggested_charter = matching_payments[0][4]
            
            if suggested_reserve and suggested_charter:
                print(f"\n  💡 SUGGESTED LINK: Reserve {suggested_reserve}, Charter {suggested_charter}")
                
                if args.write:
                    cur.execute("""
                        UPDATE charter_refunds
                        SET reserve_number = %s,
                            charter_id = %s
                        WHERE id = %s
                    """, (suggested_reserve, suggested_charter, refund_id))
                    print(f"  [OK] UPDATED")
                else:
                    print(f"  [DRY-RUN] Would update")
    else:
        print(f"  [WARN] No matching payments found within 30 days")
        
        # Try searching by description in LMS deposits
        print(f"\n  Searching for LMS deposit {deposit_num} in payment notes...")
        cur.execute("""
            SELECT p.payment_id, p.payment_date, p.amount, p.reserve_number, 
                   p.charter_id, p.notes
            FROM payments p
            WHERE notes ILIKE %s
            LIMIT 5
        """, (f'%{deposit_num}%',))
        deposit_payments = cur.fetchall()
        
        if deposit_payments:
            print(f"  Found {len(deposit_payments)} payment(s) with deposit number:")
            for p in deposit_payments:
                pay_id, pay_date, pay_amt, reserve, charter, notes = p
                print(f"    Payment #{pay_id}: ${pay_amt} on {pay_date}")
                print(f"      Reserve: {reserve}, Charter: {charter}")

if args.write:
    conn.commit()
    print("\n" + "="*80)
    print("[OK] CHANGES COMMITTED")
    print("="*80)
else:
    conn.rollback()
    print("\n" + "="*80)
    print("DRY-RUN COMPLETE (use --write to apply changes)")
    print("="*80)

# Final verification
print(f"\n{'='*80}")
print("VERIFICATION")
print(f"{'='*80}")

for refund_id, amount, refund_date, deposit_num, description in REFUNDS_TO_CHECK:
    cur.execute("""
        SELECT id, reserve_number, charter_id
        FROM charter_refunds
        WHERE id = %s
    """, (refund_id,))
    refund = cur.fetchone()
    
    if refund:
        status = "[OK] LINKED" if refund[1] and refund[2] else "[FAIL] UNLINKED"
        print(f"{status} Refund #{refund[0]}: Reserve {refund[1]}, Charter {refund[2]}")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("COMPLETE")
print(f"{'='*80}")
