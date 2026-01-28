"""
Generate per-year GST summaries for 2010–2012 using charter_gst_details_2010_2012
Outputs CSV + MD into exports/cra/<year>/
"""
import os
import csv
from pathlib import Path
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***'
    )

OUT_DIR = Path('l:/limo/exports/cra')

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

QUERY = """
WITH base AS (
  SELECT 
    COALESCE(EXTRACT(YEAR FROM d.reserve_date), EXTRACT(YEAR FROM c.charter_date))::int AS year,
    d.*
  FROM charter_gst_details_2010_2012 d
  LEFT JOIN charters c ON c.reserve_number = d.reserve_number
)
SELECT 
  year,
  COUNT(*) AS records,
  COALESCE(SUM(gst_taxable),0) AS gst_taxable,
  COALESCE(SUM(gst_amount),0) AS gst_collected,
  COALESCE(SUM(total_amount),0) AS total_amount,
  COALESCE(SUM(gratuity),0) AS gratuity,
  COALESCE(SUM(fuel_surcharge),0) AS fuel_surcharge,
  COALESCE(SUM(beverage_charge),0) AS beverage_charge,
  COALESCE(SUM(service_fee),0) AS service_fee
FROM base
WHERE year IN (2010, 2011, 2012)
GROUP BY year
ORDER BY year;
"""

def write_csv(row, year):
    year_dir = OUT_DIR / str(year)
    ensure_dir(year_dir)
    fp = year_dir / f"gst_summary_{year}.csv"
    with fp.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['year','records','gst_taxable','gst_collected','total_amount','gratuity','fuel_surcharge','beverage_charge','service_fee'])
        w.writerow([year, row['records'], f"{row['gst_taxable']:.2f}", f"{row['gst_collected']:.2f}", f"{row['total_amount']:.2f}", f"{row['gratuity']:.2f}", f"{row['fuel_surcharge']:.2f}", f"{row['beverage_charge']:.2f}", f"{row['service_fee']:.2f}"])
    return fp

def write_md(row, year):
    year_dir = OUT_DIR / str(year)
    ensure_dir(year_dir)
    fp = year_dir / f"gst_summary_{year}.md"
    with fp.open('w', encoding='utf-8') as f:
        f.write(f"# GST Summary {year}\n\n")
        f.write(f"- Records: {row['records']:,}\n")
        f.write(f"- GST Taxable: ${row['gst_taxable']:,.2f}\n")
        f.write(f"- GST Collected: ${row['gst_collected']:,.2f}\n")
        f.write(f"- Total Amount: ${row['total_amount']:,.2f}\n")
        f.write(f"- Gratuity: ${row['gratuity']:,.2f}\n")
        f.write(f"- Fuel Surcharge: ${row['fuel_surcharge']:,.2f}\n")
        f.write(f"- Beverage: ${row['beverage_charge']:,.2f}\n")
        f.write(f"- Service Fee: ${row['service_fee']:,.2f}\n")
    return fp

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(QUERY)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    total = {'gst_taxable':0,'gst_collected':0,'total_amount':0,'records':0}
    print("Per-year GST summaries (2010–2012):")
    for r in rows:
        row = dict(zip(cols, r))
        year = row['year']
        print(f"  {year}: {row['records']} records | Taxable ${row['gst_taxable']:,.2f} | GST ${row['gst_collected']:,.2f}")
        write_csv(row, year)
        write_md(row, year)
        total['gst_taxable'] += row['gst_taxable']
        total['gst_collected'] += row['gst_collected']
        total['total_amount'] += row['total_amount']
        total['records'] += row['records']
    print(f"\nTOTAL 2010–2012: {total['records']} records | Taxable ${total['gst_taxable']:,.2f} | GST ${total['gst_collected']:,.2f}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
