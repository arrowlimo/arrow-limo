"""
Find charters with $0 balance that are not closed.
These should likely be marked as closed/paid in full.
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
    print("CHARTERS WITH $0 BALANCE NOT MARKED AS CLOSED")
    print("="*120 + "\n")
    
    # Find charters with $0 balance that are not closed
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
            c.closed,
            c.cancelled,
            c.payment_status
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.balance = 0
          AND COALESCE(c.closed, FALSE) = FALSE
          AND COALESCE(c.cancelled, FALSE) = FALSE
          AND c.charter_date < CURRENT_DATE
        ORDER BY c.charter_date DESC, c.reserve_number DESC
        LIMIT 100
    """)
    
    zero_balance_not_closed = cur.fetchall()
    
    print(f"Found {len(zero_balance_not_closed)} charters with $0 balance not marked as closed\n")
    
    if not zero_balance_not_closed:
        print("All charters with $0 balance are properly closed!")
        cur.close()
        conn.close()
        return
    
    print(f"{'Reserve':<10} {'Date':<12} {'Client':<30} {'Total Due':>12} {'Paid':>12} {'Status':<20} {'Closed':<8}")
    print("-" * 120)
    
    for charter in zero_balance_not_closed:
        charter_id, reserve_num, charter_date, client_name, total_due, paid, balance, status, closed, cancelled, payment_status = charter
        
        client_display = (client_name or 'Unknown')[:30]
        
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} {client_display:<30} ${total_due or 0:>11,.2f} ${paid or 0:>11,.2f} {status or 'N/A':<20} {str(closed):<8}")
    
    print("-" * 120)
    
    # Breakdown by status
    print("\n" + "="*120)
    print("BREAKDOWN BY STATUS:")
    print("="*120 + "\n")
    
    cur.execute("""
        SELECT 
            c.status,
            COUNT(*) as count
        FROM charters c
        WHERE c.balance = 0
          AND COALESCE(c.closed, FALSE) = FALSE
          AND COALESCE(c.cancelled, FALSE) = FALSE
          AND c.charter_date < CURRENT_DATE
        GROUP BY c.status
        ORDER BY count DESC
    """)
    
    status_breakdown = cur.fetchall()
    
    print(f"{'Status':<30} {'Count':<10}")
    print("-" * 120)
    
    for status, count in status_breakdown:
        print(f"{status or '(NULL)':<30} {count:<10}")
    
    # Get total count
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.balance = 0
          AND COALESCE(c.closed, FALSE) = FALSE
          AND COALESCE(c.cancelled, FALSE) = FALSE
          AND c.charter_date < CURRENT_DATE
    """)
    
    total_count = cur.fetchone()[0]
    
    print("\n" + "="*120)
    print("SUMMARY:")
    print("="*120)
    print(f"\nTotal charters with $0 balance not marked as closed: {total_count}")
    print("\nThese charters are fully paid but not marked as closed.")
    print("Recommendation: Update status to 'Closed' or 'Paid in Full' and set closed = TRUE")
    print("\n" + "="*120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
