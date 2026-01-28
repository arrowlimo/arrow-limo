#!/usr/bin/env python3
"""
Comprehensive charter-payment verification:
1. Match ALL payments to charters via reserve_number
2. Calculate expected charter.paid_amount from payments SUM
3. Find discrepancies: payments made but not recorded in charters
4. Find orphan payments (no charter, not refunded)
5. Identify cancelled charters with retainer payments (held in escrow)
6. Generate actionable CSV reports

RULE: reserve_number is the business key for charter-payment matching
"""
import os
import csv
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print("="*80)
    print("CHARTER-PAYMENT COMPLETENESS VERIFICATION")
    print("="*80)

    # 1. Overall payment statistics
    print("\n1. PAYMENT STATISTICS")
    print("-"*80)
    
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments")
    total_payments, total_amount = cur.fetchone()
    print(f"Total payments: {total_payments:,} | ${total_amount:,.2f}")
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
    """)
    with_reserve, with_reserve_amt = cur.fetchone()
    print(f"With reserve_number: {with_reserve:,} ({with_reserve/total_payments*100:.1f}%) | ${with_reserve_amt:,.2f}")
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE (reserve_number IS NULL OR reserve_number = '') AND charter_id IS NULL
    """)
    orphan_count, orphan_amt = cur.fetchone()
    print(f"Orphan payments (no reserve, no charter_id): {orphan_count:,} ({orphan_count/total_payments*100:.1f}%) | ${orphan_amt:,.2f}")

    # 2. Charter coverage
    print("\n2. CHARTER STATISTICS")
    print("-"*80)
    
    cur.execute("SELECT COUNT(*) FROM charters")
    total_charters = cur.fetchone()[0]
    print(f"Total charters: {total_charters:,}")
    
    cur.execute("""
        SELECT COUNT(DISTINCT c.charter_id)
        FROM charters c
        INNER JOIN payments p ON p.reserve_number = c.reserve_number
    """)
    charters_with_payments = cur.fetchone()[0]
    print(f"Charters with payments: {charters_with_payments:,} ({charters_with_payments/total_charters*100:.1f}%)")
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE cancelled = true
    """)
    cancelled_charters = cur.fetchone()[0]
    print(f"Cancelled charters: {cancelled_charters:,}")

    # 3. Find payments with reserve_number but no matching charter
    print("\n3. PAYMENTS WITHOUT MATCHING CHARTER")
    print("-"*80)
    
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, p.payment_date, p.amount, p.payment_method
        FROM payments p
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
        ORDER BY p.payment_date DESC
    """)
    
    missing_charters = cur.fetchall()
    print(f"Found {len(missing_charters):,} payments with reserve_number but NO matching charter")
    
    if missing_charters:
        print(f"\nSample (first 10):")
        for payment_id, reserve, pdate, amt, method in missing_charters[:10]:
            print(f"  Payment {payment_id} | Reserve {reserve} | {pdate} | ${amt:,.2f} | {method}")
        
        # Write to CSV
        report_path = os.path.join(REPORT_DIR, "payments_missing_charter.csv")
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['payment_id', 'reserve_number', 'payment_date', 'amount', 'payment_method'])
            writer.writerows(missing_charters)
        print(f"\nReport: {report_path}")

    # 4. Calculate expected vs actual paid_amount for all charters
    print("\n4. CHARTER PAYMENT RECONCILIATION")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            COALESCE(c.paid_amount, 0) as recorded_paid,
            c.balance,
            COALESCE(SUM(p.amount), 0) as calculated_paid,
            c.cancelled,
            c.status
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.balance, c.cancelled, c.status
        HAVING COALESCE(c.paid_amount, 0) <> COALESCE(SUM(p.amount), 0)
        ORDER BY ABS(COALESCE(c.paid_amount, 0) - COALESCE(SUM(p.amount), 0)) DESC
    """)
    
    discrepancies = cur.fetchall()
    print(f"Found {len(discrepancies):,} charters with paid_amount ≠ SUM(payments)")
    
    if discrepancies:
        total_discrepancy = sum(abs(float(row[3]) - float(row[5])) for row in discrepancies)
        print(f"Total discrepancy amount: ${total_discrepancy:,.2f}")
        
        print(f"\nTop 10 discrepancies:")
        for charter_id, reserve, total_due, recorded, balance, calculated, cancelled, status in discrepancies[:10]:
            diff = float(recorded) - float(calculated)
            print(f"  Charter {charter_id} ({reserve}) | Recorded: ${recorded:,.2f} | Calculated: ${calculated:,.2f} | Diff: ${diff:+,.2f} | Cancelled: {cancelled}")
        
        # Write to CSV
        report_path = os.path.join(REPORT_DIR, "charter_payment_discrepancies.csv")
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['charter_id', 'reserve_number', 'total_amount_due', 'recorded_paid_amount', 
                           'balance', 'calculated_paid_amount', 'discrepancy', 'cancelled', 'status'])
            for row in discrepancies:
                charter_id, reserve, total_due, recorded, balance, calculated, cancelled, status = row
                diff = float(recorded) - float(calculated)
                writer.writerow([charter_id, reserve, total_due, recorded, balance, calculated, diff, cancelled, status])
        print(f"\nReport: {report_path}")

    # 5. Cancelled charters with payments (retainers in escrow)
    print("\n5. CANCELLED CHARTERS WITH PAYMENTS (RETAINERS IN ESCROW)")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            COALESCE(c.paid_amount, 0) as paid_amount,
            COALESCE(SUM(p.amount), 0) as total_payments,
            c.status,
            c.notes
        FROM charters c
        INNER JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.cancelled = true
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.status, c.notes
        ORDER BY total_payments DESC
    """)
    
    cancelled_with_payments = cur.fetchall()
    print(f"Found {len(cancelled_with_payments):,} cancelled charters with payments (retainers)")
    
    if cancelled_with_payments:
        total_retainers = sum(float(row[4]) for row in cancelled_with_payments)
        print(f"Total retainer amount held in escrow: ${total_retainers:,.2f}")
        
        print(f"\nTop 10 cancelled charters with retainers:")
        for charter_id, reserve, total_due, paid, total_pmts, status, notes in cancelled_with_payments[:10]:
            print(f"  Charter {charter_id} ({reserve}) | Payments: ${total_pmts:,.2f} | Status: {status}")
        
        # Write to CSV
        report_path = os.path.join(REPORT_DIR, "cancelled_charters_with_retainers.csv")
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['charter_id', 'reserve_number', 'total_amount_due', 'paid_amount', 
                           'total_payments', 'status', 'notes'])
            writer.writerows(cancelled_with_payments)
        print(f"\nReport: {report_path}")

    # 6. Orphan payments (no charter, no refund recorded)
    print("\n6. ORPHAN PAYMENTS (NO CHARTER, NOT REFUNDED)")
    print("-"*80)
    
    cur.execute("""
        SELECT p.payment_id, p.payment_date, p.amount, p.payment_method, 
               p.square_payment_id, p.notes, p.status
        FROM payments p
        WHERE (p.reserve_number IS NULL OR p.reserve_number = '')
        AND p.charter_id IS NULL
        AND COALESCE(p.status, '') NOT ILIKE '%refund%'
        AND COALESCE(p.status, '') NOT ILIKE '%void%'
        ORDER BY p.payment_date DESC
    """)
    
    orphan_payments = cur.fetchall()
    print(f"Found {len(orphan_payments):,} orphan payments (no charter, not refunded)")
    
    if orphan_payments:
        total_orphan = sum(float(row[2]) for row in orphan_payments)
        print(f"Total orphan payment amount: ${total_orphan:,.2f}")
        
        print(f"\nSample (first 10):")
        for payment_id, pdate, amt, method, square_id, notes, status in orphan_payments[:10]:
            print(f"  Payment {payment_id} | {pdate} | ${amt:,.2f} | {method} | Square: {square_id[:20] if square_id else 'N/A'}")
        
        # Write to CSV
        report_path = os.path.join(REPORT_DIR, "orphan_payments_not_refunded.csv")
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['payment_id', 'payment_date', 'amount', 'payment_method', 
                           'square_payment_id', 'notes', 'status'])
            writer.writerows(orphan_payments)
        print(f"\nReport: {report_path}")

    # 7. Summary statistics
    print("\n7. SUMMARY")
    print("="*80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as charters_with_balance,
            COALESCE(SUM(balance), 0) as total_balance
        FROM charters
        WHERE balance > 0
        AND (cancelled = false OR cancelled IS NULL)
    """)
    balance_count, total_balance = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*) FROM charters
        WHERE balance > 0
        AND (cancelled = false OR cancelled IS NULL)
        AND NOT EXISTS (
            SELECT 1 FROM payments p WHERE p.reserve_number = charters.reserve_number
        )
    """)
    balance_no_payments = cur.fetchone()[0]
    
    print(f"Charters with outstanding balance (non-cancelled): {balance_count:,} | ${total_balance:,.2f}")
    print(f"  - With NO payments recorded: {balance_no_payments:,}")
    print(f"  - With payments (underpaid): {balance_count - balance_no_payments:,}")
    
    print(f"\nPayments summary:")
    print(f"  - Total payments: {total_payments:,} | ${total_amount:,.2f}")
    print(f"  - Linked to charters: {with_reserve:,} ({with_reserve/total_payments*100:.1f}%)")
    print(f"  - Orphan (need action): {orphan_count:,} ({orphan_count/total_payments*100:.1f}%) | ${orphan_amt:,.2f}")
    
    print(f"\nDiscrepancies:")
    print(f"  - Payments without charter: {len(missing_charters):,}")
    print(f"  - Charters with payment amount mismatch: {len(discrepancies):,}")
    print(f"  - Cancelled charters with retainers: {len(cancelled_with_payments):,} | ${total_retainers:,.2f}")

    cur.close()
    conn.close()

    print("\n" + "="*80)
    print("VERIFICATION COMPLETE - Reports generated in reports/")
    print("="*80)


if __name__ == "__main__":
    main()
