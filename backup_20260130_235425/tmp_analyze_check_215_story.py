import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Get the full story for check 215 Welcome Wagon
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        check_number,
        category,
        is_nsf_charge,
        reconciliation_status,
        reconciliation_notes
    FROM banking_transactions 
    WHERE transaction_id IN (60114, 60118, 80594, 57979, 81728)
    ORDER BY transaction_date, transaction_id
""")

rows = cur.fetchall()

print("Complete Check #215 Welcome Wagon Transaction Story:\n")
print("="*150 + "\n")

for i, row in enumerate(rows, 1):
    tx_id, tx_date, desc, debit, credit, balance, check_num, category, is_nsf, status, notes = row
    print(f"{i}. Transaction ID: {tx_id}")
    print(f"   Date: {tx_date}")
    print(f"   Description: {desc}")
    print(f"   Debit: ${debit:.2f}" if debit else f"   Debit: N/A")
    print(f"   Credit: ${credit:.2f}" if credit else f"   Credit: N/A")
    print(f"   Balance after: ${balance:.2f}" if balance else f"   Balance after: N/A")
    print(f"   Check#: {check_num}" if check_num else f"   Check#: N/A")
    print(f"   Category: {category}")
    print(f"   Is NSF Charge: {is_nsf}")
    print(f"   Reconciliation Status: {status}")
    if notes:
        print(f"   Notes: {notes}")
    print()

print("\n" + "="*150)
print("\nSUMMARY - What appears to have happened:")
print("="*150 + "\n")

# Calculate totals
total_debits = sum([r[3] for r in rows if r[3]])
total_credits = sum([r[4] for r in rows if r[4]])

print(f"Total Debits (money out): ${total_debits:.2f}")
print(f"Total Credits (money in): ${total_credits:.2f}")
print(f"Net effect: ${total_debits - total_credits:.2f}\n")

print("Expected sequence for NSF check:")
print("1. Check #215 written for $150.00 (debit)")
print("2. Check returned NSF (credit reversal $150.00)")
print("3. NSF fee charged (debit $12.00)")
print("4. Re-payment made successfully (debit $150.00)\n")

print("What we see in the data:")
for i, row in enumerate(rows, 1):
    tx_id, tx_date, desc, debit, credit, balance, check_num, category, is_nsf, status, notes = row
    amount_str = f"${debit:.2f} debit" if debit else f"${credit:.2f} credit"
    print(f"{i}. {tx_date} - {desc[:50]} - {amount_str}")

cur.close()
conn.close()
