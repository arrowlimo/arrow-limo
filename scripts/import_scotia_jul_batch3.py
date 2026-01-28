import argparse
import hashlib
from datetime import datetime
import psycopg2

ACCOUNT_NUMBER = '903990106011'

TRANSACTIONS = [
    # 2013-07-19
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA", "amount": 917.34},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER ABCA", "amount": 150.00},
    {"date": "2013-07-19", "type": "deposit", "description": "DEPOSIT", "amount": 2000.00},
    {"date": "2013-07-19", "type": "deposit", "description": "DEPOSIT", "amount": 143.00},
    {"date": "2013-07-19", "type": "deposit", "description": "DEPOSIT", "amount": 175.00},
    {"date": "2013-07-19", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 2098.39},
    {"date": "2013-07-19", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1328.95},
    {"date": "2013-07-19", "type": "withdrawal", "description": "CHQ* 34 30031998", "amount": 2525.25},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER ABCA", "amount": 68.00},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD", "amount": 107.93},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD", "amount": 109.63},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER ABCA", "amount": 71.50},
    {"date": "2013-07-19", "type": "withdrawal", "description": "DEBIT MEMO", "amount": 2000.00},
    {"date": "2013-07-19", "type": "withdrawal", "description": "DRAFT PURCHASE SERVICE CHARGE", "amount": 7.50},
    {"date": "2013-07-19", "type": "withdrawal", "description": "CHO 218 3700312291", "amount": 567.00},
    {"date": "2013-07-19", "type": "withdrawal", "description": "POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA", "amount": 997.35},
    {"date": "2013-07-19", "type": "withdrawal", "description": "OVERDRAWN HANDLING CHGS", "amount": 5.00},

    # 2013-07-23
    {"date": "2013-07-23", "type": "deposit", "description": "DEPOSIT", "amount": 140.00},

    # 2013-07-24
    {"date": "2013-07-24", "type": "deposit", "description": "DEPOSIT", "amount": 828.99},
    {"date": "2013-07-24", "type": "withdrawal", "description": "MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA", "amount": 242.73},
    {"date": "2013-07-24", "type": "withdrawal", "description": "INSURANCE IFS PREMIUM FIN AUTO INSURANCE", "amount": 2383.24},
    {"date": "2013-07-24", "type": "withdrawal", "description": "INSURANCE JEVCO INSURANCE COMPANY", "amount": 726.29},
    {"date": "2013-07-24", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 867.31},

    # 2013-07-25
    {"date": "2013-07-25", "type": "withdrawal", "description": "SERVICE CHARGE", "amount": 85.00},
    {"date": "2013-07-25", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 978.00},
    {"date": "2013-07-25", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 175.00},
    {"date": "2013-07-25", "type": "withdrawal", "description": "SHARED ABM WITHDRAWAL INTERAC", "amount": 162.25},
    {"date": "2013-07-25", "type": "withdrawal", "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB", "amount": 200.00},
    {"date": "2013-07-25", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER ABCA", "amount": 69.00},
    {"date": "2013-07-25", "type": "withdrawal", "description": "POINT OF SALE PURCHASE MILANO FOR MEN RED DEER ABCA", "amount": 68.25},
    {"date": "2013-07-25", "type": "withdrawal", "description": "POINT OF SALE PURCHASE GEORGE'S PIZZA AND STE RED DEER ABCA", "amount": 34.87},
    {"date": "2013-07-25", "type": "withdrawal", "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD", "amount": 57.29},

    # 2013-07-26
    {"date": "2013-07-26", "type": "withdrawal", "description": "INTERAC ABM FEE", "amount": 1.50},
    {"date": "2013-07-26", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 952.62},
    {"date": "2013-07-26", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 595.84},

    # 2013-07-29
    {"date": "2013-07-29", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 250.00},
    {"date": "2013-07-29", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 2897.65},
    {"date": "2013-07-29", "type": "deposit", "description": "MCARD DEP CR CHASE PAYMENTECH 097384700019 00001", "amount": 149.00},
    {"date": "2013-07-29", "type": "deposit", "description": "DEBITCD DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 245.88},
    {"date": "2013-07-29", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 835.89},
    {"date": "2013-07-29", "type": "withdrawal", "description": "MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA", "amount": 190.02},
    {"date": "2013-07-29", "type": "withdrawal", "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER ABCA", "amount": 41.87},
    {"date": "2013-07-29", "type": "withdrawal", "description": "PC BILL PAYMENT TELUS COMMUNICATIONS 145096763", "amount": 100.00},

    # 2013-07-30
    {"date": "2013-07-30", "type": "deposit", "description": "VISA DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 1750.00},
    {"date": "2013-07-30", "type": "withdrawal", "description": "CHO 219 3700208438", "amount": 2100.00},
    {"date": "2013-07-30", "type": "deposit", "description": "DEBITCD DEP CR CHASE PAYMENTECH 087384700019 00001", "amount": 624.00},
    {"date": "2013-07-30", "type": "withdrawal", "description": "POINT OF SALE PURCHASE TONY ROMA'S - MACLEOD CALGARY ABCA", "amount": 70.88},
    {"date": "2013-07-30", "type": "withdrawal", "description": "POINT OF SALE PURCHASE CPC/SCP RC #131083", "amount": 46.91},
    {"date": "2013-07-30", "type": "withdrawal", "description": "POINT OF SALE PURCHASE MONEY MART #12 RED DEER ABCA", "amount": 250.00},

    # 2013-07-31
    {"date": "2013-07-31", "type": "withdrawal", "description": "POINT OF SALE PURCHASE PETRO-CANADA RED DEER ABCA", "amount": 65.95},
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
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
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
    parser = argparse.ArgumentParser(description="Import Scotia July 2013 batch 3 from screenshots")
    parser.add_argument('--write', action='store_true', help='Apply inserts')
    args = parser.parse_args()

    inserted, skipped = upsert_transactions(write=args.write)
    mode = 'WRITE' if args.write else 'DRY-RUN'
    print(f"{mode}: prepared {inserted} inserts, skipped {skipped} duplicates for account {ACCOUNT_NUMBER}")


if __name__ == '__main__':
    main()
