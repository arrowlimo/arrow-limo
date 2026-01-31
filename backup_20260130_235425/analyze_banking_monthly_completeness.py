import os
import sys
import psycopg2
from datetime import date
from collections import defaultdict

"""
Banking Monthly Completeness Analysis
------------------------------------
Purpose:
  Determine which months (per account_number) have no banking_transactions records
  and flag potentially incomplete (sparse) months compared to historical norms.

Output:
  - Console summary
  - Optional markdown report written to reports/BANKING_MONTHLY_COMPLETENESS_REPORT_YYYYMMDD.md

Heuristics:
  - Missing: Month between min(transaction_date) and max(transaction_date) with count = 0
  - Sparse: Month count < 25% of median non-zero month count for that account

Usage:
  python -X utf8 scripts/analyze_banking_monthly_completeness.py [--report]

Environment Variables (same as other scripts):
  DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
"""

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    return conn

def month_range(start_date, end_date):
    months = []
    y, m = start_date.year, start_date.month
    while (y, m) <= (end_date.year, end_date.month):
        months.append((y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months

def format_month(y, m):
    return f"{y:04d}-{m:02d}"

def analyze(report=False):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM banking_transactions")
    row = cur.fetchone()
    if not row or not row[0] or not row[1]:
        print("No banking_transactions date range available.")
        cur.close(); conn.close()
        return
    min_date, max_date = row

    cur.execute("""
        SELECT account_number, date_trunc('month', transaction_date) AS month_start, COUNT(*)
        FROM banking_transactions
        GROUP BY account_number, month_start
        ORDER BY account_number, month_start
    """)
    data = cur.fetchall()

    cur.close(); conn.close()

    # Organize counts
    counts = defaultdict(dict)  # counts[account_number][YYYY-MM] = count
    for account_number, month_start, cnt in data:
        ym = format_month(month_start.year, month_start.month)
        counts[account_number][ym] = cnt

    all_months_list = [format_month(y, m) for y, m in month_range(min_date, max_date)]

    report_lines = []
    report_lines.append(f"# Banking Monthly Completeness Report ({date.today().isoformat()})\n")
    report_lines.append(f"Date Range: {min_date} to {max_date}\n")
    report_lines.append("Heuristics: Missing = month with 0 records; Sparse = count < 25% of median non-zero counts for that account.\n")

    for account, month_counts in counts.items():
        # Build full month list presence
        present_months = set(month_counts.keys())
        missing_months = [m for m in all_months_list if m not in present_months]
        non_zero_counts = [c for c in month_counts.values() if c > 0]
        if non_zero_counts:
            sorted_counts = sorted(non_zero_counts)
            median = sorted_counts[len(sorted_counts)//2]
        else:
            median = 0
        sparse_threshold = median * 0.25 if median > 0 else 0
        sparse_months = [m for m, c in month_counts.items() if c > 0 and c < sparse_threshold]

        report_lines.append(f"## Account {account}\n")
        report_lines.append(f"Total months in range: {len(all_months_list)}; Present: {len(present_months)}; Missing: {len(missing_months)}\n")
        report_lines.append(f"Median non-zero month count: {median}; Sparse threshold (<25% median): {sparse_threshold:.2f}\n")
        if missing_months:
            report_lines.append("Missing Months (no records): " + ", ".join(missing_months) + "\n")
        else:
            report_lines.append("Missing Months: None\n")
        if sparse_months:
            report_lines.append("Sparse Months (<threshold): " + ", ".join(sparse_months) + "\n")
        else:
            report_lines.append("Sparse Months: None\n")

        # Sample first/last 6 months counts for quick view
        sample_lines = []
        for m in (all_months_list[:6] + ['...'] + all_months_list[-6:]):
            if m == '...':
                sample_lines.append('...')
            else:
                c = month_counts.get(m, 0)
                tag = ''
                if m in missing_months:
                    tag = ' (MISSING)'
                elif c > 0 and c < sparse_threshold:
                    tag = ' (SPARSE)'
                sample_lines.append(f"{m}:{c}{tag}")
        report_lines.append("Sample Counts: " + " | ".join(sample_lines) + "\n")
        report_lines.append("\n")

    # Console output
    for line in report_lines:
        print(line.rstrip())

    if report:
        reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, f"BANKING_MONTHLY_COMPLETENESS_REPORT_{date.today().isoformat().replace('-', '')}.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))
        print(f"Report written: {report_path}")

if __name__ == '__main__':
    make_report = '--report' in sys.argv
    analyze(report=make_report)
