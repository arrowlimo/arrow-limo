import argparse
import psycopg2
from decimal import Decimal
from datetime import datetime

# Cancelled charter 014215 remediation:
# - Charter had total_due 81.57, paid_amount 1000.00 (4 payments)
# - Valid nonrefundable retainer portion: 500.00 to be converted into credit for future use
# - Valid payment covering actual charges: 81.57 retained
# - Remaining excess (418.43) represents duplicate/erroneous payments to remove
# - Result: charter paid_amount -> 81.57, balance 0, cancelled flag preserved
# - Credit ledger entry created for 500.00 (CANCELLED_DEPOSIT reason)

RETAINER_AMOUNT = Decimal('500.00')
ACTUAL_DUE = Decimal('81.57')

def get_conn():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def fetch_payments(cur):
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, payment_key
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
    """, ('014215',))
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

def fetch_charter(cur):
    cur.execute("""
        SELECT charter_id, total_amount_due, paid_amount, balance, cancelled
        FROM charters WHERE reserve_number = %s
    """, ('014215',))
    row = cur.fetchone()
    if not row:
        raise RuntimeError('Charter 014215 not found')
    return {
        'charter_id': row[0],
        'total_amount_due': Decimal(str(row[1])) if row[1] is not None else Decimal('0'),
        'paid_amount': Decimal(str(row[2])) if row[2] is not None else Decimal('0'),
        'balance': Decimal(str(row[3])) if row[3] is not None else Decimal('0'),
        'cancelled': bool(row[4])
    }

def determine_actions(payments):
    total_paid = sum(p['amount'] for p in payments)
    excess = total_paid - ACTUAL_DUE
    # We expect total_paid == 1000, excess == 918.43
    retainer_credit = RETAINER_AMOUNT
    duplicates_to_remove_total = excess - retainer_credit
    # Strategy: keep one payment covering ACTUAL_DUE (closest match) and remove others except retainer payment converted to credit.
    # Choose payment for ACTUAL_DUE: smallest payment >= ACTUAL_DUE or smallest overall.
    sorted_by_amount = sorted(payments, key=lambda x: (abs(x['amount'] - ACTUAL_DUE), x['amount']))
    payment_for_due = sorted_by_amount[0]

    # Identify payment to represent retainer (closest to 500)
    payment_for_retainer = sorted(payments, key=lambda x: abs(x['amount'] - RETAINER_AMOUNT))[0]
    remove_ids = []
    for p in payments:
        if p['payment_id'] == payment_for_due['payment_id']:
            continue
        if p['payment_id'] == payment_for_retainer['payment_id']:
            # We convert this one to credit (delete after credit insertion)
            remove_ids.append(p['payment_id'])
            continue
        # Remaining payments considered duplicates
        remove_ids.append(p['payment_id'])
    return {
        'total_paid': total_paid,
        'excess': excess,
        'retainer_credit': retainer_credit,
        'duplicates_to_remove_total': duplicates_to_remove_total,
        'payment_for_due': payment_for_due,
        'payment_for_retainer': payment_for_retainer,
        'remove_payment_ids': remove_ids
    }

def create_credit(cur, charter_id, amount):
    # Insert into charter_credit_ledger (assumed existing schema)
    cur.execute("""
        INSERT INTO charter_credit_ledger (
            reserve_number, charter_id, credit_amount, credit_remaining, credit_reason, notes, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
    """, (
        '014215', charter_id, amount, amount, 'CANCELLED_DEPOSIT',
        'Cancelled charter retainer converted to future use credit'
    ))
    return cur.fetchone()[0]

def update_charter(cur, charter_id):
    # Set paid_amount to ACTUAL_DUE and balance to 0 (since cancelled and charges covered)
    cur.execute("""
        UPDATE charters
        SET paid_amount = %s,
            balance = 0.00,
            updated_at = NOW()
        WHERE charter_id = %s
    """, (str(ACTUAL_DUE), charter_id))

def backup_payments(cur, payment_ids):
    if not payment_ids:
        return None
    id_list = ','.join(str(i) for i in payment_ids)
    backup_table = f"payments_backup_014215_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM payments WHERE payment_id IN ({id_list})")
    return backup_table

def delete_payments(cur, payment_ids):
    if not payment_ids:
        return 0
    cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (payment_ids,))
    return cur.rowcount

def main():
    parser = argparse.ArgumentParser(description='Fix cancelled charter 014215: convert retainer to credit and remove duplicate payments.')
    parser.add_argument('--write', action='store_true', help='Apply changes (otherwise dry-run).')
    args = parser.parse_args()

    conn = get_conn()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        charter = fetch_charter(cur)
        payments = fetch_payments(cur)
        if not payments:
            print('No payments found for 014215')
            return
        actions = determine_actions(payments)
        print('--- Analysis ---')
        print(f"Total payments: {len(payments)}  Total paid: {actions['total_paid']}")
        print(f"Excess: {actions['excess']}  Retainer credit: {actions['retainer_credit']}")
        print(f"Duplicates (incl retainer conversion) removal count: {len(actions['remove_payment_ids'])}")
        print(f"Payment kept for due: ID {actions['payment_for_due']['payment_id']} amount {actions['payment_for_due']['amount']}")
        print(f"Payment converted to credit (retainer): ID {actions['payment_for_retainer']['payment_id']} amount {actions['payment_for_retainer']['amount']}")
        if not args.write:
            print('DRY-RUN: No changes applied.')
            conn.rollback()
            return
        # Backup removable payments
        backup_table = backup_payments(cur, actions['remove_payment_ids'])
        print(f'Backup table created: {backup_table}')
        # Create credit for retainer
        credit_id = create_credit(cur, charter['charter_id'], actions['retainer_credit'])
        print(f'Credit ledger entry id {credit_id} inserted.')
        # Delete removable payments
        deleted = delete_payments(cur, actions['remove_payment_ids'])
        print(f'Deleted {deleted} payments (including retainer payment now represented as credit).')
        # Update charter amounts
        update_charter(cur, charter['charter_id'])
        print('Charter updated: paid_amount set to actual due 81.57, balance 0.00.')
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
