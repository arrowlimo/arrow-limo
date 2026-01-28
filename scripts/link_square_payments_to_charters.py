#!/usr/bin/env python3
"""
Link Square client payments (payments.square_payment_id) to charters by backfilling reserve_number/charter_id
using fuzzy customer name matching and date/amount proximity.

Rules:
- Only link when high confidence: name similarity >= 0.90, date within ±7 days, amount diff <= 1.0%
- Prefer charters with balance within ±$1 of payment amount
- Write report to reports/square_payment_linkage_candidates.csv
- Support --apply (execute updates) and --dry-run (report only)
"""
import os
import sys
import csv
from difflib import SequenceMatcher
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(REPORT_DIR, "square_payment_linkage_candidates.csv")


def clean_name(name: str) -> str:
    if not name:
        return ""
    name = name.upper()
    filtered = ''.join(ch for ch in name if ch.isalpha() or ch.isspace())
    return ' '.join(filtered.split())


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, clean_name(a), clean_name(b)).ratio()


def main():
    apply_mode = ('--apply' in sys.argv or '--yes' in sys.argv)
    dry_run = ('--dry-run' in sys.argv)

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    # Load orphan Square payments (no reserve_number)
    cur.execute(
        """
        SELECT payment_id, payment_date, amount, square_payment_id, square_customer_name
        FROM payments
        WHERE square_payment_id IS NOT NULL
          AND (reserve_number IS NULL OR reserve_number = '')
        ORDER BY payment_date DESC
        """
    )
    square_payments = cur.fetchall()
    print(f"Loaded {len(square_payments):,} orphan Square payments")

    if not square_payments:
        print("No orphan Square payments to link.")
        return

    # Build client lookup
    cur.execute(
        """
        SELECT client_id, COALESCE(client_name, company_name) AS name
        FROM clients
        WHERE COALESCE(client_name, company_name) IS NOT NULL
        """
    )
    clients = cur.fetchall()

    # Build charters per client
    cur.execute(
        """
        SELECT charter_id, reserve_number, client_id, charter_date, total_amount_due, paid_amount, balance
        FROM charters
        WHERE cancelled = false OR cancelled IS NULL
        """
    )
    charters = cur.fetchall()

    # Index charters by client_id
    from collections import defaultdict
    charters_by_client = defaultdict(list)
    for ch in charters:
        charter_id, reserve_number, client_id, charter_date, total_due, paid_amount, balance = ch
        charters_by_client[client_id].append({
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'charter_date': charter_date,
            'total_due': float(total_due) if total_due is not None else None,
            'paid_amount': float(paid_amount) if paid_amount is not None else 0.0,
            'balance': float(balance) if balance is not None else None,
        })

    # Build candidates
    candidates = []
    for payment_id, payment_date, amount, square_id, square_name in square_payments:
        amount_f = float(amount)
        # Primary: Find best matching client by name (looser threshold 0.80)
        best_client = None
        best_score = 0.0
        for client_id, client_name in clients:
            score = name_similarity(square_name or '', client_name or '')
            if score > best_score:
                best_score = score
                best_client = (client_id, client_name)
        matched_charter = None
        client_id = None
        client_name = None
        if best_client and best_score >= 0.80:
            client_id, client_name = best_client
            nearby = [c for c in charters_by_client.get(client_id, [])
                      if c['charter_date'] and abs((payment_date - c['charter_date']).days) <= 14]
            # Score charters by balance proximity
            def score_charter(c):
                bal = c['balance'] if c['balance'] is not None else (
                    c['total_due'] - c['paid_amount'] if c['total_due'] is not None else None)
                if bal is None:
                    return float('inf')
                return abs(bal - amount_f)
            nearby.sort(key=score_charter)
            if nearby:
                best_charter = nearby[0]
                bal = best_charter['balance'] if best_charter['balance'] is not None else (
                    best_charter['total_due'] - best_charter['paid_amount'] if best_charter['total_due'] is not None else None)
                if bal is not None and abs(bal - amount_f) <= max(1.0, 0.02 * amount_f):
                    matched_charter = best_charter
        # Fallback: global charter match by exact balance near date if name failed
        if matched_charter is None:
            nearby_global = [c for c in charters
                             if c[3] and abs((payment_date - c[3]).days) <= 7]
            # Exact balance match
            def charter_balance(c):
                bal = float(c[6]) if c[6] is not None else (
                    (float(c[4]) - float(c[5])) if c[4] is not None and c[5] is not None else None)
                return bal
            exacts = [c for c in nearby_global if charter_balance(c) is not None and abs(charter_balance(c) - amount_f) <= 0.01]
            if len(exacts) == 1:
                charter_id, reserve_number, cl_id, ch_date, total_due, paid_amount, balance = exacts[0]
                matched_charter = {
                    'charter_id': charter_id,
                    'reserve_number': reserve_number,
                    'charter_date': ch_date,
                    'total_due': float(total_due) if total_due is not None else None,
                    'paid_amount': float(paid_amount) if paid_amount is not None else 0.0,
                    'balance': float(balance) if balance is not None else None,
                }
                client_id = cl_id
                client_name = None
                best_score = 0.0
        if matched_charter:
            candidates.append({
                'payment_id': payment_id,
                'payment_date': payment_date,
                'amount': amount_f,
                'square_payment_id': square_id,
                'square_customer_name': square_name,
                'client_id': client_id,
                'client_name': client_name,
                'charter_id': matched_charter['charter_id'],
                'reserve_number': matched_charter['reserve_number'],
                'charter_date': matched_charter['charter_date'],
                'name_score': round(best_score, 3)
            })

    print(f"Found {len(candidates):,} high-confidence Square→charter matches")

    # Write report
    headers = ['payment_id','payment_date','amount','square_payment_id','square_customer_name','client_id','client_name','charter_id','reserve_number','charter_date','name_score']
    with open(REPORT_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(candidates)
    print(f"Report written: {REPORT_PATH}")

    if not candidates:
        cur.close(); conn.close(); return

    # Apply updates
    if not apply_mode:
        print(f"Dry-run: would update {len(candidates):,} payments. Pass --apply to execute.")
        cur.close(); conn.close(); return

    print("Applying updates to payments...")
    for c in candidates:
        cur.execute(
            """
            UPDATE payments
            SET reserve_number = %s, charter_id = %s
            WHERE payment_id = %s AND (reserve_number IS NULL OR reserve_number = '')
            """,
            (c['reserve_number'], c['charter_id'], c['payment_id'])
        )
    conn.commit()
    print(f"✅ Updated {len(candidates):,} Square payments with reserve_number/charter_id")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
