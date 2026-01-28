"""
Prepare a single best candidate per payment_id from the proposals CSV.

Heuristic (conservative): pick the first row per payment_id as ranked in the
proposals file (already ordered by amount closeness in generator). This creates
an explicit candidates CSV for human review or cautious application.

Outputs: reports/best_match_candidates_pre2025.csv
"""
import os
import csv
from collections import OrderedDict


REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
PROPOSALS = os.path.join(REPORTS_DIR, 'proposed_matches_for_unmatched_pre2025.csv')
OUTPUT = os.path.join(REPORTS_DIR, 'best_match_candidates_pre2025.csv')


def main():
    if not os.path.exists(PROPOSALS):
        print(f"Proposals not found: {PROPOSALS}")
        return

    picked = OrderedDict()
    with open(PROPOSALS, 'r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            pid = row.get('payment_id')
            if not pid:
                continue
            if pid in picked:
                continue
            picked[pid] = {
                'payment_id': row['payment_id'],
                'reserve_number': row['reserve_number'],
                'confidence': row.get('confidence', ''),
            }

    if not picked:
        print('No proposals to pick from.')
        return

    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['payment_id','reserve_number','confidence'])
        w.writeheader()
        for _, row in picked.items():
            w.writerow(row)

    print(f"Best-candidate CSV written: {OUTPUT} ({len(picked)} rows)")


if __name__ == '__main__':
    main()
