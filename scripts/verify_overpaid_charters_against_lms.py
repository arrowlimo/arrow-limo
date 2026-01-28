#!/usr/bin/env python3
"""Verify overpaid PostgreSQL charters against LMS Access database source.

For each charter where paid_amount > total_amount_due (overpay), fetch LMS Reserve row and
compare authoritative fields:
  Reserve_No, Rate, Deposit, Balance, Est_Charge (if exists)

Derived LMS totals:
  lms_est_charge: Est_Charge column if present else (Deposit + Balance) if both non-null else Rate
  lms_total_paid: Deposit (LMS concept of total payments received at snapshot time)
  lms_outstanding: Balance

Comparisons & Flags:
  TOTAL_DUE_MISMATCH: abs(pg_total_due - lms_est_charge) > 1.00
  PAID_DEPOSIT_MISMATCH: abs(pg_paid_amount - lms_total_paid) > 1.00
  OVERPAY_RELATIVE_TO_LMS: pg_paid_amount > lms_est_charge * 1.10
  LMS_SHOWS_BALANCE_POSITIVE: lms_outstanding > 0 while PG charter overpaid
  LMS_CHARGES_MISSING: pg_total_due = 0 but lms_est_charge > 0

Outputs CSV: l:/limo/reports/overpaid_charters_lms_verification.csv
No writes to either database.

Safe querying strategy: attempt Est_Charge column; if not found handle gracefully.
"""

import os
import sys
import glob
import csv
import psycopg2
import pyodbc
from argparse import ArgumentParser
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DEFAULT_LMS_PATH = os.getenv("LMS_MDB_PATH", r"L:\limo\lms.mdb")
LMS_PATH = DEFAULT_LMS_PATH
CSV_PATH = "l:/limo/reports/overpaid_charters_lms_verification.csv"

TOTAL_DUE_THRESHOLD = 1.00
PAID_THRESHOLD = 1.00
OVERPAY_LMS_RATIO = 1.10


def pg_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def discover_lms_path(explicit_path=None):
    # Priority: explicit CLI path > existing env path > discovered backups
    if explicit_path:
        if os.path.exists(explicit_path):
            return explicit_path
        raise FileNotFoundError(f"Explicit LMS path not found: {explicit_path}")
    if os.path.exists(DEFAULT_LMS_PATH):
        return DEFAULT_LMS_PATH
    # Search common backup directories
    candidates = []
    for pattern in [r"L:\limo\**\lms.mdb", r"L:\limo\**\*.mdb"]:
        for p in glob.glob(pattern, recursive=True):
            name = os.path.basename(p).lower()
            if name == 'lms.mdb':
                candidates.append(p)
    # Prefer path containing 'backups' if primary missing
    if candidates:
        # Sort by whether contains backups then shortest path
        candidates.sort(key=lambda x: ("backups" not in x.lower(), len(x)))
        return candidates[0]
    raise FileNotFoundError("Could not locate lms.mdb via discovery patterns.")


def lms_conn(explicit_path=None):
    path = discover_lms_path(explicit_path)
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};"
    return pyodbc.connect(conn_str), path


def fetch_overpaid_postgres(cur):
    cur.execute(
        """
        SELECT reserve_number, charter_id, client_id, total_amount_due, paid_amount, balance, cancelled
        FROM charters
        WHERE reserve_number IS NOT NULL AND paid_amount > total_amount_due
        ORDER BY (paid_amount - total_amount_due) DESC
        """
    )
    return cur.fetchall()


def fetch_lms_row(cur_lms, reserve_number):
    # Try Est_Charge; Access uses # for dates; we only need numeric fields here
    # Some databases may name it Est_Charge or EstCharge; attempt both.
    for est_col in ["Est_Charge", "EstCharge", "EstChargeTotal"]:
        try:
            cur_lms.execute(
                f"SELECT Reserve_No, Rate, Deposit, Balance, {est_col} FROM Reserve WHERE Reserve_No = ?",
                (reserve_number,)
            )
            row = cur_lms.fetchone()
            if row:
                return {
                    'reserve_number': row[0],
                    'rate': row[1],
                    'deposit': row[2],
                    'balance': row[3],
                    'est_charge': row[4],
                    'est_column_used': est_col,
                }
        except pyodbc.Error:
            continue
    # Fallback without Est_Charge
    try:
        cur_lms.execute(
            "SELECT Reserve_No, Rate, Deposit, Balance FROM Reserve WHERE Reserve_No = ?",
            (reserve_number,)
        )
        row = cur_lms.fetchone()
        if row:
            return {
                'reserve_number': row[0],
                'rate': row[1],
                'deposit': row[2],
                'balance': row[3],
                'est_charge': None,
                'est_column_used': None,
            }
    except pyodbc.Error:
        pass
    return None


def compute_lms_est_charge(lms):
    if not lms:
        return None
    if lms['est_charge'] is not None and lms['est_charge'] not in (0, ''):
        return float(lms['est_charge'])
    dep = float(lms['deposit']) if lms['deposit'] not in (None, '') else 0.0
    bal = float(lms['balance']) if lms['balance'] not in (None, '') else 0.0
    if dep or bal:
        return dep + bal
    rate = float(lms['rate']) if lms['rate'] not in (None, '') else 0.0
    return rate if rate else None


def analyze(explicit_lms_path=None):
    pg = pg_conn()
    cur_pg = pg.cursor()
    overpaid_rows = fetch_overpaid_postgres(cur_pg)
    lms, used_path = lms_conn(explicit_lms_path)
    cur_lms = lms.cursor()

    results = []
    for reserve_number, charter_id, client_id, pg_due, pg_paid, pg_balance, cancelled in overpaid_rows:
        lms_row = fetch_lms_row(cur_lms, reserve_number)
        if not lms_row:
            results.append({
                'reserve_number': reserve_number,
                'charter_id': charter_id,
                'pg_due': float(pg_due or 0),
                'pg_paid': float(pg_paid or 0),
                'pg_balance': float(pg_balance or 0),
                'lms_est_charge': None,
                'lms_deposit': None,
                'lms_balance': None,
                'flags': ['MISSING_IN_LMS'],
                'cancelled': bool(cancelled),
                'est_column_used': None,
            })
            continue
        lms_est = compute_lms_est_charge(lms_row)
        lms_deposit = float(lms_row['deposit']) if lms_row['deposit'] not in (None, '') else 0.0
        lms_balance = float(lms_row['balance']) if lms_row['balance'] not in (None, '') else 0.0

        flags = []
        if lms_est is not None:
            if abs(float(pg_due or 0) - lms_est) > TOTAL_DUE_THRESHOLD:
                flags.append('TOTAL_DUE_MISMATCH')
        else:
            flags.append('NO_LMS_EST_CHARGE')

        if abs(float(pg_paid or 0) - lms_deposit) > PAID_THRESHOLD:
            flags.append('PAID_DEPOSIT_MISMATCH')

        if lms_est is not None and float(pg_paid or 0) > lms_est * OVERPAY_LMS_RATIO:
            flags.append('OVERPAY_RELATIVE_TO_LMS')

        if lms_balance > 0 and float(pg_paid or 0) > float(pg_due or 0):
            flags.append('LMS_SHOWS_BALANCE_POSITIVE')

        if float(pg_due or 0) == 0 and (lms_est and lms_est > 0):
            flags.append('LMS_CHARGES_MISSING')

        results.append({
            'reserve_number': reserve_number,
            'charter_id': charter_id,
            'pg_due': float(pg_due or 0),
            'pg_paid': float(pg_paid or 0),
            'pg_balance': float(pg_balance or 0),
            'lms_est_charge': lms_est,
            'lms_deposit': lms_deposit,
            'lms_balance': lms_balance,
            'flags': flags,
            'cancelled': bool(cancelled),
            'est_column_used': lms_row['est_column_used'],
        })

    cur_pg.close(); pg.close(); cur_lms.close(); lms.close()
    return results, used_path


def export_csv(results):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'reserve_number','charter_id','cancelled','pg_total_due','pg_paid_amount','pg_balance',
            'lms_est_charge','lms_deposit','lms_balance','est_column_used','flags'
        ])
        for r in results:
            w.writerow([
                r['reserve_number'], r['charter_id'], r['cancelled'], f"{r['pg_due']:.2f}", f"{r['pg_paid']:.2f}", f"{r['pg_balance']:.2f}",
                f"{r['lms_est_charge']:.2f}" if r['lms_est_charge'] is not None else '', f"{r['lms_deposit']:.2f}", f"{r['lms_balance']:.2f}",
                r['est_column_used'] or '', ';'.join(r['flags'])
            ])
    return CSV_PATH


def summarize(results):
    total = len(results)
    missing_lms = sum(1 for r in results if 'MISSING_IN_LMS' in r['flags'])
    total_due_mismatch = sum(1 for r in results if 'TOTAL_DUE_MISMATCH' in r['flags'])
    paid_deposit_mismatch = sum(1 for r in results if 'PAID_DEPOSIT_MISMATCH' in r['flags'])
    overpay_relative = sum(1 for r in results if 'OVERPAY_RELATIVE_TO_LMS' in r['flags'])
    lms_balance_positive = sum(1 for r in results if 'LMS_SHOWS_BALANCE_POSITIVE' in r['flags'])
    charges_missing = sum(1 for r in results if 'LMS_CHARGES_MISSING' in r['flags'])
    print("=== LMS Verification Summary ===")
    print(f"Overpaid charters analyzed: {total}")
    print(f"Missing in LMS: {missing_lms}")
    print(f"TOTAL_DUE_MISMATCH: {total_due_mismatch}")
    print(f"PAID_DEPOSIT_MISMATCH: {paid_deposit_mismatch}")
    print(f"OVERPAY_RELATIVE_TO_LMS: {overpay_relative}")
    print(f"LMS_SHOWS_BALANCE_POSITIVE: {lms_balance_positive}")
    print(f"LMS_CHARGES_MISSING (PG due 0): {charges_missing}")
    print("Sample anomalies (first 10):")
    anomaly_order = sorted(results, key=lambda r: (-len(r['flags']), r['reserve_number']))
    for r in anomaly_order[:10]:
        print(f" reserve={r['reserve_number']} pg_due={r['pg_due']:.2f} pg_paid={r['pg_paid']:.2f} lms_est={r['lms_est_charge'] if r['lms_est_charge'] is not None else 'NA'} lms_dep={r['lms_deposit']:.2f} flags={','.join(r['flags'])}")


def build_arg_parser():
    p = ArgumentParser(description="Verify overpaid charters against LMS Access DB")
    p.add_argument("--lms-path", dest="lms_path", help="Explicit path to lms.mdb")
    return p


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        results, used_path = analyze(args.lms_path)
        summarize(results)
        path = export_csv(results)
        print(f"CSV written: {path}")
        print(f"LMS source used: {used_path}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}. Provide --lms-path or set LMS_MDB_PATH.")
        exit(2)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(2)


if __name__ == '__main__':
    main()
