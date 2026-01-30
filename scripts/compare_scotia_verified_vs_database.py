"""
Compare verified Scotia 2012 statement transactions against database.
These are user-provided verified transactions from actual statements.
Database will be checked for corruption/missing/mismatched data.
"""
import psycopg2
from datetime import datetime
from decimal import Decimal


def parse_date(date_str):
    """Parse various date formats."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            pass
    return None


def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )
    cur = conn.cursor()

    # Verified transactions from user statement
    verified_txns = [
        {"date": "2012-01-01", "desc": "General Journal", "debit": 0, "credit": 0, "balance": 40},
        {"date": "2012-02-22", "desc": "deposit", "debit": 0, "credit": 100, "balance": 140},
        {"date": "2012-02-23", "desc": "deposit", "debit": 0, "credit": 5320, "balance": None},
        {"date": "2012-02-23", "desc": "withdrawl draft", "debit": 5250, "credit": 550, "balance": None},
        {"date": "2012-02-23", "desc": "draft purchase", "debit": 6.5, "credit": 0, "balance": None},
        {"date": "2012-02-29", "desc": "service charges", "debit": 112.5, "credit": 55.1, "balance": 91},
        {"date": "2012-04-02", "desc": "mall Business Assistance Program fee", "debit": 91, "credit": 0, "balance": 0},
        {"date": "2012-04-09", "desc": "deposit", "debit": 0, "credit": 200, "balance": 200},
        {"date": "2012-04-10", "desc": "small business assistance program fee", "debit": 21.5, "credit": 0, "balance": None},
        {"date": "2012-04-19", "desc": "deposit", "debit": 0, "credit": 200, "balance": None},
        {"date": "2012-04-30", "desc": "service charge", "debit": 112.5, "credit": 0, "balance": 266},
        {"date": "2012-05-18", "desc": "georges pizza and steak", "debit": 84.23, "credit": 0, "balance": 181.77},
        {"date": "2012-05-28", "desc": "deposit", "debit": 0, "credit": 10000, "balance": None},
        {"date": "2012-05-31", "desc": "service charge", "debit": 112.5, "credit": 0, "balance": None},
        {"date": "2012-06-15", "desc": "transfer funds", "debit": 300, "credit": 0, "balance": None},
        {"date": "2012-06-20", "desc": "deposit", "debit": 0, "credit": 770, "balance": None},
        {"date": "2012-06-20", "desc": "money order", "debit": 750, "credit": 0, "balance": None},
        {"date": "2012-06-20", "desc": "money order fee", "debit": 7.5, "credit": 0, "balance": None},
        {"date": "2012-06-21", "desc": "mcard deposit", "debit": 0, "credit": 460, "balance": None},
        {"date": "2012-06-22", "desc": "dcard deposit", "debit": 0, "credit": 175, "balance": None},
        {"date": "2012-06-22", "desc": "vcard deposit", "debit": 0, "credit": 205, "balance": None},
        {"date": "2012-06-22", "desc": "mcard deposit", "debit": 0, "credit": 455, "balance": None},
        {"date": "2012-06-22", "desc": "witdrawal", "debit": 400, "credit": 0, "balance": None},
        {"date": "2012-06-22", "desc": "mohawk", "debit": 41, "credit": 0, "balance": None},
        {"date": "2012-06-22", "desc": "centex", "debit": 61.01, "credit": 0, "balance": 156.76},
        {"date": "2012-06-25", "desc": "mcard deposit", "debit": 0, "credit": 1133, "balance": None},
        {"date": "2012-06-25", "desc": "mcard deposit", "debit": 0, "credit": 402.25, "balance": None},
        {"date": "2012-06-25", "desc": "vcard deposit", "debit": 0, "credit": 187.5, "balance": None},
        {"date": "2012-06-25", "desc": "mcard deposit", "debit": 0, "credit": 2525, "balance": 5317.51},
        {"date": "2012-06-25", "desc": "best buy", "debit": 38.84, "credit": 0, "balance": None},
        {"date": "2012-06-25", "desc": "mohawk", "debit": 34.1, "credit": 0, "balance": None},
        {"date": "2012-06-25", "desc": "centex", "debit": 56.5, "credit": 0, "balance": None},
        {"date": "2012-06-25", "desc": "liquor barn", "debit": 25.89, "credit": 0, "balance": None},
        {"date": "2012-06-25", "desc": "Plenty of liquor", "debit": 20.42, "credit": 0, "balance": None},
        {"date": "2012-06-25", "desc": "centex", "debit": 328.12, "credit": 0, "balance": None},
        {"date": "2012-06-26", "desc": "mcard deposit", "debit": 0, "credit": 175, "balance": None},
        {"date": "2012-06-26", "desc": "amex deposit", "debit": 0, "credit": 241.25, "balance": None},
        {"date": "2012-06-27", "desc": "centex", "debit": 57, "credit": 0, "balance": None},
        {"date": "2012-06-28", "desc": "mcard deposit", "debit": 0, "credit": 540, "balance": None},
        {"date": "2012-06-28", "desc": "vcard deposit", "debit": 0, "credit": 1095.5, "balance": None},
        {"date": "2012-06-29", "desc": "cash withdrawal", "debit": 2500, "credit": 0, "balance": None},
        {"date": "2012-06-29", "desc": "service charge", "debit": 112.5, "credit": 0, "balance": 4195.89},
        {"date": "2012-07-03", "desc": "mcard deposit", "debit": 0, "credit": 245, "balance": None},
        {"date": "2012-07-03", "desc": "vcard deposit", "debit": 0, "credit": 410, "balance": None},
        {"date": "2012-07-03", "desc": "vcard deposit", "debit": 0, "credit": 1211.25, "balance": None},
        {"date": "2012-07-03", "desc": "vcard deposit", "debit": 0, "credit": 567, "balance": None},
        {"date": "2012-07-03", "desc": "mcard deposit", "debit": 0, "credit": 258, "balance": None},
        {"date": "2012-07-03", "desc": "dcard deposit", "debit": 0, "credit": 270, "balance": None},
        {"date": "2012-07-03", "desc": "vcard withdrawal", "debit": 480.47, "credit": 0, "balance": None},
        {"date": "2012-07-03", "desc": "mcard fee", "debit": 120.43, "credit": 0, "balance": None},
        {"date": "2012-07-04", "desc": "mcard deposit", "debit": 0, "credit": 957.5, "balance": None},
        {"date": "2012-07-04", "desc": "cash withdrawal", "debit": 7000, "credit": 0, "balance": None},
        {"date": "2012-07-05", "desc": "mcard deposit", "debit": 0, "credit": 205, "balance": None},
        {"date": "2012-07-06", "desc": "mcard deposit", "debit": 0, "credit": 1743.5, "balance": None},
        {
            "date": "2012-07-06",
            "desc": "paper cheques ordered 6.62 gst",
            "debit": 138.96,
            "credit": 0,
            "balance": 2323.28,
        },
        {"date": "2012-07-09", "desc": "vcard deposit", "debit": 0, "credit": 178.18, "balance": None},
        {"date": "2012-07-09", "desc": "vcard deposit", "debit": 0, "credit": 869.75, "balance": None},
        {"date": "2012-07-09", "desc": "dcard deposit", "debit": 0, "credit": 660.1, "balance": None},
        {"date": "2012-07-09", "desc": "vcard deposit", "debit": 0, "credit": 654.79, "balance": None},
        {"date": "2012-07-09", "desc": "cheque #1", "debit": 1870.14, "credit": 0, "balance": None},
        {"date": "2012-07-09", "desc": "mohawk", "debit": 52.65, "credit": 0, "balance": None},
        {"date": "2012-07-09", "desc": "centratech tech services", "debit": 79.39, "credit": 0, "balance": None},
        {"date": "2012-07-09", "desc": "mid-alta motors ltd", "debit": 300.25, "credit": 0, "balance": None},
        {"date": "2012-07-10", "desc": "vcard deposit", "debit": 0, "credit": 762.5, "balance": None},
        {"date": "2012-07-11", "desc": "mgm ford", "debit": 79.89, "credit": 0, "balance": None},
        {"date": "2012-07-11", "desc": "erles", "debit": 581.49, "credit": 0, "balance": None},
        {"date": "2012-07-12", "desc": "liquor barn", "debit": 693.85, "credit": 0, "balance": None},
        {"date": "2012-07-12", "desc": "centex", "debit": 66.5, "credit": 0, "balance": None},
        {"date": "2012-07-12", "desc": "centec", "debit": 78.04, "credit": 0, "balance": None},
        {"date": "2012-07-12", "desc": "centex", "debit": 36.01, "credit": 0, "balance": 3214.39},
    ]

    print("=" * 120)
    print("SCOTIA BANK 2012 - DATABASE VS VERIFIED STATEMENT COMPARISON")
    print("=" * 120)
    print(f"Total verified transactions from statement: {len(verified_txns)}\n")

    # Load database transactions for same period
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
          AND transaction_date BETWEEN '2012-01-01' AND '2012-07-12'
        ORDER BY transaction_date ASC, transaction_id ASC
    """
    )

    db_txns = cur.fetchall()
    print(f"Total database transactions for period: {len(db_txns)}\n")

    # Compare
    print("=" * 120)
    print("COMPARISON RESULTS")
    print("=" * 120)

    # Check for balance matches (most reliable)
    balance_checks = [t for t in verified_txns if t.get("balance") is not None]
    print(f"\n✓ Verified transactions with balance stamps: {len(balance_checks)}")
    for t in balance_checks:
        print(f"  {t['date']}: Balance should be ${t['balance']}")

    # Sample database balances at those dates
    print("\n✓ Database balances at same dates:")
    for t in balance_checks:
        cur.execute(
            """
            SELECT balance FROM banking_transactions
            WHERE account_number = '903990106011'
              AND transaction_date = %s
            ORDER BY transaction_id DESC LIMIT 1
        """,
            (t["date"],),
        )
        result = cur.fetchone()
        if result:
            db_balance = result[0]
            verified_balance = Decimal(str(t["balance"]))
            match = "✓" if db_balance == verified_balance else "✗"
            print(
                f"  {match} {t['date']}: DB=${db_balance}, Verified=${verified_balance} (diff=${abs(float(db_balance or 0) - float(verified_balance))})"
            )
        else:
            print(f"  ✗ {t['date']}: NO DATABASE RECORD")

    # Check transaction counts by month
    print("\n" + "=" * 120)
    print("TRANSACTION COUNT BY MONTH")
    print("=" * 120)
    from collections import defaultdict

    verified_by_month = defaultdict(int)
    db_by_month = defaultdict(int)

    for t in verified_txns:
        month = t["date"][:7]  # YYYY-MM
        verified_by_month[month] += 1

    for txn in db_txns:
        month = str(txn[1])[:7]
        db_by_month[month] += 1

    for month in sorted(verified_by_month.keys()):
        v_count = verified_by_month.get(month, 0)
        d_count = db_by_month.get(month, 0)
        match = "✓" if v_count == d_count else "✗"
        print(f"  {match} {month}: Verified={v_count:>3}, Database={d_count:>3}, Diff={v_count - d_count:>+3}")

    # Critical dates comparison
    print("\n" + "=" * 120)
    print("CRITICAL BALANCE POINTS")
    print("=" * 120)
    critical = [
        ("2012-01-01", 40, "Opening balance"),
        ("2012-02-29", 91, "February close"),
        ("2012-04-30", 266, "April close"),
        ("2012-05-18", 181.77, "Mid-May"),
        ("2012-06-22", 156.76, "Late June (many card deposits)"),
        ("2012-06-25", 5317.51, "June 25 (multiple card deposits)"),
        ("2012-06-29", 4195.89, "End June"),
        ("2012-07-06", 2323.28, "Paper cheques"),
        ("2012-07-12", 3214.39, "July 12 close"),
    ]

    print()
    for date_str, expected_balance, note in critical:
        cur.execute(
            """
            SELECT balance FROM banking_transactions
            WHERE account_number = '903990106011'
              AND transaction_date = %s
            ORDER BY transaction_id DESC LIMIT 1
        """,
            (date_str,),
        )
        result = cur.fetchone()
        if result:
            db_balance = float(result[0])
            expected = float(expected_balance)
            match = "✓" if abs(db_balance - expected) < 0.01 else "✗"
            print(
                f"  {match} {date_str:12} | {note:30} | DB: ${db_balance:>10.2f} | Expected: ${expected:>10.2f} | Diff: ${abs(db_balance - expected):>10.2f}"
            )
        else:
            print(f"  ✗ {date_str:12} | {note:30} | NO DATABASE RECORD")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
