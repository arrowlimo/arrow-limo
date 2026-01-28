#!/usr/bin/env python3
"""
Analyze linkage coverage for staging_driver_pay to employees.

Match strategy (analysis only, no writes):
- Primary: staging_driver_pay.driver_id == employees.employee_number
- Secondary: normalized staging_driver_pay.driver_name to employees.full_name or legacy_name
- Report coverage, ambiguous matches, and top unmatched names.
"""

import os
import re
import psycopg2
from collections import Counter, defaultdict
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def normalize_name(name: str) -> str:
    if not name:
        return ''
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9\s,]+', '', s)
    s = re.sub(r'\s+', ' ', s)
    # handle Last, First -> First Last
    if ',' in s:
        parts = [p.strip() for p in s.split(',')]
        if len(parts) >= 2:
            s = parts[1] + ' ' + parts[0]
    return s.strip()

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print('='*80)
    print('STAGING DRIVER PAY → EMPLOYEES LINKAGE ANALYSIS')
    print('='*80)

    # Load employees
    cur.execute(
        """
        SELECT employee_id, employee_number, full_name, legacy_name
        FROM employees
        """
    )
    employees = cur.fetchall()

    emp_by_number = {}
    names_to_empids = defaultdict(set)

    for e in employees:
        if e['employee_number']:
            emp_by_number[e['employee_number']] = e['employee_id']
        for nm in [e['full_name'], e['legacy_name']]:
            if nm:
                names_to_empids[normalize_name(nm)].add(e['employee_id'])

    # Sample through staging_driver_pay (full count aggregation, but avoid pulling all rows fields)
    cur.execute(
        """
        SELECT driver_id, driver_name, COUNT(*) as cnt
        FROM staging_driver_pay
        WHERE driver_id IS NOT NULL OR driver_name IS NOT NULL
        GROUP BY driver_id, driver_name
        """
    )
    rows = cur.fetchall()

    total_groups = 0
    matched_primary = 0
    matched_name_unique = 0
    matched_name_ambiguous = 0
    unmatched = 0

    top_unmatched = []
    unmatched_counter = Counter()

    examples = {
        'primary': [],
        'name_unique': [],
        'name_ambiguous': [],
        'unmatched': []
    }

    for r in rows:
        total_groups += 1
        drv_id = r['driver_id']
        drv_name = r['driver_name']
        cnt = r['cnt']

        # primary match by number
        if drv_id and drv_id in emp_by_number:
            matched_primary += 1
            if len(examples['primary']) < 5:
                examples['primary'].append((drv_id, drv_name, cnt, emp_by_number[drv_id]))
            continue

        # secondary match by normalized name
        nm = normalize_name(drv_name or '')
        candidates = names_to_empids.get(nm, set())
        if candidates:
            if len(candidates) == 1:
                matched_name_unique += 1
                if len(examples['name_unique']) < 5:
                    examples['name_unique'].append((drv_id, drv_name, cnt, list(candidates)[0]))
            else:
                matched_name_ambiguous += 1
                if len(examples['name_ambiguous']) < 5:
                    examples['name_ambiguous'].append((drv_id, drv_name, cnt, sorted(list(candidates))[:3]))
        else:
            unmatched += 1
            unmatched_counter[(drv_id or '', drv_name or '')] += cnt
            if len(examples['unmatched']) < 5:
                examples['unmatched'].append((drv_id, drv_name, cnt))

    print('\nSUMMARY:')
    print(f"  Groups analyzed: {total_groups}")
    print(f"  Matched by driver_id (employee_number): {matched_primary}")
    print(f"  Matched by name (unique): {matched_name_unique}")
    print(f"  Matched by name (ambiguous): {matched_name_ambiguous}")
    print(f"  Unmatched: {unmatched}")

    def pct(x):
        return (x/total_groups*100.0) if total_groups else 0.0

    print('\nCOVERAGE:')
    print(f"  Primary: {pct(matched_primary):.1f}%")
    print(f"  Name (unique): {pct(matched_name_unique):.1f}%")
    print(f"  Name (ambiguous): {pct(matched_name_ambiguous):.1f}%")
    print(f"  Unmatched: {pct(unmatched):.1f}%")

    print('\nEXAMPLES:')
    for k in ['primary','name_unique','name_ambiguous','unmatched']:
        print(f"\n  {k.upper()}:")
        for ex in examples[k]:
            print(f"    driver_id={ex[0]!r} driver_name={ex[1]!r} count={ex[2]} -> {ex[3:]}")

    print('\nTOP 20 UNMATCHED GROUPS (by rows):')
    for (drv_id, drv_name), c in unmatched_counter.most_common(20):
        print(f"  count={c:>6}  driver_id={drv_id!r}  driver_name={drv_name!r}")

    print('\nNEXT STEPS (recommended):')
    print('  1) Build a deterministic mapping table staging_driver_pay_name_map(name_norm -> employee_id) for ambiguous cases')
    print('  2) Auto-link rows where driver_id matches employee_number or unique name match')
    print('  3) Emit a CSV of ambiguous/unmatched for manual curation')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
