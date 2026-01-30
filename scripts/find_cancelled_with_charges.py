"""
Find all cancelled charters that still have charges.
Cancelled charters should have $0 total_amount_due and no charges.
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
    print("CANCELLED CHARTERS WITH CHARGES")
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
            c.balance,
            c.status,
            c.cancelled,
            (SELECT COUNT(*) FROM charter_charges WHERE charter_id = c.charter_id) as charge_count,
            (SELECT COALESCE(SUM(amount), 0) FROM charter_charges WHERE charter_id = c.charter_id) as charge_total
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.cancelled = TRUE
          AND EXISTS (
              SELECT 1 FROM charter_charges
              WHERE charter_id = c.charter_id
          )
        ORDER BY c.charter_date DESC, c.reserve_number DESC
    """)
    
    cancelled_with_charges = cur.fetchall()
    
    print(f"Found {len(cancelled_with_charges)} cancelled charters with charges\n")
    
    if not cancelled_with_charges:
        print("No cancelled charters have charges. Database is clean!")
        cur.close()
        conn.close()
        return
    
    print(f"{'Reserve':<10} {'Date':<12} {'Client':<30} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Charges':>8} {'Status':<20}")
    print("-" * 120)
    
    total_charges = 0
    total_due = 0
    total_paid = 0
    
    for charter in cancelled_with_charges:
        charter_id, reserve_num, charter_date, client_name, amount_due, paid, balance, status, cancelled, charge_count, charge_total = charter
        
        client_display = (client_name or 'Unknown')[:30]
        
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} {client_display:<30} ${amount_due or 0:>11,.2f} ${paid or 0:>11,.2f} ${balance or 0:>11,.2f} {charge_count:>8} {status or 'Cancelled':<20}")
        
        total_charges += charge_total
        total_due += (amount_due or 0)
        total_paid += (paid or 0)
    
    print("-" * 120)
    print(f"{'TOTALS':<53} ${total_due:>11,.2f} ${total_paid:>11,.2f}")
    print(f"\nTotal charges that should be deleted: ${total_charges:,.2f}")
    
    # Show breakdown by status
    print("\n" + "="*120)
    print("BREAKDOWN BY STATUS:")
    print("="*120 + "\n")
    
    cur.execute("""
        SELECT 
            c.status,
            COUNT(*) as charter_count,
            SUM((SELECT COALESCE(SUM(amount), 0) FROM charter_charges WHERE charter_id = c.charter_id)) as charge_total
        FROM charters c
        WHERE c.cancelled = TRUE
          AND EXISTS (
              SELECT 1 FROM charter_charges
              WHERE charter_id = c.charter_id
          )
        GROUP BY c.status
        ORDER BY charter_count DESC
    """)
    
    status_breakdown = cur.fetchall()
    
    print(f"{'Status':<30} {'Count':<10} {'Total Charges':<15}")
    print("-" * 120)
    
    for status, count, charges in status_breakdown:
        print(f"{status or '(NULL)':<30} {count:<10} ${charges:>13,.2f}")
    
    print("\n" + "="*120)
    print("SUMMARY:")
    print("="*120)
    print(f"\nThese {len(cancelled_with_charges)} cancelled charters have charges that should be removed.")
    print("Cancelled charters should have:")
    print("  - total_amount_due = $0.00")
    print("  - All charter_charges deleted")
    print("  - balance = 0 - paid_amount (showing any non-refundable deposits as credits)")
    print("\n" + "="*120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
