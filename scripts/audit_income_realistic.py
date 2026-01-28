#!/usr/bin/env python3
"""
REALISTIC income reconciliation - excluding email_financial_events junk data.
Focus on: banking deposits, payments, charter revenue.
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
    print("INCOME RECONCILIATION - REALISTIC VIEW")
    print("=" * 80)

    # 1. Banking deposits (actual income into bank)
    print("\n1. BANKING DEPOSITS (Actual $ Into Bank)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_deposits,
            SUM(credit_amount) as total_amount,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest
        FROM banking_transactions
        WHERE credit_amount > 0
    """)
    deposits = cur.fetchone()
    
    print(f"Total deposits: {deposits['total_deposits']:,}")
    print(f"Total amount: ${deposits['total_amount']:,.2f}")
    print(f"Date range: {deposits['earliest']} to {deposits['latest']}")

    # 2. Payments (recorded customer payments)
    print("\n2. PAYMENT RECORDS (Customer Payments)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            SUM(amount) as total_amount,
            MIN(payment_date) as earliest,
            MAX(payment_date) as latest
        FROM payments
        WHERE amount > 0
    """)
    payments = cur.fetchone()
    
    print(f"Total payments: {payments['total_payments']:,}")
    print(f"Total amount: ${payments['total_amount']:,.2f}")
    print(f"Date range: {payments['earliest']} to {payments['latest']}")

    # 3. Charter invoiced vs paid
    print("\n3. CHARTER REVENUE (Bookings & Collections)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(rate) as invoiced,
            SUM(paid_amount) as collected,
            SUM(balance) as outstanding,
            MIN(charter_date) as earliest,
            MAX(charter_date) as latest
        FROM charters
        WHERE rate > 0
          AND cancelled = false
    """)
    charters = cur.fetchone()
    
    invoiced = charters['invoiced'] or Decimal(0)
    collected = charters['collected'] or Decimal(0)
    outstanding = charters['outstanding'] or Decimal(0)
    
    print(f"Total charters: {charters['total_charters']:,}")
    print(f"Invoiced (rate): ${invoiced:,.2f}")
    print(f"Collected (paid): ${collected:,.2f}")
    print(f"Outstanding (balance): ${outstanding:,.2f}")
    print(f"Date range: {charters['earliest']} to {charters['latest']}")
    print(f"Collection rate: {collected/invoiced*100 if invoiced > 0 else 0:.1f}%")

    # 4. Reconciliation checks
    print("\n4. RECONCILIATION STATUS")
    print("-" * 80)
    
    deposit_total = deposits['total_amount'] or Decimal(0)
    payment_total = payments['total_amount'] or Decimal(0)
    
    # Check how many deposits match payments
    cur.execute("""
        SELECT COUNT(*) as matchable
        FROM banking_transactions bt
        WHERE bt.credit_amount > 0
          AND EXISTS (
              SELECT 1 FROM payments p 
              WHERE p.payment_date::date = bt.transaction_date::date
              AND ABS(p.amount - bt.credit_amount) <= 0.01
          )
    """)
    matchable = cur.fetchone()['matchable']
    
    print(f"Banking deposits total:    ${deposit_total:,.2f}")
    print(f"Payment records total:     ${payment_total:,.2f}")
    print(f"Charter collected total:   ${collected:,.2f}")
    print(f"\nDeposits matching payments: {matchable:,} / {deposits['total_deposits']:,} ({matchable/deposits['total_deposits']*100:.1f}%)")
    
    # Ratio analysis
    if payment_total > 0:
        deposit_payment_ratio = (deposit_total / payment_total * 100)
        print(f"\nDeposit/Payment ratio: {deposit_payment_ratio:.1f}%")
        
        if deposit_payment_ratio < 25:
            print("  [WARN]  CRITICAL: Banking deposits much less than payments")
            print("      Likely: Missing bank statement imports for many years")
        elif deposit_payment_ratio < 80:
            print("  [WARN]  WARNING: Banking deposits significantly less than payments")
            print("      Likely: Incomplete banking data or different time periods")
        elif deposit_payment_ratio > 120:
            print("  [WARN]  INFO: Deposits exceed payments")
            print("      Likely: Non-payment deposits (refunds, loans, transfers)")
        else:
            print("  ✓ Deposits and payments reasonably aligned")
    
    if collected > 0 and payment_total > 0:
        payment_charter_ratio = (payment_total / collected * 100)
        print(f"\nPayment/Charter collected ratio: {payment_charter_ratio:.1f}%")
        
        if payment_charter_ratio > 200:
            print("  [WARN]  INFO: Payments much higher than charter collections")
            print("      Likely: Payments include non-charter income OR charter paid_amount incomplete")

    # 5. Detailed deposit analysis
    print("\n5. DEPOSIT BREAKDOWN BY PATTERN")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN LOWER(description) LIKE '%transfer%' THEN 'Transfer In'
                WHEN LOWER(description) LIKE '%deposit%' THEN 'Deposit'
                WHEN LOWER(description) LIKE '%reversal%' THEN 'Reversal'
                WHEN LOWER(description) LIKE '%etransfer%' OR LOWER(description) LIKE '%e-transfer%' THEN 'E-Transfer'
                WHEN LOWER(description) LIKE '%payment%' THEN 'Payment'
                WHEN description = '' OR description IS NULL THEN 'No Description'
                ELSE 'Other'
            END as deposit_type,
            COUNT(*) as count,
            SUM(credit_amount) as total
        FROM banking_transactions
        WHERE credit_amount > 0
        GROUP BY deposit_type
        ORDER BY total DESC
    """)
    
    deposit_types = cur.fetchall()
    print(f"{'Type':<20s} | {'Count':>6s} | {'Total':>15s}")
    print('-' * 50)
    for dt in deposit_types:
        print(f"{dt['deposit_type']:<20s} | {dt['count']:6,} | ${dt['total']:14,.2f}")

    # 6. Payment method breakdown
    print("\n6. PAYMENT METHOD BREAKDOWN")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COALESCE(payment_method, 'Unknown') as method,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE amount > 0
        GROUP BY payment_method
        ORDER BY total DESC
        LIMIT 10
    """)
    
    methods = cur.fetchall()
    print(f"{'Method':<20s} | {'Count':>6s} | {'Total':>15s}")
    print('-' * 50)
    for m in methods:
        print(f"{m['method']:<20s} | {m['count']:6,} | ${m['total']:14,.2f}")

    # 7. Year-by-year comparison
    print("\n7. YEAR-BY-YEAR INCOME COMPARISON")
    print("-" * 80)
    
    cur.execute("""
        WITH deposits_by_year AS (
            SELECT 
                EXTRACT(YEAR FROM transaction_date)::int as year,
                COUNT(*) as deposits,
                SUM(credit_amount) as deposit_total
            FROM banking_transactions
            WHERE credit_amount > 0
            GROUP BY EXTRACT(YEAR FROM transaction_date)
        ),
        payments_by_year AS (
            SELECT 
                EXTRACT(YEAR FROM payment_date)::int as year,
                COUNT(*) as payment_count,
                SUM(amount) as payment_total
            FROM payments
            WHERE amount > 0
            GROUP BY EXTRACT(YEAR FROM payment_date)
        )
        SELECT 
            COALESCE(d.year, p.year) as year,
            COALESCE(d.deposits, 0) as deposits,
            COALESCE(d.deposit_total, 0) as deposit_total,
            COALESCE(p.payment_count, 0) as payment_count,
            COALESCE(p.payment_total, 0) as payment_total
        FROM deposits_by_year d
        FULL OUTER JOIN payments_by_year p ON d.year = p.year
        WHERE COALESCE(d.year, p.year) BETWEEN 2007 AND 2025
        ORDER BY year DESC
    """)
    
    years = cur.fetchall()
    print(f"{'Year':<6s} | {'Deposits':>8s} | {'Deposit $':>13s} | {'Payments':>8s} | {'Payment $':>13s} | {'Ratio':>6s}")
    print('-' * 85)
    for y in years:
        ratio = (y['deposit_total'] / y['payment_total'] * 100) if y['payment_total'] and y['payment_total'] > 0 else 0
        print(f"{int(y['year']):<6d} | {y['deposits']:8,} | ${y['deposit_total']:12,.0f} | {y['payment_count']:8,} | ${y['payment_total']:12,.0f} | {ratio:5.0f}%")

    # 8. Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\n✓ Payment records: {payments['total_payments']:,} totaling ${payment_total:,.2f}")
    print(f"✓ Banking deposits: {deposits['total_deposits']:,} totaling ${deposit_total:,.2f}")
    print(f"✓ Charter collections: {charters['total_charters']:,} charters, ${collected:,.2f} collected")
    
    if matchable > 0:
        print(f"\n[WARN]  ACTION: {matchable:,} deposits can be matched to payments")
        print("   Recommendation: Review and link these for complete reconciliation")
    
    if deposit_payment_ratio < 50:
        print(f"\n[WARN]  CRITICAL: Only {deposit_payment_ratio:.0f}% of payments visible in banking")
        print("   Action needed: Import missing bank statements or investigate discrepancy")
    elif matchable / deposits['total_deposits'] < 0.20:
        print(f"\n✓ Most deposits appear to be non-payment income (transfers, refunds)")
        print(f"  Only {matchable:,} ({matchable/deposits['total_deposits']*100:.1f}%) match payment records")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
