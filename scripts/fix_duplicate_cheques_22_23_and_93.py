#!/usr/bin/env python3
"""
Investigate CHQ 22/23 potential duplicate and CHQ 93 Word of Life banking match
User suspected typing error: CHQ 22 and 23 have same amount/payee but different numbers
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("INVESTIGATE CHQ 22/23 DUPLICATE AND CHQ 93 WORD OF LIFE")
print("=" * 80)

# Check CHQ 22 and 23
print("\n1. CHECK CHQ 22 and CHQ 23")
print("-" * 80)
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23)
    ORDER BY cheque_number::INTEGER
""")

chq22_23 = cur.fetchall()
for num, date, payee, amount, tx_id, status, memo in chq22_23:
    print(f"CHQ {num}: {date} | {payee:25s} | ${amount:10.2f} | TX {tx_id} | {status}")
    print(f"       Memo: {memo}")

if len(chq22_23) == 2:
    chq22 = chq22_23[0]
    chq23 = chq22_23[1]
    
    # Check if same amount and payee (but different cheque numbers)
    if chq22[3] == chq23[3] and chq22[2] == chq23[2]:
        print("\n⚠️  DUPLICATE DETECTED: CHQ 22 and 23 have SAME amount and payee!")
        print(f"   Amount: ${chq22[3]}")
        print(f"   Payee: {chq22[2]}")
        print(f"   CHQ 22 TX: {chq22[4]}")
        print(f"   CHQ 23 TX: {chq23[4]}")
        print("\n   ACTION: CHQ 23 should be DELETED (it's a duplicate of CHQ 22)")

# Check CHQ 93 - Word of Life
print("\n\n2. CHECK CHQ 93 - WORD OF LIFE")
print("-" * 80)
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
""")

chq93 = cur.fetchone()
if chq93:
    num, date, payee, amount, tx_id, status, memo = chq93
    print(f"CHQ 93: {date} | {payee:25s} | ${amount:10.2f} | TX {tx_id} | {status}")
    print(f"       Memo: {memo}")
else:
    print("CHQ 93 not found")

# Search banking for Nov 09, 200.00 - WORD OF LIFE or similar
print("\n\n3. SEARCH BANKING FOR CHQ 93 MATCH (NOV 09, $200.00)")
print("-" * 80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, amount, 
           cleared_amount, status, account_number
    FROM banking_transactions
    WHERE transaction_date = '2012-11-09'
      AND ABS(amount - 200.00) < 0.01
      OR (description ILIKE '%WORD%OF%LIFE%' OR description ILIKE '%LIFE%')
    ORDER BY transaction_date DESC, amount DESC
    LIMIT 20
""")

banking_matches = cur.fetchall()
if banking_matches:
    print("Found potential matches:")
    for tx_id, tx_date, desc, amt, cleared_amt, tx_status, acct in banking_matches:
        print(f"TX {tx_id}: {tx_date} | {desc:40s} | ${amt:10.2f} | {tx_status}")
else:
    print("No exact matches found for NOV 09, $200.00")

# Broader search: Nov 2012, $200 amounts
print("\n\n4. BROADER SEARCH: NOV 2012, $200.00 TRANSACTIONS")
print("-" * 80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, amount, status
    FROM banking_transactions
    WHERE EXTRACT(MONTH FROM transaction_date) = 11
      AND EXTRACT(YEAR FROM transaction_date) = 2012
      AND ABS(amount - 200.00) < 0.01
    ORDER BY transaction_date, amount DESC
""")

nov_200 = cur.fetchall()
if nov_200:
    print(f"Found {len(nov_200)} transactions in Nov 2012 for ~$200.00:")
    for tx_id, tx_date, desc, amt, tx_status in nov_200:
        print(f"TX {tx_id}: {tx_date} | {desc:50s} | ${amt:10.2f}")
else:
    print("No transactions found")

print("\n" + "=" * 80)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 80)

# Check if CHQ 23 should be deleted
cur.execute("""
    SELECT COUNT(*) FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23)
""")
chq_count = cur.fetchone()[0]

if chq_count == 2:
    cur.execute("""
        SELECT amount FROM cheque_register
        WHERE cheque_number ~ '^[0-9]+$'
          AND cheque_number::INTEGER IN (22, 23)
    """)
    amounts = [row[0] for row in cur.fetchall()]
    if len(amounts) == 2 and amounts[0] == amounts[1]:
        print("\n✓ CHQ 22 and 23 ARE DUPLICATES")
        print("  ACTION: Delete CHQ 23 (keep CHQ 22 with TX 69370)")

cur.execute("""
    SELECT banking_transaction_id FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
""")
chq93_tx = cur.fetchone()
if chq93_tx and chq93_tx[0] is None:
    print("\n✓ CHQ 93 has NO banking TX ID")
    print("  Need to find Word of Life $200 transaction in banking")
    print("  Check Nov 09, 2012 for $200.00 donation payment")

cur.close()
conn.close()
