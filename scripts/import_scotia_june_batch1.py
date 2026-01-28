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
    June 2013 batch1: capture from provided screenshots.
    Includes late May lines that appear on the June page images (05/21–05/31) and early June (06/03–06/05).
    """
    return [
        # 2013-05-21
        {"date": date(2013, 5, 21), "type": "debit", "amount": 800.00, "description": "ABM WITHDRAWAL RED DEER BRANCH RED DEER AB CHQ 183 3700381951"},
        {"date": date(2013, 5, 21), "type": "credit", "amount": 1885.65, "description": "DEPOSIT CHQ 183 3700381951"},
        {"date": date(2013, 5, 21), "type": "debit", "amount": 148.95, "description": "POINT OF SALE PURCHASE FAS GAS WESTPARK SVC # RED DEER AB"},
        {"date": date(2013, 5, 21), "type": "debit", "amount": 7.96, "description": "POINT OF SALE PURCHASE HUSKY SANDST. MKT#1232 CALGARY AB"},
        {"date": date(2013, 5, 21), "type": "debit", "amount": 48.50, "description": "POINT OF SALE PURCHASE SWISS CHALET #1152 CALGARY AB"},
        {"date": date(2013, 5, 21), "type": "debit", "amount": 200.00, "description": "POINT OF SALE PURCHASE MONEY MART #1205 RED DEER AB"},
        {"date": date(2013, 5, 21), "type": "credit", "amount": 885.65, "description": "DEPOSIT CHQ 184 3700059239"},
        {"date": date(2013, 5, 21), "type": "credit", "amount": 500.00, "description": "PC BILL PAYMENT CAPITAL ONE MASTERCARD 67952237"},

        # 2013-05-23
        {"date": date(2013, 5, 23), "type": "debit", "amount": 75.60, "description": "POINT OF SALE PURCHASE BUCK OR TWO #235 RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "debit", "amount": 390.32, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "debit", "amount": 16.14, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "debit", "amount": 81.22, "description": "POINT OF SALE PURCHASE REAL CDN. WHOLESALE CL RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "debit", "amount": 176.92, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "debit", "amount": 182.39, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "debit", "amount": 172.42, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 5, 23), "type": "credit", "amount": 470.50, "description": "DEPOSIT"},

        # 2013-05-24
        {"date": date(2013, 5, 24), "type": "credit", "amount": 726.29, "description": "AUTO INSURANCE JEVCO INSURANCE COMPANY"},

        # 2013-05-27
        {"date": date(2013, 5, 27), "type": "debit", "amount": 2525.25, "description": "AUTO LEASE"},

        # 2013-05-29
        {"date": date(2013, 5, 29), "type": "debit", "amount": 168.42, "description": "POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER AB"},
        {"date": date(2013, 5, 29), "type": "debit", "amount": 75.00, "description": "POINT OF SALE PURCHASE SYLVAN ELECTRONIC SERV RED DEER AB"},
        {"date": date(2013, 5, 29), "type": "credit", "amount": 148.31, "description": "DEPOSIT CUSTOM CHEQUES GST/HST $007.06 D+H"},
        {"date": date(2013, 5, 29), "type": "credit", "amount": 550.00, "description": "DEPOSIT CHQ 186 3700084481"},
        {"date": date(2013, 5, 29), "type": "debit", "amount": 139.37, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},
        {"date": date(2013, 5, 29), "type": "debit", "amount": 71.05, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 5, 29), "type": "debit", "amount": 112.50, "description": "SERVICE CHARGE"},
        {"date": date(2013, 5, 29), "type": "debit", "amount": 0.85, "description": "OVERDRAFT INTEREST CHG"},

        # 2013-05-31
        {"date": date(2013, 5, 31), "type": "credit", "amount": 182.51, "description": "DEPOSIT"},
        {"date": date(2013, 5, 31), "type": "credit", "amount": 750.00, "description": "DEPOSIT"},
        {"date": date(2013, 5, 31), "type": "credit", "amount": 642.78, "description": "DEPOSIT"},
        {"date": date(2013, 5, 31), "type": "credit", "amount": 305.00, "description": "DEPOSIT"},
        {"date": date(2013, 5, 31), "type": "credit", "amount": 731.15, "description": "DEPOSIT"},
        {"date": date(2013, 5, 31), "type": "credit", "amount": 507.50, "description": "DEPOSIT"},

        # 2013-06-03
        {"date": date(2013, 6, 3), "type": "debit", "amount": 1000.00, "description": "ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB"},
        {"date": date(2013, 6, 3), "type": "debit", "amount": 200.00, "description": "ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB"},
        {"date": date(2013, 6, 3), "type": "debit", "amount": 2695.40, "description": "RENT/LEASES ACE TRUCK RENTALS LTD."},
        {"date": date(2013, 6, 3), "type": "debit", "amount": 889.87, "description": "AUTO LEASE"},
        {"date": date(2013, 6, 3), "type": "debit", "amount": 471.98, "description": "AUTO LEASE HEFFNER AUTO FC"},
        {"date": date(2013, 6, 3), "type": "credit", "amount": 400.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 3), "type": "debit", "amount": 72.23, "description": "POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER AB"},
        {"date": date(2013, 6, 3), "type": "debit", "amount": 119.87, "description": "POINT OF SALE PURCHASE RUN'N ON EMPTY 50AVQPE RED DEER AB"},

        # 2013-06-04
        {"date": date(2013, 6, 4), "type": "credit", "amount": 380.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 4), "type": "credit", "amount": 406.00, "description": "DEPOSIT"},
        {"date": date(2013, 6, 4), "type": "credit", "amount": 463.52, "description": "DEPOSIT"},
        {"date": date(2013, 6, 4), "type": "credit", "amount": 335.46, "description": "DEPOSIT"},
        {"date": date(2013, 6, 4), "type": "credit", "amount": 67.50, "description": "DEPOSIT"},
        {"date": date(2013, 6, 4), "type": "credit", "amount": 1675.00, "description": "DEPOSIT"},

        # 2013-06-05
        {"date": date(2013, 6, 5), "type": "credit", "amount": 745.77, "description": "DEPOSIT CHQ 193 3700484553"},
        {"date": date(2013, 6, 5), "type": "credit", "amount": 1960.26, "description": "DEPOSIT CHQ 191 3900424013"},
        {"date": date(2013, 6, 5), "type": "debit", "amount": 81.88, "description": "POINT OF SALE PURCHASE HMV #723 RED DEER AB"},
        {"date": date(2013, 6, 5), "type": "debit", "amount": 31.01, "description": "POINT OF SALE PURCHASE CINEPLEX #3132 QPS RED DEER AB"},
        {"date": date(2013, 6, 5), "type": "debit", "amount": 74.00, "description": "POINT OF SALE PURCHASE MOHAWK RED DEER #4320 RED DEER AB"},
        {"date": date(2013, 6, 5), "type": "debit", "amount": 15.00, "description": "OVERDRAWN HANDLING CHGS"},
        {"date": date(2013, 6, 5), "type": "credit", "amount": 500.00, "description": "DEPOSIT CHQ 192 3700544602"},
        {"date": date(2013, 6, 5), "type": "credit", "amount": 500.00, "description": "DEPOSIT"},
    ]


def main():
    parser = argparse.ArgumentParser(description="Import Scotia June 2013 (batch1) from captured transactions")
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
