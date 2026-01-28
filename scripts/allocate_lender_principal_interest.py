#!/usr/bin/env python3
"""
Allocate principal/interest/fees for matched lender→banking rows.

Inputs:
- reports/lender_bt_matches.csv (from reconcile_lender_to_banking_transactions.py)
- lender_statement_transactions (for descriptions that hint interest/fees)

Behavior:
- Creates table vehicle_loan_reconciliation_allocations if not exists:
    (id, lender_id, bank_txn_id, bank_txn_id_2, lender_date, bank_date,
     lender_amount, bank_net, principal_amount, interest_amount, fee_amount,
     notes, created_at)
- Heuristic allocation:
  • If lender description contains 'Interest' or 'INT', classify as interest;
    otherwise principal. NSF-like -> fee.
  • For two-bank-row matches, use combined net for total; allocate per lender row equally unless 'Interest' present.
- Writes allocations idempotently (unique on lender_id), and exports a summary CSV.
"""

import csv
import os
from typing import Dict, Any

import psycopg2

DB = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432,
}

MATCHES_CSV = os.path.join('reports', 'lender_bt_matches.csv')
OUT_SUMMARY = os.path.join('reports', 'vehicle_loan_allocation_summary.csv')


def ensure_table(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle_loan_reconciliation_allocations (
            id SERIAL PRIMARY KEY,
            lender_id INTEGER UNIQUE NOT NULL,
            bank_txn_id INTEGER,
            bank_txn_id_2 INTEGER,
            lender_date DATE,
            bank_date DATE,
            lender_amount NUMERIC(14,2),
            bank_net NUMERIC(14,2),
            principal_amount NUMERIC(14,2),
            interest_amount NUMERIC(14,2),
            fee_amount NUMERIC(14,2),
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    conn.commit()


def classify(desc: str) -> str:
    d = (desc or '').upper()
    if 'NSF' in d or 'RETURN' in d:
        return 'fee'
    if 'INT' in d or 'INTEREST' in d:
        return 'interest'
    return 'principal'


def parse_bank_txn_id(value: str):
    if value and '|' in value:
        a, b = value.split('|', 1)
        try:
            return int(a), int(b)
        except Exception:
            return None, None
    try:
        return int(value), None
    except Exception:
        return None, None


def main():
    if not os.path.exists(MATCHES_CSV):
        print(f"Missing {MATCHES_CSV}; run reconcile script first.")
        return

    # Read matches
    rows = []
    with open(MATCHES_CSV, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        rows = list(r)

    conn = psycopg2.connect(**DB)
    ensure_table(conn)
    cur = conn.cursor()

    inserted = 0
    for m in rows:
        lender_id = int(m['lender_id'])
        bank_txn_id, bank_txn_id_2 = parse_bank_txn_id(m.get('bank_txn_id'))
        lender_amount = float(m.get('lender_amount') or 0)
        bank_net = float(m.get('bank_net') or 0)
        lender_desc = m.get('lender_desc') or ''
        kind = classify(lender_desc)

        principal = interest = fee = 0.0
        if kind == 'interest':
            interest = abs(lender_amount)
        elif kind == 'fee':
            fee = abs(lender_amount)
        else:
            principal = abs(lender_amount)

        notes = f"auto-classify={kind}; bank_txn_id_2 included" if bank_txn_id_2 else f"auto-classify={kind}"

        # Idempotent upsert by lender_id
        cur.execute(
            "SELECT 1 FROM vehicle_loan_reconciliation_allocations WHERE lender_id=%s",
            (lender_id,)
        )
        exists = cur.fetchone() is not None
        if exists:
            cur.execute(
                """
                UPDATE vehicle_loan_reconciliation_allocations
                   SET bank_txn_id=%s,
                       bank_txn_id_2=%s,
                       lender_date=%s,
                       bank_date=%s,
                       lender_amount=%s,
                       bank_net=%s,
                       principal_amount=%s,
                       interest_amount=%s,
                       fee_amount=%s,
                       notes=%s
                 WHERE lender_id=%s
                """,
                (
                    bank_txn_id, bank_txn_id_2,
                    m.get('lender_date'), m.get('bank_date'),
                    lender_amount, bank_net,
                    principal, interest, fee,
                    notes,
                    lender_id,
                )
            )
        else:
            cur.execute(
                """
                INSERT INTO vehicle_loan_reconciliation_allocations(
                    lender_id, bank_txn_id, bank_txn_id_2, lender_date, bank_date,
                    lender_amount, bank_net, principal_amount, interest_amount, fee_amount, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    lender_id, bank_txn_id, bank_txn_id_2, m.get('lender_date'), m.get('bank_date'),
                    lender_amount, bank_net, principal, interest, fee, notes
                )
            )
        inserted += 1

    conn.commit()
    print(f"Allocations written: {inserted}")

    # Export a quick summary by kind
    cur.execute(
        """
        SELECT 
          COUNT(*) AS rows,
          COALESCE(SUM(principal_amount),0) AS principal,
          COALESCE(SUM(interest_amount),0) AS interest,
          COALESCE(SUM(fee_amount),0) AS fees
        FROM vehicle_loan_reconciliation_allocations
        """
    )
    summary = cur.fetchone()
    with open(OUT_SUMMARY, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['rows','principal','interest','fees'])
        w.writerow([summary[0], f"{summary[1]:.2f}", f"{summary[2]:.2f}", f"{summary[3]:.2f}"])
    print(f"Wrote {OUT_SUMMARY}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
