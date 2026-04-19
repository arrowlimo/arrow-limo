import psycopg2
from pathlib import Path
from datetime import datetime
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
ids = [77875,60621,102454,102455,78789]
cur.execute('''
SELECT bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount,
       r.receipt_id, r.vendor_name, r.canonical_vendor, r.gross_amount, r.gst_amount,
       r.gl_account_code, r.category, r.receipt_source
FROM banking_transactions bt
LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
WHERE bt.transaction_id = ANY(%s)
ORDER BY bt.transaction_id
''', (ids,))
rows = cur.fetchall()

cur.execute('SELECT COUNT(*) AS c FROM backup_easyfix_lease_links_20260407')
backup_rows = cur.fetchone()['c']
cur.close(); conn.close()

out = Path(r'l:\limo\data\audit\easy_fix_lease_links_summary_20260407_1920.txt')
lines = [
    'EASY FIX LEASE LINK SUMMARY',
    f'Generated: {datetime.now().isoformat(timespec="seconds")}',
    '',
    'Resolved missing lease banking links: 5 of 5',
    '- Relinked existing receipts: 3',
    '- Inserted new receipts: 2 (Jack Carter)',
    '- Normalized relinked lease rows: 2',
    '',
    f'Backup table: backup_easyfix_lease_links_20260407 ({backup_rows} rows)',
    '',
    'Final linked mapping:'
]
for r in rows:
    lines.append(
        f"txn {r['transaction_id']} -> receipt {r['receipt_id']} | {r['vendor_name']} |  | gst  | gl {r['gl_account_code']} | cat {r['category']} | src {r['receipt_source']}"
    )
out.write_text('\n'.join(lines), encoding='utf-8')
print(out)
