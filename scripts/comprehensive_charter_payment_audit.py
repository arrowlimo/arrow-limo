#!/usr/bin/env python3
"""
COMPREHENSIVE CHARTER-PAYMENT AUDIT
===================================

Audits every charter to verify:
1. Payment matching is legitimate (reserve_number or charter_id linkage)
2. Total payments match expected total (charges + GST + beverages + extras - discounts - reimbursements)
3. Multi-charter payments are properly allocated
4. All charge components are accounted for
5. Balance calculations are correct

Outputs:
- Summary statistics
- Issue categories with counts
- Detailed CSV reports for each issue type
"""
import os
import sys
import csv
import psycopg2
from decimal import Decimal
from collections import defaultdict

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("="*120)
print("COMPREHENSIVE CHARTER-PAYMENT AUDIT")
print("="*120)
print()

# ============================================================================
# STEP 1: Charter-Payment Linkage Validation
# ============================================================================
print("STEP 1: Validating Payment Linkage...")

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        COUNT(DISTINCT p.payment_id) as payment_count,
        COUNT(DISTINCT p.reserve_number) as via_reserve
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.cancelled = FALSE
    GROUP BY c.charter_id, c.reserve_number, c.charter_date
    HAVING COUNT(DISTINCT p.payment_id) > 0
""")

linkage_results = cur.fetchall()
total_with_payments = len(linkage_results)

# All payments should be via reserve_number (business key)
linkage_issues = []
for row in linkage_results:
    charter_id, reserve, cdate, pcount, via_reserve = row
    # All payments should match via reserve_number
    if via_reserve == 0:
        linkage_issues.append((reserve, charter_id, 'no_reserve_match', pcount))

print(f"  Total charters with payments: {total_with_payments:,}")
print(f"  Linkage issues found: {len(linkage_issues):,}")
if linkage_issues:
    print("    - No reserve_number match:", len(linkage_issues))

# ============================================================================
# STEP 2: Charge Component Verification
# ============================================================================
print("\nSTEP 2: Verifying Charge Components...")

cur.execute("""
    WITH charge_breakdown AS (
        SELECT 
            charter_id,
            SUM(CASE WHEN LOWER(description) LIKE '%gst%' OR LOWER(description) LIKE '%tax%' THEN amount ELSE 0 END) as gst_charges,
            SUM(CASE WHEN LOWER(description) LIKE '%beverage%' OR LOWER(description) LIKE '%drink%' THEN amount ELSE 0 END) as beverage_charges,
            SUM(CASE WHEN LOWER(description) LIKE '%fuel%' OR LOWER(description) LIKE '%surcharge%' THEN amount ELSE 0 END) as fuel_charges,
            SUM(CASE WHEN LOWER(description) LIKE '%discount%' OR amount < 0 THEN amount ELSE 0 END) as discounts,
            SUM(CASE WHEN LOWER(description) NOT LIKE '%gst%' 
                     AND LOWER(description) NOT LIKE '%tax%'
                     AND LOWER(description) NOT LIKE '%beverage%'
                     AND LOWER(description) NOT LIKE '%fuel%'
                     AND LOWER(description) NOT LIKE '%discount%'
                     AND amount > 0 
                THEN amount ELSE 0 END) as base_charges,
            SUM(CASE WHEN charge_type != 'customer_tip' THEN amount ELSE 0 END) as total_charges,
            COUNT(*) as charge_count
        FROM charter_charges
        GROUP BY charter_id
    )
    SELECT 
        c.reserve_number,
        c.charter_id,
        c.total_amount_due,
        COALESCE(cb.total_charges, 0) as sum_charges,
        COALESCE(cb.base_charges, 0) as base_charges,
        COALESCE(cb.gst_charges, 0) as gst_charges,
        COALESCE(cb.beverage_charges, 0) as beverage_charges,
        COALESCE(cb.fuel_charges, 0) as fuel_charges,
        COALESCE(cb.discounts, 0) as discounts,
        COALESCE(cb.charge_count, 0) as charge_count
    FROM charters c
    LEFT JOIN charge_breakdown cb ON cb.charter_id = c.charter_id
    WHERE c.cancelled = FALSE
      AND (c.total_amount_due IS NOT NULL OR cb.total_charges IS NOT NULL)
""")

charge_results = cur.fetchall()
charge_mismatches = []

for row in charge_results:
    reserve, cid, total_due, sum_charges, base, gst, bev, fuel, disc, cnt = row
    total_due = Decimal(str(total_due or 0))
    sum_charges = Decimal(str(sum_charges))
    
    if abs(total_due - sum_charges) > Decimal('0.01'):
        charge_mismatches.append({
            'reserve': reserve,
            'charter_id': cid,
            'total_due': total_due,
            'sum_charges': sum_charges,
            'difference': total_due - sum_charges,
            'base': base,
            'gst': gst,
            'beverage': bev,
            'fuel': fuel,
            'discount': disc,
            'charge_count': cnt
        })

print(f"  Total charters with charges: {len(charge_results):,}")
print(f"  Charge component mismatches: {len(charge_mismatches):,}")

# ============================================================================
# STEP 3: Payment Amount Verification
# ============================================================================
print("\nSTEP 3: Verifying Payment Amounts...")

cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            COUNT(*) as payment_count,
            SUM(amount) as total_paid,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as refunds,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as payments,
            STRING_AGG(DISTINCT payment_method, ', ') as methods,
            MIN(payment_date) as first_payment,
            MAX(payment_date) as last_payment
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        c.reserve_number,
        c.charter_id,
        c.charter_date,
        c.paid_amount,
        COALESCE(ps.total_paid, 0) as sum_payments,
        COALESCE(ps.payment_count, 0) as payment_count,
        COALESCE(ps.refunds, 0) as refunds,
        COALESCE(ps.payments, 0) as gross_payments,
        ps.methods,
        ps.first_payment,
        ps.last_payment,
        c.total_amount_due,
        c.balance
    FROM charters c
    LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
    WHERE c.cancelled = FALSE
      AND (c.paid_amount IS NOT NULL OR ps.total_paid IS NOT NULL)
""")

payment_results = cur.fetchall()
payment_mismatches = []
balance_mismatches = []

for row in payment_results:
    reserve, cid, cdate, paid_amt, sum_pay, pcnt, refunds, gross, methods, first, last, total_due, balance = row
    
    paid_amt = Decimal(str(paid_amt or 0))
    sum_pay = Decimal(str(sum_pay))
    total_due = Decimal(str(total_due or 0))
    balance_field = Decimal(str(balance or 0))
    
    # Check paid_amount vs sum(payments)
    if abs(paid_amt - sum_pay) > Decimal('0.01'):
        payment_mismatches.append({
            'reserve': reserve,
            'charter_id': cid,
            'date': cdate,
            'paid_amount': paid_amt,
            'sum_payments': sum_pay,
            'difference': paid_amt - sum_pay,
            'payment_count': pcnt,
            'refunds': refunds,
            'methods': methods
        })
    
    # Check balance calculation
    computed_balance = total_due - paid_amt
    if abs(balance_field - computed_balance) > Decimal('0.01'):
        balance_mismatches.append({
            'reserve': reserve,
            'charter_id': cid,
            'balance_field': balance_field,
            'computed': computed_balance,
            'difference': balance_field - computed_balance,
            'total_due': total_due,
            'paid_amount': paid_amt
        })

print(f"  Total charters with payments: {len(payment_results):,}")
print(f"  Paid_amount mismatches: {len(payment_mismatches):,}")
print(f"  Balance calculation mismatches: {len(balance_mismatches):,}")

# ============================================================================
# STEP 4: Multi-Charter Payment Detection
# ============================================================================
print("\nSTEP 4: Detecting Multi-Charter Payments...")

cur.execute("""
    WITH payment_charter_count AS (
        SELECT 
            p.payment_id,
            p.payment_key,
            p.amount,
            p.payment_date,
            COUNT(DISTINCT c.reserve_number) as charter_count,
            STRING_AGG(DISTINCT c.reserve_number, ', ' ORDER BY c.reserve_number) as reserves
        FROM payments p
        JOIN charters c ON p.reserve_number = c.reserve_number
        WHERE c.cancelled = FALSE
        GROUP BY p.payment_id, p.payment_key, p.amount, p.payment_date
        HAVING COUNT(DISTINCT c.reserve_number) > 1
    )
    SELECT 
        payment_id, payment_key, amount, payment_date, charter_count, reserves
    FROM payment_charter_count
    ORDER BY charter_count DESC, amount DESC
""")

multi_charter_payments = cur.fetchall()
print(f"  Multi-charter payments found: {len(multi_charter_payments):,}")

if multi_charter_payments:
    multi_summary = defaultdict(int)
    for _, _, _, _, charter_count, _ in multi_charter_payments:
        multi_summary[charter_count] += 1
    
    print("  Distribution:")
    for count in sorted(multi_summary.keys()):
        print(f"    {count} charters: {multi_summary[count]} payments")

# ============================================================================
# STEP 5: Payment Key Batch Analysis
# ============================================================================
print("\nSTEP 5: Analyzing Payment Key Batches...")

cur.execute("""
    SELECT 
        payment_key,
        COUNT(*) as payment_count,
        COUNT(DISTINCT reserve_number) as charter_count,
        SUM(amount) as total_amount,
        MIN(payment_date) as first_date,
        MAX(payment_date) as last_date
    FROM payments
    WHERE payment_key IS NOT NULL
      AND payment_key != ''
    GROUP BY payment_key
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 100
""")

batch_results = cur.fetchall()
suspicious_batches = [r for r in batch_results if r[1] != r[2]]  # payment_count != charter_count

print(f"  Payment key batches (>1 payment): {len(batch_results):,}")
print(f"  Suspicious batches (payments != charters): {len(suspicious_batches):,}")

# ============================================================================
# STEP 6: Final Reconciliation Check
# ============================================================================
print("\nSTEP 6: Final Reconciliation...")

cur.execute("""
    WITH charter_financials AS (
        SELECT 
            c.reserve_number,
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            COALESCE((SELECT SUM(amount) FROM charter_charges cc WHERE cc.reserve_number = c.reserve_number), 0) as sum_charges,
            COALESCE((SELECT SUM(amount) FROM payments p WHERE p.reserve_number = c.reserve_number), 0) as sum_payments,
            c.status,
            c.cancelled
        FROM charters c
        WHERE c.cancelled = FALSE
    )
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN ABS(total_amount_due - sum_charges) > 0.01 THEN 1 END) as charge_mismatch,
        COUNT(CASE WHEN ABS(paid_amount - sum_payments) > 0.01 THEN 1 END) as payment_mismatch,
        COUNT(CASE WHEN ABS(balance - (total_amount_due - paid_amount)) > 0.01 THEN 1 END) as balance_mismatch,
        COUNT(CASE WHEN sum_charges = 0 AND sum_payments = 0 THEN 1 END) as no_activity,
        COUNT(CASE WHEN sum_charges > 0 AND sum_payments = 0 THEN 1 END) as unpaid,
        COUNT(CASE WHEN sum_charges > 0 AND ABS(balance) <= 0.01 THEN 1 END) as paid_in_full,
        COUNT(CASE WHEN balance > 0.01 THEN 1 END) as outstanding_balance,
        COUNT(CASE WHEN balance < -0.01 THEN 1 END) as credits
    FROM charter_financials
""")

final_stats = cur.fetchone()

print(f"  Total non-cancelled charters: {final_stats[0]:,}")
print(f"  Charge mismatches: {final_stats[1]:,}")
print(f"  Payment mismatches: {final_stats[2]:,}")
print(f"  Balance mismatches: {final_stats[3]:,}")
print(f"  No activity: {final_stats[4]:,}")
print(f"  Unpaid with charges: {final_stats[5]:,}")
print(f"  Paid in full: {final_stats[6]:,}")
print(f"  Outstanding balances: {final_stats[7]:,}")
print(f"  Credits: {final_stats[8]:,}")

# ============================================================================
# EXPORT DETAILED REPORTS
# ============================================================================
print("\n" + "="*120)
print("EXPORTING DETAILED REPORTS")
print("="*120)

os.makedirs('reports', exist_ok=True)

# Report 1: Linkage Issues
if linkage_issues:
    with open('reports/audit_linkage_issues.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Reserve', 'Charter_ID', 'Issue_Type', 'Payment_Count'])
        w.writerows(linkage_issues)
    print(f"✓ Linkage issues: reports/audit_linkage_issues.csv ({len(linkage_issues)} rows)")

# Report 2: Charge Mismatches
if charge_mismatches:
    with open('reports/audit_charge_mismatches.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['reserve', 'charter_id', 'total_due', 'sum_charges', 'difference', 
                                          'base', 'gst', 'beverage', 'fuel', 'discount', 'charge_count'])
        w.writeheader()
        w.writerows(charge_mismatches)
    print(f"✓ Charge mismatches: reports/audit_charge_mismatches.csv ({len(charge_mismatches)} rows)")

# Report 3: Payment Mismatches
if payment_mismatches:
    with open('reports/audit_payment_mismatches.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['reserve', 'charter_id', 'date', 'paid_amount', 'sum_payments', 
                                          'difference', 'payment_count', 'refunds', 'methods'])
        w.writeheader()
        w.writerows(payment_mismatches)
    print(f"✓ Payment mismatches: reports/audit_payment_mismatches.csv ({len(payment_mismatches)} rows)")

# Report 4: Balance Mismatches
if balance_mismatches:
    with open('reports/audit_balance_mismatches.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['reserve', 'charter_id', 'balance_field', 'computed', 
                                          'difference', 'total_due', 'paid_amount'])
        w.writeheader()
        w.writerows(balance_mismatches)
    print(f"✓ Balance mismatches: reports/audit_balance_mismatches.csv ({len(balance_mismatches)} rows)")

# Report 5: Multi-Charter Payments
if multi_charter_payments:
    with open('reports/audit_multi_charter_payments.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Payment_ID', 'Payment_Key', 'Amount', 'Payment_Date', 'Charter_Count', 'Reserve_Numbers'])
        w.writerows(multi_charter_payments)
    print(f"✓ Multi-charter payments: reports/audit_multi_charter_payments.csv ({len(multi_charter_payments)} rows)")

# Report 6: Suspicious Batches
if suspicious_batches:
    with open('reports/audit_suspicious_batches.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Payment_Key', 'Payment_Count', 'Charter_Count', 'Total_Amount', 'First_Date', 'Last_Date'])
        w.writerows(suspicious_batches)
    print(f"✓ Suspicious batches: reports/audit_suspicious_batches.csv ({len(suspicious_batches)} rows)")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*120)
print("AUDIT SUMMARY")
print("="*120)
print()
print(f"Total non-cancelled charters audited: {final_stats[0]:,}")
print()
print("ISSUES FOUND:")
print(f"  Linkage issues:           {len(linkage_issues):>8,}")
print(f"  Charge mismatches:        {len(charge_mismatches):>8,}")
print(f"  Payment mismatches:       {len(payment_mismatches):>8,}")
print(f"  Balance mismatches:       {len(balance_mismatches):>8,}")
print(f"  Multi-charter payments:   {len(multi_charter_payments):>8,}")
print(f"  Suspicious batches:       {len(suspicious_batches):>8,}")
print()

total_issues = (len(linkage_issues) + len(charge_mismatches) + len(payment_mismatches) + 
                len(balance_mismatches) + len(multi_charter_payments) + len(suspicious_batches))

if total_issues == 0:
    print("[OK] NO ISSUES FOUND - All charter-payment relationships are valid!")
else:
    print(f"[WARN]  TOTAL ISSUES: {total_issues:,}")
    print()
    print("Review the CSV reports in the 'reports/' directory for details.")

cur.close()
conn.close()
print()
print("="*120)
print("AUDIT COMPLETE")
print("="*120)
