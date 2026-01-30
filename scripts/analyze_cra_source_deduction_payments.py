"""
Analyze all CRA and source deduction payments to identify patterns and potential gaps.

Searches receipts, banking_transactions, and email_financial_events for:
- CRA payments (income tax, GST/HST remittances)
- Source deduction payments (CPP, EI, payroll tax remittances)
- Receiver General payments
- WCB payments

Then analyzes payroll data to estimate expected remittances and identify gaps.
"""

import psycopg2
import os
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CRA & SOURCE DEDUCTION PAYMENTS ANALYSIS")
    print("=" * 80)
    print()
    
    # 1. Find all CRA-related receipts
    print("1. RECEIPTS TABLE - CRA/Source Deduction Payments")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            category
        FROM receipts
        WHERE 
            UPPER(vendor_name) LIKE '%CRA%'
            OR UPPER(vendor_name) LIKE '%CANADA REVENUE%'
            OR UPPER(vendor_name) LIKE '%RECEIVER GENERAL%'
            OR UPPER(vendor_name) LIKE '%SOURCE DEDUCTION%'
            OR UPPER(vendor_name) LIKE '%PAYROLL REMITTANCE%'
            OR UPPER(description) LIKE '%CRA%'
            OR UPPER(description) LIKE '%CANADA REVENUE%'
            OR UPPER(description) LIKE '%RECEIVER GENERAL%'
            OR UPPER(description) LIKE '%SOURCE DEDUCTION%'
            OR category = 'government_fees'
        ORDER BY receipt_date
    """)
    
    receipt_payments = cur.fetchall()
    receipt_total = sum(row[2] for row in receipt_payments if row[2])
    
    print(f"Found {len(receipt_payments)} CRA/government receipts")
    print(f"Total amount: ${receipt_total:,.2f}\n")
    
    if receipt_payments:
        print("Recent entries:")
        for date, vendor, amount, desc, cat in receipt_payments[-10:]:
            print(f"  {date} | {vendor:40s} | ${amount:>10,.2f} | {cat}")
    print()
    
    # 2. Find all CRA-related banking transactions
    print("2. BANKING TRANSACTIONS - CRA/Source Deduction Payments")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE 
            UPPER(description) LIKE '%CRA%'
            OR UPPER(description) LIKE '%CANADA REVENUE%'
            OR UPPER(description) LIKE '%RECEIVER GENERAL%'
            OR UPPER(description) LIKE '%RQ%' -- Revenu Quebec
            OR UPPER(description) LIKE '%SOURCE DEDUCTION%'
            OR UPPER(description) LIKE '%PAYROLL%REMIT%'
            OR UPPER(description) LIKE '%TAX REMIT%'
        ORDER BY transaction_date
    """)
    
    banking_payments = cur.fetchall()
    banking_total = sum(row[2] for row in banking_payments if row[2])
    
    print(f"Found {len(banking_payments)} CRA/government banking transactions")
    print(f"Total amount: ${banking_total:,.2f}\n")
    
    if banking_payments:
        print("Recent entries:")
        for date, desc, amount, acct in banking_payments[-10:]:
            acct_name = 'CIBC' if acct == '0228362' else 'Scotia' if acct == '903990106011' else (acct or 'Unknown')
            desc_str = (desc or '')[:50]
            amt_val = amount or 0
            print(f"  {date} | {desc_str:50s} | ${amt_val:>10,.2f} | {acct_name}")
    print()
    
    # 3. Find WCB payments (related to payroll)
    print("3. WCB (Workers Compensation) Payments")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            description
        FROM receipts
        WHERE 
            UPPER(vendor_name) LIKE '%WCB%'
            OR UPPER(vendor_name) LIKE '%WORKERS COMP%'
            OR UPPER(description) LIKE '%WCB%'
            OR UPPER(description) LIKE '%WORKERS COMP%'
        ORDER BY receipt_date
    """)
    
    wcb_payments = cur.fetchall()
    wcb_total = sum(row[2] for row in wcb_payments if row[2])
    
    print(f"Found {len(wcb_payments)} WCB payments")
    print(f"Total amount: ${wcb_total:,.2f}\n")
    
    if wcb_payments:
        print("All WCB payments:")
        for date, vendor, amount, desc in wcb_payments:
            print(f"  {date} | {vendor:40s} | ${amount:>10,.2f}")
    print()
    
    # 4. Email financial events
    print("4. EMAIL FINANCIAL EVENTS - Government/CRA")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            email_date,
            event_type,
            amount,
            notes,
            matched_account_number
        FROM email_financial_events
        WHERE 
            UPPER(notes) LIKE '%CRA%'
            OR UPPER(notes) LIKE '%RECEIVER GENERAL%'
            OR UPPER(notes) LIKE '%TAX%'
            OR event_type LIKE '%government%'
        ORDER BY email_date
    """)
    
    email_events = cur.fetchall()
    email_total = sum(row[2] for row in email_events if row[2])
    
    print(f"Found {len(email_events)} email events related to government payments")
    print(f"Total amount: ${email_total:,.2f}\n")
    
    if email_events:
        for date, event_type, amount, notes, acct in email_events[-10:]:
            event_str = (event_type or '')[:20]
            amt_val = amount or 0
            notes_str = (notes or '')[:50]
            print(f"  {date} | {event_str:20s} | ${amt_val:>10,.2f} | {notes_str}")
    print()
    
    # 5. Analyze payroll to estimate expected remittances
    print("5. PAYROLL ANALYSIS - Expected Source Deductions")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            year,
            COUNT(*) as pay_periods,
            SUM(gross_pay) as total_gross,
            SUM(cpp) as total_cpp,
            SUM(ei) as total_ei,
            SUM(tax) as total_tax,
            SUM(COALESCE(cpp, 0) + COALESCE(ei, 0) + COALESCE(tax, 0)) as total_remittance_due
        FROM driver_payroll
        WHERE payroll_class = 'WAGE' OR payroll_class IS NULL
        GROUP BY year
        ORDER BY year
    """)
    
    payroll_summary = cur.fetchall()
    
    print("Expected source deduction remittances by year:")
    print(f"{'Year':<6} {'Periods':<8} {'Gross Pay':>12} {'CPP':>12} {'EI':>12} {'Tax':>12} {'Total Due':>12}")
    print("-" * 80)
    
    total_expected = 0
    for year, periods, gross, cpp, ei, tax, remit_due in payroll_summary:
        print(f"{year:<6} {periods:<8} ${gross or 0:>11,.2f} ${cpp or 0:>11,.2f} ${ei or 0:>11,.2f} ${tax or 0:>11,.2f} ${remit_due or 0:>11,.2f}")
        total_expected += (remit_due or 0)
    
    print("-" * 80)
    print(f"{'TOTAL':<6} {'':<8} {'':<12} {'':<12} {'':<12} {'':<12} ${total_expected:>11,.2f}")
    print()
    
    # 6. Gap analysis
    print("6. GAP ANALYSIS")
    print("-" * 80)
    
    total_paid = receipt_total + banking_total + wcb_total
    
    print(f"Expected source deductions (from payroll):  ${total_expected:>12,.2f}")
    print(f"CRA payments found in receipts:             ${receipt_total:>12,.2f}")
    print(f"CRA payments found in banking:              ${banking_total:>12,.2f}")
    print(f"WCB payments found:                         ${wcb_total:>12,.2f}")
    print(f"Total payments identified:                  ${total_paid:>12,.2f}")
    print()
    print(f"Potential gap:                              ${total_expected - total_paid:>12,.2f}")
    print()
    
    # 7. Year-by-year analysis
    print("7. YEAR-BY-YEAR COMPARISON")
    print("-" * 80)
    
    for year, periods, gross, cpp, ei, tax, remit_due in payroll_summary:
        # Find payments for this year
        cur.execute("""
            SELECT SUM(gross_amount)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            AND (
                UPPER(vendor_name) LIKE '%%CRA%%'
                OR UPPER(vendor_name) LIKE '%%CANADA REVENUE%%'
                OR UPPER(vendor_name) LIKE '%%RECEIVER GENERAL%%'
                OR category = 'government_fees'
            )
        """, (year,))
        
        year_receipts = cur.fetchone()[0] or 0
        
        cur.execute("""
            SELECT SUM(debit_amount)
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND (
                UPPER(description) LIKE '%%CRA%%'
                OR UPPER(description) LIKE '%%CANADA REVENUE%%'
                OR UPPER(description) LIKE '%%RECEIVER GENERAL%%'
            )
        """, (year,))
        
        year_banking = cur.fetchone()[0] or 0
        
        year_paid = year_receipts + year_banking
        year_gap = (remit_due or 0) - year_paid
        
        print(f"\n{year}:")
        print(f"  Expected remittance: ${remit_due or 0:>10,.2f}")
        print(f"  Payments found:      ${year_paid:>10,.2f}")
        print(f"  Gap:                 ${year_gap:>10,.2f}")
        
        if year_gap > 1000:
            print(f"  ⚠️  SIGNIFICANT GAP - May be missing payment records")
        elif year_gap < -1000:
            print(f"  ⚠️  OVERPAYMENT - May include other tax payments (GST, corporate tax)")
        else:
            print(f"  ✅ Reasonable match")
    
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print("NOTES:")
    print("- Source deductions include CPP, EI, and income tax withheld from employees")
    print("- Employer must remit these to CRA monthly (or quarterly if small remitter)")
    print("- Gaps may indicate:")
    print("  1. Missing payment records in system")
    print("  2. Payments made but not categorized as CRA")
    print("  3. Outstanding balances owed to CRA")
    print("- Large overpayments may include GST/HST remittances or corporate tax")
    print("- WCB is separate from CRA (provincial workers compensation)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
