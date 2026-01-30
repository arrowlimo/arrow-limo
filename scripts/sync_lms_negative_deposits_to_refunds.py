#!/usr/bin/env python3
"""
Sync all negative LMS Deposit entries to charter_refunds.
- For each negative deposit, find reserve_number via LMS Payment.[Key]
- Determine if a matching refund exists in charter_refunds by (amount, date±30d)
- Classify: linked (has reserve), unlinked (no reserve), missing (no row)
- Dry-run prints planned INSERTs/UPDATEs; --write applies changes

Safety:
- Uses positive amount for charter_refunds.amount (refund amounts stored as positive)
- Adds description marker: "from LMS Deposit {Number} Key {Key}" for audit
- No deletions. Only inserts or updates reserve_number/charter_id on existing rows

Usage:
  python -X utf8 scripts/sync_lms_negative_deposits_to_refunds.py          # dry-run
  python -X utf8 scripts/sync_lms_negative_deposits_to_refunds.py --write  # apply
"""
import argparse
import os
from dataclasses import dataclass
from typing import Optional, List, Tuple
import psycopg2
import pyodbc

@dataclass
class LMSDeposit:
    number: Optional[str]
    date: str
    key: Optional[str]
    total: float
    dep_type: Optional[str]
    transact: Optional[str]

@dataclass
class RefundRow:
    id: int
    refund_date: str
    amount: float
    reserve_number: Optional[str]
    charter_id: Optional[int]
    description: Optional[str]


def get_pg():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        database=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REDACTED***')
    )

def get_lms():
    LMS_PATH = r'L:\\oldlms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)


def fetch_negative_deposits(lms) -> List[LMSDeposit]:
    cur = lms.cursor()
    cur.execute("""
        SELECT [Number], [Date], [Key], [Total], [Type], [Transact]
        FROM Deposit
        WHERE [Total] < 0
        ORDER BY [Date]
    """)
    rows = []
    for row in cur.fetchall():
        num, date, key, total, dep_type, trans = row
        rows.append(LMSDeposit(
            number=str(num) if num is not None else None,
            date=str(date),
            key=str(key) if key is not None else None,
            total=abs(float(total)) if total is not None else 0.0,
            dep_type=str(dep_type) if dep_type is not None else None,
            transact=str(trans) if trans is not None else None,
        ))
    cur.close()
    return rows


def find_reserve_via_payment(lms, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    cur = lms.cursor()
    try:
        cur.execute("""
            SELECT TOP 1 Reserve_No
            FROM Payment
            WHERE [Key] = ?
        """, (key,))
        r = cur.fetchone()
        return str(r[0]).zfill(6) if r and r[0] else None
    finally:
        cur.close()


def find_charter_by_reserve(pg, reserve: str) -> Optional[int]:
    cur = pg.cursor()
    try:
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
        r = cur.fetchone()
        return int(r[0]) if r else None
    finally:
        cur.close()


def find_existing_refunds(pg, amount: float, date_str: str) -> List[RefundRow]:
    """Find all existing refund rows near the date with the same amount."""
    cur = pg.cursor()
    try:
        cur.execute(
            """
            SELECT id, refund_date::text, amount, reserve_number, charter_id, description
            FROM charter_refunds
            WHERE ABS(amount - %s) < 0.01
              AND ABS(EXTRACT(EPOCH FROM (refund_date::timestamp - %s::timestamp))) < 30*86400
            ORDER BY ABS(EXTRACT(EPOCH FROM (refund_date::timestamp - %s::timestamp)))
            LIMIT 25
            """,
            (amount, date_str, date_str)
        )
        rows = [RefundRow(*r) for r in cur.fetchall()]
        return rows
    finally:
        cur.close()


def insert_refund(pg, date_str: str, amount: float, reserve: Optional[str], charter_id: Optional[int], desc: str, write: bool) -> Optional[int]:
    cur = pg.cursor()
    try:
        if write:
            cur.execute(
                """
                INSERT INTO charter_refunds (refund_date, amount, reserve_number, charter_id, description, source_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (date_str, amount, reserve, charter_id, desc, 'LMS Deposit sync')
            )
            new_id = cur.fetchone()[0]
            pg.commit()
            return new_id
        else:
            print(f"DRY-RUN: Would INSERT refund date={date_str} amount={amount:.2f} reserve={reserve} charter_id={charter_id} desc={desc}")
            return None
    finally:
        cur.close()


def update_link(pg, refund_id: int, reserve: Optional[str], charter_id: Optional[int], write: bool):
    cur = pg.cursor()
    try:
        if write:
            cur.execute(
                "UPDATE charter_refunds SET reserve_number=%s, charter_id=%s WHERE id=%s",
                (reserve, charter_id, refund_id)
            )
            pg.commit()
        else:
            print(f"DRY-RUN: Would UPDATE refund id={refund_id} set reserve={reserve} charter_id={charter_id}")
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes')
    args = ap.parse_args()

    pg = get_pg()
    lms = get_lms()

    deposits = fetch_negative_deposits(lms)
    print(f"Loaded {len(deposits)} negative LMS deposits")

    stats = {'linked':0,'unlinked':0,'missing':0,'updated':0,'inserted':0,'skipped':0}

    for d in deposits:
        reserve = find_reserve_via_payment(lms, d.key)
        charter_id = find_charter_by_reserve(pg, reserve) if reserve else None
        desc = f"from LMS Deposit {d.number or ''} Key {d.key or ''} Type {d.dep_type or ''} Transact {d.transact or ''}".strip()

        existing_rows = find_existing_refunds(pg, d.total, d.date)
        if existing_rows:
            # Safe mode: only fill NULL fields; never override an existing reserve/charter
            for existing in existing_rows:
                existing_has_both = (existing.reserve_number is not None) and (existing.charter_id is not None)
                if existing.reserve_number is None or existing.charter_id is None:
                    # Compute values to apply (only for the NULLs)
                    new_reserve = existing.reserve_number or reserve
                    new_charter = existing.charter_id or charter_id

                    # If we still don't have something to fill, skip
                    if (existing.reserve_number is None and new_reserve is None) or \
                       (existing.charter_id is None and new_charter is None):
                        stats['skipped'] += 1
                        continue

                    # Apply update to fill the missing links
                    if existing.reserve_number is None or existing.charter_id is None:
                        update_link(pg, existing.id, new_reserve, new_charter, args.write)
                        stats['updated'] += 1

                    # Count state after update intention
                    if new_reserve is None or new_charter is None:
                        stats['unlinked'] += 1
                    else:
                        stats['linked'] += 1
                else:
                    # Already fully linked; do not normalize/override
                    stats['linked'] += 1
        else:
            stats['missing'] += 1
            insert_refund(pg, d.date, d.total, reserve, charter_id, desc, args.write)
            stats['inserted'] += 1

    print("\nSUMMARY:")
    print(f"  Linked already: {stats['linked']}")
    print(f"  Unlinked fixed: {stats['updated']}")
    print(f"  Missing added: {stats['inserted']}")
    print(f"  Skipped (no safe update possible): {stats['skipped']}")

    pg.close(); lms.close()

if __name__ == '__main__':
    main()
