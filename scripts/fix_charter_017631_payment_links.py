"""
Fix Charter 017631 - Remove 9 Incorrect ETR: Payment Linkages (WORST CASE)

Correct payments: 21952, 22554, 22555, 22576 = $2,892 ✓
Incorrect ETR: payments: All 9 are business expenses incorrectly linked = $31,796 ✗
  - 100263: Service charge
  - 100302: Gas station purchase
  - 100306: Square merchant payment (CREDIT - actually income but wrong charter)
  - 100309, 100312: Petro-Canada gas purchases
  - 100313: Square merchant payment (CREDIT - wrong charter)
  - 100314, 100315: Heffner Auto car payments
  - 100317: Barb Peacock personal e-transfer
"""

import psycopg2
import os
from datetime import datetime

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
    print("FIX CHARTER 017631 - REMOVE 9 INCORRECT ETR: PAYMENT LINKAGES")
    print("=" * 80)
    print()
    
    incorrect_payment_ids = [100263, 100302, 100306, 100309, 100312, 100313, 100314, 100315, 100317]
    
    # Create backup
    backup_table = f"payments_backup_017631_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM payments
        WHERE payment_id IN ({','.join(map(str, incorrect_payment_ids))})
    """)
    print(f"Created backup: {backup_table}")
    print()
    
    # Unlink incorrect payments
    cur.execute(f"""
        UPDATE payments
        SET reserve_number = NULL,
            charter_id = NULL
        WHERE payment_id IN ({','.join(map(str, incorrect_payment_ids))})
    """)
    print(f"Unlinked {cur.rowcount} payments from charter 017631")
    print(f"  These were all business expenses (gas, car payments, bank fees, personal transfers)")
    print()
    
    # Recalculate charter
    cur.execute("""
        WITH payment_sum AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as total_paid
            FROM payments
            WHERE reserve_number = '017631'
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.total_paid,
            balance = c.total_amount_due - ps.total_paid
        FROM payment_sum ps
        WHERE c.reserve_number = ps.reserve_number
        RETURNING c.reserve_number, c.total_amount_due, c.paid_amount, c.balance
    """)
    
    updated = cur.fetchone()
    print(f"Updated charter 017631:")
    print(f"  Total Due: ${updated[1]}")
    print(f"  Paid Amount: ${updated[2]}")
    print(f"  Balance: ${updated[3]}")
    print()
    
    if updated[3] == 0:
        print("✓ SUCCESS: Charter 017631 balanced!")
        print(f"✓ Removed $31,796 in incorrect expense transactions")
        print(f"✓ Kept $2,892 in correct customer payments")
    
    conn.commit()
    print("✓ Changes committed")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
