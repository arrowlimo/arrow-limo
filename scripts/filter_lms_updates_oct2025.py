#!/usr/bin/env python
"""
Filter LMS updates to show only changes since October 2025.
Produces a focused report of recent activity.
"""
import csv
import json
from datetime import datetime
from collections import defaultdict

CSV_IN = r"L:\limo\reports\LMS_UPDATES_DETAILS.csv"
CSV_OUT = r"L:\limo\reports\LMS_UPDATES_SINCE_OCT2025.csv"
JSON_OUT = r"L:\limo\reports\LMS_UPDATES_SINCE_OCT2025_SUMMARY.json"

CUTOFF = datetime(2025, 10, 1)

def parse_date(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('T', ' ').split('.')[0])
    except:
        return None

def main():
    recent = []
    reserves_touched = set()
    by_reserve = defaultdict(list)
    
    with open(CSV_IN, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_date(row.get('last_updated', ''))
            if dt and dt >= CUTOFF:
                recent.append(row)
                reserve = row.get('reserve', '')
                if reserve:
                    reserves_touched.add(reserve)
                    by_reserve[reserve].append(row)
    
    # Write filtered CSV
    if recent:
        with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=recent[0].keys())
            writer.writeheader()
            writer.writerows(recent)
    
    # Summary
    summary = {
        'cutoff_date': CUTOFF.isoformat(),
        'total_updates': len(recent),
        'reserves_affected': len(reserves_touched),
        'by_table': {},
        'top_20_reserves': []
    }
    
    # Count by table
    for row in recent:
        tbl = row.get('table', 'unknown')
        summary['by_table'][tbl] = summary['by_table'].get(tbl, 0) + 1
    
    # Top reserves by update count
    reserve_counts = [(res, len(rows)) for res, rows in by_reserve.items()]
    reserve_counts.sort(key=lambda x: x[1], reverse=True)
    
    for res, cnt in reserve_counts[:20]:
        rows = by_reserve[res]
        total_amt = sum(float(r.get('amount', 0) or 0) for r in rows)
        summary['top_20_reserves'].append({
            'reserve_number': res,
            'update_count': cnt,
            'total_amount': round(total_amt, 2),
            'descriptions': list(set(r.get('desc', '') for r in rows if r.get('desc')))[:5]
        })
    
    with open(JSON_OUT, 'w', encoding='utf-8') as jf:
        json.dump(summary, jf, indent=2)
    
    print(f"Since Oct 2025: {len(recent)} updates across {len(reserves_touched)} reserves")
    print(f"Details: {CSV_OUT}")
    print(f"Summary: {JSON_OUT}")
    
    if summary['top_20_reserves']:
        print("\nTop 5 reserves by update count:")
        for item in summary['top_20_reserves'][:5]:
            print(f"  {item['reserve_number']}: {item['update_count']} updates, ${item['total_amount']:.2f}")

if __name__ == '__main__':
    main()
