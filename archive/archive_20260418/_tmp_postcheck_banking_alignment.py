import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from datetime import datetime

ids = [82544,62569,62579,62666,63005,63036,88735,88765,44961,45269,45191,92932]

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute('SELECT COUNT(*) AS c FROM backup_easyfix_banking_alignment_20260407')
backup_rows = cur.fetchone()['c']

cur.execute('''
SELECT transaction_id, transaction_date, description, category, reconciliation_notes
FROM banking_transactions
WHERE transaction_id = ANY(%s)
ORDER BY transaction_date, transaction_id
''', (ids,))
rows = cur.fetchall()

tagged = 0
for r in rows:
    note = r['reconciliation_notes'] or ''
    if 'NON_EXPENSE_REV' in note:
        tagged += 1

out = Path(r'l:\limo\data\audit\easy_fix_banking_alignment_summary_20260407_1935.txt')
lines = [
    'EASY FIX BANKING ALIGNMENT SUMMARY',
    f'Generated: {datetime.now().isoformat(timespec="seconds")}',
    '',
    'Applied changes:',
    '- Added reconciliation note to banking rows linked to NON_EXPENSE_REV receipts',
    '- No category overwrite, no deletion, no transfer/nsf flag changes',
    '',
    f'Target rows: {len(ids)}',
    f'Rows with marker note: {tagged}',
    f'Backup table rows: {backup_rows}',
    '',
    'Rows:'
]
for r in rows:
    lines.append(f"{r['transaction_id']} | {r['transaction_date']} | {r['category']} | {r['description']}")
out.write_text('\n'.join(lines), encoding='utf-8')
print(out)
print('tagged', tagged)
print('backup_rows', backup_rows)

cur.close(); conn.close()
