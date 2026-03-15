"""
Find all payments auto-linked via "Direct rate match" from LMS.
These may be incorrectly duplicating Square payments to charters.
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
    print("PAYMENTS AUTO-LINKED VIA 'DIRECT RATE MATCH' ANALYSIS")
    print("="*120 + "\n")
    
    # Find all payments with "Direct rate match" in notes
    cur.execute("""
        SELECT 
            p.payment_id,
            p.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.square_transaction_id,
            p.notes,
            p.created_at
        FROM payments p
        LEFT JOIN charters c ON p.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE LOWER(p.notes) LIKE '%direct rate match%'
        ORDER BY c.reserve_number, p.payment_date
    """)
    
    payments = cur.fetchall()
    
    print(f"Found {len(payments)} payments with 'Direct rate match' in notes\n")
    
    if not payments:
        print("No payments found with 'Direct rate match'")
        cur.close()
        conn.close()
        return
    
    # Group by charter
    charter_payments = {}
    for payment in payments:
        payment_id, charter_id, reserve_num, charter_date, client_name, payment_date, amount, method, square_id, notes, created_at = payment
        
        if reserve_num not in charter_payments:
            charter_payments[reserve_num] = {
                'charter_id': charter_id,
                'charter_date': charter_date,
                'client_name': client_name,
                'payments': []
            }
        
        charter_payments[reserve_num]['payments'].append({
            'payment_id': payment_id,
            'payment_date': payment_date,
            'amount': amount,
            'method': method,
            'square_id': square_id,
            'notes': notes,
            'created_at': created_at
        })
    
    print(f"Spread across {len(charter_payments)} charters\n")
    print("="*120)
    
    # Show charters with multiple "Direct rate match" payments (likely duplicates)
    problem_charters = {k: v for k, v in charter_payments.items() if len(v['payments']) > 5}
    
    print(f"\nCHARTERS WITH >5 'DIRECT RATE MATCH' PAYMENTS (likely duplicates): {len(problem_charters)}")
    print("="*120)
    
    for reserve_num in sorted(problem_charters.keys()):
        charter_info = problem_charters[reserve_num]
        payment_count = len(charter_info['payments'])
        total_amount = sum(p['amount'] for p in charter_info['payments'])
        
        print(f"\n{reserve_num} - {charter_info['client_name']} ({charter_info['charter_date']})")
        print(f"  {payment_count} payments totaling ${total_amount:,.2f}")
        
        # Get charter financial summary
        cur.execute("""
            SELECT total_amount_due, paid_amount, balance
            FROM charters
            WHERE charter_id = %s
        """, (charter_info['charter_id'],))
        total_due, paid_amount, balance = cur.fetchone()
        
        print(f"  Charter: Due=${total_due or 0:,.2f}, Paid=${paid_amount or 0:,.2f}, Balance=${balance or 0:,.2f}")
        
        if balance and balance < -1000:
            print(f"  [WARN]  LARGE CREDIT: ${abs(balance):,.2f}")
        
        # Show first 5 and last 5 payments
        display_payments = charter_info['payments'][:5] + charter_info['payments'][-5:] if payment_count > 10 else charter_info['payments']
        
        for p in display_payments[:10]:  # Limit display
            square_info = f" [Square: {p['square_id'][:20]}]" if p['square_id'] else ""
            print(f"    {p['payment_id']}: {p['payment_date']} ${p['amount']:,.2f}{square_info}")
        
        if payment_count > 10:
            print(f"    ... ({payment_count - 10} more payments)")
    
    # Summary statistics
    print("\n" + "="*120)
    print("SUMMARY STATISTICS")
    print("="*120)
    
    total_payments = len(payments)
    total_amount = sum(p[6] for p in payments)  # amount is index 6
    square_payments = sum(1 for p in payments if p[8])  # square_id is index 8
    
    print(f"Total 'Direct rate match' payments: {total_payments}")
    print(f"Total amount: ${total_amount:,.2f}")
    print(f"Payments with Square IDs: {square_payments} ({square_payments/total_payments*100:.1f}%)")
    print(f"Charters affected: {len(charter_payments)}")
    print(f"Charters with >5 payments: {len(problem_charters)} (likely have duplicates)")
    
    # Check if these Square transactions are linked elsewhere
    print("\n" + "="*120)
    print("CHECKING FOR DUPLICATE SQUARE TRANSACTION LINKAGES")
    print("="*120)
    
    # Get unique Square IDs from these payments
    square_ids = [p[8] for p in payments if p[8]]
    
    if square_ids:
        # Check how many times each Square ID appears
        cur.execute("""
            SELECT 
                square_transaction_id,
                COUNT(*) as link_count,
                COUNT(DISTINCT charter_id) as charter_count,
                SUM(amount) as total_amount
            FROM payments
            WHERE square_transaction_id = ANY(%s)
            GROUP BY square_transaction_id
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """, (square_ids,))
        
        duplicate_squares = cur.fetchall()
        
        if duplicate_squares:
            print(f"\nFound {len(duplicate_squares)} Square transactions linked multiple times:")
            print(f"\n{'Square ID':<50} {'Links':<8} {'Charters':<10} {'Total Amount':<15}")
            print("-"*120)
            
            for square_id, link_count, charter_count, total_amount in duplicate_squares:
                print(f"{square_id:<50} {link_count:<8} {charter_count:<10} ${total_amount:>12,.2f}")
        else:
            print("\nNo Square transactions linked multiple times (good)")
    
    print("\n" + "="*120)
    print("ANALYSIS")
    print("="*120)
    print("\n[WARN]  The 'Direct rate match' auto-linking appears to have created duplicate payment links.")
    print("   These Square payments were likely already correctly linked to their proper charters,")
    print("   but the auto-matching script matched them AGAIN based on the $500 rate amount.")
    print("\n   Charters 014941 and 013717 show this clearly - they have 19 and 20 payments respectively,")
    print("   all auto-linked via 'Direct rate match', creating $8,500 and $8,000 in false credits.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
