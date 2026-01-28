#!/usr/bin/env python3
"""
Read-only snapshot of core table row counts for assurance auditing.
Writes CSV to staging/audit/core_table_counts_YYYYMMDD_HHMMSS.csv and prints totals.

Safe: SELECT-only. Uses api.get_db_connection() helper.
"""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

try:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent))  # add repo root
    from api import get_db_connection  # type: ignore
except Exception as e:
    print(f"ERROR: Unable to import get_db_connection from api.py: {e}")
    raise

CORE_TABLES = [
    'journal',
    'receipts',
    'payments',
    'charters',
    'clients',
    'employees',
    'vehicles',
    'banking_transactions',
    'unified_general_ledger',
]

def snapshot_counts():
    conn = get_db_connection()
    cur = conn.cursor()
    results = []
    for tbl in CORE_TABLES:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            cnt = cur.fetchone()[0]
            results.append((tbl, cnt, 'OK'))
        except Exception as e:
            results.append((tbl, None, f"ERROR: {e}"))
    cur.close(); conn.close()
    return results


def write_csv(rows):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = Path(r"L:\limo\staging\audit")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"core_table_counts_{ts}.csv"
    with open(out_file, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['table', 'row_count', 'status'])
        for tbl, cnt, status in rows:
            w.writerow([tbl, cnt if cnt is not None else '', status])
    return out_file


def main():
    rows = snapshot_counts()
    out_file = write_csv(rows)
    print("Core table counts (read-only):")
    for tbl, cnt, status in rows:
        print(f" - {tbl:24s} : {cnt if cnt is not None else 'N/A'} {'' if status=='OK' else status}")
    print(f"\nSnapshot written to: {out_file}")


if __name__ == '__main__':
    main()
