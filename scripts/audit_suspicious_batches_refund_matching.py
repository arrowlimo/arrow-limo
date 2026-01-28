"""Audit payment_key batches for refund / reversal patterns and reserve number relationships.

Usage (dry run by default):
  python -X utf8 scripts/audit_suspicious_batches_refund_matching.py \
        [--lookback-days 30] [--min-negative-threshold 5.00] [--exclude-pennies] [--limit-batches 500] [--write]

Outputs (always generated; write flag is only for future mutation features - currently read-only):
  reports/refund_batch_audit.csv              (one row per batch with metrics)
  reports/refund_candidates_detailed.csv      (one row per suspected refund or unmatched negative)
  reports/refund_batch_audit_summary.md       (human summary of top suspicious batches)

Refund / reversal logic (hierarchical):
  1. Intra-batch exact match: negative amount equals prior positive amount (same reserve_number or account_number).
  2. Intra-batch aggregation: sum of multiple negatives equals a prior positive for same reserve_number.
  3. Cross-batch prior positive within lookback-days window (positive earlier, negative now) for same reserve_number.
  4. High negative ratio: negatives > 40% of lines OR net near zero (abs(net) <= 0.5% of total positive) with mixed signs.

Balancing pennies: abs(amount) <= 0.01 => classified separately (never refund).

Reserve number relationships flagged when payment_count != distinct_reserves OR any reserve_number repeats in a batch OR negative entries reference a reserve_number that also has a positive entry in same batch.

Environment variables: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD.
No data modifications are performed.
"""

from __future__ import annotations

import os
import sys
import csv
import math
import argparse
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import psycopg2
import psycopg2.extras


@dataclass
class PaymentRow:
    payment_id: int
    payment_key: str
    reserve_number: Optional[str]
    charter_id: Optional[int]
    account_number: Optional[str]
    amount: float
    payment_date: Optional[datetime]
    created_at: Optional[datetime]
    payment_method: Optional[str]


@dataclass
class RefundCandidate:
    payment_key: str
    negative_payment_id: int
    negative_amount: float
    negative_reserve: Optional[str]
    negative_date: Optional[datetime]
    match_type: str  # INTRA_EXACT | INTRA_AGG | CROSS_BATCH | UNMATCHED
    matched_positive_id: Optional[int] = None
    matched_positive_amount: Optional[float] = None
    matched_positive_date: Optional[datetime] = None
    matched_positive_reserve: Optional[str] = None
    reason_codes: List[str] = field(default_factory=list)

@dataclass
class BatchMetrics:
    payment_key: str
    payment_count: int
    distinct_reserves: int
    distinct_charters: int
    repeat_reserve_count: int
    total_positive: float
    total_negative: float
    net_amount: float
    negative_count: int
    penny_count: int
    refund_candidate_count: int
    span_days: int
    earliest_date: Optional[datetime]
    latest_date: Optional[datetime]
    negative_ratio: float
    suspicious: bool
    reason_codes: List[str]


REASON = {
    'R1': 'intra_batch_exact_refund',
    'R2': 'cross_batch_refund',
    'R3': 'net_zero_mixed_sign',
    'R4': 'high_negative_ratio',
    'R5': 'multi_negative_matching_positive',
    'R6': 'unmatched_negative_over_threshold',
    'R7': 'repeat_reserve_numbers',
}


def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            dbname=os.getenv('DB_NAME', 'almsdata'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        )
        return conn
    except Exception as e:
        print(f"[FAIL] Database connection failed: {e}")
        sys.exit(2)


def load_payments(conn, limit_batches: Optional[int] = None) -> List[PaymentRow]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # We combine amount columns defensively; some schemas have both amount/payment_amount
    # Negative amounts may denote refunds/reversals.
    sql = """
        WITH base AS (
            SELECT payment_id, payment_key,
                   reserve_number, charter_id, account_number,
                   COALESCE(payment_amount, amount, 0) AS amt,
                   payment_date, created_at, payment_method
            FROM payments
            WHERE payment_key IS NOT NULL AND payment_key <> ''
        ), ranked AS (
            SELECT payment_key, COUNT(*) AS cnt
            FROM base
            GROUP BY payment_key
            ORDER BY cnt DESC
        )
        SELECT b.* FROM base b
        JOIN ranked r USING (payment_key)
        ORDER BY b.payment_key, b.payment_id
    """
    cur.execute(sql)
    rows = cur.fetchall()
    payments = [
        PaymentRow(
            payment_id=row['payment_id'],
            payment_key=row['payment_key'],
            reserve_number=row['reserve_number'],
            charter_id=row['charter_id'],
            account_number=row['account_number'],
            amount=float(row['amt'] or 0),
            payment_date=row['payment_date'],
            created_at=row['created_at'],
            payment_method=row['payment_method']
        ) for row in rows
    ]
    if limit_batches:
        # Keep only first N distinct payment_keys
        seen = []
        keep_keys = set()
        for p in payments:
            if p.payment_key not in keep_keys:
                if len(seen) >= limit_batches:
                    break
                keep_keys.add(p.payment_key)
                seen.append(p.payment_key)
        payments = [p for p in payments if p.payment_key in keep_keys]
    return payments


def group_by_batch(payments: List[PaymentRow]) -> Dict[str, List[PaymentRow]]:
    batches: Dict[str, List[PaymentRow]] = defaultdict(list)
    for p in payments:
        batches[p.payment_key].append(p)
    return batches


def find_refund_candidates(batches: Dict[str, List[PaymentRow]], lookback_days: int,
                           min_negative_threshold: float, exclude_pennies: bool,
                           prior_index: Dict[str, List[PaymentRow]]) -> Tuple[Dict[str, BatchMetrics], List[RefundCandidate]]:
    batch_metrics: Dict[str, BatchMetrics] = {}
    candidates: List[RefundCandidate] = []
    lookback_delta = timedelta(days=lookback_days)

    # Build cross-batch positive lookup by reserve_number for quick matching
    positives_by_reserve: Dict[str, List[PaymentRow]] = defaultdict(list)
    for rows in prior_index.values():
        for r in rows:
            if r.amount > 0 and r.reserve_number:
                positives_by_reserve[r.reserve_number].append(r)

    for key, rows in batches.items():
        positives = [r for r in rows if r.amount > 0]
        negatives = [r for r in rows if r.amount < 0]
        pennies = [r for r in rows if abs(r.amount) <= 0.01]
        if exclude_pennies:
            negatives_effective = [r for r in negatives if abs(r.amount) > 0.01]
        else:
            negatives_effective = negatives

        reserve_numbers = [r.reserve_number for r in rows if r.reserve_number]
        distinct_reserves = len(set(reserve_numbers))
        distinct_charters = len({r.charter_id for r in rows if r.charter_id is not None})
        repeat_reserve_count = sum(v for v in Counter(reserve_numbers).values() if v > 1)

        total_positive = sum(r.amount for r in positives)
        total_negative = sum(r.amount for r in negatives)
        net_amount = total_positive + total_negative

        all_dates = [r.payment_date or r.created_at for r in rows if (r.payment_date or r.created_at)]
        earliest = min(all_dates) if all_dates else None
        latest = max(all_dates) if all_dates else None
        span_days = (latest - earliest).days if earliest and latest else 0
        negative_ratio = len(negatives_effective) / len(rows) if rows else 0

        reason_codes: List[str] = []

        # Reserve repetition flag
        if repeat_reserve_count > 0 or distinct_reserves != len(rows):
            reason_codes.append('R7')

        # Net near-zero mixed sign
        if total_positive > 0 and total_negative < 0:
            if abs(net_amount) <= 0.005 * total_positive and len(negatives_effective) > 0:
                reason_codes.append('R3')

        # High negative ratio
        if negative_ratio >= 0.4 and len(negatives_effective) >= 2:
            reason_codes.append('R4')

        # Intra-batch matching
        positives_by_reserve_local: Dict[str, List[PaymentRow]] = defaultdict(list)
        for p in positives:
            if p.reserve_number:
                positives_by_reserve_local[p.reserve_number].append(p)

        # Aggregate detection helper
        def try_aggregate_match(neg: PaymentRow) -> Optional[PaymentRow]:
            # If multiple negatives sum to a positive amount in same reserve
            if not neg.reserve_number:
                return None
            poss = positives_by_reserve_local.get(neg.reserve_number, [])
            if not poss:
                return None
            target_amounts = {round(p.amount, 2): p for p in poss}
            # Try sums of other negatives excluding current
            other_negs = [n for n in negatives_effective if n != neg and n.reserve_number == neg.reserve_number]
            if not other_negs:
                return None
            # Basic subset sum with small set limit
            amounts = [round(abs(n.amount), 2) for n in other_negs]
            # Limit complexity
            if len(amounts) > 15:
                return None
            # Simple DP
            reachable = {0: []}
            for idx, amt in enumerate(amounts):
                new_reachable = dict(reachable)
                for s, used in reachable.items():
                    new_sum = round(s + amt, 2)
                    if new_sum not in new_reachable:
                        new_reachable[new_sum] = used + [idx]
                reachable = new_reachable
            for pos_amt, pos_row in target_amounts.items():
                if pos_amt in reachable and math.isclose(pos_amt, abs(neg.amount) + sum(amounts[i] for i in reachable[pos_amt]), rel_tol=1e-4, abs_tol=0.01):
                    return pos_row
            return None

        for neg in negatives_effective:
            amt_abs = abs(neg.amount)
            if amt_abs < min_negative_threshold and amt_abs > 0.01:
                # Skip small fee-like negatives unless exact match exists
                pass
            match_row = None
            match_type = 'UNMATCHED'

            # 1. Intra-batch exact
            if neg.reserve_number and neg.reserve_number in positives_by_reserve_local:
                for pos in positives_by_reserve_local[neg.reserve_number]:
                    if math.isclose(pos.amount, amt_abs, rel_tol=1e-4, abs_tol=0.01):
                        match_row = pos
                        match_type = 'INTRA_EXACT'
                        reason_codes.append('R1')
                        break

            # 2. Intra-batch aggregate
            if not match_row:
                agg = try_aggregate_match(neg)
                if agg:
                    match_row = agg
                    match_type = 'INTRA_AGG'
                    reason_codes.append('R5')

            # 3. Cross-batch prior positive
            if not match_row and neg.reserve_number and neg.reserve_number in positives_by_reserve:
                for pos in positives_by_reserve[neg.reserve_number]:
                    if pos.payment_date and neg.payment_date:
                        if pos.payment_date < neg.payment_date and (neg.payment_date - pos.payment_date) <= lookback_delta:
                            if math.isclose(abs(pos.amount), amt_abs, rel_tol=1e-4, abs_tol=0.01):
                                match_row = pos
                                match_type = 'CROSS_BATCH'
                                reason_codes.append('R2')
                                break
            if not match_row:
                # Unmatched significant negative
                if amt_abs >= min_negative_threshold:
                    reason_codes.append('R6')

            candidates.append(RefundCandidate(
                payment_key=key,
                negative_payment_id=neg.payment_id,
                negative_amount=neg.amount,
                negative_reserve=neg.reserve_number,
                negative_date=neg.payment_date,
                match_type=match_type,
                matched_positive_id=match_row.payment_id if match_row else None,
                matched_positive_amount=match_row.amount if match_row else None,
                matched_positive_date=match_row.payment_date if match_row else None,
                matched_positive_reserve=match_row.reserve_number if match_row else None,
                reason_codes=list(set(reason_codes))
            ))

        suspicious = len(reason_codes) > 0
        batch_metrics[key] = BatchMetrics(
            payment_key=key,
            payment_count=len(rows),
            distinct_reserves=distinct_reserves,
            distinct_charters=distinct_charters,
            repeat_reserve_count=repeat_reserve_count,
            total_positive=total_positive,
            total_negative=total_negative,
            net_amount=net_amount,
            negative_count=len(negatives_effective),
            penny_count=len(pennies),
            refund_candidate_count=sum(1 for c in candidates if c.payment_key == key),
            span_days=span_days,
            earliest_date=earliest,
            latest_date=latest,
            negative_ratio=negative_ratio,
            suspicious=suspicious,
            reason_codes=sorted(set(reason_codes))
        )

    return batch_metrics, candidates


def write_csv_batch_metrics(path: str, metrics: Dict[str, BatchMetrics]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'payment_key','payment_count','distinct_reserves','distinct_charters','repeat_reserve_count',
            'total_positive','total_negative','net_amount','negative_count','penny_count','refund_candidate_count',
            'span_days','earliest_date','latest_date','negative_ratio','suspicious','reason_codes'
        ])
        for m in metrics.values():
            w.writerow([
                m.payment_key, m.payment_count, m.distinct_reserves, m.distinct_charters, m.repeat_reserve_count,
                f"{m.total_positive:.2f}", f"{m.total_negative:.2f}", f"{m.net_amount:.2f}", m.negative_count, m.penny_count,
                m.refund_candidate_count, m.span_days,
                m.earliest_date.isoformat() if m.earliest_date else '',
                m.latest_date.isoformat() if m.latest_date else '',
                f"{m.negative_ratio:.3f}", 'Y' if m.suspicious else 'N', ';'.join(m.reason_codes)
            ])


def write_csv_candidates(path: str, candidates: List[RefundCandidate]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'payment_key','negative_payment_id','negative_amount','negative_reserve','negative_date',
            'match_type','matched_positive_id','matched_positive_amount','matched_positive_reserve','matched_positive_date','reason_codes'
        ])
        for c in candidates:
            w.writerow([
                c.payment_key, c.negative_payment_id, f"{c.negative_amount:.2f}", c.negative_reserve or '',
                c.negative_date.isoformat() if c.negative_date else '', c.match_type,
                c.matched_positive_id or '',
                f"{c.matched_positive_amount:.2f}" if c.matched_positive_amount else '',
                c.matched_positive_reserve or '',
                c.matched_positive_date.isoformat() if c.matched_positive_date else '',
                ';'.join(sorted(set(c.reason_codes)))
            ])


def write_summary(path: str, metrics: Dict[str, BatchMetrics]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Sort suspicious batches by composite risk score
    def risk_score(m: BatchMetrics) -> Tuple[int, float, float]:
        return (len(m.reason_codes), m.negative_ratio, abs(m.net_amount))
    suspicious = [m for m in metrics.values() if m.suspicious]
    suspicious.sort(key=risk_score, reverse=True)
    top = suspicious[:25]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# Refund / Reversal Batch Audit Summary\n\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()} UTC\n\n")
        f.write(f"Total batches analyzed: {len(metrics)}\n")
        f.write(f"Suspicious batches: {len(suspicious)}\n\n")
        f.write("## Top Suspicious Batches\n\n")
        for m in top:
            f.write(f"- {m.payment_key}: payments={m.payment_count}, distinct_reserves={m.distinct_reserves}, repeats={m.repeat_reserve_count}, ")
            f.write(f"pos={m.total_positive:.2f}, neg={m.total_negative:.2f}, net={m.net_amount:.2f}, neg_ratio={m.negative_ratio:.2%}, reasons={';'.join(m.reason_codes)}\n")
        f.write("\nReason Codes:\n")
        for code, desc in REASON.items():
            f.write(f"- {code}: {desc}\n")


def build_prior_index(payments: List[PaymentRow]) -> Dict[str, List[PaymentRow]]:
    by_key: Dict[str, List[PaymentRow]] = defaultdict(list)
    for p in payments:
        by_key[p.payment_key].append(p)
    return by_key


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Audit payment_key batches for refund / reversal patterns")
    ap.add_argument('--lookback-days', type=int, default=30, help='Cross-batch matching lookback window (days)')
    ap.add_argument('--min-negative-threshold', type=float, default=5.00, help='Minimum negative to treat as potential refund if unmatched')
    ap.add_argument('--exclude-pennies', action='store_true', help='Exclude <= $0.01 lines from negative analysis')
    ap.add_argument('--limit-batches', type=int, help='Limit number of batches (for quick test)')
    ap.add_argument('--write', action='store_true', help='Reserved for future data mutation features (currently no effect)')
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    conn = get_db_connection()
    try:
        payments = load_payments(conn, limit_batches=args.limit_batches)
        prior_index = build_prior_index(payments)  # For cross-batch matching we reuse all loaded payments
        batches = group_by_batch(payments)
        metrics, candidates = find_refund_candidates(
            batches,
            lookback_days=args.lookback_days,
            min_negative_threshold=args.min_negative_threshold,
            exclude_pennies=args.exclude_pennies,
            prior_index=prior_index
        )
        write_csv_batch_metrics('reports/refund_batch_audit.csv', metrics)
        write_csv_candidates('reports/refund_candidates_detailed.csv', candidates)
        write_summary('reports/refund_batch_audit_summary.md', metrics)

        # Quick console highlights of reserve relationships
        suspicious_with_reserve_repeats = [m for m in metrics.values() if 'R7' in m.reason_codes]
        print(f"\n🔍 Reserve number relationship batches: {len(suspicious_with_reserve_repeats)}")
        for m in suspicious_with_reserve_repeats[:15]:
            print(f"  • {m.payment_key}: repeats={m.repeat_reserve_count}, distinct_reserves={m.distinct_reserves}, payments={m.payment_count}, reasons={';'.join(m.reason_codes)}")

        print("\n[OK] Completed refund batch audit.")
        print("   CSV: reports/refund_batch_audit.csv")
        print("   CSV: reports/refund_candidates_detailed.csv")
        print("   MD : reports/refund_batch_audit_summary.md")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
