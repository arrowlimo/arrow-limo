import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get charter details
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance
    FROM charters 
    WHERE reserve_number = '013932'
""")
charter = cur.fetchone()

print(f"\n{'='*80}")
print(f"Charter {charter[1]} Details:")
print(f"{'='*80}")
print(f"  charter_id: {charter[0]}")
print(f"  total_amount_due: ${charter[2] or 0:,.2f}")
print(f"  paid_amount: ${charter[3] or 0:,.2f}")
print(f"  balance: ${charter[4] or 0:,.2f}")

# Check charges
cur.execute("""
    SELECT COUNT(*), SUM(amount) 
    FROM charter_charges 
    WHERE charter_id = %s
""", (charter[0],))
charge_count, charge_sum = cur.fetchone()

print(f"\nCharges:")
print(f"  Count: {charge_count}")
print(f"  Sum: ${charge_sum or 0:,.2f}")

# Check payments by reserve_number
cur.execute("""
    SELECT COUNT(*), SUM(amount) 
    FROM payments 
    WHERE reserve_number = %s
""", (charter[1],))
payment_count, payment_sum = cur.fetchone()

print(f"\nPayments (by reserve_number):")
print(f"  Count: {payment_count}")
print(f"  Sum: ${payment_sum or 0:,.2f}")

# Show payment details
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes
    FROM payments 
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (charter[1],))

print(f"\nPayment Details:")
for p in cur.fetchall():
    print(f"  {p[1]} - ${p[2]:,.2f} ({p[3] or 'unknown'}) {p[4] or ''}")

cur.close()
conn.close()
