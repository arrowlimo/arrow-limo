import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("CHARTER 016461 - PAYMENT LINKAGE ANALYSIS")
print("=" * 80)

# Get all payments linked to 016461
cur.execute("""
    SELECT payment_id, reserve_number, charter_id, amount, payment_date, 
           payment_method, payment_key, notes
    FROM payments 
    WHERE reserve_number = '016461'
    ORDER BY payment_date
""")
payments = cur.fetchall()

print(f"\nFound {len(payments)} payments linked to reserve 016461")
print(f"Total amount: ${sum(p[3] for p in payments)}")

# LMS shows only 2 payments: $400 (03/04/2022) and $230 (08/24/2022)
correct_payments = []
incorrect_payments = []

for p in payments:
    payment_id, reserve, charter_id, amount, date, method, key, notes = p
    # Check if this matches the LMS payments
    if (amount == 400 and str(date) == '2022-03-04') or (amount == 230 and str(date) == '2022-08-24'):
        correct_payments.append(p)
    else:
        incorrect_payments.append(p)

print("\n" + "=" * 80)
print(f"CORRECT PAYMENTS (match LMS): {len(correct_payments)}")
print("=" * 80)
for p in correct_payments:
    print(f"Payment {p[0]} | ${p[3]} | {p[4]} | Key: {p[6]}")

print("\n" + "=" * 80)
print(f"INCORRECT PAYMENTS (don't match LMS): {len(incorrect_payments)}")
print(f"Total incorrect amount: ${sum(p[3] for p in incorrect_payments)}")
print("=" * 80)
for p in incorrect_payments:
    print(f"Payment {p[0]} | ${p[3]} | {p[4]} | Charter: {p[2]} | Key: {p[6]}")
    if p[7]:
        print(f"  Notes: {p[7][:100]}")

# Check if these payments have other reserve numbers they should belong to
print("\n" + "=" * 80)
print("CHECKING PAYMENT KEYS FOR ACTUAL RESERVE NUMBERS:")
print("=" * 80)

for p in incorrect_payments[:5]:  # Check first 5 as examples
    key = p[6]
    if key and key.startswith('ETR:'):
        # Check banking_transactions for this e-transfer
        txn_id = key.replace('ETR:', '')
        cur.execute("""
            SELECT transaction_id, transaction_date, description, credit_amount
            FROM banking_transactions 
            WHERE transaction_id = %s
        """, (txn_id,))
        bank = cur.fetchone()
        if bank:
            print(f"\nPayment {p[0]} (${p[3]} on {p[4]})")
            print(f"  Banking: Txn {bank[0]} | {bank[1]} | ${bank[3]}")
            print(f"  Desc: {bank[2][:80]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print("Remove incorrect reserve_number='016461' from 14 payments")
print("Keep only the 2 payments that match LMS ($400 on 03/04/2022 and $230 on 08/24/2022)")
print("Total to remove: $6,220 in incorrect linkages")
