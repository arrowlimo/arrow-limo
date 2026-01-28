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


def fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "$0.00"


def render_month_section(title, balances, debits, credits, register):
    end = balances['period_end']
    def tab(header, rows, numeric_idx):
        out = ["<table>"]
        out.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in header) + "</tr></thead>")
        out.append("<tbody>")
        for r in rows:
            tds = []
            for i, c in enumerate(r):
                cls = " class='right'" if i in numeric_idx else ""
                tds.append(f"<td{cls}>{c}</td>")
            out.append("<tr>" + "".join(tds) + "</tr>")
        out.append("</tbody></table>")
        return "\n".join(out)

    html = [f"<div class='month-section'>", f"<h2 id='{end:%Y-%m}'>" + title + "</h2>"]
    html.append("<div class='kv'>")
    html.append(f"<div>Beginning Balance</div><div>{fmt_money(balances['beginning_balance'])}</div>")
    html.append(f"<div>Cheques and Payments</div><div>{balances['debit_count']} items · {fmt_money(balances['debit_total'])}</div>")
    html.append(f"<div>Deposits and Credits</div><div>{balances['credit_count']} items · {fmt_money(balances['credit_total'])}</div>")
    html.append(f"<div>Total Cleared Transactions</div><div>{fmt_money(balances['net_cleared'])}</div>")
    html.append(f"<div>Cleared Balance</div><div>{fmt_money(balances['cleared_balance'])}</div>")
    html.append(f"<div>Register Balance as of {end:%Y-%m-%d}</div><div>{fmt_money(balances['ending_balance'])}</div>")
    html.append("</div>")

    html.append("<h3>Cheques and Payments</h3>")
    html.append(tab(["Date", "Description", "Debit", "Balance"], debits, numeric_idx={2,3}))
    html.append("<h3>Deposits and Credits</h3>")
    html.append(tab(["Date", "Description", "Credit", "Balance"], credits, numeric_idx={2,3}))
    html.append("<h3>Register</h3>")
    html.append(tab(["Date", "Description", "Debit", "Credit", "Balance"], register, numeric_idx={2,3,4}))
    html.append("</div>")
    return "\n".join(html)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Render a single annual HTML bundle of monthly reconciliation packets")
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
        col_desc = pick(["description", "vendor_name", "memo"], cols) or "description"
        col_debit = pick(["debit_amount", "debit", "amount_out"], cols) or "debit_amount"
        col_credit = pick(["credit_amount", "credit", "amount_in"], cols) or "credit_amount"
        col_bal = pick(["balance", "running_balance"], cols) or "balance"
        col_id = pick(["transaction_id", "id"], cols) or "transaction_id"

        # Build per-month sections
        month_sections = []
        toc = []
        for m in range(1, 13):
            start, end = month_bounds(year, m)

            # Beginning balance
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

            # Ending balance (fallback to cleared_balance)
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

            title = f"{year}-{m:02d} Reconciliation"
            month_sections.append(render_month_section(title, balances, debits, credits, register))
            toc.append(f"<li><a href='#{end:%Y-%m}'>{year}-{m:02d}</a></li>")

        css = """
        <style>
        body { font-family: Segoe UI, Arial, sans-serif; color: #111; }
        h1, h2 { margin: 0.2rem 0; }
        .kv { display: grid; grid-template-columns: 260px 1fr; row-gap: 6px; }
        table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
        th, td { border: 1px solid #ccc; padding: 6px 8px; font-size: 12px; }
        th { background: #f6f6f6; text-align: left; }
        .right { text-align: right; }
        .toc { margin: 0.5rem 0 1rem 0; }
        .toc li { display: inline-block; margin-right: 8px; }
        @media print { a { color: #000; text-decoration: none; } }
        </style>
        """

        html = ["<html><head><meta charset='utf-8'><title>Reconciliation Packet - Annual</title>", css, "</head><body>"]
        html.append(f"<h1>Reconciliation Packet - Account {account} - Year {year}</h1>")
        html.append("<ul class='toc'>" + "".join(toc) + "</ul>")
        html.extend(month_sections)
        html.append("</body></html>")

        out_dir = os.path.join("exports", "reconciliation", account, str(year))
        ensure_dir(out_dir)
        out_path = os.path.join(out_dir, f"reconciliation_packet_{year}_all.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html))
        print(f"[OK] Wrote annual printable HTML bundle: {out_path}")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
