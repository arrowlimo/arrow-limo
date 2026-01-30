import os
import psycopg2
import json
import datetime
from decimal import Decimal

TARGETS = [
    # (display_label, service_date (YYYY-MM-DD), time(HH:MM), client hints list)
    ("PACE SETTER", "2025-10-25", "15:30", ["pace", "setter", "403-968-4468"]),
    ("MANDY STINSON", "2025-12-26", "19:30", ["mandy", "stinson", "403-826-0309"]),
    ("CATHOLIC SOCIAL SERVICES", "2025-08-06", "12:00", ["catholic", "social", "services"]),
    ("JILL SHEWCHUK #1", "2024-05-15", "05:30", ["jill", "shewchuk", "403-886-8604"]),
    ("JILL SHEWCHUK #2", "2024-05-16", "09:00", ["jill", "shewchuk", "403-886-8604"]),
]

WINDOW_MINUTES = 75  # search +/- this many minutes around stated time

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def fetch_candidates(cur, date_str):
    # Adjusted columns (client_name may not exist). Use charter_data or client_notes if present; fetch wide set.
    cur.execute("""
        SELECT charter_id, reserve_number, client_id, charter_date, pickup_time, cancelled, total_amount_due, paid_amount, balance, client_notes, booking_notes, notes, charter_data
        FROM charters
        WHERE charter_date::date = %s
        ORDER BY pickup_time NULLS LAST, charter_id
    """, (date_str,))
    return cur.fetchall()

def time_to_minutes(tstr):
    try:
        parts = tstr.split(':')
        return int(parts[0])*60 + int(parts[1])
    except Exception:
        return None

def normalize_text(s):
    # charter_data may be JSON/dict; coerce to string safely
    if s is None:
        return ''
    if isinstance(s, (dict, list, tuple)):
        try:
            import json as _json
            return _json.dumps(s, separators=(',', ':')).lower()
        except Exception:
            return str(s).lower()
    return str(s).lower()

def match_score(row, target_time_minutes, hints):
    (charter_id, reserve_number, client_id, charter_date, pickup_time, cancelled, total_due, paid_amount, balance,
     client_notes, booking_notes, notes, charter_data) = row
    score = 0
    # Time proximity
    pickup_minutes = None
    if pickup_time:
        # Accept formats HH:MM or HH:MM:SS
        pickup_minutes = time_to_minutes(pickup_time[:5])
    if pickup_minutes is not None and target_time_minutes is not None:
        diff = abs(pickup_minutes - target_time_minutes)
        if diff <= WINDOW_MINUTES:
            # closer gives higher points
            score += max(0, (WINDOW_MINUTES - diff))
    # Hint matching (client name / phone fragments)
    # Aggregate textual fields for hint matching
    haystack = ' '.join([
        normalize_text(client_notes),
        normalize_text(booking_notes),
        normalize_text(notes),
        normalize_text(charter_data)
    ])
    for h in hints:
        if h in haystack:
            score += 50
    # Cancellation flag (if already cancelled boosts confidence the record represents the calendar line)
    if cancelled:
        score += 10
    return score

def main():
    conn = get_conn()
    cur = conn.cursor()
    results = []
    for label, date_str, time_str, hints in TARGETS:
        candidates = fetch_candidates(cur, date_str)
        target_minutes = time_to_minutes(time_str)
        scored = []
        for r in candidates:
            s = match_score(r, target_minutes, [h.lower() for h in hints])
            if s > 0:
                scored.append((s, r))
        scored.sort(reverse=True, key=lambda x: x[0])
        top = []
        for s, r in scored[:10]:  # limit output
            (charter_id, reserve_number, client_id, charter_date, pickup_time, cancelled, total_due, paid_amount, balance,
             client_notes, booking_notes, notes, charter_data) = r
            top.append({
                'score': s,
                'charter_id': charter_id,
                'reserve_number': reserve_number,
                'client_notes': client_notes,
                'booking_notes': booking_notes,
                'charter_date': str(charter_date),
                'pickup_time': pickup_time,
                'cancelled': cancelled,
                'total_amount_due': str(total_due),
                'paid_amount': str(paid_amount),
                'balance': str(balance),
                'notes_excerpt': (notes[:120] + '...') if notes and notes and len(notes) > 120 else notes,
                'charter_data_excerpt': (charter_data[:120] + '...') if charter_data and len(charter_data) > 120 else charter_data
            })
        results.append({
            'calendar_entry_label': label,
            'calendar_date': date_str,
            'calendar_time': time_str,
            'hints': hints,
            'matches_found': len(top),
            'top_matches': top
        })
    cur.close(); conn.close()
    print(json.dumps({'generated_at': datetime.datetime.utcnow().isoformat()+'Z', 'window_minutes': WINDOW_MINUTES, 'entries': results}, indent=2))

if __name__ == '__main__':
    main()
