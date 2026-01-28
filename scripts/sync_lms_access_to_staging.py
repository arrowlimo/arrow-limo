#!/usr/bin/env python3
"""
Sync LMS Access tables into Postgres staging tables (idempotent, incremental).
Tables: Reserve, Payment, Customer, Vehicles

Design
- Each staging table stores a natural key, last_updated (from Access), and raw JSON payload of the entire row
- Upsert by natural key; only rows with LastUpdated > max(last_updated) in staging are fetched after first run
- Writes a concise summary to stdout and to reports/lms_staging_sync_summary.csv

Safe to run repeatedly.
"""
from __future__ import annotations
import os
import csv
import json
from datetime import datetime

import pyodbc
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

load_dotenv()

ACCESS_PATH = os.environ.get('LMS_ACCESS_PATH', r'L:\limo\docs\lms.mdb')
PG_HOST = os.getenv('DB_HOST', 'localhost')
PG_PORT = int(os.getenv('DB_PORT', '5432'))
PG_NAME = os.getenv('DB_NAME', 'almsdata')
PG_USER = os.getenv('DB_USER', 'postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD', '')
SUMMARY_CSV = r'l:/limo/reports/lms_staging_sync_summary.csv'

ACCESS_CONN_STR = (
    r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
    f'DBQ={ACCESS_PATH};'
)

STAGING_DDL = {
    'lms_staging_reserve': '''
        CREATE TABLE IF NOT EXISTS lms_staging_reserve (
            reserve_no TEXT PRIMARY KEY,
            last_updated TIMESTAMPTZ,
            raw_data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''',
    'lms_staging_payment': '''
        CREATE TABLE IF NOT EXISTS lms_staging_payment (
            payment_id INTEGER PRIMARY KEY,
            reserve_no TEXT,
            last_updated TIMESTAMPTZ,
            raw_data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''',
    'lms_staging_customer': '''
        CREATE TABLE IF NOT EXISTS lms_staging_customer (
            customer_id INTEGER PRIMARY KEY,
            last_updated TIMESTAMPTZ,
            raw_data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''',
    'lms_staging_vehicles': '''
        CREATE TABLE IF NOT EXISTS lms_staging_vehicles (
            vehicle_code TEXT PRIMARY KEY,
            vin TEXT,
            last_updated TIMESTAMPTZ,
            raw_data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    ''',
}


def ensure_staging(pg_conn):
    with pg_conn.cursor() as cur:
        for ddl in STAGING_DDL.values():
            cur.execute(ddl)
    pg_conn.commit()


def dt_to_iso(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        # Assume Access datetime is naive local time; store as ISO string
        return val.isoformat(sep=' ', timespec='seconds')
    return str(val)


def fetch_incremental_rows(acc_cursor, table: str, last_updated_col: str | None, key_filter_sql: str | None = None, params: tuple = ()):
    # Determine incremental predicate
    if last_updated_col:
        where_clause = f"WHERE {last_updated_col} > ?"
        query_params = params
    else:
        where_clause = ""
        query_params = params
    # Build SELECT
    if last_updated_col:
        sql = f"SELECT * FROM {table} {where_clause} ORDER BY {last_updated_col}"
    else:
        sql = f"SELECT * FROM {table}"
    if key_filter_sql:
        if where_clause:
            sql = f"SELECT * FROM {table} {where_clause} AND ({key_filter_sql})"
        else:
            sql = f"SELECT * FROM {table} WHERE {key_filter_sql}"
    acc_cursor.execute(sql, query_params if last_updated_col else ())
    columns = [col[0] for col in acc_cursor.description]
    for row in acc_cursor.fetchall():
        yield dict(zip(columns, row))


def upsert_reserve(acc_cursor, pg_conn) -> dict:
    summary = {"table": "Reserve", "fetched": 0, "upserted": 0}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(last_updated), '1900-01-01'::timestamptz) FROM lms_staging_reserve")
        max_lu = cur.fetchone()[0]
    # Access incremental fetch
    acc_cursor.execute("SELECT * FROM Reserve WHERE LastUpdated > ? ORDER BY LastUpdated", (max_lu,))
    cols = [c[0] for c in acc_cursor.description]
    rows = acc_cursor.fetchall()
    summary["fetched"] = len(rows)
    # Deduplicate by Reserve_No, keep last by LastUpdated
    by_key = {}
    for r in rows:
        rec = dict(zip(cols, r))
        reserve_no = (rec.get('Reserve_No') or rec.get('RESERVE_NO') or '').strip()
        if not reserve_no:
            continue
        last_updated = rec.get('LastUpdated')
        lu_iso = dt_to_iso(last_updated)
        raw = json.dumps({k: (dt_to_iso(v) if isinstance(v, datetime) else v) for k, v in rec.items()}, default=str)
        by_key[reserve_no] = (reserve_no, lu_iso, raw)
    payload = list(by_key.values())
    if not payload:
        return summary
    with pg_conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO lms_staging_reserve (reserve_no, last_updated, raw_data, updated_at)
            VALUES %s
            ON CONFLICT (reserve_no) DO UPDATE
              SET last_updated = EXCLUDED.last_updated,
                  raw_data = EXCLUDED.raw_data,
                  updated_at = now()
            """,
            [(rn, lu, Json(json.loads(raw)),) for rn, lu, raw in payload],
            template="(%s,%s,%s, now())",
        )
        summary["upserted"] = cur.rowcount or len(payload)
    pg_conn.commit()
    return summary


def upsert_payment(acc_cursor, pg_conn) -> dict:
    summary = {"table": "Payment", "fetched": 0, "upserted": 0}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(last_updated), '1900-01-01'::timestamptz) FROM lms_staging_payment")
        max_lu = cur.fetchone()[0]
    acc_cursor.execute("SELECT * FROM Payment WHERE LastUpdated > ? ORDER BY LastUpdated", (max_lu,))
    cols = [c[0] for c in acc_cursor.description]
    rows = acc_cursor.fetchall()
    summary["fetched"] = len(rows)
    by_key = {}
    for r in rows:
        rec = dict(zip(cols, r))
        pid = rec.get('PaymentID')
        if pid is None:
            continue
        reserve_no = (rec.get('Reserve_No') or '').strip() if rec.get('Reserve_No') else None
        last_updated = rec.get('LastUpdated')
        lu_iso = dt_to_iso(last_updated)
        raw = json.dumps({k: (dt_to_iso(v) if isinstance(v, datetime) else v) for k, v in rec.items()}, default=str)
        by_key[pid] = (pid, reserve_no, lu_iso, raw)
    payload = list(by_key.values())
    if not payload:
        return summary
    with pg_conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO lms_staging_payment (payment_id, reserve_no, last_updated, raw_data, updated_at)
            VALUES %s
            ON CONFLICT (payment_id) DO UPDATE
              SET reserve_no = EXCLUDED.reserve_no,
                  last_updated = EXCLUDED.last_updated,
                  raw_data = EXCLUDED.raw_data,
                  updated_at = now()
            """,
            [(pid, rn, lu, Json(json.loads(raw)),) for pid, rn, lu, raw in payload],
            template="(%s,%s,%s,%s, now())",
        )
        summary["upserted"] = cur.rowcount or len(payload)
    pg_conn.commit()
    return summary


def upsert_customer(acc_cursor, pg_conn) -> dict:
    summary = {"table": "Customer", "fetched": 0, "upserted": 0}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(last_updated), '1900-01-01'::timestamptz) FROM lms_staging_customer")
        max_lu = cur.fetchone()[0]
    acc_cursor.execute("SELECT * FROM Customer WHERE LastUpdated > ? ORDER BY LastUpdated", (max_lu,))
    cols = [c[0] for c in acc_cursor.description]
    rows = acc_cursor.fetchall()
    summary["fetched"] = len(rows)
    by_key = {}
    for r in rows:
        rec = dict(zip(cols, r))
        cid = rec.get('ID')
        if cid is None:
            continue
        last_updated = rec.get('LastUpdated')
        lu_iso = dt_to_iso(last_updated)
        raw = json.dumps({k: (dt_to_iso(v) if isinstance(v, datetime) else v) for k, v in rec.items()}, default=str)
        by_key[cid] = (cid, lu_iso, raw)
    payload = list(by_key.values())
    if not payload:
        return summary
    with pg_conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO lms_staging_customer (customer_id, last_updated, raw_data, updated_at)
            VALUES %s
            ON CONFLICT (customer_id) DO UPDATE
              SET last_updated = EXCLUDED.last_updated,
                  raw_data = EXCLUDED.raw_data,
                  updated_at = now()
            """,
            [(cid, lu, Json(json.loads(raw)),) for cid, lu, raw in payload],
            template="(%s,%s,%s, now())",
        )
        summary["upserted"] = cur.rowcount or len(payload)
    pg_conn.commit()
    return summary


def upsert_vehicles(acc_cursor, pg_conn) -> dict:
    summary = {"table": "Vehicles", "fetched": 0, "upserted": 0}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(last_updated), '1900-01-01'::timestamptz) FROM lms_staging_vehicles")
        max_lu = cur.fetchone()[0]
    acc_cursor.execute("SELECT * FROM Vehicles WHERE LastUpdated > ? ORDER BY LastUpdated", (max_lu,))
    cols = [c[0] for c in acc_cursor.description]
    rows = acc_cursor.fetchall()
    summary["fetched"] = len(rows)
    by_key = {}
    for r in rows:
        rec = dict(zip(cols, r))
        vehicle_code = (rec.get('Vehicle') or '').strip() if rec.get('Vehicle') else None
        if not vehicle_code:
            continue
        vin = (rec.get('VIN') or '').strip() if rec.get('VIN') else None
        last_updated = rec.get('LastUpdated')
        lu_iso = dt_to_iso(last_updated)
        raw = json.dumps({k: (dt_to_iso(v) if isinstance(v, datetime) else v) for k, v in rec.items()}, default=str)
        by_key[vehicle_code] = (vehicle_code, vin, lu_iso, raw)
    payload = list(by_key.values())
    if not payload:
        return summary
    with pg_conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO lms_staging_vehicles (vehicle_code, vin, last_updated, raw_data, updated_at)
            VALUES %s
            ON CONFLICT (vehicle_code) DO UPDATE
              SET vin = EXCLUDED.vin,
                  last_updated = EXCLUDED.last_updated,
                  raw_data = EXCLUDED.raw_data,
                  updated_at = now()
            """,
            [(vc, vin, lu, Json(json.loads(raw)),) for vc, vin, lu, raw in payload],
            template="(%s,%s,%s,%s, now())",
        )
        summary["upserted"] = cur.rowcount or len(payload)
    pg_conn.commit()
    return summary


def write_summary(summaries):
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    with open(SUMMARY_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['table', 'fetched', 'upserted'])
        w.writeheader()
        for s in summaries:
            w.writerow(s)
    print('Staging sync summary written to', SUMMARY_CSV)


def main():
    # Connect to Access and Postgres
    with pyodbc.connect(ACCESS_CONN_STR, autocommit=True) as acc_conn, \
         psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD) as pg_conn:
        pg_conn.autocommit = True
        ensure_staging(pg_conn)
        acc_cur = acc_conn.cursor()
        summaries = []
        for fn in (upsert_reserve, upsert_payment, upsert_customer, upsert_vehicles):
            try:
                s = fn(acc_cur, pg_conn)
            except Exception as e:
                s = {"table": fn.__name__.replace('upsert_', '').title(), "fetched": 0, "upserted": 0}
                print(f"Error syncing {s['table']}: {e}")
            summaries.append(s)
        write_summary(summaries)


if __name__ == '__main__':
    main()
