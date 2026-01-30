#!/usr/bin/env python3
"""
Populate Square Capital loans from square_capital_activity.
Identifies loan advances and payments to track Square financing.
"""

import psycopg2
import os
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def analyze_square_activity(conn):
    """Analyze square_capital_activity to identify loans."""
    cur = conn.cursor()
    
    print("="*80)
    print("SQUARE CAPITAL ACTIVITY ANALYSIS")
    print("="*80)
    
    # Find all loan-related transactions
    cur.execute("""
        SELECT id, activity_date, description, amount
        FROM square_capital_activity
        WHERE description ILIKE '%loan%'
           OR description ILIKE '%advance%'
           OR description ILIKE '%capital%'
        ORDER BY activity_date, amount DESC
    """)
    
    transactions = cur.fetchall()
    
    print(f"\nFound {len(transactions)} loan-related transactions:")
    print(f"{'ID':<8} {'Date':<12} {'Amount':>12} {'Description':<50}")
    print("-" * 80)
    
    loan_advances = []
    loan_payments = []
    
    for txn_id, date, desc, amount in transactions:
        print(f"{txn_id:<8} {date.strftime('%Y-%m-%d'):<12} ${amount:>11.2f} {desc[:50]}")
        
        # Identify loan advances (large positive amounts)
        if amount > 10000 and ('deposit' in desc.lower() or 'advance' in desc.lower()):
            loan_advances.append({
                'id': txn_id,
                'date': date,
                'amount': amount,
                'description': desc
            })
        # Identify payments (could be refunds or deductions)
        elif 'payment' in desc.lower() or 'refund' in desc.lower():
            loan_payments.append({
                'id': txn_id,
                'date': date,
                'amount': amount,
                'description': desc
            })
    
    print(f"\n{'='*80}")
    print(f"IDENTIFIED LOANS: {len(loan_advances)}")
    print("="*80)
    
    for loan in loan_advances:
        print(f"  {loan['date'].strftime('%Y-%m-%d')}: ${loan['amount']:,.2f} - {loan['description']}")
    
    print(f"\n{'='*80}")
    print(f"IDENTIFIED PAYMENTS: {len(loan_payments)}")
    print("="*80)
    
    total_payments = sum(p['amount'] for p in loan_payments)
    print(f"  Total payments/refunds: ${total_payments:,.2f}")
    
    return loan_advances, loan_payments


def find_banking_links(conn, date, amount):
    """Find matching banking transaction."""
    cur = conn.cursor()
    
    # Try exact match first (credit for loan deposit, debit for payments)
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE transaction_date::date = %s::date
          AND (ABS(COALESCE(credit_amount, 0) - %s) < 0.01 
            OR ABS(COALESCE(debit_amount, 0) - %s) < 0.01)
          AND (description ILIKE '%%square%%' OR vendor_extracted ILIKE '%%square%%')
        LIMIT 1
    """, (date, amount, amount))
    
    exact = cur.fetchone()
    if exact:
        return exact[0]
    
    # Try within 3 days
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE transaction_date::date BETWEEN (%s::date - INTERVAL '3 days')::date 
          AND (%s::date + INTERVAL '3 days')::date
          AND (ABS(COALESCE(credit_amount, 0) - %s) < 0.01 
            OR ABS(COALESCE(debit_amount, 0) - %s) < 0.01)
          AND (description ILIKE '%%square%%' OR vendor_extracted ILIKE '%%square%%')
        ORDER BY ABS(EXTRACT(EPOCH FROM (transaction_date::timestamp - %s::timestamp)))
        LIMIT 1
    """, (date, date, amount, amount, date))
    
    close = cur.fetchone()
    if close:
        return close[0]
    
    return None


def populate_square_loans(conn, loan_advances, dry_run=True):
    """Populate square_capital_loans table."""
    cur = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"POPULATING SQUARE_CAPITAL_LOANS (dry_run={dry_run})")
    print("="*80)
    
    for idx, loan in enumerate(loan_advances, 1):
        # Generate square_loan_id
        square_loan_id = f"SQ-LOAN-{loan['date'].strftime('%Y%m%d')}-{idx}"
        
        # Find banking link
        banking_txn_id = find_banking_links(conn, loan['date'], loan['amount'])
        banking_status = "✓ Linked" if banking_txn_id else "⚠ No link"
        
        print(f"\nLoan {idx}:")
        print(f"  Square ID: {square_loan_id}")
        print(f"  Date: {loan['date']}")
        print(f"  Amount: ${loan['amount']:,.2f}")
        print(f"  Description: {loan['description']}")
        print(f"  Banking: {banking_status}")
        
        if not dry_run:
            cur.execute("""
                INSERT INTO square_capital_loans 
                (square_loan_id, loan_amount, received_date, status, 
                 banking_transaction_id, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (square_loan_id) DO UPDATE
                SET loan_amount = EXCLUDED.loan_amount,
                    received_date = EXCLUDED.received_date,
                    banking_transaction_id = EXCLUDED.banking_transaction_id,
                    description = EXCLUDED.description,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING loan_id
            """, (
                square_loan_id,
                loan['amount'],
                loan['date'],
                'active',  # Will update status based on payments
                banking_txn_id,
                loan['description']
            ))
            
            loan_id = cur.fetchone()[0]
            print(f"  ✓ Inserted loan_id: {loan_id}")


def populate_square_loan_payments(conn, loan_payments, dry_run=True):
    """Populate square_loan_payments table."""
    cur = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"POPULATING SQUARE_LOAN_PAYMENTS (dry_run={dry_run})")
    print("="*80)
    
    # Get all loans to link payments to
    cur.execute("SELECT loan_id, received_date, loan_amount FROM square_capital_loans ORDER BY received_date")
    loans = cur.fetchall()
    
    if not loans:
        print("⚠ No loans found in square_capital_loans table")
        return
    
    print(f"\nFound {len(loans)} loans to link payments to")
    
    for payment in loan_payments:
        # Link to most recent loan before payment date
        matching_loan = None
        for loan_id, loan_date, loan_amount in loans:
            if loan_date <= payment['date']:
                matching_loan = loan_id
        
        if not matching_loan:
            print(f"⚠ No matching loan for payment on {payment['date']}: ${payment['amount']:.2f}")
            continue
        
        # Find banking link
        banking_txn_id = find_banking_links(conn, payment['date'], payment['amount'])
        banking_status = "✓ Linked" if banking_txn_id else "⚠ No link"
        
        print(f"\nPayment:")
        print(f"  Date: {payment['date']}")
        print(f"  Amount: ${payment['amount']:,.2f}")
        print(f"  Description: {payment['description']}")
        print(f"  Linked to loan_id: {matching_loan}")
        print(f"  Banking: {banking_status}")
        
        if not dry_run:
            cur.execute("""
                INSERT INTO square_loan_payments 
                (loan_id, payment_date, payment_amount, banking_transaction_id, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING payment_id
            """, (
                matching_loan,
                payment['date'],
                payment['amount'],
                banking_txn_id,
                payment['description']
            ))
            
            result = cur.fetchone()
            if result:
                print(f"  ✓ Inserted payment_id: {result[0]}")


def update_loan_status(conn, dry_run=True):
    """Update loan status based on payments."""
    cur = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"UPDATING LOAN STATUS (dry_run={dry_run})")
    print("="*80)
    
    cur.execute("""
        SELECT 
            l.loan_id,
            l.square_loan_id,
            l.loan_amount,
            COALESCE(SUM(p.payment_amount), 0) as total_paid
        FROM square_capital_loans l
        LEFT JOIN square_loan_payments p ON p.loan_id = l.loan_id
        GROUP BY l.loan_id, l.square_loan_id, l.loan_amount
    """)
    
    for loan_id, square_id, loan_amount, total_paid in cur.fetchall():
        remaining = loan_amount - total_paid
        
        if remaining <= Decimal('0.01'):
            new_status = 'completed'
        elif total_paid > 0:
            new_status = 'repaying'
        else:
            new_status = 'active'
        
        print(f"\n{square_id}:")
        print(f"  Loan amount: ${loan_amount:,.2f}")
        print(f"  Total paid: ${total_paid:,.2f}")
        print(f"  Remaining: ${remaining:,.2f}")
        print(f"  Status: {new_status}")
        
        if not dry_run:
            cur.execute("""
                UPDATE square_capital_loans
                SET status = %s
                WHERE loan_id = %s
            """, (new_status, loan_id))


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    
    try:
        # Step 1: Analyze activity
        loan_advances, loan_payments = analyze_square_activity(conn)
        
        # Step 2: Populate loans
        populate_square_loans(conn, loan_advances, dry_run)
        
        if not dry_run:
            conn.commit()
            print("\n✓ Loans committed")
        
        # Step 3: Populate payments
        populate_square_loan_payments(conn, loan_payments, dry_run)
        
        # Step 4: Update status
        update_loan_status(conn, dry_run)
        
        if not dry_run:
            conn.commit()
            print("\n✓ All changes committed")
        else:
            print("\n⚠ DRY RUN - No changes made. Use --write to apply changes.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
