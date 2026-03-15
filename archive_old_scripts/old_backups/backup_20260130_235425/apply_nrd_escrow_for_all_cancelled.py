import argparse
from decimal import Decimal
import psycopg2
from datetime import datetime


def get_conn():
    return psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')


def ensure_charges_backup(cur, backup_table):
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {backup_table} AS 
        SELECT * FROM charter_charges WHERE 1=0
        """
    )


def find_cancelled_with_deposits(cur):
    cur.execute(
        """
        SELECT c.charter_id,
               c.reserve_number,
               COALESCE(SUM(CASE WHEN p.amount > 0 THEN p.amount ELSE 0 END), 0) AS total_payments,
               COUNT(*) FILTER (WHERE p.amount > 0) AS payment_count
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.cancelled = TRUE
        GROUP BY c.charter_id, c.reserve_number
        HAVING COALESCE(SUM(CASE WHEN p.amount > 0 THEN p.amount ELSE 0 END), 0) > 0
        ORDER BY c.reserve_number
        """
    )
    rows = cur.fetchall()
    return [
        {
            'charter_id': r[0],
            'reserve_number': r[1],
            'total_payments': Decimal(str(r[2] or 0)),
            'payment_count': r[3],
        }
        for r in rows
    ]


def get_existing_nrd(cur, reserve_number):
    cur.execute(
        """
        SELECT COALESCE(SUM(credit_amount),0), COALESCE(SUM(remaining_balance),0)
        FROM charter_credit_ledger
        WHERE source_reserve_number = %s AND credit_reason = 'NRD_ESCROW'
        """,
        (reserve_number,),
    )
    amt_sum, rem_sum = cur.fetchone()
    return Decimal(str(amt_sum or 0)), Decimal(str(rem_sum or 0))


def backup_charges(cur, backup_table, reserve_number):
    cur.execute(f"INSERT INTO {backup_table} SELECT * FROM charter_charges WHERE reserve_number = %s", (reserve_number,))


def delete_charges(cur, reserve_number):
    cur.execute("DELETE FROM charter_charges WHERE reserve_number = %s", (reserve_number,))
    return cur.rowcount


def insert_credit(cur, reserve_number, charter_id, amount):
    cur.execute(
        """
        INSERT INTO charter_credit_ledger (
            source_reserve_number, source_charter_id, client_id, credit_amount, credit_reason, remaining_balance,
            created_date, applied_date, applied_to_reserve_number, applied_to_charter_id, notes, created_by
        ) VALUES (%s, %s, NULL, %s, %s, %s, NOW(), NULL, NULL, NULL, %s, %s)
        RETURNING credit_id
        """,
        (
            reserve_number,
            int(charter_id) if str(charter_id).isdigit() else None,
            amount,
            'NRD_ESCROW',
            amount,
            'Non-refundable deposit held in escrow (kept, not refunded).',
            'NRD_ESCROW_SCRIPT',
        ),
    )
    return cur.fetchone()[0]


def annotate_payments(cur, reserve_number, credit_id=None):
    tag = f" | NRD_ESCROW credit_id={credit_id}" if credit_id else " | NRD_ESCROW"
    cur.execute(
        """
        UPDATE payments
        SET notes = CONCAT(COALESCE(notes,''), %s)
        WHERE reserve_number = %s AND (notes IS NULL OR notes NOT ILIKE %s)
        """,
        (tag, reserve_number, '%NRD_ESCROW%'),
    )
    return cur.rowcount


def zero_charter(cur, reserve_number):
    cur.execute(
        """
        UPDATE charters
        SET total_amount_due = 0.00, paid_amount = 0.00, balance = 0.00, cancelled = TRUE, updated_at = NOW()
        WHERE reserve_number = %s
        """,
        (reserve_number,),
    )
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description='Escrow all deposits for cancelled charters; keep payments, remove charges, credit ledger, zero charter totals.')
    parser.add_argument('--write', action='store_true', help='Apply changes (omit for dry-run).')
    args = parser.parse_args()

    conn = get_conn()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        backup_table = f"charter_charges_backup_nrd_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ensure_charges_backup(cur, backup_table)

        candidates = find_cancelled_with_deposits(cur)
        print(f"Cancelled with deposits: {len(candidates)}")
        total_delta = Decimal('0')
        processed = 0
        for row in candidates:
            rn = row['reserve_number']
            cid = row['charter_id']
            total_pay = row['total_payments']
            existing_amt, existing_rem = get_existing_nrd(cur, rn)
            delta = total_pay - existing_amt
            print(f"\n{rn} (charter_id={cid}) pay_total={total_pay} existing_nrd_amt={existing_amt} delta={delta}")

            if not args.write:
                print(f"DRY-RUN: would backup charges to {backup_table}, delete charges, insert/top-up NRD {delta if delta>0 else 0}, annotate payments, zero charter.")
                continue

            backup_charges(cur, backup_table, rn)
            _ = delete_charges(cur, rn)
            credit_id = None
            if delta > Decimal('0.004'):
                credit_id = insert_credit(cur, rn, cid, delta)
                total_delta += delta
            ann = annotate_payments(cur, rn, credit_id)
            zero_charter(cur, rn)
            processed += 1
            print(f"Applied: credit_id={credit_id} annotated={ann}")

        if args.write:
            conn.commit()
            print(f"\n=== Committed. Processed={processed}, total_new_escrow={total_delta} ===")
        else:
            conn.rollback()
            print("\n=== DRY-RUN only (no changes) ===")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
