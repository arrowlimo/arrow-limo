import os
import csv
import re
from datetime import datetime
from difflib import SequenceMatcher

import psycopg2

from verify_lms_reserve_client_consistency import (
    build_combined_lms_mapping,
    load_charters_and_clients,
)


def norm(s: str) -> str:
    if not s:
        return ''
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9& ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def get_pg_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )


def load_clients():
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, COALESCE(client_name, company_name) AS display_name, client_name, company_name
        FROM clients
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    items = []
    for cid, disp, cname, comp in rows:
        items.append({
            'client_id': cid,
            'display_name': disp or '',
            'client_name': cname or '',
            'company_name': comp or '',
            'norm': norm(disp or cname or comp or '')
        })
    return items


def best_match(name: str, clients, min_score=0.9):
    n = norm(name)
    if not n or len(n) < 3:
        return None
    best = None
    best_score = 0.0
    for c in clients:
        if not c['norm']:
            continue
        score = SequenceMatcher(None, n, c['norm']).ratio()
        if score > best_score:
            best_score = score
            best = c
    if best and best_score >= min_score:
        return best, best_score
    return None


def main(min_score=0.9, write=False):
    lms_map, _ = build_combined_lms_mapping()
    charter_map = load_charters_and_clients()
    clients = load_clients()

    # target only charters with NULL client_id
    missing = [rn for rn, info in charter_map.items() if not info['client_id']]

    suggestions = []
    for rn in missing:
        lms_name = lms_map.get(rn, '')
        if not lms_name:
            continue
        res = best_match(lms_name, clients, min_score=min_score)
        if res:
            c, score = res
            suggestions.append({
                'reserve_number': rn,
                'lms_name': lms_name,
                'suggested_client_id': c['client_id'],
                'suggested_client_name': c['display_name'],
                'score': round(score, 4)
            })

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_csv = os.path.join('l:\\limo', 'reports', f'suggested_client_links_{ts}.csv')
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['reserve_number','lms_name','suggested_client_id','suggested_client_name','score'])
        w.writeheader()
        for row in suggestions:
            w.writerow(row)
    print(f'Suggestions written: {out_csv} (count={len(suggestions)})')

    if write and suggestions:
        conn = get_pg_conn()
        cur = conn.cursor()
        # Backup targeted rows only
        backup = f"charters_backup_client_link_{ts}"
        rn_list = [s['reserve_number'] for s in suggestions]
        cur.execute(f"CREATE TABLE {backup} AS SELECT * FROM charters WHERE reserve_number = ANY(%s)", (rn_list,))
        # Apply updates safely using reserve_number as business key
        for s in suggestions:
            cur.execute("""
                UPDATE charters c
                SET client_id = cl.client_id,
                    client_display_name = COALESCE(cl.client_name, cl.company_name)
                FROM clients cl
                WHERE c.reserve_number = %s
                  AND cl.client_id = %s
                  AND c.client_id IS NULL
            """, (s['reserve_number'], s['suggested_client_id']))
        conn.commit()
        cur.close()
        conn.close()
        print(f'Applied updates. Backup table: {backup}')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--min-score', type=float, default=0.9)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    main(min_score=args.min_score, write=args.write)
