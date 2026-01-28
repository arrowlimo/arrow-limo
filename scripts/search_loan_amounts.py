#!/usr/bin/env python3
"""
Search for exact loan payment amounts from Woodridge bill of sale.
Amounts: 965.50 (monthly), 130.30 (final), 131.26 (e-transfer)
"""
import psycopg2
from datetime import date

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Search for 965.50 (the monthly preauthorized payment amount)
amounts_to_search = [965.50, 130.30, 131.26]

print("WOODRIDGE LOAN PAYMENT SEARCH")
print("=" * 80)

for amt in amounts_to_search:
    print(f"\n\nSearching for ${amt:.2f}")
    print("-" * 80)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount, description
        FROM banking_transactions
        WHERE (ABS(COALESCE(debit_amount, 0) - %s) < 0.01 
           OR ABS(COALESCE(credit_amount, 0) - %s) < 0.01)
          AND EXTRACT(YEAR FROM transaction_date) IN (2017, 2018, 2019)
        ORDER BY transaction_date
    """, (amt, amt))
    
    rows = cur.fetchall()
    print(f"Found {len(rows)} transactions")
    
    # Group by year
    by_year = {}
    for r in rows:
        year = r[1].year
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(r)
    
    for year in sorted(by_year.keys()):
        print(f"\n  {year} ({len(by_year[year])} transactions):")
        for r in by_year[year][:5]:  # Show first 5 per year
            tid, tdate, debit, credit, desc = r
            print(f"    {tdate}  ID {tid}  debit ${debit or 0:.2f}  credit ${credit or 0:.2f}")
            print(f"      {desc[:120]}")
        if len(by_year[year]) > 5:
            print(f"    ... and {len(by_year[year]) - 5} more")

cur.close()
conn.close()
