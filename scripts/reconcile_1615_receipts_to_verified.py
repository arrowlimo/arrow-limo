import os
import sys
import math
import hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional

import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

BANK_ID = 4
ACCOUNT_NUMBER = '1615'
DATE_START = date(2012, 1, 1)
DATE_END = date(2017, 12, 31)
VERIFIED_TAG = 'CIBC_7461615_2012_2017_VERIFIED.xlsx'


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def calculate_gst_inclusive(gross_amount: float, tax_rate: float = 0.05) -> Tuple[float, float]:
    if gross_amount is None:
        return 0.0, 0.0
    gst = round(gross_amount * tax_rate / (1 + tax_rate), 2)
    net = round(gross_amount - gst, 2)
    return gst, net


def backup(cur) -> Tuple[str, str]:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    receipts_backup = f"receipts_1615_backup_{ts}"
    ledger_backup = f"banking_receipt_matching_ledger_1615_backup_{ts}"

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {receipts_backup} AS
        SELECT r.*
        FROM receipts r
        WHERE EXISTS (
            SELECT 1 FROM banking_transactions bt
            WHERE bt.transaction_id = r.banking_transaction_id
              AND bt.bank_id = %s
              AND bt.account_number IN ('1615','74-61615')
              AND bt.transaction_date BETWEEN %s AND %s
        )
        OR (r.created_from_banking = TRUE AND r.banking_transaction_id IS NULL)
        """,
        (BANK_ID, DATE_START, DATE_END),
    )

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ledger_backup} AS
        SELECT bm.*
        FROM banking_receipt_matching_ledger bm
        WHERE EXISTS (
            SELECT 1 FROM banking_transactions bt
            WHERE bt.transaction_id = bm.banking_transaction_id
              AND bt.bank_id = %s
              AND bt.account_number IN ('1615','74-61615')
              AND bt.transaction_date BETWEEN %s AND %s
        )
        """,
        (BANK_ID, DATE_START, DATE_END),
    )

    return receipts_backup, ledger_backup


def unlink_old_matches(cur) -> Tuple[int, int]:
    # Remove ledger links first
    cur.execute(
        """
        DELETE FROM banking_receipt_matching_ledger bm
        USING banking_transactions bt
        WHERE bm.banking_transaction_id = bt.transaction_id
          AND bt.bank_id = %s
          AND bt.account_number IN ('1615','74-61615')
          AND bt.source_file IS DISTINCT FROM %s
          AND bt.transaction_date BETWEEN %s AND %s
        """,
        (BANK_ID, VERIFIED_TAG, DATE_START, DATE_END),
    )
    deleted_ledger = cur.rowcount

    # Unlink receipts that point to any 1615 tx in range that aren't from the verified import
    cur.execute(
        """
        UPDATE receipts r
        SET banking_transaction_id = NULL
        FROM banking_transactions bt
        WHERE r.banking_transaction_id = bt.transaction_id
          AND bt.bank_id = %s
          AND bt.account_number IN ('1615','74-61615')
          AND bt.source_file IS DISTINCT FROM %s
          AND bt.transaction_date BETWEEN %s AND %s
        """,
        (BANK_ID, VERIFIED_TAG, DATE_START, DATE_END),
    )
    unlinked = cur.rowcount
    return deleted_ledger, unlinked


def fetch_1615_transactions(cur) -> List[Dict]:
    cur.execute(
        """
        SELECT 
            bt.transaction_id, bt.transaction_date, bt.description, 
            bt.debit_amount, bt.credit_amount, bt.balance,
            COALESCE(bt.vendor_extracted, bt.description) AS vendor_hint
        FROM banking_transactions bt
        WHERE bt.bank_id = %s
          AND bt.account_number = %s
          AND bt.source_file = %s
          AND bt.transaction_date BETWEEN %s AND %s
        ORDER BY bt.transaction_date, bt.transaction_id
        """,
        (BANK_ID, ACCOUNT_NUMBER, VERIFIED_TAG, DATE_START, DATE_END),
    )
    rows = [dict(r) for r in cur.fetchall()]
    return rows


def fetch_existing_receipts(cur) -> List[Dict]:
    cur.execute(
        """
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.description,
               r.gross_amount, r.gst_amount, r.net_amount,
               r.banking_transaction_id, r.created_from_banking
        FROM receipts r
        WHERE r.receipt_date BETWEEN %s AND %s
        """,
        (DATE_START, DATE_END),
    )
    return [dict(r) for r in cur.fetchall()]


def amount_of(bt_row: Dict) -> Optional[float]:
    d = bt_row.get('debit_amount')
    c = bt_row.get('credit_amount')
    if d is not None:
        return float(d)
    if c is not None:
        return -float(c)
    return None


def normalize_vendor(text: Optional[str]) -> str:
    if not text:
        return ''
    t = text.strip().lower()
    for token in ["  ", " ltd", ".", ",", " inc", " limited", " corp", " corporation"]:
        t = t.replace(token, ' ')
    return ' '.join(t.split())


def try_match(bt: Dict, candidates: List[Dict]) -> Optional[int]:
    amt = amount_of(bt)
    if amt is None:
        return None

    txd: date = bt['transaction_date']
    vendor_hint = normalize_vendor(bt.get('vendor_hint'))
    is_nsf = 'nsf' in (bt.get('description') or '').lower()
    is_redo = 'redo' in (bt.get('description') or '').lower()

    # Filter by amount and date tolerance +/- 3 days
    possibles = []
    for r in candidates:
        if r['banking_transaction_id'] is not None:
            continue
        if r['gross_amount'] is None:
            continue
        if abs(float(r['gross_amount']) - abs(amt)) > 0.01:
            continue
        if abs((r['receipt_date'] - txd).days) > 3:
            continue
        score = 0
        rv = normalize_vendor(r.get('vendor_name'))
        rd = (r.get('description') or '').lower()
        if vendor_hint and vendor_hint in rv:
            score += 2
        if is_nsf and ('nsf' in rv or 'nsf' in rd):
            score += 2
        if is_redo and ('redo' in rv or 'redo' in rd):
            score += 1
        if str(amt).endswith('.00') and (rd.endswith('1') or rd.endswith('2')):
            score += 1
        # prefer manual receipts over auto-created ones
        if not r.get('created_from_banking'):
            score += 1
        possibles.append((score, r))

    if not possibles:
        return None
    possibles.sort(key=lambda x: (-x[0], x[1]['receipt_date']))
    return possibles[0][1]['receipt_id']


def ensure_ledger_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS banking_receipt_matching_ledger (
            id SERIAL PRIMARY KEY,
            banking_transaction_id BIGINT,
            receipt_id BIGINT,
            match_date DATE,
            match_type TEXT,
            match_status TEXT,
            match_confidence NUMERIC(4,2),
            notes TEXT,
            created_by TEXT
        )
        """
    )


def link(cur, bt_id: int, receipt_id: int, confidence: float, note: str):
    cur.execute(
        """
        UPDATE receipts SET banking_transaction_id = %s WHERE receipt_id = %s
        """,
        (bt_id, receipt_id),
    )
    cur.execute(
        """
        INSERT INTO banking_receipt_matching_ledger (
            banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (bt_id, receipt_id, date.today(), 'auto-1615-verified', 'linked', confidence, note, 'reconcile_1615_receipts_to_verified.py'),
    )


def create_receipt(cur, bt: Dict) -> int:
    amt = amount_of(bt)
    if amt is None or amt <= 0:
        raise ValueError('create_receipt called for non-debit or null amount')
    gst, net = calculate_gst_inclusive(abs(amt))
    vendor = bt.get('vendor_hint') or 'Unknown'
    desc = (bt.get('description') or '') + ' [AUTO from 1615 verified]'

    cur.execute(
        """
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount, gst_amount, net_amount,
            created_from_banking, banking_transaction_id
        ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
        RETURNING receipt_id
        """,
        (bt['transaction_date'], vendor, desc[:500], abs(amt), gst, net, bt['transaction_id']),
    )
    new_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO banking_receipt_matching_ledger (
            banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (bt['transaction_id'], new_id, date.today(), 'auto-1615-verified-create', 'linked', 1.00, 'Auto-created from 1615 verified banking', 'reconcile_1615_receipts_to_verified.py'),
    )
    return new_id


def reconcile(write: bool = True):
    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        ensure_ledger_table(cur)

        # Back up
        rb, lb = backup(cur)
        print(f"Backed up receipts -> {rb}; ledger -> {lb}")

        # Remove old links from non-verified 1615 rows
        deleted_ledger, unlinked = unlink_old_matches(cur)
        print(f"Removed {deleted_ledger} ledger links; unlinked {unlinked} receipts from old 1615 tx")

        # Load data
        bt_rows = fetch_1615_transactions(cur)
        print(f"Loaded {len(bt_rows)} verified 1615 banking transactions")
        receipts = fetch_existing_receipts(cur)
        print(f"Loaded {len(receipts)} candidate receipts (2012–2017)")

        # Build quick index of receipts by id
        r_by_id = {r['receipt_id']: r for r in receipts}

        matched = 0
        created = 0
        skipped_credits = 0
        unmatched = []

        for bt in bt_rows:
            amt = amount_of(bt)
            if amt is None:
                continue
            if amt < 0:
                # credit (deposit) — do not create receipts, just skip
                skipped_credits += 1
                continue

            # Try find a receipt match
            rid = try_match(bt, receipts)
            if rid:
                link(cur, bt['transaction_id'], rid, 1.00, 'Match by amount/date/vendor')
                # Mark this receipt as linked in our local copy to avoid double-link
                for r in receipts:
                    if r['receipt_id'] == rid:
                        r['banking_transaction_id'] = bt['transaction_id']
                        break
                matched += 1
                continue

            # No match: create a receipt
            create_receipt(cur, bt)
            created += 1

        if write:
            conn.commit()
            print(f"Committed: matched={matched}, created={created}, credits_skipped={skipped_credits}")
        else:
            conn.rollback()
            print(f"Dry-run: matched={matched}, created={created}, credits_skipped={skipped_credits}")

        print("Done.")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    write = True
    if '--dry-run' in sys.argv:
        write = False
    reconcile(write)
