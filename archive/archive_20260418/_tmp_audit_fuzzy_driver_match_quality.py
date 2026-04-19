import re

import psycopg2

from _tmp_apply_fuzzy_driver_match_etransfers import extract_candidate_name, norm_text

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute(
    """
    SELECT bt.transaction_id, bt.debit_amount, bt.description, bt.vendor_extracted, bt.reconciliation_notes
    FROM banking_transactions bt
    WHERE bt.reconciliation_status = 'DRIVER_PAY_FUZZY'
      AND bt.reconciliation_notes ILIKE '%etransfer_fuzzy_driver_match%'
    ORDER BY bt.transaction_id
    """
)
rows = cur.fetchall()

emp_re = re.compile(r'employee=([^\(]+)\s*\(id=')
issues = []
for tid, amt, desc, vendor, notes in rows:
    m = emp_re.search(notes or "")
    if not m:
        issues.append((tid, amt, 'NO_EMP_IN_NOTES', '', desc or ''))
        continue

    emp_name = norm_text(m.group(1))
    cand = norm_text(extract_candidate_name(desc or '', vendor))

    cand_toks = set(cand.split())
    emp_toks = set(emp_name.replace(',', ' ').split())
    overlap = cand_toks & emp_toks

    # Flag weak lexical overlap as possible false positives.
    if len(overlap) == 0:
        issues.append((tid, amt, 'ZERO_TOKEN_OVERLAP', f'{cand} -> {emp_name}', desc or ''))
    elif len(cand_toks) >= 2 and len(overlap) == 1:
        issues.append((tid, amt, 'LOW_TOKEN_OVERLAP', f'{cand} -> {emp_name}', desc or ''))

print(f'TOTAL_FUZZY_ROWS={len(rows)}')
print(f'FLAGGED_ROWS={len(issues)}')
for r in issues[:120]:
    print('|'.join(str(x) for x in r))

cur.close()
conn.close()
