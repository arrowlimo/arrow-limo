#!/usr/bin/env python3
"""
Comprehensive income reconciliation audit:
- Banking deposits (income side)
- Payments received (customer payments)
- Square transactions
- Charter revenue
- Email financial events (e-transfers)

Check if every income dollar is matched and accounted for.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("INCOME RECONCILIATION AUDIT")
    print("=" * 80)

    # 1. Banking deposits (credit_amount > 0)
    print("\n1. BANKING DEPOSITS (Income Side)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_deposits,
            SUM(credit_amount) as total_amount,
            COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as linked_to_receipt,
            SUM(CASE WHEN receipt_id IS NOT NULL THEN credit_amount END) as amount_linked_receipt
        FROM banking_transactions
        WHERE credit_amount > 0
    """)
    deposits = cur.fetchone()
    
    print(f"Total deposits: {deposits['total_deposits']:,}")
    print(f"Total amount: ${deposits['total_amount']:,.2f}")
    print(f"Linked to receipts: {deposits['linked_to_receipt']:,} ({deposits['linked_to_receipt']/deposits['total_deposits']*100:.1f}%)")
    print(f"Amount linked to receipts: ${deposits['amount_linked_receipt'] or 0:,.2f}")
    
    # Check if deposits should be linked to payments instead
    cur.execute("""
        SELECT COUNT(*) as count
        FROM banking_transactions bt
        WHERE bt.credit_amount > 0
          AND bt.receipt_id IS NULL
          AND EXISTS (
              SELECT 1 FROM payments p 
              WHERE p.payment_date::date = bt.transaction_date::date
              AND ABS(p.amount - bt.credit_amount) <= 0.01
          )
    """)
    matchable_to_payments = cur.fetchone()['count']
    print(f"Matchable to payments (date+amount): {matchable_to_payments:,}")

    # 2. Payments table (customer payments)
    print("\n2. PAYMENTS (Customer Revenue)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            SUM(amount) as total_amount,
            COUNT(DISTINCT client_id) as unique_clients,
            COUNT(DISTINCT charter_id) as linked_charters,
            COUNT(CASE WHEN square_transaction_id IS NOT NULL THEN 1 END) as square_payments
        FROM payments
        WHERE amount > 0
    """)
    payments = cur.fetchone()
    
    print(f"Total payments: {payments['total_payments']:,}")
    print(f"Total amount: ${payments['total_amount']:,.2f}")
    print(f"Unique clients: {payments['unique_clients']:,}")
    print(f"Linked to charters: {payments['linked_charters']:,}")
    print(f"Square payments: {payments['square_payments']:,}")

    # 3. Charter revenue
    print("\n3. CHARTER REVENUE (Bookings)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(rate) as total_rate,
            SUM(paid_amount) as total_paid,
            SUM(balance) as total_balance,
            COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_charters,
            COUNT(CASE WHEN payment_status = 'partial' THEN 1 END) as partial_charters,
            COUNT(CASE WHEN payment_status = 'unpaid' THEN 1 END) as unpaid_charters
        FROM charters
        WHERE rate > 0
          AND cancelled = false
    """)
    charters = cur.fetchone()
    
    print(f"Total charters: {charters['total_charters']:,}")
    print(f"Total rate (invoice value): ${charters['total_rate'] or 0:,.2f}")
    print(f"Total paid: ${charters['total_paid'] or 0:,.2f}")
    print(f"Total balance: ${charters['total_balance'] or 0:,.2f}")
    print(f"Payment status: Paid={charters['paid_charters']:,}, Partial={charters['partial_charters']:,}, Unpaid={charters['unpaid_charters']:,}")

    # 4. Square transactions
    print("\n4. SQUARE TRANSACTIONS (Card Processing)")
    print("-" * 80)
    
    # Check if square_transactions table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'square_transactions'
        )
    """)
    
    if cur.fetchone()['exists']:
        cur.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_income,
                COUNT(CASE WHEN payment_id IS NOT NULL THEN 1 END) as linked_to_payments
            FROM square_transactions
        """)
        square = cur.fetchone()
        
        print(f"Total Square transactions: {square['total_transactions']:,}")
        print(f"Total income: ${square['total_income']:,.2f}")
        print(f"Linked to payments: {square['linked_to_payments']:,}")
    else:
        print("Square transactions table not found")

    # 5. Email financial events (e-transfers)
    print("\n5. EMAIL FINANCIAL EVENTS (E-transfers)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_events,
            SUM(amount) as total_amount,
            COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as linked_to_banking,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN amount END) as amount_linked,
            COUNT(CASE WHEN event_type = 'etransfer_received' THEN 1 END) as etransfers_in
        FROM email_financial_events
        WHERE amount > 0
    """)
    email_events = cur.fetchone()
    
    print(f"Total income events: {email_events['total_events']:,}")
    print(f"Total amount: ${email_events['total_amount'] or 0:,.2f}")
    print(f"Linked to banking: {email_events['linked_to_banking']:,} ({email_events['linked_to_banking']/email_events['total_events']*100 if email_events['total_events'] > 0 else 0:.1f}%)")
    print(f"Amount linked: ${email_events['amount_linked'] or 0:,.2f}")
    print(f"E-transfers received: {email_events['etransfers_in']:,}")

    # 6. Cross-system reconciliation
    print("\n6. CROSS-SYSTEM RECONCILIATION")
    print("-" * 80)
    
    # Banking deposits vs Payments
    deposit_total = deposits['total_amount'] or Decimal(0)
    payment_total = payments['total_amount'] or Decimal(0)
    charter_paid = charters['total_paid'] or Decimal(0)
    
    print(f"Banking deposits:     ${deposit_total:,.2f}")
    print(f"Payment records:      ${payment_total:,.2f}")
    print(f"Charter paid amount:  ${charter_paid:,.2f}")
    
    if payment_total > 0:
        deposit_coverage = (deposit_total / payment_total * 100)
        print(f"\nBanking/Payment ratio: {deposit_coverage:.1f}%")
        
        if deposit_coverage < 90:
            print("  [WARN]  WARNING: Banking deposits significantly less than payment records")
            print("      Possible issues: Missing bank imports, unreconciled periods")
        elif deposit_coverage > 110:
            print("  [WARN]  WARNING: Banking deposits significantly more than payment records")
            print("      Possible issues: Non-payment deposits (refunds, loans, etc.)")
        else:
            print("  ✓ Banking and payment totals reasonably aligned")
    
    # Charter revenue vs Payments
    if charter_paid > 0 and payment_total > 0:
        charter_payment_ratio = (payment_total / charter_paid * 100)
        print(f"\nPayment/Charter ratio: {charter_payment_ratio:.1f}%")
        
        if charter_payment_ratio < 90:
            print("  [WARN]  WARNING: Payments less than charter paid amounts")
            print("      Possible issues: Unrecorded payments, data sync issues")
        elif charter_payment_ratio > 110:
            print("  [WARN]  WARNING: Payments more than charter paid amounts")
            print("      Possible issues: Duplicate payments, non-charter income")
        else:
            print("  ✓ Charter and payment totals reasonably aligned")

    # 7. Unmatched income analysis
    print("\n7. UNMATCHED INCOME ANALYSIS")
    print("-" * 80)
    
    # Deposits not linked to anything
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(credit_amount) as amount
        FROM banking_transactions
        WHERE credit_amount > 0
          AND receipt_id IS NULL
    """)
    unlinked = cur.fetchone()
    
    print(f"Unlinked bank deposits: {unlinked['count']:,} (${unlinked['amount']:,.2f})")
    
    # Payment methods breakdown
    cur.execute("""
        SELECT 
            payment_method,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE amount > 0
        GROUP BY payment_method
        ORDER BY total DESC
        LIMIT 10
    """)
    methods = cur.fetchall()
    
    if methods:
        print("\nTop payment methods:")
        for m in methods:
            method = m['payment_method'] or 'Unknown'
            print(f"  {method:20s}: {m['count']:5,} payments, ${m['total']:,.2f}")

    # 8. Summary and recommendations
    print("\n" + "=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)
    
    total_income_sources = deposit_total + (email_events['total_amount'] or Decimal(0))
    total_income_recorded = payment_total + charter_paid
    
    print(f"\nTotal income (banking+email):  ${total_income_sources:,.2f}")
    print(f"Total income (payments+charters): ${total_income_recorded:,.2f}")
    
    if matchable_to_payments > 0:
        print(f"\n[WARN]  ACTION NEEDED: {matchable_to_payments:,} bank deposits can be matched to payments")
        print("    Run: python scripts/reconcile_deposits_to_payments_enhanced.py --write")
    
    if unlinked['count'] > 1000:
        print(f"\n[WARN]  ATTENTION: {unlinked['count']:,} unlinked deposits totaling ${unlinked['amount']:,.2f}")
        print("    These may be: refunds, loans, transfers, or missing payment records")
    
    if deposit_coverage and 95 <= deposit_coverage <= 105:
        print("\n✓ Income reconciliation appears healthy (banking ≈ payments)")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
