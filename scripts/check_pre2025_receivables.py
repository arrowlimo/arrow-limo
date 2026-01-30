import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get non-balanced charters (clients owe money) prior to 2025
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.status,
        COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) as charges,
        COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0) as payments,
        COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) - 
        COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0) as balance
    FROM charters c
    WHERE c.charter_date < '2025-01-01'
        AND c.status NOT IN ('Cancelled', 'cancelled', 'Canceled', 'canceled')
        AND (
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) - 
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0)
        ) > 0.01
    ORDER BY balance DESC
    LIMIT 20
""")

rows = cur.fetchall()

print(f"Non-balanced charters (clients owe money) prior to 2025:")
print(f"{'Reserve':<12} {'Date':<12} {'Status':<15} {'Charges':<12} {'Payments':<12} {'Balance':<12}")
print("-" * 85)

total_owed = 0.0
for row in rows:
    reserve, date, status, charges, payments, balance = row
    print(f"{reserve:<12} {str(date):<12} {status:<15} ${float(charges):>10.2f} ${float(payments):>10.2f} ${float(balance):>10.2f}")
    total_owed += float(balance)

print("-" * 85)
print(f"Top 20 total owed: ${total_owed:,.2f}")

# Get count and total
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) - 
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0)
        ) as total_owed
    FROM charters c
    WHERE c.charter_date < '2025-01-01'
        AND c.status NOT IN ('Cancelled', 'cancelled', 'Canceled', 'canceled')
        AND (
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) - 
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0)
        ) > 0.01
""")

count, total = cur.fetchone()

print()
print(f"TOTAL non-balanced charters (positive balance, pre-2025): {count}")
print(f"TOTAL amount owed by clients: ${float(total or 0):,.2f}")

cur.close()
conn.close()
