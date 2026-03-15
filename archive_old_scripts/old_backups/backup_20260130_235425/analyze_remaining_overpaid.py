import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()

# Count remaining overpaid
cur.execute('SELECT COUNT(*) FROM charters WHERE paid_amount > total_amount_due')
total_overpaid = cur.fetchone()[0]

cur.execute('SELECT SUM(paid_amount - total_amount_due) FROM charters WHERE paid_amount > total_amount_due')
total_excess = cur.fetchone()[0]

# Count existing credits
cur.execute('SELECT COUNT(*), SUM(credit_amount), SUM(remaining_balance) FROM charter_credit_ledger')
r = cur.fetchone()
credit_count, credit_total, credit_available = r[0], r[1] or 0, r[2] or 0

print(f"Remaining Overpaid Charters: {total_overpaid}")
print(f"Total excess amount: ${float(total_excess):,.2f}" if total_excess else "Total excess amount: $0.00")
print(f"\nExisting credit ledger entries: {credit_count}")
print(f"Total credits: ${float(credit_total):,.2f}")
print(f"Available balance: ${float(credit_available):,.2f}")
print()

# Check which clients have most overpayments
cur.execute("""
    SELECT 
        cl.client_name,
        COUNT(*) as overpaid_count,
        SUM(c.paid_amount - c.total_amount_due) as excess_amount
    FROM charters c
    JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.paid_amount > c.total_amount_due
    GROUP BY cl.client_name
    ORDER BY excess_amount DESC
    LIMIT 10
""")

print("Top 10 clients with overpayments:")
print(f"{'Client':<40} {'Count':<8} {'Excess':>12}")
print("=" * 65)
for client, count, excess in cur.fetchall():
    client_display = (client or 'Unknown')[:40]
    print(f"{client_display:<40} {count:<8} ${float(excess):>10,.2f}")
