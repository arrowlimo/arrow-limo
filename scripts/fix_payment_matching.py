#!/usr/bin/env python
"""
COMPREHENSIVE PAYMENT MATCHING FIX

This script will:
1. Backup charter_payments table
2. Correct 20,760 mismatched payment applications (move to correct charter)
3. Apply 1,195 unmatched payments with reserve_numbers
4. Re-sync charters.paid_amount from corrected charter_payments
5. Recalculate balances

Usage:
  python -X utf8 scripts/fix_payment_matching.py              # dry run, show what would change
  python -X utf8 scripts/fix_payment_matching.py --write      # apply all fixes
"""
import argparse
from datetime import datetime
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def create_backup(cur):
    """Create timestamped backup of charter_payments."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"charter_payments_backup_{ts}"
    print(f"\nCreating backup: {backup}")
    cur.execute(f"CREATE TABLE {backup} AS SELECT * FROM charter_payments")
    cur.execute(f"SELECT COUNT(*) FROM {backup}")
    count = cur.fetchone()[0]
    print(f"✓ Backup created: {count:,} rows in {backup}")
    return backup


def fix_mismatched_payments(cur, write=False):
    """Fix payments applied to wrong charter by updating charter_id to match payments.reserve_number."""
    print("\n" + "=" * 80)
    print("FIXING MISMATCHED PAYMENT APPLICATIONS")
    print("=" * 80)
    
    # First, get count and details
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(cp.amount),0)
        FROM charter_payments cp
        JOIN payments p ON p.payment_id = cp.payment_id
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND cp.charter_id <> p.reserve_number
    """)
    mismatch_count, mismatch_sum = cur.fetchone()
    
    print(f"\nMismatched payments found: {mismatch_count:,}")
    print(f"Total amount: ${float(mismatch_sum):,.2f}")
    
    if mismatch_count == 0:
        print("No mismatches to fix.")
        return 0
    
    # Sample before
    print("\nSample (first 10 before fix):")
    cur.execute("""
        SELECT cp.payment_id, cp.charter_id AS wrong_charter, p.reserve_number AS correct_charter,
               cp.amount
        FROM charter_payments cp
        JOIN payments p ON p.payment_id = cp.payment_id
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND cp.charter_id <> p.reserve_number
        ORDER BY cp.amount DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(f"  PID {row[0]}: {row[1]} → {row[2]} (${float(row[3]):,.2f})")
    
    if write:
        print("\nApplying fix...")
        cur.execute("""
            UPDATE charter_payments cp
            SET charter_id = p.reserve_number
            FROM payments p
            WHERE p.payment_id = cp.payment_id
            AND p.reserve_number IS NOT NULL 
            AND p.reserve_number <> ''
            AND cp.charter_id <> p.reserve_number
        """)
        updated = cur.rowcount
        print(f"✓ Updated {updated:,} charter_payments to correct charter_id")
        return updated
    else:
        print(f"\nDRY RUN: Would update {mismatch_count:,} records")
        return 0


def apply_unmatched_payments(cur, write=False):
    """Insert unmatched payments with reserve_numbers into charter_payments."""
    print("\n" + "=" * 80)
    print("APPLYING UNMATCHED PAYMENTS")
    print("=" * 80)
    
    # Get unmatched with reserve_numbers
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, 
               COALESCE(p.payment_amount, p.amount) AS amt,
               p.payment_date, p.payment_method
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
        AND COALESCE(p.payment_amount, p.amount, 0) <> 0
    """)
    unmatched = cur.fetchall()
    
    print(f"\nUnmatched payments with reserve_numbers: {len(unmatched):,}")
    if len(unmatched) > 0:
        total_amt = sum(float(row[2]) if row[2] else 0 for row in unmatched)
        print(f"Total amount: ${total_amt:,.2f}")
        
        print("\nSample (first 10):")
        for row in unmatched[:10]:
            print(f"  PID {row[0]}: Reserve {row[1]}, ${float(row[2]) if row[2] else 0:.2f}, {row[3]}, {row[4]}")
    
    if write and len(unmatched) > 0:
        print("\nInserting into charter_payments...")
        inserted = 0
        for pid, reserve, amt, date, method in unmatched:
            if amt is None or amt == 0:
                continue
            try:
                cur.execute("""
                    INSERT INTO charter_payments 
                    (payment_id, charter_id, amount, payment_date, payment_method, source, imported_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (pid, reserve, amt, date, method or 'unknown', 'fix_script'))
                inserted += 1
            except Exception as e:
                print(f"  Error inserting PID {pid}: {e}")
        
        print(f"✓ Inserted {inserted:,} new charter_payments")
        return inserted
    else:
        print(f"\nDRY RUN: Would insert {len(unmatched):,} new records")
        return 0


def resync_paid_amounts(cur, write=False):
    """Re-sync charters.paid_amount from charter_payments."""
    print("\n" + "=" * 80)
    print("RE-SYNCING PAID AMOUNTS")
    print("=" * 80)
    
    # Get current state
    cur.execute("""
        WITH payment_sums AS (
            SELECT charter_id::text AS reserve_number, 
                   COALESCE(SUM(amount),0) AS cp_sum
            FROM charter_payments
            GROUP BY charter_id
        )
        SELECT COUNT(*), 
               COALESCE(SUM(c.paid_amount),0) AS current_sum,
               COALESCE(SUM(ps.cp_sum),0) AS target_sum
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number::text
        WHERE ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.cp_sum,0)) > 0.02
    """)
    need_update, current_sum, target_sum = cur.fetchone()
    
    print(f"\nCharters needing paid_amount update: {need_update:,}")
    print(f"Current paid_amount sum: ${float(current_sum):,.2f}")
    print(f"Target (charter_payments sum): ${float(target_sum):,.2f}")
    
    if need_update == 0:
        print("All paid_amounts already in sync.")
        return 0
    
    if write:
        print("\nUpdating paid_amounts...")
        cur.execute("""
            WITH payment_sums AS (
                SELECT charter_id::text AS reserve_number, 
                       COALESCE(SUM(amount),0) AS cp_sum
                FROM charter_payments
                GROUP BY charter_id
            )
            UPDATE charters c
            SET paid_amount = ps.cp_sum
            FROM payment_sums ps
            WHERE ps.reserve_number = c.reserve_number::text
            AND ABS(COALESCE(c.paid_amount,0) - ps.cp_sum) > 0.02
        """)
        updated = cur.rowcount
        print(f"✓ Updated {updated:,} charters")
        return updated
    else:
        print(f"\nDRY RUN: Would update {need_update:,} charters")
        return 0


def recalculate_balances(cur, write=False):
    """Recalculate charter balances after paid_amount sync."""
    print("\n" + "=" * 80)
    print("RECALCULATING BALANCES")
    print("=" * 80)
    
    # Check how many need update
    cur.execute("""
        WITH targets AS (
            SELECT charter_id,
                   ROUND(COALESCE(total_amount_due,0) - COALESCE(paid_amount,0), 2) AS target_balance
            FROM charters
        )
        SELECT COUNT(*),
               COALESCE(SUM(c.balance),0) AS current_sum,
               COALESCE(SUM(t.target_balance),0) AS target_sum
        FROM charters c
        JOIN targets t USING (charter_id)
        WHERE ABS(COALESCE(c.balance,0) - t.target_balance) > 0.02
    """)
    need_update, current_sum, target_sum = cur.fetchone()
    
    print(f"\nCharters needing balance update: {need_update:,}")
    print(f"Current balance sum: ${float(current_sum):,.2f}")
    print(f"Target balance sum: ${float(target_sum):,.2f}")
    
    if need_update == 0:
        print("All balances already correct.")
        return 0
    
    if write:
        print("\nUpdating balances...")
        cur.execute("""
            WITH targets AS (
                SELECT charter_id,
                       ROUND(COALESCE(total_amount_due,0) - COALESCE(paid_amount,0), 2) AS target_balance
                FROM charters
            )
            UPDATE charters c
            SET balance = t.target_balance
            FROM targets t
            WHERE c.charter_id = t.charter_id
            AND ABS(COALESCE(c.balance,0) - t.target_balance) > 0.02
        """)
        updated = cur.rowcount
        print(f"✓ Updated {updated:,} charter balances")
        return updated
    else:
        print(f"\nDRY RUN: Would update {need_update:,} balances")
        return 0


def verify_results(cur):
    """Verify the fixes worked."""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    # Check remaining mismatches
    cur.execute("""
        SELECT COUNT(*)
        FROM charter_payments cp
        JOIN payments p ON p.payment_id = cp.payment_id
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND cp.charter_id <> p.reserve_number
    """)
    remaining_mismatches = cur.fetchone()[0]
    
    # Check remaining unmatched with reserve_number
    cur.execute("""
        SELECT COUNT(*)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
    """)
    remaining_unmatched = cur.fetchone()[0]
    
    # Check balance distribution
    cur.execute("""
        SELECT 
          COUNT(*) FILTER(WHERE balance > 0.01) AS positive,
          COUNT(*) FILTER(WHERE balance < -0.01) AS negative,
          COUNT(*) FILTER(WHERE ABS(balance) <= 0.01) AS zero,
          COALESCE(SUM(balance) FILTER(WHERE balance > 0.01), 0) AS positive_sum,
          COALESCE(SUM(balance) FILTER(WHERE balance < -0.01), 0) AS negative_sum
        FROM charters
        WHERE (cancelled IS NULL OR cancelled = FALSE)
    """)
    positive, negative, zero, pos_sum, neg_sum = cur.fetchone()
    
    print(f"\nRemaining mismatched payments: {remaining_mismatches:,}")
    print(f"Remaining unmatched with reserve_number: {remaining_unmatched:,}")
    print(f"\nNon-cancelled charter balance distribution:")
    print(f"  Positive (owed to you): {positive:,} (${float(pos_sum):,.2f})")
    print(f"  Negative (credits): {negative:,} (${float(neg_sum):,.2f})")
    print(f"  Zero: {zero:,}")
    
    if remaining_mismatches == 0 and remaining_unmatched == 0:
        print("\n✓ SUCCESS! All payments correctly matched.")
    else:
        print(f"\n⚠ Still have issues to investigate.")


def main():
    parser = argparse.ArgumentParser(description="Fix payment matching issues")
    parser.add_argument("--write", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    print("=" * 80)
    print("PAYMENT MATCHING COMPREHENSIVE FIX")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    
    if args.write:
        backup = create_backup(cur)
    
    # Step 1: Fix mismatched
    fixed_count = fix_mismatched_payments(cur, write=args.write)
    
    # Step 2: Apply unmatched
    applied_count = apply_unmatched_payments(cur, write=args.write)
    
    # Step 3: Re-sync paid amounts
    synced_count = resync_paid_amounts(cur, write=args.write)
    
    # Step 4: Recalculate balances
    balanced_count = recalculate_balances(cur, write=args.write)
    
    # Step 5: Verify
    if args.write:
        conn.commit()
        verify_results(cur)
        print(f"\n✓ All changes committed")
        print(f"\nBackup: {backup}")
        print(f"Rollback SQL:")
        print(f"  DROP TABLE IF EXISTS charter_payments;")
        print(f"  ALTER TABLE {backup} RENAME TO charter_payments;")
    else:
        conn.rollback()
        print("\n" + "=" * 80)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 80)
        print("To apply fixes, run with --write flag")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
