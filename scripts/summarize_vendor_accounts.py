import os
import csv
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

OUT_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "reports", "vendor_accounts")


def conn_cur():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    return conn, conn.cursor()


def get_accounts(cur):
    cur.execute("SELECT account_id, canonical_vendor, COALESCE(display_name, canonical_vendor) FROM vendor_accounts ORDER BY canonical_vendor")
    return cur.fetchall()


def get_ledger_entries(cur, account_id):
    cur.execute("""
        SELECT ledger_id, entry_date, entry_type, amount, balance_after, external_ref, notes
        FROM vendor_account_ledger
        WHERE account_id=%s
        ORDER BY entry_date ASC, CASE WHEN entry_type='INVOICE' THEN 0 ELSE 1 END, ledger_id ASC
    """, (account_id,))
    return cur.fetchall()


def summarize_account(account_id, vendor_name, entries):
    invoices = 0
    payments = 0
    last_balance = Decimal("0.00")
    first_date = None
    last_date = None
    for _, d, t, a, bal, *_ in entries:
        if t == 'INVOICE':
            invoices += 1
        elif t == 'PAYMENT':
            payments += 1
        last_balance = Decimal(str(bal or 0))
        if first_date is None:
            first_date = d
        last_date = d
    return {
        'account_id': account_id,
        'vendor': vendor_name,
        'entries_count': len(entries),
        'invoices_count': invoices,
        'payments_count': payments,
        'first_date': first_date.isoformat() if first_date else '',
        'last_date': last_date.isoformat() if last_date else '',
        'ending_balance': f"{last_balance:.2f}",
        'outstanding_payable': f"{(last_balance if last_balance > 0 else Decimal('0.00')):.2f}",
        'prepaid_or_credit': f"{(abs(last_balance) if last_balance < 0 else Decimal('0.00')):.2f}",
    }


def write_csv(summary_rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "VENDOR_ACCOUNTS_SUMMARY.csv")
    fields = [
        'account_id','vendor','entries_count','invoices_count','payments_count','first_date','last_date','ending_balance','outstanding_payable','prepaid_or_credit'
    ]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in summary_rows:
            w.writerow(r)
    return path


def write_latest_entries(vendor_name, entries, n=10):
    latest = entries[-n:] if len(entries) > n else entries
    txt_path = os.path.join(OUT_DIR, f"{vendor_name.replace(' ','_')}_LATEST.txt")
    lines = []
    lines.append(f"Latest {len(latest)} entries for {vendor_name}")
    lines.append("date | type | amount | bal_after | ref | notes")
    for _, d, t, a, bal, ref, notes in latest:
        lines.append(f"{d} | {t:<9} | {Decimal(str(a)):+.2f} | {Decimal(str(bal or 0)):+.2f} | {ref or ''} | {notes or ''}")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    return txt_path


def write_top_outstanding(summary_rows, top_n=20):
    # Sort by outstanding_payable desc
    def to_dec(s):
        try:
            return Decimal(s)
        except Exception:
            return Decimal('0')
    sorted_rows = sorted(summary_rows, key=lambda r: to_dec(r['outstanding_payable']), reverse=True)
    path = os.path.join(OUT_DIR, "TOP_OUTSTANDING_PAYABLES.txt")
    lines = []
    lines.append("Top Outstanding Payables (by ending balance > 0)")
    lines.append("vendor | account_id | ending_balance | entries | last_date")
    for r in sorted_rows[:top_n]:
        lines.append(f"{r['vendor']} | {r['account_id']} | {r['ending_balance']} | {r['entries_count']} | {r['last_date']}")
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    return path


def main():
    conn, cur = conn_cur()
    accounts = get_accounts(cur)
    summary_rows = []
    latest_paths = []
    for acc_id, canon, disp in accounts:
        entries = get_ledger_entries(cur, acc_id)
        summary = summarize_account(acc_id, disp, entries)
        summary_rows.append(summary)
        latest_paths.append(write_latest_entries(disp, entries, n=10))
    conn.close()

    csv_path = write_csv(summary_rows)
    tops_path = write_top_outstanding(summary_rows)

    print(csv_path)
    print(tops_path)
    for p in latest_paths[:5]:
        print(p)


if __name__ == "__main__":
    main()
