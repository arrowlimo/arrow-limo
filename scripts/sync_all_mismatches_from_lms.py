"""
Sync all payment mismatches using LMS as source of truth.
Compares PostgreSQL charters/payments against LMS Reserve/Payment tables.
Fixes discrepancies in charges and payments.
"""
import psycopg2
import pyodbc
import os
import sys
from decimal import Decimal

LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def get_lms_conn():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_mismatched_charters(pg_cur, limit=50):
    """Get charters with payment mismatches"""
    pg_cur.execute("""
        WITH payment_totals AS (
            SELECT reserve_number, ROUND(SUM(amount)::numeric,2) AS actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT 
            c.reserve_number,
            c.charter_id,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            COALESCE(pt.actual_paid, 0) as actual_paid,
            ABS(c.paid_amount - COALESCE(pt.actual_paid, 0)) as paid_diff
        FROM charters c
        LEFT JOIN payment_totals pt ON pt.reserve_number = c.reserve_number
        WHERE ABS(c.paid_amount - COALESCE(pt.actual_paid, 0)) > 0.01
           OR COALESCE(pt.actual_paid, 0) > c.total_amount_due * 2
        ORDER BY paid_diff DESC
        LIMIT %s
    """, (limit,))
    return pg_cur.fetchall()

def get_lms_charter_info(lms_cur, reserve_number):
    """Get charter info from LMS"""
    try:
        lms_cur.execute("""
            SELECT Reserve_No, Est_Charge, Deposit, Balance, Rate, Status
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve_number,))
        return lms_cur.fetchone()
    except:
        return None

def get_lms_payments(lms_cur, reserve_number):
    """Get payments from LMS for this reserve"""
    try:
        lms_cur.execute("""
            SELECT PaymentID, Amount, LastUpdated
            FROM Payment
            WHERE Reserve_No = ?
            ORDER BY LastUpdated
        """, (reserve_number,))
        return lms_cur.fetchall()
    except:
        return []

def fix_charter_charges(pg_cur, charter_id, reserve_number, lms_total):
    """Update charter charges to match LMS Est_Charge"""
    # Backup existing charges
    pg_cur.execute("""
        CREATE TABLE IF NOT EXISTS charter_charges_backup_lms_sync_20251123 AS
        SELECT * FROM charter_charges WHERE 1=0
    """)
    
    pg_cur.execute("""
        INSERT INTO charter_charges_backup_lms_sync_20251123
        SELECT * FROM charter_charges WHERE charter_id = %s
    """, (charter_id,))
    
    # Delete old charges
    pg_cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (charter_id,))
    
    # Create new charge matching LMS
    pg_cur.execute("""
        INSERT INTO charter_charges (charter_id, description, amount, created_at)
        VALUES (%s, 'Charter total (from LMS Est_Charge)', %s, CURRENT_TIMESTAMP)
    """, (charter_id, lms_total))

def fix_charter_payments(pg_cur, reserve_number, charter_id, lms_deposit):
    """Update charter paid_amount to match LMS Deposit by unlinking excess payments"""
    # Get current actual payments
    pg_cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payments
        WHERE reserve_number = %s
    """, (reserve_number,))
    actual_paid = float(pg_cur.fetchone()[0])
    
    # If actual payments already match LMS, we're good
    if abs(actual_paid - lms_deposit) < 0.01:
        return actual_paid
    
    # If actual > LMS, we have excess payments linked (likely ETR: errors)
    if actual_paid > lms_deposit:
        # Get all payments for this charter
        pg_cur.execute("""
            SELECT payment_id, amount, payment_date, payment_key, payment_method, charter_id
            FROM payments
            WHERE reserve_number = %s
            ORDER BY 
                CASE 
                    WHEN payment_key NOT LIKE 'ETR:%%' AND payment_key IS NOT NULL THEN 1
                    WHEN payment_key IS NULL THEN 2
                    WHEN payment_key LIKE 'ETR:%%' THEN 3
                    ELSE 4
                END,
                payment_date ASC
        """, (reserve_number,))
        
        payments = pg_cur.fetchall()
        running_total = 0
        payments_to_keep = []
        payments_to_unlink = []
        
        # Keep payments until we reach LMS deposit amount
        for pid, amt, pdate, key, method, cid in payments:
            amt_f = float(amt)
            if running_total + amt_f <= lms_deposit + 0.01:
                payments_to_keep.append(pid)
                running_total += amt_f
            else:
                payments_to_unlink.append(pid)
        
        # Unlink excess payments
        if payments_to_unlink:
            pg_cur.execute("""
                CREATE TABLE IF NOT EXISTS payments_backup_lms_sync_20251123 AS
                SELECT * FROM payments WHERE 1=0
            """)
            
            pg_cur.execute("""
                INSERT INTO payments_backup_lms_sync_20251123
                SELECT * FROM payments WHERE payment_id = ANY(%s)
            """, (payments_to_unlink,))
            
            pg_cur.execute("""
                UPDATE payments
                SET reserve_number = NULL, charter_id = NULL
                WHERE payment_id = ANY(%s)
            """, (payments_to_unlink,))
            
            return running_total
    
    return actual_paid

def main():
    apply_mode = '--apply' in sys.argv
    limit = 50
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        limit = int(sys.argv[idx + 1])
    
    pg_conn = get_pg_conn()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_conn()
    lms_cur = lms_conn.cursor()
    
    print("="*80)
    print("LMS SYNC: Fix Payment Mismatches Using LMS as Source of Truth")
    print("="*80)
    print()
    
    # Get mismatched charters from PostgreSQL
    print(f"Finding up to {limit} mismatched charters...")
    mismatches = get_mismatched_charters(pg_cur, limit)
    print(f"Found {len(mismatches)} charters with payment mismatches\n")
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    for row in mismatches:
        reserve, charter_id, pg_total, pg_paid, pg_bal, actual_paid, diff = row
        
        # Handle NULL values
        pg_total = pg_total if pg_total is not None else 0
        pg_paid = pg_paid if pg_paid is not None else 0
        pg_bal = pg_bal if pg_bal is not None else 0
        actual_paid = actual_paid if actual_paid is not None else 0
        
        print(f"\nCharter {reserve}:")
        print(f"  PostgreSQL: Total ${pg_total:.2f}, Paid ${pg_paid:.2f}, Balance ${pg_bal:.2f}")
        print(f"  Actual Payments: ${actual_paid:.2f}")
        
        # Get LMS data
        lms_info = get_lms_charter_info(lms_cur, reserve)
        if not lms_info:
            print(f"  ⚠️  Not found in LMS - skipping")
            skipped_count += 1
            continue
        
        lms_res, lms_total, lms_deposit, lms_balance, lms_rate, lms_status = lms_info
        lms_total = float(lms_total) if lms_total else 0.0
        lms_deposit = float(lms_deposit) if lms_deposit else 0.0
        lms_balance = float(lms_balance) if lms_balance else 0.0
        
        # Convert PostgreSQL Decimal to float for comparison
        pg_total_f = float(pg_total)
        pg_paid_f = float(pg_paid)
        actual_paid_f = float(actual_paid)
        
        print(f"  LMS: Total ${lms_total:.2f}, Deposit ${lms_deposit:.2f}, Balance ${lms_balance:.2f}")
        
        # Determine what needs fixing
        needs_charge_fix = abs(pg_total_f - lms_total) > 0.01
        needs_payment_fix = abs(actual_paid_f - lms_deposit) > 0.01
        
        if needs_charge_fix:
            print(f"  → Charge mismatch: PG ${pg_total_f:.2f} vs LMS ${lms_total:.2f}")
        
        if needs_payment_fix:
            print(f"  → Payment mismatch: PG ${actual_paid_f:.2f} vs LMS ${lms_deposit:.2f}")
        
        if not needs_charge_fix and not needs_payment_fix:
            # Just recalculate balance
            print(f"  → Just needs recalculation")
        
        if apply_mode:
            try:
                # Fix charges if needed
                if needs_charge_fix:
                    fix_charter_charges(pg_cur, charter_id, reserve, lms_total)
                    print(f"    ✓ Updated charges to ${lms_total:.2f}")
                
                # Recalculate from actual payments (unlink excess if needed)
                actual_paid_final = fix_charter_payments(pg_cur, reserve, charter_id, lms_deposit)
                
                # Update charter record
                pg_cur.execute("""
                    UPDATE charters
                    SET total_amount_due = %s,
                        paid_amount = %s,
                        balance = %s - %s
                    WHERE charter_id = %s
                """, (lms_total, actual_paid_final, lms_total, actual_paid_final, charter_id))
                
                print(f"    ✓ Updated charter: Total ${lms_total:.2f}, Paid ${actual_paid_final:.2f}, Balance ${lms_total - actual_paid_final:.2f}")
                fixed_count += 1
                
            except Exception as e:
                print(f"    ✗ ERROR: {e}")
                error_count += 1
                pg_conn.rollback()
        else:
            print(f"  → Would fix in --apply mode")
    
    if apply_mode:
        pg_conn.commit()
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(f"Fixed: {fixed_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Errors: {error_count}")
        print("\n✓ Changes committed")
    else:
        print("\n" + "="*80)
        print("DRY RUN - Use --apply to execute fixes")
        print("Use --limit N to process more/fewer charters")
        print("="*80)
    
    pg_cur.close()
    pg_conn.close()
    lms_cur.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
