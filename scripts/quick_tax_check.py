import psycopg2
c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
r = c.cursor()

# Revenue by year
r.execute("""
    SELECT 
        EXTRACT(YEAR FROM charter_date)::int as year,
        COUNT(*) as charters,
        SUM(total_amount_due) as revenue
    FROM charters
    WHERE charter_date IS NOT NULL 
    AND EXTRACT(YEAR FROM charter_date) IN (2013, 2014)
    GROUP BY year
    ORDER BY year
""")
print("REVENUE (from charters):")
print("Year   Charters    Revenue")
print("-" * 40)
for row in r.fetchall():
    print(f"{row[0]}   {row[1]:>7,}    ${row[2] or 0:>12,.2f}")

# Expenses by year
r.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date)::int as year,
        COUNT(*) as receipts,
        SUM(amount) as expenses
    FROM receipts
    WHERE receipt_date IS NOT NULL 
    AND EXTRACT(YEAR FROM receipt_date) IN (2013, 2014)
    GROUP BY year
    ORDER BY year
""")
print("\nEXPENSES (from receipts):")
print("Year   Receipts    Expenses")
print("-" * 40)
for row in r.fetchall():
    print(f"{row[0]}   {row[1]:>7,}    ${row[2] or 0:>12,.2f}")

c.close()
