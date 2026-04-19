import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import datetime

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute('SELECT COUNT(*) AS c FROM backup_easyfix_corr_stop_20260407')
backup_rows = cur.fetchone()['c']

cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status = 'NON_EXPENSE_REV' AND COALESCE(exclude_from_reports,false)=true")
marked = cur.fetchone()['c']

cur.execute('''
SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, is_nsf, exclude_from_reports, receipt_review_status
FROM receipts
WHERE receipt_review_status = 'NON_EXPENSE_REV'
ORDER BY receipt_date, receipt_id
''')
rows = cur.fetchall()

out = Path(r'l:\limo\data\audit\easy_fix_corr_stop_summary_20260407_1927.txt')
lines = [
    'EASY FIX CORRECTION STOP SUMMARY',
    f'Generated: {datetime.now().isoformat(timespec="seconds")}',
    '',
    'Applied changes:',
    '- correction/stop-payment style rows excluded from reports only',
    '- no deletions, no new is_nsf marking in this pass',
    '',
    f'Rows marked this status: {marked}',
    f'Backup table rows: {backup_rows}',
    '',
    'Rows:'
]
for r in rows:
    lines.append(f"{r['receipt_id']} | {r['receipt_date']} | {r['vendor_name']} |  | nsf={r['is_nsf']} | excluded={r['exclude_from_reports']} | {r['description']}")
out.write_text('\n'.join(lines), encoding='utf-8')

print(out)
print('rows_marked', marked)
print('backup_rows', backup_rows)

cur.close(); conn.close()
