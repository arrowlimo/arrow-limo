"""
Infer and insert missing charter charges for pre-2025 charters with payments but no charges (dry-run by default).

Rules:
- Candidate: pre-2025, total_amount_due = 0, (paid_amount > 0 OR balance > 0), and no charter_charges present.
- Insert a single charter_charge: amount = paid_amount + balance (expected total). Description: 'Inferred charter total (pre-2025)'.
- Idempotent: skip if a charge with this description already exists for the charter.
- After insert (if write), update total_amount_due from charges and recompute balance = total - paid (by reserve_number).
"""
import os
import sys
import argparse
from datetime import date
import psycopg2

CUTOFF = date(2025, 1, 1)


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def table_exists(cur, name: str) -> bool:
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)", (name,))
    return cur.fetchone()[0]


def columns(cur, table: str):
    cur.execute(
        """SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply inserts and updates')
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'charters') or not table_exists(cur, 'charter_charges') or not table_exists(cur, 'payments'):
        print('Required tables not present (charters, charter_charges, payments).')
        sys.exit(2)

    ccols = columns(cur, 'charters')
    chg_cols = columns(cur, 'charter_charges')
    pcols = columns(cur, 'payments')

    charter_date_col = 'charter_date' if 'charter_date' in ccols else ('reservation_time' if 'reservation_time' in ccols else None)
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    if not charter_date_col or not amount_col:
        print('Missing needed columns.')
        sys.exit(2)

    # Determine join strategy for charter_charges
    join_on_charter_id = 'charter_id' in ccols and 'charter_id' in chg_cols
    join_on_rn = 'reserve_number' in ccols and 'reserve_number' in chg_cols

    # Candidates: pre-2025, total_due = 0, paid>0 or balance>0, and no charges
    cur.execute(
        f"""
        WITH c AS (
          SELECT charter_id, reserve_number,
                 CAST({charter_date_col} AS DATE) AS cdate,
                 ROUND(COALESCE(total_amount_due,0)::numeric,2) AS total_due,
                 ROUND(COALESCE(paid_amount,0)::numeric,2) AS paid,
                 ROUND(COALESCE(balance,0)::numeric,2) AS bal
          FROM charters
          WHERE CAST({charter_date_col} AS DATE) < %s
            AND ROUND(COALESCE(total_amount_due,0)::numeric,2) = 0
            AND (ROUND(COALESCE(paid_amount,0)::numeric,2) > 0 OR ROUND(COALESCE(balance,0)::numeric,2) > 0)
        ), present AS (
          SELECT {('cc.charter_id' if join_on_charter_id else 'cc.reserve_number')} AS key, COUNT(*) AS n
          FROM charter_charges cc
          GROUP BY 1
        )
        SELECT c.charter_id, c.reserve_number, c.cdate, c.paid, c.bal,
               (c.paid + c.bal) AS inferred_total,
               COALESCE(present.n, 0) AS charges_count
        FROM c
        LEFT JOIN present ON present.key = {('c.charter_id' if join_on_charter_id else 'c.reserve_number')}
        WHERE COALESCE(present.n, 0) = 0
        ORDER BY c.cdate ASC
        """,
        (CUTOFF,)
    )
    candidates = cur.fetchall()
    print(f"Candidates with no charges: {len(candidates)}")
    if not args.write:
        conn.rollback()
        print('Dry-run complete. No inserts performed.')
        return

    # Insert charges
    inserted = 0
    for charter_id, rn, cdate, paid, bal, inferred_total, charge_count in candidates:
        desc = 'Inferred charter total (pre-2025)'
        # Idempotency: check charge exists with this desc
        if join_on_charter_id:
            cur.execute(
                "SELECT 1 FROM charter_charges WHERE charter_id = %s AND description = %s LIMIT 1",
                (charter_id, desc)
            )
        else:
            cur.execute(
                "SELECT 1 FROM charter_charges WHERE reserve_number = %s AND description = %s LIMIT 1",
                (rn, desc)
            )
        if cur.fetchone():
            continue
        # Build insert
        cols = []
        vals = []
        if join_on_charter_id:
            cols += ['charter_id']
            vals += [charter_id]
        elif 'reserve_number' in chg_cols:
            cols += ['reserve_number']
            vals += [rn]
        if 'description' in chg_cols:
            cols += ['description']
            vals += [desc]
        if 'amount' in chg_cols:
            cols += ['amount']
            vals += [float(inferred_total)]
        cur.execute(
            f"INSERT INTO charter_charges ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))})",
            vals
        )
        inserted += 1

    # Recalculate totals and balances for affected charters
    # Totals from charges
    cur.execute(
        f"""
        WITH charges AS (
          SELECT c.reserve_number, ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) AS charges_sum
          FROM charters c
          LEFT JOIN charter_charges cc ON {('cc.charter_id = c.charter_id' if join_on_charter_id else 'cc.reserve_number = c.reserve_number')}
          WHERE CAST(c.{charter_date_col} AS DATE) < %s
          GROUP BY c.reserve_number
        )
        UPDATE charters c
        SET total_amount_due = ch.charges_sum
        FROM charges ch
        WHERE c.reserve_number = ch.reserve_number
        """,
        (CUTOFF,)
    )

    # Balance from payments
    cur.execute(
        """
        WITH payment_sums AS (
          SELECT reserve_number, ROUND(SUM(COALESCE(amount, payment_amount, 0))::numeric, 2) AS actual_paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.actual_paid,
            balance = ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ps.actual_paid
        FROM payment_sums ps
        WHERE c.reserve_number = ps.reserve_number
        """
    )

    conn.commit()
    print(f"Inserted charter_charges: {inserted}")
    print("Recalculated totals and balances for pre-2025 charters.")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
