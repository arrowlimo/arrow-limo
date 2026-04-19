import re
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute(
    """
    SELECT source, COUNT(1)
    FROM email_financial_events
    GROUP BY source
    ORDER BY COUNT(1) DESC
    """
)
print('SOURCE_COUNTS')
for src, cnt in cur.fetchall():
    print(f'{src}|{cnt}')

cur.execute(
    """
    SELECT id, source, from_email, subject, event_type, amount, email_date
    FROM email_financial_events
    WHERE source IN ('outlook_etransfer_payment', 'manual_etransfer', 'outlook_etransfer')
       OR event_type ILIKE '%etransfer%'
       OR subject ILIKE '%e-transfer%'
       OR subject ILIKE '%interac%'
    ORDER BY id DESC
    LIMIT 200
    """
)
rows = cur.fetchall()
print(f'EMAIL_ROWS={len(rows)}')
for r in rows[:40]:
    print('|'.join('' if x is None else str(x) for x in r))

name_re = re.compile(r'INTERAC\s+e-Transfer:\s+(.+?)\s+sent you money', re.IGNORECASE)
names = {}
for _id, _src, _from, subj, _etype, _amt, _dt in rows:
    if not subj:
        continue
    m = name_re.search(subj)
    if m:
        nm = m.group(1).strip()
        names[nm] = names.get(nm, 0) + 1

print('PARSED_SUBJECT_NAMES')
for k, v in sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[:50]:
    print(f'{k}|{v}')

cur.close()
conn.close()
