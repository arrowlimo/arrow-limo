import os
import sys
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple, Optional

import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

SCOTIA_BANK_ID = 2
SCOTIA_ACCOUNT = "903990106011"
DATE_START = date(2012, 1, 1)
DATE_END = date(2019, 12, 31)  # Scotia goes to 2019


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
    receipts_backup = f"receipts_scotia_backup_{ts}"
    ledger_backup = f"banking_receipt_matching_ledger_scotia_backup_{ts}"

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {receipts_backup} AS
        SELECT r.*
        FROM receipts r
        WHERE EXISTS (
            SELECT 1 FROM banking_transactions bt
            WHERE bt.transaction_id = r.banking_transaction_id
              AND bt.bank_id = %s
              AND bt.account_number = %s
        )
        OR r.mapped_bank_account_id = %s
        """,
        (SCOTIA_BANK_ID, SCOTIA_ACCOUNT, SCOTIA_BANK_ID),
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
              AND bt.account_number = %s
        )
        """,
        (SCOTIA_BANK_ID, SCOTIA_ACCOUNT),
    )

    return receipts_backup, ledger_backup


def unlink_old_matches(cur) -> Tuple[int, int]:
    # Remove old ledger links
    cur.execute(
        """
        DELETE FROM banking_receipt_matching_ledger bm
        USING banking_transactions bt
        WHERE bm.banking_transaction_id = bt.transaction_id
          AND bt.bank_id = %s
          AND bt.account_number = %s
          AND bt.is_transfer IS DISTINCT FROM TRUE
        """,
        (SCOTIA_BANK_ID, SCOTIA_ACCOUNT),
    )
    deleted_ledger = cur.rowcount

    # Unlink receipts
    cur.execute(
        """
        UPDATE receipts r
        SET banking_transaction_id = NULL
        FROM banking_transactions bt
        WHERE r.banking_transaction_id = bt.transaction_id
          AND bt.bank_id = %s
          AND bt.account_number = %s
          AND bt.is_transfer IS DISTINCT FROM TRUE
        """,
        (SCOTIA_BANK_ID, SCOTIA_ACCOUNT),
    )
    unlinked = cur.rowcount
    return deleted_ledger, unlinked


def fetch_scotia_transactions(cur) -> List[Dict]:
    cur.execute(
        """
        SELECT 
            bt.transaction_id, bt.transaction_date, bt.description, 
            bt.debit_amount, bt.credit_amount, bt.balance,
            bt.is_transfer,
            COALESCE(bt.vendor_extracted, bt.description) AS vendor_hint
        FROM banking_transactions bt
        WHERE bt.bank_id = %s
          AND bt.account_number = %s
          AND bt.transaction_date BETWEEN %s AND %s
        ORDER BY bt.transaction_date, bt.transaction_id
        """,
        (SCOTIA_BANK_ID, SCOTIA_ACCOUNT, DATE_START, DATE_END),
    )
    rows = [dict(r) for r in cur.fetchall()]
    return rows


def fetch_existing_receipts(cur) -> List[Dict]:
    cur.execute(
        """
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.description,
               r.gross_amount, r.gst_amount, r.net_amount,
               r.banking_transaction_id, r.created_from_banking, r.is_transfer
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
        UPDATE receipts SET banking_transaction_id = %s, mapped_bank_account_id = %s 
        WHERE receipt_id = %s
        """,
        (bt_id, SCOTIA_BANK_ID, receipt_id),
    )
    cur.execute(
        """
        INSERT INTO banking_receipt_matching_ledger (
            banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (bt_id, receipt_id, date.today(), 'auto-scotia-verified', 'linked', confidence, note, 'reconcile_scotia_receipts.py'),
    )


def create_receipt(cur, bt: Dict) -> int:
    amt = amount_of(bt)
    if amt is None or amt <= 0:
        raise ValueError('create_receipt called for non-debit or null amount')
    gst, net = calculate_gst_inclusive(abs(amt))
    vendor = bt.get('vendor_hint') or 'Unknown'
    desc = (bt.get('description') or '') + ' [AUTO from Scotia verified]'

    cur.execute(
        """
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount, gst_amount, net_amount,
            created_from_banking, banking_transaction_id, mapped_bank_account_id
        ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
        RETURNING receipt_id
        """,
        (bt['transaction_date'], vendor, desc[:500], abs(amt), gst, net, bt['transaction_id'], SCOTIA_BANK_ID),
    )
    new_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO banking_receipt_matching_ledger (
            banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (bt['transaction_id'], new_id, date.today(), 'auto-scotia-verified-create', 'linked', 1.00, 'Auto-created from Scotia verified banking', 'reconcile_scotia_receipts.py'),
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

        # Remove old links (except transfers)
        deleted_ledger, unlinked = unlink_old_matches(cur)
        print(f"Removed {deleted_ledger} ledger links; unlinked {unlinked} receipts from Scotia tx")

        # Load data
        bt_rows = fetch_scotia_transactions(cur)
        print(f"Loaded {len(bt_rows)} Scotia banking transactions")
        
        # Filter out transfers
        non_transfer_bt = [r for r in bt_rows if not r.get('is_transfer')]
        print(f"  {len(non_transfer_bt)} non-transfer transactions to reconcile")
        
        receipts = fetch_existing_receipts(cur)
        # Filter out transfer receipts
        non_transfer_receipts = [r for r in receipts if not r.get('is_transfer')]
        print(f"Loaded {len(non_transfer_receipts)} candidate receipts (excluding transfers)")

        matched = 0
        created = 0
        skipped_credits = 0
        skipped_transfers = len(bt_rows) - len(non_transfer_bt)

        for bt in non_transfer_bt:
            amt = amount_of(bt)
            if amt is None:
                continue
            if amt < 0:
                skipped_credits += 1
                continue
            if amt <= 0:
                # Edge case: zero or negative treated as credit
                skipped_credits += 1
                continue

            # Try find a receipt match
            rid = try_match(bt, non_transfer_receipts)
            if rid:
                link(cur, bt['transaction_id'], rid, 1.00, 'Match by amount/date/vendor')
                for r in non_transfer_receipts:
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
            print(f"✅ Committed: matched={matched}, created={created}, credits_skipped={skipped_credits}, transfers_skipped={skipped_transfers}")
        else:
            conn.rollback()
            print(f"Dry-run: matched={matched}, created={created}, credits_skipped={skipped_credits}, transfers_skipped={skipped_transfers}")

        print("Done.")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    write = '--write' not in sys.argv or '--write' in sys.argv
    reconcile(write)
