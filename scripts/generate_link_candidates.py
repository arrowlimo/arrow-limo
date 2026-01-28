#!/usr/bin/env python3
"""
Generate candidate charter links for unlinked payments.
- Uses explicit hints (e.g., #12345 in description/notes)
- Falls back to amount +/- tolerance and date window +/- days
Writes CSV: reports/unlinked_payment_link_candidates.csv
"""
import os
import re
import csv
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')
CSV_OUT = 'l:/limo/reports/unlinked_payment_link_candidates.csv'
LOOKBACK_DAYS = int(os.getenv('LINK_CANDIDATES_LOOKBACK_DAYS','365'))
DATE_WINDOW_DAYS = int(os.getenv('LINK_CANDIDATES_DATE_WINDOW_DAYS','14'))
AMOUNT_TOLERANCE = float(os.getenv('LINK_CANDIDATES_AMOUNT_TOLERANCE','1.00'))
MAX_CANDIDATES_PER_PAYMENT = int(os.getenv('LINK_CANDIDATES_MAX_PER_PAYMENT','3'))

HINT_PATTERN = re.compile(r"#(\d{3,7})")


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def charters_has_is_placeholder(cur) -> bool:
    cur.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema='public'
           AND table_name='charters'
           AND column_name='is_placeholder'
        LIMIT 1
    """)
    return cur.fetchone() is not None


def fetch_unlinked_payments(cur):
    cur.execute(
        """
                SELECT payment_id, amount, payment_date, payment_method, payment_key, notes
          FROM payments
         WHERE reserve_number IS NULL
           AND amount > 0
           AND payment_date >= CURRENT_DATE - INTERVAL '%s days'
         ORDER BY payment_date DESC
        """ % LOOKBACK_DAYS
    )
    return cur.fetchall()


def get_charter_by_id(cur, charter_id):
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, total_amount_due
          FROM charters
         WHERE charter_id = %s
        """,
        (charter_id,)
    )
    return cur.fetchone()


def find_amount_date_candidates(cur, p, exclude_placeholders: bool):
    # Build dynamic SQL depending on availability of is_placeholder
    sql = [
        "SELECT charter_id, reserve_number, charter_date, total_amount_due",
        "  FROM charters",
        " WHERE charter_date BETWEEN %s AND %s",
        "   AND ABS(COALESCE(total_amount_due,0) - %s) <= %s",
    ]
    params = [
        p['payment_date'] - timedelta(days=DATE_WINDOW_DAYS),
        p['payment_date'] + timedelta(days=DATE_WINDOW_DAYS),
        p['amount'],
        AMOUNT_TOLERANCE,
    ]
    if exclude_placeholders:
        sql.append("   AND COALESCE(is_placeholder,false) = false")
    sql.append(" ORDER BY ABS(COALESCE(total_amount_due,0) - %s), charter_date ASC LIMIT %s")
    params.extend([p['amount'], MAX_CANDIDATES_PER_PAYMENT])
    cur.execute("\n".join(sql), params)
    return cur.fetchall()


def extract_hint(text: str):
    if not text:
        return None
    m = HINT_PATTERN.search(text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def main():
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    total_unlinked = 0
    payments_with_hints = 0
    payments_with_candidates = 0
    total_candidates = 0

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            unlinked = fetch_unlinked_payments(cur)
            total_unlinked = len(unlinked)
            exclude_placeholders = charters_has_is_placeholder(cur)

            with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow([
                    'payment_id','payment_date','payment_method','amount','source','payment_key',
                    'notes','hint_charter_id','candidate_match_type','candidate_score',
                    'candidate_charter_id','candidate_reserve_number','candidate_charter_date','candidate_total_amount_due'
                ])

                for p in unlinked:
                    pk = p.get('payment_key') or ''
                    if pk.startswith('BTX:'):
                        source = 'non-card'
                    elif (p.get('payment_method') or '').lower() == 'credit_card':
                        source = 'square'
                    else:
                        source = 'other'

                    hint_id = extract_hint((p.get('notes') or ''))
                    wrote_any = False

                    # 1) Hint-based candidate
                    if hint_id:
                        payments_with_hints += 1
                        c = get_charter_by_id(cur, hint_id)
                        if c:
                            payments_with_candidates += 1
                            total_candidates += 1
                            w.writerow([
                                p['payment_id'], p['payment_date'], p['payment_method'], p['amount'], source, p.get('payment_key',''),
                                p.get('notes',''), hint_id, 'hint', 1.0,
                                c['charter_id'], c['reserve_number'], c['charter_date'], c['total_amount_due']
                            ])
                            wrote_any = True

                    # 2) Amount+date candidates
                    cand = find_amount_date_candidates(cur, p, exclude_placeholders)
                    if cand:
                        payments_with_candidates += 1
                        for idx, c in enumerate(cand):
                            def _f(x):
                                try:
                                    return float(x) if x is not None else 0.0
                                except Exception:
                                    return 0.0
                            score = max(0.0, 1.0 - abs(_f(c['total_amount_due']) - _f(p['amount'])) / max(1.0, AMOUNT_TOLERANCE))
                            total_candidates += 1
                            w.writerow([
                                p['payment_id'], p['payment_date'], p['payment_method'], p['amount'], source, p.get('payment_key',''),
                                p.get('notes',''), hint_id, 'amount_date', round(score,3),
                                c['charter_id'], c['reserve_number'], c['charter_date'], c['total_amount_due']
                            ])
                            wrote_any = True
                    if not wrote_any:
                        w.writerow([
                            p['payment_id'], p['payment_date'], p['payment_method'], p['amount'], source, p.get('payment_key',''),
                            p.get('notes',''), hint_id, '', '', '', '', '', ''
                        ])

    print('Unlinked payments in lookback:', total_unlinked)
    print('Payments with explicit #hint:', payments_with_hints)
    print('Payments with any candidates:', payments_with_candidates)
    print('Total candidate rows written:', total_candidates)
    print('Output:', CSV_OUT)


if __name__ == '__main__':
    main()
