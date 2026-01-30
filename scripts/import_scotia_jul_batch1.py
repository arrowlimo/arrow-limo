import argparse
import hashlib
from datetime import datetime
import psycopg2

# Arrow Limousine - Scotia 903990106011 July 2013 screenshot batch import
# Pattern: manual duplicate prevention via SHA256(date|description|amount)
# Account: 903990106011 (Scotia)

ACCOUNT_NUMBER = '903990106011'

TRANSACTIONS = [
    # From screenshots: columns show description and amount; right column shows date codes 0705, 0708, 0709
    # We map them to July 5, 8, 9, 2013 respectively. Amounts are parsed as dollars.cents with implied decimal from statement.

    # 2013-07-05 block
    {"date": "2013-07-05", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 1087.50},
    {"date": "2013-07-05", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 593.92},
    {"date": "2013-07-05", "type": "withdrawal", "description": "CHO 200 3700294603", "amount": 1016.98},
    {"date": "2013-07-05", "type": "withdrawal", "description": "CHO 215 3700296601", "amount": 664.51},
    {"date": "2013-07-05", "type": "withdrawal", "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD", "amount": 10.02},
    {"date": "2013-07-05", "type": "withdrawal", "description": "POINT OF SALE PURCHASE CELLCOM WIRELESS INC RED DEER ABCA", "amount": 91.85},
    {"date": "2013-07-05", "type": "withdrawal", "description": "POINT OF SALE PURCHASE WINDSHIELD SURGEONS RED DEER ABCA", "amount": 183.75},
    {"date": "2013-07-05", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RED DEER CO-OP QPE RED DEER ABCA", "amount": 26.01},
    {"date": "2013-07-05", "type": "withdrawal", "description": "POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA", "amount": 119.70},
    {"date": "2013-07-05", "type": "withdrawal", "description": "POINT OF SALE PURCHASE SUMMIT ESSO RED DEER ABCA", "amount": 97.55},
    {"date": "2013-07-05", "type": "withdrawal", "description": "PC BILL PAYMENT ROGERS WIRELESS SERVICES 63804785", "amount": 650.28},
    {"date": "2013-07-05", "type": "withdrawal", "description": "PC BILL PAYMENT TELUS COMMUNICATIONS 63804786", "amount": 2461.99},

    # 2013-07-08 block
    {"date": "2013-07-08", "type": "withdrawal", "description": "AMEX BANK OF CANADA MISC PAYMENT AMEX 9322877839", "amount": 275.30},
    {"date": "2013-07-08", "type": "withdrawal", "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB", "amount": 300.00},
    {"date": "2013-07-08", "type": "withdrawal", "description": "CHO 209 3700375347", "amount": 1363.77},
    {"date": "2013-07-08", "type": "withdrawal", "description": "CHO 216 3700381835", "amount": 438.38},
    {"date": "2013-07-08", "type": "withdrawal", "description": "RONA #66220 RED DEER ABCA POINT OF SALE PURCHASE", "amount": 59.81},
    {"date": "2013-07-08", "type": "withdrawal", "description": "STAPLES #285 RED DEER ABCA POINT OF SALE PURCHASE", "amount": 72.61},
    {"date": "2013-07-08", "type": "withdrawal", "description": "NATIONAL MONEYMART #12 RED DEER ABCA POINT OF SALE PURCHASE", "amount": 1000.00},
    {"date": "2013-07-08", "type": "withdrawal", "description": "PHIL'S RESTAURANTS RED DEER ABCA POINT OF SALE PURCHASE", "amount": 47.91},
    {"date": "2013-07-08", "type": "withdrawal", "description": "604 - LB 67TH ST. RED DEER ABCD POINT OF SALE PURCHASE", "amount": 92.14},
    {"date": "2013-07-08", "type": "withdrawal", "description": "CELLCOM WIRELESS INC RED DEER ABCA POINT OF SALE PURCHASE", "amount": 280.83},
    {"date": "2013-07-08", "type": "withdrawal", "description": "CENTEX DEERPAK (C-STOR) RED DEER ABCA POINT OF SALE PURCHASE", "amount": 127.18},
    {"date": "2013-07-08", "type": "withdrawal", "description": "ERLES AUTO REPAIR RED DEER ABCA POINT OF SALE PURCHASE", "amount": 62.88},
    {"date": "2013-07-08", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 606.18},
    {"date": "2013-07-08", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 242.74},
    {"date": "2013-07-08", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 177.54},

    # 2013-07-09 block
    {"date": "2013-07-09", "type": "withdrawal", "description": "ACCOUNT FEE S/C", "amount": 30.88},
]


def generate_hash(date_str: str, description: str, amount: float) -> str:
    key = f"{date_str}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(key).hexdigest()


def get_db_connection():
    import os
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    return conn


def upsert_transactions(write: bool = False):
    conn = get_db_connection()
    cur = conn.cursor()

    # Preload existing hashes to avoid unique constraint failures
    cur.execute("SELECT source_hash FROM banking_transactions WHERE account_number = %s", (ACCOUNT_NUMBER,))
    existing_hashes = {row[0] for row in cur.fetchall() if row[0]}

    inserted = 0
    skipped = 0

    for txn in TRANSACTIONS:
        date_str = txn["date"]
        description = txn["description"]
        amount = float(txn["amount"])  # dollars
        source_hash = generate_hash(date_str, description, amount)

        if source_hash in existing_hashes:
            skipped += 1
            continue

        # Split into debit/credit
        debit_amount = amount if txn["type"] == "withdrawal" else None
        credit_amount = amount if txn["type"] == "deposit" else None

        if write:
            cur.execute(
                """
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    ACCOUNT_NUMBER,
                    datetime.strptime(date_str, "%Y-%m-%d").date(),
                    description,
                    debit_amount,
                    credit_amount,
                    source_hash,
                ),
            )
        inserted += 1
        existing_hashes.add(source_hash)

    if write:
        conn.commit()
    cur.close()
    conn.close()
    return inserted, skipped


def main():
    parser = argparse.ArgumentParser(description="Import Scotia July 2013 batch from screenshots")
    parser.add_argument('--write', action='store_true', help='Apply inserts')
    args = parser.parse_args()

    inserted, skipped = upsert_transactions(write=args.write)
    mode = 'WRITE' if args.write else 'DRY-RUN'
    print(f"{mode}: prepared {inserted} inserts, skipped {skipped} duplicates for account {ACCOUNT_NUMBER}")


if __name__ == '__main__':
    main()
