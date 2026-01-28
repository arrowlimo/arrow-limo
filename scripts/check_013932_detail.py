import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

print("Checking reserve 013932 after credit ledger fix:")
print("=" * 60)

# Payment count and sum
cur.execute('''
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE reserve_number = '013932'
    AND ABS(amount - 774.00) < 0.01
''')
r = cur.fetchone()
print(f"Payment records:  {r[0]} payments")
print(f"Payment sum:      ${r[1]:,.2f}")
print()

# Charter amounts
cur.execute('''
    SELECT total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = '013932'
''')
r = cur.fetchone()
print(f"Charter due:      ${r[0]:,.2f}")
print(f"Charter paid:     ${r[1]:,.2f}")
print(f"Charter balance:  ${r[2]:,.2f}")
print()

# Credit ledger
cur.execute('''
    SELECT credit_amount, remaining_balance
    FROM charter_credit_ledger
    WHERE source_reserve_number = '013932'
''')
r = cur.fetchone()
if r:
    print(f"Credit amount:    ${r[0]:,.2f}")
    print(f"Credit remaining: ${r[1]:,.2f}")
else:
    print("No credit ledger entry found")

print()
print("Analysis:")
print("-" * 60)
print("The credit ledger fix reduced charter.paid_amount from $16,254")
print("down to $774 (correct), but left the 21 payment RECORDS in place.")
print()
print("These 20 extra payment records should be DELETED because:")
print("  1. LMS shows only 1 payment for reserve 013932")
print("  2. They have payment_key=NULL (no source)")
print("  3. They were created 2025-08-05 (bad import)")
print("  4. They don't represent real payments")
