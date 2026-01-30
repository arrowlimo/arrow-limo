import argparse
import psycopg2
from decimal import Decimal
from datetime import datetime

# Charter 016530: Cancelled; refund sent; non-refundable retainer held for future use.
# Data snapshot from residual analysis:
# - Payments total (PostgreSQL): 668.00 (2 payments)
# - LMS deposit recorded: 468.00 (assumed retainer portion)
# - Charges: 0.00 (no service delivered under this charter)
# Objective:
#   1. Convert retainer (closest payment to LMS deposit) into a credit ledger entry (CANCELLED_DEPOSIT)
#   2. Remove all existing payment rows for reserve_number 016530
#   3. Set charter paid_amount = 0.00 and balance = 0.00 (since cancelled, no charges)
#   4. Preserve backup of removed payments
# NOTE: The refund has been handled externally; we reflect the retained retainer only as future-use credit.

RESERVE_NUMBER = '016530'
RETAINER_TARGET = Decimal('468.00')  # From LMS deposit column

def get_conn():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def fetch_charter(cur):
    cur.execute("""
        SELECT charter_id, total_amount_due, paid_amount, balance, cancelled
        FROM charters WHERE reserve_number = %s
    """, (RESERVE_NUMBER,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f'Charter {RESERVE_NUMBER} not found')
    return {
        'charter_id': row[0],
        'total_amount_due': Decimal(str(row[1])) if row[1] is not None else Decimal('0'),
        'paid_amount': Decimal(str(row[2])) if row[2] is not None else Decimal('0'),
        'balance': Decimal(str(row[3])) if row[3] is not None else Decimal('0'),
        'cancelled': bool(row[4])
    }

def fetch_payments(cur):
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, payment_key
        FROM payments WHERE reserve_number = %s ORDER BY payment_date, payment_id
    """, (RESERVE_NUMBER,))
    rows = cur.fetchall()
    return [
        {
            'payment_id': r[0],
            'amount': Decimal(str(r[1])) if r[1] is not None else Decimal('0'),
            'payment_date': r[2],
            'payment_method': r[3],
            'payment_key': r[4]
        } for r in rows
    ]

def select_retainer_payment(payments):
    if not payments:
        raise RuntimeError('No payments to evaluate for retainer selection')
    return min(payments, key=lambda p: abs(p['amount'] - RETAINER_TARGET))

def backup_payments(cur, payment_ids):
    if not payment_ids:
        return None
    backup_table = f"payments_backup_{RESERVE_NUMBER}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    id_list = ','.join(str(i) for i in payment_ids)
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM payments WHERE payment_id IN ({id_list})")
    return backup_table

def create_credit(cur, charter_id, amount, payment_id):
    cur.execute("""
        INSERT INTO charter_credit_ledger (
            reserve_number, charter_id, credit_amount, credit_remaining, credit_reason, notes, source_payment_id, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) RETURNING id
    """, (
        RESERVE_NUMBER, charter_id, amount, amount, 'CANCELLED_DEPOSIT',
        'Cancelled charter retainer held for future use', payment_id
    ))
    return cur.fetchone()[0]

def delete_payments(cur, payment_ids):
    if not payment_ids:
        return 0
    cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (payment_ids,))
    return cur.rowcount

def update_charter(cur, charter_id):
    cur.execute("""
        UPDATE charters
        SET paid_amount = 0.00, balance = 0.00, updated_at = NOW()
        WHERE charter_id = %s
    """, (charter_id,))

def main():
    parser = argparse.ArgumentParser(description='Process cancelled charter 016530: convert retainer to credit and remove payments.')
    parser.add_argument('--write', action='store_true', help='Apply changes; otherwise dry-run.')
    args = parser.parse_args()

    conn = get_conn()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        charter = fetch_charter(cur)
        payments = fetch_payments(cur)
        print(f"Found {len(payments)} payments. Charter cancelled flag: {charter['cancelled']}")
        if not payments:
            conn.rollback()
            return
        retainer_payment = select_retainer_payment(payments)
        retainer_amount = retainer_payment['amount']
        total_paid = sum(p['amount'] for p in payments)
        print(f"Total paid: {total_paid}; Selected retainer payment ID {retainer_payment['payment_id']} amount {retainer_amount}")
        print(f"Retainer target {RETAINER_TARGET} (difference {retainer_amount - RETAINER_TARGET})")
        removal_ids = [p['payment_id'] for p in payments]  # All payments removed after converting retainer to credit
        if not args.write:
            print('DRY-RUN ONLY: Would create credit and delete payments, then zero charter.')
            conn.rollback()
            return
        backup_table = backup_payments(cur, removal_ids)
        print(f'Backup table: {backup_table}')
        credit_id = create_credit(cur, charter['charter_id'], retainer_amount, retainer_payment['payment_id'])
        print(f'Credit ledger entry created id={credit_id} for amount {retainer_amount}')
        deleted = delete_payments(cur, removal_ids)
        print(f'Deleted {deleted} payments.')
        update_charter(cur, charter['charter_id'])
        print('Charter financials zeroed.')
        conn.commit()
        print('Commit complete.')
    except Exception as e:
        conn.rollback()
        print('ERROR:', e)
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
