import psycopg2
from datetime import datetime

DB = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
TXN_ID = 102510
RECEIPT_ID = 140834
NOTE_TAG = 'manual_link_chq101_parrs_20260419'


def is_null_or_zero(v):
    return v is None or v == 0

conn = psycopg2.connect(**DB)
conn.autocommit = False
try:
    with conn.cursor() as cur:
        cur.execute(
            '''
            SELECT transaction_id, receipt_id, reconciled_receipt_id, reconciliation_status, description, check_number, reconciliation_notes
            FROM banking_transactions
            WHERE transaction_id = %s
            ''',
            (TXN_ID,),
        )
        bt = cur.fetchone()

        cur.execute(
            '''
            SELECT receipt_id, banking_transaction_id, vendor_name, gross_amount, receipt_date
            FROM receipts
            WHERE receipt_id = %s
            ''',
            (RECEIPT_ID,),
        )
        rc = cur.fetchone()

        print('BEFORE banking_transactions:', bt)
        print('BEFORE receipts:', rc)

        bt_rows = 0
        rc_rows = 0

        if bt is None:
            print(f'banking_transactions row {TXN_ID} not found')
        else:
            _, bt_receipt_id, bt_reconciled_receipt_id, _, _, _, bt_notes = bt
            if is_null_or_zero(bt_receipt_id) and is_null_or_zero(bt_reconciled_receipt_id):
                cur.execute(
                    '''
                    UPDATE banking_transactions
                    SET
                        receipt_id = %s,
                        reconciled_receipt_id = %s,
                        reconciliation_status = 'reconciled',
                        reconciliation_notes = CASE
                            WHEN reconciliation_notes IS NULL OR btrim(reconciliation_notes) = '' THEN %s
                            ELSE reconciliation_notes || ' | ' || %s
                        END,
                        reconciled_at = NOW(),
                        updated_at = NOW()
                    WHERE transaction_id = %s
                    ''',
                    (RECEIPT_ID, RECEIPT_ID, NOTE_TAG, NOTE_TAG, TXN_ID),
                )
                bt_rows = cur.rowcount
            else:
                print('Skipped banking_transactions update: receipt linkage already present')

        if rc is None:
            print(f'receipts row {RECEIPT_ID} not found')
        else:
            _, rc_btid, _, _, _ = rc
            if is_null_or_zero(rc_btid):
                cur.execute(
                    '''
                    UPDATE receipts
                    SET
                        banking_transaction_id = %s,
                        is_matched = TRUE,
                        updated_at = NOW()
                    WHERE receipt_id = %s
                    ''',
                    (TXN_ID, RECEIPT_ID),
                )
                rc_rows = cur.rowcount
            else:
                print('Skipped receipts update: banking_transaction_id already present')

        conn.commit()
        print(f'ROWS AFFECTED banking_transactions: {bt_rows}')
        print(f'ROWS AFFECTED receipts: {rc_rows}')

        cur.execute(
            '''
            SELECT receipt_id, reconciled_receipt_id, reconciliation_status, description, check_number
            FROM banking_transactions
            WHERE transaction_id = %s
            ''',
            (TXN_ID,),
        )
        bt_after = cur.fetchone()

        cur.execute(
            '''
            SELECT banking_transaction_id, vendor_name, gross_amount, receipt_date
            FROM receipts
            WHERE receipt_id = %s
            ''',
            (RECEIPT_ID,),
        )
        rc_after = cur.fetchone()

        print('AFTER banking_transactions:', bt_after)
        print('AFTER receipts:', rc_after)
finally:
    conn.close()
