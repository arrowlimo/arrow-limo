"""
CRITICAL VERIFICATION: Ensure "duplicate" payments are truly duplicates
- Check charter balance impact if duplicates are removed
- Verify Global Payments vs Square payment patterns
- Match actual CC payment amounts to charter charges
- Confirm transaction IDs differ (or are same for TRUE duplicates)
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

def connect():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_suspected_duplicates():
    """Deep analysis of suspected duplicate payments"""
    print("=" * 120)
    print("DUPLICATE PAYMENT VERIFICATION - CRITICAL CHECK BEFORE REMOVAL")
    print("=" * 120)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    conn = connect()
    cur = conn.cursor()
    
    # Find suspected duplicates (same reserve, date, amount)
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                p.reserve_number,
                p.payment_date,
                p.amount,
                p.payment_method,
                COUNT(*) as duplicate_count,
                ARRAY_AGG(p.payment_id ORDER BY p.payment_id) as payment_ids,
                ARRAY_AGG(p.square_transaction_id ORDER BY p.payment_id) as square_ids,
                ARRAY_AGG(p.authorization_code ORDER BY p.payment_id) as auth_codes,
                ARRAY_AGG(p.check_number ORDER BY p.payment_id) as check_numbers,
                ARRAY_AGG(p.created_at ORDER BY p.payment_id) as created_dates
            FROM payments p
            WHERE p.payment_date >= '2024-01-01'
            GROUP BY p.reserve_number, p.payment_date, p.amount, p.payment_method
            HAVING COUNT(*) > 1
        )
        SELECT * FROM duplicates
        ORDER BY duplicate_count DESC, amount DESC
    """)
    
    suspected = cur.fetchall()
    
    print(f"Found {len(suspected)} sets of suspected duplicate payments\n")
    print("=" * 120)
    
    total_suspected_amount = Decimal('0.00')
    true_duplicates_count = 0
    false_positives_count = 0
    
    for idx, dup_set in enumerate(suspected, 1):
        reserve = dup_set[0]
        payment_date = dup_set[1]
        amount = dup_set[2] if dup_set[2] else Decimal('0.00')
        method = dup_set[3] or 'N/A'
        count = dup_set[4]
        payment_ids = dup_set[5]
        square_ids = dup_set[6]
        auth_codes = dup_set[7]
        check_numbers = dup_set[8]
        created_dates = dup_set[9]
        
        print(f"\n{'=' * 120}")
        print(f"SUSPECTED DUPLICATE SET #{idx}")
        print(f"{'=' * 120}")
        print(f"Reserve: {reserve or 'UNMATCHED'}")
        print(f"Date: {payment_date}")
        print(f"Amount: ${amount:,.2f}")
        print(f"Method: {method}")
        print(f"Count: {count} payments")
        print(f"Payment IDs: {payment_ids}")
        
        # Get charter details if reserve exists
        if reserve:
            cur.execute("""
                SELECT 
                    c.client_display_name,
                    c.charter_date,
                    c.total_amount_due,
                    c.paid_amount,
                    c.balance,
                    c.status
                FROM charters c
                WHERE c.reserve_number = %s
            """, (reserve,))
            charter_row = cur.fetchone()
            
            if charter_row:
                print(f"\nCharter Details:")
                print(f"  Customer: {charter_row[0]}")
                print(f"  Charter Date: {charter_row[1]}")
                print(f"  Total Due: ${charter_row[2] if charter_row[2] else 0:,.2f}")
                print(f"  Paid Amount: ${charter_row[3] if charter_row[3] else 0:,.2f}")
                print(f"  Balance Due: ${charter_row[4] if charter_row[4] else 0:,.2f}")
                print(f"  Status: {charter_row[5]}")
                
                # Calculate what balance WOULD be if we remove duplicates
                current_paid = charter_row[3] if charter_row[3] else Decimal('0.00')
                duplicate_total = amount * (count - 1)  # Keep 1, remove others
                new_paid = current_paid - duplicate_total
                new_balance = (charter_row[2] if charter_row[2] else Decimal('0.00')) - new_paid
                
                print(f"\n  ⚠️  IF DUPLICATES REMOVED:")
                print(f"  Current Paid: ${current_paid:,.2f}")
                print(f"  Duplicate Total to Remove: ${duplicate_total:,.2f}")
                print(f"  New Paid Amount: ${new_paid:,.2f}")
                print(f"  New Balance: ${new_balance:,.2f}")
                
                if new_balance < 0:
                    print(f"  ❌ WARNING: Removing would create NEGATIVE balance (overpayment)!")
                    false_positives_count += 1
                elif new_balance == charter_row[4]:
                    print(f"  ⚠️  Balance unchanged - duplicates likely recorded but not applied")
        
        # Check transaction identifiers
        print(f"\nTransaction Identifiers:")
        print(f"  Square IDs: {square_ids}")
        print(f"  Auth Codes: {auth_codes}")
        print(f"  Check Numbers: {check_numbers}")
        print(f"  Created Dates: {created_dates}")
        
        # Determine if TRUE duplicate or FALSE positive
        unique_square_ids = [sid for sid in square_ids if sid is not None and sid != '']
        unique_auth_codes = [ac for ac in auth_codes if ac is not None and ac != '']
        unique_check_nums = [cn for cn in check_numbers if cn is not None and cn != '']
        
        # Check if all created at EXACT same timestamp (microsecond precision)
        unique_timestamps = set([str(cd) for cd in created_dates if cd is not None])
        same_timestamp = len(unique_timestamps) == 1 and count > 1
        
        is_true_duplicate = False
        reason = ""
        
        if len(set(unique_square_ids)) == 1 and len(unique_square_ids) > 1:
            is_true_duplicate = True
            reason = "Same Square transaction ID - TRUE DUPLICATE"
        elif len(set(unique_auth_codes)) == 1 and len(unique_auth_codes) > 1:
            is_true_duplicate = True
            reason = "Same authorization code - TRUE DUPLICATE"
        elif same_timestamp and not unique_square_ids and not unique_auth_codes and not unique_check_nums:
            is_true_duplicate = True
            reason = "Same timestamp + no unique identifiers - TRUE DUPLICATE (bulk import error)"
        elif len(unique_square_ids) == count or len(unique_auth_codes) == count:
            is_true_duplicate = False
            reason = "Different transaction IDs - LIKELY LEGITIMATE (multiple payments)"
        elif method == 'check' and len(set(unique_check_nums)) == count:
            is_true_duplicate = False
            reason = "Different check numbers - LEGITIMATE (multiple checks)"
        elif same_timestamp and (unique_square_ids or unique_auth_codes or unique_check_nums):
            # Same timestamp but has some unique IDs - possibly legitimate rapid payments
            if len(set(unique_square_ids)) == count or len(set(unique_auth_codes)) == count:
                is_true_duplicate = False
                reason = "Same timestamp but unique IDs - LIKELY LEGITIMATE (rapid successive payments)"
            else:
                reason = "Same timestamp, partial IDs - NEEDS REVIEW"
        else:
            reason = "UNCLEAR - Manual review required"
        
        print(f"\n{'🔴 TRUE DUPLICATE' if is_true_duplicate else '🟡 NEEDS REVIEW'}: {reason}")
        
        if is_true_duplicate:
            true_duplicates_count += 1
            total_suspected_amount += amount * (count - 1)
        
        # Get all payment details
        print(f"\nDetailed Payment Records:")
        print(f"{'ID':<8} {'Created':<20} {'Square ID':<30} {'Auth Code':<20} {'Check #':<15}")
        print("-" * 120)
        for i, pid in enumerate(payment_ids):
            created = created_dates[i].strftime('%Y-%m-%d %H:%M:%S') if created_dates[i] else 'N/A'
            sq_id = (square_ids[i] or 'N/A')[:30]
            auth = (auth_codes[i] or 'N/A')[:20]
            check = (check_numbers[i] or 'N/A')[:15]
            print(f"{pid:<8} {created:<20} {sq_id:<30} {auth:<20} {check:<15}")
    
    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print(f"Total Suspected Duplicate Sets: {len(suspected)}")
    print(f"Confirmed TRUE Duplicates: {true_duplicates_count}")
    print(f"Likely False Positives: {false_positives_count}")
    print(f"Needs Manual Review: {len(suspected) - true_duplicates_count - false_positives_count}")
    print(f"Total Amount if TRUE Duplicates Removed: ${total_suspected_amount:,.2f}")
    
    conn.close()

def check_global_payments_pattern():
    """Check for Global Payments merchant services pattern"""
    print("\n" + "=" * 120)
    print("GLOBAL PAYMENTS vs SQUARE PATTERN ANALYSIS")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    # Check for payments with authorization codes (pre-Square era)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as total_payments,
            SUM(CASE WHEN square_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as square_payments,
            SUM(CASE WHEN authorization_code IS NOT NULL AND square_transaction_id IS NULL THEN 1 ELSE 0 END) as auth_code_payments,
            SUM(amount) as total_amount
        FROM payments
        WHERE payment_method IN ('credit_card', 'debit_card')
          AND payment_date >= '2012-01-01'
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year
    """)
    
    print(f"\n{'Year':<6} {'Total CC':>10} {'Square':>10} {'Auth Code':>10} {'Total Amount':>15}")
    print("-" * 120)
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        total = row[1]
        square = row[2]
        auth = row[3]
        amount = row[4] if row[4] else 0.0
        print(f"{year:<6} {total:>10,} {square:>10,} {auth:>10,} ${amount:>13,.2f}")
    
    print("\nℹ️  Auth Code payments = Global Payments (pre-2014)")
    print("ℹ️  Square payments = Square (2014+)")
    
    conn.close()

def verify_charter_balances_with_without_duplicates():
    """Show charter balances with and without suspected duplicates"""
    print("\n" + "=" * 120)
    print("CHARTER BALANCE VERIFICATION (Before vs After Duplicate Removal)")
    print("=" * 120)
    
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("""
        WITH duplicate_totals AS (
            SELECT 
                p.reserve_number,
                SUM(p.amount) as duplicate_amount
            FROM payments p
            WHERE (p.reserve_number, p.payment_date, p.amount, p.payment_method) IN (
                SELECT reserve_number, payment_date, amount, payment_method
                FROM payments
                WHERE payment_date >= '2024-01-01'
                GROUP BY reserve_number, payment_date, amount, payment_method
                HAVING COUNT(*) > 1
            )
            AND p.payment_id NOT IN (
                SELECT MIN(payment_id)
                FROM payments
                WHERE payment_date >= '2024-01-01'
                GROUP BY reserve_number, payment_date, amount, payment_method
                HAVING COUNT(*) > 1
            )
            GROUP BY p.reserve_number
        )
        SELECT 
            c.reserve_number,
            c.client_display_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            dt.duplicate_amount,
            c.paid_amount - dt.duplicate_amount as new_paid,
            c.total_amount_due - (c.paid_amount - dt.duplicate_amount) as new_balance
        FROM charters c
        JOIN duplicate_totals dt ON dt.reserve_number = c.reserve_number
        ORDER BY dt.duplicate_amount DESC
    """)
    
    print(f"\n{'Reserve':<10} {'Customer':<25} {'Total Due':>12} {'Current Paid':>12} {'Dup Amount':>12} {'New Paid':>12} {'New Balance':>12}")
    print("-" * 120)
    
    for row in cur.fetchall():
        reserve = row[0]
        customer = (row[1] or 'N/A')[:25]
        total_due = row[2] if row[2] else 0.0
        current_paid = row[3] if row[3] else 0.0
        dup_amount = row[4] if row[4] else 0.0
        new_paid = row[5] if row[5] else 0.0
        new_balance = row[6] if row[6] else 0.0
        
        flag = ""
        if new_balance < 0:
            flag = "❌ NEGATIVE!"
        elif new_balance == 0:
            flag = "✅ PAID"
        
        print(f"{reserve:<10} {customer:<25} ${total_due:>10,.2f} ${current_paid:>10,.2f} ${dup_amount:>10,.2f} ${new_paid:>10,.2f} ${new_balance:>10,.2f} {flag}")
    
    conn.close()

def main():
    analyze_suspected_duplicates()
    check_global_payments_pattern()
    verify_charter_balances_with_without_duplicates()
    
    print("\n" + "=" * 120)
    print("⚠️  CRITICAL NEXT STEPS")
    print("=" * 120)
    print("1. Review each suspected duplicate above")
    print("2. Check if different transaction IDs = legitimate separate payments")
    print("3. Verify charter balances would be CORRECT after removal")
    print("4. ONLY remove payments where:")
    print("   - Same Square transaction ID (TRUE duplicate)")
    print("   - OR Same authorization code (TRUE duplicate)")
    print("   - AND removal would NOT create negative balance")
    print("5. DO NOT remove if:")
    print("   - Different transaction IDs (likely legitimate)")
    print("   - Different check numbers")
    print("   - Removal would make balance negative")
    print("\n⚠️  DO NOT PROCEED WITH BULK DELETION - MANUAL REVIEW REQUIRED")

if __name__ == "__main__":
    main()
