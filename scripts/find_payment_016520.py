"""Find payment for reserve 016520 with card ending 4813."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 100)
print("SEARCHING FOR PAYMENT: Reserve 016520, Card ending 4813, Amount $200")
print("=" * 100)

# Search payments for this reserve
cur.execute("""
    SELECT 
        payment_id,
        reserve_number,
        amount,
        payment_date,
        payment_method,
        credit_card_last4,
        square_last4,
        payment_key,
        notes,
        square_transaction_id
    FROM payments
    WHERE reserve_number = '016520'
    ORDER BY payment_date
""")

print("\nAll payments for reserve 016520:")
print(f"{'ID':6s} | {'Amount':>10s} | {'Date':12s} | {'Method':15s} | {'Last4':6s} | {'Key':20s} | Notes")
print("-" * 100)

total = 0
for row in cur.fetchall():
    pid = row[0]
    amount = row[2] or 0
    date = str(row[3]) if row[3] else ''
    method = row[4] or ''
    last4 = row[5] or row[6] or ''
    key = row[7] or ''
    notes = row[8] or ''
    
    total += amount
    marker = " ← MATCH!" if last4 == '4813' or amount == 200 else ""
    print(f"{pid:6d} | ${amount:>9,.2f} | {date:12s} | {method:15s} | {last4:6s} | {key:20s} | {notes[:30]}{marker}")

print(f"\nTotal paid: ${total:,.2f}")

# Search by card number ending
cur.execute("""
    SELECT 
        payment_id,
        reserve_number,
        amount,
        payment_date,
        payment_method,
        credit_card_last4,
        square_last4
    FROM payments
    WHERE credit_card_last4 = '4813' OR square_last4 = '4813'
    ORDER BY payment_date DESC
    LIMIT 20
""")

print("\n" + "=" * 100)
print("All payments with card ending 4813:")
print(f"{'ID':6s} | {'Reserve':8s} | {'Amount':>10s} | {'Date':12s} | {'Method':15s}")
print("-" * 100)

for row in cur.fetchall():
    marker = " ← RESERVE 016520" if row[1] == '016520' else ""
    print(f"{row[0]:6d} | {row[1] or '':8s} | ${row[2]:>9,.2f} | {str(row[3]) if row[3] else '':12s} | {row[4] or '':15s}{marker}")

# Get charter info
cur.execute("""
    SELECT 
        charter_date,
        total_amount_due,
        paid_amount,
        balance,
        payment_status
    FROM charters
    WHERE reserve_number = '016520'
""")

print("\n" + "=" * 100)
print("Charter 016520 status:")
result = cur.fetchone()
if result:
    print(f"Date: {result[0]}")
    print(f"Total Due: ${result[1]:,.2f}")
    print(f"Paid: ${result[2]:,.2f}")
    print(f"Balance: ${result[3]:,.2f}")
    print(f"Status: {result[4]}")

conn.close()
