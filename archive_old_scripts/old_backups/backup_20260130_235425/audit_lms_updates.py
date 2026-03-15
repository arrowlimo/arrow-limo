#!/usr/bin/env python
"""
Audit LMS (Access MDB) tables for updated rows and export a list of what changed signals.

Outputs:
- reports/LMS_UPDATES_SUMMARY.json: counts by table and recent date windows
- reports/LMS_UPDATES_DETAILS.csv: row-level details with keys and LastUpdated/LastUpdatedBy

Notes:
- We do not modify LMS; this is read-only.
- "What was changed" is inferred from LastUpdated/LastUpdatedBy fields; field-level diffs
  require comparing two snapshots which we can add if needed.
"""
import os
import csv
import json
from datetime import datetime
import pyodbc

MDB_FILE = r"L:\limo\backups\lms.mdb"
CSV_OUT = r"L:\limo\reports\LMS_UPDATES_DETAILS.csv"
JSON_OUT = r"L:\limo\reports\LMS_UPDATES_SUMMARY.json"

TABLES = [
    {
        'name': 'Reserve',
        'key': 'Reserve_No',
        'fields': ['Reserve_No', 'Client', 'Event', 'Balance', 'LastUpdated', 'LastUpdatedBy']
    },
    {
        'name': 'Charge',
        'key': 'ChargeID',
        'fields': ['ChargeID', 'Reserve_No', 'Amount', 'Desc', 'LastUpdated', 'LastUpdatedBy']
    },
    {
        'name': 'Payment',
        'key': 'PaymentID',
        'fields': ['PaymentID', 'Reserve_No', 'Amount', 'Payment_Date', 'Method', 'LastUpdated', 'LastUpdatedBy']
    },
]


def connect_mdb():
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_FILE};"
    return pyodbc.connect(conn_str)


def safe_query(cur, table, fields):
    try:
        # Introspect available columns
        cur.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description] if cur.description else []
        # Build select with only existing columns
        selected = [f for f in fields if f in cols]
        if not selected:
            # Fall back to key + LastUpdated/LastUpdatedBy if present
            selected = []
            for f in ['Reserve_No', 'ChargeID', 'PaymentID', 'Amount', 'Desc', 'Payment_Date', 'Balance', 'LastUpdated', 'LastUpdatedBy']:
                if f in cols:
                    selected.append(f)
        cur.execute(f"SELECT {', '.join(selected)} FROM {table}")
        rows = cur.fetchall()
        # Map rows to dicts with requested fields, fill missing with None
        # Ensure returned order matches 'fields' list for downstream code
        normalized = []
        for r in rows:
            rec = {}
            # Build dict of available selected columns
            for i, col in enumerate(selected):
                rec[col] = r[i]
            # Ensure keys for downstream
            for f in fields:
                if f not in rec:
                    rec[f] = None
            normalized.append(rec)
        return normalized
    except Exception as e:
        print(f"Skipping table {table}: {e}")
        return []


def to_iso(dt):
    if dt is None:
        return None
    try:
        # pyodbc returns datetime or string
        if isinstance(dt, str):
            return dt
        return dt.isoformat()
    except Exception:
        return str(dt)


def main():
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)

    conn = connect_mdb()
    cur = conn.cursor()

    summary = {'tables': {}, 'generated_at': datetime.now().isoformat()}
    details_rows = []

    for tbl in TABLES:
        name = tbl['name']
        fields = tbl['fields']
        key_field = tbl['key']
        rows = safe_query(cur, name, fields)
        updated = 0
        non_null = 0
        latest = None
        for record in rows:
            lu = record.get('LastUpdated')
            lub = record.get('LastUpdatedBy')
            lu_iso = to_iso(lu)
            is_updated = (lu is not None) or (lub is not None and str(lub).strip() != '')
            if is_updated:
                updated += 1
                # Track latest
                try:
                    if lu is not None and (latest is None or lu > latest):
                        latest = lu
                except Exception:
                    pass
                # Append detail
                details_rows.append({
                    'table': name,
                    'key': str(record.get(key_field)) if record.get(key_field) is not None else '',
                    'reserve': str(record.get('Reserve_No')) if record.get('Reserve_No') is not None else '',
                    'amount': str(record.get('Amount')) if 'Amount' in record and record.get('Amount') is not None else '',
                    'desc': str(record.get('Desc')) if 'Desc' in record and record.get('Desc') is not None else '',
                    'method': str(record.get('Method')) if 'Method' in record and record.get('Method') is not None else '',
                    'payment_date': str(record.get('Payment_Date')) if 'Payment_Date' in record and record.get('Payment_Date') is not None else '',
                    'balance': str(record.get('Balance')) if 'Balance' in record and record.get('Balance') is not None else '',
                    'last_updated': lu_iso or '',
                    'last_updated_by': str(lub) if lub is not None else ''
                })
            if lu is not None:
                non_null += 1
        total = len(rows)
        summary['tables'][name] = {
            'total_rows': total,
            'updated_rows': updated,
            'rows_with_lastupdated': non_null,
            'latest_lastupdated': to_iso(latest)
        }

    # Write CSV details
    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['table','key','reserve','amount','desc','method','payment_date','balance','last_updated','last_updated_by'])
        writer.writeheader()
        writer.writerows(details_rows)

    # Write JSON summary
    with open(JSON_OUT, 'w', encoding='utf-8') as jf:
        json.dump(summary, jf, indent=2)

    print(f"Summary: {JSON_OUT}")
    print(f"Details: {CSV_OUT} ({len(details_rows)} updated rows)")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
