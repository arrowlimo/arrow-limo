import psycopg2

conn = psycopg2.connect('dbname=almsdata user=postgres password=***REMOVED*** host=localhost')
cur = conn.cursor()

# Update 014617 to uncancelled promo status
cur.execute("""
    UPDATE charters 
    SET cancelled = FALSE,
        status = 'Promo'
    WHERE reserve_number = '014617'
""")

print(f"✓ Updated {cur.rowcount} charter(s)")
conn.commit()

# Verify
cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance, cancelled, status
    FROM charters 
    WHERE reserve_number IN ('014617', '014618')
    ORDER BY reserve_number
""")

print("\nVerification:")
print("Reserve    Total    Paid     Balance  Cancelled  Status")
print("-" * 70)
for r in cur.fetchall():
    print(f"{r[0]}  ${r[1]:>7.2f}  ${r[2]:>7.2f}  ${r[3]:>7.2f}  {str(r[4]):9s}  {r[5] or ''}")

cur.close()
conn.close()
