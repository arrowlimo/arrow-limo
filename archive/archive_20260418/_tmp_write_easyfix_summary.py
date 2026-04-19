import psycopg2
from pathlib import Path
from datetime import datetime

conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM backup_easyfix_receipts_20260407')
backup_rows = cur.fetchone()[0]
cur.close(); conn.close()

out = Path(r'l:\limo\data\audit\easy_fix_apply_summary_20260407_1912.txt')
out.write_text('\n'.join([
    'EASY FIX APPLY SUMMARY',
    f'Generated: {datetime.now().isoformat(timespec="seconds")}',
    '',
    'Applied changes (committed):',
    '- receipts is_nsf + exclude_from_reports set on 193 high-confidence NSF rows',
    '- gst_amount backfilled on 27 lease GST candidate rows',
    "- potential_duplicate + receipt_review_status='DUP_SAME_BANKING' set on 299 duplicate-candidate rows",
    '',
    'Before/After checks:',
    '- is_nsf=true: 1338 -> 1531 (+193)',
    '- exclude_from_reports=true: 2152 -> 2345 (+193)',
    '- lease GST csv rows still zero GST: 0 of 27',
    '- DUP_SAME_BANKING marked rows: 299',
    '',
    f'DB backup table: backup_easyfix_receipts_20260407 ({backup_rows} rows)',
    'No receipt deletions performed.',
]), encoding='utf-8')
print(out)
print('backup_rows', backup_rows)
