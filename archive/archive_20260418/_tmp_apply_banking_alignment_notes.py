import psycopg2
from datetime import datetime

ids = [82544,62569,62579,62666,63005,63036,88735,88765,44961,45269,45191,92932]

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

try:
    cur.execute('CREATE TABLE IF NOT EXISTS backup_easyfix_banking_alignment_20260407 AS SELECT * FROM banking_transactions WHERE 1=0')
    cur.execute('INSERT INTO backup_easyfix_banking_alignment_20260407 SELECT * FROM banking_transactions WHERE transaction_id = ANY(%s)', (ids,))
    backed = cur.rowcount

    cur.execute('''
        UPDATE banking_transactions
        SET reconciliation_notes = COALESCE(reconciliation_notes,'') ||
            CASE WHEN COALESCE(reconciliation_notes,'')='' THEN '' ELSE E'\\n' END ||
            'Easy fix 2026-04-07: linked receipt flagged NON_EXPENSE_REV (correction/reversal/stop-payment style). Review category if needed.',
            updated_at = NOW()
        WHERE transaction_id = ANY(%s)
    ''', (ids,))
    updated = cur.rowcount

    conn.commit()
    print('BANKING_ALIGNMENT_APPLIED')
    print('backed_up_rows', backed)
    print('updated_rows', updated)
except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
