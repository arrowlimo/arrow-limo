import argparse
import os
from datetime import date, timedelta

import pandas as pd
import psycopg2


DEFAULT_ACCOUNT = "903990106011"


def month_range(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def export_year(conn, account: str, year: int, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"scotia_{account}_{year}_by_month.xlsx")

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        for month in range(1, 13):
            start, end = month_range(year, month)
            df = pd.read_sql(
                """
                SELECT transaction_id, transaction_date, description,
                       debit_amount, credit_amount, balance
                FROM banking_transactions
                WHERE account_number = %(account)s
                  AND transaction_date >= %(start)s
                  AND transaction_date < %(end)s
                ORDER BY transaction_date ASC, transaction_id ASC
                """,
                conn,
                params={"account": account, "start": start, "end": end},
            )

            # Ensure sheet exists even if month has no rows.
            if df.empty:
                df = pd.DataFrame(
                    columns=[
                        "transaction_id",
                        "transaction_date",
                        "description",
                        "debit_amount",
                        "credit_amount",
                        "balance",
                    ]
                )

            df.to_excel(writer, sheet_name=f"{month:02d}", index=False)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Export banking transactions by month to Excel workbooks."
    )
    parser.add_argument(
        "--account", default=DEFAULT_ACCOUNT, help="Bank account number to export."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2012, 2013, 2014],
        help="Years to export (e.g., --years 2012 2013 2014).",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory to place generated Excel files.",
    )
    parser.add_argument(
        "--db-host", default="localhost", help="Database host (default: localhost)."
    )
    parser.add_argument(
        "--db-name", default="almsdata", help="Database name (default: almsdata)."
    )
    parser.add_argument(
        "--db-user", default="postgres", help="Database user (default: postgres)."
    )
    parser.add_argument(
        "--db-password", default="***REDACTED***", help="Database password."
    )
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=args.db_host,
        database=args.db_name,
        user=args.db_user,
        password=args.db_password,
    )

    try:
        outputs = []
        for year in args.years:
            path = export_year(conn, args.account, year, args.output_dir)
            outputs.append(path)
            print(f"Exported {year} to {path}")
    finally:
        conn.close()

    print("Done. Generated files:")
    for p in outputs:
        print(f"  {p}")


if __name__ == "__main__":
    main()
