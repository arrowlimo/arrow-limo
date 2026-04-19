import psycopg2

updates = [
    (6200, False, 141642),
    (6200, False, 140913),
    (6400, False, 140676),
    (1000, True, 169989),
    (1000, True, 170014),
    (1000, True, 170919),
]

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor()
try:
    for gl, exclude, rid in updates:
        cur.execute(
            """
            UPDATE receipts
            SET gl_account_code = %s,
                exclude_from_reports = %s,
                updated_at = NOW()
            WHERE receipt_id = %s
              AND EXTRACT(YEAR FROM receipt_date)=2012
            """,
            (str(gl), exclude, rid),
        )
    conn.commit()
    print('UPDATED_ROWS_TARGETED: 6')
except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
