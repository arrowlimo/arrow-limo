"""
Find recurring monthly payments that could be CRA source deduction remittances.

Since no quarterly payments were made, searches for:
- Monthly recurring payment patterns
- Pre-authorized debits (PAD)
- Online bill payments
- Cheque payments in typical CRA remittance ranges
"""

import psycopg2
import os
from collections import defaultdict
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("SEARCHING FOR RECURRING MONTHLY CRA PAYMENTS")
    print("=" * 80)
    print()
    
    # 1. Search for PAD/Pre-authorized debits
    print("1. PRE-AUTHORIZED DEBITS (PAD)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE 
            (UPPER(description) LIKE '%PAD%'
            OR UPPER(description) LIKE '%PRE-AUTH%'
            OR UPPER(description) LIKE '%PREAUTH%'
            OR UPPER(description) LIKE '%PRE AUTH%')
            AND debit_amount > 0
        ORDER BY transaction_date
    """)
    
    pad_payments = cur.fetchall()
    print(f"Found {len(pad_payments)} PAD transactions\n")
    
    if pad_payments:
        print("PAD transactions (showing all):")
        for date, desc, amount, acct in pad_payments:
            acct_name = 'CIBC' if acct == '0228362' else 'Scotia' if acct == '903990106011' else (acct or 'Unknown')
            print(f"  {date} | {(desc or '')[:55]:55s} | ${amount or 0:>10,.2f} | {acct_name}")
    print()
    
    # 2. Search for online bill payments
    print("2. ONLINE BILL PAYMENTS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE 
            (UPPER(description) LIKE '%BILL PAYMENT%'
            OR UPPER(description) LIKE '%BILLPAY%'
            OR UPPER(description) LIKE '%PAYMENT TO%'
            OR UPPER(description) LIKE '%ONLINE PAYMENT%'
            OR UPPER(description) LIKE '%INTERNET PAYMENT%')
            AND debit_amount > 0
            AND debit_amount > 100  -- Exclude small payments
        ORDER BY transaction_date
    """)
    
    bill_payments = cur.fetchall()
    print(f"Found {len(bill_payments)} online bill payments\n")
    
    if bill_payments:
        # Group by month to identify recurring patterns
        by_month = defaultdict(list)
        for date, desc, amount, acct in bill_payments:
            month_key = f"{date.year}-{date.month:02d}"
            by_month[month_key].append((date, desc, amount, acct))
        
        print(f"Payments by month ({len(by_month)} months):")
        for month in sorted(by_month.keys())[-24:]:  # Last 24 months
            payments = by_month[month]
            total = sum(p[2] or 0 for p in payments)
            print(f"  {month}: {len(payments)} payments, ${total:,.2f}")
    print()
    
    # 3. Search for MISC PAYMENT (generic payment descriptor)
    print("3. MISC PAYMENTS (Generic Payment Descriptor)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE 
            UPPER(description) LIKE '%MISC PAYMENT%'
            AND debit_amount > 0
        ORDER BY transaction_date
    """)
    
    misc_payments = cur.fetchall()
    print(f"Found {len(misc_payments)} MISC PAYMENT transactions\n")
    
    if misc_payments:
        print("All MISC PAYMENT transactions:")
        for date, desc, amount, acct in misc_payments:
            acct_name = 'CIBC' if acct == '0228362' else 'Scotia' if acct == '903990106011' else (acct or 'Unknown')
            print(f"  {date} | {(desc or '')[:55]:55s} | ${amount or 0:>10,.2f} | {acct_name}")
    print()
    
    # 4. Search for payments in typical CRA remittance amount ranges
    print("4. PAYMENTS IN TYPICAL CRA REMITTANCE RANGES")
    print("-" * 80)
    print("Looking for monthly payments between $500-$5,000 (typical for small business)")
    print()
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            EXTRACT(MONTH FROM transaction_date) as month,
            COUNT(*) as payment_count,
            ARRAY_AGG(transaction_date ORDER BY transaction_date) as dates,
            ARRAY_AGG(debit_amount ORDER BY transaction_date) as amounts,
            ARRAY_AGG(description ORDER BY transaction_date) as descriptions
        FROM banking_transactions
        WHERE 
            debit_amount BETWEEN 500 AND 5000
            AND UPPER(description) NOT LIKE '%PURCHASE%'
            AND UPPER(description) NOT LIKE '%CENTEX%'
            AND UPPER(description) NOT LIKE '%SHELL%'
            AND UPPER(description) NOT LIKE '%GAS%'
            AND UPPER(description) NOT LIKE '%HEFFNER%'
        GROUP BY year, month
        HAVING COUNT(*) BETWEEN 1 AND 3  -- 1-3 payments per month
        ORDER BY year, month
    """)
    
    monthly_patterns = cur.fetchall()
    print(f"Found {len(monthly_patterns)} months with 1-3 payments in CRA range\n")
    
    if monthly_patterns:
        print("Recent months with potential CRA payments:")
        for year, month, count, dates, amounts, descs in monthly_patterns[-24:]:
            print(f"\n  {int(year)}-{int(month):02d}: {count} payment(s)")
            for i in range(count):
                desc_str = (descs[i] or '')[:50] if descs else ''
                amt = amounts[i] if amounts else 0
                print(f"    {dates[i]} | ${amt:>10,.2f} | {desc_str}")
    print()
    
    # 5. Search for cheque payments in CRA range
    print("5. CHEQUE PAYMENTS IN CRA REMITTANCE RANGE")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE 
            (UPPER(description) LIKE '%CHEQUE%'
            OR UPPER(description) LIKE '%CHQ%'
            OR UPPER(description) LIKE '%CHECK%')
            AND debit_amount BETWEEN 500 AND 5000
        ORDER BY transaction_date
    """)
    
    cheque_payments = cur.fetchall()
    print(f"Found {len(cheque_payments)} cheque payments in $500-$5,000 range\n")
    
    if cheque_payments:
        # Group by year
        by_year = defaultdict(list)
        for date, desc, amount, acct in cheque_payments:
            by_year[date.year].append((date, desc, amount, acct))
        
        print("Cheque payments by year:")
        for year in sorted(by_year.keys()):
            payments = by_year[year]
            total = sum(p[2] or 0 for p in payments)
            print(f"\n  {year}: {len(payments)} cheques, ${total:,.2f} total")
            for date, desc, amount, acct in payments[:5]:  # Show first 5
                print(f"    {date} | ${amount or 0:>10,.2f} | {(desc or '')[:45]}")
            if len(payments) > 5:
                print(f"    ... and {len(payments) - 5} more")
    print()
    
    # 6. Look for payments on specific days of month (CRA remittance due dates)
    print("6. PAYMENTS ON TYPICAL CRA REMITTANCE DUE DATES")
    print("-" * 80)
    print("CRA remittances typically due by 15th of following month")
    print()
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE 
            EXTRACT(DAY FROM transaction_date) BETWEEN 10 AND 20
            AND debit_amount BETWEEN 500 AND 10000
            AND UPPER(description) NOT LIKE '%PURCHASE%'
            AND UPPER(description) NOT LIKE '%CENTEX%'
            AND UPPER(description) NOT LIKE '%SHELL%'
            AND UPPER(description) NOT LIKE '%HEFFNER%'
            AND EXTRACT(YEAR FROM transaction_date) >= 2012
        ORDER BY transaction_date DESC
        LIMIT 50
    """)
    
    mid_month_payments = cur.fetchall()
    print(f"Found {len(mid_month_payments)} payments between 10th-20th of month (showing recent 50)\n")
    
    if mid_month_payments:
        for date, desc, amount, acct in mid_month_payments[:20]:
            acct_name = 'CIBC' if acct == '0228362' else 'Scotia' if acct == '903990106011' else (acct or 'Unknown')
            print(f"  {date} | {(desc or '')[:50]:50s} | ${amount or 0:>10,.2f} | {acct_name}")
    
    print()
    print("=" * 80)
    print("SEARCH COMPLETE")
    print("=" * 80)
    print()
    print("NEXT STEPS:")
    print("- Review PAD payments for CRA identifiers")
    print("- Check MISC PAYMENT descriptions for government references")
    print("- Examine mid-month payments (10th-20th) as these align with CRA due dates")
    print("- Look for patterns in cheque payments that repeat monthly")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
