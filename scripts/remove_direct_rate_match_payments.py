"""
Remove all payments that were incorrectly auto-linked via "Direct rate match".
These Square payments were already correctly linked to other charters, but got
duplicated by an auto-matching script that matched based on rate amounts.
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
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*120)
    print("REMOVE INCORRECTLY AUTO-LINKED 'DIRECT RATE MATCH' PAYMENTS")
    print("="*120 + "\n")
    
    # Find all payments with "Direct rate match" in notes
    cur.execute("""
        SELECT 
            p.payment_id,
            p.charter_id,
            c.reserve_number,
            p.payment_date,
            p.amount,
            p.square_transaction_id,
            p.notes
        FROM payments p
        LEFT JOIN charters c ON p.charter_id = c.charter_id
        WHERE LOWER(p.notes) LIKE '%direct rate match%'
        ORDER BY p.payment_id
    """)
    
    payments_to_delete = cur.fetchall()
    
    print(f"Found {len(payments_to_delete)} payments to remove\n")
    
    if not payments_to_delete:
        print("No payments to remove.")
        cur.close()
        conn.close()
        return
    
    # Group by charter to show impact
    charter_impact = {}
    total_amount = 0
    
    for payment in payments_to_delete:
        payment_id, charter_id, reserve_num, payment_date, amount, square_id, notes = payment
        total_amount += amount
        
        if reserve_num not in charter_impact:
            charter_impact[reserve_num] = {
                'charter_id': charter_id,
                'payment_count': 0,
                'total_amount': 0
            }
        
        charter_impact[reserve_num]['payment_count'] += 1
        charter_impact[reserve_num]['total_amount'] += amount
    
    print(f"Total amount to remove: ${total_amount:,.2f}")
    print(f"Charters affected: {len(charter_impact)}\n")
    
    print("Top 20 most affected charters:")
    print(f"{'Reserve':<10} {'Payments':<10} {'Amount':<15} {'Current Balance':<15}")
    print("-" * 120)
    
    sorted_charters = sorted(charter_impact.items(), 
                            key=lambda x: x[1]['payment_count'], 
                            reverse=True)[:20]
    
    for reserve_num, info in sorted_charters:
        # Get current charter balance
        cur.execute("""
            SELECT total_amount_due, paid_amount, balance
            FROM charters
            WHERE charter_id = %s
        """, (info['charter_id'],))
        result = cur.fetchone()
        if result:
            total_due, paid_amount, balance = result
            print(f"{reserve_num:<10} {info['payment_count']:<10} ${info['total_amount']:<14,.2f} ${balance:<14,.2f}")
    
    print("\n" + "="*120)
    print("ACTIONS TO PERFORM:")
    print("="*120)
    print("1. Delete all payments with 'Direct rate match' in notes")
    print("2. Recalculate paid_amount for all affected charters")
    print("3. Recalculate balance for all affected charters")
    print(f"\nThis will remove {len(payments_to_delete)} payment records totaling ${total_amount:,.2f}")
    print()
    
    response = input("Proceed with deletion? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Cancelled - no changes made")
        conn.rollback()
        cur.close()
        conn.close()
        return
    
    print("\nCreating backup...")
    
    # Create backup table with timestamp
    backup_table = f"payments_direct_rate_match_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM payments
        WHERE LOWER(notes) LIKE '%direct rate match%'
    """)
    
    backup_count = cur.rowcount
    print(f"✓ Backed up {backup_count} payments to table: {backup_table}")
    
    # Delete foreign key references first
    print("\nDeleting foreign key references...")
    
    # Delete from income_ledger
    cur.execute("""
        DELETE FROM income_ledger
        WHERE payment_id IN (
            SELECT payment_id FROM payments
            WHERE LOWER(notes) LIKE '%direct rate match%'
        )
    """)
    ledger_deleted = cur.rowcount
    print(f"✓ Deleted {ledger_deleted} income_ledger entries")
    
    # Delete from banking_payment_links
    cur.execute("""
        DELETE FROM banking_payment_links
        WHERE payment_id IN (
            SELECT payment_id FROM payments
            WHERE LOWER(notes) LIKE '%direct rate match%'
        )
    """)
    banking_links_deleted = cur.rowcount
    print(f"✓ Deleted {banking_links_deleted} banking_payment_links entries")
    
    # Delete the payments
    print("\nDeleting payments...")
    
    cur.execute("""
        DELETE FROM payments
        WHERE LOWER(notes) LIKE '%direct rate match%'
    """)
    
    deleted_count = cur.rowcount
    print(f"✓ Deleted {deleted_count} payment records")
    
    # Get list of affected charters
    affected_charter_ids = list(set(info['charter_id'] for info in charter_impact.values()))
    
    print(f"\nRecalculating balances for {len(affected_charter_ids)} charters...")
    
    # Recalculate paid_amount and balance for each affected charter
    for charter_id in affected_charter_ids:
        # Calculate total payments
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE charter_id = %s
        """, (charter_id,))
        new_paid_amount = cur.fetchone()[0]
        
        # Update charter
        cur.execute("""
            UPDATE charters
            SET paid_amount = %s,
                balance = COALESCE(total_amount_due, 0) - %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (new_paid_amount, new_paid_amount, charter_id))
    
    print(f"✓ Recalculated balances for {len(affected_charter_ids)} charters")
    
    # Show some examples of fixed charters
    print("\nExample fixes (top 5 most affected):")
    print(f"{'Reserve':<10} {'Old Balance':<15} {'New Balance':<15} {'Change':<15}")
    print("-" * 120)
    
    for reserve_num, info in sorted_charters[:5]:
        cur.execute("""
            SELECT balance FROM charters WHERE charter_id = %s
        """, (info['charter_id'],))
        new_balance = cur.fetchone()[0]
        
        # Calculate what old balance was
        cur.execute("""
            SELECT total_amount_due, paid_amount FROM charters WHERE charter_id = %s
        """, (info['charter_id'],))
        total_due, new_paid = cur.fetchone()
        
        old_balance = (total_due or 0) - ((new_paid or 0) + info['total_amount'])
        
        print(f"{reserve_num:<10} ${old_balance:<14,.2f} ${new_balance:<14,.2f} ${info['total_amount']:<14,.2f}")
    
    conn.commit()
    
    print("\n" + "="*120)
    print("COMPLETE!")
    print("="*120)
    print(f"\n✓ Deleted {deleted_count} incorrectly auto-linked payments")
    print(f"✓ Removed ${total_amount:,.2f} in false payment credits")
    print(f"✓ Fixed {len(affected_charter_ids)} charter balances")
    print(f"✓ Backup saved to: {backup_table}")
    print("\n" + "="*120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
