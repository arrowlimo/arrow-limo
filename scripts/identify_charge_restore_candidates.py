#!/usr/bin/env python3
"""
Identify candidates from WRITE_OFF_MISSING and CANCELLED_NONZERO where charges should be restored.
Filter out likely NRDs (negative balances on cancelled charters, probably deposits).
Output candidates for bulk restore.
"""

import csv
import json

audit_csv = r'L:\limo\reports\ALMS_LMS_BALANCE_AUDIT.csv'
output_candidates = r'L:\limo\reports\CANDIDATES_FOR_CHARGE_RESTORE.csv'
output_summary = r'L:\limo\reports\CANDIDATES_FOR_CHARGE_RESTORE_SUMMARY.json'

candidates = []
nrd_skipped = []

with open(audit_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        category = row['category']
        status = row['status'].lower() if row['status'] else ''
        
        # Filter: only WRITE_OFF_MISSING and CANCELLED_NONZERO
        if category not in ['WRITE_OFF_MISSING', 'CANCELLED_NONZERO']:
            continue
        
        try:
            alms_balance = float(row['alms_balance'])
            lms_balance = float(row['lms_balance']) if row['lms_balance'] else 0.0
        except (ValueError, TypeError):
            continue
        
        # Skip: LMS balance is not ~0
        if abs(lms_balance) >= 1.0:
            continue
        
        # Skip: alms balance is 0
        if abs(alms_balance) < 0.01:
            continue
        
        reserve = row['reserve_number']
        
        # Likely NRD: cancelled with negative balance (deposit held on account)
        if 'cancel' in status and alms_balance < -0.01:
            # Could still be a write-off, but negative balance on cancelled is suspicious
            # For now, skip it (it's probably intended as a retainer/NRD)
            nrd_skipped.append({
                'reserve': reserve,
                'status': status,
                'alms_balance': alms_balance,
                'reason': 'Likely NRD on cancelled charter'
            })
            continue
        
        # Candidate: restore charges
        candidates.append({
            'reserve': reserve,
            'status': status,
            'category': category,
            'alms_charges': float(row['alms_charges'] or 0),
            'alms_payments': float(row['alms_payments'] or 0),
            'alms_balance': alms_balance,
            'lms_charges': float(row['lms_charges'] or 0),
            'lms_balance': lms_balance,
            'action': 'Restore LMS charges to almsdata'
        })

print(f"Total candidates for restore: {len(candidates)}")
print(f"NRDs skipped (likely deposits): {len(nrd_skipped)}")
print()

# Write candidates CSV
with open(output_candidates, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['reserve', 'status', 'category', 'alms_charges', 'alms_payments', 'alms_balance', 'lms_charges', 'lms_balance', 'action']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in candidates:
        writer.writerow(row)

# Summary
summary = {
    'total_candidates': len(candidates),
    'nrd_skipped': len(nrd_skipped),
    'total_charges_to_restore': sum(float(r['lms_charges']) for r in candidates),
    'sample_candidates': [c['reserve'] for c in candidates[:10]],
}

with open(output_summary, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"Candidates: {output_candidates}")
print(f"Summary: {output_summary}")
print()
print(f"Top 10 candidates (by reserve number):")
for c in sorted(candidates, key=lambda x: x['reserve'])[:10]:
    print(f"  {c['reserve']} | alms=${c['alms_balance']:+.2f} | lms_charges=${c['lms_charges']:.2f}")
