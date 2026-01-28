"""Summarize batches flagged with reserve-number relationships (R7).

Reads:
  reports/refund_batch_audit.csv
  reports/refund_candidates_enriched.csv (optional enrichment for source mix per batch)

Writes:
  reports/refund_r7_batches.csv (all R7 batches with metrics and source mix)
  Prints a top-20 preview to console.
"""

from __future__ import annotations
import os, csv
from collections import defaultdict, Counter


def read_csv(path: str):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    audit_rows = read_csv('reports/refund_batch_audit.csv')
    enriched_rows = read_csv('reports/refund_candidates_enriched.csv')

    # Map payment_key -> source classifications found among matches
    source_by_key = defaultdict(Counter)
    for r in enriched_rows:
        key = r.get('payment_key')
        src = r.get('source_classification') or 'Unknown'
        if key:
            source_by_key[key][src] += 1

    r7_rows = [r for r in audit_rows if 'R7' in (r.get('reason_codes') or '')]
    # Sort by repeat_reserve_count desc then payment_count desc
    def keyfn(r):
        try:
            return (int(r.get('repeat_reserve_count') or 0), int(r.get('payment_count') or 0))
        except Exception:
            return (0, 0)
    r7_rows.sort(key=keyfn, reverse=True)

    out_path = 'reports/refund_r7_batches.csv'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fields = ['payment_key','payment_count','distinct_reserves','repeat_reserve_count','negative_count','net_amount','reason_codes','source_mix']
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in r7_rows:
            key = r.get('payment_key')
            mix = source_by_key.get(key, Counter())
            mix_str = ', '.join(f"{k}:{v}" for k, v in mix.most_common()) if mix else ''
            w.writerow({
                'payment_key': key,
                'payment_count': r.get('payment_count'),
                'distinct_reserves': r.get('distinct_reserves'),
                'repeat_reserve_count': r.get('repeat_reserve_count'),
                'negative_count': r.get('negative_count'),
                'net_amount': r.get('net_amount'),
                'reason_codes': r.get('reason_codes'),
                'source_mix': mix_str,
            })

    print(f"✓ R7 summary written: {out_path} ({len(r7_rows)} batches)")
    print("\nTop 20 R7 batches:")
    for r in r7_rows[:20]:
        print(f"  • {r.get('payment_key')}: repeats={r.get('repeat_reserve_count')}, distinct_reserves={r.get('distinct_reserves')}, payments={r.get('payment_count')}, reasons={r.get('reason_codes')}")


if __name__ == '__main__':
    main()
