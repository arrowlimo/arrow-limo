#!/usr/bin/env python3
"""
Generate a top 50 sample of driver mismatches for quick review.
Reads exports/driver_audit/mismatches_2021_2024.csv and writes
exports/driver_audit/mismatches_top50.csv sorted by charter_date, pay_date.
"""
import csv
from pathlib import Path
from datetime import datetime

SRC = Path(__file__).parent.parent / 'exports' / 'driver_audit' / 'mismatches_2021_2024.csv'
DST = Path(__file__).parent.parent / 'exports' / 'driver_audit' / 'mismatches_top50.csv'

if not SRC.exists():
    raise SystemExit(f"Not found: {SRC}")

rows = []
with open(SRC, 'r', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        # Normalize date
        cd = row.get('charter_date')
        try:
            row['_cd'] = datetime.fromisoformat(cd) if cd else datetime.min
        except Exception:
            row['_cd'] = datetime.min
        rows.append(row)

rows.sort(key=lambda x: x['_cd'])

headers = [
    'charter_id','reserve_number','charter_date','assigned_driver_name',
    'payroll_entry_id','payroll_employee_name','pay_date','gross_pay','issue'
]

with open(DST, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    for row in rows[:50]:
        w.writerow({k: row.get(k) for k in headers})

print(f"Top 50 mismatches written to: {DST}")
