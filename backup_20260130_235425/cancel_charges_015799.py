import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=== Cancelling all charges on 015799 ===\n")

# Get current state
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, status
    FROM charters
    WHERE reserve_number = '015799'
""")
charter = cur.fetchone()

if charter:
    total = float(charter[2] or 0)
    paid = float(charter[3] or 0)
    balance = float(charter[4] or 0)
    
    print(f"Before: Total=${total} | Paid=${paid} | Balance=${balance} | Status={charter[5]}")
    
    # Cancel all charges - set total to 0, balance becomes negative of paid amount
    new_balance = 0 - paid
    
    cur.execute("""
        UPDATE charters
        SET total_amount_due = 0,
            balance = %s
        WHERE reserve_number = '015799'
    """, (new_balance,))
    
    conn.commit()
    
    print(f"After: Total=$0 | Paid=${paid} | Balance=${new_balance}")
    print(f"\n✅ All charges cancelled on 015799")
    if new_balance < 0:
        print(f"   Note: Customer has credit of ${abs(new_balance)}")
else:
    print("❌ Charter 015799 not found")

cur.close()
conn.close()
