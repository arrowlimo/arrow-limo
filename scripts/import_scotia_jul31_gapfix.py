import argparse
import hashlib
from datetime import datetime
import psycopg2

ACCOUNT_NUMBER = '903990106011'

TRANSACTIONS = [
    # Missing 2013-07-31 items from screenshot
    {"date": "2013-07-31", "type": "withdrawal", "description": "POINT OF SALE PURCHASE BELL CONNECTIONS ROCKY VIEW ABCA", "amount": 31.45},
    {"date": "2013-07-31", "type": "withdrawal", "description": "SERVICE CHARGE", "amount": 11.90},
    {"date": "2013-07-31", "type": "withdrawal", "description": "OVERDRAFT INTEREST CHG", "amount": 17.91},
]


def generate_hash(date_str: str, description: str, amount: float) -> str:
    key = f"{date_str}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(key).hexdigest()


def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def upsert_transactions(write: bool = False):
    conn = get_db_connection()
    cur = conn.cursor()

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
    cur.close(); conn.close()
    return inserted, skipped


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix missing 2013-07-31 transactions from screenshots")
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()

    ins, skip = upsert_transactions(write=args.write)
    print(("WRITE" if args.write else "DRY-RUN") + f": prepared {ins} inserts, skipped {skip}")


if __name__ == '__main__':
    main()
