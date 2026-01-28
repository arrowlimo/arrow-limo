"""
Find Waste Connections charters that are closed but not fully paid.
Remove charges from unpaid closed charters.
"""

import psycopg2
import os

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
    
    print("\n" + "="*100)
    print("WASTE CONNECTIONS CHARTER CLEANUP")
    print("="*100 + "\n")
    
    # Find Waste Connections charters that are closed with balances
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.cancelled,
            c.closed
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE LOWER(cl.client_name) LIKE '%waste connection%'
          AND (c.closed = TRUE OR LOWER(c.status) LIKE '%closed%')
          AND c.balance != 0
          AND COALESCE(c.cancelled, FALSE) = FALSE
        ORDER BY c.charter_date, c.reserve_number
    """)
    
    charters = cur.fetchall()
    
    print(f"Found {len(charters)} Waste Connections charters that are closed with balances\n")
    
    if not charters:
        print("No charters to process.")
        cur.close()
        conn.close()
        return
    
    print(f"{'Reserve':<10} {'Date':<12} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Status':<20}")
    print("-" * 100)
    
    for charter in charters:
        charter_id, reserve_num, charter_date, client_name, total_due, paid, balance, status, cancelled, closed = charter
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} ${total_due or 0:>11,.2f} ${paid or 0:>11,.2f} ${balance or 0:>11,.2f} {status or 'N/A':<20}")
    
    print("\n" + "="*100)
    print("ACTIONS TO PERFORM FOR EACH CHARTER:")
    print("="*100)
    print("1. Delete all charter_charges records")
    print("2. Set total_amount_due = 0")
    print("3. Recalculate balance = 0 - paid_amount")
    print("4. Keep status/closed/cancelled as is")
    print()
    
    response = input(f"Proceed with removing charges from {len(charters)} charters? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Cancelled - no changes made")
        conn.rollback()
        cur.close()
        conn.close()
        return
    
    print("\nProcessing charters...\n")
    
    total_charges_deleted = 0
    
    for charter in charters:
        charter_id, reserve_num, charter_date, client_name, total_due, paid, balance, status, cancelled, closed = charter
        
        # Get charge count first
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        charge_count, charge_total = cur.fetchone()
        
        if charge_count > 0:
            # Delete charges
            cur.execute("""
                DELETE FROM charter_charges
                WHERE charter_id = %s
            """, (charter_id,))
            deleted = cur.rowcount
            total_charges_deleted += deleted
            
            # Update charter
            cur.execute("""
                UPDATE charters
                SET total_amount_due = 0,
                    balance = 0 - COALESCE(paid_amount, 0),
                    updated_at = CURRENT_TIMESTAMP
                WHERE charter_id = %s
            """, (charter_id,))
            
            # Get new balance
            cur.execute("""
                SELECT balance
                FROM charters
                WHERE charter_id = %s
            """, (charter_id,))
            new_balance = cur.fetchone()[0]
            
            print(f"✓ {reserve_num}: Deleted {deleted} charges (${charge_total:,.2f}), new balance: ${new_balance:,.2f}")
        else:
            print(f"  {reserve_num}: No charges found (already cleaned)")
    
    conn.commit()
    
    print("\n" + "="*100)
    print(f"COMPLETE: Deleted {total_charges_deleted} charge records from {len(charters)} charters")
    print("="*100 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
