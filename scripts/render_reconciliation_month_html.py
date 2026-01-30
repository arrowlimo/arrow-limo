import os
import csv
import psycopg2
from datetime import date, timedelta


def env(name, default=None):
    return os.environ.get(name, default)


def get_db_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        dbname=env("DB_NAME", "almsdata"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "***REDACTED***"),
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


def fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "$0.00"


def render_html(account, year, month, balances, debits, credits, register):
    end = balances['period_end']
    css = """
    <style>
    body { font-family: Segoe UI, Arial, sans-serif; color: #111; }
    h1, h2 { margin: 0.2rem 0; }
    .section { margin: 1rem 0; }
    .kv { display: grid; grid-template-columns: 260px 1fr; row-gap: 6px; }
    .kv div { padding: 2px 0; }
    table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
    th, td { border: 1px solid #ccc; padding: 6px 8px; font-size: 12px; }
    th { background: #f6f6f6; text-align: left; }
    .right { text-align: right; }
    .muted { color: #555; }
    .small { font-size: 12px; }
    hr { border: 0; border-top: 1px solid #ddd; margin: 1rem 0; }
    @media print { a { color: #000; text-decoration: none; } }
    </style>
    """

    def tab(title, rows, header):
        out = [f"<div class='section'><h2>{title}</h2>"]
        out.append("<table>")
        out.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in header) + "</tr></thead>")
        out.append("<tbody>")
        for r in rows:
            out.append("<tr>" + "".join(f"<td class='right'>{c}</td>" if i in (2,3,4) else f"<td>{c}</td>" for i, c in enumerate(r)) + "</tr>")
        out.append("</tbody></table></div>")
        return "\n".join(out)

    html = ["<html><head><meta charset='utf-8'><title>Reconciliation Packet</title>", css, "</head><body>"]
    html.append(f"<h1>Reconciliation Packet</h1>")
    html.append(f"<div class='muted small'>Account {account} &middot; Period Ending {end:%Y-%m-%d}</div>")
    html.append("<hr/>")

    # Summary
    html.append("<div class='section'><h2>Summary</h2><div class='kv'>")
    html.append(f"<div>Beginning Balance</div><div>{fmt_money(balances['beginning_balance'])}</div>")
    html.append(f"<div>Cheques and Payments</div><div>{balances['debit_count']} items &middot; {fmt_money(balances['debit_total'])}</div>")
    html.append(f"<div>Deposits and Credits</div><div>{balances['credit_count']} items &middot; {fmt_money(balances['credit_total'])}</div>")
    html.append(f"<div>Total Cleared Transactions</div><div>{fmt_money(balances['net_cleared'])}</div>")
    html.append(f"<div>Cleared Balance</div><div>{fmt_money(balances['cleared_balance'])}</div>")
    html.append(f"<div>Register Balance as of {end:%Y-%m-%d}</div><div>{fmt_money(balances['ending_balance'])}</div>")
    html.append("</div></div>")

    # Tables
    html.append(tab("Cheques and Payments", debits, ["Date", "Description", "Debit", "Balance"]))
    html.append(tab("Deposits and Credits", credits, ["Date", "Description", "Credit", "Balance"]))
    html.append(tab("Register", register, ["Date", "Description", "Debit", "Credit", "Balance"]))

    html.append("<div class='section small muted'>Note: Transactions dated within the period are considered 'cleared' for comparison purposes.</div>")
    html.append("</body></html>")
    return "\n".join(html)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Render a single printable HTML packet for a month")
    parser.add_argument("--account", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    account, year, month = args.account, args.year, args.month

    # We'll reconstruct the same aggregates as in the generator to avoid relying on parsing files
    conn = get_db_connection()
    try:
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
        debits = [(r[0], r[1], f"{float(r[2] or 0):,.2f}", f"{float(r[3] or 0):,.2f}" if r[3] is not None else "") for r in cur.fetchall()]

        cur.execute(
            f"""
            SELECT {col_date}, {col_desc}, {col_credit}, {col_bal}
            FROM banking_transactions
            WHERE {col_acc}=%s AND {col_date} >= %s AND {col_date} <= %s AND COALESCE({col_credit},0) > 0
            ORDER BY {col_date}, {col_id}
            """,
            [account, start, end],
        )
        credits = [(r[0], r[1], f"{float(r[2] or 0):,.2f}", f"{float(r[3] or 0):,.2f}" if r[3] is not None else "") for r in cur.fetchall()]

        cur.execute(
            f"""
            SELECT {col_date}, {col_desc}, COALESCE({col_debit},0), COALESCE({col_credit},0), {col_bal}
            FROM banking_transactions
            WHERE {col_acc}=%s AND {col_date} >= %s AND {col_date} <= %s
            ORDER BY {col_date}, {col_id}
            """,
            [account, start, end],
        )
        register = [
            (
                r[0],
                r[1],
                f"{float(r[2] or 0):,.2f}",
                f"{float(r[3] or 0):,.2f}",
                f"{float(r[4] or 0):,.2f}" if r[4] is not None else "",
            )
            for r in cur.fetchall()
        ]

        balances = {
            'period_end': end,
            'beginning_balance': beginning_balance,
            'debit_count': dcount,
            'debit_total': dtotal,
            'credit_count': ccount,
            'credit_total': ctotal,
            'net_cleared': net_cleared,
            'cleared_balance': cleared_balance,
            'ending_balance': ending_balance,
        }

        html = render_html(account, year, month, balances, debits, credits, register)
        out_dir = os.path.join("exports", "reconciliation", account, str(year), f"{year}-{month:02d}")
        ensure_dir(out_dir)
        out_path = os.path.join(out_dir, f"reconciliation_packet_{year}-{month:02d}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[OK] Wrote printable HTML: {out_path}")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
