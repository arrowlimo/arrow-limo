#!/usr/bin/env python3
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
conn.autocommit = False
cur = conn.cursor()

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

fixes = {
    '012144': {
        'charter_id': 10955,
        'status': 'Closed',
        'cancelled': False,
        'total_amount_due': 300.00,
        'subtotal': 250.00,
        'gst_amount': 12.50,
        'grand_total': 300.00,
        'extra_gratuity': 37.50,
        'payment_totals': 300.00,
        'paid_amount': 300.00,
        'amount_paid': 300.00,
        'balance': 0.00,
        'balance_owing': 0.00,
        'payment_status': 'Paid',
    },
    '012237': {
        'charter_id': 11145,
        'status': 'Closed',
        'cancelled': False,
        'total_amount_due': 250.00,
        'subtotal': 250.00,
        'gst_amount': 0.00,
        'grand_total': 250.00,
        'extra_gratuity': 0.00,
        'payment_totals': 250.00,
        'paid_amount': 250.00,
        'amount_paid': 250.00,
        'balance': 0.00,
        'balance_owing': 0.00,
        'payment_status': 'Paid',
    },
}

try:
    # Back up touched rows before mutation.
    cur.execute(f'''
        CREATE TABLE backup_charters_user_confirmed_residuals_{timestamp} AS
        SELECT * FROM charters WHERE reserve_number IN ('006341', '007504', '012144', '012237')
    ''')
    cur.execute(f'''
        CREATE TABLE backup_payments_user_confirmed_residuals_{timestamp} AS
        SELECT * FROM payments WHERE reserve_number IN ('006341', '007504', '012144', '012237')
           OR payment_id IN (7988, 8029)
    ''')
    cur.execute(f'''
        CREATE TABLE backup_charter_payments_user_confirmed_residuals_{timestamp} AS
        SELECT * FROM charter_payments WHERE charter_id IN ('5311', '6439', '10955', '11145')
           OR payment_id IN (7988, 8029)
    ''')
    cur.execute(f'''
        CREATE TABLE backup_income_ledger_user_confirmed_residuals_{timestamp} AS
        SELECT * FROM income_ledger WHERE income_id IN (19656, 19660) OR payment_id IN (7988, 8029)
    ''')

    for reserve_number, values in fixes.items():
        cur.execute(
            '''
            UPDATE charters
               SET status = %(status)s,
                   cancelled = %(cancelled)s,
                   total_amount_due = %(total_amount_due)s,
                   subtotal = %(subtotal)s,
                   gst_amount = %(gst_amount)s,
                   grand_total = %(grand_total)s,
                   extra_gratuity = %(extra_gratuity)s,
                   payment_totals = %(payment_totals)s,
                   paid_amount = %(paid_amount)s,
                   amount_paid = %(amount_paid)s,
                   balance = %(balance)s,
                   balance_owing = %(balance_owing)s,
                   payment_status = %(payment_status)s
             WHERE reserve_number = %(reserve_number)s
            ''',
            {**values, 'reserve_number': reserve_number},
        )

    # Reserve 007504: remove extra credit adjustment payment.
    cur.execute(
        'UPDATE income_ledger SET payment_id = NULL WHERE income_id = %s AND payment_id = %s',
        (19656, 7988),
    )
    cur.execute('DELETE FROM charter_payments WHERE payment_id = %s', (7988,))
    cur.execute('DELETE FROM payments WHERE payment_id = %s', (7988,))
    cur.execute(
        '''
        UPDATE charters
           SET payment_id = %s,
               payment_totals = %s,
               paid_amount = %s,
               amount_paid = %s,
               balance = %s,
               balance_owing = %s,
               payment_status = %s
         WHERE reserve_number = %s
        ''',
        (7987, 55.00, 55.00, 55.00, 0.00, 0.00, 'Paid', '007504'),
    )

    # Reserve 006341: remove late duplicate cheque payment but keep the bounced pair.
    cur.execute(
        'UPDATE income_ledger SET payment_id = NULL WHERE income_id = %s AND payment_id = %s',
        (19660, 8029),
    )
    cur.execute('DELETE FROM charter_payments WHERE payment_id = %s', (8029,))
    cur.execute('DELETE FROM payments WHERE payment_id = %s', (8029,))
    cur.execute(
        '''
        UPDATE charters
           SET payment_id = %s,
               payment_totals = %s,
               paid_amount = %s,
               amount_paid = %s,
               balance = %s,
               balance_owing = %s,
               payment_status = %s
         WHERE reserve_number = %s
        ''',
        (6566, 1000.00, 1000.00, 1000.00, 0.00, 0.00, 'Paid', '006341'),
    )

    conn.commit()
    print('Applied fixes successfully.')
    print(f'backup_charters_user_confirmed_residuals_{timestamp}')
    print(f'backup_payments_user_confirmed_residuals_{timestamp}')
    print(f'backup_charter_payments_user_confirmed_residuals_{timestamp}')
    print(f'backup_income_ledger_user_confirmed_residuals_{timestamp}')
except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
