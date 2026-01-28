"""
Recalculate charter.paid_amount from payments BY RESERVE_NUMBER (not charter_id).
Then recalculate balance = total_amount_due - paid_amount.

CRITICAL: Must use reserve_number NOT charter_id (from copilot instructions Nov 11, 2025)
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', database='almsdata',
    user='postgres', password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("RECALCULATE PAID_AMOUNT AND BALANCE FROM PAYMENTS (BY RESERVE_NUMBER)")
print("=" * 120)
print()

# First, find discrepancies
print("Checking for discrepancies...")
cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        c.paid_amount as stored_paid,
        COALESCE(ps.actual_paid, 0) as actual_paid,
        c.balance as stored_balance,
        c.total_amount_due - COALESCE(ps.actual_paid, 0) as calculated_balance
    FROM charters c
    LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
    WHERE ABS(c.paid_amount - COALESCE(ps.actual_paid, 0)) > 0.02
       OR ABS(c.balance - (c.total_amount_due - COALESCE(ps.actual_paid, 0))) > 0.02
    ORDER BY ABS(c.paid_amount - COALESCE(ps.actual_paid, 0)) DESC
""")
discrepancies = cur.fetchall()

print(f"Found {len(discrepancies)} charters with incorrect paid_amount or balance")
print()

if discrepancies:
    print("Top 20 discrepancies:")
    print(f"{'Charter':<8} {'Reserve':<12} {'Total Due':<12} {'Stored Paid':<12} {'Actual Paid':<12} {'Paid Diff':<12} {'Balance Diff':<12}")
    print("-" * 120)
    
    for disc in discrepancies[:20]:
        charter_id, reserve, total_due, stored_paid, actual_paid, stored_balance, calc_balance = disc
        paid_diff = actual_paid - stored_paid
        balance_diff = calc_balance - stored_balance
        print(f"{charter_id:<8} {reserve:<12} ${total_due:>10,.2f} ${stored_paid:>10,.2f} ${actual_paid:>10,.2f} ${paid_diff:>10,.2f} ${balance_diff:>10,.2f}")
    
    if len(discrepancies) > 20:
        print(f"... and {len(discrepancies) - 20} more")
    
    print()
    print("=" * 120)
    print("DRY RUN - No changes made")
    print("Run with --apply to fix these discrepancies")
    print("=" * 120)
    
    import sys
    if '--apply' in sys.argv:
        print()
        print("APPLYING FIXES...")
        print()
        
        # Create backup
        backup_table = f"charters_paid_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cur.execute(f"""
            CREATE TABLE {backup_table} AS 
            SELECT charter_id, reserve_number, paid_amount, balance 
            FROM charters
        """)
        print(f"✓ Backup created: {backup_table}")
        
        # Update paid_amount and balance using reserve_number
        cur.execute("""
            WITH payment_sums AS (
                SELECT 
                    reserve_number,
                    ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number IS NOT NULL
                GROUP BY reserve_number
            )
            UPDATE charters c
            SET 
                paid_amount = COALESCE(ps.actual_paid, 0),
                balance = c.total_amount_due - COALESCE(ps.actual_paid, 0)
            FROM payment_sums ps
            WHERE c.reserve_number = ps.reserve_number
              AND (ABS(c.paid_amount - ps.actual_paid) > 0.02
                   OR ABS(c.balance - (c.total_amount_due - ps.actual_paid)) > 0.02)
        """)
        updated_count = cur.rowcount
        conn.commit()
        
        print(f"✓ Updated {updated_count} charters")
        print()
        
        # Verify
        cur.execute("""
            WITH payment_sums AS (
                SELECT 
                    reserve_number,
                    ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number IS NOT NULL
                GROUP BY reserve_number
            )
            SELECT COUNT(*)
            FROM charters c
            LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
            WHERE ABS(c.paid_amount - COALESCE(ps.actual_paid, 0)) > 0.02
               OR ABS(c.balance - (c.total_amount_due - COALESCE(ps.actual_paid, 0))) > 0.02
        """)
        remaining = cur.fetchone()[0]
        
        print("=" * 120)
        if remaining == 0:
            print("✓ SUCCESS! All paid_amount and balance fields now match actual payments")
        else:
            print(f"⚠️  WARNING: {remaining} charters still have discrepancies")
        print("=" * 120)
        print(f"Backup table: {backup_table}")
        print(f"Rollback: UPDATE charters c SET paid_amount = b.paid_amount, balance = b.balance FROM {backup_table} b WHERE c.charter_id = b.charter_id;")
else:
    print("✅ All paid_amount and balance fields are correct!")

cur.close()
conn.close()
