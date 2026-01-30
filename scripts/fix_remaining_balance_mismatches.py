"""
Fix remaining charter balance mismatches with improved duplicate detection.
Checks BOTH payment_key AND amount+date combinations to prevent duplicates.
"""

import pyodbc
import psycopg2
import sys

# LMS Access database
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')

# PostgreSQL database
pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

def get_lms_payments(reserve_no):
    """Get all payments from LMS for a reserve number."""
    cur = lms_conn.cursor()
    cur.execute("""
        SELECT PaymentID, [Key], LastUpdated, Amount, Reserve_No
        FROM Payment
        WHERE Reserve_No = ?
        ORDER BY LastUpdated
    """, (reserve_no,))
    return cur.fetchall()

def get_pg_payments(reserve_number):
    """Get all payments from PostgreSQL for a reserve number."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT payment_id, payment_key, payment_date, amount
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve_number,))
    return cur.fetchall()

def payment_exists(reserve_number, amount, payment_date):
    """
    Check if a payment with this amount and date already exists.
    Uses tolerance of $0.01 for floating point comparison.
    """
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM payments
        WHERE reserve_number = %s
        AND ABS(amount - %s) < 0.01
        AND payment_date = %s
    """, (reserve_number, float(amount), payment_date))
    count = cur.fetchone()[0]
    return count > 0

def import_missing_payment(reserve_number, payment_key, payment_date, amount, lms_payment_id):
    """Import a single payment if it doesn't already exist."""
    cur = pg_conn.cursor()
    
    # Check payment_key first
    cur.execute("SELECT COUNT(*) FROM payments WHERE payment_key = %s", (payment_key,))
    if cur.fetchone()[0] > 0:
        print(f"  [SKIP] Payment key {payment_key} already exists")
        return False
    
    # Check amount + date combination
    if payment_exists(reserve_number, amount, payment_date):
        print(f"  [SKIP] Payment ${amount} on {payment_date} already exists")
        return False
    
    # Import payment
    cur.execute("""
        INSERT INTO payments (reserve_number, payment_key, payment_date, amount, last_updated_by, created_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (reserve_number, payment_key, payment_date, float(amount), 'fix_remaining_balance_mismatches.py'))
    
    print(f"  [IMPORT] ${amount} on {payment_date} - LMS:{lms_payment_id}")
    return True

def recalculate_charter_balance(reserve_number):
    """Recalculate paid_amount and balance for a charter."""
    cur = pg_conn.cursor()
    cur.execute("""
        UPDATE charters
        SET paid_amount = (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        ),
        balance = total_amount_due - (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        )
        WHERE reserve_number = %s
        RETURNING total_amount_due, paid_amount, balance
    """, (reserve_number, reserve_number, reserve_number))
    result = cur.fetchone()
    if result:
        total, paid, balance = result
        print(f"  [UPDATE] Total=${total:.2f} Paid=${paid:.2f} Balance=${balance:.2f}")
    return result

def fix_charter(reserve_number):
    """Fix a single charter by importing missing payments."""
    print(f"\nCHARTER {reserve_number}:")
    
    # Get LMS payments
    lms_payments = get_lms_payments(reserve_number)
    if not lms_payments:
        print("  [WARN] No payments found in LMS")
        return False
    
    lms_total = sum(float(p[3]) for p in lms_payments)
    print(f"  LMS: {len(lms_payments)} payments totaling ${lms_total:.2f}")
    
    # Get PostgreSQL payments
    pg_payments = get_pg_payments(reserve_number)
    pg_total = sum(float(p[3]) for p in pg_payments)
    print(f"  PostgreSQL: {len(pg_payments)} payments totaling ${pg_total:.2f}")
    
    # Import missing payments
    imported = 0
    for lms_payment in lms_payments:
        payment_id, key, last_updated, amount, reserve_no = lms_payment
        payment_key = f"LMS:{payment_id}"
        payment_date = last_updated.date() if hasattr(last_updated, 'date') else last_updated
        
        if import_missing_payment(reserve_number, payment_key, payment_date, amount, payment_id):
            imported += 1
    
    if imported > 0:
        print(f"  [SUMMARY] Imported {imported} missing payment(s)")
        recalculate_charter_balance(reserve_number)
        return True
    else:
        print(f"  [SUMMARY] No missing payments to import")
        return False

# Charters to fix (from rollback output)
CHARTERS_TO_FIX = [
    '016086',  # Paid $467 should be $1,954
    '013690',  # Paid $1,740 should be $2,980
    '017720',  # Paid $1,008 should be $2,028
    '018199',  # Paid $1,954 should be $2,954
]

print("=" * 80)
print("FIXING REMAINING CHARTER BALANCE MISMATCHES")
print("=" * 80)

try:
    fixed_count = 0
    for reserve_number in CHARTERS_TO_FIX:
        if fix_charter(reserve_number):
            fixed_count += 1
    
    # Ask before committing
    print("\n" + "=" * 80)
    print(f"READY TO COMMIT: {fixed_count} charters fixed")
    print("=" * 80)
    response = input("Commit changes? (yes/no): ").strip().lower()
    
    if response == 'yes':
        pg_conn.commit()
        print("\n[OK] Changes committed")
    else:
        pg_conn.rollback()
        print("\n[CANCELLED] Changes rolled back")

except Exception as e:
    print(f"\n[ERROR] {e}")
    pg_conn.rollback()
    raise

finally:
    lms_conn.close()
    pg_conn.close()
