import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("LINKING DAVID RICHARD E-TRANSFER TO CHARTER 17061:\n")
print("=" * 100)

# The e-transfer: Trans 28906 on Oct 10, 2023 for $630 from DAVID RICHARD
# The payment: Payment 24723 for reserve 018172 (charter 17061)
# Need to: Update banking_transactions.reconciled_payment_id = 24723

print("\nBEFORE UPDATE:")
print("-" * 100)
cur.execute("""
    SELECT transaction_id, transaction_date, credit_amount, description, reconciled_payment_id
    FROM banking_transactions
    WHERE transaction_id = 28906
""")
before = cur.fetchone()
if before:
    trans_id, date, amount, desc, rec_id = before
    print(f"Banking Trans {trans_id}: {date} | ${amount:.2f} | {desc[:80]}")
    print(f"  Current reconciled_payment_id: {rec_id}")

print("\nUpdating...\n")

# Update the banking transaction to link it to the payment
cur.execute("""
    UPDATE banking_transactions
    SET reconciled_payment_id = 24723
    WHERE transaction_id = 28906
""")

conn.commit()

print("AFTER UPDATE:")
print("-" * 100)
cur.execute("""
    SELECT transaction_id, transaction_date, credit_amount, description, reconciled_payment_id
    FROM banking_transactions
    WHERE transaction_id = 28906
""")
after = cur.fetchone()
if after:
    trans_id, date, amount, desc, rec_id = after
    print(f"Banking Trans {trans_id}: {date} | ${amount:.2f} | {desc[:80]}")
    print(f"  ✅ reconciled_payment_id: {rec_id}")

print("\n\nVerification - Payment and Charter:")
print("-" * 100)
cur.execute("""
    SELECT p.payment_id, p.reserve_number, p.amount, p.payment_date, p.payment_method,
           c.charter_id, c.charter_date, c.total_amount_due, c.paid_amount, c.notes
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.payment_id = 24723
""")

verify = cur.fetchone()
if verify:
    p_id, reserve, p_amount, p_date, p_method, c_id, c_date, c_total, c_paid, c_notes = verify
    print(f"Payment {p_id}: {reserve} | ${p_amount:.2f} | {p_date}")
    print(f"  Method: {p_method}")
    print(f"Charter {c_id}: {c_date} | Total: ${c_total:.2f} | Paid: ${c_paid:.2f}")
    print(f"  Notes: {c_notes[:100]}")

print("\n✅ LINKING COMPLETE!")
print("   David Richard's $630 e-transfer (Oct 10, 2023) is now linked to")
print("   Payment 24723 for Charter 17061 (Oct 17, 2023)")

cur.close()
conn.close()
