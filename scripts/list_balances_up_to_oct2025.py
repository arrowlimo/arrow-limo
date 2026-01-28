"""
List all charters up to October 2025 with outstanding balances.
Shows charter details, amounts due, payments, and current balance.
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
    
    # Get all charters up to Oct 31, 2025 with non-zero balances
    query = """
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.client_id,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.cancelled,
            c.payment_status
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date <= '2025-10-31'
          AND c.balance != 0
          AND COALESCE(c.cancelled, false) = false
        ORDER BY c.charter_date, c.reserve_number
    """
    
    cur.execute(query)
    charters = cur.fetchall()
    
    print(f"\n{'='*120}")
    print(f"CHARTERS WITH OUTSTANDING BALANCES (Up to October 31, 2025)")
    print(f"{'='*120}\n")
    
    if not charters:
        print("No charters found with outstanding balances up to October 2025.")
        cur.close()
        conn.close()
        return
    
    print(f"{'Reserve':<10} {'Date':<12} {'Client':<30} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Status':<15}")
    print(f"{'-'*120}")
    
    total_due = 0
    total_paid = 0
    total_balance = 0
    positive_balances = 0
    negative_balances = 0
    
    for charter in charters:
        charter_id, reserve_num, charter_date, client_id, client_name, amount_due, paid, balance, status, cancelled, payment_status = charter
        
        # Truncate client name if too long
        client_display = (client_name or 'Unknown')[:30]
        
        # Format amounts
        due_str = f"${amount_due or 0:,.2f}"
        paid_str = f"${paid or 0:,.2f}"
        balance_str = f"${balance or 0:,.2f}"
        
        # Color code balance (for visual reference in output)
        balance_indicator = "[WARN]" if balance and balance > 0 else "💰" if balance and balance < 0 else ""
        
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} {client_display:<30} {due_str:>12} {paid_str:>12} {balance_str:>12} {status or 'N/A':<15}")
        
        total_due += (amount_due or 0)
        total_paid += (paid or 0)
        total_balance += (balance or 0)
        
        if balance and balance > 0:
            positive_balances += 1
        elif balance and balance < 0:
            negative_balances += 1
    
    print(f"{'-'*120}")
    print(f"{'TOTALS':<53} ${total_due:>11,.2f} ${total_paid:>11,.2f} ${total_balance:>11,.2f}")
    print(f"\n{'='*120}")
    print(f"\nSUMMARY:")
    print(f"  Total charters with balances: {len(charters)}")
    print(f"  Charters owing money (positive balance): {positive_balances}")
    print(f"  Charters with credits (negative balance): {negative_balances}")
    print(f"  Net balance outstanding: ${total_balance:,.2f}")
    print(f"{'='*120}\n")
    
    # Show top 10 largest balances owing
    print("\nTOP 10 LARGEST BALANCES OWING:")
    print(f"{'-'*120}")
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date <= '2025-10-31'
          AND c.balance > 0
          AND COALESCE(c.cancelled, false) = false
        ORDER BY c.balance DESC
        LIMIT 10
    """)
    
    top_owing = cur.fetchall()
    
    for charter in top_owing:
        reserve_num, charter_date, client_name, amount_due, paid, balance = charter
        client_display = (client_name or 'Unknown')[:40]
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} {client_display:<40} Balance: ${balance:,.2f}")
    
    # Show top 10 largest credits
    print(f"\n\nTOP 10 LARGEST CREDITS (Overpayments):")
    print(f"{'-'*120}")
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date <= '2025-10-31'
          AND c.balance < 0
          AND COALESCE(c.cancelled, false) = false
        ORDER BY c.balance ASC
        LIMIT 10
    """)
    
    top_credits = cur.fetchall()
    
    for charter in top_credits:
        reserve_num, charter_date, client_name, amount_due, paid, balance = charter
        client_display = (client_name or 'Unknown')[:40]
        print(f"{reserve_num or 'N/A':<10} {str(charter_date):<12} {client_display:<40} Credit: ${abs(balance):,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
