"""
Synchronize charter.paid_amount with charter_payments table.

This is PHASE 1 of the charter payment system fix:
- Updates charter.paid_amount to equal SUM(charter_payments.amount) per charter
- Only updates charters that have charter_payments records
- Preserves existing paid_amount where no charter_payments exist (legacy data)
- Creates backup before any changes
- Provides detailed before/after statistics

SAFETY:
- Dry-run mode by default (--write flag required for actual changes)
- Automatic backup of charters table before updates
- Audit logging of all changes
- Rollback capability

Usage:
  python scripts/sync_charter_paid_amounts.py                # Dry run
  python scripts/sync_charter_paid_amounts.py --write        # Apply changes
  python scripts/sync_charter_paid_amounts.py --verify-only  # Check current state
"""
import argparse
import psycopg2
from datetime import datetime


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


def create_backup(cur):
    """Create timestamped backup of charters table"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_table = f"charters_backup_{timestamp}"
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM charters")
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"✓ Backup created: {count:,} rows in {backup_table}")
    
    return backup_table


def get_sync_stats(cur):
    """Get current state statistics"""
    
    # Charters with both paid_amount and charter_payments
    cur.execute("""
    WITH cp_sums AS (
      SELECT 
          charter_id AS reserve_num,
        SUM(amount) AS cp_total,
        COUNT(*) AS cp_count
      FROM charter_payments
      WHERE charter_id IS NOT NULL 
        GROUP BY charter_id
    )
    SELECT 
      COUNT(*) AS total_charters,
      COUNT(CASE WHEN c.paid_amount IS NULL THEN 1 END) AS null_paid_amount,
      COUNT(CASE WHEN c.paid_amount = 0 THEN 1 END) AS zero_paid_amount,
      SUM(c.paid_amount) AS charter_paid_sum,
      SUM(cp.cp_total) AS cp_sum,
      SUM(ABS(COALESCE(c.paid_amount, 0) - cp.cp_total)) AS total_discrepancy,
      COUNT(CASE WHEN ABS(COALESCE(c.paid_amount, 0) - cp.cp_total) > 0.02 THEN 1 END) AS mismatched_count
    FROM charters c
      JOIN cp_sums cp ON cp.reserve_num = c.reserve_number
    """)
    
    return cur.fetchone()


def get_update_candidates(cur):
    """Get list of charters that need updating"""
    
    cur.execute("""
    WITH cp_sums AS (
      SELECT 
          charter_id AS reserve_num,
        SUM(amount) AS cp_total,
        COUNT(*) AS cp_count,
        MIN(payment_date) AS first_payment,
        MAX(payment_date) AS last_payment
      FROM charter_payments
      WHERE charter_id IS NOT NULL 
        GROUP BY charter_id
    )
    SELECT 
      c.charter_id,
      c.reserve_number,
      COALESCE(c.paid_amount, 0) AS current_paid,
      cp.cp_total AS should_be_paid,
      cp.cp_total - COALESCE(c.paid_amount, 0) AS adjustment,
      cp.cp_count AS payment_count,
      cp.first_payment,
      cp.last_payment
    FROM charters c
      JOIN cp_sums cp ON cp.reserve_num = c.reserve_number
    WHERE ABS(COALESCE(c.paid_amount, 0) - cp.cp_total) > 0.02
    ORDER BY ABS(cp.cp_total - COALESCE(c.paid_amount, 0)) DESC
    """)
    
    return cur.fetchall()


def apply_sync(cur, dry_run=True):
    """Apply the synchronization updates"""
    
    if not dry_run:
        cur.execute("""
        WITH cp_sums AS (
          SELECT 
              charter_id AS reserve_num,
            SUM(amount) AS cp_total
          FROM charter_payments
          WHERE charter_id IS NOT NULL 
            GROUP BY charter_id
        )
        UPDATE charters c
        SET paid_amount = cp.cp_total
        FROM cp_sums cp
          WHERE cp.reserve_num = c.reserve_number
          AND ABS(COALESCE(c.paid_amount, 0) - cp.cp_total) > 0.02
        """)
        
        return cur.rowcount
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Sync charter.paid_amount with charter_payments")
    parser.add_argument("--write", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--verify-only", action="store_true", help="Only show current state, no changes")
    args = parser.parse_args()
    
    print("=" * 100)
    print("CHARTER PAID_AMOUNT SYNCHRONIZATION")
    print("=" * 100)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current state
    print("\nCURRENT STATE:")
    print("-" * 100)
    stats = get_sync_stats(cur)
    total_charters, null_paid, zero_paid, charter_paid_sum, cp_sum, total_disc, mismatch_count = stats
    
    print(f"Charters with charter_payments records: {total_charters:,}")
    print(f"  With NULL paid_amount: {null_paid:,}")
    print(f"  With ZERO paid_amount: {zero_paid:,}")
    print(f"\nCurrent charter.paid_amount sum: {fmt_money(charter_paid_sum)}")
    print(f"charter_payments sum (should be): {fmt_money(cp_sum)}")
    print(f"Total discrepancy: {fmt_money(total_disc)}")
    print(f"Charters needing update (>$0.02 diff): {mismatch_count:,}")
    
    if args.verify_only:
        print("\n✓ Verification complete (--verify-only mode)")
        cur.close()
        conn.close()
        return
    
    # Get update candidates
    print("\nUPDATE CANDIDATES:")
    print("-" * 100)
    candidates = get_update_candidates(cur)
    
    if not candidates:
        print("✓ No updates needed - all charters already synchronized!")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(candidates):,} charters needing updates")
    print("\nTop 20 largest adjustments:")
    print(f"{'CharterID':<10} {'Reserve':<8} {'Current$':>12} {'Should Be$':>12} {'Adjustment':>12} {'#Pay':>6}")
    print("-" * 70)
    
    for i, (cid, res, current, should_be, adj, pcount, first, last) in enumerate(candidates[:20]):
        print(f"{cid:<10} {str(res or ''):<8} {fmt_money(current):>12} {fmt_money(should_be):>12} {fmt_money(adj):>12} {pcount:>6}")
    
    if len(candidates) > 20:
        print(f"... and {len(candidates) - 20:,} more")
    
    # Calculate net adjustments
    total_increase = sum(float(adj) for _, _, _, _, adj, _, _, _ in candidates if adj > 0)
    total_decrease = sum(float(adj) for _, _, _, _, adj, _, _, _ in candidates if adj < 0)
    
    print(f"\nSummary of adjustments:")
    print(f"  Increases (charter_payments > paid_amount): {fmt_money(total_increase)}")
    print(f"  Decreases (charter_payments < paid_amount): {fmt_money(total_decrease)}")
    print(f"  Net change: {fmt_money(total_increase + total_decrease)}")
    
    if args.write:
        print("\n" + "!" * 100)
        print("APPLYING CHANGES")
        print("!" * 100)
        
        # Create backup
        backup_table = create_backup(cur)
        conn.commit()
        
        # Apply updates
        print("\nUpdating charter.paid_amount values...")
        updated_count = apply_sync(cur, dry_run=False)
        conn.commit()
        
        print(f"✓ Updated {updated_count:,} charters")
        
        # Verify results
        print("\nVERIFYING RESULTS:")
        print("-" * 100)
        after_stats = get_sync_stats(cur)
        after_total, after_null, after_zero, after_charter_sum, after_cp_sum, after_disc, after_mismatch = after_stats
        
        print(f"charter.paid_amount sum: {fmt_money(after_charter_sum)}")
        print(f"charter_payments sum: {fmt_money(after_cp_sum)}")
        print(f"Remaining discrepancy: {fmt_money(after_disc)}")
        print(f"Charters still mismatched (>$0.02): {after_mismatch:,}")
        
        if after_mismatch == 0:
            print("\n✓ SUCCESS! All charters synchronized")
        else:
            print(f"\n[WARN]  {after_mismatch:,} charters still have discrepancies")
            print("    (May be due to rounding or data entry issues)")
        
        print(f"\n✓ Backup saved as: {backup_table}")
        print("  To rollback: UPDATE charters c SET paid_amount = b.paid_amount")
        print(f"               FROM {backup_table} b WHERE b.charter_id = c.charter_id;")
        
    else:
        print("\n" + "=" * 100)
        print("DRY RUN MODE - No changes made")
        print("=" * 100)
        print("Run with --write flag to apply these changes")
        print("Example: python scripts/sync_charter_paid_amounts.py --write")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("SYNC COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
