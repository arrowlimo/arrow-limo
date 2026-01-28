import argparse
import hashlib
import sys
from datetime import date

# Ensure we can import get_db_connection from api.py
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import get_db_connection  # type: ignore


ACCOUNT_NUMBER = "903990106011"  # Scotia Bank


def sha256_key(txn_date: date, description: str, amount: float) -> str:
    key = f"{txn_date.isoformat()}|{description.strip()}|{amount:.2f}".encode("utf-8")
    return hashlib.sha256(key).hexdigest()


def load_existing_hashes(cur):
    cur.execute(
        """
        SELECT source_hash FROM banking_transactions
        WHERE account_number = %s AND source_hash IS NOT NULL
        """,
        (ACCOUNT_NUMBER,),
    )
    return {row[0] for row in cur.fetchall()}


def planned_transactions():
    """
    Initial May 2013 entries captured from statement screenshots.
    Amounts are entered as positive numbers and classified as 'debit' or 'credit'.

    IMPORTANT: Only clearly readable entries are included in batch1.
    We'll append more lines in batch2/3 as we progress through the pages.
    """
    return [
        # 2013-05-01
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 100.00,
            "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB",
        },
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 2695.40,
            "description": "RENT/LEASES ACE TRUCK RENTALS LTD.",
        },
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 889.87,
            "description": "AUTO LEASE",
        },
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 471.98,
            "description": "AUTO LEASE HEFFNER AUTO FC",
        },
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 48.00,
            "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB",
        },
        {
            "date": date(2013, 5, 1),
            "type": "credit",
            "amount": 85.00,
            "description": "DEPOSIT CHASE PAYMENTECH (marker)",
        },
        {
            "date": date(2013, 5, 1),
            "type": "credit",
            "amount": 515.50,
            "description": "DEPOSIT CHASE PAYMENTECH (marker)",
        },
        {
            "date": date(2013, 5, 1),
            "type": "credit",
            "amount": 397.45,
            "description": "DEPOSIT CHASE PAYMENTECH (marker)",
        },
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 53.27,
            "description": "POINT OF SALE PURCHASE MONGOLIE GRILL RED DEER AB",
        },
        {
            "date": date(2013, 5, 1),
            "type": "debit",
            "amount": 30.00,
            "description": "POINT OF SALE PURCHASE CANADIAN TIRE GAS BAR RED DEER AB",
        },
        {
            "date": date(2013, 5, 1),
            "type": "credit",
            "amount": 567.95,
            "description": "DEPOSIT CHASE PAYMENTECH (marker)",
        },
        {
            "date": date(2013, 5, 1),
            "type": "credit",
            "amount": 219.75,
            "description": "DEPOSIT CHASE PAYMENTECH (marker)",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 205.00,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 494.81,
            "description": "DEPOSIT CHQ 175 240049286",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 1500.00,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 528.15,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 997.50,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 640.00,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 500.00,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 82.50,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 3),
            "type": "credit",
            "amount": 1069.00,
            "description": "DEPOSIT",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 200.00,
            "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB",
        },
        {
            "date": date(2013, 5, 6),
            "type": "credit",
            "amount": 1500.00,
            "description": "DEPOSIT CHQ 178 3700063990",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 50.06,
            "description": "POINT OF SALE PURCHASE CENTEX DEERPARK RED DEER AB",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 77.08,
            "description": "POINT OF SALE PURCHASE RED DEER CO-OP QPE RED DEER AB",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 67.12,
            "description": "POINT OF SALE PURCHASE 606 - LD NORTH HILL RED DEER AB",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 70.25,
            "description": "POINT OF SALE PURCHASE CENTEX DEERPARK (C-STORE) RED DEER AB",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 192.12,
            "description": "POINT OF SALE PURCHASE CANADIAN TIRE #645 RED DEER AB",
        },
        {
            "date": date(2013, 5, 6),
            "type": "debit",
            "amount": 20.99,
            "description": "POINT OF SALE PURCHASE CANADIAN TIRE #329 RED DEER AB",
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="Import Scotia May 2013 (batch1) from captured transactions")
    parser.add_argument("--write", action="store_true", help="Apply changes to database (default is dry-run)")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        existing_hashes = load_existing_hashes(cur)

        rows_prepared = 0
        rows_inserted = 0

        for t in planned_transactions():
            txn_date = t["date"]
            desc = t["description"].strip()
            amount = float(t["amount"])
            typ = t["type"]  # 'debit' or 'credit'

            if typ not in ("debit", "credit"):
                raise ValueError(f"Invalid type for {desc}: {typ}")

            source_hash = sha256_key(txn_date, desc, amount)
            if source_hash in existing_hashes:
                # Already present; skip
                continue

            rows_prepared += 1
            if args.write:
                debit_amount = amount if typ == "debit" else None
                credit_amount = amount if typ == "credit" else None
                cur.execute(
                    """
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount, source_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ACCOUNT_NUMBER,
                        txn_date,
                        desc,
                        debit_amount,
                        credit_amount,
                        source_hash,
                    ),
                )
                existing_hashes.add(source_hash)
                rows_inserted += 1

        if args.write:
            conn.commit()
        else:
            conn.rollback()

        mode = "APPLIED" if args.write else "DRY-RUN"
        print(f"{mode}: prepared={rows_prepared}, inserted={rows_inserted}")
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
