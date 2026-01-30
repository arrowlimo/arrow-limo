#!/usr/bin/env python3
import argparse
from datetime import datetime
import psycopg2

RESERVES = ["019223", "019224"]
TOTAL_AMOUNT = 1000.00
SPLIT_AMOUNTS = [500.00, 500.00]
PAYMENT_METHOD = 'credit_card'
CARD_LAST4 = '2198'
AUTH_CODE = '#tGl6'
NOTES = 'Retainer split $1,000 across 019223 and 019224 (MC 2198, auth #tGl6)'


def get_conn():
    return psycopg2.connect(
        dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost'
    )


def fetch_charter(cur, reserve_number):
    cur.execute(
        """
        SELECT charter_id, client_id, total_amount_due, paid_amount, balance
        FROM charters WHERE reserve_number = %s
        """,
        (reserve_number,)
    )
    return cur.fetchone()


def insert_payment(cur, reserve_number, amount, payment_key, payment_date):
    # Use charter lookup to populate foreign keys and client_id
    cur.execute(
        """
        SELECT charter_id, client_id, account_number
        FROM charters WHERE reserve_number = %s
        """,
        (reserve_number,)
    )
    row = cur.fetchone()
    charter_id = row[0] if row else None
    client_id = row[1] if row else None
    account_number = row[2] if row else None

    cur.execute(
        """
        INSERT INTO payments (
            charter_id, reserve_number, account_number, client_id,
            amount, payment_key, payment_date,
            payment_method, credit_card_last4, authorization_code,
            status, notes, created_at
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            'paid', %s, CURRENT_TIMESTAMP
        )
        RETURNING payment_id
        """,
        (
            charter_id, reserve_number, account_number, client_id,
            amount, payment_key, payment_date,
            PAYMENT_METHOD, CARD_LAST4, AUTH_CODE,
            NOTES,
        ),
    )
    return cur.fetchone()[0]


def recalc_two(cur, reserves):
    cur.execute(
        """
        WITH payment_sums AS (
            SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
            FROM payments
            WHERE reserve_number = ANY(%s)
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.actual_paid,
            balance = c.total_amount_due - ps.actual_paid
        FROM payment_sums ps
        WHERE c.reserve_number = ps.reserve_number
        """,
        (reserves,),
    )


def main():
    parser = argparse.ArgumentParser(description='Record split retainer across two reserves')
    parser.add_argument('--write', action='store_true', help='Apply changes (default dry-run)')
    parser.add_argument('--date', type=str, help='Payment date YYYY-MM-DD (default: today)')
    args = parser.parse_args()

    payment_date = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else datetime.now().date()
    payment_key = f"MANUAL:MC{CARD_LAST4}:{AUTH_CODE}:{payment_date.isoformat()}:019223+019224"

    conn = get_conn()
    cur = conn.cursor()

    print('Preview (before):')
    for r in RESERVES:
        row = fetch_charter(cur, r)
        if row:
            cid, client_id, due, paid, bal = row
            print(f"  {r}: due={due} paid={paid} bal={bal}")
        else:
            print(f"  {r}: NOT FOUND")

    # Idempotency: if this payment_key already exists, do nothing
    cur.execute("SELECT COUNT(*) FROM payments WHERE payment_key = %s", (payment_key,))
    exists = cur.fetchone()[0] > 0

    if exists:
        print(f"\nPayment key already exists: {payment_key} -> no inserts")
    else:
        print(f"\nWould insert with payment_key: {payment_key}")
        for r, amt in zip(RESERVES, SPLIT_AMOUNTS):
            print(f"  -> {r} amount ${amt:.2f}")
            if args.write:
                insert_payment(cur, r, amt, payment_key, payment_date)

    if args.write and not exists:
        recalc_two(cur, RESERVES)
        conn.commit()
        print("\nApplied. After:")
        for r in RESERVES:
            row = fetch_charter(cur, r)
            if row:
                cid, client_id, due, paid, bal = row
                print(f"  {r}: due={due} paid={paid} bal={bal}")
    else:
        print("\nDRY-RUN (no changes committed)")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
