import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=== Fixing rounding errors on 005612 and 005613 ===\n")

for reserve in ['005612', '005613']:
    cur.execute("""
        SELECT charter_id, total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    charter = cur.fetchone()
    if charter:
        total = float(charter[1] or 0)
        paid = float(charter[2] or 0)
        old_balance = float(charter[3] or 0)
        new_balance = round(total - paid, 2)
        
        print(f"{reserve}: Total=${total} | Paid=${paid}")
        print(f"  Balance: ${old_balance} → ${new_balance}")
        
        cur.execute("""
            UPDATE charters
            SET balance = %s
            WHERE reserve_number = %s
        """, (new_balance, reserve))
        
        print(f"  ✅ Fixed\n")

conn.commit()

# Verify
print("=== Verification ===")
cur.execute("""
    SELECT COUNT(*) as discrepancies
    FROM charters c
    LEFT JOIN (
        SELECT reserve_number, SUM(amount) as total_paid
        FROM payments
        GROUP BY reserve_number
    ) p ON c.reserve_number = p.reserve_number
    WHERE ABS(c.balance - (c.total_amount_due - COALESCE(p.total_paid, 0))) > 0.01
""")
remaining = cur.fetchone()[0]
print(f"Remaining discrepancies: {remaining}")

cur.close()
conn.close()

print("\n✅ Rounding errors fixed")
