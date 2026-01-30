"""
Fix Charter 018864 - Remove 4 Incorrect ETR: Payment Linkages

Correct payments: 23969 ($500) + 24167 ($1,409) = $1,909
Incorrect ETR: payments: 100515, 100516, 100517, 100530 = $10,750
"""

import psycopg2
import os
from datetime import datetime

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
    print("FIX CHARTER 018864 - REMOVE 4 INCORRECT ETR: PAYMENT LINKAGES")
    print("=" * 80)
    print()
    
    incorrect_payment_ids = [100515, 100516, 100517, 100530]
    
    # Create backup
    backup_table = f"payments_backup_018864_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
    print(f"Unlinked {cur.rowcount} payments from charter 018864")
    print()
    
    # Recalculate charter
    cur.execute("""
        WITH payment_sum AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as total_paid
            FROM payments
            WHERE reserve_number = '018864'
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
    print(f"Updated charter 018864:")
    print(f"  Total Due: ${updated[1]}")
    print(f"  Paid Amount: ${updated[2]}")
    print(f"  Balance: ${updated[3]}")
    print()
    
    if updated[3] == 0:
        print("✓ SUCCESS: Charter 018864 balanced!")
    
    conn.commit()
    print("✓ Changes committed")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
