"""
Fix charters 016593 and 001918:
- 016593: Already cancelled, verify charges removed
- 001918: $205 non-refundable retainer, mark cancelled, erase charges, close
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("CHARTER CANCELLATION CLEANUP - 016593 & 001918")
    print("="*80 + "\n")
    
    # Charter 016593 - Verify status
    print("CHARTER 016593 - 1979535 Alberta Ltd")
    print("-" * 80)
    cur.execute("""
        SELECT charter_id, reserve_number, client_id, charter_date,
               total_amount_due, paid_amount, balance, cancelled, status
        FROM charters
        WHERE reserve_number = '016593'
    """)
    charter_016593 = cur.fetchone()
    
    if charter_016593:
        charter_id, reserve_num, client_id, charter_date, total_due, paid, balance, cancelled, status = charter_016593
        print(f"Current Status:")
        print(f"  Charter ID: {charter_id}")
        print(f"  Date: {charter_date}")
        print(f"  Total Due: ${total_due or 0:,.2f}")
        print(f"  Paid: ${paid or 0:,.2f}")
        print(f"  Balance: ${balance or 0:,.2f}")
        print(f"  Cancelled: {cancelled}")
        print(f"  Status: {status}")
        
        # Check for charges
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        charge_count, charge_total = cur.fetchone()
        print(f"  Charges: {charge_count} records, ${charge_total:,.2f} total")
        
        if cancelled:
            print("✓ Already marked as cancelled")
        
        if charge_count == 0:
            print("✓ Charges already removed")
        
        print()
    else:
        print("ERROR: Charter 016593 not found!")
        print()
    
    # Charter 001918 - Process cancellation
    print("CHARTER 001918 - $205 Non-Refundable Retainer")
    print("-" * 80)
    cur.execute("""
        SELECT charter_id, reserve_number, client_id, charter_date,
               total_amount_due, paid_amount, balance, cancelled, status
        FROM charters
        WHERE reserve_number = '001918'
    """)
    charter_001918 = cur.fetchone()
    
    if charter_001918:
        charter_id, reserve_num, client_id, charter_date, total_due, paid, balance, cancelled, status = charter_001918
        print(f"Current Status:")
        print(f"  Charter ID: {charter_id}")
        print(f"  Date: {charter_date}")
        print(f"  Total Due: ${total_due or 0:,.2f}")
        print(f"  Paid: ${paid or 0:,.2f}")
        print(f"  Balance: ${balance or 0:,.2f}")
        print(f"  Cancelled: {cancelled}")
        print(f"  Status: {status}")
        
        # Check for charges
        cur.execute("""
            SELECT charge_id, description, amount
            FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        charges = cur.fetchall()
        print(f"  Charges: {len(charges)} records")
        for charge_id, desc, amount in charges:
            print(f"    - Charge {charge_id}: {desc} - ${amount:,.2f}")
        
        # Check for payments
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method
            FROM payments
            WHERE charter_id = %s
            ORDER BY payment_date
        """, (charter_id,))
        payments = cur.fetchall()
        print(f"  Payments: {len(payments)} records")
        for payment_id, payment_date, amount, method in payments:
            print(f"    - Payment {payment_id}: {payment_date} - ${amount:,.2f} ({method or 'unknown'})")
        
        print("\n" + "="*80)
        print("ACTIONS TO PERFORM:")
        print("="*80)
        print("1. Delete all charter_charges records")
        print("2. Set total_amount_due = 0")
        print("3. Recalculate balance = 0 - paid_amount (will show credit)")
        print("4. Set cancelled = TRUE")
        print("5. Set status = 'Cancelled $$' (non-refundable retainer)")
        print()
        
        response = input("Proceed with cancellation? (yes/no): ").strip().lower()
        
        if response == 'yes':
            # Delete charges
            cur.execute("""
                DELETE FROM charter_charges
                WHERE charter_id = %s
            """, (charter_id,))
            deleted_charges = cur.rowcount
            print(f"✓ Deleted {deleted_charges} charge records")
            
            # Update charter
            cur.execute("""
                UPDATE charters
                SET total_amount_due = 0,
                    balance = 0 - COALESCE(paid_amount, 0),
                    cancelled = TRUE,
                    status = 'Cancelled $$',
                    updated_at = CURRENT_TIMESTAMP
                WHERE charter_id = %s
            """, (charter_id,))
            print(f"✓ Updated charter status to Cancelled $$")
            
            # Verify final state
            cur.execute("""
                SELECT total_amount_due, paid_amount, balance, cancelled, status
                FROM charters
                WHERE charter_id = %s
            """, (charter_id,))
            final_total, final_paid, final_balance, final_cancelled, final_status = cur.fetchone()
            
            print(f"\nFinal State:")
            print(f"  Total Due: ${final_total or 0:,.2f}")
            print(f"  Paid: ${final_paid or 0:,.2f}")
            print(f"  Balance: ${final_balance or 0:,.2f}")
            print(f"  Cancelled: {final_cancelled}")
            print(f"  Status: {final_status}")
            
            conn.commit()
            print("\n✓ Changes committed to database")
        else:
            print("Cancelled - no changes made")
            conn.rollback()
        
        print()
    else:
        print("ERROR: Charter 001918 not found!")
        print()
    
    cur.close()
    conn.close()
    
    print("="*80)
    print("PROCESSING COMPLETE")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
