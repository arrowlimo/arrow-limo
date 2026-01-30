"""
Verify client overpayments and detect if LMS payments duplicate existing payments
- Check for negative balances (overpayments)
- Match LMS payments to existing almsdata payments by date+amount
- Confirm balance=0 charters are fully paid (not overpaid)
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def connect():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def check_overpayments():
    """Check for overpaid charters (negative balance)"""
    print("=" * 120)
    print("CLIENT OVERPAYMENT VERIFICATION")
    print("=" * 120)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    conn = connect()
    cur = conn.cursor()
    
    # Find charters with negative balance (overpaid)
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.client_display_name,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status
        FROM charters c
        WHERE c.balance < -0.01  -- Negative balance = overpaid
        ORDER BY c.balance ASC
        LIMIT 50
    """)
    
    overpayments = cur.fetchall()
    
    if overpayments:
        print(f"⚠️  Found {len(overpayments)} charters with OVERPAYMENTS (negative balance):\n")
        print(f"{'Reserve':<10} {'Customer':<30} {'Charter Date':<12} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Status':<10}")
        print("-" * 120)
        
        total_overpaid = Decimal('0.00')
        for row in overpayments:
            reserve = row[0]
            customer = (row[1] or 'N/A')[:30]
            charter_date = row[2]
            total_due = row[3] if row[3] is not None else Decimal('0.00')
            paid = row[4] if row[4] is not None else Decimal('0.00')
            balance = row[5] if row[5] is not None else Decimal('0.00')
            status = (row[6] or 'N/A')[:10]
            
            total_overpaid += abs(balance)
            print(f"{reserve:<10} {customer:<30} {str(charter_date):<12} ${total_due:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f} {status:<10}")
        
        print(f"\nTotal Overpaid Amount: ${total_overpaid:,.2f}")
    else:
        print("✅ No overpayments found (all balances >= 0)\n")
    
    # Check charters with balance = 0 (fully paid, no issues)
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE ABS(c.balance) < 0.01  -- Balance is zero (fully paid)
    """)
    zero_balance_count = cur.fetchone()[0]
    print(f"✅ {zero_balance_count:,} charters with ZERO balance (fully paid, no issues)")
    
    conn.close()

def check_lms_vs_existing_payments():
    """Check if LMS payments match existing almsdata payments (potential duplicates)"""
    print("\n" + "=" * 120)
    print("LMS vs EXISTING PAYMENT MATCHING")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    # Find LMS payments that match existing non-LMS payments by reserve+date+amount
    cur.execute("""
        WITH lms_payments AS (
            SELECT 
                p.payment_id,
                p.reserve_number,
                p.payment_date,
                p.amount,
                p.reference_number
            FROM payments p
            WHERE p.reference_number LIKE 'LMS-Payment-%'
        ),
        existing_payments AS (
            SELECT 
                p.payment_id,
                p.reserve_number,
                p.payment_date,
                p.amount,
                p.square_transaction_id,
                p.authorization_code,
                p.reference_number
            FROM payments p
            WHERE p.reference_number IS NULL 
               OR p.reference_number NOT LIKE 'LMS-Payment-%'
        )
        SELECT 
            lms.reserve_number,
            lms.payment_date,
            lms.amount,
            COUNT(DISTINCT lms.payment_id) as lms_count,
            COUNT(DISTINCT ex.payment_id) as existing_count,
            ARRAY_AGG(DISTINCT lms.payment_id) as lms_ids,
            ARRAY_AGG(DISTINCT ex.payment_id) as existing_ids,
            STRING_AGG(DISTINCT ex.square_transaction_id, ', ') as square_ids,
            STRING_AGG(DISTINCT ex.authorization_code, ', ') as auth_codes
        FROM lms_payments lms
        LEFT JOIN existing_payments ex 
            ON ex.reserve_number = lms.reserve_number
            AND ex.payment_date = lms.payment_date
            AND ABS(ex.amount - lms.amount) < 0.01
        WHERE ex.payment_id IS NOT NULL
        GROUP BY lms.reserve_number, lms.payment_date, lms.amount
        HAVING COUNT(DISTINCT ex.payment_id) > 0
        ORDER BY lms.amount DESC
        LIMIT 50
    """)
    
    matches = cur.fetchall()
    
    if matches:
        print(f"\n⚠️  Found {len(matches)} LMS payments that MATCH existing payments:\n")
        print(f"{'Reserve':<10} {'Date':<12} {'Amount':>12} {'LMS':>5} {'Existing':>8} {'Square/Auth IDs':<50}")
        print("-" * 120)
        
        for row in matches:
            reserve = row[0] or 'N/A'
            date = str(row[1]) if row[1] else 'N/A'
            amount = row[2] if row[2] is not None else 0.0
            lms_count = row[3]
            existing_count = row[4]
            square_ids = (row[7] or 'None')[:50]
            
            print(f"{reserve:<10} {date:<12} ${amount:>10,.2f} {lms_count:>5} {existing_count:>8} {square_ids:<50}")
        
        print(f"\n⚠️  These LMS payments may be duplicates of existing payments!")
        print("    If Square/Auth IDs are present, the existing payment is the original.")
        print("    The LMS import may have re-imported already recorded payments.")
    else:
        print("\n✅ No LMS payments match existing payments - no duplicate imports detected")
    
    conn.close()

def verify_payment_totals_by_source():
    """Break down payments by source to identify any issues"""
    print("\n" + "=" * 120)
    print("PAYMENT BREAKDOWN BY SOURCE")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    # Count payments by source
    cur.execute("""
        SELECT 
            CASE 
                WHEN reference_number LIKE 'LMS-Payment-%' THEN 'LMS Import (Jan 7, 2026)'
                WHEN square_transaction_id IS NOT NULL THEN 'Square Payments'
                WHEN authorization_code IS NOT NULL THEN 'Global Payments (Auth Code)'
                WHEN payment_method = 'check' THEN 'Check Payments'
                WHEN payment_method = 'cash' THEN 'Cash Payments'
                WHEN payment_method = 'bank_transfer' THEN 'Bank Transfer'
                ELSE 'Other/Unknown'
            END as source,
            COUNT(*) as payment_count,
            SUM(amount) as total_amount
        FROM payments
        GROUP BY 
            CASE 
                WHEN reference_number LIKE 'LMS-Payment-%' THEN 'LMS Import (Jan 7, 2026)'
                WHEN square_transaction_id IS NOT NULL THEN 'Square Payments'
                WHEN authorization_code IS NOT NULL THEN 'Global Payments (Auth Code)'
                WHEN payment_method = 'check' THEN 'Check Payments'
                WHEN payment_method = 'cash' THEN 'Cash Payments'
                WHEN payment_method = 'bank_transfer' THEN 'Bank Transfer'
                ELSE 'Other/Unknown'
            END
        ORDER BY SUM(amount) DESC
    """)
    
    print(f"\n{'Source':<35} {'Count':>10} {'Total Amount':>15}")
    print("-" * 120)
    
    grand_total = Decimal('0.00')
    for row in cur.fetchall():
        source = row[0]
        count = row[1]
        amount = row[2] if row[2] is not None else 0.0
        grand_total += Decimal(str(amount))
        print(f"{source:<35} {count:>10,} ${amount:>13,.2f}")
    
    print("-" * 120)
    print(f"{'GRAND TOTAL':<35} {'':<10} ${grand_total:>13,.2f}")
    
    conn.close()

def check_balance_calculation_accuracy():
    """Verify that balance = total_due - paid_amount"""
    print("\n" + "=" * 120)
    print("BALANCE CALCULATION ACCURACY CHECK")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.client_display_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            (c.total_amount_due - c.paid_amount) as calculated_balance,
            ABS(c.balance - (c.total_amount_due - c.paid_amount)) as difference
        FROM charters c
        WHERE ABS(c.balance - (c.total_amount_due - c.paid_amount)) > 0.01
        ORDER BY ABS(c.balance - (c.total_amount_due - c.paid_amount)) DESC
        LIMIT 20
    """)
    
    mismatches = cur.fetchall()
    
    if mismatches:
        print(f"\n⚠️  Found {len(mismatches)} charters with INCORRECT balance calculations:\n")
        print(f"{'Reserve':<10} {'Customer':<25} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Should Be':>12} {'Diff':>10}")
        print("-" * 120)
        
        for row in mismatches:
            reserve = row[0]
            customer = (row[1] or 'N/A')[:25]
            total_due = row[2] if row[2] is not None else 0.0
            paid = row[3] if row[3] is not None else 0.0
            balance = row[4] if row[4] is not None else 0.0
            calculated = row[5] if row[5] is not None else 0.0
            diff = row[6] if row[6] is not None else 0.0
            
            print(f"{reserve:<10} {customer:<25} ${total_due:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f} ${calculated:>10,.2f} ${diff:>8,.2f}")
    else:
        print("\n✅ All charter balances are calculated correctly (balance = total_due - paid_amount)")
    
    conn.close()

def main():
    check_overpayments()
    check_lms_vs_existing_payments()
    verify_payment_totals_by_source()
    check_balance_calculation_accuracy()
    
    print("\n" + "=" * 120)
    print("SUMMARY RECOMMENDATIONS")
    print("=" * 120)
    print("1. ✅ Charters with balance = 0 are fully paid (no action needed)")
    print("2. ⚠️  Charters with balance < 0 are overpaid (review for refunds or credits)")
    print("3. ⚠️  If LMS payments match existing Square/Global payments:")
    print("      - REMOVE the LMS duplicate")
    print("      - KEEP the original payment with transaction ID")
    print("4. ✅ Verify all balances are calculated correctly before finalizing")

if __name__ == "__main__":
    main()
