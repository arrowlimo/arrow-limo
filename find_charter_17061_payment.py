import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Charter 17061 (Oct 17, 2023, David Richard, $630) - FINDING THE PAYMENT:\n")
print("=" * 100)

# 1. Check payments already linked to this reserve
print("\n1️⃣ PAYMENTS LINKED TO RESERVE 018172:")
print("-" * 100)
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, status, notes
    FROM payments
    WHERE reserve_number = '018172'
    ORDER BY payment_date DESC
""")

payments = cur.fetchall()
print(f"Found {len(payments)} payments linked to this reserve\n")
for p in payments:
    p_id, reserve, amount, date, method, status, notes = p
    print(f"Payment {p_id:6d} | {date} | ${amount:10.2f} | {method:15s} | {status}")
    if notes:
        print(f"  Notes: {notes}")

# 2. Search banking for e-transfer around Oct 17, 2023 for ~$630
print("\n\n2️⃣ BANKING E-TRANSFERS around Oct 17, 2023 ($600-$650):")
print("-" * 100)
cur.execute("""
    SELECT transaction_id, transaction_date, credit_amount, debit_amount, 
           description, reconciled_payment_id
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2023-10-15' AND '2023-10-20'
    AND (
        (credit_amount BETWEEN 600 AND 650)
        OR (debit_amount BETWEEN 600 AND 650)
    )
    ORDER BY transaction_date DESC
""")

banking = cur.fetchall()
print(f"Found {len(banking)} banking transactions\n")
for b in banking:
    trans_id, date, credit, debit, desc, rec_id = b
    amount = credit if credit else debit
    trans_type = "CREDIT (IN)" if credit else "DEBIT (OUT)"
    print(f"Trans {trans_id:8d} | {date} | ${amount:10.2f} ({trans_type})")
    print(f"  Description: {desc[:100]}")
    if rec_id:
        print(f"  Linked to Payment ID: {rec_id}")
    print()

# 3. Search for DAVID or RICHARD in banking Oct 2023
print("\n\n3️⃣ BANKING TRANSACTIONS mentioning DAVID/RICHARD in Oct 2023:")
print("-" * 100)
cur.execute("""
    SELECT transaction_id, transaction_date, credit_amount, debit_amount,
           description, reconciled_payment_id
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2023-10-01' AND '2023-10-31'
    AND (
        description ILIKE '%david%'
        OR description ILIKE '%richard%'
        OR description ILIKE 'CHQ%'  -- checks
    )
    ORDER BY transaction_date DESC
    LIMIT 30
""")

david_banking = cur.fetchall()
print(f"Found {len(david_banking)} transactions\n")
for b in david_banking[:20]:
    trans_id, date, credit, debit, desc, rec_id = b
    amount = credit if credit else debit
    trans_type = "CREDIT" if credit else "DEBIT"
    print(f"Trans {trans_id:8d} | {date} | ${amount:10.2f} ({trans_type:6s}) | {desc[:80]}")

# 4. Check charter payment_status more carefully
print("\n\n4️⃣ CHARTER 17061 PAYMENT DETAILS:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, 
           status, payment_status, notes
    FROM charters
    WHERE charter_id = 17061
""")

charter = cur.fetchone()
if charter:
    cid, reserve, total, paid, status, payment_status, notes = charter
    paid_amt = paid if paid else 0
    print(f"Total Due: ${total:.2f}")
    print(f"Paid Amount: ${paid_amt:.2f}")
    print(f"Status: {status}")
    print(f"Payment Status: {payment_status}")
    print(f"Notes: {notes}")

cur.close()
conn.close()
