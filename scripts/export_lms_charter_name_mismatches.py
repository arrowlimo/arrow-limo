import os
import csv
import json
from datetime import datetime

from verify_lms_reserve_client_consistency import (
    build_combined_lms_mapping,
    load_charters_and_clients,
    compare,
)


def ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def main():
    lms_map, sources = build_combined_lms_mapping()
    charter_map = load_charters_and_clients()
    report = compare(lms_map, sources, charter_map)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out1 = os.path.join('l:\\limo', 'reports', f'lms_charter_name_mismatches_{ts}.csv')
    out2 = os.path.join('l:\\limo', 'reports', f'charters_missing_client_id_{ts}.csv')
    out3 = os.path.join('l:\\limo', 'reports', f'lms_missing_in_charters_{ts}.csv')
    meta = os.path.join('l:\\limo', 'reports', f'lms_charter_name_summary_{ts}.json')

    ensure_dir(out1)

    # write mismatches
    with open(out1, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number', 'lms_name', 'charter_display_name', 'client_name'])
        for item in report['name_mismatches']:
            w.writerow([
                item['reserve_number'],
                item['lms_name'],
                item['charter_display'],
                item['client_name'],
            ])

    # write charters with missing client_id
    with open(out2, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number', 'charter_display_name'])
        for rn in report['client_missing']:
            info = charter_map.get(rn, {})
            w.writerow([rn, info.get('charter_client_display_name', '')])

    # write LMS reserves missing in charters
    with open(out3, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number', 'lms_name'])
        for rn in report['missing_in_charters']:
            w.writerow([rn, lms_map.get(rn, '')])

    # write summary meta
    summary = {
        'counts': report.get('counts') or {
            'total_lms_reserves': report['total_lms_reserves'],
            'matched_in_charters': report['matched_in_charters'],
            'perfect_matches': report['perfect_matches'],
            'name_mismatches': len(report['name_mismatches']),
            'missing_in_charters': len(report['missing_in_charters']),
            'client_missing_on_charter': len(report['client_missing'])
        },
        'source_breakdown': report['by_source']
    }
    with open(meta, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print('Wrote:')
    print(' ', out1)
    print(' ', out2)
    print(' ', out3)
    print(' ', meta)


if __name__ == '__main__':
    main()
