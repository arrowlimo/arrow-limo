import argparse
import hashlib
from datetime import datetime
import psycopg2

ACCOUNT_NUMBER = '903990106011'

# Parsed from screenshots: dates encoded as 0709, 0710, 0711, 0712, 0715, 0716, 0718, 0719
# Map to 2013-07-DD
TRANSACTIONS = [
    # 2013-07-09 (continuation)
    {"date": "2013-07-09", "type": "withdrawal", "description": "POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA", "amount": 74.15},
    {"date": "2013-07-09", "type": "withdrawal", "description": "POINT OF SALE PURCHASE SUMMIT ESSO 88004388 RED DEER ABCA", "amount": 101.00},
    {"date": "2013-07-09", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 756.14},
    {"date": "2013-07-09", "type": "withdrawal", "description": "OVERDRAWN HANDLING CHGS SERVICE CHARGE", "amount": 15.00},
    {"date": "2013-07-09", "type": "deposit", "description": "DEPOSIT GAETZ AND 67TH STREET 514069 002", "amount": 1763.26},
    {"date": "2013-07-09", "type": "deposit", "description": "DEBITCD DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1082.00},
    {"date": "2013-07-09", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 240.98},

    # 2013-07-10
    {"date": "2013-07-10", "type": "withdrawal", "description": "RETURNED ITEM/CHARGEBACK CHO #202 REV CDA INSUFFICIENT FUNDS RETURNED NSF CHEQUE", "amount": 2963.51},
    {"date": "2013-07-10", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 3060.18},
    {"date": "2013-07-10", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 733.72},

    # 2013-07-11
    {"date": "2013-07-11", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1676.01},
    {"date": "2013-07-11", "type": "withdrawal", "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB", "amount": 200.00},
    {"date": "2013-07-11", "type": "withdrawal", "description": "SERVICE CHARGE", "amount": 42.50},

    # 2013-07-12
    {"date": "2013-07-12", "type": "withdrawal", "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB", "amount": 200.00},
    {"date": "2013-07-12", "type": "deposit", "description": "DEPOSIT CHO 212 3700187556", "amount": 668.38},
    {"date": "2013-07-12", "type": "deposit", "description": "DEBITCD DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1750.00},

    # 2013-07-12 (second screenshot set)
    {"date": "2013-07-12", "type": "withdrawal", "description": "POINT OF SALE PURCHASE CANADA SAFEWAY #813 RED DEER ABCA", "amount": 175.32},
    {"date": "2013-07-12", "type": "deposit", "description": "DEBITCD DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 689.38},
    {"date": "2013-07-12", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 61.43},
    {"date": "2013-07-12", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 1265.88},
    {"date": "2013-07-12", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 205.00},
    {"date": "2013-07-12", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 103.36},
    {"date": "2013-07-12", "type": "withdrawal", "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB", "amount": 1000.00},
    {"date": "2013-07-12", "type": "withdrawal", "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB", "amount": 400.00},
    {"date": "2013-07-12", "type": "withdrawal", "description": "AUTO LEASE J08136 JACK CARTER", "amount": 2525.25},
    {"date": "2013-07-12", "type": "withdrawal", "description": "AUTO LEASE HEFFNER AUTO FC", "amount": 1475.25},
    {"date": "2013-07-12", "type": "withdrawal", "description": "AUTO LEASE HEFFNER AUTO FC", "amount": 1900.50},
    {"date": "2013-07-12", "type": "withdrawal", "description": "AUTO LEASE HEFFNER AUTO FC", "amount": 889.88},
    {"date": "2013-07-12", "type": "withdrawal", "description": "AUTO LEASE HEFFNER AUTO FC", "amount": 471.97},
    {"date": "2013-07-12", "type": "withdrawal", "description": "POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA", "amount": 60.00},
    {"date": "2013-07-12", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER ABCA", "amount": 26.95},

    # 2013-07-15
    {"date": "2013-07-15", "type": "withdrawal", "description": "DEBIT MEMO 83704064", "amount": 350.00},
    {"date": "2013-07-15", "type": "withdrawal", "description": "OVERDRAWN HANDLING CHGS SERVICE CHARGE", "amount": 30.00},
    {"date": "2013-07-15", "type": "deposit", "description": "PC-EMAIL MONEY TRF", "amount": 1.00},
    {"date": "2013-07-15", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 855.06},

    # 2013-07-16
    {"date": "2013-07-16", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1215.62},
    {"date": "2013-07-16", "type": "deposit", "description": "OTHER CREDIT MEMO RETURN ITEM REV OHC", "amount": 20.00},
    {"date": "2013-07-16", "type": "withdrawal", "description": "OTHER CREDIT MEMO RETURN ITEM", "amount": 1900.50},
    {"date": "2013-07-16", "type": "withdrawal", "description": "OTHER CREDIT MEMO RETURN ITEM", "amount": 1475.25},
    {"date": "2013-07-16", "type": "withdrawal", "description": "OTHER CREDIT MEMO RETURN ITEM", "amount": 2525.25},
    {"date": "2013-07-16", "type": "withdrawal", "description": "OTHER CREDIT MEMO RETURN ITEM", "amount": 1885.65},
    {"date": "2013-07-16", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 240.98},

    # 2013-07-18
    {"date": "2013-07-18", "type": "deposit", "description": "DEPOSIT NORTHLAND RADIATOR RED DEER ABCD", "amount": 1000.00},
    {"date": "2013-07-18", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1001.50},
    {"date": "2013-07-18", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 500.00},

    # 2013-07-19
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD", "amount": 62.01},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE", "amount": 11.99},
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
    cur.close()
    conn.close()
    return inserted, skipped


def main():
    parser = argparse.ArgumentParser(description="Import Scotia July 2013 batch 2 from screenshots")
    parser.add_argument('--write', action='store_true', help='Apply inserts')
    args = parser.parse_args()

    inserted, skipped = upsert_transactions(write=args.write)
    mode = 'WRITE' if args.write else 'DRY-RUN'
    print(f"{mode}: prepared {inserted} inserts, skipped {skipped} duplicates for account {ACCOUNT_NUMBER}")


if __name__ == '__main__':
    main()
