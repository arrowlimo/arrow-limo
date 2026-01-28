#!/usr/bin/env python3
"""
Propose 2015 Receipts from Banking (dry-run CSV)
-----------------------------------------------
Builds a candidate list of expense receipts from 2015 banking transactions.
- Prefers debit_amount>0 when available; otherwise falls back to generic amount columns with sign heuristics.
- Excludes transactions already linked to receipts via receipts.bank_id when possible.
- Computes GST as INCLUDED at 5% (AB) by default.
- Writes CSV to exports/receipts/2015_receipt_candidates.csv for human review.

No database writes.
"""
import csv
import pathlib
import sys
from typing import Dict, Any, List, Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import get_db_connection  # type: ignore

EXPORT_DIR = ROOT / 'exports' / 'receipts'
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_PATH = EXPORT_DIR / '2015_receipt_candidates.csv'

CANDIDATE_AMOUNT_COLS = [
    'debit_amount',
    'amount',
    'withdrawal_amount',
    'debit',
]


def get_cols(cur, table: str) -> Dict[str, bool]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,)
    )
    return {r[0].lower(): True for r in cur.fetchall()}


def pick_amount(row: dict, cols_present: Dict[str, bool]) -> float:
    # Prefer explicit debit_amount if positive
    if cols_present.get('debit_amount') and row.get('debit_amount') is not None:
        try:
            val = float(row['debit_amount'] or 0)
            if val > 0:
                return val
        except Exception:
            pass
    # Try generic columns
    for c in CANDIDATE_AMOUNT_COLS:
        if c == 'debit_amount':
            continue
        if cols_present.get(c) and row.get(c) is not None:
            try:
                val = float(row[c] or 0)
                # Heuristic: positive -> cash outflow, negative -> inflow
                if val > 0:
                    return val
            except Exception:
                continue
    return 0.0


def gst_included(amount: float, rate: float = 0.05) -> float:
    return round(amount * rate / (1.0 + rate), 2)


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    bcols = get_cols(cur, 'banking_transactions')
    rcols = get_cols(cur, 'receipts')

    # Column names
    date_col = 'transaction_date' if bcols.get('transaction_date') else 'date' if bcols.get('date') else None
    desc_col = 'description' if bcols.get('description') else None
    vendor_col = 'vendor_name' if bcols.get('vendor_name') else None
    id_col = 'transaction_id' if bcols.get('transaction_id') else 'id' if bcols.get('id') else None

    if not date_col or not id_col:
        print('[FAIL] Required columns missing in banking_transactions')
        return

    # Build set of already-linked banking IDs from receipts.bank_id if present
    linked_ids: set = set()
    if rcols.get('bank_id'):
        cur.execute("SELECT DISTINCT bank_id FROM receipts WHERE bank_id IS NOT NULL")
        linked_ids = {r[0] for r in cur.fetchall()}

    # Fetch 2015 rows with basic columns and potential amount columns
    select_cols = [id_col, date_col]
    for c in ['debit_amount', 'amount', 'withdrawal_amount', 'debit']:
        if bcols.get(c):
            select_cols.append(c)
    if desc_col:
        select_cols.append(desc_col)
    if vendor_col:
        select_cols.append(vendor_col)

    sql = f"SELECT {', '.join(select_cols)} FROM banking_transactions WHERE {date_col} >= DATE '2015-01-01' AND {date_col} < DATE '2016-01-01' ORDER BY {date_col}, {id_col}"
    cur.execute(sql)

    rows = []
    colnames = [d[0].lower() for d in cur.description]
    for rec in cur.fetchall():
        rows.append({colnames[i]: rec[i] for i in range(len(colnames))})

    candidates: List[dict] = []
    for r in rows:
        bid = r[id_col]
        if bid in linked_ids:
            continue
        amt = pick_amount(r, bcols)
        if amt <= 0:
            continue
        date_val = r[date_col]
        desc = (r.get(desc_col) if desc_col else '') or ''
        vendor = (r.get(vendor_col) if vendor_col else '') or ''

        gst = gst_included(amt, 0.05)
        net = round(amt - gst, 2)

        candidates.append({
            'receipt_date': date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val),
            'vendor_name': vendor if vendor else desc[:60],
            'gross_amount': f"{amt:.2f}",
            'gst_amount': f"{gst:.2f}",
            'net_amount': f"{net:.2f}",
            'description': desc,
            'category': '',
            'employee_id': '',
            'vehicle_id': '',
            'banking_transaction_id': bid,
            'source': 'banking'
        })

    # Write CSV
    headers = ['receipt_date','vendor_name','gross_amount','gst_amount','net_amount','description','category','employee_id','vehicle_id','banking_transaction_id','source']
    with EXPORT_PATH.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for c in candidates:
            w.writerow(c)

    print('=== Proposed 2015 Receipt Candidates ===')
    print(f"Candidates written: {len(candidates)}")
    print(f"File: {EXPORT_PATH}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
