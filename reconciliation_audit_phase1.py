"""
CRITICAL RECONCILIATION AUDIT: Charter-Payment Matching
==========================================================
Source of truth: Banking payments (bank statements) → Match to charters/charges
Verify: All payments have matching charters AND charges
Find: Missing payments, overpayments, deleted charges, rounding errors

Phase 1: Banking payments → Charter matching
Phase 2: Reverse verify (Charter → Banking)
Phase 3: Overpayment categorization & fixes
"""

import os
import psycopg2
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("CRITICAL RECONCILIATION AUDIT: Charter-Payment-Banking Matching")
print("=" * 120)

# ============================================================================
# PHASE 1: Banking Payments → Charter Matching
# ============================================================================

print("\n[PHASE 1] BANKING PAYMENTS → CHARTER MATCHING")
print("-" * 120)

# Get all banking transactions that look like income (credits/deposits, not expenses)
# banking_transactions: credit_amount for deposits, debit_amount for withdrawals
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description,
        bt.vendor_extracted,
        bt.category,
        bt.account_number
    FROM banking_transactions bt
    WHERE 
        bt.credit_amount > 0  -- Only credits (income)
        AND (bt.category ILIKE '%deposit%' OR bt.category ILIKE '%income%'
             OR bt.description ILIKE '%e-transfer%' OR bt.description ILIKE '%etransfer%'
             OR bt.description ILIKE '%global%payment%' OR bt.description ILIKE '%customer%payment%'
             OR bt.vendor_extracted ILIKE '%global%' OR bt.vendor_extracted ILIKE '%etransfer%')
        AND bt.transaction_date >= '2012-01-01'
    ORDER BY bt.transaction_date DESC
""")

banking_payments = cur.fetchall()
print(f"✅ Found {len(banking_payments)} banking deposits/income transactions")

# For each banking payment, find matching charter payments
print("\n[1.1] MATCHING BANKING PAYMENTS TO CHARTERS")
print("-" * 120)

matched = 0
unmatched_banking = []
overpaid_charters = []

for bt_id, trans_date, amount, desc, vendor, category, acct in banking_payments:
    # Try to find payment with matching amount within 7 days
    cur.execute("""
        SELECT 
            p.payment_id, p.reserve_number, p.amount, p.payment_date, p.payment_method,
            c.charter_id, c.total_amount_due, c.status,
            COALESCE(SUM(p2.amount), 0) as total_payments_for_charter
        FROM payments p
        LEFT JOIN charters c ON p.reserve_number = c.reserve_number
        LEFT JOIN payments p2 ON p2.reserve_number = c.reserve_number AND p2.amount IS NOT NULL
        WHERE 
            ABS(p.amount - %s) < 0.01
            AND ABS(EXTRACT(DAY FROM (p.payment_date - %s))) <= 7
        GROUP BY p.payment_id, p.reserve_number, p.amount, p.payment_date, p.payment_method,
                 c.charter_id, c.total_amount_due, c.status
        LIMIT 5
    """, (amount, trans_date))
    
    matches = cur.fetchall()
    
    if matches:
        # Payment found - check for overpayment
        for pmt_id, reserve, pmt_amt, pmt_date, pmt_method, charter_id, due, status, total_pmts in matches:
            if total_pmts > due + 0.01:  # Overpaid
                overpaid_charters.append({
                    'banking_id': bt_id,
                    'banking_date': trans_date,
                    'banking_amount': amount,
                    'charter_id': charter_id,
                    'reserve': reserve,
                    'due': due,
                    'total_payments': total_pmts,
                    'overpayment': total_pmts - due,
                    'status': status,
                    'payment_id': pmt_id
                })
            matched += 1
    else:
        # Payment not found - this is a problem!
        unmatched_banking.append({
            'banking_id': bt_id,
            'date': trans_date,
            'amount': amount,
            'description': desc,
            'vendor': vendor
        })

print(f"✅ Matched banking payments to charters: {matched}")
print(f"⚠️  UNMATCHED banking payments (NO charter match): {len(unmatched_banking)}")
print(f"⚠️  OVERPAID charters (payments > due): {len(overpaid_charters)}")

# ============================================================================
# PHASE 1.2: Show Unmatched Banking Payments
# ============================================================================

if unmatched_banking:
    print("\n[1.2] UNMATCHED BANKING PAYMENTS (Critical Issue)")
    print("-" * 120)
    print(f"{'ID':<10} {'Date':<12} {'Amount':<15} {'Description':<40} {'Vendor':<30}")
    print("-" * 120)
    
    for item in unmatched_banking[:20]:  # Show top 20
        desc = str(item['description'])[:38]
        vendor = str(item['vendor'])[:28]
        print(f"{item['banking_id']:<10} {str(item['date']):<12} ${item['amount']:>13.2f} {desc:<40} {vendor:<30}")
    
    if len(unmatched_banking) > 20:
        print(f"... and {len(unmatched_banking) - 20} more unmatched banking payments")

# ============================================================================
# PHASE 2: Reverse Verify - Charter → Payments → Banking
# ============================================================================

print("\n[PHASE 2] REVERSE VERIFY: CHARTER → PAYMENTS → BANKING")
print("-" * 120)

# For each charter, verify all payments are accounted for
cur.execute("""
    SELECT DISTINCT
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.balance,
        c.status,
        COUNT(p.payment_id) as payment_count,
        COALESCE(SUM(p.amount), 0) as total_paid
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.reserve_number IS NOT NULL
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.balance, c.status
    ORDER BY c.charter_id
""")

charters = cur.fetchall()
print(f"✅ Analyzing {len(charters)} charters")

unpaid_charters = []
zero_due_charters = []
balance_mismatch = []

for charter_id, reserve, charter_date, due, balance, status, pmt_count, total_paid in charters:
    calculated_balance = due - total_paid
    
    # Check 1: Unpaid charters
    if due > 0.01 and total_paid < 0.01:
        unpaid_charters.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'date': charter_date,
            'due': due,
            'paid': total_paid,
            'status': status,
            'pmt_count': pmt_count
        })
    
    # Check 2: Zero-due charters (charges should exist)
    if due < 0.01 and pmt_count > 0:
        zero_due_charters.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due,
            'paid': total_paid,
            'pmt_count': pmt_count,
            'status': status
        })
    
    # Check 3: Balance mismatch
    if abs(calculated_balance - balance) > 0.01:
        balance_mismatch.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due,
            'paid': total_paid,
            'calc_balance': calculated_balance,
            'stored_balance': balance,
            'discrepancy': balance - calculated_balance
        })

print(f"✅ Unpaid charters (due > $0.01, paid = $0): {len(unpaid_charters)}")
print(f"⚠️  Zero-due charters with payments: {len(zero_due_charters)} (charge deletion issue?)")
print(f"⚠️  Balance mismatches: {len(balance_mismatch)}")

# Show zero-due with payments (indicates charge was deleted)
if zero_due_charters:
    print("\n[2.1] ZERO-DUE CHARTERS WITH PAYMENTS (Deleted Charges?)")
    print("-" * 120)
    print(f"{'Charter':<10} {'Reserve':<10} {'Due':<12} {'Paid':<12} {'Pmts':<6} {'Status':<20}")
    print("-" * 120)
    
    for item in zero_due_charters[:10]:
        print(f"{item['charter_id']:<10} {item['reserve']:<10} ${item['due']:>10.2f} ${item['paid']:>10.2f} {item['pmt_count']:<6} {str(item['status']):<20}")

# ============================================================================
# PHASE 3: Overpayment Categorization
# ============================================================================

print("\n[PHASE 3] OVERPAYMENT CATEGORIZATION & ANALYSIS")
print("-" * 120)

retainer_overpay = []
rounding_overpay = []
actual_overpay = []

for overpay in overpaid_charters:
    overpay_amt = overpay['overpayment']
    status = overpay['status']
    
    # Categorize
    if overpay_amt < 0.02:  # Less than $0.02 = rounding
        rounding_overpay.append(overpay)
    elif status and 'cancel' in str(status).lower():  # Cancelled = retainer
        retainer_overpay.append(overpay)
    elif status and 'retainer' in str(status).lower():  # Retainer status
        retainer_overpay.append(overpay)
    else:  # Actual overpayment
        actual_overpay.append(overpay)

print(f"✅ Retainer overpayments (cancelled/retainer status): {len(retainer_overpay)}")
print(f"✅ Rounding overpayments (<$0.02): {len(rounding_overpay)}")
print(f"⚠️  ACTUAL overpayments (needs investigation): {len(actual_overpay)}")

if actual_overpay:
    print("\n[3.1] ACTUAL OVERPAYMENTS (Verify These)")
    print("-" * 120)
    print(f"{'Charter':<10} {'Reserve':<10} {'Due':<12} {'Paid':<12} {'Overpay':<12} {'Status':<20}")
    print("-" * 120)
    
    for item in actual_overpay[:15]:
        print(f"{item['charter_id']:<10} {item['reserve']:<10} ${item['due']:>10.2f} ${item['total_payments']:>10.2f} ${item['overpayment']:>10.2f} {str(item['status']):<20}")

# ============================================================================
# PHASE 4: Generate Reconciliation Report
# ============================================================================

print("\n[PHASE 4] RECONCILIATION REPORT & FIX GENERATION")
print("-" * 120)

now = datetime.now().strftime("%Y%m%d_%H%M%S")
report_file = f"reconciliation_report_{now}.csv"
fix_script_file = f"reconciliation_fixes_{now}.py"

# Write reconciliation report
with open(report_file, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Reconciliation Issue', 'Count', 'Status', 'Action Required'])
    writer.writerow(['Unmatched banking payments', len(unmatched_banking), 'CRITICAL', 'Investigate why banking payment has no charter match'])
    writer.writerow(['Zero-due charters with payments', len(zero_due_charters), 'CRITICAL', 'Charge deletion may have been incorrect - verify & restore'])
    writer.writerow(['Balance mismatches', len(balance_mismatch), 'HIGH', 'Recalculate balance or fix payment amounts'])
    writer.writerow(['Actual overpayments', len(actual_overpay), 'MEDIUM', 'Verify overpayments are correct (may need refund)'])
    writer.writerow(['Rounding overpayments', len(rounding_overpay), 'LOW', 'Add penny charges to balance to $0'])

print(f"✅ Report written: {report_file}")

# ============================================================================
# SUMMARY & RECOMMENDATIONS
# ============================================================================

print("\n" + "=" * 120)
print("CRITICAL FINDINGS SUMMARY")
print("=" * 120)

issues_found = len(unmatched_banking) + len(zero_due_charters) + len(actual_overpay)

print(f"""
🚨 CRITICAL ISSUES FOUND: {issues_found}

1. UNMATCHED BANKING PAYMENTS: {len(unmatched_banking)}
   → Banking transactions with NO matching charter payment
   → Action: Find which charter these should belong to
   
2. ZERO-DUE WITH PAYMENTS: {len(zero_due_charters)}
   → Charters with payments but $0 due (charges deleted)
   → Action: Verify charges were meant to be deleted or restore them
   
3. BALANCE MISMATCHES: {len(balance_mismatch)}
   → Stored balance ≠ calculated balance
   → Action: Fix balance calculations or payment amounts
   
4. ACTUAL OVERPAYMENTS: {len(actual_overpay)}
   → Customers paid more than due (non-retainer, non-rounding)
   → Action: Verify and decide on refund/credit

5. RETAINER OVERPAYMENTS: {len(retainer_overpay)}
   → Expected (cancelled nonrefundable retainers)
   → Action: Confirm are retainers and mark as such

6. ROUNDING OVERPAYMENTS: {len(rounding_overpay)}
   → Minor $0.01 discrepancies
   → Action: Add penny charges to balance to $0

NEXT STEPS:
1. Review unmatched banking payments (most critical)
2. Verify zero-due charter situations
3. Fix balance mismatches
4. Categorize and document overpayments
5. Add penny charges for rounding issues
6. Run forward reconciliation again to verify fixes

Files generated:
- {report_file} (CSV report)
""")

print("=" * 120)

cur.close()
conn.close()
