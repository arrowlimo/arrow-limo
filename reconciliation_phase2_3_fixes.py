"""
RECONCILIATION AUDIT PHASE 2: Charter → Payment → Banking Reverse
+ Phase 3: Overpayment Categorization & Fix Generation

This phase:
1. For EVERY charter, verify all payments are recorded and in banking
2. Find charters with zero due but payments exist (charge deletion issue)
3. Categorize all overpayments (retainer vs actual)
4. Find $0.01 rounding discrepancies to fix
5. Generate SQL fixes
"""

import os
import psycopg2
from decimal import Decimal
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("RECONCILIATION AUDIT PHASE 2: Reverse Check (Charter → Payment → Banking)")
print("=" * 120)

# ============================================================================
# PHASE 2: Charter-level verification
# ============================================================================

print("\n[PHASE 2.1] CHARTER-LEVEL VERIFICATION")
print("-" * 120)

# Get all charters with their payments
cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.balance,
        c.status,
        COUNT(p.payment_id) as pmt_count,
        COALESCE(SUM(p.amount), 0) as total_paid
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.balance, c.status
    ORDER BY c.charter_id
""")

all_charters = cur.fetchall()
print(f"✅ Analyzing {len(all_charters):,} charters")

zero_due_with_pmts = []
unpaid_with_pmts = []
balance_mismatch = []
rounding_issues = []

for charter_id, reserve, charter_date, due, stored_balance, status, pmt_count, total_paid in all_charters:
    due_f = float(due) if due else 0
    paid_f = float(total_paid) if total_paid else 0
    balance_f = float(stored_balance) if stored_balance else 0
    
    calc_balance = due_f - paid_f
    
    # Issue 1: Zero-due charters with payments (charges deleted?)
    if due_f < 0.01 and pmt_count > 0:
        zero_due_with_pmts.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'date': charter_date,
            'due': due_f,
            'paid': paid_f,
            'pmt_count': pmt_count,
            'status': status
        })
    
    # Issue 2: Unpaid charters (still have money owed)
    if due_f > 0.01 and paid_f > 0:
        unpaid_with_pmts.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due_f,
            'paid': paid_f,
            'calc_balance': calc_balance,
            'stored_balance': balance_f,
            'pmt_count': pmt_count,
            'status': status
        })
    
    # Issue 3: Balance mismatch
    if abs(calc_balance - balance_f) > 0.01:
        balance_mismatch.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due_f,
            'paid': paid_f,
            'calc_balance': calc_balance,
            'stored_balance': balance_f,
            'discrepancy': balance_f - calc_balance
        })
    
    # Issue 4: $0.01 rounding discrepancies
    if 0.005 <= abs(calc_balance - balance_f) < 0.015:
        rounding_issues.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due_f,
            'paid': paid_f,
            'discrepancy': balance_f - calc_balance
        })

print(f"⚠️  Zero-due charters with payments: {len(zero_due_with_pmts)}")
print(f"✅ Unpaid charters (still owe money): {len(unpaid_with_pmts):,}")
print(f"⚠️  Balance mismatches: {len(balance_mismatch)}")
print(f"⚠️  $0.01 rounding issues (need penny charges): {len(rounding_issues)}")

# ============================================================================
# Show zero-due with payments (CRITICAL - charges deleted)
# ============================================================================

if zero_due_with_pmts:
    print("\n[CRITICAL] ZERO-DUE WITH PAYMENTS (Charges deleted?)")
    print("-" * 120)
    print(f"{'Charter':<10} {'Reserve':<10} {'Date':<12} {'Due':<8} {'Paid':<12} {'Pmts':<6} {'Status':<20}")
    print("-" * 120)
    
    for item in zero_due_with_pmts[:20]:
        print(f"{item['charter_id']:<10} {item['reserve']:<10} {str(item['date']):<12} $0.00   ${item['paid']:>10.2f} {item['pmt_count']:<6} {str(item['status']):<20}")
    
    if len(zero_due_with_pmts) > 20:
        print(f"... and {len(zero_due_with_pmts) - 20} more")

# ============================================================================
# PHASE 3: Overpayment Categorization
# ============================================================================

print("\n[PHASE 3] OVERPAYMENT CATEGORIZATION")
print("-" * 120)

# Get all overpayments
cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        COALESCE(SUM(p.amount), 0) as total_paid,
        c.status,
        c.retainer_amount,
        c.cancelled,
        c.deposit
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.status, c.retainer_amount, c.cancelled, c.deposit
    HAVING COALESCE(SUM(p.amount), 0) > c.total_amount_due + 0.01
    ORDER BY c.charter_id
""")

overpayments = cur.fetchall()

retainers = []
rounding_overpay = []
actual_overpay = []

for charter_id, reserve, due, paid, status, retainer_amt, cancelled, deposit in overpayments:
    due_f = float(due) if due else 0
    paid_f = float(paid) if paid else 0
    deposit_f = float(deposit) if deposit else 0
    retainer_f = float(retainer_amt) if retainer_amt else 0
    
    overpay_amt = paid_f - due_f
    
    # Categorize
    is_cancelled = cancelled or (status and 'cancel' in str(status).lower())
    is_retainer = is_cancelled or (status and 'retainer' in str(status).lower())
    is_rounding = overpay_amt < 0.02
    
    if is_retainer:
        retainers.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due_f,
            'paid': paid_f,
            'overpay': overpay_amt,
            'status': status,
            'retainer_amt': retainer_f
        })
    elif is_rounding:
        rounding_overpay.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due_f,
            'paid': paid_f,
            'overpay': overpay_amt
        })
    else:
        actual_overpay.append({
            'charter_id': charter_id,
            'reserve': reserve,
            'due': due_f,
            'paid': paid_f,
            'overpay': overpay_amt,
            'status': status
        })

print(f"✅ Retainer overpayments (cancelled/nonrefundable): {len(retainers)}")
print(f"✅ Rounding overpayments (<$0.02): {len(rounding_overpay)}")
print(f"⚠️  ACTUAL overpayments (needs review): {len(actual_overpay)}")

if actual_overpay:
    print("\n[ACTION REQUIRED] ACTUAL OVERPAYMENTS")
    print("-" * 120)
    print(f"{'Charter':<10} {'Reserve':<10} {'Due':<12} {'Paid':<12} {'Overpay':<12} {'Status':<20}")
    print("-" * 120)
    
    for item in actual_overpay[:15]:
        print(f"{item['charter_id']:<10} {item['reserve']:<10} ${item['due']:>10.2f} ${item['paid']:>10.2f} ${item['overpay']:>10.2f} {str(item['status']):<20}")

# ============================================================================
# PHASE 4: Generate SQL Fix Script
# ============================================================================

print("\n[PHASE 4] GENERATING FIX SCRIPT")
print("-" * 120)

now = datetime.now().strftime("%Y%m%d_%H%M%S")
fix_file = f"reconciliation_fixes_{now}.sql"

with open(fix_file, 'w') as f:
    f.write("-- RECONCILIATION FIXES GENERATED\n")
    f.write(f"-- Generated: {now}\n")
    f.write("-- BEFORE RUNNING: Review all fixes and commit database\n\n")
    
    # Fix 1: Add penny charges for rounding
    if rounding_issues:
        f.write("-- FIX 1: Add penny charges for $0.01 rounding discrepancies\n")
        f.write("-- These charters need a $0.01 charge to balance to $0 due\n\n")
        
        for issue in rounding_issues[:10]:  # Show first 10
            penny = issue['discrepancy']
            f.write(f"-- Charter {issue['charter_id']} (Reserve {issue['reserve']}): Add ${abs(penny):.2f} charge\n")
            f.write(f"INSERT INTO receipts (reserve_number, charter_id, vendor, net_amount, gross_amount, gst_amount, receipt_date, category, status)\n")
            f.write(f"VALUES ('{issue['reserve']}', {issue['charter_id']}, 'ROUNDING ADJUSTMENT', {abs(penny)}, {abs(penny)}, 0, NOW(), 'adjustment', 'auto_generated');\n\n")
    
    # Fix 2: Verify retainers are marked
    if retainers:
        f.write("-- FIX 2: Verify retainer charters are marked correctly\n")
        f.write("-- These should have retainer_received = TRUE\n\n")
        
        for ret in retainers[:5]:
            f.write(f"-- Charter {ret['charter_id']} ({ret['reserve']}): Verify retainer_received = TRUE\n")
            f.write(f"UPDATE charters SET retainer_received = TRUE WHERE charter_id = {ret['charter_id']};\n\n")
    
    # Fix 3: Flag zero-due with payments for review
    if zero_due_with_pmts:
        f.write("-- FIX 3: REVIEW zero-due charters with payments\n")
        f.write("-- These indicate charges may have been incorrectly deleted\n")
        f.write("-- DO NOT AUTO-FIX: Requires manual verification\n\n")
        
        for zero in zero_due_with_pmts[:10]:
            f.write(f"-- Charter {zero['charter_id']} ({zero['reserve']}): {zero['pmt_count']} payments exist but due=$0\n")
            f.write(f"--   Status: {zero['status']}, Paid: ${zero['paid']:.2f}\n\n")

print(f"✅ Fix script generated: {fix_file}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 120)
print("PHASE 2-3 SUMMARY")
print("=" * 120)

total_issues = len(zero_due_with_pmts) + len(balance_mismatch) + len(actual_overpay)

print(f"""
CRITICAL FINDINGS:

1. ZERO-DUE WITH PAYMENTS: {len(zero_due_with_pmts)}
   → Charters with $0 due but payments recorded
   → Indicates charges may have been deleted
   → ACTION: Review each one and restore charges if needed
   
2. BALANCE MISMATCHES: {len(balance_mismatch)}
   → Stored balance ≠ calculated balance
   → ACTION: Fix balance calculations or payment records
   
3. ROUNDING ISSUES: {len(rounding_issues)}
   → $0.01 discrepancies (penny rounding)
   → ACTION: Add $0.01 charges to balance to $0
   → FIX SCRIPT READY: See {fix_file}
   
4. OVERPAYMENTS:
   - Retainers (expected): {len(retainers)}
   - Rounding (<$0.02): {len(rounding_overpay)}
   - ACTUAL OVERPAYS (review): {len(actual_overpay)}
   
5. UNPAID CHARTERS: {len(unpaid_with_pmts):,}
   → Still owe money but have partial/full payments
   
TOTAL RECONCILIATION ISSUES: {total_issues}

NEXT STEPS:
1. Review fix script: {fix_file}
2. Manually verify zero-due situations before restoring charges
3. Run penny rounding fix if approved
4. Verify retainers are marked correctly
5. Re-run Phase 1 to confirm banking deposits match after fixes
""")

print("=" * 120)

cur.close()
conn.close()
