"""
Verify specific LMS refunds in the Deposit table and cross-check they exist in PostgreSQL charter_refunds.
Input list (from user): deposit numbers/dates/keys/amounts for 2023-2025, plus a separate 2016 $91.88 Square refund.
"""

import pyodbc
import psycopg2
from datetime import datetime, timedelta

LMS_PATH = r'L:\oldlms.mdb'
LMS_CONN_STR = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

PG_CONN_KW = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# Records to verify (deposit_number, date, key_text, total)
TARGETS = [
    ("0020670", "2023-12-07", "Refund", -231.00),
    ("0020858", "2024-02-12", "", -31.50),
    ("0021292", "2024-07-17", "Remb Cab Fare/meal", -200.00),
    ("0021302", "2024-07-22", "", -720.00),
    ("0021305", "2024-07-22", "07/22/24", -239.85),
    ("0022254", "2025-06-20", "Credit", 100.00),
    ("0022319", "2025-07-15", "Wanted Tip Back Paid", -173.25),
    ("0022341", "2025-07-21", "", -150.93),
    ("0022368", "2025-07-28", "", 400.00),
]

# Also verify a 2016 $91.88 Square-related refund (email evidence)
ALSO_CHECK_AMOUNT_2016 = 91.88
ALSO_CHECK_DATE_2016 = datetime(2016, 7, 6)


def fetch_lms_deposits():
    conn = pyodbc.connect(LMS_CONN_STR)
    cur = conn.cursor()

    # Some Access installs name the table Deposit; bracket reserved words
    cols = "[Number], [Date], [Key], [Total], [Transact], [Type]"
    # LastUpdated/LastUpdatedBy may not exist on Deposit in some dbs; try/except
    try:
        cur.execute(f"SELECT TOP 1 [LastUpdated], [LastUpdatedBy] FROM [Deposit]")
        has_last = True
    except Exception:
        has_last = False

    select_cols = cols + (", [LastUpdated], [LastUpdatedBy]" if has_last else "")

    # Build IN clause
    numbers = ",".join([f"'{n}'" for n, *_ in TARGETS])
    query = f"SELECT {select_cols} FROM [Deposit] WHERE [Number] IN ({numbers}) ORDER BY [Date]"

    rows = []
    try:
        cur.execute(query)
        for r in cur.fetchall():
            rows.append(tuple(r))
    except Exception as e:
        print("Error querying Deposit:", e)

    conn.close()
    return has_last, rows


def check_pg_charter_refunds():
    conn = psycopg2.connect(**PG_CONN_KW)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, refund_date, amount, reserve_number, charter_id, description, source_file
        FROM charter_refunds
        ORDER BY refund_date DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def near(d1, d2, days=14):
    """Compare date/datetime tolerance in days handling mixed types."""
    if not d1 or not d2:
        return False
    # Normalize to date objects
    if isinstance(d1, datetime):
        d1 = d1.date()
    if isinstance(d2, datetime):
        d2 = d2.date()
    try:
        return abs((d1 - d2).days) <= days
    except Exception:
        return False


if __name__ == "__main__":
    print("Verifying specific LMS refunds in Deposit table and cross-checking in PostgreSQL...\n")

    has_last, lms_rows = fetch_lms_deposits()
    print(f"LMS Deposit rows fetched: {len(lms_rows)} (LastUpdated cols: {'present' if has_last else 'absent'})")

    # Map by number for quick access
    lms_by_number = {}
    for r in lms_rows:
        # Unpack flexible
        if has_last:
            number, date, key, total, transact, typ, lastupdated, lastby = r
        else:
            number, date, key, total, transact, typ = r
            lastupdated = None
            lastby = None
        lms_by_number[str(number).zfill(7)] = {
            'date': date,
            'key': key,
            'total': float(total) if total is not None else None,
            'transact': transact,
            'type': typ,
            'lastupdated': lastupdated,
            'lastupdatedby': lastby,
        }

    # Report on each target
    missing = []
    print("\nLMS Deposit verification:")
    for dep_no, dep_date, dep_key, dep_total in TARGETS:
        rec = lms_by_number.get(dep_no)
        if not rec:
            print(f"  ✗ NOT FOUND in Deposit: {dep_no} {dep_date} {dep_key} {dep_total}")
            missing.append(dep_no)
            continue
        ok_total = (rec['total'] is not None) and abs(rec['total'] - dep_total) < 0.02
        ok_date = True
        try:
            ok_date = (rec['date'].date().isoformat() == dep_date)
        except Exception:
            # Access date may be datetime or None
            ok_date = False
        print(f"  ✓ {dep_no}: date={'OK' if ok_date else rec['date']}, total={rec['total']:.2f}, key='{rec['key']}', trans='{rec['transact']}', type='{rec['type']}', lastby='{rec['lastupdatedby']}'")
        if not ok_total:
            print(f"    • Amount mismatch: expected {dep_total:.2f}")

    # Pull charter_refunds and try to match by amount/date proximity
    pg_rows = check_pg_charter_refunds()

    # Index refunds by rounded amount
    from collections import defaultdict
    by_amt = defaultdict(list)
    for rid, rdate, amount, reserve, cid, desc, src in pg_rows:
        if amount is None:
            continue
        by_amt[round(float(amount), 2)].append((rid, rdate, reserve, cid, desc, src))

    print("\nCross-check in charter_refunds:")
    for dep_no, dep_date, dep_key, dep_total in TARGETS:
        amt = round(abs(dep_total), 2)
        candidates = by_amt.get(amt, [])
        parsed_date = datetime.strptime(dep_date, "%Y-%m-%d")
        near_candidates = [c for c in candidates if near(c[1], parsed_date, days=30)]
        if near_candidates:
            # Prefer one with reserve_number present
            with_reserve = [c for c in near_candidates if c[2]]
            chosen = with_reserve[0] if with_reserve else near_candidates[0]
            chosen_date = chosen[1].date() if isinstance(chosen[1], datetime) else chosen[1]
            print(f"  ✓ Deposit {dep_no} amount {amt:.2f} matches charter_refunds #{chosen[0]} on {chosen_date} src={chosen[5]} reserve={chosen[2]} linked={'yes' if chosen[3] else 'no'} (candidates={len(near_candidates)})")
        else:
            print(f"  ✗ Deposit {dep_no} amount {amt:.2f} has no charter_refunds within ±30 days of {dep_date}")

    # Special check for $91.88 refund (2016-07)
    amt = round(ALSO_CHECK_AMOUNT_2016, 2)
    candidates = by_amt.get(amt, [])
    near_candidates = [c for c in candidates if near(c[1], ALSO_CHECK_DATE_2016, days=60)]
    print("\n$91.88 refund (circa 2016-07-06, Square email evidence):")
    if near_candidates:
        for c in near_candidates[:5]:
            cdate = c[1].date() if isinstance(c[1], datetime) else c[1]
            print(f"  ✓ charter_refunds #{c[0]} date={cdate} reserve={c[2]} src={c[5]} linked={'yes' if c[3] else 'no'}")
    else:
        print("  ✗ Not found in charter_refunds within ±60 days. May only exist in email evidence/Square.")

    print("\nDone.")
