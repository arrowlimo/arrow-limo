import psycopg2, json, os, datetime

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REDACTED***')
    )

CALENDAR_CREATED_BY = 'calendar_import'

QUERY = """
WITH credit_charters AS (
    SELECT ccl.source_reserve_number AS reserve_number,
           ccl.source_charter_id AS charter_id,
           ccl.credit_amount,
           ccl.created_date
    FROM charter_credit_ledger ccl
    WHERE ccl.created_by = %s
), deleted_payment_backups AS (
    SELECT pb.payment_id, pb.reserve_number, pb.amount, pb.payment_date, pb.backup_timestamp
    FROM payment_backups pb
    LEFT JOIN payments p ON p.payment_id = pb.payment_id
    WHERE p.payment_id IS NULL -- truly deleted
), joined AS (
    SELECT cc.reserve_number,
           cc.charter_id,
           cc.credit_amount,
           cc.created_date AS credit_created,
           dpb.payment_id AS deleted_payment_id,
           dpb.amount AS deleted_payment_amount,
           dpb.payment_date AS deleted_payment_date,
           dpb.backup_timestamp
    FROM credit_charters cc
    LEFT JOIN deleted_payment_backups dpb
      ON dpb.reserve_number = cc.reserve_number
         AND (dpb.amount = cc.credit_amount OR cc.credit_amount IS NULL)
)
SELECT * FROM joined ORDER BY reserve_number;
"""

def main():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(QUERY, (CALENDAR_CREATED_BY,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    data = []
    for r in rows:
        rec = dict(zip(cols, r))
        # Derive status
        if rec['deleted_payment_id'] is None:
            rec['status'] = 'payment_missing_or_not_deleted_in_backup'
        else:
            rec['status'] = 'payment_deleted'
        data.append(rec)
    summary = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'count': len(data),
        'missing_payments': sum(1 for d in data if d['deleted_payment_id'] is None),
        'items': data
    }
    print(json.dumps(summary, indent=2, default=str))
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
