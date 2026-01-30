"""
Scan charter notes to extract possible driver and vehicle identifiers to reduce
mapping ambiguity. Produces a console summary and optional CSV of candidates.

Notes fields scanned (if present): booking_notes, driver_notes, vehicle_notes, notes, charter_data.

Logic:
- Vehicle tokens: L-?NN, LNN, 'vehicle L-22', 'unit 10'; normalized to LNN for matching.
- Driver tokens: DRNNN, 'Driver: Name', 'Chauffeur: Name'; prefers numeric DR codes.
- Cross-check against employees.employee_number and vehicles.unit_number/license_plate.

Safety: Read-only. Use --write-csv to export candidates to CSV.
"""
import argparse
import csv
import os
import re
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


NOTE_COLUMNS_CANDIDATES = [
    'booking_notes', 'driver_notes', 'vehicle_notes', 'notes', 'charter_data'
]


VEHICLE_TOKEN_RE = re.compile(r'\bL\s*-?\s*(\d{1,3})\b', re.IGNORECASE)
UNIT_TOKEN_RE = re.compile(r'\bunit\s*(\d{1,3})\b', re.IGNORECASE)
DRIVER_CODE_RE = re.compile(r'\bDR\s*[-:]?\s*(\d{1,4})\b', re.IGNORECASE)
DRIVER_NAME_RE = re.compile(r"""\b(?:driver|chauffeur)\s*[:\-]\s*([A-Za-z][A-Za-z\s\.'"-]{2,40})""", re.IGNORECASE)


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    pwd = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, database=db, user=user, password=pwd)


def get_existing_columns(cur, table):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
    )
    return {r['column_name'] for r in cur.fetchall()}


def norm_vehicle_token(token: str) -> str:
    if not token:
        return ''
    token = token.strip().upper()
    token = re.sub(r'\s+', '', token)
    # Ensure L prefix
    if token.startswith('L'):
        # Collapse L-22 -> L22
        token = token.replace('-', '')
    elif token.isdigit():
        token = 'L' + token
    return token


def load_vehicle_index(cur):
    cur.execute("SELECT vehicle_id, unit_number, license_plate FROM vehicles")
    unit_idx = {}
    plate_idx = {}
    for r in cur.fetchall():
        unit = r['unit_number'] or ''
        plate = r['license_plate'] or ''
        if unit:
            unit_idx[norm_vehicle_token(unit)] = r['vehicle_id']
        if plate:
            plate_idx[plate.strip().upper()] = r['vehicle_id']
    return unit_idx, plate_idx


def load_employee_index(cur):
    # employee_number may be text or int; normalize to string
    cur.execute("SELECT employee_id, employee_number, full_name FROM employees")
    num_idx = {}
    num_digits_idx = {}
    name_idx = {}
    for r in cur.fetchall():
        if r['employee_number'] is not None:
            en = str(r['employee_number']).strip()
            num_idx[en] = r['employee_id']
            digits = re.sub(r'\D', '', en)
            if digits:
                num_digits_idx.setdefault(digits, set()).add(r['employee_id'])
        if r['full_name']:
            key = r['full_name'].strip().upper()
            name_idx[key] = r['employee_id']
    return num_idx, num_digits_idx, name_idx


def build_charter_select(existing_cols):
    base_cols = [
        'charter_id', 'reserve_number', 'vehicle', 'vehicle_id', 'driver', 'assigned_driver_id'
    ]
    cols = [c for c in base_cols if c in existing_cols]
    for nc in NOTE_COLUMNS_CANDIDATES:
        if nc in existing_cols:
            cols.append(nc)
    if not cols:
        raise RuntimeError('No expected columns found in charters')
    return ', '.join(cols)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='Limit rows scanned')
    parser.add_argument('--write-csv', action='store_true', help='Write candidates CSV to l:\\limo\\data')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    existing_cols = get_existing_columns(cur, 'charters')
    select_list = build_charter_select(existing_cols)

    cur.execute(f"SELECT COUNT(*) AS total FROM charters")
    total_charters = cur.fetchone()['total']

    sql = f"SELECT {select_list} FROM charters"
    if args.limit:
        sql += " ORDER BY charter_id DESC LIMIT %s"
        cur.execute(sql, (args.limit,))
    else:
        cur.execute(sql)
    rows = cur.fetchall()

    unit_idx, plate_idx = load_vehicle_index(cur)
    emp_num_idx, emp_num_digits_idx, emp_name_idx = load_employee_index(cur)

    found_vehicle_candidates = 0
    resolvable_vehicle = 0
    found_driver_code_candidates = 0
    resolvable_driver_code = 0

    candidates = []

    note_cols_present = [c for c in NOTE_COLUMNS_CANDIDATES if c in existing_cols]
    for r in rows:
        note_blob = []
        for col in note_cols_present:
            val = r.get(col)
            if val:
                note_blob.append(str(val))
        if not note_blob:
            continue
        text = ' \n '.join(note_blob)

        # Vehicle tokens
        v_tokens = set()
        for m in VEHICLE_TOKEN_RE.finditer(text):
            v_tokens.add(norm_vehicle_token('L' + m.group(1)))
        for m in UNIT_TOKEN_RE.finditer(text):
            v_tokens.add(norm_vehicle_token(m.group(1)))

        v_matches = []
        for tok in v_tokens:
            vid = unit_idx.get(tok)
            if vid:
                v_matches.append((tok, vid))

        # Driver tokens
        d_codes = set(m.group(1) for m in DRIVER_CODE_RE.finditer(text))
        d_code_matches = []
        for code in d_codes:
            # try exact (DR style) first
            emp_id = emp_num_idx.get(f'DR{code}') or emp_num_idx.get(f'Dr{code}') or emp_num_idx.get(str(code))
            if not emp_id:
                # try digit-only index (ensure unambiguous)
                cand = emp_num_digits_idx.get(str(code))
                if cand and len(cand) == 1:
                    emp_id = list(cand)[0]
            if emp_id:
                d_code_matches.append((code, emp_id))

        d_names = set()
        for m in DRIVER_NAME_RE.finditer(text):
            name = m.group(1).strip().upper()
            name = re.sub(r'\s+', ' ', name)
            d_names.add(name)
        d_name_matches = []
        for name in d_names:
            emp_id = emp_name_idx.get(name)
            if emp_id:
                d_name_matches.append((name, emp_id))

        if v_tokens:
            found_vehicle_candidates += 1
        if v_matches:
            resolvable_vehicle += 1
        if d_codes:
            found_driver_code_candidates += 1
        if d_code_matches:
            resolvable_driver_code += 1

        if v_tokens or d_codes or d_names:
            candidates.append({
                'charter_id': r.get('charter_id'),
                'reserve_number': r.get('reserve_number'),
                'existing_vehicle': r.get('vehicle'),
                'existing_vehicle_id': r.get('vehicle_id'),
                'vehicle_tokens': ';'.join(sorted(v_tokens)) if v_tokens else '',
                'vehicle_matches': ';'.join(f"{t}:{vid}" for t, vid in v_matches) if v_matches else '',
                'existing_driver': r.get('driver'),
                'existing_assigned_driver_id': r.get('assigned_driver_id'),
                'driver_codes': ';'.join(sorted(d_codes)) if d_codes else '',
                'driver_code_matches': ';'.join(f"{c}:{eid}" for c, eid in d_code_matches) if d_code_matches else '',
                'driver_names': ';'.join(sorted(d_names)) if d_names else '',
                'driver_name_matches': ';'.join(f"{n}:{eid}" for n, eid in d_name_matches) if d_name_matches else '',
            })

    print("\nCharter Notes Scan Summary")
    print("-" * 80)
    scanned = len(rows)
    print(f"Charters scanned: {scanned} of {total_charters}")
    print(f"Vehicle tokens found in notes: {found_vehicle_candidates}")
    print(f"Vehicle tokens resolvable to vehicle_id: {resolvable_vehicle}")
    print(f"Driver DR-code tokens found in notes: {found_driver_code_candidates}")
    print(f"Driver DR-code resolvable to employee_id: {resolvable_driver_code}")

    sample = candidates[:10]
    if sample:
        print("\nSample candidates (up to 10):")
        for c in sample:
            print(
                f"  res={c['reserve_number']} veh_tokens=[{c['vehicle_tokens']}] veh_matches=[{c['vehicle_matches']}] "
                f"drv_codes=[{c['driver_codes']}] drv_matches=[{c['driver_code_matches']}] drv_names=[{c['driver_names']}]"
            )

    if args.write_csv and candidates:
        out_dir = r"l:\\limo\\data"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'charter_notes_mapping_candidates.csv')
        fieldnames = list(candidates[0].keys())
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(candidates)
        print(f"\nCSV written: {out_path} ({len(candidates)} rows)")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
