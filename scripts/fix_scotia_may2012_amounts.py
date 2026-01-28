#!/usr/bin/env python3
"""
Fix May 2012 Scotia Bank amounts - checking all for column separator errors
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*100)
print("CHECKING MAY 2012 SCOTIA BANK TRANSACTIONS FOR COLUMN ERRORS")
print("="*100)

# May 2012 corrections based on proper column reading
corrections = [
    # May 31, 2012 - Page 1
    (54713, 'debit', 300.00, 'DEBIT MEMO TRANSFER 9324 - was 30000, should be 300.00'),
    (54714, 'credit', 770.00, 'TRANSFER TO DEPOSIT - was 77000, should be 770.00'),
    (54715, 'debit', 750.00, 'DEBIT MEMO DRAFT ORDER PURCHASE - was 75000, should be 750.00'),
    (54717, 'credit', 460.00, 'DEPOSIT MCARD - was 46000, should be 460.00'),
    (54718, 'credit', 175.00, 'DEPOSIT DEBITCD - was 17500, should be 175.00'),
    (54719, 'credit', 205.00, 'DEPOSIT DEBITCD - was 20500, should be 205.00'),
    (54720, 'credit', 455.00, 'DEPOSIT MCARD - was 45500, should be 455.00'),
    (54721, 'debit', 400.00, 'CHASE FORWARD - was 40000, should be 400.00'),
    (54722, 'debit', 41.00, 'POS PURCHASE MOHAWK - was 4100, should be 41.00'),
    (54723, 'debit', 66.01, 'POS PURCHASE CENTEX - was 6601, should be 66.01'),
    (54724, 'credit', 1133.00, 'DEPOSIT MCARD - was 113300, should be 1133.00'),
    (54725, 'credit', 402.25, 'DEPOSIT DEBITCD - was 40225, should be 402.25'),
    (54726, 'credit', 187.50, 'DEPOSIT VISA - was 18750, should be 187.50'),
    (54727, 'credit', 2025.00, 'DEPOSIT MCARD - was 202500, should be 2025.00'),
    
    # May 31, 2012 - Page 2
    (54728, 'debit', 38.84, 'POS PURCHASE BEST BUY - was 3884, should be 38.84'),
    (54729, 'debit', 34.10, 'POS PURCHASE MOHAWK - was 3410, should be 34.10'),
    (54730, 'debit', 56.50, 'POS PURCHASE CENTEX - was 5650, should be 56.50'),
    (54731, 'debit', 25.89, 'POS PURCHASE 604 LB 67TH - was 2589, should be 25.89'),
    (54732, 'debit', 20.42, 'POS PURCHASE RED DEER PL - was 2042, should be 20.42'),
    (54733, 'debit', 328.12, 'POS PURCHASE CENTEX - was 32812, should be 328.12'),
    (54734, 'credit', 175.00, 'DEPOSIT MCARD - was 17500, should be 175.00'),
    (54735, 'credit', 2412.50, 'MISC PAYMENT AMEX - was 241250, should be 2412.50'),
    (54736, 'debit', 57.00, 'POS PURCHASE CENTEX - was 5700, should be 57.00'),
    (54737, 'credit', 540.00, 'DEPOSIT MCARD - was 54000, should be 540.00'),
    (54738, 'credit', 1095.50, 'DEPOSIT VISA - was 109550, should be 1095.50'),
    (54739, 'debit', 2500.00, 'CASH TO CUST OTHER - was 250000, should be 2500.00'),
    (54740, 'debit', 112.50, 'SERVICE CHARGE - was 11250, should be 112.50'),
]

print(f"\nFound {len(corrections)} transactions needing correction")
print("-"*100)
for tid, side, new_amount, note in corrections[:5]:
    print(f"ID {tid}: {note}")
print(f"... and {len(corrections)-5} more")

response = input("\nApply all corrections? (yes/no): ")
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
    print(f"  ✓ Fixed {tid}")

conn.commit()
print(f"\n[OK] Fixed {len(corrections)} May 2012 transactions")

# Summary
cur.execute("""
    SELECT 
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions 
    WHERE transaction_id BETWEEN 54713 AND 54740
""")
debits, credits = cur.fetchone()
print(f"\nMay 2012 Corrected Totals:")
print(f"  Total Debits:  ${debits:,.2f}")
print(f"  Total Credits: ${credits:,.2f}")
print(f"  Net:           ${credits - debits:,.2f}")

cur.close()
conn.close()
