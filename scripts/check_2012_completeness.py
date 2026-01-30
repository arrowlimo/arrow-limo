#!/usr/bin/env python3
"""
Comprehensive 2012 data completeness check.

Analyzes what's missing from 2012 before moving to 2013:
- Banking transactions (CIBC & Scotia)
- Receipts coverage
- Charter/payment data
- Payroll records
- Outstanding balances

Created: November 25, 2025
"""

import psycopg2
import os
from datetime import date

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\n" + "="*80)
print("2012 DATA COMPLETENESS ASSESSMENT")
print("="*80)

# 1. Banking Transactions Coverage
print("\n1. BANKING TRANSACTIONS (2012)")
print("-"*80)

# CIBC 0228362
cur.execute("""
    SELECT 
        COUNT(*) as txn_count,
        COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debits,
        COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credits,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
cibc = cur.fetchone()

print(f"\nCIBC (0228362):")
print(f"  Total transactions: {cibc[0]:,}")
print(f"  Debits: {cibc[1]:,} (${cibc[3]:,.2f})")
print(f"  Credits: {cibc[2]:,} (${cibc[4]:,.2f})")
print(f"  Net: ${cibc[4] - cibc[3]:,.2f}")

# Scotia 903990106011
cur.execute("""
    SELECT 
        COUNT(*) as txn_count,
        COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debits,
        COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credits,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
scotia = cur.fetchone()

print(f"\nScotia (903990106011):")
print(f"  Total transactions: {scotia[0]:,}")
print(f"  Debits: {scotia[1]:,} (${scotia[3]:,.2f})")
print(f"  Credits: {scotia[2]:,} (${scotia[4]:,.2f})")
print(f"  Net: ${scotia[4] - scotia[3]:,.2f}")

print(f"\nCombined 2012 Banking:")
print(f"  Total transactions: {cibc[0] + scotia[0]:,}")
print(f"  Total debits: ${cibc[3] + scotia[3]:,.2f}")
print(f"  Total credits: ${cibc[4] + scotia[4]:,.2f}")

# 2. Receipts Coverage
print("\n\n2. RECEIPTS COVERAGE (2012)")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(*) as receipt_count,
        COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as from_banking,
        COUNT(CASE WHEN created_from_banking = FALSE OR created_from_banking IS NULL THEN 1 END) as manual,
        SUM(gross_amount) as total_gross,
        SUM(gst_amount) as total_gst,
        SUM(net_amount) as total_net
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
""")
receipts = cur.fetchone()

print(f"\nTotal receipts: {receipts[0]:,}")
print(f"  From banking (auto): {receipts[1]:,}")
print(f"  Manual/imported: {receipts[2]:,}")
print(f"  Total gross: ${receipts[3]:,.2f}")
print(f"  Total GST: ${receipts[4]:,.2f}")
print(f"  Total net: ${receipts[5]:,.2f}")

# Receipt-Banking linkage
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
    WHERE EXTRACT(YEAR FROM r.receipt_date) = 2012
""")
linked = cur.fetchone()[0]

print(f"\nReceipt-Banking Linkage:")
print(f"  Receipts linked to banking: {linked:,} ({linked/receipts[0]*100:.1f}%)")
print(f"  Unlinked receipts: {receipts[0] - linked:,}")

# Receipts by category
cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    GROUP BY category
    ORDER BY total DESC
    LIMIT 10
""")
print(f"\nTop 10 Receipt Categories:")
for row in cur.fetchall():
    print(f"  {row[0]:30} {row[1]:5,} receipts  ${row[2]:>12,.2f}")

# 3. Charter/Payment Data
print("\n\n3. CHARTER & PAYMENT DATA (2012)")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(*) as charter_count,
        COUNT(CASE WHEN cancelled = TRUE THEN 1 END) as cancelled,
        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
        SUM(total_amount_due) as total_revenue,
        SUM(paid_amount) as total_paid,
        SUM(balance) as total_balance
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
""")
charters = cur.fetchone()

print(f"\nCharters:")
print(f"  Total: {charters[0]:,}")
print(f"  Cancelled: {charters[1]:,}")
print(f"  Completed: {charters[2]:,}")
print(f"  Total revenue: ${charters[3]:,.2f}")
print(f"  Total paid: ${charters[4]:,.2f}")
print(f"  Outstanding balance: ${charters[5]:,.2f}")

cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
""")
payments = cur.fetchone()

print(f"\nPayments:")
print(f"  Total: {payments[0]:,}")
print(f"  Total amount: ${payments[1]:,.2f}")

# Payment matching
cur.execute("""
    SELECT COUNT(*)
    FROM payments p
    WHERE EXTRACT(YEAR FROM p.payment_date) = 2012
    AND (p.reserve_number IS NULL OR p.reserve_number NOT IN (
        SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL
    ))
""")
unmatched_payments = cur.fetchone()[0]

print(f"  Unmatched to charters: {unmatched_payments:,}")

# 4. Payroll Data
print("\n\n4. PAYROLL DATA (2012)")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(*) as pay_records,
        COUNT(DISTINCT driver_id) as unique_drivers,
        SUM(gross_pay) as total_gross,
        SUM(net_pay) as total_net,
        SUM(cpp + ei + tax) as total_deductions
    FROM driver_payroll
    WHERE year = 2012
    AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
""")
payroll = cur.fetchone()

print(f"\nDriver Payroll:")
print(f"  Pay records: {payroll[0]:,}")
print(f"  Unique drivers: {payroll[1]:,}")
print(f"  Gross pay: ${payroll[2]:,.2f}")
print(f"  Net pay: ${payroll[3]:,.2f}")
print(f"  Total deductions: ${payroll[4]:,.2f}")

# 5. Data Quality Issues
print("\n\n5. DATA QUALITY ISSUES")
print("-"*80)

# Unlinked banking debits
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions bt
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND debit_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = bt.transaction_id
    )
""")
unlinked_debits = cur.fetchone()[0]

print(f"\nUnlinked Banking Debits: {unlinked_debits:,}")
if unlinked_debits > 0:
    print(f"  ⚠️  Banking expenses without receipts")

# Charters with mismatched balances
cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND ABS(balance - (total_amount_due - paid_amount)) > 0.01
""")
balance_issues = cur.fetchone()[0]

print(f"\nCharters with Balance Mismatches: {balance_issues:,}")
if balance_issues > 0:
    print(f"  ⚠️  Charter balance calculations incorrect")

# Receipts without GST
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND gross_amount > 0
    AND (gst_amount IS NULL OR gst_amount = 0)
    AND category NOT IN ('bank_fees', 'general_journal')
""")
no_gst = cur.fetchone()[0]

print(f"\nReceipts without GST: {no_gst:,}")
if no_gst > 0:
    print(f"  ⚠️  Tax calculation may be incomplete")

# 6. Monthly Coverage Gaps
print("\n\n6. MONTHLY COVERAGE GAPS")
print("-"*80)

print(f"\n{'Month':>10} {'Banking':>10} {'Receipts':>10} {'Charters':>10} {'Payments':>10}")
print("-"*60)

for month in range(1, 13):
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM banking_transactions 
             WHERE EXTRACT(YEAR FROM transaction_date) = 2012 
             AND EXTRACT(MONTH FROM transaction_date) = %s),
            (SELECT COUNT(*) FROM receipts 
             WHERE EXTRACT(YEAR FROM receipt_date) = 2012 
             AND EXTRACT(MONTH FROM receipt_date) = %s),
            (SELECT COUNT(*) FROM charters 
             WHERE EXTRACT(YEAR FROM charter_date) = 2012 
             AND EXTRACT(MONTH FROM charter_date) = %s),
            (SELECT COUNT(*) FROM payments 
             WHERE EXTRACT(YEAR FROM payment_date) = 2012 
             AND EXTRACT(MONTH FROM payment_date) = %s)
    """, (month, month, month, month))
    
    m_banking, m_receipts, m_charters, m_payments = cur.fetchone()
    month_name = date(2012, month, 1).strftime('%B')
    
    gaps = []
    if m_banking == 0:
        gaps.append('BANK')
    if m_receipts == 0:
        gaps.append('RCPT')
    if m_charters == 0:
        gaps.append('CHTR')
    if m_payments == 0:
        gaps.append('PYMT')
    
    gap_str = f" ⚠️ {','.join(gaps)}" if gaps else ""
    print(f"{month_name:>10} {m_banking:>10,} {m_receipts:>10,} {m_charters:>10,} {m_payments:>10,}{gap_str}")

# 7. Summary
print("\n\n" + "="*80)
print("SUMMARY: 2012 DATA COMPLETENESS")
print("="*80)

all_good = True

print("\n✓ COMPLETE:")
print(f"  - Banking: {cibc[0] + scotia[0]:,} transactions (${cibc[3] + scotia[3] + cibc[4] + scotia[4]:,.2f})")
print(f"  - Receipts: {receipts[0]:,} receipts (${receipts[3]:,.2f})")
print(f"  - Charters: {charters[0]:,} charters (${charters[3]:,.2f})")
print(f"  - Payments: {payments[0]:,} payments (${payments[1]:,.2f})")
print(f"  - Payroll: {payroll[0]:,} records (${payroll[2]:,.2f})")

if unlinked_debits > 0 or balance_issues > 0 or no_gst > 0 or unmatched_payments > 0:
    print("\n⚠️  ISSUES TO REVIEW:")
    if unlinked_debits > 0:
        print(f"  - {unlinked_debits:,} banking debits without receipts")
    if balance_issues > 0:
        print(f"  - {balance_issues:,} charters with balance calculation errors")
    if no_gst > 0:
        print(f"  - {no_gst:,} receipts without GST calculation")
    if unmatched_payments > 0:
        print(f"  - {unmatched_payments:,} payments not matched to charters")
    all_good = False

if all_good:
    print("\n✓ 2012 DATA IS COMPLETE - READY TO MOVE TO 2013")
else:
    print("\n⚠️  RESOLVE ISSUES ABOVE BEFORE MOVING TO 2013")

print("\n" + "="*80)

cur.close()
conn.close()
