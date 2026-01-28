import psycopg2, os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 100)
print("PAYMENT 30480: $210 on 2024-10-18 - KERI JENSEN")
print("=" * 100)

# Check both Keri Jensen clients
for client_id in [3722, 5879]:
    cur.execute("""
        SELECT client_id, client_name, account_number
        FROM clients
        WHERE client_id = %s
    """, (client_id,))
    
    client = cur.fetchone()
    if client:
        print(f"\nClient {client[0]}: {client[1]} (Account {client[2]})")
        
        # Find charters around Oct 18, 2024
        cur.execute("""
            SELECT charter_id, reserve_number, charter_date, balance, total_amount_due, rate
            FROM charters
            WHERE client_id = %s
              AND charter_date BETWEEN '2024-09-18' AND '2024-11-18'
            ORDER BY charter_date
        """, (client_id,))
        
        charters = cur.fetchall()
        if charters:
            print(f"  Charters around Oct 18, 2024:")
            for cid, reserve, cdate, balance, total_due, rate in charters:
                amount_match = ""
                if balance and abs(float(balance) - 210) < 1.0:
                    amount_match = " [OK] BALANCE MATCH $210!"
                if total_due and abs(float(total_due) - 210) < 1.0:
                    amount_match = " [OK] TOTAL DUE MATCH $210!"
                if rate and abs(float(rate) - 210) < 1.0:
                    amount_match = " [OK] RATE MATCH $210!"
                    
                print(f"    Charter {cid} (Reserve {reserve}): {cdate}")
                print(f"      Balance: ${balance if balance else 0:.2f}, "
                      f"Total Due: ${total_due if total_due else 0:.2f}, "
                      f"Rate: ${rate if rate else 0:.2f}{amount_match}")
        else:
            print("  No charters in this date range")

print("\n" + "=" * 100)
print("PAYMENT 30483 & 30484: $200 each - DARLIE KRUEGER")
print("=" * 100)

cur.execute("""
    SELECT charter_id, reserve_number, charter_date, balance, total_amount_due, rate, paid_amount
    FROM charters
    WHERE client_id = 5921
      AND charter_date BETWEEN '2024-09-16' AND '2024-11-16'
    ORDER BY charter_date
""")

charters = cur.fetchall()
print("\nClient 5921: Krueger Darlie (Account 06975)")
print(f"  Charters around Oct 16-17, 2024:")

total_balance = 0
for cid, reserve, cdate, balance, total_due, rate, paid in charters:
    amount_match = ""
    if balance:
        total_balance += float(balance)
        if abs(float(balance) - 200) < 1.0:
            amount_match = " [OK] BALANCE MATCH $200!"
    if total_due and abs(float(total_due) - 200) < 1.0:
        amount_match = " [OK] TOTAL DUE MATCH $200!"
        
    print(f"    Charter {cid} (Reserve {reserve}): {cdate}")
    print(f"      Balance: ${balance if balance else 0:.2f}, "
          f"Total Due: ${total_due if total_due else 0:.2f}, "
          f"Paid: ${paid if paid else 0:.2f}{amount_match}")

print(f"\n  Total balance across charters: ${total_balance:.2f}")
if abs(total_balance - 400) < 1.0:
    print("  [OK] TWO $200 PAYMENTS = $400 TOTAL BALANCE!")

cur.close()
conn.close()
