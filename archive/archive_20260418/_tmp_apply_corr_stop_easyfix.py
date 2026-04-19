import csv
from pathlib import Path
from datetime import datetime
import psycopg2

src = Path(r'l:\limo\data\audit\nsf_correction_high_conf_candidates_20260407_190606.csv')
if not src.exists():
    raise SystemExit('source csv missing')

ids = []
with src.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        reason = (row.get('reason') or '')
        suggest_excl = (row.get('suggest_set_exclude_from_reports') or '').lower() == 'true'
        suggest_nsf = (row.get('suggest_set_is_nsf') or '').lower() == 'true'
        if suggest_excl and (('keyword_correction' in reason) or ('keyword_stop_payment' in reason)) and not suggest_nsf:
            ids.append(int(row['receipt_id']))
ids = sorted(set(ids))

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

try:
    cur.execute('CREATE TABLE IF NOT EXISTS backup_easyfix_corr_stop_20260407 AS SELECT * FROM receipts WHERE 1=0')
    if ids:
        cur.execute('INSERT INTO backup_easyfix_corr_stop_20260407 SELECT * FROM receipts WHERE receipt_id = ANY(%s)', (ids,))

    cur.execute('''
        UPDATE receipts
        SET exclude_from_reports = TRUE,
            receipt_review_status = COALESCE(NULLIF(receipt_review_status,''), 'NON_EXPENSE_REV'),
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\\n' END ||
                'Easy fix 2026-04-07: correction/stop-payment style row excluded from reports.',
            updated_at = NOW()
        WHERE receipt_id = ANY(%s)
          AND COALESCE(exclude_from_reports,false)=FALSE
    ''', (ids,))
    updated = cur.rowcount

    conn.commit()
    print('CORR_STOP_EASY_FIX_APPLIED')
    print('candidate_ids', len(ids))
    print('rows_updated', updated)
except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
