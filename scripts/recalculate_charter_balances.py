#!/usr/bin/env python3
"""
Recalculate charter paid_amount and balance using reserve_number-based payment sums.

This uses the business key reserve_number to avoid missing payments where charter_id is NULL.
Safe to run after LMS sync/mismatch fixes.
"""
import os
import sys
import psycopg2

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

SQL = """
WITH payment_sums AS (
    SELECT 
        reserve_number,
        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS actual_paid
    FROM payments
    WHERE reserve_number IS NOT NULL
    GROUP BY reserve_number
)
UPDATE charters c
SET paid_amount = ps.actual_paid,
    balance = c.total_amount_due - ps.actual_paid
FROM payment_sums ps
WHERE c.reserve_number = ps.reserve_number;
"""

def main():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cur = conn.cursor()
        cur.execute(SQL)
        updated = cur.rowcount
        conn.commit()
        print(f"Recalculated balances for {updated} charters using reserve_number sums.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if cur:
                cur.close()
            if conn:
                conn.close()
        except Exception:
            pass

if __name__ == '__main__':
    main()
"""
Recalculate charter.balance with safeguards.

Formula base: expected_balance_raw = total_amount_due - paid_amount

Enhancements:
1. Snap tiny residuals: if abs(expected_balance_raw) <= 0.01 -> 0.00
2. Clamp overpayments optionally: if --clamp-overpay and expected_balance_raw < 0 -> set balance = 0.00 (treat as credit held externally)
3. Export credits (overpayments) to reports/charter_overpayment_credits.csv when clamping enabled
4. Preserve only rows with > $0.02 difference for update
5. Backup original balance column before changes

Usage:
  python -X utf8 scripts/recalculate_charter_balances.py                     # dry run
  python -X utf8 scripts/recalculate_charter_balances.py --write             # apply standard
  python -X utf8 scripts/recalculate_charter_balances.py --write --clamp-overpay  # apply with clamping
"""
import argparse
from datetime import datetime
import os
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


def create_backup(cur):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"charters_balance_backup_{ts}"
    print(f"\nCreating backup: {backup}")
    cur.execute(f"CREATE TABLE {backup} AS SELECT charter_id, balance FROM charters")
    cur.execute(f"SELECT COUNT(*) FROM {backup}")
    count = cur.fetchone()[0]
    print(f"✓ Backup created: {count:,} rows in {backup}")
    return backup


def get_stats(cur):
    cur.execute(
        """
        WITH targets AS (
          SELECT 
            charter_id,
            ROUND(COALESCE(total_amount_due,0) - COALESCE(paid_amount,0), 2) AS target_balance
          FROM charters
        )
        SELECT 
          COUNT(*) AS total_charters,
          SUM(CASE WHEN ABS(COALESCE(c.balance,0) - t.target_balance) > 0.02 THEN 1 ELSE 0 END) AS need_update,
          SUM(COALESCE(c.balance,0)) AS current_balance_sum,
          SUM(t.target_balance) AS target_balance_sum
        FROM charters c
        JOIN targets t USING (charter_id)
        """
    )
    return cur.fetchone()


def get_candidates(cur, limit=20):
    cur.execute(
        """
        WITH targets AS (
          SELECT 
            charter_id,
            reserve_number,
            ROUND(COALESCE(total_amount_due,0) - COALESCE(paid_amount,0), 2) AS target_balance
          FROM charters
        )
        SELECT 
          c.charter_id,
          c.reserve_number,
          COALESCE(c.balance,0) AS current_balance,
          t.target_balance,
          (t.target_balance - COALESCE(c.balance,0)) AS adjustment
        FROM charters c
        JOIN targets t USING (charter_id)
        WHERE ABS(COALESCE(c.balance,0) - t.target_balance) > 0.02
        ORDER BY ABS(t.target_balance - COALESCE(c.balance,0)) DESC
        LIMIT %s
        """,
        (limit,),
    )
    return cur.fetchall()


def apply_updates(cur, dry_run=True, clamp_overpay=False):
    """Perform balance updates and return (updated_count, clamped_count).

    In dry_run mode no changes are applied and (0,0) is returned.
    """
    if dry_run:
        return 0, 0

    cur.execute(
        """
        WITH raw AS (
          SELECT 
            charter_id,
            COALESCE(total_amount_due,0) - COALESCE(paid_amount,0) AS raw_balance
          FROM charters
        ),
        targets AS (
          SELECT 
            charter_id,
            CASE 
              WHEN ABS(ROUND(raw_balance, 2)) <= 0.01 THEN 0.00
              ELSE ROUND(raw_balance, 2)
            END AS snapped_balance,
            raw_balance
          FROM raw
        ),
        clamped AS (
          SELECT 
            charter_id,
            snapped_balance,
            raw_balance,
            CASE 
              WHEN %(clamp)s AND snapped_balance < 0 THEN 0.00
              ELSE snapped_balance
            END AS final_balance,
            CASE WHEN snapped_balance < 0 THEN 1 ELSE 0 END AS is_overpay
          FROM targets
        ),
        to_update AS (
          SELECT c.charter_id, ch.balance AS current_balance, c.final_balance, c.raw_balance, c.is_overpay
          FROM clamped c
          JOIN charters ch ON ch.charter_id = c.charter_id
          WHERE ch.balance IS DISTINCT FROM c.final_balance
            AND ABS(COALESCE(ch.balance,0) - c.final_balance) > 0.02
        )
        UPDATE charters upd
        SET balance = tu.final_balance
        FROM to_update tu
        WHERE tu.charter_id = upd.charter_id
        RETURNING tu.charter_id, tu.current_balance, tu.final_balance, tu.raw_balance, tu.is_overpay;
        """,
        {"clamp": clamp_overpay},
    )
    updated_rows = cur.fetchall()
    overpay_clamped = sum(1 for r in updated_rows if r[4] == 1 and clamp_overpay)
    return len(updated_rows), overpay_clamped


def main():
    parser = argparse.ArgumentParser(description="Recalculate charter balances")
    parser.add_argument("--write", action="store_true", help="Apply changes")
    parser.add_argument("--clamp-overpay", action="store_true", help="Clamp negative balances to zero and export credit list")
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    print("=" * 100)
    print("CHARTER BALANCE RECALCULATION")
    print("=" * 100)

    total, need_update, curr_sum, target_sum = get_stats(cur)
    print("\nCURRENT STATE:")
    print("-" * 100)
    print(f"Total charters: {total:,}")
    print(f"Charters needing update (> $0.02): {need_update:,}")
    print(f"Current balance sum: {fmt_money(curr_sum)}")
    print(f"Target  balance sum: {fmt_money(target_sum)}")

    print("\nTOP 20 LARGEST ADJUSTMENTS:")
    print("-" * 100)
    rows = get_candidates(cur, limit=20)
    if rows:
        print("Charter  Reserve   Current$    Target$     Adjustment")
        print("-" * 66)
        for cid, res, cur_bal, tgt_bal, adj in rows:
            print(f"{cid:7d}  {res:7s}  {fmt_money(cur_bal):>10s}  {fmt_money(tgt_bal):>10s}  {fmt_money(adj):>10s}")
    else:
        print("No differences above threshold.")

    if args.write:
        print("\nApplying updates...")
        backup = create_backup(cur)
        updated, clamped = apply_updates(cur, dry_run=False, clamp_overpay=args.clamp_overpay)
        conn.commit()
        print(f"✓ Updated {updated:,} charters")
        if args.clamp_overpay:
            print(f"✓ Clamped overpayment balances to zero for {clamped:,} charters (credits exported)")

            # Export credit list (post-update so reflects clamped state)
            cur.execute(
                """
                SELECT charter_id, reserve_number, COALESCE(total_amount_due,0) AS total_due,
                       COALESCE(paid_amount,0) AS paid_amount,
                       (COALESCE(paid_amount,0) - COALESCE(total_amount_due,0)) AS credit
                FROM charters
                WHERE COALESCE(paid_amount,0) > COALESCE(total_amount_due,0)
                ORDER BY credit DESC
                """
            )
            credit_rows = cur.fetchall()
            import csv
            os.makedirs("reports", exist_ok=True)
            credit_path = os.path.join("reports", "charter_overpayment_credits.csv")
            with open(credit_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["charter_id", "reserve_number", "total_due", "paid_amount", "credit_amount"])
                for r in credit_rows:
                    w.writerow(r)
            print(f"✓ Credit list written: {credit_path}")

        # Verification summary
        total2, need_update2, curr_sum2, target_sum2 = get_stats(cur)
        print("\nVERIFICATION:")
        print("-" * 100)
        print(f"Charters still needing update (> $0.02): {need_update2:,}")
        print(f"Current balance sum: {fmt_money(curr_sum2)}")
        print(f"Target  balance sum: {fmt_money(target_sum2)}")
        if need_update2 == 0:
            print("\n✓ SUCCESS! Balances synchronized.")
        print(f"\nBackup saved as: {backup}")
        print("Rollback (balance only):")
        print(f"  UPDATE charters c SET balance = b.balance FROM {backup} b WHERE b.charter_id = c.charter_id;")
    else:
        print("\nDRY RUN - No changes made. Run with --write to apply.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
