import argparse
import hashlib
import sys
from datetime import date
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import get_db_connection  # type: ignore

ACCOUNT_NUMBER = "903990106011"


def sha256_key(txn_date: date, description: str, amount: float) -> str:
    return hashlib.sha256(f"{txn_date.isoformat()}|{description.strip()}|{amount:.2f}".encode("utf-8")).hexdigest()


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
    June 2013 batch3: final June entries (06/24-06/28) from screenshots.
    """
    return [
        # 2013-06-24
        {"date": date(2013, 6, 24), "type": "credit", "amount": 1202.76, "description": "DEPOSIT GAETZ AND 67TH STREET 51409 002"},
        {"date": date(2013, 6, 24), "type": "credit", "amount": 500.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 24), "type": "credit", "amount": 1265.25, "description": "DEPOSIT"},

        # 2013-06-25
        {"date": date(2013, 6, 25), "type": "credit", "amount": 667.78, "description": "MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA"},
        {"date": date(2013, 6, 25), "type": "credit", "amount": 75.27, "description": "MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA"},
        {"date": date(2013, 6, 25), "type": "credit", "amount": 166.11, "description": "ERROR CORRECTION CHQ 830 3700068633"},
        {"date": date(2013, 6, 25), "type": "credit", "amount": 500.00, "description": "DEPOSIT CHQ 204 3700148838"},
        {"date": date(2013, 6, 25), "type": "debit", "amount": 131.75, "description": "POINT OF SALE PURCHASE MOHAWK RED DEER #4320 RED DEER AB"},
        {"date": date(2013, 6, 25), "type": "debit", "amount": 74.90, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 6, 25), "type": "debit", "amount": 172.20, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 6, 25), "type": "debit", "amount": 1198.47, "description": "POINT OF SALE PURCHASE NORTHLAND RADIATOR RED DEER AB"},
        {"date": date(2013, 6, 25), "type": "debit", "amount": 500.00, "description": "DEBIT MEMO 44472367 PC-EMAIL MONEY TRF"},
        {"date": date(2013, 6, 25), "type": "debit", "amount": 1.00, "description": "SERVICE CHARGE PC-EMAIL MONEY TRF"},

        # 2013-06-26
        {"date": date(2013, 6, 26), "type": "credit", "amount": 3918.50, "description": "DEPOSIT"},
        {"date": date(2013, 6, 26), "type": "credit", "amount": 527.71, "description": "DEPOSIT"},

        # 2013-06-27
        {"date": date(2013, 6, 27), "type": "debit", "amount": 89.50, "description": "POINT OF SALE PURCHASE WAL-MART #3075 RED DEER AB"},
        {"date": date(2013, 6, 27), "type": "debit", "amount": 70.00, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 27), "type": "credit", "amount": 511.60, "description": "DEPOSIT"},
        {"date": date(2013, 6, 27), "type": "credit", "amount": 375.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 27), "type": "credit", "amount": 1812.43, "description": "DEPOSIT"},
        {"date": date(2013, 6, 27), "type": "debit", "amount": 61.60, "description": "POINT OF SALE PURCHASE SAVE ON FOODS #6682 RED DEER AB"},
        {"date": date(2013, 6, 27), "type": "debit", "amount": 75.60, "description": "POINT OF SALE PURCHASE BUCK OR TWO #235 RED DEER AB"},
        {"date": date(2013, 6, 27), "type": "debit", "amount": 591.00, "description": "POINT OF SALE PURCHASE RED DEER REGISTRIES RED DEER AB"},

        # 2013-06-28
        {"date": date(2013, 6, 28), "type": "debit", "amount": 112.50, "description": "SERVICE CHARGE"},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 5.21, "description": "OVERDRAFT INTEREST CHG"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 1807.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 744.50, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 574.14, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 355.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 1201.25, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 158.79, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 3510.11, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 526.25, "description": "DEPOSIT"},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 2695.40, "description": "RENT/LEASES ACE TRUCK RENTALS LTD."},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 889.87, "description": "AUTO LEASE"},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 471.98, "description": "AUTO LEASE HEFFNER AUTO FC"},
        {"date": date(2013, 6, 28), "type": "credit", "amount": 1500.00, "description": "DEPOSIT CHQ 205 3700471526"},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 83.80, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 194.83, "description": "POINT OF SALE PURCHASE RED DEER CO-OP TAYLOR RED DEER AB"},
        {"date": date(2013, 6, 28), "type": "debit", "amount": 70.35, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
    ]


def main():
    parser = argparse.ArgumentParser(description="Import Scotia June 2013 (batch3) final entries")
    parser.add_argument("--write", action="store_true", help="Apply changes to database (default is dry-run)")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        existing_hashes = load_existing_hashes(cur)
        prepared = 0
        inserted = 0

        for t in planned_transactions():
            txn_date = t["date"]
            desc = t["description"].strip()
            amount = float(t["amount"])
            typ = t["type"]

            source_hash = sha256_key(txn_date, desc, amount)
            if source_hash in existing_hashes:
                continue

            prepared += 1
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
                    (ACCOUNT_NUMBER, txn_date, desc, debit_amount, credit_amount, source_hash),
                )
                existing_hashes.add(source_hash)
                inserted += 1

        if args.write:
            conn.commit()
        else:
            conn.rollback()

        print(("APPLIED" if args.write else "DRY-RUN") + f": prepared={prepared}, inserted={inserted}")
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
