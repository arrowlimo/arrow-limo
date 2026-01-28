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
    June 2013 batch2: 06/07-06/21 entries from screenshots.
    """
    return [
        # 2013-06-07
        {"date": date(2013, 6, 7), "type": "debit", "amount": 58.01, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 50.00, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 117.3, "description": "POINT OF SALE PURCHASE CENTEX DEERPARK (C-STOR RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 595.63, "description": "DEPOSIT"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 500.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 2690.46, "description": "DEPOSIT"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 3085.75, "description": "DEPOSIT"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 207.50, "description": "DEPOSIT"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 520.88, "description": "DEPOSIT CHQ 184 3700167676"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 500.00, "description": "DEPOSIT CHQ 187 7800168772"},
        {"date": date(2013, 6, 7), "type": "credit", "amount": 157.30, "description": "DEPOSIT"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 93.60, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 110.96, "description": "POINT OF SALE PURCHASE CANADA SAFEWAY #813 RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 74.90, "description": "POINT OF SALE PURCHASE CENTEX DEERPARK (C-STOR RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 27.35, "description": "POINT OF SALE PURCHASE RED DEER CO-OP QPE RED DEER AB"},
        {"date": date(2013, 6, 7), "type": "debit", "amount": 40.00, "description": "POINT OF SALE PURCHASE VILLAGE CHIROPRACTIC"},

        # 2013-06-10
        {"date": date(2013, 6, 10), "type": "debit", "amount": 674.26, "description": "POINT OF SALE PURCHASE MONEY MART #1205 RED DEER AB"},
        {"date": date(2013, 6, 10), "type": "debit", "amount": 30.00, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 10), "type": "debit", "amount": 104.67, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 6, 10), "type": "debit", "amount": 2932.18, "description": "PC BILL PAYMENT TELUS COMMUNICATIONS 07066735"},
        {"date": date(2013, 6, 10), "type": "credit", "amount": 587.50, "description": "DEPOSIT"},
        {"date": date(2013, 6, 10), "type": "credit", "amount": 583.00, "description": "DEPOSIT"},

        # 2013-06-11
        {"date": date(2013, 6, 11), "type": "credit", "amount": 1351.99, "description": "DEPOSIT CHQ 196 3700214513"},
        {"date": date(2013, 6, 11), "type": "credit", "amount": 1575.00, "description": "DEPOSIT CHQ 195 3700279538"},
        {"date": date(2013, 6, 11), "type": "credit", "amount": 175.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 11), "type": "credit", "amount": 786.00, "description": "DEPOSIT"},

        # 2013-06-12
        {"date": date(2013, 6, 12), "type": "debit", "amount": 1000.00, "description": "PC BILL PAYMENT CHQ 199 3700143849"},
        {"date": date(2013, 6, 12), "type": "debit", "amount": 221.01, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 12), "type": "credit", "amount": 1397.00, "description": "DEPOSIT"},

        # 2013-06-13
        {"date": date(2013, 6, 13), "type": "credit", "amount": 500.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 13), "type": "credit", "amount": 288.74, "description": "DEPOSIT"},
        {"date": date(2013, 6, 13), "type": "credit", "amount": 470.60, "description": "MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA"},

        # 2013-06-17
        {"date": date(2013, 6, 17), "type": "credit", "amount": 205.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 17), "type": "credit", "amount": 1795.00, "description": "DEPOSIT"},

        # 2013-06-18
        {"date": date(2013, 6, 18), "type": "debit", "amount": 2963.51, "description": "RETURNED NSF CHEQUE"},
        {"date": date(2013, 6, 18), "type": "credit", "amount": 108.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 18), "type": "credit", "amount": 437.50, "description": "DEPOSIT"},
        {"date": date(2013, 6, 18), "type": "credit", "amount": 192.50, "description": "DEPOSIT"},

        # 2013-06-19
        {"date": date(2013, 6, 19), "type": "debit", "amount": 42.50, "description": "SERVICE CHARGE"},
        {"date": date(2013, 6, 19), "type": "credit", "amount": 697.06, "description": "DEPOSIT"},
        {"date": date(2013, 6, 19), "type": "credit", "amount": 115.50, "description": "DEPOSIT"},

        # 2013-06-20
        {"date": date(2013, 6, 20), "type": "debit", "amount": 100.00, "description": "ABM WITHDRAWAL AT SHELL"},
        {"date": date(2013, 6, 20), "type": "debit", "amount": 55.06, "description": "POINT OF SALE PURCHASE CO0319 MOUNT ROYAL SHE CALGARY AB"},
        {"date": date(2013, 6, 20), "type": "credit", "amount": 1700.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 20), "type": "credit", "amount": 205.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 20), "type": "credit", "amount": 500.00, "description": "DEPOSIT CHQ 188 3000253025"},
        {"date": date(2013, 6, 20), "type": "debit", "amount": 46.51, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 20), "type": "debit", "amount": 241.64, "description": "POINT OF SALE PURCHASE STAPLES#285 RED DEER AB"},
        {"date": date(2013, 6, 20), "type": "debit", "amount": 11.50, "description": "POINT OF SALE PURCHASE TENSHI SUSHI INFERAC RED DEER AB"},
        {"date": date(2013, 6, 20), "type": "debit", "amount": 51.34, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},

        # 2013-06-21
        {"date": date(2013, 6, 21), "type": "debit", "amount": 100.01, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 6, 21), "type": "credit", "amount": 407.76, "description": "DEPOSIT"},
        {"date": date(2013, 6, 21), "type": "credit", "amount": 287.25, "description": "DEPOSIT"},
        {"date": date(2013, 6, 21), "type": "credit", "amount": 1777.88, "description": "DEPOSIT"},
        {"date": date(2013, 6, 21), "type": "credit", "amount": 82.69, "description": "DEPOSIT"},
        {"date": date(2013, 6, 21), "type": "credit", "amount": 1250.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 21), "type": "credit", "amount": 559.70, "description": "MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 726.29, "description": "AUTO INSURANCE JEVCO INSURANCE COMPANY INSURANCE"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 2383.24, "description": "IPS PREMIUM FIN CHQ 203 5000464420"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 209.504, "description": "POINT OF SALE PURCHASE FAS GAS LAKEVIEW SVC # SYLVAN LAKE AB"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 154.79, "description": "POINT OF SALE PURCHASE HUSKY DOWNTOWN #6795 RED DEER AB"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 156.75, "description": "POINT OF SALE PURCHASE UPTOWN LIQUOR STORE RED DEER AB"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 420.00, "description": "POINT OF SALE PURCHASE WINDSFIELD SURGEONS RED DEER AB"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 45.14, "description": "POINT OF SALE PURCHASE PET PLANET - RED DEER RED DEER AB"},
        {"date": date(2013, 6, 21), "type": "debit", "amount": 150.02, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
    ]


def main():
    parser = argparse.ArgumentParser(description="Import Scotia June 2013 (batch2) from captured transactions")
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
