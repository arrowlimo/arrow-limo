import os
import re
import csv
import json
from collections import defaultdict

import psycopg2

try:
    import pyodbc  # optional, Access DB
    HAS_PYODBC = True
except Exception:
    HAS_PYODBC = False


RESERVE_CSV_PATH = os.path.join('l:\\limo', 'Reserve.csv')
RESERVE2_CSV_PATH = os.path.join('l:\\limo', 'new_system', 'Reserve2.csv')
ACCESS_DB_PATH = os.path.join('l:\\limo', 'lms.mdb')


def norm_name(s):
    if s is None:
        return ''
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9& ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def load_access_reserves():
    data = {}
    if not HAS_PYODBC or not os.path.exists(ACCESS_DB_PATH):
        return data
    try:
        conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        cur.execute("SELECT Reserve_No, Name FROM Reserve")
        for row in cur.fetchall():
            reserve_no = str(row[0]).strip()
            name = (row[1] or '').strip()
            if re.fullmatch(r'\d{6}', reserve_no):
                data[reserve_no] = name
            else:
                # pad to 6 if numeric shorter
                if reserve_no.isdigit() and len(reserve_no) < 6:
                    padded = reserve_no.zfill(6)
                    data[padded] = name
        cur.close()
        conn.close()
    except Exception:
        return {}
    return data


def parse_reserve_csv(path):
    mapping = {}
    if not os.path.exists(path):
        return mapping
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip('\n')
            if not line:
                continue
            six_digits = re.findall(r'\b\d{6}\b', line)
            if not six_digits:
                continue
            reserve_number = six_digits[-1]  # heuristic: last 6-digit token is standardized reserve
            # Name heuristic: choose longest alpha token
            parts = [p for p in line.split(',') if p and re.search(r'[A-Za-z]', p)]
            if parts:
                # prefer token containing spaces and not dollar sign
                candidates = [p for p in parts if ' ' in p and '$' not in p]
                token = max(candidates or parts, key=lambda x: len(x))
            else:
                token = ''
            name = token.strip()
            if reserve_number not in mapping or (len(name) > len(mapping[reserve_number])):
                mapping[reserve_number] = name
    return mapping


def parse_reserve2_csv(path):
    mapping = {}
    if not os.path.exists(path):
        return mapping
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            raw_id = row[0].strip()
            if not raw_id.isdigit():
                continue
            reserve_number = raw_id.zfill(6)
            # heuristic: name field around index 8
            name = ''
            if len(row) >= 9:
                name = row[8].strip()
            if name:
                mapping[reserve_number] = name
    return mapping


def get_pg_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )


def load_charters_and_clients():
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.reserve_number, c.client_display_name, c.client_id, cl.client_name
        FROM charters c LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.reserve_number IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    data = {}
    for r in rows:
        data[str(r[0]).strip()] = {
            'charter_client_display_name': r[1] or '',
            'client_id': r[2],
            'client_name': r[3] or ''
        }
    return data


def build_combined_lms_mapping():
    access_map = load_access_reserves()
    r_map = parse_reserve_csv(RESERVE_CSV_PATH)
    r2_map = parse_reserve2_csv(RESERVE2_CSV_PATH)

    # Prefer authoritative sources: Access > Reserve2.csv
    preferred_keys = set()
    if access_map:
        preferred_keys.update(access_map.keys())
    preferred_keys.update(r2_map.keys())

    combined = {}
    sources = defaultdict(list)

    # Seed with Access/Reserve2 first
    for m, label in [(access_map, 'access'), (r2_map, 'reserve2_csv')]:
        for k, v in m.items():
            if k not in combined or (len(v) > len(combined[k]) and norm_name(v)):
                combined[k] = v
            sources[k].append(label)

    # Add Reserve.csv entries only if they appear in preferred keys (to avoid notes/false tokens)
    for k, v in r_map.items():
        if k in preferred_keys:
            if k not in combined or (len(v) > len(combined[k]) and norm_name(v)):
                combined[k] = v
            sources[k].append('reserve_csv')
    return combined, sources


def compare(lms_map, sources, charter_map):
    report = {
        'total_lms_reserves': len(lms_map),
        'matched_in_charters': 0,
        'missing_in_charters': [],
        'name_mismatches': [],
        'perfect_matches': 0,
        'client_missing': [],
        'by_source': {}
    }
    for k, v in lms_map.items():
        if k in charter_map:
            report['matched_in_charters'] += 1
            charter_info = charter_map[k]
            lms_norm = norm_name(v)
            charter_norm = norm_name(charter_info['charter_client_display_name'] or charter_info['client_name'])
            if not charter_info['client_id']:
                report['client_missing'].append(k)
            if lms_norm and charter_norm and lms_norm != charter_norm:
                report['name_mismatches'].append({
                    'reserve_number': k,
                    'lms_name': v,
                    'charter_display': charter_info['charter_client_display_name'],
                    'client_name': charter_info['client_name']
                })
            else:
                report['perfect_matches'] += 1
        else:
            report['missing_in_charters'].append(k)
    # source stats
    src_counts = defaultdict(int)
    for k, src_list in sources.items():
        for s in src_list:
            src_counts[s] += 1
    report['by_source'] = dict(src_counts)
    return report


def main():
    lms_map, src = build_combined_lms_mapping()
    charter_map = load_charters_and_clients()
    report = compare(lms_map, src, charter_map)
    summary = {
        'counts': {
            'total_lms_reserves': report['total_lms_reserves'],
            'matched_in_charters': report['matched_in_charters'],
            'perfect_matches': report['perfect_matches'],
            'name_mismatches': len(report['name_mismatches']),
            'missing_in_charters': len(report['missing_in_charters']),
            'client_missing_on_charter': len(report['client_missing'])
        },
        'source_breakdown': report['by_source']
    }
    print('LMS Reserve → Name Mapping Verification Summary')
    print(json.dumps(summary, indent=2))
    if report['missing_in_charters']:
        print('\nMissing in charters sample (first 25):')
        for k in report['missing_in_charters'][:25]:
            print(f'  {k} -> {lms_map[k]}')
    if report['name_mismatches']:
        print('\nName mismatches sample (first 25):')
        for item in report['name_mismatches'][:25]:
            print(f"  {item['reserve_number']} | LMS='{item['lms_name']}' vs CharterDisplay='{item['charter_display']}' Client='{item['client_name']}'")
    if report['client_missing']:
        print('\nCharters without client_id (first 25):')
        for k in report['client_missing'][:25]:
            info = charter_map.get(k, {})
            print(f"  {k} | display='{info.get('charter_client_display_name','')}'")


if __name__ == '__main__':
    main()
