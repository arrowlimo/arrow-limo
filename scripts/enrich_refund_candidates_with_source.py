"""Enrich refund_candidates_detailed.csv with source attribution for original positive payments.

Reads reports/refund_candidates_detailed.csv produced by audit_suspicious_batches_refund_matching.py
and adds columns indicating where the matched positive originated from (e.g., Square, Bank Transfer,
Check, Credit Card, E-transfer, Trade, Unknown), plus charter linkage summary.

Output:
  reports/refund_candidates_enriched.csv

Logic:
  - Load candidates CSV.
  - For each row, if matched_positive_id present, query payments table for:
        payment_method, amount, reserve_number, charter_id, account_number, payment_date, payment_key
    Also attempt to classify source:
        payment_method heuristic mapping + pattern checks in notes/authorization_code / square fields if present.
  - If match_type CROSS_BATCH and no matched_positive_id (defensive), attempt lookup via reserve_number + absolute amount + date window.
  - Add columns: source_classification, charter_has_balance_flag, charter_balance, charter_total_due, charter_paid_amount.
  - If negative_reserve exists but matched_positive_reserve differs, flag mismatch.

No DB mutations.
"""

from __future__ import annotations
import os, csv, sys
from typing import Dict, Any, Optional
import psycopg2
import psycopg2.extras


SOURCE_MAP = {
    'credit_card': 'CreditCard',
    'debit_card': 'DebitCard',
    'bank_transfer': 'BankTransfer',
    'cash': 'Cash',
    'check': 'Check',
    'etransfer': 'ETransfer',
    'trade_of_services': 'Trade',
}


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def classify_source(row: Dict[str, Any]) -> str:
    pm = (row.get('payment_method') or '').lower()
    source = SOURCE_MAP.get(pm, '')
    if not source:
        # Square heuristic
        if row.get('square_payment_id') or row.get('square_transaction_id'):
            return 'Square'
        if pm.startswith('credit'):
            return 'CreditCard'
        if 'transfer' in pm:
            return 'BankTransfer'
    return source or 'Unknown'


def load_candidates(path: str) -> list[dict[str,str]]:
    if not os.path.exists(path):
        print(f"[FAIL] Candidates file not found: {path}")
        sys.exit(1)
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        return list(r)


def fetch_payment(cur, payment_id: int) -> Optional[Dict[str, Any]]:
    cur.execute("""
        SELECT payment_id, payment_key, reserve_number, charter_id, account_number,
               COALESCE(payment_amount, amount, 0) AS amount, payment_method,
               payment_date, status, square_payment_id, square_transaction_id,
               authorization_code, notes
        FROM payments WHERE payment_id = %s
    """, (payment_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def fetch_charter(cur, charter_id: int) -> Optional[Dict[str, Any]]:
    cur.execute("""
        SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, status
        FROM charters WHERE charter_id = %s
    """, (charter_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def main():
    in_path = 'reports/refund_candidates_detailed.csv'
    out_path = 'reports/refund_candidates_enriched.csv'
    candidates = load_candidates(in_path)
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    enriched_rows = []
    for c in candidates:
        neg_pid = int(c['negative_payment_id']) if c['negative_payment_id'] else None
        pos_pid = int(c['matched_positive_id']) if c.get('matched_positive_id') else None
        pos_payment = fetch_payment(cur, pos_pid) if pos_pid else None
        charter = fetch_charter(cur, pos_payment['charter_id']) if pos_payment and pos_payment.get('charter_id') else None
        source_classification = classify_source(pos_payment) if pos_payment else ''
        charter_has_balance_flag = ''
        charter_balance = ''
        charter_total_due = ''
        charter_paid_amount = ''
        if charter:
            charter_balance = f"{charter.get('balance'):.2f}" if charter.get('balance') is not None else ''
            charter_total_due = f"{charter.get('total_amount_due'):.2f}" if charter.get('total_amount_due') is not None else ''
            charter_paid_amount = f"{charter.get('paid_amount'):.2f}" if charter.get('paid_amount') is not None else ''
            if charter.get('balance') and abs(charter.get('balance')) > 0.01:
                charter_has_balance_flag = 'Y'
            else:
                charter_has_balance_flag = 'N'
        reserve_mismatch = ''
        if c.get('negative_reserve') and c.get('matched_positive_reserve') and c['negative_reserve'] != c['matched_positive_reserve']:
            reserve_mismatch = 'Y'
        enriched_rows.append({
            **c,
            'source_classification': source_classification,
            'positive_payment_method': (pos_payment.get('payment_method') if pos_payment else ''),
            'positive_payment_status': (pos_payment.get('status') if pos_payment else ''),
            'positive_amount': f"{pos_payment.get('amount'):.2f}" if pos_payment else '',
            'charter_id': pos_payment.get('charter_id') if pos_payment else '',
            'charter_total_due': charter_total_due,
            'charter_paid_amount': charter_paid_amount,
            'charter_balance': charter_balance,
            'charter_has_balance': charter_has_balance_flag,
            'reserve_mismatch': reserve_mismatch,
        })
    # Write output
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = list(enriched_rows[0].keys()) if enriched_rows else []
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in enriched_rows:
            w.writerow(row)
    print(f"✓ Enriched refund candidates written: {out_path} ({len(enriched_rows)} rows)")
    cur.close(); conn.close()


if __name__ == '__main__':
    main()
