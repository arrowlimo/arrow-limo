import psycopg2
import os

# Database connection
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("ALL SKELLY LIEM PAYMENTS (CHARTERS 018841 & 018842)")
print("=" * 80)

# Get all payments
cur.execute("""
    SELECT payment_id, reserve_number, charter_id, amount, payment_date, 
           payment_method, payment_key, notes
    FROM payments 
    WHERE reserve_number IN ('018841', '018842')
    ORDER BY payment_date
""")
payments = cur.fetchall()

print("\nPAYMENTS:")
print("-" * 80)
for p in payments:
    print(f"Payment {p[0]} | Res: {p[1]} | Charter: {p[2]} | ${p[3]} | {p[4]}")
    print(f"  Method: {p[5]} | Key: {p[6]}")
    if p[7]:
        print(f"  Notes: {p[7]}")
    print()

# Get charter 018841 details
print("\nCHARTER 018841 DETAILS:")
print("-" * 80)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, client_id, 
           total_amount_due, paid_amount, balance, cancelled
    FROM charters 
    WHERE reserve_number = '018841'
""")
c1 = cur.fetchone()
if c1:
    print(f"Charter {c1[0]} | Res: {c1[1]} | Date: {c1[2]} | Client: {c1[3]}")
    print(f"Total Due: ${c1[4]} | Paid: ${c1[5]} | Balance: ${c1[6]} | Cancelled: {c1[7]}")

# Get charter 018842 details
print("\nCHARTER 018842 DETAILS:")
print("-" * 80)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, client_id, 
           total_amount_due, paid_amount, balance, cancelled
    FROM charters 
    WHERE reserve_number = '018842'
""")
c2 = cur.fetchone()
if c2:
    print(f"Charter {c2[0]} | Res: {c2[1]} | Date: {c2[2]} | Client: {c2[3]}")
    print(f"Total Due: ${c2[4]} | Paid: ${c2[5]} | Balance: ${c2[6]} | Cancelled: {c2[7]}")

# Get charter charges
print("\nCHARTER CHARGES:")
print("-" * 80)
cur.execute("""
    SELECT reserve_number, description, amount 
    FROM charter_charges 
    WHERE reserve_number IN ('018841', '018842')
    ORDER BY reserve_number
""")
charges = cur.fetchall()
for ch in charges:
    print(f"{ch[0]} | {ch[1]} | ${ch[2]}")

# Search for any $279.70 payments in January 2025
print("\n" + "=" * 80)
print("ALL $279.70 PAYMENTS IN JANUARY 2025:")
print("=" * 80)
cur.execute("""
    SELECT payment_id, reserve_number, charter_id, amount, payment_date, 
           payment_method, payment_key, notes
    FROM payments 
    WHERE amount = 279.70 
    AND payment_date >= '2025-01-01' 
    AND payment_date < '2025-02-01'
    ORDER BY payment_date
""")
jan_payments = cur.fetchall()
for p in jan_payments:
    print(f"Payment {p[0]} | Res: {p[1]} | Charter: {p[2]} | ${p[3]} | {p[4]}")
    print(f"  Method: {p[5]} | Key: {p[6]}")
    if p[7]:
        print(f"  Notes: {p[7]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
