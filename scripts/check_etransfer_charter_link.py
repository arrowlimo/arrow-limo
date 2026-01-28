"""Check if e-transfer categorization helped identify missing charter payments."""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("E-TRANSFER TO CHARTER PAYMENT ANALYSIS")
print("=" * 80)

# Check e-transfer status
cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(amount) as total
    FROM etransfer_transactions
    WHERE direction = 'IN'
    GROUP BY category
    ORDER BY total DESC NULLS LAST
""")
print("\nE-TRANSFER INCOMING (potential customer payments):")
for row in cur.fetchall():
    cat = row[0] or 'UNCATEGORIZED'
    print(f"  {cat:30s}: {row[1]:5d} transactions, ${row[2]:>12,.2f}")

# Check payments with e-transfer keys
cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE payment_key LIKE 'BTX:%'
""")
result = cur.fetchone()
print(f"\nPayments with e-transfer keys (BTX:): {result[0]} payments, ${result[1]:,.2f}")

# Check unmatched payments
cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE reserve_number NOT IN (SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL)
    OR reserve_number IS NULL
""")
result = cur.fetchone()
print(f"Unmatched payments (no charter): {result[0]} payments, ${result[1]:,.2f}")

# Check charter balance issues (excluding 2025)
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(balance) as total_owed
    FROM charters
    WHERE paid_amount > 0 AND balance > 0
    AND EXTRACT(YEAR FROM charter_date) < 2025
""")
result = cur.fetchone()
print(f"\nPartially paid charters (pre-2025): {result[0]} charters, ${result[1]:,.2f} owed")

cur.execute("""
    SELECT 
        COUNT(*) as count,
        ABS(SUM(balance)) as total_overpaid
    FROM charters
    WHERE balance < 0
    AND EXTRACT(YEAR FROM charter_date) < 2025
""")
result = cur.fetchone()
print(f"Overpaid charters (pre-2025): {result[0]} charters, ${result[1]:,.2f} overpaid")

# Check if any IN e-transfers might be customer payments
cur.execute("""
    SELECT 
        et.sender_recipient_name,
        COUNT(*) as payment_count,
        SUM(et.amount) as total_amount
    FROM etransfer_transactions et
    WHERE et.direction = 'IN'
    AND et.category IS NULL
    GROUP BY et.sender_recipient_name
    HAVING COUNT(*) > 5
    ORDER BY SUM(et.amount) DESC
    LIMIT 10
""")
print("\nTop 10 uncategorized INCOMING e-transfer senders (potential customers):")
for row in cur.fetchall():
    name = row[0] or '(blank)'
    print(f"  {name:40s}: {row[1]:3d} payments, ${row[2]:>10,.2f}")

conn.close()
print("\n" + "=" * 80)
