import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

for tbl in ['employees', 'banking_transactions', 'email_financial_events']:
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name=%s
        ORDER BY ordinal_position
        """,
        (tbl,),
    )
    rows = cur.fetchall()
    print(f'TABLE={tbl}|COLUMNS={len(rows)}')
    for c, t in rows[:60]:
        print(f'  {c}|{t}')

print('EMPLOYEE_SAMPLE')
cur.execute(
    """
    SELECT employee_id, COALESCE(full_name, TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) AS nm
    FROM employees
    WHERE COALESCE(full_name, TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) <> ''
    ORDER BY employee_id
    LIMIT 30
    """
)
for r in cur.fetchall():
    print('|'.join(str(x) for x in r))

print('ETRANSFER_DEBIT_SAMPLE')
cur.execute(
    """
    SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted, reconciliation_status
    FROM banking_transactions
    WHERE debit_amount > 0
      AND (description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%' OR description ILIKE '%interac%' OR description ILIKE '%email transfer%')
    ORDER BY debit_amount DESC, transaction_id DESC
    LIMIT 60
    """
)
for r in cur.fetchall():
    print('|'.join(str(x) for x in r))

print('EMAIL_EVENT_NAME_SAMPLE')
cur.execute(
    """
    SELECT *
    FROM email_financial_events
    ORDER BY event_id DESC
    LIMIT 5
    """
)
rows = cur.fetchall()
print(f'rows={len(rows)}')
if rows:
    print('sample_row_colcount=' + str(len(rows[0])))

cur.close()
conn.close()
