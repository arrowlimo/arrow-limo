#!/usr/bin/env python3
"""
Comprehensive 2012 Cash Transaction Scanner

Scans and reports on ALL cash transactions in 2012 from multiple sources:
1. payments table - payment_method = 'cash'
2. banking_transactions - cash withdrawals, ATM, etc.
3. receipts table - cash receipts
4. LMS Access database - cash payment types

Generates detailed report with:
- Monthly cash flow analysis
- Matched vs unmatched cash transactions
- Cash payment reconciliation status
- Vendor analysis for cash expenses
- Charter linkage for cash revenue
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from collections import defaultdict

# Try to connect to LMS Access database if available
try:
    import pyodbc
    LMS_AVAILABLE = True
    LMS_PATH = r'L:\limo\lms.mdb'
except ImportError:
    LMS_AVAILABLE = False
    print("Warning: pyodbc not available - LMS data will be skipped")

def get_db_connection():
    """Connect to PostgreSQL almsdata database."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    )

def get_lms_connection():
    """Connect to LMS Access database if available."""
    if not LMS_AVAILABLE:
        return None
    try:
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"Warning: Could not connect to LMS: {e}")
        return None

def analyze_payments_cash(cur):
    """Analyze cash payments from payments table."""
    print("\n" + "="*100)
    print("1. PAYMENTS TABLE - CASH TRANSACTIONS")
    print("="*100)
    
    # Total cash payments in 2012
    cur.execute("""
        SELECT 
            COUNT(*) as payment_count,
            SUM(amount) as total_amount,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as matched_to_charter,
            COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as unmatched,
            COUNT(DISTINCT account_number) as unique_accounts,
            COUNT(DISTINCT client_id) as unique_clients
        FROM payments
        WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(payment_method) = 'cash'
    """)
    totals = cur.fetchone()
    
    print(f"\n=== 2012 Cash Payments Overview ===")
    print(f"Total cash payments: {totals['payment_count']:,}")
    print(f"Total amount: ${totals['total_amount']:,.2f}" if totals['total_amount'] else "$0.00")
    print(f"Matched to charters: {totals['matched_to_charter']:,} ({totals['matched_to_charter']/totals['payment_count']*100:.1f}%)" if totals['payment_count'] > 0 else "Matched to charters: 0")
    print(f"Unmatched: {totals['unmatched']:,}")
    print(f"Unique accounts: {totals['unique_accounts']:,}")
    print(f"Unique clients: {totals['unique_clients']:,}")
    
    # Monthly breakdown
    cur.execute("""
        SELECT 
            TO_CHAR(payment_date, 'YYYY-MM') as month,
            COUNT(*) as payment_count,
            SUM(amount) as total_amount,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as matched,
            COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as unmatched
        FROM payments
        WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(payment_method) = 'cash'
        GROUP BY month
        ORDER BY month
    """)
    
    print(f"\n=== Monthly Cash Payment Breakdown ===")
    print(f"{'Month':<10} {'Count':>7} {'Amount':>14} {'Matched':>10} {'Unmatched':>10} {'Match %':>10}")
    print("-" * 80)
    
    monthly_data = []
    for row in cur.fetchall():
        amt = row['total_amount'] or 0
        count = row['payment_count'] or 0
        matched = row['matched'] or 0
        match_pct = (matched / count * 100) if count > 0 else 0
        monthly_data.append(row)
        print(f"{row['month']:<10} {count:>7,} ${amt:>13,.2f} {matched:>10,} {row['unmatched']:>10,} {match_pct:>9.1f}%")
    
    # Top unmatched cash payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            account_number,
            reserve_number,
            reference_number,
            notes
        FROM payments
        WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(payment_method) = 'cash'
          AND charter_id IS NULL
        ORDER BY amount DESC NULLS LAST
        LIMIT 20
    """)
    
    unmatched = cur.fetchall()
    if unmatched:
        print(f"\n=== Top 20 Unmatched Cash Payments (High Value) ===")
        print(f"{'ID':<10} {'Date':<12} {'Amount':>12} {'Account':<12} {'Reserve#':<12} {'Reference':<15} {'Notes':<30}")
        print("-" * 110)
        for row in unmatched:
            notes_str = (row['notes'] or '')[:27] + '...' if row['notes'] and len(row['notes']) > 30 else (row['notes'] or '')
            ref_str = (row['reference_number'] or '')[:12] + '...' if row['reference_number'] and len(row['reference_number']) > 15 else (row['reference_number'] or '')
            print(f"{row['payment_id']:<10} {row['payment_date'].strftime('%Y-%m-%d'):<12} ${row['amount']:>11,.2f} {row['account_number'] or 'N/A':<12} {row['reserve_number'] or 'N/A':<12} {ref_str:<15} {notes_str:<30}")
    
    return monthly_data

def analyze_banking_cash(cur):
    """Analyze cash-related banking transactions."""
    print("\n" + "="*100)
    print("2. BANKING TRANSACTIONS - CASH WITHDRAWALS & ATM")
    print("="*100)
    
    # Cash withdrawals from banking
    cur.execute("""
        SELECT 
            COUNT(*) as transaction_count,
            SUM(debit_amount) as total_debits,
            COUNT(DISTINCT account_number) as unique_accounts
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND debit_amount IS NOT NULL
          AND debit_amount > 0
          AND (
              UPPER(description) LIKE '%CASH%'
              OR UPPER(description) LIKE '%ATM%'
              OR UPPER(description) LIKE '%WITHDRAWAL%'
              OR UPPER(description) LIKE '%CHEQUE%CASH%'
          )
    """)
    totals = cur.fetchone()
    
    print(f"\n=== 2012 Cash-Related Banking Transactions ===")
    print(f"Total transactions: {totals['transaction_count']:,}")
    print(f"Total amount: ${totals['total_debits']:,.2f}" if totals['total_debits'] else "$0.00")
    print(f"Accounts: {totals['unique_accounts']:,}")
    
    # Monthly breakdown
    cur.execute("""
        SELECT 
            TO_CHAR(transaction_date, 'YYYY-MM') as month,
            COUNT(*) as transaction_count,
            SUM(debit_amount) as total_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND debit_amount IS NOT NULL
          AND debit_amount > 0
          AND (
              UPPER(description) LIKE '%CASH%'
              OR UPPER(description) LIKE '%ATM%'
              OR UPPER(description) LIKE '%WITHDRAWAL%'
              OR UPPER(description) LIKE '%CHEQUE%CASH%'
          )
        GROUP BY month
        ORDER BY month
    """)
    
    print(f"\n=== Monthly Cash Banking Activity ===")
    print(f"{'Month':<10} {'Count':>7} {'Amount':>14}")
    print("-" * 40)
    for row in cur.fetchall():
        amt = row['total_amount'] or 0
        print(f"{row['month']:<10} {row['transaction_count']:>7,} ${amt:>13,.2f}")
    
    # Sample transactions by pattern
    patterns = [
        ('ATM Withdrawals', '%ATM%'),
        ('Cash Withdrawals', '%WITHDRAWAL%'),
        ('Cheque Cash', '%CHEQUE%CASH%'),
        ('Direct Cash', '%DD CASH%'),
        ('Cash Deposits', 'CASH%')
    ]
    
    print(f"\n=== Cash Transaction Patterns ===")
    for pattern_name, pattern in patterns:
        cur.execute("""
            SELECT COUNT(*) as count, SUM(debit_amount) as debit_sum, SUM(credit_amount) as credit_sum
            FROM banking_transactions
            WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
              AND UPPER(description) LIKE %s
        """, (pattern,))
        
        row = cur.fetchone()
        if row and row['count'] > 0:
            debit_amt = row['debit_sum'] or 0
            credit_amt = row['credit_sum'] or 0
            print(f"{pattern_name:20s}: {row['count']:4,} transactions | Debits: ${debit_amt:>12,.2f} | Credits: ${credit_amt:>12,.2f}")
    
    # Top cash transactions
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            account_number
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (
              UPPER(description) LIKE '%CASH%'
              OR UPPER(description) LIKE '%ATM%'
          )
        ORDER BY COALESCE(debit_amount, credit_amount) DESC NULLS LAST
        LIMIT 20
    """)
    
    print(f"\n=== Top 20 Cash Banking Transactions ===")
    print(f"{'Date':<12} {'Description':<50} {'Debit':>12} {'Credit':>12} {'Account':<10}")
    print("-" * 110)
    for row in cur.fetchall():
        desc = row['description'][:47] + '...' if len(row['description']) > 50 else row['description']
        debit = f"${row['debit_amount']:,.2f}" if row['debit_amount'] else ""
        credit = f"${row['credit_amount']:,.2f}" if row['credit_amount'] else ""
        print(f"{row['transaction_date'].strftime('%Y-%m-%d'):<12} {desc:<50} {debit:>12} {credit:>12} {row['account_number']:<10}")

def analyze_receipts_cash(cur):
    """Analyze cash receipts/expenses."""
    print("\n" + "="*100)
    print("3. RECEIPTS TABLE - CASH EXPENSES")
    print("="*100)
    
    # Check if payment_method column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name = 'payment_method'
    """)
    has_payment_method = cur.fetchone() is not None
    
    if has_payment_method:
        # Cash receipts with explicit payment_method
        cur.execute("""
            SELECT 
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount,
                COUNT(DISTINCT vendor_name) as unique_vendors,
                COUNT(DISTINCT category) as unique_categories
            FROM receipts
            WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
              AND LOWER(payment_method) = 'cash'
        """)
        totals = cur.fetchone()
        
        print(f"\n=== 2012 Cash Receipts (Explicit) ===")
        print(f"Total receipts: {totals['receipt_count']:,}")
        print(f"Total amount: ${totals['total_amount']:,.2f}" if totals['total_amount'] else "$0.00")
        print(f"Unique vendors: {totals['unique_vendors']:,}")
        print(f"Unique categories: {totals['unique_categories']:,}")
    else:
        print("\n=== Note: payment_method column not found in receipts ===")
    
    # All receipts in 2012 (regardless of payment method)
    cur.execute("""
        SELECT 
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount,
            COUNT(DISTINCT vendor_name) as unique_vendors,
            COUNT(CASE WHEN created_from_banking = true THEN 1 END) as from_banking
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
    """)
    all_receipts = cur.fetchone()
    
    print(f"\n=== 2012 All Receipts (Any Payment Method) ===")
    print(f"Total receipts: {all_receipts['receipt_count']:,}")
    print(f"Total amount: ${all_receipts['total_amount']:,.2f}" if all_receipts['total_amount'] else "$0.00")
    print(f"Unique vendors: {all_receipts['unique_vendors']:,}")
    print(f"Created from banking: {all_receipts['from_banking']:,}")
    
    # Category breakdown
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
        GROUP BY category
        ORDER BY total_amount DESC NULLS LAST
        LIMIT 15
    """)
    
    print(f"\n=== Top 15 Receipt Categories (2012) ===")
    print(f"{'Category':<30} {'Count':>7} {'Amount':>14}")
    print("-" * 60)
    for row in cur.fetchall():
        cat = (row['category'] or 'Uncategorized')[:27] + '...' if row['category'] and len(row['category']) > 30 else (row['category'] or 'Uncategorized')
        amt = row['total_amount'] or 0
        print(f"{cat:<30} {row['receipt_count']:>7,} ${amt:>13,.2f}")

def analyze_lms_cash(lms_conn):
    """Analyze cash payments from LMS Access database."""
    print("\n" + "="*100)
    print("4. LMS ACCESS DATABASE - CASH PAYMENTS")
    print("="*100)
    
    if not lms_conn:
        print("\n=== LMS Not Available ===")
        return
    
    try:
        cur = lms_conn.cursor()
        
        # Cash payments in 2012
        cur.execute("""
            SELECT 
                COUNT(*) as payment_count,
                SUM(Amount) as total_amount
            FROM Payment
            WHERE Year(LastUpdated) = 2012
              AND (Pymt_Type LIKE '%cash%' OR Pymt_Type LIKE '%Cash%')
        """)
        
        row = cur.fetchone()
        if row:
            print(f"\n=== 2012 LMS Cash Payments ===")
            print(f"Total payments: {row[0]:,}")
            print(f"Total amount: ${row[1]:,.2f}" if row[1] else "$0.00")
        
        # Monthly breakdown
        cur.execute("""
            SELECT 
                Format(LastUpdated, 'yyyy-mm') as Month,
                COUNT(*) as PaymentCount,
                SUM(Amount) as TotalAmount
            FROM Payment
            WHERE Year(LastUpdated) = 2012
              AND (Pymt_Type LIKE '%cash%' OR Pymt_Type LIKE '%Cash%')
            GROUP BY Format(LastUpdated, 'yyyy-mm')
            ORDER BY Format(LastUpdated, 'yyyy-mm')
        """)
        
        print(f"\n=== Monthly LMS Cash Payments ===")
        print(f"{'Month':<10} {'Count':>7} {'Amount':>14}")
        print("-" * 40)
        for row in cur.fetchall():
            print(f"{row[0]:<10} {row[1]:>7,} ${row[2]:>13,.2f}" if row[2] else f"{row[0]:<10} {row[1]:>7,} $0.00")
        
        # Payment type breakdown
        cur.execute("""
            SELECT 
                Pymt_Type,
                COUNT(*) as PaymentCount,
                SUM(Amount) as TotalAmount
            FROM Payment
            WHERE Year(LastUpdated) = 2012
              AND (Pymt_Type LIKE '%cash%' OR Pymt_Type LIKE '%Cash%')
            GROUP BY Pymt_Type
            ORDER BY COUNT(*) DESC
        """)
        
        print(f"\n=== LMS Cash Payment Types ===")
        print(f"{'Payment Type':<20} {'Count':>7} {'Amount':>14}")
        print("-" * 50)
        for row in cur.fetchall():
            ptype = (row[0] or 'Unknown')[:17] + '...' if row[0] and len(row[0]) > 20 else (row[0] or 'Unknown')
            print(f"{ptype:<20} {row[1]:>7,} ${row[2]:>13,.2f}" if row[2] else f"{ptype:<20} {row[1]:>7,} $0.00")
        
        cur.close()
        
    except Exception as e:
        print(f"\n=== Error querying LMS: {e} ===")

def reconciliation_summary(cur):
    """Generate reconciliation summary between sources."""
    print("\n" + "="*100)
    print("5. CASH TRANSACTION RECONCILIATION SUMMARY")
    print("="*100)
    
    # Compare payments vs banking
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM payments 
             WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
             AND LOWER(payment_method) = 'cash') as payments_cash,
            (SELECT SUM(amount) FROM payments 
             WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
             AND LOWER(payment_method) = 'cash') as payments_amount,
            (SELECT COUNT(*) FROM banking_transactions
             WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
             AND debit_amount IS NOT NULL
             AND (UPPER(description) LIKE '%CASH%' OR UPPER(description) LIKE '%ATM%')) as banking_cash,
            (SELECT SUM(debit_amount) FROM banking_transactions
             WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
             AND debit_amount IS NOT NULL
             AND (UPPER(description) LIKE '%CASH%' OR UPPER(description) LIKE '%ATM%')) as banking_amount,
            (SELECT COUNT(*) FROM receipts
             WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31') as receipts_count,
            (SELECT SUM(gross_amount) FROM receipts
             WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31') as receipts_amount
    """)
    
    row = cur.fetchone()
    
    print(f"\n=== Data Source Comparison ===")
    print(f"{'Source':<25} {'Count':>10} {'Amount':>15}")
    print("-" * 60)
    print(f"{'Payments (cash)':<25} {row['payments_cash']:>10,} ${row['payments_amount']:>14,.2f}" if row['payments_amount'] else f"{'Payments (cash)':<25} {row['payments_cash']:>10,} $0.00")
    print(f"{'Banking (cash/ATM)':<25} {row['banking_cash']:>10,} ${row['banking_amount']:>14,.2f}" if row['banking_amount'] else f"{'Banking (cash/ATM)':<25} {row['banking_cash']:>10,} $0.00")
    print(f"{'Receipts (all)':<25} {row['receipts_count']:>10,} ${row['receipts_amount']:>14,.2f}" if row['receipts_amount'] else f"{'Receipts (all)':<25} {row['receipts_count']:>10,} $0.00")
    
    print(f"\n=== Key Metrics ===")
    payments_matched_pct = "(see section 1 above)"
    print(f"Cash payments matched to charters: {payments_matched_pct}")
    print(f"Banking-linked receipts: (see section 3 above)")
    
    print(f"\n=== Recommendations ===")
    print("1. Review unmatched cash payments for charter linkage opportunities")
    print("2. Verify banking cash withdrawals have corresponding receipts/expenses")
    print("3. Cross-reference LMS cash payments with PostgreSQL payments table")
    print("4. Investigate high-value unmatched transactions first")

def main():
    """Main execution function."""
    print("\n" + "="*100)
    print("COMPREHENSIVE 2012 CASH TRANSACTION SCANNER")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    # Connect to databases
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    lms_conn = get_lms_connection()
    
    try:
        # Run all analyses
        analyze_payments_cash(cur)
        analyze_banking_cash(cur)
        analyze_receipts_cash(cur)
        analyze_lms_cash(lms_conn)
        reconciliation_summary(cur)
        
        print("\n" + "="*100)
        print("SCAN COMPLETE")
        print("="*100 + "\n")
        
    finally:
        cur.close()
        conn.close()
        if lms_conn:
            lms_conn.close()

if __name__ == '__main__':
    main()
