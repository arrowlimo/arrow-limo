"""Analyze overpaid charters by type - separate legitimate overpayments from cancelled deposits."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 100)
print("OVERPAID CHARTER ANALYSIS (PRE-2025)")
print("=" * 100)

# Cancelled charters with $0 charges (non-refundable deposits)
cur.execute("""
    SELECT COUNT(*), ABS(SUM(balance))
    FROM charters
    WHERE balance < 0
    AND EXTRACT(YEAR FROM charter_date) < 2025
    AND total_amount_due = 0
    AND (cancelled = TRUE OR status = 'Cancelled' OR payment_status LIKE '%Cancelled%')
""")
result = cur.fetchone()
print(f"\n1. CANCELLED with $0 charges (non-refundable deposits):")
print(f"   {result[0]} charters, ${result[1]:,.2f}")
print(f"   → These are LEGITIMATE - customer forfeited deposit")

# Non-cancelled with $0 charges (data issues)
cur.execute("""
    SELECT COUNT(*), ABS(SUM(balance))
    FROM charters
    WHERE balance < 0
    AND EXTRACT(YEAR FROM charter_date) < 2025
    AND total_amount_due = 0
    AND NOT (cancelled = TRUE OR status = 'Cancelled' OR payment_status LIKE '%Cancelled%')
""")
result = cur.fetchone()
print(f"\n2. NON-CANCELLED with $0 charges (missing charge data):")
print(f"   {result[0]} charters, ${result[1]:,.2f}")
print(f"   → These need investigation - payments without charges")

# Actual overpayments (paid more than owed)
cur.execute("""
    SELECT COUNT(*), ABS(SUM(balance))
    FROM charters
    WHERE balance < 0
    AND EXTRACT(YEAR FROM charter_date) < 2025
    AND total_amount_due > 0
""")
result = cur.fetchone()
print(f"\n3. OVERPAID with actual charges (paid more than total due):")
print(f"   {result[0]} charters, ${result[1]:,.2f}")
print(f"   → True overpayments - duplicate payments or customer credits")

# Show samples of non-cancelled $0 charge overpayments
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        cl.client_name,
        c.paid_amount,
        c.balance,
        c.payment_status,
        c.status
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.balance < 0
    AND EXTRACT(YEAR FROM c.charter_date) < 2025
    AND c.total_amount_due = 0
    AND NOT (c.cancelled = TRUE OR c.status = 'Cancelled' OR c.payment_status LIKE '%Cancelled%')
    ORDER BY c.balance
    LIMIT 20
""")

print("\n" + "=" * 100)
print("SAMPLE: Non-cancelled charters with $0 charges but payments received")
print("=" * 100)
print(f"{'Reserve#':8s} | {'Date':12s} | {'Client':30s} | {'Paid':>10s} | {'Balance':>10s} | Status")
print("-" * 100)

for row in cur.fetchall():
    reserve = row[0] or ''
    date = str(row[1]) if row[1] else ''
    client = (row[2] or '')[:30]
    paid = row[3] or 0
    balance = row[4] or 0
    pay_status = row[5] or ''
    status = row[6] or ''
    
    print(f"{reserve:8s} | {date:12s} | {client:30s} | ${paid:>9,.2f} | ${balance:>9,.2f} | {pay_status or status}")

print("\n" + "=" * 100)

conn.close()
