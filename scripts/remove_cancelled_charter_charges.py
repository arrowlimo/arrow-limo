"""
Remove charges from all cancelled charters.
Cancelled charters should have no charges.
"""

import psycopg2
import os

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*120)
    print("REMOVE CHARGES FROM CANCELLED CHARTERS")
    print("="*120 + "\n")
    
    # Find cancelled charters with charges
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.cancelled = TRUE
          AND EXISTS (
              SELECT 1 FROM charter_charges
              WHERE charter_id = c.charter_id
          )
        ORDER BY c.reserve_number
    """)
    
    cancelled_charters = cur.fetchall()
    
    print(f"Found {len(cancelled_charters)} cancelled charters with charges\n")
    
    if not cancelled_charters:
        print("No cancelled charters have charges. Nothing to do!")
        cur.close()
        conn.close()
        return
    
    print(f"{'Reserve':<10} {'Date':<12} {'Client':<35} {'Total Due':>12} {'Paid':>12} {'Balance':>12}")
    print("-" * 120)
    
    for charter in cancelled_charters:
        charter_id, reserve_num, charter_date, client_name, amount_due, paid, balance = charter
        client_display = (client_name or 'Unknown')[:35]
        
        # Get charge details
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        charge_count, charge_total = cur.fetchone()
        
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} {client_display:<35} ${amount_due or 0:>11,.2f} ${paid or 0:>11,.2f} ${balance or 0:>11,.2f}")
        print(f"           {'→ ' + str(charge_count) + ' charges totaling $' + f'{charge_total:,.2f}'}")
    
    print("\n" + "="*120)
    print("ACTIONS TO PERFORM:")
    print("="*120)
    print("1. Delete all charter_charges for cancelled charters")
    print("2. Verify total_amount_due = 0 (should already be correct)")
    print("3. Verify balance = 0 - paid_amount")
    print()
    
    response = input(f"Proceed with removing charges from {len(cancelled_charters)} cancelled charters? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Cancelled - no changes made")
        conn.rollback()
        cur.close()
        conn.close()
        return
    
    print("\nProcessing charters...\n")
    
    total_charges_deleted = 0
    
    for charter in cancelled_charters:
        charter_id, reserve_num, charter_date, client_name, amount_due, paid, balance = charter
        
        # Get charge count
        cur.execute("""
            SELECT COUNT(*) FROM charter_charges WHERE charter_id = %s
        """, (charter_id,))
        charge_count = cur.fetchone()[0]
        
        # Delete charges
        cur.execute("""
            DELETE FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        deleted = cur.rowcount
        total_charges_deleted += deleted
        
        # Verify charter state
        cur.execute("""
            UPDATE charters
            SET total_amount_due = 0,
                balance = 0 - COALESCE(paid_amount, 0),
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (charter_id,))
        
        # Get final balance
        cur.execute("""
            SELECT balance FROM charters WHERE charter_id = %s
        """, (charter_id,))
        final_balance = cur.fetchone()[0]
        
        balance_display = f"${final_balance:,.2f}" if final_balance != 0 else "$0.00"
        print(f"✓ {reserve_num}: Deleted {deleted} charges, balance: {balance_display}")
    
    conn.commit()
    
    print("\n" + "="*120)
    print(f"COMPLETE: Deleted {total_charges_deleted} charge records from {len(cancelled_charters)} cancelled charters")
    print("="*120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
