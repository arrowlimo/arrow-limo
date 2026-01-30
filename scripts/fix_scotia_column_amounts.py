#!/usr/bin/env python3
"""
Fix Scotia Bank amounts that were incorrectly parsed due to column misalignment
The dotted line separator splits dollars (left) from cents (right)
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*100)
print("FIXING SCOTIA BANK AMOUNT ERRORS - Column Separator Misalignment")
print("="*100)

# Corrections needed based on proper column reading:
# Transaction 54705: 532000 -> 5320.00 (RBC deposit)
# Transaction 54709: 200000 -> 2000.00 (RBM deposit) 
# Transaction 54711: 200000 -> 2000.00 (RBM deposit)
# Need to check all others too

corrections = [
    # Jan 31, 2012 - Page 4
    (54705, 'credit', 5320.00, 'RBC CROSS BRANCH FED RED DEER AB DEPOSIT - was 532000, should be 5320.00'),
    (54706, 'debit', 50.00, 'DRAFT PURCHASE - was 5000, should be 50.00'),
    (54707, 'debit', 112.50, 'SERVICE CHARGE - was 11250, should be 112.50'),
    
    # Mar 30, 2012
    (54708, 'debit', 91.00, 'RBM DEPOSIT - was 9100, should be 91.00'),
    (54709, 'credit', 2000.00, 'RBM DEPOSIT - was 200000, should be 2000.00'),
    (54710, 'debit', 21.50, 'RBM DEPOSIT - was 2150, should be 21.50'),
    (54711, 'credit', 2000.00, 'RBM DEPOSIT - was 200000, should be 2000.00'),
    (54712, 'debit', 112.50, 'SERVICE CHARGE - was 11250, should be 112.50'),
]

print("\nProposed corrections:")
print("-"*100)
for tid, side, new_amount, note in corrections:
    print(f"ID {tid}: {note}")
    
response = input("\nApply these corrections? (yes/no): ")
if response.lower() != 'yes':
    print("Cancelled")
    cur.close()
    conn.close()
    exit()

print("\nApplying corrections...")
for tid, side, new_amount, note in corrections:
    if side == 'debit':
        cur.execute("""
            UPDATE banking_transactions 
            SET debit_amount = %s, credit_amount = 0
            WHERE transaction_id = %s
        """, (new_amount, tid))
    else:
        cur.execute("""
            UPDATE banking_transactions 
            SET credit_amount = %s, debit_amount = 0
            WHERE transaction_id = %s
        """, (new_amount, tid))
    print(f"  ✓ Fixed transaction {tid}: {note}")

conn.commit()
print(f"\n[OK] Fixed {len(corrections)} transactions")

# Show corrected transactions
print("\n" + "="*100)
print("CORRECTED TRANSACTIONS:")
print("="*100)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions 
    WHERE transaction_id BETWEEN 54704 AND 54712
    ORDER BY transaction_id
""")

print("\nID     | Date       | Description                              | Debit    | Credit")
print("-"*100)
for row in cur.fetchall():
    tid, date, desc, debit, credit = row
    print(f"{tid:6} | {date} | {desc[:40]:40} | {debit or 0:8.2f} | {credit or 0:8.2f}")

cur.close()
conn.close()
