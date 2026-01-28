#!/usr/bin/env python3
"""
Final comprehensive charter-payment reconciliation audit.
Shows overall data quality metrics after all cleanup efforts.
"""

import os
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("FINAL COMPREHENSIVE RECONCILIATION AUDIT")
print(f"Date: January 23, 2026")
print("="*80)

# 1. Total charter count
cur.execute("SELECT COUNT(*) FROM charters WHERE total_amount_due > 0")
active_charters = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charters")
total_charters = cur.fetchone()[0]

print(f"\nTotal charters: {total_charters:,}")
print(f"Active charters (total_due > 0): {active_charters:,}")

# 2. Charge reconciliation (total_amount_due vs charge_sum)
print("\n" + "="*80)
print("CHARGE RECONCILIATION (total_amount_due vs charge_sum)")
print("="*80)

cur.execute("""
    WITH charge_sums AS (
        SELECT 
            c.reserve_number,
            c.total_amount_due,
            COALESCE(SUM(cc.amount), 0) as charge_sum
        FROM charters c
        LEFT JOIN charter_charges cc ON c.reserve_number = cc.reserve_number
        WHERE c.total_amount_due > 0
        GROUP BY c.reserve_number, c.total_amount_due
    )
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ABS(total_amount_due - charge_sum) < 0.01 THEN 1 ELSE 0 END) as exact_match,
        SUM(CASE WHEN charge_sum > total_amount_due THEN 1 ELSE 0 END) as overages,
        SUM(CASE WHEN charge_sum < total_amount_due THEN 1 ELSE 0 END) as deficits,
        SUM(CASE WHEN charge_sum = 0 THEN 1 ELSE 0 END) as zero_charges
    FROM charge_sums
""")

row = cur.fetchone()
total, exact, overages, deficits, zero = row

exact_pct = (exact/total*100) if total > 0 else 0
print(f"Exact match (within $0.01):      {exact:>6,} ({exact_pct:.1f}%)")
print(f"Overages (charges > total):      {overages:>6,} ({overages/total*100:.1f}%)")
print(f"Deficits (charges < total):      {deficits:>6,} ({deficits/total*100:.1f}%)")
print(f"Zero charges (historical):       {zero:>6,} ({zero/total*100:.1f}%)")

# 3. Payment matching (paid_amount vs SUM(payments))
print("\n" + "="*80)
print("PAYMENT MATCHING (paid_amount vs SUM(payments))")
print("="*80)

cur.execute("""
    WITH payment_sums AS (
        SELECT 
            c.reserve_number,
            c.paid_amount,
            COALESCE(SUM(p.amount), 0) as payment_sum
        FROM charters c
        LEFT JOIN payments p ON c.reserve_number = p.reserve_number
        GROUP BY c.reserve_number, c.paid_amount
    )
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ABS(paid_amount - payment_sum) < 0.01 THEN 1 ELSE 0 END) as matched
    FROM payment_sums
""")

row = cur.fetchone()
pmt_total, pmt_matched = row

print(f"Matched (within $0.01):          {pmt_matched:>6,} ({pmt_matched/pmt_total*100:.1f}%)")
print(f"Mismatched:                      {pmt_total-pmt_matched:>6,} ({(pmt_total-pmt_matched)/pmt_total*100:.1f}%)")

# 4. Balance calculations (balance = total_due - paid)
print("\n" + "="*80)
print("BALANCE CALCULATIONS (balance = total_amount_due - paid_amount)")
print("="*80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ABS(balance - (total_amount_due - paid_amount)) < 0.01 THEN 1 ELSE 0 END) as correct
    FROM charters
""")

row = cur.fetchone()
bal_total, bal_correct = row

print(f"Correct:                         {bal_correct:>6,} ({bal_correct/bal_total*100:.1f}%)")
print(f"Incorrect:                       {bal_total-bal_correct:>6,} ({(bal_total-bal_correct)/bal_total*100:.1f}%)")

# 5. Financial summary
print("\n" + "="*80)
print("FINANCIAL SUMMARY")
print("="*80)

cur.execute("""
    SELECT 
        SUM(total_amount_due) as total_revenue,
        SUM(paid_amount) as total_paid,
        SUM(balance) as total_outstanding
    FROM charters
    WHERE total_amount_due > 0
""")

row = cur.fetchone()
revenue, paid, outstanding = row

print(f"Total revenue:                   ${revenue:>15,.2f}")
print(f"Total paid:                      ${paid:>15,.2f}")
print(f"Total outstanding:               ${outstanding:>15,.2f}")
print(f"Collection rate:                 {paid/revenue*100:>14.1f}%")

# 6. Pre-2025 specific metrics
print("\n" + "="*80)
print("PRE-2025 CHARTER RECONCILIATION")
print("="*80)

cur.execute("""
    WITH charge_sums AS (
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(cc.amount), 0) as charge_sum
        FROM charters c
        LEFT JOIN charter_charges cc ON c.reserve_number = cc.reserve_number
        WHERE c.total_amount_due > 0
        AND c.charter_date < '2025-01-01'
        GROUP BY c.reserve_number, c.charter_date, c.total_amount_due
    )
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ABS(total_amount_due - charge_sum) < 0.01 THEN 1 ELSE 0 END) as exact_match,
        SUM(CASE WHEN charge_sum > total_amount_due THEN 1 ELSE 0 END) as overages,
        SUM(CASE WHEN charge_sum < total_amount_due THEN 1 ELSE 0 END) as deficits
    FROM charge_sums
""")

row = cur.fetchone()
pre2025_total, pre2025_exact, pre2025_over, pre2025_def = row

print(f"Pre-2025 charters:               {pre2025_total:>6,}")
print(f"  Exact match:                   {pre2025_exact:>6,} ({pre2025_exact/pre2025_total*100:.1f}%)")
print(f"  Overages:                      {pre2025_over:>6,} ({pre2025_over/pre2025_total*100:.1f}%)")
print(f"  Deficits:                      {pre2025_def:>6,} ({pre2025_def/pre2025_total*100:.1f}%)")

# 7. Top deficits (if any)
if deficits > 0:
    print("\n" + "="*80)
    print(f"TOP 10 REMAINING DEFICITS")
    print("="*80)
    
    cur.execute("""
        WITH charge_sums AS (
            SELECT 
                c.reserve_number,
                c.charter_date,
                c.total_amount_due,
                c.status,
                COALESCE(SUM(cc.amount), 0) as charge_sum
            FROM charters c
            LEFT JOIN charter_charges cc ON c.reserve_number = cc.reserve_number
            WHERE c.total_amount_due > 0
            GROUP BY c.reserve_number, c.charter_date, c.total_amount_due, c.status
        )
        SELECT 
            reserve_number,
            charter_date,
            total_amount_due,
            charge_sum,
            (total_amount_due - charge_sum) as deficit,
            status
        FROM charge_sums
        WHERE charge_sum < total_amount_due
        ORDER BY (total_amount_due - charge_sum) DESC
        LIMIT 10
    """)
    
    print(f"\n{'Reserve':<12} {'Date':<12} {'Total':<12} {'Charges':<12} {'Deficit':<12} {'Status':<15}")
    print("-"*80)
    for row in cur.fetchall():
        reserve, date, total, charges, deficit, status = row
        print(f"{reserve:<12} {date} ${total:>9,.2f} ${charges:>9,.2f} ${deficit:>9,.2f} {status or 'N/A':<15}")

# 8. Payment table metrics
print("\n" + "="*80)
print("PAYMENT TABLE METRICS")
print("="*80)

cur.execute("SELECT COUNT(*) FROM payments")
payments_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charter_payments")
charter_payments_count = cur.fetchone()[0]

cur.execute("SELECT SUM(amount) FROM payments")
payments_total = cur.fetchone()[0] or Decimal('0')

print(f"payments table:                  {payments_count:>6,} records (${payments_total:,.2f})")
print(f"charter_payments table:          {charter_payments_count:>6,} records (legacy/staging)")

# 9. Overall data quality score
print("\n" + "="*80)
print("OVERALL DATA QUALITY SCORE")
print("="*80)

charge_quality = exact_pct  # Already calculated above
payment_quality = (pmt_matched / pmt_total * 100) if pmt_total > 0 else 0
balance_quality = (bal_correct / bal_total * 100) if bal_total > 0 else 0
overall_score = (charge_quality + payment_quality + balance_quality) / 3

print(f"Charge reconciliation:           {charge_quality:>5.1f}%")
print(f"Payment matching:                {payment_quality:>5.1f}%")
print(f"Balance calculations:            {balance_quality:>5.1f}%")
print(f"\n{'='*50}")
print(f"OVERALL DATA QUALITY:            {overall_score:>5.1f}%")
print(f"{'='*50}")

# Status indicator
if overall_score >= 99.0:
    status_icon = "🟢"
    status_text = "EXCELLENT"
elif overall_score >= 95.0:
    status_icon = "🟡"
    status_text = "GOOD"
elif overall_score >= 90.0:
    status_icon = "🟠"
    status_text = "FAIR"
else:
    status_icon = "🔴"
    status_text = "NEEDS WORK"

print(f"\nStatus: {status_icon} {status_text}")

cur.close()
conn.close()
