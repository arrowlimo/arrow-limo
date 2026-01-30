#!/usr/bin/env python
"""
Analyze general_ledger to identify accounts needed for CRA forms:
- GST/HST collected, paid, ITCs
- Revenue/sales accounts
- Payroll tax accounts (CPP, EI, Income Tax)
- Source deduction remittances
"""
import psycopg2
from collections import defaultdict
from decimal import Decimal

def get_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def analyze_gst_accounts():
    """Find GST/HST related accounts"""
    print("=" * 80)
    print("GST/HST ACCOUNTS")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Find GST/HST accounts
    cur.execute("""
        SELECT DISTINCT account
        FROM general_ledger
        WHERE lower(account) LIKE '%gst%' 
           OR lower(account) LIKE '%hst%'
           OR lower(account) LIKE '%goods and services%'
        ORDER BY account
    """)
    
    gst_accounts = [r[0] for r in cur.fetchall() if r[0]]
    print(f"\nFound {len(gst_accounts)} GST/HST accounts:\n")
    
    for acc in gst_accounts:
        cur.execute("""
            SELECT 
                COUNT(*) as txn_count,
                SUM(COALESCE(debit, 0)) as total_debits,
                SUM(COALESCE(credit, 0)) as total_credits,
                SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) as net_balance
            FROM general_ledger
            WHERE account = %s
        """, (acc,))
        
        count, debits, credits, net = cur.fetchone()
        print(f"  {acc}")
        print(f"    Transactions: {count:,}")
        print(f"    Debits:  ${debits:,.2f}")
        print(f"    Credits: ${credits:,.2f}")
        print(f"    Net:     ${net:,.2f}")
        print()
    
    conn.close()
    return gst_accounts

def analyze_revenue_accounts():
    """Find revenue/sales accounts"""
    print("=" * 80)
    print("REVENUE/SALES ACCOUNTS")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT account
        FROM general_ledger
        WHERE (lower(account) LIKE '%revenue%' 
           OR lower(account) LIKE '%sales%'
           OR lower(account) LIKE '%income%')
           AND lower(account) NOT LIKE '%expense%'
           AND lower(account) NOT LIKE '%cost%'
        ORDER BY account
    """)
    
    rev_accounts = [r[0] for r in cur.fetchall() if r[0]]
    print(f"\nFound {len(rev_accounts)} revenue accounts:\n")
    
    for acc in rev_accounts[:20]:  # Show top 20
        cur.execute("""
            SELECT 
                COUNT(*) as txn_count,
                SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) as net_revenue
            FROM general_ledger
            WHERE account = %s
        """, (acc,))
        
        count, net = cur.fetchone()
        print(f"  {acc}")
        print(f"    Transactions: {count:,}")
        print(f"    Net Revenue: ${net:,.2f}")
        print()
    
    if len(rev_accounts) > 20:
        print(f"  ... and {len(rev_accounts) - 20} more revenue accounts")
    
    conn.close()
    return rev_accounts

def analyze_payroll_tax_accounts():
    """Find payroll/source deduction accounts"""
    print("=" * 80)
    print("PAYROLL TAX ACCOUNTS (CPP, EI, Income Tax)")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT account
        FROM general_ledger
        WHERE lower(account) LIKE '%cpp%' 
           OR lower(account) LIKE '%ei%'
           OR lower(account) LIKE '%income tax%'
           OR lower(account) LIKE '%payroll tax%'
           OR lower(account) LIKE '%source deduction%'
           OR lower(account) LIKE '%withhold%'
        ORDER BY account
    """)
    
    payroll_accounts = [r[0] for r in cur.fetchall() if r[0]]
    print(f"\nFound {len(payroll_accounts)} payroll tax accounts:\n")
    
    for acc in payroll_accounts:
        cur.execute("""
            SELECT 
                COUNT(*) as txn_count,
                SUM(COALESCE(debit, 0)) as total_debits,
                SUM(COALESCE(credit, 0)) as total_credits,
                SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) as net_balance
            FROM general_ledger
            WHERE account = %s
        """, (acc,))
        
        count, debits, credits, net = cur.fetchone()
        print(f"  {acc}")
        print(f"    Transactions: {count:,}")
        print(f"    Debits:  ${debits:,.2f}")
        print(f"    Credits: ${credits:,.2f}")
        print(f"    Net:     ${net:,.2f}")
        print()
    
    conn.close()
    return payroll_accounts

def sample_2025_gst_summary():
    """Show 2025 GST summary for validation"""
    print("=" * 80)
    print("2025 GST/HST SUMMARY (Jan-Sep)")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # GST Collected
    cur.execute("""
        SELECT 
            SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) as gst_collected
        FROM general_ledger
        WHERE (lower(account) LIKE '%gst%' OR lower(account) LIKE '%hst%')
          AND (lower(account) LIKE '%collect%' OR lower(account) LIKE '%payable%' OR lower(account) LIKE '%charged%')
          AND date BETWEEN '2025-01-01' AND '2025-09-30'
    """)
    gst_collected = cur.fetchone()[0] or Decimal('0')
    
    # ITCs (GST Paid)
    cur.execute("""
        SELECT 
            SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) as itcs
        FROM general_ledger
        WHERE (lower(account) LIKE '%gst%' OR lower(account) LIKE '%hst%')
          AND (lower(account) LIKE '%paid%' OR lower(account) LIKE '%recoverable%' OR lower(account) LIKE '%receivable%' OR lower(account) LIKE '%itc%')
          AND date BETWEEN '2025-01-01' AND '2025-09-30'
    """)
    itcs = cur.fetchone()[0] or Decimal('0')
    
    # Revenue
    cur.execute("""
        SELECT 
            SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) as revenue
        FROM general_ledger
        WHERE (lower(account) LIKE '%revenue%' OR lower(account) LIKE '%sales%' OR lower(account) LIKE '%income%')
          AND lower(account) NOT LIKE '%expense%'
          AND lower(account) NOT LIKE '%cost%'
          AND date BETWEEN '2025-01-01' AND '2025-09-30'
    """)
    revenue = cur.fetchone()[0] or Decimal('0')
    
    print(f"\nJan 1 - Sep 30, 2025:")
    print(f"  Total Revenue/Sales:        ${revenue:,.2f}")
    print(f"  GST/HST Collected:          ${gst_collected:,.2f}")
    print(f"  ITCs (GST Paid/Recoverable): ${itcs:,.2f}")
    print(f"  Net GST/HST Owing:           ${gst_collected - itcs:,.2f}")
    print()
    
    conn.close()

def main():
    print("\nANALYZING ALMSDATA FOR CRA FORM MAPPINGS\n")
    
    gst_accounts = analyze_gst_accounts()
    rev_accounts = analyze_revenue_accounts()
    payroll_accounts = analyze_payroll_tax_accounts()
    sample_2025_gst_summary()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"GST/HST accounts: {len(gst_accounts)}")
    print(f"Revenue accounts: {len(rev_accounts)}")
    print(f"Payroll tax accounts: {len(payroll_accounts)}")
    print()
    print("Use these account names to refine mapping_gst.json and create mapping_pd7a.json")

if __name__ == '__main__':
    main()
