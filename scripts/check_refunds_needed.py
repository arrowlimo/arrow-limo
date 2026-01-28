import psycopg2
import csv
import os

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

OUT_FILE = r"L:\limo\reports\CHARTERS_TO_REFUND.csv"

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=== Charters with negative balance (we owe refunds) ===\n")

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
    WHERE c.balance < 0
    ORDER BY c.balance ASC, c.charter_date DESC
""")

refunds = cur.fetchall()

total_refund = sum(abs(float(r[6] or 0)) for r in refunds)

print(f"Charters requiring refund: {len(refunds)}")
print(f"Total refund amount: ${total_refund:,.2f}\n")

if refunds:
    print("Top 20 by refund amount:")
    for r in refunds[:20]:
        refund_amt = abs(float(r[6]))
        print(f"  {r[1]} | {r[2]} | Refund: ${refund_amt:,.2f} | Status: {r[3]} | Total: ${float(r[4]):,.2f} | Paid: ${float(r[5]):,.2f}")
    
    # Write to CSV
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['charter_id', 'reserve_number', 'charter_date', 'status', 'total_amount_due', 'paid_amount', 'refund_amount', 'client_id'])
        for r in refunds:
            refund_amt = abs(float(r[6]))
            writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], refund_amt, r[7]])
    
    print(f"\nFull report: {OUT_FILE}")
else:
    print("No refunds needed")

cur.close()
conn.close()
