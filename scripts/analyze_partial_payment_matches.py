"""
Analyze partial payment matches - where payment amounts don't match charter balances.

This identifies:
1. Overpayments: Payment amount > Charter balance
2. Underpayments: Payment amount < Charter balance  
3. Multiple payments to same charter: Sum of payments vs charter total
4. Unallocated payment amounts: Payments matched but amounts don't reconcile
"""

import psycopg2
import os

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_partial_matches():
    """Analyze partial payment matches."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("PARTIAL PAYMENT MATCH ANALYSIS")
    print("=" * 120)
    print()
    
    # Get charters with payments and compare amounts
    print("Analyzing matched payments vs charter balances...")
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.account_number,
            c.charter_date,
            c.rate,
            c.balance,
            c.deposit,
            c.total_amount_due,
            c.paid_amount,
            COUNT(p.payment_id) as payment_count,
            SUM(p.amount) as total_payments,
            STRING_AGG(CAST(p.payment_id AS TEXT) || ':$' || CAST(COALESCE(p.amount, 0) AS TEXT), ', ' ORDER BY p.payment_id) as payment_details
        FROM charters c
        INNER JOIN payments p ON c.charter_id = p.charter_id
        WHERE c.reserve_number IS NOT NULL
          AND c.charter_date >= '2007-01-01' 
          AND c.charter_date < '2025-01-01'
        GROUP BY c.charter_id, c.reserve_number, c.account_number, c.charter_date, 
                 c.rate, c.balance, c.deposit, c.total_amount_due, c.paid_amount
        HAVING COUNT(p.payment_id) > 0
        ORDER BY c.charter_date DESC
        LIMIT 100
    """)
    
    results = cur.fetchall()
    
    # Categorize payment matches
    perfect_matches = []
    overpayments = []
    underpayments = []
    multiple_payments = []
    balance_mismatch = []
    
    for row in results:
        charter_id, reserve, account, cdate, rate, balance, deposit, total_due, paid_amount, payment_count, total_payments, payment_details = row
        
        # Use appropriate comparison field
        charter_amount = balance if balance is not None else (total_due if total_due is not None else rate)
        payment_sum = total_payments if total_payments is not None else 0
        
        if charter_amount is None:
            continue
        
        # Convert to float for comparison
        charter_amt = float(charter_amount)
        payment_amt = float(payment_sum)
            
        diff = abs(payment_amt - charter_amt)
        
        if payment_count > 1:
            multiple_payments.append(row)
        
        if diff < 0.02:  # Perfect match (within 2 cents for rounding)
            perfect_matches.append(row)
        elif payment_amt > charter_amt + 0.02:
            overpayments.append(row)
        elif payment_amt < charter_amt - 0.02:
            underpayments.append(row)
        else:
            balance_mismatch.append(row)
    
    print(f"Total charters analyzed (2007-2024, with payments): {len(results)}")
    print()
    print(f"Perfect matches (payment = balance ±2¢):    {len(perfect_matches)}")
    print(f"Overpayments (payment > balance):           {len(overpayments)}")
    print(f"Underpayments (payment < balance):          {len(underpayments)}")
    print(f"Multiple payments to same charter:          {len(multiple_payments)}")
    print()
    
    # Show overpayment examples
    if overpayments:
        print("\n" + "=" * 120)
        print("OVERPAYMENTS - Payment amount exceeds charter balance")
        print("=" * 120)
        print(f"{'Charter':<10} {'Reserve':<10} {'Date':<12} {'Balance':<12} {'Paid':<12} {'Diff':<12} {'Pymt Cnt'}")
        print("-" * 120)
        for row in overpayments[:20]:
            charter_id, reserve, account, cdate, rate, balance, deposit, total_due, paid_amount, payment_count, total_payments, payment_details = row
            charter_amount = balance if balance is not None else (total_due if total_due is not None else rate)
            diff = (total_payments if total_payments else 0) - (charter_amount if charter_amount else 0)
            print(f"{charter_id:<10} {reserve if reserve else 'NULL':<10} {str(cdate) if cdate else 'NULL':<12} "
                  f"${charter_amount if charter_amount else 0:<11.2f} ${total_payments if total_payments else 0:<11.2f} "
                  f"${diff:<11.2f} {payment_count}")
        
        if len(overpayments) > 20:
            print(f"... and {len(overpayments) - 20} more overpayments")
    
    # Show underpayment examples
    if underpayments:
        print("\n" + "=" * 120)
        print("UNDERPAYMENTS - Payment amount less than charter balance (partial payments)")
        print("=" * 120)
        print(f"{'Charter':<10} {'Reserve':<10} {'Date':<12} {'Balance':<12} {'Paid':<12} {'Unpaid':<12} {'Pymt Cnt'}")
        print("-" * 120)
        for row in underpayments[:20]:
            charter_id, reserve, account, cdate, rate, balance, deposit, total_due, paid_amount, payment_count, total_payments, payment_details = row
            charter_amount = balance if balance is not None else (total_due if total_due is not None else rate)
            diff = (charter_amount if charter_amount else 0) - (total_payments if total_payments else 0)
            print(f"{charter_id:<10} {reserve if reserve else 'NULL':<10} {str(cdate) if cdate else 'NULL':<12} "
                  f"${charter_amount if charter_amount else 0:<11.2f} ${total_payments if total_payments else 0:<11.2f} "
                  f"${diff:<11.2f} {payment_count}")
        
        if len(underpayments) > 20:
            print(f"... and {len(underpayments) - 20} more underpayments")
    
    # Show multiple payment examples
    if multiple_payments:
        print("\n" + "=" * 120)
        print("MULTIPLE PAYMENTS TO SAME CHARTER")
        print("=" * 120)
        print(f"{'Charter':<10} {'Reserve':<10} {'Date':<12} {'Balance':<12} {'Total Paid':<12} {'Pymt Cnt':<10} {'Payment IDs & Amounts'}")
        print("-" * 120)
        for row in multiple_payments[:15]:
            charter_id, reserve, account, cdate, rate, balance, deposit, total_due, paid_amount, payment_count, total_payments, payment_details = row
            charter_amount = balance if balance is not None else (total_due if total_due is not None else rate)
            print(f"{charter_id:<10} {reserve if reserve else 'NULL':<10} {str(cdate) if cdate else 'NULL':<12} "
                  f"${charter_amount if charter_amount else 0:<11.2f} ${total_payments if total_payments else 0:<11.2f} "
                  f"{payment_count:<10} {payment_details[:60] if payment_details else 'NULL'}...")
        
        if len(multiple_payments) > 15:
            print(f"... and {len(multiple_payments) - 15} more charters with multiple payments")
    
    # Analyze unmatched payments with amounts
    print("\n" + "=" * 120)
    print("UNMATCHED PAYMENTS (2007-2024) - Payments with amounts but no charter")
    print("=" * 120)
    
    cur.execute("""
        SELECT 
            COUNT(*) as unmatched_count,
            SUM(amount) as total_unmatched_amount,
            AVG(amount) as avg_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount
        FROM payments
        WHERE reserve_number IS NULL
          AND payment_date >= '2007-01-01'
          AND payment_date < '2025-01-01'
          AND amount IS NOT NULL
    """)
    
    unmatched_stats = cur.fetchone()
    if unmatched_stats:
        unmatched_count, total_amount, avg_amount, min_amount, max_amount = unmatched_stats
        print(f"Total unmatched payments: {unmatched_count}")
        print(f"Total unmatched amount:   ${total_amount if total_amount else 0:,.2f}")
        print(f"Average payment:          ${avg_amount if avg_amount else 0:,.2f}")
        print(f"Min payment:              ${min_amount if min_amount else 0:,.2f}")
        print(f"Max payment:              ${max_amount if max_amount else 0:,.2f}")
    
    # Show unmatched payment samples by amount range
    print("\nUnmatched payments by amount range:")
    cur.execute("""
        SELECT 
            CASE 
                WHEN amount < 0 THEN 'Negative (refunds/adjustments)'
                WHEN amount = 0 THEN 'Zero amount'
                WHEN amount <= 1 THEN '$0.01 - $1.00 (balancing)'
                WHEN amount <= 50 THEN '$1.01 - $50.00 (small)'
                WHEN amount <= 200 THEN '$50.01 - $200.00 (medium)'
                WHEN amount <= 500 THEN '$200.01 - $500.00 (large)'
                ELSE '$500+ (very large)'
            END as amount_range,
            COUNT(*) as payment_count,
            SUM(amount) as total_amount
        FROM payments
        WHERE reserve_number IS NULL
          AND payment_date >= '2007-01-01'
          AND payment_date < '2025-01-01'
        GROUP BY 
            CASE 
                WHEN amount < 0 THEN 'Negative (refunds/adjustments)'
                WHEN amount = 0 THEN 'Zero amount'
                WHEN amount <= 1 THEN '$0.01 - $1.00 (balancing)'
                WHEN amount <= 50 THEN '$1.01 - $50.00 (small)'
                WHEN amount <= 200 THEN '$50.01 - $200.00 (medium)'
                WHEN amount <= 500 THEN '$200.01 - $500.00 (large)'
                ELSE '$500+ (very large)'
            END
        ORDER BY amount_range
    """)
    
    amount_ranges = cur.fetchall()
    print(f"\n{'Amount Range':<40} {'Count':<10} {'Total Amount'}")
    print("-" * 120)
    for amount_range, count, total in amount_ranges:
        print(f"{amount_range:<40} {count:<10} ${total if total else 0:,.2f}")
    
    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print()
    
    if underpayments:
        print(f"[WARN]  PARTIAL PAYMENTS FOUND: {len(underpayments)} charters")
        print(f"   These charters have payments but still have outstanding balances")
        print()
    
    if overpayments:
        print(f"[WARN]  OVERPAYMENTS FOUND: {len(overpayments)} charters")
        print(f"   Payments exceed charter balance - may indicate:")
        print(f"   - Tips/gratuities included in payment")
        print(f"   - Payment applied to wrong charter")
        print(f"   - Charter balance not updated after payment")
        print()
    
    if multiple_payments:
        print(f"[OK] MULTIPLE PAYMENTS: {len(multiple_payments)} charters have 2+ payments")
        print(f"   This is normal for:")
        print(f"   - Deposit + final payment")
        print(f"   - Installment payments")
        print(f"   - Batch payments with balancing entries")
        print()
    
    total_unallocated = 0
    if unmatched_stats and unmatched_stats[1]:
        total_unallocated = unmatched_stats[1]
    
    print(f"💰 UNMATCHED PAYMENT AMOUNTS: ${total_unallocated:,.2f}")
    print(f"   {unmatched_count if unmatched_stats else 0} payments with amounts but no charter match")
    print(f"   These represent potential revenue or tracking gaps")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_partial_matches()
