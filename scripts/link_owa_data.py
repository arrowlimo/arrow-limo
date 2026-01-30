import os
import sys
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Tuple

import psycopg2

# Reuse existing DB helper if available; fallback to env parsing
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
    from api import get_db_connection  # type: ignore
except Exception:
    def get_db_connection():  # type: ignore
        return psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', '5432')),
            database=os.environ.get('DB_NAME', 'almsdata'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
        )

CAL_LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'reports', 'owa_calendar_linkage_log.json')

def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_calendar_log() -> Dict[str, Any]:
    if not os.path.exists(CAL_LOG_PATH):
        return {'events': []}
    try:
        with open(CAL_LOG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'events': []}

def save_calendar_log(log: Dict[str, Any]):
    os.makedirs(os.path.dirname(CAL_LOG_PATH), exist_ok=True)
    with open(CAL_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

def ensure_email_links_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_payment_links (
          id SERIAL PRIMARY KEY,
          payment_id INTEGER REFERENCES payments(payment_id) ON DELETE CASCADE,
          reserve_number VARCHAR(10),
          email_received TIMESTAMP,
          email_subject TEXT,
          email_type VARCHAR(20),
          amount NUMERIC(12,2),
          source_hash CHAR(64) UNIQUE,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_payment_links_reserve_amount_date
        ON email_payment_links(reserve_number, amount, email_received);
    """)

def hash_calendar_event(reserve_number: str, start: str, subject: str) -> str:
    h_in = f"{reserve_number}|{start}|{subject}".encode('utf-8')
    return hashlib.sha256(h_in).hexdigest()

def hash_email_link(reserve_number: str, amount: float, received: str, email_type: str) -> str:
    h_in = f"{reserve_number}|{amount:.2f}|{received}|{email_type}".encode('utf-8')
    return hashlib.sha256(h_in).hexdigest()

def link_calendar_events(data: Dict[str, Any], cur, write: bool) -> Tuple[int, int]:
    cal = data.get('calendar', {}).get('events', [])
    log = load_calendar_log()
    existing_hashes = {e.get('hash') for e in log.get('events', [])}
    processed = 0
    applied = 0
    for evt in cal:
        reserve_numbers: List[str] = evt.get('reserve_numbers') or []
        if not reserve_numbers:
            continue
        start = evt.get('start') or ''
        subject = (evt.get('subject') or '')[:140]
        body_excerpt = (evt.get('body') or '')[:200].replace('\n', ' ').strip()
        for rn in reserve_numbers:
            evt_hash = hash_calendar_event(rn, start, subject)
            processed += 1
            if evt_hash in existing_hashes:
                continue
            # Fetch charter
            cur.execute("SELECT charter_id, booking_notes, reservation_time FROM charters WHERE reserve_number=%s", (rn,))
            row = cur.fetchone()
            if not row:
                continue
            charter_id, booking_notes, reservation_time = row
            booking_notes = booking_notes or ''
            # Prepare note line
            note_line = f"OWA CAL NOTE ({start}): {subject} | {body_excerpt} [CAL_HASH:{evt_hash[:12]}]"
            if note_line in booking_notes:
                continue
            if write:
                new_notes = (booking_notes + "\n" + note_line).strip()
                # Only set reservation_time if null
                if reservation_time is None and start:
                    cur.execute(
                        "UPDATE charters SET booking_notes=%s, reservation_time=%s WHERE charter_id=%s",
                        (new_notes, start, charter_id)
                    )
                else:
                    cur.execute(
                        "UPDATE charters SET booking_notes=%s WHERE charter_id=%s",
                        (new_notes, charter_id)
                    )
                # Append to log
                log['events'].append({
                    'hash': evt_hash,
                    'reserve_number': rn,
                    'start': start,
                    'subject': subject,
                    'applied_at': datetime.utcnow().isoformat()
                })
                applied += 1
            else:
                applied += 1  # counts potential applications
    if write:
        save_calendar_log(log)
    return processed, applied

def link_emails(data: Dict[str, Any], cur, write: bool) -> Tuple[int, int]:
    emails = data.get('emails', {}).get('items', [])
    attempts = 0
    inserted = 0
    for em in emails:
        reserve_numbers: List[str] = em.get('reserve_numbers') or []
        if not reserve_numbers:
            continue
        amounts: List[float] = em.get('amounts') or []
        if not amounts:
            continue
        email_type = 'etransfer' if em.get('is_etransfer') else (
            'square' if em.get('is_square') else (
                'banking' if em.get('is_banking') else 'unknown'
            )
        )
        received = em.get('received') or ''
        subject = (em.get('subject') or '')[:200]
        for rn in reserve_numbers:
            for amt in amounts:
                if amt <= 0 or amt > 1000000:  # basic sanity
                    continue
                attempts += 1
                hval = hash_email_link(rn, amt, received, email_type)
                # Check existing
                cur.execute("SELECT 1 FROM email_payment_links WHERE source_hash=%s", (hval,))
                if cur.fetchone():
                    continue
                # Find payment candidates close to received date
                # Parse received date
                try:
                    recv_dt = datetime.fromisoformat(received.replace('Z',''))
                except Exception:
                    recv_dt = None
                payment_row = None
                if recv_dt:
                    cur.execute("""
                        SELECT payment_id, amount, reserve_number, payment_date
                        FROM payments
                        WHERE reserve_number=%s AND ROUND(amount::numeric,2)=ROUND(%s::numeric,2)
                        ORDER BY payment_date DESC
                        LIMIT 8
                    """, (rn, amt))
                    candidates = cur.fetchall()
                    # Choose nearest by absolute date diff if payment_date not null
                    best = None
                    best_diff = None
                    for c in candidates:
                        pid, c_amt, c_rn, p_date = c
                        if not p_date:
                            continue
                        diff = abs((recv_dt.date() - p_date).days)
                        if best is None or diff < best_diff:
                            best = c
                            best_diff = diff
                    payment_row = best
                if payment_row is None:
                    # fallback: first match ignoring date proximity
                    cur.execute("""
                        SELECT payment_id, amount, reserve_number, payment_date
                        FROM payments
                        WHERE reserve_number=%s AND ROUND(amount::numeric,2)=ROUND(%s::numeric,2)
                        LIMIT 1
                    """, (rn, amt))
                    payment_row = cur.fetchone()
                if not payment_row:
                    continue
                pid, p_amt, p_rn, p_date = payment_row
                if write:
                    cur.execute("""
                        INSERT INTO email_payment_links (payment_id, reserve_number, email_received, email_subject, email_type, amount, source_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_hash) DO NOTHING
                    """, (pid, rn, received, subject, email_type, amt, hval))
                    # Tag payment notes
                    cur.execute("SELECT notes FROM payments WHERE payment_id=%s", (pid,))
                    notes_row = cur.fetchone()
                    notes_val = (notes_row[0] or '') if notes_row else ''
                    tag = f"[EMAIL CONFIRMED {email_type.upper()} {received[:10]}]"
                    if tag not in notes_val:
                        new_notes = (notes_val + '\n' + tag).strip()
                        cur.execute("UPDATE payments SET notes=%s WHERE payment_id=%s", (new_notes, pid))
                    inserted += 1
                else:
                    inserted += 1  # potential insertion count
    return attempts, inserted

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Link OWA extracted data to charters and payments')
    parser.add_argument('--owa-json', default='reports/owa_complete_export.json', help='Path to OWA export JSON')
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()

    json_path = os.path.join(os.path.dirname(__file__), '..', args.owa_json)
    if not os.path.exists(json_path):
        print(f"ERROR: OWA JSON not found: {json_path}")
        sys.exit(1)

    data = load_json(json_path)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        ensure_email_links_table(cur)
        # Calendar linking
        cal_processed, cal_applied = link_calendar_events(data, cur, write=args.write)
        # Email linking
        email_attempts, email_inserted = link_emails(data, cur, write=args.write)
        if args.write:
            conn.commit()
        else:
            conn.rollback()
        print("\nSummary:")
        print(f"  Calendar events with reserve_numbers processed: {cal_processed}")
        print(f"  Calendar notes {'applied' if args.write else 'would apply'}: {cal_applied}")
        print(f"  Email link attempts: {email_attempts}")
        print(f"  Email links {'inserted' if args.write else 'would insert'}: {email_inserted}")
        if not args.write:
            print("\nRun again with --write to apply these changes.")
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

if __name__ == '__main__':
    main()