import psycopg2
from pathlib import Path
from datetime import datetime
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("SELECT COUNT(*) AS c FROM backup_easyfix_xacc_refine_20260407")
backup_rows = cur.fetchone()['c']
cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status='XACC_DUP_AUTO'")
xacc_auto = cur.fetchone()['c']
cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status='XACC_REVIEW'")
xacc_review = cur.fetchone()['c']
cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE COALESCE(receipt_review_notes,'') ILIKE '%cross-account 8362<->1615 safe duplicate candidate%'")
auto_note_count = cur.fetchone()['c']

cur.execute('''
SELECT receipt_id, receipt_date, vendor_name, gross_amount, receipt_review_status
FROM receipts
WHERE receipt_review_status IN ('XACC_DUP_AUTO','XACC_REVIEW')
ORDER BY receipt_date DESC, receipt_id DESC
LIMIT 25
''')
sample = cur.fetchall()

out = Path(r'l:\limo\data\audit\xacc_refine_summary_20260407_1940.txt')
lines = [
    'XACC REFINEMENT SUMMARY',
    f'Generated: {datetime.now().isoformat(timespec="seconds")}',
    '',
    'Applied in this pass:',
    '- Safe same-day+both-auto subset tagged on 8362-side as duplicate candidates',
    '- Remaining shortlist rows tagged for manual cross-account review',
    '- No deletions performed',
    '',
    f'Backup table rows: {backup_rows}',
    f"Current status count XACC_DUP_AUTO: {xacc_auto}",
    f"Current status count XACC_REVIEW: {xacc_review}",
    f"Rows with safe-auto note marker: {auto_note_count}",
    '',
    'Sample latest tagged rows:'
]
for r in sample:
    lines.append(f"{r['receipt_id']} | {r['receipt_date']} | {r['vendor_name']} |  | {r['receipt_review_status']}")
out.write_text('\n'.join(lines), encoding='utf-8')

print(out)
print('backup_rows', backup_rows)
print('xacc_auto', xacc_auto)
print('xacc_review', xacc_review)
print('auto_note_count', auto_note_count)

cur.close(); conn.close()
