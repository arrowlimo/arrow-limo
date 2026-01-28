import os
import psycopg2
from collections import defaultdict

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    # Get year-end summary totals (from T4 table only)
    cur.execute("""
        SELECT year, employee_name, sin, box_14_employment_income
        FROM staging_t4_validation
    """)
    summary_totals = defaultdict(dict)
    for year, name, sin, total in cur.fetchall():
        summary_totals[year][name.strip().upper()] = float(total)
    
    # Aggregate ingested driver pay records by employee and year
    cur.execute("""
        SELECT EXTRACT(YEAR FROM pay_date) as year, employee_name, SUM(amount) as total_pay
        FROM staging_driver_pay
        GROUP BY year, employee_name
    """)
    ingested_totals = defaultdict(dict)
    for year, name, total in cur.fetchall():
        ingested_totals[int(year)][name.strip().upper()] = float(total)
    
    # Compare and report discrepancies
    output = []
    output.append("YEAR-END PAY TOTALS COMPARISON")
    output.append("="*80)
    for year in sorted(summary_totals.keys()):
        output.append(f"\nYear: {year}")
        output.append("Employee                | Summary Total | Ingested Total | Difference")
        output.append("------------------------+---------------+---------------+-----------")
        for name in sorted(summary_totals[year].keys()):
            summary_total = summary_totals[year][name]
            ingested_total = ingested_totals.get(int(year), {}).get(name, 0.0)
            diff = summary_total - ingested_total
            output.append(f"{name:24s} | {summary_total:13.2f} | {ingested_total:13.2f} | {diff:10.2f}")
    
    # Save to file
    with open("driver_pay_year_end_comparison.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print("\n".join(output))
    print("\nReport saved to: driver_pay_year_end_comparison.txt")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
