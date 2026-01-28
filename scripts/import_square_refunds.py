#!/usr/bin/env python3
"""
Import Square refund emails into payments as negative amounts.

Source: reports/square_emails.csv with type=refund and amount/date.

Behavior:
  - Upsert into payments with payment_method='credit_card', payment_key='SQREF:<message_id>' and negative amount
  - Try to link to a charter if a #hint is present in subject or message_excerpt
  - Write applied and skipped CSVs
"""
import os
import re
import csv
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

CSV_IN = r"l:/limo/reports/square_emails.csv"
CSV_APPLIED = r"l:/limo/reports/square_refunds_applied.csv"
CSV_SKIPPED = r"l:/limo/reports/square_refunds_skipped.csv"

HINT_RE = re.compile(r"#(\d{3,7})")


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def load_rows():
    if not os.path.exists(CSV_IN):
        return []
    out = []
    with open(CSV_IN, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get('type') or '').lower() != 'refund':
                continue
            try:
                amt = float(row.get('amount') or 0)
                dt = row.get('email_date')
                out.append({
                    'message_id': row.get('message_id') or row.get('uid') or '',
                    'email_date': datetime.fromisoformat(dt) if dt else None,
                    'amount': round(float(amt), 2),
                    'subject': row.get('subject') or '',
                    'excerpt': row.get('message_excerpt') or '',
                })
            except Exception:
                continue
    return out


def find_charter_from_hint(cur, text: str):
    m = HINT_RE.search(text or '')
    if not m:
        return None
    try:
        cid = int(m.group(1))
        cur.execute("SELECT charter_id, reserve_number FROM charters WHERE charter_id=%s", (cid,))
        row = cur.fetchone()
        return row
    except Exception:
        return None


def main():
    rows = load_rows()
    applied = []
    skipped = []
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for r in rows:
                try:
                    pkey = f"SQREF:{r['message_id']}"
                    cur.execute("SELECT payment_id, charter_id FROM payments WHERE payment_key=%s", (pkey,))
                    ex = cur.fetchone()
                    link_charter = find_charter_from_hint(cur, (r['subject'] + ' ' + r['excerpt']))
                    if ex:
                        cur.execute(
                            """
                            UPDATE payments SET amount=%s, payment_date=%s, notes=%s, last_updated=NOW()
                             WHERE payment_id=%s
                            """,
                            (-abs(float(r['amount'] or 0)), r['email_date'].date() if r['email_date'] else None,
                             f"[Square Refund] {r['subject']}", ex['payment_id'])
                        )
                        pid = ex['payment_id']
                    else:
                        cur.execute(
                            """
                            INSERT INTO payments (amount, payment_date, charter_id, payment_method, payment_key, notes, last_updated, created_at)
                            VALUES (%s,%s,%s,%s,%s,%s,NOW(),NOW())
                            RETURNING payment_id
                            """,
                            (-abs(float(r['amount'] or 0)), r['email_date'].date() if r['email_date'] else None,
                             None, 'credit_card', pkey, f"[Square Refund] {r['subject']}")
                        )
                        pid = cur.fetchone()['payment_id']
                    if link_charter and (ex is None or ex['charter_id'] is None):
                        try:
                            cur.execute("UPDATE payments SET charter_id=%s WHERE payment_id=%s AND charter_id IS NULL", (link_charter['charter_id'], pid))
                        except Exception:
                            pass
                    applied.append({'payment_id': pid, **r})
                except Exception as e:
                    skipped.append({**r, 'reason': f'error: {e}'})
            conn.commit()

    os.makedirs(os.path.dirname(CSV_APPLIED), exist_ok=True)
    with open(CSV_APPLIED, 'w', newline='', encoding='utf-8') as f:
        if applied:
            w = csv.DictWriter(f, fieldnames=list(applied[0].keys()))
            w.writeheader(); w.writerows(applied)
        else:
            f.write('')
    with open(CSV_SKIPPED, 'w', newline='', encoding='utf-8') as f:
        if skipped:
            keys = set(); [keys.update(s.keys()) for s in skipped]
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader(); w.writerows(skipped)
        else:
            f.write('')
    print(f"Square refunds import complete: applied={len(applied)}, skipped={len(skipped)}")
    print(' ', CSV_APPLIED)
    print(' ', CSV_SKIPPED)


if __name__ == '__main__':
    main()
