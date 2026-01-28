import psycopg2
import csv
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

OUT_FILE = r"L:\limo\reports\PRE_2024_OUTSTANDING_BALANCES.csv"

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.status,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        c.client_id
    FROM charters c
    WHERE c.charter_date < '2024-01-01'
        AND c.balance > 0
    ORDER BY c.balance DESC, c.charter_date
""")

rows = cur.fetchall()

total_owed = sum(float(r[6] or 0) for r in rows)

print(f"Pre-2024 charters with outstanding balance: {len(rows)}")
print(f"Total amount owed: ${total_owed:,.2f}\n")

if rows:
    print("Top 20 by balance owed:")
    for r in rows[:20]:
        print(f"  {r[1]} | {r[2]} | ${float(r[6]):,.2f} | Status: {r[3]} | Total: ${float(r[4]):,.2f} | Paid: ${float(r[5]):,.2f}")

# Write to CSV
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['charter_id', 'reserve_number', 'charter_date', 'status', 'total_amount_due', 'paid_amount', 'balance_owed', 'client_id'])
    for r in rows:
        writer.writerow(r)

print(f"\nFull report: {OUT_FILE}")

cur.close()
conn.close()
