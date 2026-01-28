"""
Generate consolidated GST history for 2010–2015 by combining:
- 2010–2012 from charter_gst_details_2010_2012
- 2013–2015 from existing exports/cra/<year>/tax_year_summary_<year>.csv if present
Outputs: exports/cra/GST_HISTORY_2010_2015.md
"""
import csv
from pathlib import Path
import psycopg2

BASE = Path('l:/limo/exports/cra')

def get_db_connection():
    return psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')


def gst_from_details_2010_2012():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
    WITH base AS (
      SELECT COALESCE(EXTRACT(YEAR FROM d.reserve_date), EXTRACT(YEAR FROM c.charter_date))::int AS year, d.*
      FROM charter_gst_details_2010_2012 d
      LEFT JOIN charters c ON c.reserve_number = d.reserve_number
    )
    SELECT year, COUNT(*), COALESCE(SUM(gst_taxable),0), COALESCE(SUM(gst_amount),0)
    FROM base
    WHERE year IN (2010,2011,2012)
    GROUP BY year ORDER BY year
    """)
    data = {}
    for year, records, taxable, gst in cur.fetchall():
        data[int(year)] = {'records':records, 'gst_taxable':float(taxable), 'gst_collected':float(gst)}
    cur.close(); conn.close(); return data


def read_tax_summary_csv(year):
    fp = BASE / str(year) / f"tax_year_summary_{year}.csv"
    if not fp.exists():
        return None
    with fp.open('r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        row = next(r)
        # Expected headers: gst_collected, gst_itc, revenue, expense, net_income, cra_payments
        return {
            'gst_collected': float(row.get('gst_collected', '0') or 0.0),
            'gst_itc': float(row.get('gst_itc', '0') or 0.0),
            'cra_payments': float(row.get('cra_payments', '0') or 0.0)
        }


def main():
    out = BASE / 'GST_HISTORY_2010_2015.md'
    d_2010_2012 = gst_from_details_2010_2012()
    summary = {}

    # Start with 2010–2012
    for y in (2010, 2011, 2012):
        s = d_2010_2012.get(y, {'records':0,'gst_taxable':0,'gst_collected':0})
        summary[y] = {
            'gst_collected': s['gst_collected'],
            'gst_itc': 0.0,  # Typically ITC isn't in this spreadsheet; left as 0
            'cra_payments': 0.0
        }

    # Add 2013–2015 from exports if available
    for y in (2013, 2014, 2015):
        s = read_tax_summary_csv(y)
        if s:
            summary[y] = s
        else:
            summary[y] = {'gst_collected':0.0,'gst_itc':0.0,'cra_payments':0.0}

    # Write MD
    total_collect = total_itc = total_pay = 0.0
    with out.open('w', encoding='utf-8') as f:
        f.write('# GST History 2010–2015\n\n')
        for y in range(2010, 2016):
            s = summary.get(y, {'gst_collected':0.0,'gst_itc':0.0,'cra_payments':0.0})
            net = s['gst_collected'] - s['gst_itc']
            f.write(f"## {y}\n")
            f.write(f"- GST Collected: ${s['gst_collected']:,.2f}\n")
            f.write(f"- ITCs: ${s['gst_itc']:,.2f}\n")
            f.write(f"- Net GST: ${net:,.2f}\n")
            f.write(f"- CRA Payments: ${s['cra_payments']:,.2f}\n\n")
            total_collect += s['gst_collected']
            total_itc += s['gst_itc']
            total_pay += s['cra_payments']
        f.write('---\n')
        f.write(f"**TOTAL 2010–2015**\n\n")
        f.write(f"- GST Collected: ${total_collect:,.2f}\n")
        f.write(f"- ITCs: ${total_itc:,.2f}\n")
        f.write(f"- Net GST: ${total_collect - total_itc:,.2f}\n")
        f.write(f"- CRA Payments: ${total_pay:,.2f}\n")

    print(f"[OK] Wrote consolidated report: {out}")

if __name__ == '__main__':
    main()
