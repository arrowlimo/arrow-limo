#!/usr/bin/env python3
"""
Verify reserve numbers continuity and integrity.

Checks:
- LMS staging: lms_staging_reserve.reserve_no values
  * classify as numeric 6-digit, REF*, AUDIT*, other
  * list duplicates, gaps in numeric sequence, min/max
- Main: charters.reserve_number values (same classification)
- Cross-compare: numbers present in LMS but missing in charters and vice versa

Output: concise PASS/FAIL summary with counts and sample gaps.
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor

NUMERIC_RE = re.compile(r"^\d{6}$")
REF_RE = re.compile(r"^REF\d+$", re.IGNORECASE)
AUDIT_RE = re.compile(r"^AUDIT\d+$", re.IGNORECASE)


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def classify(values):
    numeric = []
    ref = []
    audit = []
    other = []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if NUMERIC_RE.match(s):
            numeric.append(int(s))
        elif REF_RE.match(s):
            ref.append(s.upper())
        elif AUDIT_RE.match(s):
            audit.append(s.upper())
        else:
            other.append(s)
    return numeric, ref, audit, other


def summarize_numeric(nums):
    if not nums:
        return {
            'count': 0,
            'min': None,
            'max': None,
            'missing': [],
            'missing_count': 0,
            'duplicates': []
        }
    nums_sorted = sorted(nums)
    # duplicates
    dups = []
    seen = set()
    for n in nums_sorted:
        if n in seen and n not in dups:
            dups.append(n)
        seen.add(n)
    # gaps
    mn, mx = nums_sorted[0], nums_sorted[-1]
    full = set(range(mn, mx + 1))
    miss = sorted(list(full.difference(set(nums_sorted))))
    return {
        'count': len(nums_sorted),
        'min': mn,
        'max': mx,
        'missing': miss,
        'missing_count': len(miss),
        'duplicates': dups
    }


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print('='*80)
    print('RESERVE NUMBER SEQUENCE VERIFICATION')
    print('='*80)

    # LMS staging
    cur.execute("SELECT reserve_no FROM lms_staging_reserve")
    lms_vals = [row['reserve_no'] for row in cur.fetchall()]
    lms_numeric, lms_ref, lms_audit, lms_other = classify(lms_vals)
    lms_summary = summarize_numeric(lms_numeric)

    print('\nLMS STAGING (lms_staging_reserve)')
    print('-'*80)
    print(f"Total: {len(lms_vals)} | Numeric: {len(lms_numeric)} | REF: {len(lms_ref)} | AUDIT: {len(lms_audit)} | Other: {len(lms_other)}")
    print(f"Numeric range: {lms_summary['min']} - {lms_summary['max']}")
    print(f"Missing count: {lms_summary['missing_count']}")
    if lms_summary['missing_count'] > 0:
        sample = lms_summary['missing'][:25]
        print(f"  Sample missing ({len(sample)} shown): {sample}")
    print(f"Duplicates: {len(lms_summary['duplicates'])}")
    if lms_summary['duplicates']:
        print(f"  Duplicate numbers: {lms_summary['duplicates'][:20]}")

    # MAIN charters
    cur.execute("SELECT reserve_number FROM charters")
    ch_vals = [row['reserve_number'] for row in cur.fetchall()]
    ch_numeric, ch_ref, ch_audit, ch_other = classify(ch_vals)
    ch_summary = summarize_numeric(ch_numeric)

    print('\nMAIN (charters)')
    print('-'*80)
    print(f"Total: {len(ch_vals)} | Numeric: {len(ch_numeric)} | REF: {len(ch_ref)} | AUDIT: {len(ch_audit)} | Other: {len(ch_other)}")
    print(f"Numeric range: {ch_summary['min']} - {ch_summary['max']}")
    print(f"Missing count: {ch_summary['missing_count']}")
    if ch_summary['missing_count'] > 0:
        sample = ch_summary['missing'][:25]
        print(f"  Sample missing ({len(sample)} shown): {sample}")
    print(f"Duplicates: {len(ch_summary['duplicates'])}")
    if ch_summary['duplicates']:
        print(f"  Duplicate numbers: {ch_summary['duplicates'][:20]}")

    # Cross compare (numeric only)
    set_lms = set(lms_numeric)
    set_ch = set(ch_numeric)
    only_in_lms = sorted(list(set_lms - set_ch))
    only_in_charters = sorted(list(set_ch - set_lms))

    print('\nCROSS-COMPARISON (numeric)')
    print('-'*80)
    print(f"In LMS but not in charters: {len(only_in_lms)}")
    if only_in_lms:
        print(f"  Sample: {only_in_lms[:25]}")
    print(f"In charters but not in LMS: {len(only_in_charters)}")
    if only_in_charters:
        print(f"  Sample: {only_in_charters[:25]}")

    # Pass/Fail judgement for LMS continuity
    print('\nRESULT:')
    if lms_summary['missing_count'] == 0 and not lms_summary['duplicates']:
        print('[OK] LMS reserve numbers are continuous (no gaps) and have no duplicates among numeric values.')
    else:
        print('[WARN]  LMS reserve numbers have gaps and/or duplicates. See details above.')

    # Note AUDIT entries
    if lms_audit:
        print(f"Note: Found {len(lms_audit)} AUDIT entries (special). Excluded from numeric continuity check.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
