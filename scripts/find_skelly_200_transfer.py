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
print("SEARCHING FOR $200 LIAM SKELLY / LIAMJSKELLY5@GMAIL.COM TRANSFER")
print("=" * 80)

# Search payments table for $200 payments
print("\n1. PAYMENTS TABLE - $200 payments (recent):")
print("-" * 80)
cur.execute("""
    SELECT payment_id, reserve_number, charter_id, amount, payment_date, 
           payment_method, payment_key, notes
    FROM payments 
    WHERE amount = 200 
    ORDER BY payment_date DESC 
    LIMIT 30
""")
payments = cur.fetchall()
for p in payments:
    print(f"Payment {p[0]} | Res: {p[1]} | Charter: {p[2]} | ${p[3]} | {p[4]} | {p[5]} | Key: {p[6]}")
    if p[7]:
        print(f"  Notes: {p[7][:100]}")

# Search banking_transactions for Skelly/Liam
print("\n2. BANKING TRANSACTIONS - Skelly/Liam:")
print("-" * 80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount, account_number
    FROM banking_transactions 
    WHERE LOWER(description) LIKE '%skelly%' 
       OR LOWER(description) LIKE '%liam%'
    ORDER BY transaction_date DESC
""")
banking = cur.fetchall()
if banking:
    for b in banking:
        print(f"Txn {b[0]} | {b[1]} | Debit: ${b[3] or 0} | Credit: ${b[4] or 0} | Acct: {b[5]}")
        print(f"  Desc: {b[2]}")
else:
    print("No banking transactions found with Skelly/Liam")

# Search for charter 018841 and 018842 (from calendar data)
print("\n3. CHARTERS 018841 & 018842 (Skelly Liem charters from Sept 2024):")
print("-" * 80)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, client_id, 
           total_amount_due, paid_amount, balance, cancelled
    FROM charters 
    WHERE reserve_number IN ('018841', '018842')
""")
charters = cur.fetchall()
for c in charters:
    print(f"Charter {c[0]} | Res: {c[1]} | Date: {c[2]} | Client: {c[3]}")
    print(f"  Total: ${c[4]} | Paid: ${c[5]} | Balance: ${c[6]} | Cancelled: {c[7]}")

# Get payments for these charters
print("\n4. PAYMENTS FOR CHARTERS 018841 & 018842:")
print("-" * 80)
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, payment_key
    FROM payments 
    WHERE reserve_number IN ('018841', '018842')
    ORDER BY payment_date
""")
charter_payments = cur.fetchall()
for p in charter_payments:
    print(f"Payment {p[0]} | Res: {p[1]} | ${p[2]} | {p[3]} | {p[4]} | Key: {p[5]}")

# Search email_financial_events
print("\n5. EMAIL FINANCIAL EVENTS - Skelly:")
print("-" * 80)
cur.execute("""
    SELECT id, email_date, from_email, subject, event_type, amount, status
    FROM email_financial_events 
    WHERE LOWER(subject) LIKE '%skelly%' 
       OR LOWER(from_email) LIKE '%skelly%'
       OR LOWER(from_email) LIKE '%liamj%'
    ORDER BY email_date DESC
""")
emails = cur.fetchall()
if emails:
    for e in emails:
        print(f"Event {e[0]} | {e[1]} | From: {e[2]}")
        print(f"  Subject: {e[3]}")
        print(f"  Type: {e[4]} | Amount: ${e[5]} | Status: {e[6]}")
else:
    print("No email events found")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("SEARCH COMPLETE")
print("=" * 80)
