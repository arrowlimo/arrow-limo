"""Analyze unmatched payments after accounting for charity/trade charters."""
import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("UNMATCHED PAYMENTS ANALYSIS - POST CHARITY/TRADE RECONCILIATION")
    print("=" * 100)
    print()
    
    # Total payments
    cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE amount > 0")
    total_payments, total_amount = cur.fetchone()
    print(f"Total Payments: {total_payments:,} (${float(total_amount):,.2f})")
    
    # Matched payments (have charter_id)
    cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE charter_id IS NOT NULL AND amount > 0")
    matched_payments, matched_amount = cur.fetchone()
    print(f"Matched Payments: {matched_payments:,} (${float(matched_amount):,.2f})")
    
    # Unmatched payments (no charter_id)
    cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE charter_id IS NULL AND amount > 0")
    unmatched_payments, unmatched_amount = cur.fetchone()
    print(f"Unmatched Payments: {unmatched_payments:,} (${float(unmatched_amount):,.2f})")
    print()
    
    # Check if any charity/trade charters have unmatched status
    print("=" * 100)
    print("CHARITY/TRADE CHARTERS - PAYMENT MATCHING STATUS")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.status,
            c.closed,
            c.cancelled,
            c.balance,
            ctc.classification,
            ctc.payments_total,
            ctc.payment_count,
            cl.client_name,
            (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id) as linked_payments
        FROM charity_trade_charters ctc
        JOIN charters c ON ctc.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        ORDER BY c.charter_date DESC
    """)
    
    charity_charters = cur.fetchall()
    
    closed_paid = []
    closed_unpaid = []
    open_with_balance = []
    cancelled = []
    
    for row in charity_charters:
        reserve_number = row[0]
        charter_date = row[1]
        status = row[2]
        closed = row[3]
        cancelled_flag = row[4]
        balance = float(row[5]) if row[5] else 0
        classification = row[6]
        payments_total = float(row[7])
        payment_count = row[8]
        client_name = row[9] or 'Unknown'
        linked_payments = row[10]
        
        if cancelled_flag:
            cancelled.append(row)
        elif closed:
            if balance <= 0:
                closed_paid.append(row)
            else:
                closed_unpaid.append(row)
        else:
            if balance > 0:
                open_with_balance.append(row)
    
    print(f"Closed & Paid in Full: {len(closed_paid)} charters")
    print(f"Closed with Balance Owing: {len(closed_unpaid)} charters")
    print(f"Open with Balance: {len(open_with_balance)} charters")
    print(f"Cancelled: {len(cancelled)} charters")
    print()
    
    # Show closed & paid in full charters
    if closed_paid:
        print("=" * 100)
        print(f"CLOSED & PAID IN FULL CHARITY/TRADE CHARTERS ({len(closed_paid)} charters)")
        print("=" * 100)
        print()
        print(f"{'Reserve':<12} {'Date':<12} {'Client':<25} {'Classification':<20} {'Payments':<12} {'Linked':<8}")
        print("-" * 100)
        
        for row in closed_paid:
            print(f"{row[0]:<12} {str(row[1]):<12} {(row[9] or 'Unknown')[:23]:<25} {row[6][:18]:<20} ${row[7]:>10.2f} {row[10]:>6}")
        
        print()
    
    # Check for charters with payments but no linked payment records
    print("=" * 100)
    print("CHARITY/TRADE CHARTERS - PAYMENT LINKAGE CHECK")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            ctc.classification,
            ctc.payments_total,
            ctc.payment_count,
            c.balance,
            (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id) as linked_count
        FROM charity_trade_charters ctc
        JOIN charters c ON ctc.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE ctc.payments_total > 0
        ORDER BY linked_count, c.charter_date DESC
    """)
    
    payment_linkage = cur.fetchall()
    unlinked_charity = [r for r in payment_linkage if r[7] == 0]
    
    if unlinked_charity:
        print(f"[WARN]  CHARITY/TRADE CHARTERS WITH PAYMENTS BUT NO LINKED PAYMENT RECORDS: {len(unlinked_charity)}")
        print()
        print(f"{'Reserve':<12} {'Date':<12} {'Client':<25} {'Classification':<20} {'Payments':<12} {'Balance':<12}")
        print("-" * 100)
        
        for row in unlinked_charity:
            print(f"{row[0]:<12} {str(row[1]):<12} {(row[2] or 'Unknown')[:23]:<25} {row[3][:18]:<20} ${row[4]:>10.2f} ${row[6]:>10.2f}")
        
        print()
        print("These payments were recorded in charity_trade_charters but not linked in payments table.")
        print("This may indicate:")
        print("  1. Payments recorded in LMS but not yet imported to PostgreSQL payments table")
        print("  2. Payment linkage (charter_id) needs to be established")
        print("  3. Payments are in staging tables waiting for import")
        print()
    else:
        print("✓ All charity/trade charters with payments have linked payment records")
        print()
    
    # Overall unmatched payment analysis
    print("=" * 100)
    print("OVERALL UNMATCHED PAYMENT STATUS")
    print("=" * 100)
    print()
    
    # Breakdown of unmatched by payment method
    cur.execute("""
        SELECT 
            COALESCE(payment_method, 'null/unknown') as method,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE charter_id IS NULL AND amount > 0
        GROUP BY payment_method
        ORDER BY total DESC
    """)
    
    print(f"{'Payment Method':<30} {'Count':<10} {'Total Amount':<15}")
    print("-" * 100)
    
    for row in cur.fetchall():
        method = row[0]
        count = row[1]
        total = float(row[2])
        print(f"{method:<30} {count:<10} ${total:>12,.2f}")
    
    print()
    print(f"TOTAL UNMATCHED: {unmatched_payments:,} payments, ${float(unmatched_amount):,.2f}")
    print()
    
    # Check if unmatched payments might match charity charters by reserve_number
    print("=" * 100)
    print("POTENTIAL CHARITY/TRADE MATCHES IN UNMATCHED PAYMENTS")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            c.reserve_number as charter_reserve,
            c.charter_date,
            c.status,
            ctc.classification
        FROM payments p
        LEFT JOIN charters c ON p.reserve_number = c.reserve_number
        LEFT JOIN charity_trade_charters ctc ON c.charter_id = ctc.charter_id
        WHERE p.charter_id IS NULL 
        AND p.amount > 0
        AND p.reserve_number IS NOT NULL
        AND ctc.id IS NOT NULL
        ORDER BY p.payment_date DESC
        LIMIT 20
    """)
    
    potential_matches = cur.fetchall()
    
    if potential_matches:
        print(f"Found {len(potential_matches)} unmatched payments with reserve_numbers matching charity/trade charters:")
        print()
        print(f"{'Payment ID':<12} {'Reserve':<10} {'Date':<12} {'Amount':<12} {'Method':<20} {'Charter Status':<15}")
        print("-" * 100)
        
        for row in potential_matches:
            print(f"{row[0]:<12} {row[1] or 'None':<10} {str(row[2]):<12} ${row[3]:>10.2f} {(row[4] or 'unknown')[:18]:<20} {row[7] or 'N/A':<15}")
        
        print()
        print("[WARN]  These payments have reserve_numbers matching charity/trade charters but charter_id is NULL")
        print("    Action: Run payment matching script to link these payments")
    else:
        print("✓ No unmatched payments found with reserve_numbers matching charity/trade charters")
    
    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print()
    print(f"Total Payments: {total_payments:,} (${float(total_amount):,.2f})")
    print(f"Matched: {matched_payments:,} ({matched_payments/total_payments*100:.1f}%)")
    print(f"Unmatched: {unmatched_payments:,} ({unmatched_payments/total_payments*100:.1f}%)")
    print()
    print(f"Charity/Trade Charters:")
    print(f"  - Closed & Paid: {len(closed_paid)} charters")
    print(f"  - With unlinked payments: {len(unlinked_charity)} charters")
    print(f"  - Potential matches in unmatched: {len(potential_matches)} payments")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
