"""
List charters with outstanding balances that are marked as CANCELLED.
These represent potential write-offs or collection issues.
"""
import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*100)
    print(f"CANCELLED CHARTERS WITH OUTSTANDING BALANCES - Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*100)
    print()
    
    # Get cancelled charters with outstanding balances
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.notes,
            CURRENT_DATE - c.charter_date as days_since_charter
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.cancelled = TRUE
        AND c.balance > 0.01
        ORDER BY c.balance DESC, c.charter_date DESC
    """)
    
    results = cur.fetchall()
    
    if not results:
        print("No cancelled charters with outstanding balances found.")
        cur.close()
        conn.close()
        return
    
    total_cancelled = len(results)
    total_balance = sum(r[5] for r in results)
    total_billed = sum(r[3] for r in results)
    total_paid = sum(r[4] for r in results)
    
    print(f"Found {total_cancelled} cancelled charters with outstanding balances")
    print(f"Total Amount Billed: ${total_billed:,.2f}")
    print(f"Total Amount Paid: ${total_paid:,.2f}")
    print(f"Total Outstanding Balance: ${total_balance:,.2f}")
    print()
    
    # Summary by age
    print("AGE DISTRIBUTION:")
    print("-" * 100)
    
    age_ranges = {
        '0-90 days': (0, 90),
        '91-180 days': (91, 180),
        '181-365 days': (181, 365),
        '1-2 years': (366, 730),
        'Over 2 years': (731, 99999)
    }
    
    for age_label, (min_days, max_days) in age_ranges.items():
        in_range = [r for r in results if r[8] and min_days <= r[8] <= max_days]
        if in_range:
            count = len(in_range)
            amount = sum(r[5] for r in in_range)
            print(f"  {age_label:<15} {count:>3} charters  ${amount:>12,.2f}")
    
    print()
    
    # Detailed list
    print("DETAILED LISTING:")
    print("-" * 100)
    print(f"{'Reserve#':<10} {'Date':<12} {'Age (days)':<12} {'Client':<30} {'Total Due':<12} {'Paid':<12} {'Balance':<12}")
    print("-" * 100)
    
    for reserve, charter_date, client, total_due, paid, balance, status, notes, days_since in results:
        date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
        client_str = (client or 'Unknown')[:28]
        days_str = str(days_since) if days_since else 'N/A'
        
        print(f"{reserve:<10} {date_str:<12} {days_str:<12} {client_str:<30} "
              f"${total_due:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f}")
    
    print()
    print("-" * 100)
    print(f"TOTAL: {total_cancelled} charters, ${total_balance:,.2f} outstanding")
    print()
    
    # Group by client
    print("BY CLIENT (Top 10):")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            cl.client_name,
            COUNT(*) as charter_count,
            SUM(c.total_amount_due) as total_billed,
            SUM(c.paid_amount) as total_paid,
            SUM(c.balance) as total_balance
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.cancelled = TRUE
        AND c.balance > 0.01
        GROUP BY cl.client_name
        ORDER BY total_balance DESC
        LIMIT 10
    """)
    
    print(f"{'Client':<40} {'Charters':<10} {'Total Due':<12} {'Paid':<12} {'Balance':<12}")
    print("-" * 100)
    
    for client, count, billed, paid, balance in cur.fetchall():
        client_str = (client or 'Unknown')[:38]
        print(f"{client_str:<40} {count:<10} ${billed:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f}")
    
    print()
    
    # High-value cancelled charters (>$500)
    high_value = [r for r in results if r[5] > 500]
    if high_value:
        print()
        print("HIGH-VALUE CANCELLED CHARTERS (Balance > $500):")
        print("-" * 100)
        print(f"{'Reserve#':<10} {'Date':<12} {'Client':<35} {'Balance':<12} {'Notes':<30}")
        print("-" * 100)
        
        for reserve, charter_date, client, total_due, paid, balance, status, notes, days_since in high_value:
            date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
            client_str = (client or 'Unknown')[:33]
            notes_str = (notes or '')[:28]
            print(f"{reserve:<10} {date_str:<12} {client_str:<35} ${balance:>10,.2f} {notes_str:<30}")
        
        print()
        print(f"Total high-value cancelled: {len(high_value)} charters, ${sum(r[5] for r in high_value):,.2f}")
    
    print()
    print("="*100)
    print("RECOMMENDATIONS:")
    print("="*100)
    print()
    print("1. REVIEW FOR WRITE-OFF: Cancelled charters over 1 year old may qualify for bad debt write-off")
    print("2. COLLECTION ATTEMPT: Contact clients with high balances (>$500) for payment/settlement")
    print("3. REFUND PROCESSING: Check if any balances represent deposits requiring refund")
    print("4. ACCOUNTING CLEANUP: Consider clearing small balances (<$50) as administrative write-offs")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
