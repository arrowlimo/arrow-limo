#!/usr/bin/env python3
"""
Use lms_deposits as a high-signal source to link payments to charters.

Heuristics:
  - If Number looks like a reserve number (digits 4-7 long), try to match charters.reserve_number directly.
  - Else, try amount/date unique match to charters due or outstanding balance within ±14 days.
  - Ensure a payment exists: create payment_key = LMSDEP:<dep_key or id>:<number or 'NA'> on the deposit date with that amount.
  - Apply only when a single unambiguous charter is found.

Outputs:
  - reports/lms_deposit_links_applied.csv
  - reports/lms_deposit_links_skipped.csv
"""
import os
import re
import csv
from datetime import timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

DATE_WINDOW_DAYS = int(os.getenv('LMSDEP_DATE_WINDOW_DAYS','14'))
AMOUNT_TOL = float(os.getenv('LMSDEP_AMOUNT_TOLERANCE','1.00'))
LOOKBACK_DAYS = int(os.getenv('LMSDEP_LOOKBACK_DAYS','400'))
CARD_TYPES = {'VISA','MASTER CARD','MASTERCARD','AMERICAN EXPRESS','DEBIT CARDS','DEBIT CARD'}

CSV_APPLIED = r"l:/limo/reports/lms_deposit_links_applied.csv"
CSV_SKIPPED = r"l:/limo/reports/lms_deposit_links_skipped.csv"


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def looks_like_reserve(s: str) -> str | None:
    s = (s or '').strip()
    if not s:
        return None
    m = re.search(r"(\d{4,7})", s)
    if not m:
        return None
    val = m.group(1)
    if len(val) < 6:
        return val.zfill(6)
    return val


def ensure_payment(cur, key_hint: str, dep_date, amount: float, note: str, apply: bool):
    pkey = f"LMSDEP:{key_hint}"
    cur.execute("SELECT payment_id FROM payments WHERE payment_key=%s", (pkey,))
    ex = cur.fetchone()
    if ex:
        return ex[0]
    if not apply:
        return None
    cur.execute(
        """
        INSERT INTO payments (amount, payment_date, charter_id, payment_method, payment_key, notes, last_updated, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,NOW(),NOW())
        RETURNING payment_id
        """,
        (amount, dep_date, None, 'bank_transfer', pkey, note[:500])
    )
    return cur.fetchone()[0]


def find_charter_by_reserve(cur, reserve: str):
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, COALESCE(total_amount_due, COALESCE(rate,0)) AS due
          FROM charters
         WHERE reserve_number=%s
        """,
        (reserve,)
    )
    rows = cur.fetchall()
    return rows[0] if len(rows) == 1 else None


def find_unique_by_amount_date(cur, amount: float, dep_date):
    # Outstanding balance match
    cur.execute(
        """
        WITH cand AS (
            SELECT c.charter_id, c.reserve_number, c.charter_date, COALESCE(c.total_amount_due, COALESCE(c.rate,0)) AS due,
                   COALESCE(SUM(p.amount),0) AS paid
              FROM charters c
         LEFT JOIN payments p ON p.charter_id = c.charter_id
             WHERE c.charter_date BETWEEN %s AND %s
             GROUP BY c.charter_id
        )
        SELECT charter_id, reserve_number, charter_date, (due - paid) AS outstanding
          FROM cand
         WHERE ABS((due - paid) - %s) <= %s
         ORDER BY ABS((due - paid) - %s) ASC, charter_date ASC
        """,
        (dep_date - timedelta(days=DATE_WINDOW_DAYS), dep_date + timedelta(days=DATE_WINDOW_DAYS), amount, AMOUNT_TOL, amount)
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, COALESCE(total_amount_due, COALESCE(rate,0)) AS due
          FROM charters
         WHERE charter_date BETWEEN %s AND %s
           AND ABS(COALESCE(total_amount_due, COALESCE(rate,0)) - %s) <= %s
         ORDER BY ABS(COALESCE(total_amount_due, COALESCE(rate,0)) - %s) ASC, charter_date ASC
        """,
        (dep_date - timedelta(days=DATE_WINDOW_DAYS), dep_date + timedelta(days=DATE_WINDOW_DAYS), amount, AMOUNT_TOL, amount)
    )
    rows2 = cur.fetchall()
    return rows2[0] if len(rows2) == 1 else None


def main():
    ap = os.getenv('LMSDEP_APPLY','false').lower() in {'1','true','yes'}
    applied = []
    skipped = []
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Limit to recent and exclude obvious card batches so we focus on Interac/Cash/Cheque/Trade
            cur.execute(
                """
                SELECT id, cb_no, dep_date, dep_key, number, total, transact, type
                  FROM lms_deposits
                 WHERE total IS NOT NULL
                   AND dep_date >= CURRENT_DATE - INTERVAL %s
                """,
                (f"{LOOKBACK_DAYS} days",)
            )
            rows = cur.fetchall()
            for r in rows:
                try:
                    typ = (r['type'] or '').upper()
                    if typ in CARD_TYPES:
                        skipped.append({'lms_id': r['id'], 'reason':'skip_card_type', 'type': r['type']})
                        continue
                    key_hint = (r['dep_key'] or str(r['id'])) + ':' + (r['number'] or 'NA')
                    pid = ensure_payment(cur, key_hint, r['dep_date'], float(r['total']), f"[LMS Deposit {r['dep_key']}] {r['number'] or ''} / {r['type'] or ''}", ap)
                    # already linked?
                    ch = None
                    if pid is not None:
                        cur.execute("SELECT charter_id FROM payments WHERE payment_id=%s", (pid,))
                        ch = cur.fetchone()
                    if ch and ch.get('charter_id') is not None:
                        skipped.append({'id': r['id'], 'reason':'already_linked', 'payment_id': pid})
                        continue
                    # try reserve in Number
                    reserve = looks_like_reserve(r['number'] or '')
                    charter = None
                    if reserve:
                        charter = find_charter_by_reserve(cur, reserve)
                    if not charter:
                        charter = find_unique_by_amount_date(cur, float(r['total']), r['dep_date'])
                    if charter:
                        if ap:
                            # Ensure payment exists if we are applying
                            if pid is None:
                                pid = ensure_payment(cur, key_hint, r['dep_date'], float(r['total']), f"[LMS Deposit {r['dep_key']}] {r['number'] or ''} / {r['type'] or ''}", True)
                            cur.execute("UPDATE payments SET charter_id=%s, last_updated=NOW() WHERE payment_id=%s AND charter_id IS NULL", (charter['charter_id'], pid))
                        applied.append({
                            'lms_id': r['id'], 'dep_date': r['dep_date'], 'number': r['number'], 'amount': float(r['total']),
                            'payment_id': pid or f"LMSDEP:{key_hint}", 'charter_id': charter['charter_id'], 'reserve_number': charter['reserve_number'], 'charter_date': charter['charter_date']
                        })
                    else:
                        skipped.append({'lms_id': r['id'], 'dep_date': r['dep_date'], 'number': r['number'], 'amount': float(r['total']), 'reason':'no_unique_charter'})
                except Exception as e:
                    skipped.append({'lms_id': r.get('id'), 'reason': f'error: {e}'})
            if ap:
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
    print(f"LMS deposit linker complete: applied={len(applied)}, skipped={len(skipped)}")
    print(' ', CSV_APPLIED)
    print(' ', CSV_SKIPPED)


if __name__ == '__main__':
    main()
