import os
import psycopg2
from datetime import date, timedelta


def env(name, default=None):
    return os.environ.get(name, default)


def get_db_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        dbname=env("DB_NAME", "almsdata"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "***REMOVED***"),
    )


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def month_bounds(y, m):
    start = date(y, m, 1)
    if m == 12:
        end = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(y, m + 1, 1) - timedelta(days=1)
    return start, end


def get_columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def pick(candidates, available):
    for c in candidates:
        if c in available:
            return c
    return None


def fmt_money(val):
    try:
        return f"${float(val):,.2f}"
    except Exception:
        return "$0.00"


def summary_text(account, period_end, beginning_balance, dcount, dtotal, ccount, ctotal, net_cleared, cleared_balance, ending_balance):
    lines = []
    lines.append(f"Account {account} - Period Ending {period_end:%Y-%m-%d}")
    lines.append("=" * 53)
    lines.append("")
    lines.append("Beginning Balance".ljust(46) + fmt_money(beginning_balance).rjust(7))
    lines.append("")
    lines.append("Cleared Transactions")
    lines.append("  Cheques and Payments - {:>3} items {}".format(dcount or 0, fmt_money(dtotal).rjust(20)))
    lines.append("  Deposits and Credits  - {:>3} items {}".format(ccount or 0, fmt_money(ctotal).rjust(20)))
    lines.append("  Total Cleared Transactions".ljust(46) + fmt_money(net_cleared).rjust(7))
    lines.append("")
    lines.append("Cleared Balance".ljust(46) + fmt_money(cleared_balance).rjust(7))
    lines.append("")
    lines.append("Register Balance as of {:}".format(period_end.strftime("%Y-%m-%d")).ljust(46) + fmt_money(ending_balance).rjust(7))
    lines.append("")
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate QB-style monthly summary text files")
    parser.add_argument("--account", required=True)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    account = args.account
    year = args.year

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cols = get_columns(cur, "banking_transactions")
        col_acc = pick(["account_number", "account", "acct"], cols) or "account_number"
        col_date = pick(["transaction_date", "date", "posted_date"], cols) or "transaction_date"
        col_debit = pick(["debit_amount", "debit", "amount_out"], cols) or "debit_amount"
        col_credit = pick(["credit_amount", "credit", "amount_in"], cols) or "credit_amount"
        col_bal = pick(["balance", "running_balance"], cols) or "balance"
        col_id = pick(["transaction_id", "id"], cols) or "transaction_id"

        base_out = os.path.join("exports", "reconciliation", account, str(year))
        ensure_dir(base_out)

        for m in range(1, 12 + 1):
            start, end = month_bounds(year, m)

            # Beginning
            cur.execute(
                f"""
                SELECT {col_bal}
                FROM banking_transactions
                WHERE {col_acc}=%s AND {col_date} < %s
                ORDER BY {col_date} DESC, {col_id} DESC
                LIMIT 1
                """,
                [account, start],
            )
            row = cur.fetchone()
            beginning_balance = float(row[0]) if row and row[0] is not None else 0.0

            # Totals
            cur.execute(
                f"""
                SELECT
                  COUNT(CASE WHEN COALESCE({col_debit},0) > 0 THEN 1 END),
                  COALESCE(SUM(CASE WHEN COALESCE({col_debit},0) > 0 THEN {col_debit} ELSE 0 END),0),
                  COUNT(CASE WHEN COALESCE({col_credit},0) > 0 THEN 1 END),
                  COALESCE(SUM(CASE WHEN COALESCE({col_credit},0) > 0 THEN {col_credit} ELSE 0 END),0)
                FROM banking_transactions
                WHERE {col_acc}=%s AND {col_date} >= %s AND {col_date} <= %s
                """,
                [account, start, end],
            )
            dcount, dtotal, ccount, ctotal = cur.fetchone()
            dtotal = float(dtotal or 0)
            ctotal = float(ctotal or 0)
            net_cleared = ctotal - dtotal
            cleared_balance = beginning_balance + net_cleared

            # Ending
            cur.execute(
                f"""
                SELECT {col_bal}
                FROM banking_transactions
                WHERE {col_acc}=%s AND {col_date} <= %s
                ORDER BY {col_date} DESC, {col_id} DESC
                LIMIT 1
                """,
                [account, end],
            )
            row = cur.fetchone()
            ending_balance = float(row[0]) if row and row[0] is not None else cleared_balance

            # Write .txt
            month_dir = os.path.join(base_out, f"{year}-{m:02d}")
            ensure_dir(month_dir)
            path = os.path.join(month_dir, f"reconciliation_summary_{year}-{m:02d}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    summary_text(
                        account,
                        end,
                        beginning_balance,
                        dcount,
                        dtotal,
                        ccount,
                        ctotal,
                        net_cleared,
                        cleared_balance,
                        ending_balance,
                    )
                )

        print(f"[OK] Monthly QB-style summary text files written under: {base_out}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
