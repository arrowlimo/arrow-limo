"""
Match external calendar event rows to existing charters using business rules:

Inputs: CSV file provided via --events path with columns (header case-insensitive):
  event_date        (YYYY-MM-DD or DD/MM/YYYY)
  start_time        (HH:MM or HH:MM:SS 24h)
  client            (client name as appears on calendar)
  amount            (numeric total expected / quoted)
  vehicle           (e.g. L-10, L10, L10/L-11 for replacement candidates)
  driver_notes      (e.g. MR/DAV, DR117, Mike/Paul)
  reserve_hint      (optional partial or full reserve number if present)

Rules:
  - Date must match charter_date exactly.
  - Time tolerance: +/- 120 minutes from pickup_time if pickup_time present.
  - Vehicle tokens: split on '/' -> candidates. Normalize L patterns to L-#.
  - Driver tokens: split on '/' -> candidates. Try to resolve to employee via:
       1) Exact DR### code matching employees.employee_number
       2) Initials / first name prefix (3+ chars) against employees.full_name
  - Amount tolerance: +/- 5% when amount provided; if missing skip.
  - Client fuzzy: ILIKE match against clients.client_name; try direct equals, then startswith, then contains.

Output:
  - For each event row produce: match_status, chosen_charter_id/reserve_number, reasoning summary.
  - Flag ambiguous cases (multiple candidates) or irregularities (vehicle/driver mismatch) for manual review.

Dry-run: always (no DB mutations). Future enhancement could write a linkage table.
"""
import argparse
import csv
import datetime as dt
import math
import os
import re
import sys
from typing import List, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor

DATE_PATTERNS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
TIME_PATTERNS = ["%H:%M", "%H:%M:%S"]

VEHICLE_TOKEN_RE = re.compile(r"^L-?(\d{1,3})$", re.IGNORECASE)
DR_CODE_RE = re.compile(r"^DR\s*-?\s*(\d{1,4})$", re.IGNORECASE)

def parse_date(s: str):
    s = s.strip()
    for p in DATE_PATTERNS:
        try:
            return dt.datetime.strptime(s, p).date()
        except ValueError:
            continue
    return None

def parse_time(s: str):
    s = s.strip()
    for p in TIME_PATTERNS:
        try:
            t = dt.datetime.strptime(s, p).time()
            return dt.datetime.combine(dt.date.today(), t)  # anchor for diff
        except ValueError:
            continue
    return None

def norm_vehicle_token(tok: str) -> str:
    tok = tok.strip().upper()
    m = VEHICLE_TOKEN_RE.match(tok)
    if m:
        return f"L-{int(m.group(1))}"  # canonical L-# form
    return tok

def split_tokens(raw: str) -> List[str]:
    return [t for t in re.split(r"[/,]", raw) if t.strip()]

def load_employee_maps(cur):
    cur.execute("SELECT employee_id, employee_number, full_name FROM employees")
    num_map = {}
    name_map = {}
    prefix_map = {}
    for r in cur.fetchall():
        emp_id = r['employee_id']
        num = r['employee_number']
        name = r['full_name'] or ''
        if num:
            num_map[str(num).upper()] = emp_id
        if name:
            upper = name.upper()
            name_map[upper] = emp_id
            # build prefixes up to length 6 for matching abbreviations
            parts = upper.split(',')[0].split()  # first name region before comma
            if parts:
                first = parts[0]
                for L in range(2, min(len(first), 6) + 1):
                    prefix_map.setdefault(first[:L].upper(), set()).add(emp_id)
        # also build DR### forms
        if isinstance(num, str) and num.upper().startswith('DR'):
            digits = re.sub(r'\D', '', num)
            if digits:
                num_map[f"DR{digits}"] = emp_id
    return num_map, name_map, prefix_map

def load_clients(cur):
    cur.execute("SELECT client_id, client_name FROM clients")
    clients = cur.fetchall()
    return clients

def fuzzy_client_ids(client_rows, name: str) -> List[int]:
    name_u = (name or '').strip().upper()
    if not name_u:
        return []
    exact = [r['client_id'] for r in client_rows if (r['client_name'] or '').upper() == name_u]
    if exact:
        return exact
    starts = [r['client_id'] for r in client_rows if (r['client_name'] or '').upper().startswith(name_u)]
    if starts:
        return starts
    contains = [r['client_id'] for r in client_rows if name_u in (r['client_name'] or '').upper()]
    return contains

def get_charters_for_date(cur, date: dt.date):
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, pickup_time, total_amount_due, client_id, vehicle, driver, vehicle_id, assigned_driver_id
        FROM charters
        WHERE charter_date = %s
        """,
        (date,),
    )
    return cur.fetchall()

def parse_amount(val: str):
    if val is None:
        return None
    try:
        return float(str(val).replace('$', '').replace(',', '').strip())
    except ValueError:
        return None

def time_diff_minutes(charter_pickup_time, event_time_obj):
    if charter_pickup_time is None or event_time_obj is None:
        return None
    # charter_pickup_time may be a time; anchor
    cp = dt.datetime.combine(dt.date.today(), charter_pickup_time)
    return abs((cp - event_time_obj).total_seconds() / 60.0)

def resolve_driver_tokens(tokens: List[str], num_map, prefix_map) -> List[int]:
    resolved = set()
    for tok in tokens:
        raw = tok.strip().upper()
        # DR code pattern
        m = DR_CODE_RE.match(raw)
        if m:
            digits = m.group(1)
            key = f"DR{digits}"
            if key in num_map:
                resolved.add(num_map[key])
            continue
        # attempt prefix match
        if raw in prefix_map and len(prefix_map[raw]) == 1:
            resolved.add(next(iter(prefix_map[raw])))
    return list(resolved)

def score_match(event_row, charter, driver_emp_ids, vehicle_tokens_norm):
    score = 0
    reasoning = []
    # vehicle match heuristic
    charter_vehicle_norm = norm_vehicle_token(charter['vehicle'] or '')
    if charter_vehicle_norm in vehicle_tokens_norm:
        score += 25
        reasoning.append(f"vehicle={charter_vehicle_norm}")
    # driver match
    if driver_emp_ids and charter['assigned_driver_id'] in driver_emp_ids:
        score += 25
        reasoning.append(f"driver={charter['assigned_driver_id']}")
    # amount match
    ev_amt = event_row.get('amount_parsed')
    ch_amt = charter['total_amount_due']
    if ev_amt and ch_amt:
        diff = abs(ev_amt - ch_amt)
        tolerance = ev_amt * 0.05
        if diff <= tolerance:
            score += 20
            reasoning.append(f"amount≈{ch_amt}")
    # time proximity
    td = time_diff_minutes(charter['pickup_time'], event_row.get('start_time_obj'))
    if td is not None:
        if td <= 30:
            score += 20
            reasoning.append(f"time≤30m")
        elif td <= 120:
            score += 10
            reasoning.append(f"time≤120m")
    # client hint (if reserve_hint or client fuzzy resulted in one candidate) skipped now
    return score, ','.join(reasoning)

def process(events_path: str, conn):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    num_map, name_map, prefix_map = load_employee_maps(cur)
    clients = load_clients(cur)

    results = []
    with open(events_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = {k.lower(): v for k, v in raw_row.items()}
            event_date = parse_date(row.get('event_date', ''))
            start_time_obj = parse_time(row.get('start_time', ''))
            amount_parsed = parse_amount(row.get('amount'))
            client_name = row.get('client', '')
            vehicle_raw = row.get('vehicle', '')
            driver_notes = row.get('driver_notes', '')
            reserve_hint = row.get('reserve_hint', '').strip()

            vehicle_tokens = split_tokens(vehicle_raw) if vehicle_raw else []
            vehicle_tokens_norm = [norm_vehicle_token(t) for t in vehicle_tokens]
            driver_tokens = split_tokens(driver_notes) if driver_notes else []
            driver_emp_ids = resolve_driver_tokens(driver_tokens, num_map, prefix_map)

            event_row = {
                'event_date': event_date,
                'start_time_obj': start_time_obj,
                'amount_parsed': amount_parsed,
            }

            status = 'no-date'
            matched_charter_id = None
            matched_reserve = None
            reasoning = ''
            irregularities = []

            if not event_date:
                results.append({**row, 'match_status': status, 'reasoning': 'invalid date'})
                continue

            day_charters = get_charters_for_date(cur, event_date)
            if reserve_hint:
                rh = reserve_hint.lstrip('0')
                for c in day_charters:
                    if c['reserve_number'] and c['reserve_number'].lstrip('0') == rh:
                        matched_charter_id = c['charter_id']
                        matched_reserve = c['reserve_number']
                        status = 'matched-reserve-hint'
                        reasoning = 'reserve_hint'
                        break
                if status == 'matched-reserve-hint':
                    results.append({**row, 'match_status': status, 'charter_id': matched_charter_id, 'reserve_number': matched_reserve, 'reasoning': reasoning})
                    continue

            client_ids = fuzzy_client_ids(clients, client_name)

            candidates = []
            for c in day_charters:
                # client filter if we have hints
                if client_ids and c['client_id'] not in client_ids:
                    continue
                score, rsn = score_match(event_row, c, driver_emp_ids, vehicle_tokens_norm)
                if score > 0:
                    candidates.append((score, rsn, c))

            if not candidates:
                status = 'no-candidate'
                results.append({**row, 'match_status': status, 'reasoning': 'no scoring candidates'})
                continue

            candidates.sort(key=lambda x: x[0], reverse=True)
            top_score = candidates[0][0]
            top = [c for c in candidates if c[0] == top_score]
            if len(top) > 1:
                status = 'ambiguous'
                reasoning = f"{len(top)} top candidates score={top_score}"
                results.append({**row, 'match_status': status, 'reasoning': reasoning})
                continue

            chosen = top[0][2]
            matched_charter_id = chosen['charter_id']
            matched_reserve = chosen['reserve_number']
            status = 'matched'
            reasoning = candidates[0][1]

            # Irregularities: vehicle token provided but did not match chosen charter vehicle
            if vehicle_tokens_norm and norm_vehicle_token(chosen['vehicle'] or '') not in vehicle_tokens_norm:
                irregularities.append('vehicle-mismatch')
            if driver_emp_ids and chosen['assigned_driver_id'] not in driver_emp_ids:
                irregularities.append('driver-mismatch')
            if len(irregularities) > 0:
                status = 'manual-review'
                reasoning += ';' + ';'.join(irregularities)

            results.append({**row, 'match_status': status, 'charter_id': matched_charter_id, 'reserve_number': matched_reserve, 'reasoning': reasoning})

    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--events', required=True, help='Path to calendar events CSV')
    ap.add_argument('--limit-output', type=int, default=50, help='Limit printed results')
    ap.add_argument('--export', help='Optional path to write full result CSV')
    args = ap.parse_args()

    if not os.path.exists(args.events):
        print(f"Events file not found: {args.events}")
        sys.exit(2)

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )

    results = process(args.events, conn)
    conn.close()

    print(f"Processed {len(results)} event rows")
    header = ['event_date','start_time','client','amount','vehicle','driver_notes','reserve_hint','match_status','charter_id','reserve_number','reasoning']
    print('\nSample Output:')
    print('|'.join(header))
    for r in results[: args.limit_output]:
        row_vals = [str(r.get(h,'')) for h in header]
        print('|'.join(row_vals))

    if args.export:
        with open(args.export, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            for r in results:
                w.writerow({h: r.get(h,'') for h in header})
        print(f"\nFull results written to {args.export}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
