import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=== Finding cancelled charters with payments ===\n")

# Find cancelled charters with payments
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.status, c.total_amount_due, c.paid_amount, c.balance,
           COUNT(p.payment_id) as payment_count, SUM(p.amount) as total_payments
    FROM charters c
    INNER JOIN payments p ON c.reserve_number = p.reserve_number
    WHERE LOWER(c.status) LIKE '%cancel%'
    GROUP BY c.charter_id, c.reserve_number, c.status, c.total_amount_due, c.paid_amount, c.balance
    ORDER BY total_payments DESC
""")

cancelled_with_payments = cur.fetchall()

if cancelled_with_payments:
    total_to_remove = sum(float(r[7] or 0) for r in cancelled_with_payments)
    total_payments_count = sum(int(r[6] or 0) for r in cancelled_with_payments)
    
    print(f"Found {len(cancelled_with_payments)} cancelled charters with payments")
    print(f"Total payment records: {total_payments_count}")
    print(f"Total payment amount: ${total_to_remove:,.2f}\n")
    
    print("Top 20 by payment amount:")
    for r in cancelled_with_payments[:20]:
        print(f"  {r[1]} | Status: {r[2]} | Payments: {r[6]} × ${float(r[7]):,.2f} | Charter Total: ${float(r[3]):,.2f}")
    
    # Remove payments for cancelled charters
    print(f"\n=== Removing {total_payments_count} payments from cancelled charters ===")
    
    for charter in cancelled_with_payments:
        reserve = charter[1]
        
        # Delete payments
        cur.execute("""
            DELETE FROM payments
            WHERE reserve_number = %s
        """, (reserve,))
        
        # Update charter to reflect no payments
        cur.execute("""
            UPDATE charters
            SET paid_amount = 0,
                balance = total_amount_due
            WHERE reserve_number = %s
        """, (reserve,))
    
    conn.commit()
    
    print(f"✅ Removed {total_payments_count} payment records")
    print(f"✅ Updated {len(cancelled_with_payments)} charter balances")
    
else:
    print("No cancelled charters with payments found")

cur.close()
conn.close()
