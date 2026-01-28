#!/usr/bin/env python
"""
Assign `account_number` for all cheques in `cheque_register` where it's NULL/empty.
Matching strategy:
- Prefer exact match on `banking_transactions.check_number = cheque_number`
- Require exact `amount` match (using credit/debit depending on sign)
- Use date window: from cheque_date - 7 days to cheque_date + 60 days
- If multiple matches across accounts, choose the one with smallest date delta; if tie, skip for manual review
- Back up affected cheques to JSON before updating

Usage:
  python -X utf8 scripts/assign_accounts_for_unassigned_cheques.py [--dry-run]
"""

import os
import json
from datetime import datetime, timedelta
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DRY_RUN = "--dry-run" in os.sys.argv


def fetch_unassigned_cheques(cur):
    cur.execute("""
        SELECT id, cheque_number, cheque_date, amount, payee
        FROM cheque_register
        WHERE (account_number IS NULL OR account_number = '')
        ORDER BY cheque_date NULLS LAST
    """)
    return cur.fetchall()


def find_candidate_matches(cur, cheque_number, cheque_date, amount):
    # Date window
    start_date = None
    end_date = None
    if cheque_date:
        start_date = cheque_date - timedelta(days=7)
        end_date = cheque_date + timedelta(days=60)

    # Normalize amount: banking may store in debit/credit
    # Cheques are money out, so expect debit_amount > 0, credit_amount NULL/0
    # We'll match on absolute value equality in either column for safety
    params = {"cheque_number": str(cheque_number)}
    sql = [
        """
        SELECT transaction_id, account_number, transaction_date, description,
               debit_amount, credit_amount, check_number, check_recipient
        FROM banking_transactions
        WHERE check_number = %(cheque_number)s
        """
    ]
    if start_date and end_date:
        sql[0] += " AND transaction_date BETWEEN %(start)s AND %(end)s"
        params.update({"start": start_date, "end": end_date})

    cur.execute(sql[0], params)
    rows = cur.fetchall()

    # Filter by amount exact match
    amt = float(amount)
    def amt_matches(r):
        debit = float(r[4]) if r[4] is not None else 0.0
        credit = float(r[5]) if r[5] is not None else 0.0
        return abs(debit - amt) < 0.005 or abs(credit - amt) < 0.005

    rows = [r for r in rows if amt_matches(r)]

    # Fallback: search description when check_number not populated
    if not rows:
        desc_sql = (
            """
            SELECT transaction_id, account_number, transaction_date, description,
                   debit_amount, credit_amount, check_number, check_recipient
            FROM banking_transactions
            WHERE description ILIKE %(pattern)s
            """
        )
        desc_params = {"pattern": f"%CHQ {cheque_number}%"}
        if start_date and end_date:
            desc_sql += " AND transaction_date BETWEEN %(start)s AND %(end)s"
            desc_params.update({"start": start_date, "end": end_date})
        cur.execute(desc_sql, desc_params)
        desc_rows = cur.fetchall()
        rows = [r for r in desc_rows if amt_matches(r)]

    # Rank by date distance
    def date_delta(r):
        dt = r[2]
        if cheque_date and dt:
            return abs((dt - cheque_date).days)
        return 9999

    rows.sort(key=date_delta)
    # If still no rows, try amount-only matching within a wider window
    if not rows:
        amt_sql = (
            """
            SELECT transaction_id, account_number, transaction_date, description,
                   debit_amount, credit_amount, check_number, check_recipient
            FROM banking_transactions
            WHERE (debit_amount = %(amt)s OR credit_amount = %(amt)s)
            """
        )
        amt_params = {"amt": float(amount)}
        # Use a wider window if we have a cheque_date; else restrict to 2012 (common for current work)
        if start_date and end_date:
            wider_start = cheque_date - timedelta(days=30)
            wider_end = cheque_date + timedelta(days=120)
            amt_sql += " AND transaction_date BETWEEN %(wstart)s AND %(wend)s"
            amt_params.update({"wstart": wider_start, "wend": wider_end})
        else:
            amt_sql += " AND transaction_date BETWEEN '2012-01-01'::date AND '2012-12-31'::date"
        cur.execute(amt_sql, amt_params)
        rows = cur.fetchall()
        rows = [r for r in rows if amt_matches(r)]
        rows.sort(key=date_delta)
    return rows


def backup_cheques(cur, cheque_ids):
    if not cheque_ids:
        return None
    cur.execute(
        """
        SELECT id, cheque_number, account_number, cheque_date, amount, payee, status
        FROM cheque_register
        WHERE id = ANY(%s)
        ORDER BY cheque_date, cheque_number
        """,
        (cheque_ids,)
    )
    rows = cur.fetchall()
    backup_data = [
        {
            "id": r[0],
            "cheque_number": r[1],
            "account_number": r[2],
            "cheque_date": (str(r[3]) if r[3] else None),
            "amount": str(r[4]),
            "payee": r[5],
            "status": r[6],
        }
        for r in rows
    ]
    fname = f"cheque_unassigned_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(backup_data, f, indent=2)
    return fname


def main():
    print("=" * 100)
    print("ASSIGN ACCOUNT_NUMBER FOR UNASSIGNED CHEQUES")
    print("=" * 100)
    print(f"Dry-run: {DRY_RUN}")

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    try:
        unassigned = fetch_unassigned_cheques(cur)
        print(f"Unassigned cheques: {len(unassigned)}")
        for r in unassigned:
            print(f"  ID {r[0]} | CHQ {r[1]} | {r[2]} | ${r[3]} | {r[4]}")

        updates = []  # (id, cheque_number, assigned_account)
        ambiguous = []  # (id, cheque_number, candidates)
        unmatched = []  # (id, cheque_number)

        for (cid, chq_no, chq_date, amt, payee) in unassigned:
            candidates = find_candidate_matches(cur, chq_no, chq_date, amt)
            if not candidates:
                unmatched.append((cid, chq_no))
                continue
            # If one clear best candidate (top-ranked) and unique account_number among candidates
            top = candidates[0]
            acct = top[1]
            accounts = {c[1] for c in candidates}
            if len(accounts) == 1:
                updates.append((cid, chq_no, acct))
            else:
                ambiguous.append((cid, chq_no, [(c[0], c[1], c[2], c[3]) for c in candidates[:5]]))

        print(f"\nProposed updates: {len(updates)}")
        for u in updates:
            print(f"  CHQ {u[1]} -> Account {u[2]} (ID {u[0]})")
        print(f"Ambiguous: {len(ambiguous)} | Unmatched: {len(unmatched)}")

        if DRY_RUN:
            print("\nDry-run mode: no changes applied.")
            return

        # Backup
        backup_file = backup_cheques(cur, [u[0] for u in updates])
        if backup_file:
            print(f"\n✅ Backup created: {backup_file}")

        # Apply updates
        updated = 0
        for (cid, chq_no, acct) in updates:
            cur.execute(
                """
                UPDATE cheque_register
                SET account_number = %s
                WHERE id = %s
                  AND (account_number IS NULL OR account_number = '')
                """,
                (acct, cid)
            )
            updated += cur.rowcount
        conn.commit()
        print(f"\n✅ Updated {updated} cheques with assigned account_number")

        # Verification
        cur.execute(
            """
            SELECT cheque_number, account_number, cheque_date, amount
            FROM cheque_register
            WHERE id = ANY(%s)
            ORDER BY cheque_date, cheque_number
            """,
            ([u[0] for u in updates],)
        )
        verify_rows = cur.fetchall()
        print("\n📋 Verification:")
        for v in verify_rows:
            print(f"  CHQ {v[0]} | Account {v[1]} | {v[2]} | ${v[3]}")

        if ambiguous:
            print("\n⚠️ Ambiguous cheques (manual review needed):")
            for (cid, chq, cands) in ambiguous:
                print(f"  CHQ {chq} (ID {cid}) candidates:")
                for c in cands:
                    print(f"    TX {c[0]} | Account {c[1]} | {c[2]} | {c[3]}")
        if unmatched:
            print("\n❌ Unmatched cheques:")
            for (cid, chq) in unmatched:
                print(f"  CHQ {chq} (ID {cid})")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close(); conn.close()


if __name__ == "__main__":
    main()
