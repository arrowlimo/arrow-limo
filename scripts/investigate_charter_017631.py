"""
Investigate Charter 017631 - $31,796 Overpayment (WORST CASE)

From audit: Due $2,892, shows $34,688 in payments (13 payments total)
This is the most severe mismatch in the entire system.
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
    print("INVESTIGATE CHARTER 017631 - WORST CASE ($31,796 OVERPAYMENT)")
    print("=" * 80)
    print()
    
    # Get charter details
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, client_id,
               total_amount_due, paid_amount, balance, cancelled
        FROM charters
        WHERE reserve_number = '017631'
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
               bt.transaction_date, bt.description as bank_description,
               bt.debit_amount, bt.credit_amount
        FROM payments p
        LEFT JOIN banking_transactions bt ON p.payment_key = 'ETR:' || bt.transaction_id
        WHERE p.reserve_number = '017631'
        ORDER BY p.payment_date, p.payment_id
    """)
    payments = cur.fetchall()
    
    print(f"Payments linked to 017631: {len(payments)}")
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
            etr_payments.append((p[0], p[1]))
            if p[6]:
                print(f"  Bank Date: {p[6]}")
                print(f"  Bank Desc: {p[7]}")
                print(f"  Bank Debit: {p[8]}")
                print(f"  Bank Credit: {p[9]}")
                
                date_diff = abs((p[2] - p[6]).days) if p[2] and p[6] else 0
                print(f"  Date Diff: {date_diff} days")
                if date_diff > 90:
                    print(f"  ⚠️ WARNING: >90 day date difference!")
                
                # Check if transaction is income or expense
                if p[8] and p[8] > 0:  # Debit = money out
                    print(f"  🚨 EXPENSE TRANSACTION (money out, not income!)")
        else:
            normal_payments.append((p[0], p[1]))
    
    print()
    print("-" * 80)
    print(f"Total payment amount: ${total_payments:.2f}")
    print(f"Charter total due: ${charter[4]}")
    print(f"Difference: ${total_payments - charter[4]:.2f}")
    print()
    
    normal_total = sum(p[1] for p in normal_payments)
    etr_total = sum(p[1] for p in etr_payments)
    
    print(f"Normal payments ({len(normal_payments)}): {[p[0] for p in normal_payments]} = ${normal_total:.2f}")
    print(f"ETR: payments ({len(etr_payments)}): {[p[0] for p in etr_payments]} = ${etr_total:.2f}")
    print()
    
    print("RECOMMENDATION:")
    print(f"  Charter total due is ${charter[4]:.2f}")
    print(f"  Need to identify which payments (normal or ETR) are correct")
    print(f"  ETR payments total ${etr_total:.2f} - likely all incorrect based on pattern")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
