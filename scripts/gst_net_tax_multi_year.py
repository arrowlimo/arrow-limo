#!/usr/bin/env python3
"""Compute GST collected vs input tax credits (ITCs) for specified years.
Assumptions:
 - Alberta 5% GST included in gross charter and receipt amounts.
 - Charter totals (charters.total_amount_due) are tax-included for taxable supplies.
 - Receipts: use receipts.gross_amount and receipts.tax_rate where available; fallback to 5% if is_taxable and tax_rate NULL.
Outputs markdown summary to reports/GST_NET_TAX_SUMMARY_<timestamp>.md
"""
import os, sys, psycopg2, argparse, datetime

GST_DEFAULT_RATE = 0.05

YEAR_CHARters_SQL = """
SELECT EXTRACT(YEAR FROM charter_date) AS yr,
       ROUND(SUM(total_amount_due)::numeric,2) AS total_due,
       ROUND(SUM(total_amount_due * %s / (1+%s))::numeric,2) AS gst_extracted
FROM charters
WHERE charter_date >= %s AND charter_date < %s AND cancelled IS NOT TRUE
GROUP BY yr;
"""

BASE_RECEIPTS_SQL_ALL_TAXABLE = """
SELECT EXTRACT(YEAR FROM receipt_date) AS yr,
       ROUND(SUM(gross_amount)::numeric,2) AS gross_total,
    ROUND(SUM( gross_amount * %s / (1+%s) )::numeric,2) AS gst_itc
FROM receipts
WHERE receipt_date >= %s AND receipt_date < %s
GROUP BY yr;"""

BASE_RECEIPTS_SQL_WITH_FLAGS = """
SELECT EXTRACT(YEAR FROM receipt_date) AS yr,
       ROUND(SUM(gross_amount)::numeric,2) AS gross_total,
       ROUND(SUM( CASE 
           WHEN is_taxable THEN (
               CASE WHEN tax_rate IS NOT NULL AND tax_rate > 0
                    THEN gross_amount * tax_rate / (1+tax_rate)
                    ELSE gross_amount * %s / (1+%s) END )
           ELSE 0 END )::numeric,2) AS gst_itc
FROM receipts
WHERE receipt_date >= %s AND receipt_date < %s
GROUP BY yr;"""

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def table_has_column(cur, table, column):
    cur.execute("""SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s""", (table, column))
    return cur.fetchone() is not None

def run(years):
    conn = get_conn(); cur = conn.cursor()
    has_is_taxable = table_has_column(cur, 'receipts', 'is_taxable')
    has_tax_rate = table_has_column(cur, 'receipts', 'tax_rate')
    receipts_sql = BASE_RECEIPTS_SQL_WITH_FLAGS if has_is_taxable else BASE_RECEIPTS_SQL_ALL_TAXABLE
    results = []
    for year in years:
        start = f"{year}-01-01"; end = f"{year+1}-01-01"
        cur.execute(YEAR_CHARters_SQL, (GST_DEFAULT_RATE, GST_DEFAULT_RATE, start, end))
        charter_row = cur.fetchone()
        charter_totals = {'year': year, 'charter_total_due': None, 'gst_collected': None}
        if charter_row:
            charter_totals['charter_total_due'] = float(charter_row[1])
            charter_totals['gst_collected'] = float(charter_row[2])
        cur.execute(receipts_sql, (GST_DEFAULT_RATE, GST_DEFAULT_RATE, start, end))
        receipt_row = cur.fetchone()
        receipt_totals = {'gst_itc': None, 'receipts_gross_total': None}
        if receipt_row:
            receipt_totals['receipts_gross_total'] = float(receipt_row[1])
            receipt_totals['gst_itc'] = float(receipt_row[2])
        combined = {**charter_totals, **receipt_totals}
        if combined['gst_collected'] is not None and combined['gst_itc'] is not None:
            combined['net_tax'] = round(combined['gst_collected'] - combined['gst_itc'], 2)
        else:
            combined['net_tax'] = None
        results.append(combined)
    cur.close(); conn.close()
    return results

def write_report(results):
    ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(os.path.dirname(__file__), '..', 'reports', f'GST_NET_TAX_SUMMARY_{ts}.md')
    path = os.path.normpath(path)
    lines = ["# GST Net Tax Summary (Draft)", f"Generated UTC: {ts}", "", "| Year | Charter Total (Tax-Incl) | GST Collected (Extracted) | Receipts Gross | GST ITCs | Net Tax |", "|------|--------------------------|---------------------------|---------------|----------|---------|"]
    for r in results:
        def fmt(v):
            return f"${v:,.2f}" if isinstance(v, (int,float)) else 'N/A'
        lines.append(f"| {r['year']} | {fmt(r['charter_total_due'])} | {fmt(r['gst_collected'])} | {fmt(r['receipts_gross_total'])} | {fmt(r['gst_itc'])} | {fmt(r['net_tax'])} |")
    lines.append("\nNotes: Net Tax = GST Collected - GST ITCs (does not include adjustments, bad debts, or prior period corrections).")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Report written: {path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--years', type=int, nargs='*', default=[2012,2013])
    args = parser.parse_args()
    res = run(args.years)
    write_report(res)
