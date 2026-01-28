#!/usr/bin/env python
"""
Insert missing LMS charges for a fixed list of reserves.
"""
import os
import sys
import psycopg2
import pyodbc
from collections import Counter
from datetime import datetime, UTC
import json

RESERVES = [
    '015901','015902','012861','016011','016021','016009','016010','016022'
]

MDB_FILE = r"L:\limo\backups\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

OUT_JSON = r"L:\limo\reports\charges_inserted_specific_reserves.json"


def connect_mdb():
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_FILE};"
    return pyodbc.connect(conn_str)


def connect_pg():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def fetch_lms_charges(cur_mdb, reserve_no):
    cur_mdb.execute(
        "SELECT Amount, Desc FROM Charge WHERE Reserve_No = ?",
        reserve_no,
    )
    rows = cur_mdb.fetchall()
    out = []
    for r in rows:
        amt = float(r[0]) if r[0] is not None else 0.0
        desc = r[1] if len(r) > 1 else ''
        desc = (desc or '').strip()
        out.append((amt, desc))
    return out


def fetch_pg_charges(cur_pg, reserve_no):
    cur_pg.execute(
        "SELECT amount, COALESCE(description,'') FROM charter_charges WHERE reserve_number = %s",
        (reserve_no,),
    )
    return [(float(r[0]) if r[0] is not None else 0.0, (r[1] or '').strip()) for r in cur_pg.fetchall()]


def get_charter_id(cur_pg, reserve_no):
    cur_pg.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_no,))
    row = cur_pg.fetchone()
    return row[0] if row else None


def multiset(rows):
    return Counter((round(a,2), d.lower()) for a,d in rows)


def main():
    # Hard guard: respect no-LMS-sync policy
    if os.getenv('DISABLE_LMS_SYNC') == '1' or os.path.exists(r"L:\limo\CONFIG_NO_LMS_SYNC.txt"):
        print("❌ LMS sync disabled: skipping add_missing_charges_for_specific_reserves.py")
        sys.exit(0)

    mdb = connect_mdb(); pg = connect_pg()
    cm = mdb.cursor(); cp = pg.cursor()

    summary = { 'processed': [], 'skipped': [], 'inserted_total': 0 }

    for res in RESERVES:
        charter_id = get_charter_id(cp, res)
        if not charter_id:
            summary['skipped'].append({ 'reserve': res, 'reason': 'no charter_id' })
            continue
        lms_rows = fetch_lms_charges(cm, res)
        pg_rows = fetch_pg_charges(cp, res)
        need = []
        lm = multiset(lms_rows); pm = multiset(pg_rows)
        for key, count in lm.items():
            missing = count - pm.get(key, 0)
            for _ in range(max(missing,0)):
                need.append(key)
        inserted = 0
        for amount, desc in need:
            cp.execute(
                """
                INSERT INTO charter_charges (reserve_number, charter_id, amount, gst_amount, description, created_at, last_updated_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (res, charter_id, amount, 0.0, desc[:200] if desc else None, datetime.now(UTC), 'lms_sync_specific')
            )
            inserted += 1
        summary['processed'].append({ 'reserve': res, 'charter_id': charter_id, 'lms_count': sum(lm.values()), 'pg_count': sum(pm.values()), 'inserted': inserted })
        summary['inserted_total'] += inserted

    pg.commit()
    cm.close(); cp.close(); mdb.close(); pg.close()

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Inserted {summary['inserted_total']} charges; details at {OUT_JSON}")

if __name__ == '__main__':
    main()
