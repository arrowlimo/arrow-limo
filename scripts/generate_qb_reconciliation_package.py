import os
import csv
import sys
import math
import psycopg2
from datetime import date, datetime, timedelta


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


def write_csv(path, rows, header=None):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        for r in rows:
            w.writerow(r)


def write_text(path, content):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def generate_month_package(conn, account, year, month, out_dir):
    cur = conn.cursor()

    cols = get_columns(cur, "banking_transactions")
    col_acc = pick(["account_number", "account", "acct"], cols) or "account_number"
    col_date = pick(["transaction_date", "date", "posted_date"], cols) or "transaction_date"
    col_desc = pick(["description", "vendor_name", "memo"], cols) or "description"
    col_debit = pick(["debit_amount", "debit", "amount_out"], cols) or "debit_amount"
    col_credit = pick(["credit_amount", "credit", "amount_in"], cols) or "credit_amount"
    col_bal = pick(["balance", "running_balance"], cols) or "balance"
    col_id = pick(["transaction_id", "id"], cols) or "transaction_id"

    start, end = month_bounds(year, month)

    # Beginning balance = last balance before start
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

    # Debits/Credits within month
    cur.execute(
        f"""
        SELECT
          COUNT(CASE WHEN COALESCE({col_debit},0) > 0 THEN 1 END) AS debit_count,
          COALESCE(SUM(CASE WHEN COALESCE({col_debit},0) > 0 THEN {col_debit} ELSE 0 END),0) AS debit_total,
          COUNT(CASE WHEN COALESCE({col_credit},0) > 0 THEN 1 END) AS credit_count,
          COALESCE(SUM(CASE WHEN COALESCE({col_credit},0) > 0 THEN {col_credit} ELSE 0 END),0) AS credit_total
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

    # Ending balance = last balance on/before end, fallback to cleared_balance
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

    # Lists
    cur.execute(
        f"""
        SELECT {col_date}, {col_desc}, {col_debit}, {col_bal}
        FROM banking_transactions
        WHERE {col_acc}=%s AND {col_date} >= %s AND {col_date} <= %s AND COALESCE({col_debit},0) > 0
        ORDER BY {col_date}, {col_id}
        """,
        [account, start, end],
    )
    debits = cur.fetchall()

    cur.execute(
        f"""
        SELECT {col_date}, {col_desc}, {col_credit}, {col_bal}
        FROM banking_transactions
        WHERE {col_acc}=%s AND {col_date} >= %s AND {col_date} <= %s AND COALESCE({col_credit},0) > 0
        ORDER BY {col_date}, {col_id}
        """,
        [account, start, end],
    )
    credits = cur.fetchall()

    cur.execute(
        f"""
        SELECT {col_date}, {col_desc}, COALESCE({col_debit},0), COALESCE({col_credit},0), {col_bal}
        FROM banking_transactions
        WHERE {col_acc}=%s AND {col_date} >= %s AND {col_date} <= %s
        ORDER BY {col_date}, {col_id}
        """,
        [account, start, end],
    )
    register = cur.fetchall()

    # Write outputs
    month_dir = os.path.join(out_dir, f"{year}-{month:02d}")
    ensure_dir(month_dir)

    # Summary (Markdown)
    summary_md = []
    summary_md.append("# Reconciliation Summary")
    summary_md.append("")
    summary_md.append(f"Account: {account}")
    summary_md.append(f"Period Ending: {end.isoformat()}")
    summary_md.append("")
    summary_md.append("## Balances")
    summary_md.append("")
    summary_md.append(f"- Beginning Balance: {fmt_money(beginning_balance)}")
    summary_md.append(f"- Cleared Transactions Net: {fmt_money(net_cleared)}")
    summary_md.append(f"- Cleared Balance: {fmt_money(cleared_balance)}")
    summary_md.append(f"- Ending Balance: {fmt_money(ending_balance)}")
    summary_md.append("")
    summary_md.append("## Cleared Transactions")
    summary_md.append("")
    summary_md.append(f"- Cheques and Payments: {dcount} items, total {fmt_money(dtotal)}")
    summary_md.append(f"- Deposits and Credits: {ccount} items, total {fmt_money(ctotal)}")
    summary_md.append("")
    summary_md.append("Notes: In this package, transactions dated within the month are treated as 'cleared' for comparison to printed QB packages.")
    summary_md.append("")

    write_text(os.path.join(month_dir, f"reconciliation_summary_{year}-{month:02d}.md"), "\n".join(summary_md))

    # CSVs
    write_csv(
        os.path.join(month_dir, f"cheques_and_payments_{year}-{month:02d}.csv"),
        [(r[0], r[1], f"{float(r[2] or 0):.2f}", f"{float(r[3] or 0):.2f}" if r[3] is not None else "") for r in debits],
        header=["date", "description", "debit", "balance"],
    )
    write_csv(
        os.path.join(month_dir, f"deposits_and_credits_{year}-{month:02d}.csv"),
        [(r[0], r[1], f"{float(r[2] or 0):.2f}", f"{float(r[3] or 0):.2f}" if r[3] is not None else "") for r in credits],
        header=["date", "description", "credit", "balance"],
    )
    write_csv(
        os.path.join(month_dir, f"register_{year}-{month:02d}.csv"),
        [
            (
                r[0],
                r[1],
                f"{float(r[2] or 0):.2f}",
                f"{float(r[3] or 0):.2f}",
                f"{float(r[4] or 0):.2f}" if r[4] is not None else "",
            )
            for r in register
        ],
        header=["date", "description", "debit", "credit", "balance"],
    )

    return {
        "period_end": end,
        "beginning_balance": beginning_balance,
        "debit_count": dcount,
        "debit_total": dtotal,
        "credit_count": ccount,
        "credit_total": ctotal,
        "net_cleared": net_cleared,
        "cleared_balance": cleared_balance,
        "ending_balance": ending_balance,
    }


def generate_year_index(out_dir, account, year, summaries):
    lines = []
    lines.append("# Reconciliation Package Index")
    lines.append("")
    lines.append(f"Account: {account}")
    lines.append(f"Year: {year}")
    lines.append("")
    lines.append("Month | Beginning | Debits | Credits | Net | Ending")
    lines.append("---|---:|---:|---:|---:|---:")
    for m in range(1, 13):
        s = summaries.get(m)
        if not s:
            continue
        lines.append(
            f"{year}-{m:02d} | {fmt_money(s['beginning_balance'])} | {fmt_money(s['debit_total'])} | {fmt_money(s['credit_total'])} | {fmt_money(s['net_cleared'])} | {fmt_money(s['ending_balance'])}"
        )
    write_text(os.path.join(out_dir, f"reconciliation_index_{year}.md"), "\n".join(lines))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate QuickBooks-style reconciliation packages (monthly)")
    parser.add_argument("--account", required=True, help="Account number to process")
    parser.add_argument("--year", type=int, required=True, help="Year to process")
    parser.add_argument("--out", default=None, help="Output base directory (default: exports/reconciliation/<account>/<year>)")
    args = parser.parse_args()

    account = args.account
    year = args.year
    base_out = args.out or os.path.join("exports", "reconciliation", account, str(year))
    ensure_dir(base_out)

    conn = get_db_connection()
    try:
        monthly_summaries = {}
        for m in range(1, 13):
            summary = generate_month_package(conn, account, year, m, base_out)
            monthly_summaries[m] = summary
        generate_year_index(base_out, account, year, monthly_summaries)

        print(f"\n[OK] Reconciliation packages written to: {base_out}")
        print("Contents per month:")
        print(" - reconciliation_summary_YYYY-MM.md")
        print(" - cheques_and_payments_YYYY-MM.csv")
        print(" - deposits_and_credits_YYYY-MM.csv")
        print(" - register_YYYY-MM.csv")
        print("And an annual index: reconciliation_index_YEAR.md")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
