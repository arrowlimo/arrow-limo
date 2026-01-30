"""
Investigate Charter 017350 - $4,200 Overpayment

From audit: Due $1,050, shows $5,250 in payments (5 payments total)
Need to identify which payments are incorrectly linked.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("INVESTIGATE CHARTER 017350")
    print("=" * 80)
    print()
    
    # Get charter details
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, client_id,
               total_amount_due, paid_amount, balance, cancelled
        FROM charters
        WHERE reserve_number = '017350'
    """)
    charter = cur.fetchone()
    
    if not charter:
        print("Charter 017350 not found!")
        return
    
    print(f"Charter Details:")
    print(f"  Charter ID: {charter[0]}")
    print(f"  Reserve: {charter[1]}")
    print(f"  Date: {charter[2]}")
    print(f"  Client: {charter[3]}")
    print(f"  Total Due: ${charter[4]}")
    print(f"  Paid Amount: ${charter[5]}")
    print(f"  Balance: ${charter[6]}")
    print(f"  Cancelled: {charter[7]}")
    print()
    
    # Get all payments
    cur.execute("""
        SELECT p.payment_id, p.amount, p.payment_date, p.payment_key, 
               p.payment_method, p.charter_id, p.notes,
               bt.transaction_date, bt.description as bank_description
        FROM payments p
        LEFT JOIN banking_transactions bt ON p.payment_key = 'ETR:' || bt.transaction_id
        WHERE p.reserve_number = '017350'
        ORDER BY p.payment_date, p.payment_id
    """)
    payments = cur.fetchall()
    
    print(f"Payments linked to 017350: {len(payments)}")
    print("-" * 80)
    
    total_payments = 0
    for p in payments:
        total_payments += p[1]
        print(f"\nPayment {p[0]}:")
        print(f"  Amount: ${p[1]:.2f}")
        print(f"  Payment Date: {p[2]}")
        print(f"  Payment Key: {p[3]}")
        print(f"  Method: {p[4]}")
        print(f"  Charter ID: {p[5]}")
        if p[6]:
            print(f"  Notes: {p[6]}")
        
        # Check if ETR payment
        if p[3] and p[3].startswith('ETR:'):
            print(f"  *** ETR PAYMENT ***")
            if p[7]:
                print(f"  Bank Date: {p[7]}")
                print(f"  Bank Desc: {p[8]}")
                
                # Check date difference
                if p[2] and p[7]:
                    date_diff = abs((p[2] - p[7]).days)
                    print(f"  Date Diff: {date_diff} days")
                    if date_diff > 90:
                        print(f"  ⚠️ WARNING: >90 day date difference!")
    
    print()
    print("-" * 80)
    print(f"Total payment amount: ${total_payments:.2f}")
    print(f"Charter total due: ${charter[4]}")
    print(f"Difference: ${total_payments - charter[4]:.2f}")
    print()
    
    # Get charter charges
    cur.execute("""
        SELECT charge_id, description, amount, created_at
        FROM charter_charges
        WHERE charter_id = %s
        ORDER BY created_at
    """, (charter[0],))
    charges = cur.fetchall()
    
    print(f"Charter Charges: {len(charges)}")
    print("-" * 80)
    total_charges = 0
    for c in charges:
        total_charges += c[2]
        print(f"  Charge {c[0]}: ${c[2]:.2f} - {c[1]} (date: {c[3]})")
    
    print(f"Total charges: ${total_charges:.2f}")
    print()
    
    # Check for duplicate payment keys
    cur.execute("""
        SELECT payment_key, COUNT(*), SUM(amount), 
               STRING_AGG(reserve_number::text, ', ') as reserves
        FROM payments
        WHERE payment_key IN (
            SELECT payment_key FROM payments WHERE reserve_number = '017350'
        )
        GROUP BY payment_key
        HAVING COUNT(*) > 1
    """)
    dupes = cur.fetchall()
    
    if dupes:
        print("DUPLICATE PAYMENT KEYS:")
        print("-" * 80)
        for d in dupes:
            print(f"  Key {d[0]}: Used {d[1]} times, Total ${d[2]:.2f}")
            print(f"    Reserves: {d[3]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
