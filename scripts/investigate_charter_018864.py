"""
Investigate Charter 018864 - $10,750 Overpayment

From audit: Due $1,909, shows $12,659 in payments (6 payments total)
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("INVESTIGATE CHARTER 018864")
    print("=" * 80)
    print()
    
    # Get charter details
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, client_id,
               total_amount_due, paid_amount, balance, cancelled
        FROM charters
        WHERE reserve_number = '018864'
    """)
    charter = cur.fetchone()
    
    print(f"Charter Details:")
    print(f"  Charter ID: {charter[0]}")
    print(f"  Reserve: {charter[1]}")
    print(f"  Date: {charter[2]}")
    print(f"  Client ID: {charter[3]}")
    print(f"  Total Due: ${charter[4]}")
    print(f"  Paid Amount: ${charter[5]}")
    print(f"  Balance: ${charter[6]}")
    print(f"  Cancelled: {charter[7]}")
    print()
    
    # Get all payments
    cur.execute("""
        SELECT p.payment_id, p.amount, p.payment_date, p.payment_key, 
               p.payment_method, p.charter_id,
               bt.transaction_date, bt.description as bank_description
        FROM payments p
        LEFT JOIN banking_transactions bt ON p.payment_key = 'ETR:' || bt.transaction_id
        WHERE p.reserve_number = '018864'
        ORDER BY p.payment_date, p.payment_id
    """)
    payments = cur.fetchall()
    
    print(f"Payments linked to 018864: {len(payments)}")
    print("-" * 80)
    
    total_payments = 0
    etr_payments = []
    normal_payments = []
    
    for p in payments:
        total_payments += p[1]
        is_etr = p[3] and p[3].startswith('ETR:')
        
        print(f"\nPayment {p[0]}:")
        print(f"  Amount: ${p[1]:.2f}")
        print(f"  Payment Date: {p[2]}")
        print(f"  Payment Key: {p[3]}")
        print(f"  Method: {p[4]}")
        print(f"  Charter ID: {p[5]}")
        
        if is_etr:
            print(f"  *** ETR PAYMENT ***")
            etr_payments.append(p[0])
            if p[6]:
                print(f"  Bank Date: {p[6]}")
                print(f"  Bank Desc: {p[7]}")
                
                date_diff = abs((p[2] - p[6]).days) if p[2] and p[6] else 0
                print(f"  Date Diff: {date_diff} days")
                if date_diff > 90:
                    print(f"  ⚠️ WARNING: >90 day date difference!")
        else:
            normal_payments.append(p[0])
    
    print()
    print("-" * 80)
    print(f"Total payment amount: ${total_payments:.2f}")
    print(f"Charter total due: ${charter[4]}")
    print(f"Difference: ${total_payments - charter[4]:.2f}")
    print()
    print(f"Normal payments ({len(normal_payments)}): {normal_payments}")
    print(f"ETR: payments ({len(etr_payments)}): {etr_payments}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
