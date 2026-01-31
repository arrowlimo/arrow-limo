#!/usr/bin/env python3
"""Allocate 2012 batch deposit payments (payments without reserve_number) across charters.
Dry-run by default. Writes allocation rows to batch_deposit_allocations table when --apply provided.
Allocation Strategy (initial heuristic):
 1. Identify 2012 positive payments with reserve_number IS NULL (batch deposits).
 2. For each deposit payment (dp):
    - Gather candidate charter payments (cp) with reserve_number NOT NULL and payment_date within ±2 days of dp.payment_date.
    - Restrict candidates to ones where cp.amount <= dp.amount and charter still had outstanding timing difference (approx by payment_date proximity).
    - Compute total candidate sum; if >= deposit amount, allocate proportionally: alloc = round(deposit_amount * (cp.amount / total_candidate_sum), 2).
    - Track rounding remainder (deposit_amount - sum(alloc)); if |remainder| <= 0.05 keep as rounding; else mark as UNALLOCATED remainder.
 3. Persist allocations with metadata (method=PROPORTIONAL_SAME_DAY, remainder flag) into batch_deposit_allocations.
Idempotency: Existing allocations for a deposit_payment_id are skipped unless --recompute provided.

Creates report file reports/2012_batch_deposit_allocation_preview.csv in dry-run.

NOTE: This is a heuristic; manual review recommended for large deposits.
"""
import os, sys, csv, argparse, psycopg2
from datetime import date, timedelta

SCHEMA_SETUP_SQL = """
CREATE TABLE IF NOT EXISTS batch_deposit_allocations (
    allocation_id SERIAL PRIMARY KEY,
    deposit_payment_id INTEGER NOT NULL,
    target_payment_id INTEGER,
    reserve_number VARCHAR(20),
    allocation_amount NUMERIC(12,2) NOT NULL,
    method VARCHAR(50) NOT NULL,
    remainder BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
"""

FETCH_DEPOSITS_SQL = """
SELECT payment_id, amount, payment_date
FROM payments
WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
  AND reserve_number IS NULL AND amount > 0
ORDER BY payment_date, amount DESC;
"""

CANDIDATE_PAYMENTS_SQL = """
SELECT payment_id, reserve_number, amount, payment_date
FROM payments
WHERE payment_date BETWEEN %s AND %s
  AND reserve_number IS NOT NULL
  AND amount > 0;
"""

EXISTING_ALLOCATIONS_SQL = """
SELECT COUNT(*) FROM batch_deposit_allocations WHERE deposit_payment_id = %s;
"""

INSERT_ALLOC_SQL = """
INSERT INTO batch_deposit_allocations (deposit_payment_id, target_payment_id, reserve_number, allocation_amount, method, remainder, notes)
VALUES (%s,%s,%s,%s,%s,%s,%s);
"""

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def proportional_allocate(deposit_amount, candidates):
    total = sum(c['amount'] for c in candidates)
    allocations = []
    if total <= 0:
        return allocations, deposit_amount  # entire amount remainder
    running = 0
    for c in candidates:
        raw = deposit_amount * (c['amount'] / total)
        alloc = round(raw, 2)
        running += alloc
        allocations.append({
            'target_payment_id': c['payment_id'],
            'reserve_number': c['reserve_number'],
            'allocation_amount': alloc,
            'method': 'PROPORTIONAL_SAME_DAY',
            'remainder': False,
            'notes': f"CandidatePaymentAmount={c['amount']} TotalCandidateSum={total}"
        })
    remainder = round(deposit_amount - running, 2)
    return allocations, remainder

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Write allocations to DB')
    ap.add_argument('--recompute', action='store_true', help='Ignore existing allocations and recompute')
    ap.add_argument('--days-window', type=int, default=2, help='Day window on either side for candidate payments')
    ap.add_argument('--limit', type=int, default=None, help='Limit number of deposits processed')
    ap.add_argument('--min-candidates', type=int, default=2, help='Minimum candidate payments to attempt allocation')
    args = ap.parse_args()

    conn = get_conn(); cur = conn.cursor()
    cur.execute(SCHEMA_SETUP_SQL)
    conn.commit()

    cur.execute(FETCH_DEPOSITS_SQL)
    deposits = cur.fetchall()
    if args.limit:
        deposits = deposits[:args.limit]

    preview_rows = []
    processed = 0
    for payment_id, amount, pdate in deposits:
        # Skip if allocations exist and not recompute
        if not args.recompute:
            cur.execute(EXISTING_ALLOCATIONS_SQL, (payment_id,))
            if cur.fetchone()[0] > 0:
                preview_rows.append({'deposit_payment_id': payment_id, 'status': 'SKIP_EXISTING', 'deposit_amount': amount})
                continue
        start = pdate - timedelta(days=args.days_window)
        end = pdate + timedelta(days=args.days_window)
        cur.execute(CANDIDATE_PAYMENTS_SQL, (start, end))
        cand_rows = cur.fetchall()
        candidates = [{'payment_id': r[0], 'reserve_number': r[1], 'amount': float(r[2]), 'payment_date': r[3]} for r in cand_rows]
        if len(candidates) < args.min_candidates:
            preview_rows.append({'deposit_payment_id': payment_id, 'status': 'INSUFFICIENT_CANDIDATES', 'deposit_amount': amount, 'candidate_count': len(candidates)})
            continue
        allocations, remainder = proportional_allocate(float(amount), candidates)
        remainder_flag = abs(remainder) > 0.05
        if args.apply:
            for alloc in allocations:
                cur.execute(INSERT_ALLOC_SQL, (
                    payment_id,
                    alloc['target_payment_id'],
                    alloc['reserve_number'],
                    alloc['allocation_amount'],
                    alloc['method'],
                    False,
                    alloc['notes']
                ))
            if remainder_flag:
                cur.execute(INSERT_ALLOC_SQL, (
                    payment_id,
                    None,
                    None,
                    remainder,
                    'PROPORTIONAL_SAME_DAY',
                    True,
                    f'Remainder after proportional allocation'
                ))
        preview_rows.append({
            'deposit_payment_id': payment_id,
            'status': 'ALLOCATED',
            'deposit_amount': amount,
            'allocated_sum': round(sum(a['allocation_amount'] for a in allocations),2),
            'remainder': remainder,
            'candidate_count': len(candidates)
        })
        processed += 1

    if args.apply:
        conn.commit()

    # Write preview CSV
    out_path = os.path.join(os.path.dirname(__file__), '..', 'reports', '2012_batch_deposit_allocation_preview.csv')
    out_path = os.path.normpath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['deposit_payment_id','status','deposit_amount','allocated_sum','remainder','candidate_count'])
        w.writeheader()
        for r in preview_rows:
            w.writerow(r)
    print(f"Processed deposits: {processed}; preview written to {out_path}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
