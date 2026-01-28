"""Document resolved R7 cases to exclude from future suspicious batch reviews.

Maintains a record of R7 batches that have been manually verified as legitimate.
"""

import csv
import os
from datetime import datetime

# Resolved cases
RESOLVED_CASES = [
    {
        'date_resolved': '2025-11-10',
        'batch_key': '0020524',
        'reserve_number': '017720',
        'occurrences': 6,
        'reason': 'Non-recoverable balance adjustment - charter balanced to $0',
        'resolved_by': 'Manual verification',
        'notes': 'Balance marked as not recoverable, multiple adjusting entries to zero out charter',
        'status': 'LEGITIMATE'
    }
]

def main():
    out_path = 'reports/r7_resolved_cases.csv'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    fieldnames = ['date_resolved', 'batch_key', 'reserve_number', 'occurrences', 
                  'reason', 'resolved_by', 'notes', 'status']
    
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(RESOLVED_CASES)
    
    print(f"✓ Documented {len(RESOLVED_CASES)} resolved R7 cases")
    print(f"  File: {out_path}")
    
    for case in RESOLVED_CASES:
        print(f"\n  Batch {case['batch_key']}, Reserve {case['reserve_number']}:")
        print(f"    {case['reason']}")
        print(f"    Status: {case['status']}")

if __name__ == '__main__':
    main()
