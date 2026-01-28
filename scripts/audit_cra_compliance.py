#!/usr/bin/env python3
"""
Comprehensive charter audit for CRA compliance.
Checks:
1. Payment linkage (all payments linked to charters and banking)
2. Closed flag consistency (all $0 balance charters marked closed)
3. Reconciled status (revenue properly recorded)
4. Pre-2025 uncollectible balances
5. Gratuity integrity (employee payments preserved)
6. Data integrity for CRA audit
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("COMPREHENSIVE CRA AUDIT - CHARTER SYSTEM")
    print("="*80)
    print(f"Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. PAYMENT LINKAGE AUDIT
    print("\n" + "="*80)
    print("1. PAYMENT LINKAGE AUDIT")
    print("="*80)
    
    # Payments not linked to charters
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE reserve_number IS NULL
    """)
    unlinked_count, unlinked_amount = cur.fetchone()
    
    print(f"\nPayments NOT linked to charters:")
    print(f"  Count: {unlinked_count:,}")
    print(f"  Amount: ${unlinked_amount:,.2f}")
    print(f"  Status: {'✓ PASS' if unlinked_count == 0 else '[WARN] NEEDS REVIEW'}")
    
    # Payments not linked to banking
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(p.amount), 0)
        FROM payments p
        LEFT JOIN banking_payment_links bpl ON p.payment_id = bpl.payment_id
        WHERE bpl.payment_id IS NULL
        AND p.payment_method IN ('bank_transfer', 'check')
    """)
    no_banking_count, no_banking_amount = cur.fetchone()
    
    print(f"\nBank payments NOT linked to banking_transactions:")
    print(f"  Count: {no_banking_count:,}")
    print(f"  Amount: ${no_banking_amount:,.2f}")
    print(f"  Status: {'✓ PASS' if no_banking_count < 100 else '[WARN] NEEDS REVIEW'}")
    
    # Payments not in income_ledger
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(p.amount), 0)
        FROM payments p
        LEFT JOIN income_ledger il ON p.payment_id = il.payment_id
        WHERE il.payment_id IS NULL
        AND p.charter_id IS NOT NULL
    """)
    no_ledger_count, no_ledger_amount = cur.fetchone()
    
    print(f"\nPayments NOT in income_ledger:")
    print(f"  Count: {no_ledger_count:,}")
    print(f"  Amount: ${no_ledger_amount:,.2f}")
    print(f"  Status: {'✓ PASS' if no_ledger_count < 100 else '[WARN] NEEDS REVIEW'}")
    
    # 2. CLOSED FLAG CONSISTENCY
    print("\n" + "="*80)
    print("2. CLOSED FLAG CONSISTENCY AUDIT")
    print("="*80)
    
    # $0 balance but not closed
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE COALESCE(balance, 0) = 0
        AND COALESCE(closed, FALSE) = FALSE
        AND COALESCE(cancelled, FALSE) = FALSE
    """)
    not_closed_count = cur.fetchone()[0]
    
    print(f"\n$0 balance charters NOT marked closed:")
    print(f"  Count: {not_closed_count:,}")
    print(f"  Status: {'✓ PASS' if not_closed_count == 0 else '[FAIL] FAIL - NEEDS FIX'}")
    
    # Closed but has balance
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(ABS(balance)), 0)
        FROM charters
        WHERE closed = TRUE
        AND balance != 0
        AND cancelled = FALSE
    """)
    closed_with_balance_count, closed_balance_amount = cur.fetchone()
    
    print(f"\nClosed charters with non-zero balance:")
    print(f"  Count: {closed_with_balance_count:,}")
    print(f"  Amount: ${closed_balance_amount:,.2f}")
    print(f"  Status: {'✓ PASS' if closed_with_balance_count == 0 else '[WARN] NEEDS REVIEW'}")
    
    # 3. RECONCILIATION STATUS
    print("\n" + "="*80)
    print("3. REVENUE RECONCILIATION AUDIT")
    print("="*80)
    
    # Total charter revenue
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            COALESCE(SUM(total_amount_due), 0) as total_revenue,
            COALESCE(SUM(paid_amount), 0) as total_paid,
            COALESCE(SUM(balance), 0) as total_outstanding
        FROM charters
        WHERE cancelled = FALSE
        AND charter_date < '2025-11-12'
    """)
    
    charter_count, total_revenue, total_paid, total_outstanding = cur.fetchone()
    
    print(f"\nRevenue Summary (all time through Nov 11, 2025):")
    print(f"  Total charters: {charter_count:,}")
    print(f"  Total revenue (charges): ${total_revenue:,.2f}")
    print(f"  Total collected: ${total_paid:,.2f}")
    print(f"  Total outstanding: ${total_outstanding:,.2f}")
    print(f"  Collection rate: {(total_paid/total_revenue*100) if total_revenue > 0 else 0:.1f}%")
    
    # Income ledger reconciliation
    cur.execute("""
        SELECT COALESCE(SUM(gross_amount), 0)
        FROM income_ledger
        WHERE transaction_date < '2025-11-12'
    """)
    ledger_total = cur.fetchone()[0]
    
    print(f"\nIncome Ledger Total: ${ledger_total:,.2f}")
    print(f"  Difference from paid_amount: ${abs(total_paid - ledger_total):,.2f}")
    print(f"  Status: {'✓ PASS' if abs(total_paid - ledger_total) < 1000 else '[WARN] NEEDS REVIEW'}")
    
    # 4. PRE-2025 UNCOLLECTIBLE BALANCES
    print("\n" + "="*80)
    print("4. PRE-2025 UNCOLLECTIBLE BALANCES AUDIT")
    print("="*80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            COALESCE(SUM(balance), 0) as total_owing
        FROM charters
        WHERE charter_date < '2025-01-01'
        AND balance > 0
        AND cancelled = FALSE
        AND closed = FALSE
    """)
    
    old_owing_count, old_owing_amount = cur.fetchone()
    
    print(f"\nPre-2025 charters with balances owing:")
    print(f"  Count: {old_owing_count:,}")
    print(f"  Amount: ${old_owing_amount:,.2f}")
    
    # Breakdown by age
    cur.execute("""
        SELECT 
            CASE 
                WHEN EXTRACT(YEAR FROM charter_date) <= 2015 THEN '2007-2015 (10+ years)'
                WHEN EXTRACT(YEAR FROM charter_date) <= 2020 THEN '2016-2020 (5-9 years)'
                WHEN EXTRACT(YEAR FROM charter_date) <= 2022 THEN '2021-2022 (3-4 years)'
                ELSE '2023-2024 (1-2 years)'
            END as age_group,
            COUNT(*) as count,
            COALESCE(SUM(balance), 0) as total
        FROM charters
        WHERE charter_date < '2025-01-01'
        AND balance > 0
        AND cancelled = FALSE
        AND closed = FALSE
        GROUP BY age_group
        ORDER BY MIN(charter_date)
    """)
    
    print(f"\n  Aging breakdown:")
    for row in cur.fetchall():
        age_group, count, total = row
        print(f"    {age_group}: {count:,} charters, ${total:,.2f}")
    
    # Likely uncollectible (5+ years old, small balances)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(balance), 0)
        FROM charters
        WHERE charter_date < '2020-01-01'
        AND balance > 0
        AND balance < 500
        AND cancelled = FALSE
        AND closed = FALSE
    """)
    uncollectible_count, uncollectible_amount = cur.fetchone()
    
    print(f"\n  Likely uncollectible (5+ years, <$500):")
    print(f"    Count: {uncollectible_count:,}")
    print(f"    Amount: ${uncollectible_amount:,.2f}")
    print(f"    Recommendation: Write off for CRA bad debt deduction")
    
    # 5. GRATUITY INTEGRITY
    print("\n" + "="*80)
    print("5. GRATUITY/DRIVER PAY INTEGRITY AUDIT")
    print("="*80)
    
    # Check driver_payroll linkage
    cur.execute("""
        SELECT 
            COUNT(*) as payroll_records,
            COALESCE(SUM(gross_pay), 0) as total_gross
        FROM driver_payroll
        WHERE year <= 2024
    """)
    
    payroll_count, total_gross = cur.fetchone()
    
    print(f"\nDriver Payroll Summary (through 2024):")
    print(f"  Payroll records: {payroll_count:,}")
    print(f"  Total gross pay: ${total_gross:,.2f}")
    
    # Check for charters with driver pay but no payroll record
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE COALESCE(driver_total, 0) > 0
        AND charter_date < '2025-01-01'
        AND charter_id NOT IN (
            SELECT DISTINCT charter_id::integer
            FROM driver_payroll 
            WHERE reserve_number IS NOT NULL
            AND charter_id ~ '^[0-9]+$'
        )
    """)
    missing_payroll = cur.fetchone()[0]
    
    print(f"\nCharters with driver pay but no payroll record:")
    print(f"  Count: {missing_payroll:,}")
    print(f"  Status: {'✓ PASS' if missing_payroll < 100 else '[WARN] NEEDS REVIEW'}")
    
    # 6. CANCELLED CHARTERS INTEGRITY
    print("\n" + "="*80)
    print("6. CANCELLED CHARTERS INTEGRITY")
    print("="*80)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE cancelled = TRUE
        AND total_amount_due != 0
    """)
    cancelled_with_charges = cur.fetchone()[0]
    
    print(f"\nCancelled charters with charges:")
    print(f"  Count: {cancelled_with_charges:,}")
    print(f"  Status: {'✓ PASS' if cancelled_with_charges == 0 else '[FAIL] FAIL - NEEDS FIX'}")
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(paid_amount), 0)
        FROM charters
        WHERE cancelled = TRUE
        AND paid_amount != 0
    """)
    cancelled_with_payments = cur.fetchone()
    cancelled_payment_count, cancelled_payment_amount = cancelled_with_payments
    
    print(f"\nCancelled charters with payments (non-refundable deposits):")
    print(f"  Count: {cancelled_payment_count:,}")
    print(f"  Amount: ${cancelled_payment_amount:,.2f}")
    print(f"  Status: {'✓ ACCEPTABLE' if cancelled_payment_amount > 0 else '✓ PASS'}")
    
    # 7. NEGATIVE BALANCES (CREDITS)
    print("\n" + "="*80)
    print("7. NEGATIVE BALANCES (OVERPAYMENTS/CREDITS)")
    print("="*80)
    
    cur.execute("""
        SELECT 
            COUNT(*),
            COALESCE(SUM(ABS(balance)), 0),
            COALESCE(SUM(CASE WHEN charter_date >= '2025-01-01' THEN ABS(balance) ELSE 0 END), 0) as current_year,
            COALESCE(SUM(CASE WHEN charter_date < '2025-01-01' THEN ABS(balance) ELSE 0 END), 0) as prior_years
        FROM charters
        WHERE balance < 0
        AND cancelled = FALSE
    """)
    
    credit_count, total_credits, current_credits, prior_credits = cur.fetchone()
    
    print(f"\nCharters with negative balances (credits):")
    print(f"  Total count: {credit_count:,}")
    print(f"  Total credits: ${total_credits:,.2f}")
    print(f"  2025 credits: ${current_credits:,.2f}")
    print(f"  Pre-2025 credits: ${prior_credits:,.2f}")
    print(f"  Status: {'[WARN] NEEDS REVIEW' if credit_count > 100 else '✓ ACCEPTABLE'}")
    
    # 8. OVERALL CRA COMPLIANCE SUMMARY
    print("\n" + "="*80)
    print("8. CRA COMPLIANCE SUMMARY")
    print("="*80)
    
    issues = []
    warnings = []
    
    if unlinked_count > 0:
        warnings.append(f"{unlinked_count:,} payments not linked to charters (${unlinked_amount:,.2f})")
    
    if not_closed_count > 0:
        issues.append(f"{not_closed_count:,} charters with $0 balance not marked closed")
    
    if cancelled_with_charges > 0:
        issues.append(f"{cancelled_with_charges:,} cancelled charters still have charges")
    
    if uncollectible_count > 0:
        warnings.append(f"{uncollectible_count:,} likely uncollectible balances (${uncollectible_amount:,.2f})")
    
    if credit_count > 100:
        warnings.append(f"{credit_count:,} charters with credits (${total_credits:,.2f})")
    
    print(f"\nCRITICAL ISSUES (Must Fix):")
    if issues:
        for issue in issues:
            print(f"  [FAIL] {issue}")
    else:
        print(f"  ✓ No critical issues found")
    
    print(f"\nWARNINGS (Should Review):")
    if warnings:
        for warning in warnings:
            print(f"  [WARN]  {warning}")
    else:
        print(f"  ✓ No warnings")
    
    print(f"\nOVERALL STATUS:")
    if len(issues) == 0:
        print(f"  ✓ READY FOR CRA AUDIT")
    else:
        print(f"  [FAIL] NEEDS CORRECTIONS BEFORE CRA AUDIT")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
