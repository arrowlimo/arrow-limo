"""
Fix Charter 016461 - Remove 14 Incorrect Payment Linkages

Based on check_016461_payment_links.py analysis:
- Keep only 2 correct payments: 20184 ($400) and 21027 ($230) = $630
- Remove reserve_number='016461' from 14 incorrect payments with ETR: keys
- Set cancelled=FALSE (charter was rebooked and paid in full)
- Recalculate paid_amount to $630

Incorrect payment IDs to unlink:
100128, 100157, 100160, 100161, 100162, 100163, 100164, 100165, 100166, 
100168, 100173, 100174, 100175, 100183
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
    print("FIX CHARTER 016461 - REMOVE INCORRECT PAYMENT LINKAGES")
    print("=" * 80)
    print()
    
    # IDs of incorrect payments to unlink
    incorrect_payment_ids = [
        100128, 100157, 100160, 100161, 100162, 100163, 100164, 100165, 
        100166, 100168, 100173, 100174, 100175, 100183
    ]
    
    print("STEP 1: Verify current state")
    print("-" * 80)
    
    # Check charter current state
    cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount, 
               balance, cancelled
        FROM charters 
        WHERE reserve_number = '016461'
    """)
    charter = cur.fetchone()
    
    if charter:
        print(f"Charter 016461:")
        print(f"  Date: {charter[1]}")
        print(f"  Total Due: ${charter[2]}")
        print(f"  Paid Amount: ${charter[3]}")
        print(f"  Balance: ${charter[4]}")
        print(f"  Cancelled: {charter[5]}")
    else:
        print("ERROR: Charter 016461 not found!")
        return
    
    print()
    
    # Check current payments
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, charter_id
        FROM payments
        WHERE reserve_number = '016461'
        ORDER BY payment_id
    """)
    current_payments = cur.fetchall()
    
    print(f"Current payments linked to 016461: {len(current_payments)}")
    total_current = sum(p[1] for p in current_payments)
    print(f"Total current payment amount: ${total_current:.2f}")
    print()
    
    # Identify correct vs incorrect
    correct_payments = [p for p in current_payments if p[0] in [20184, 21027]]
    incorrect_payments = [p for p in current_payments if p[0] in incorrect_payment_ids]
    
    print(f"Correct payments (2): {[p[0] for p in correct_payments]}")
    correct_total = sum(p[1] for p in correct_payments)
    print(f"  Total: ${correct_total:.2f}")
    print()
    
    print(f"Incorrect payments ({len(incorrect_payments)}): {[p[0] for p in incorrect_payments]}")
    incorrect_total = sum(p[1] for p in incorrect_payments)
    print(f"  Total: ${incorrect_total:.2f}")
    print()
    
    # Verify we found all incorrect payments
    if len(incorrect_payments) != len(incorrect_payment_ids):
        print(f"WARNING: Expected {len(incorrect_payment_ids)} incorrect payments, found {len(incorrect_payments)}")
        missing = set(incorrect_payment_ids) - set(p[0] for p in incorrect_payments)
        if missing:
            print(f"  Missing payment IDs: {missing}")
    
    print()
    print("STEP 2: Create backup")
    print("-" * 80)
    
    backup_table = f"payments_backup_016461_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM payments
        WHERE payment_id IN ({','.join(map(str, incorrect_payment_ids))})
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"Created backup: {backup_table}")
    print(f"  Backed up {backup_count} payments")
    print()
    
    print("STEP 3: Remove incorrect payment linkages")
    print("-" * 80)
    
    # Remove reserve_number from incorrect payments (set to NULL)
    cur.execute(f"""
        UPDATE payments
        SET reserve_number = NULL,
            charter_id = NULL
        WHERE payment_id IN ({','.join(map(str, incorrect_payment_ids))})
    """)
    
    unlinked_count = cur.rowcount
    print(f"Unlinked {unlinked_count} payments from charter 016461")
    print()
    
    print("STEP 4: Update charter status")
    print("-" * 80)
    
    # Recalculate paid_amount from remaining linked payments
    cur.execute("""
        WITH payment_sum AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as total_paid
            FROM payments
            WHERE reserve_number = '016461'
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.total_paid,
            balance = c.total_amount_due - ps.total_paid,
            cancelled = FALSE
        FROM payment_sum ps
        WHERE c.reserve_number = ps.reserve_number
        RETURNING c.reserve_number, c.total_amount_due, c.paid_amount, c.balance, c.cancelled
    """)
    
    updated = cur.fetchone()
    if updated:
        print(f"Updated charter 016461:")
        print(f"  Total Due: ${updated[1]}")
        print(f"  Paid Amount: ${updated[2]}")
        print(f"  Balance: ${updated[3]}")
        print(f"  Cancelled: {updated[4]}")
    
    print()
    print("STEP 5: Verify final state")
    print("-" * 80)
    
    # Check final payments
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key
        FROM payments
        WHERE reserve_number = '016461'
        ORDER BY payment_date
    """)
    final_payments = cur.fetchall()
    
    print(f"Final payments linked to 016461: {len(final_payments)}")
    for p in final_payments:
        print(f"  Payment {p[0]}: ${p[1]:.2f} on {p[2]} (key: {p[3]})")
    
    final_total = sum(p[1] for p in final_payments)
    print(f"Total final payment amount: ${final_total:.2f}")
    print()
    
    if len(final_payments) == 2 and final_total == 630.00:
        print("✓ SUCCESS: Charter 016461 corrected!")
        print("  - 2 correct payments remain ($630 total)")
        print("  - 14 incorrect payments unlinked")
        print("  - Charter marked as not cancelled (rebooked)")
        print("  - Balance should be $0.00")
    else:
        print("⚠ WARNING: Unexpected final state")
        print(f"  Expected 2 payments totaling $630, got {len(final_payments)} totaling ${final_total:.2f}")
    
    print()
    print("=" * 80)
    print("COMMIT CHANGES? (yes/no): ", end="")
    response = input().strip().lower()
    
    if response == 'yes':
        conn.commit()
        print("✓ Changes committed to database")
    else:
        conn.rollback()
        print("✗ Changes rolled back")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
