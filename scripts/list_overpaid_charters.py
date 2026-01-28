"""List all overpaid charters (pre-2025) for review."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT 
        c.reserve_number, 
        c.charter_date, 
        cl.client_name, 
        c.total_amount_due, 
        c.paid_amount, 
        c.balance,
        c.payment_status
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.balance < 0 
    AND EXTRACT(YEAR FROM c.charter_date) < 2025 
    ORDER BY c.balance
""")

rows = cur.fetchall()

print("=" * 140)
print("OVERPAID CHARTERS (PRE-2025)")
print("=" * 140)
print(f"{'Reserve#':8s} | {'Date':12s} | {'Client Name':36s} | {'Total Due':>11s} | {'Paid':>11s} | {'Balance':>11s} | Status")
print("-" * 140)

total_overpaid = 0
for row in rows:
    reserve = row[0] or ''
    date = str(row[1]) if row[1] else ''
    client = (row[2] or '')[:36]
    total_due = row[3] or 0
    paid = row[4] or 0
    balance = row[5] or 0
    status = row[6] or ''
    
    total_overpaid += abs(balance)
    
    print(f"{reserve:8s} | {date:12s} | {client:36s} | ${total_due:>10,.2f} | ${paid:>10,.2f} | ${balance:>10,.2f} | {status}")

print("-" * 140)
print(f"\nTotal overpaid charters: {len(rows)}")
print(f"Total overpayment amount: ${total_overpaid:,.2f}")

# Group by payment status
cur.execute("""
    SELECT 
        payment_status,
        COUNT(*) as count,
        ABS(SUM(balance)) as total
    FROM charters 
    WHERE balance < 0 
    AND EXTRACT(YEAR FROM charter_date) < 2025 
    GROUP BY payment_status
    ORDER BY total DESC
""")

print("\nBreakdown by payment status:")
for row in cur.fetchall():
    status = row[0] or 'NULL'
    print(f"  {status:20s}: {row[1]:3d} charters, ${row[2]:>10,.2f}")

conn.close()
