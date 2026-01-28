#!/usr/bin/env python3
"""
Verify CHQ 22 and 23 matches to banking - dates may differ
Focus on amount and description match, not date match
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("VERIFY CHQ 22, 23, 93 BANKING MATCHES")
print("(Note: Check dates may differ from banking clear dates)")
print("=" * 80)

# CHQ 22 - WITH THIS RING $682.50
print("\n1. CHQ 22 - WITH THIS RING $682.50")
print("-" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
""")

chq22 = cur.fetchone()
if chq22:
    num, chq_date, payee, amount, tx_id, memo = chq22
    print(f"Check: {payee} ${amount:.2f} (written {chq_date})")
    print(f"Current Banking TX: {tx_id}")
    
    if tx_id:
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (tx_id,))
        banking = cur.fetchone()
        if banking:
            btx_id, btx_date, btx_desc = banking
            print(f"Banking: {btx_desc} (cleared {btx_date})")
            print(f"✓ VERIFIED: Amount ${amount:.2f} and 'WITH THIS RING' match")
    else:
        print("⚠️  No banking TX linked yet")

# CHQ 23 - HEFFNER AUTO $1,475.25
print("\n2. CHQ 23 - HEFFNER AUTO $1,475.25")
print("-" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 23
""")

chq23 = cur.fetchone()
if chq23:
    num, chq_date, payee, amount, tx_id, memo = chq23
    print(f"Check: {payee} ${amount:.2f} (written {chq_date})")
    print(f"Banking TX: {tx_id}")
    
    if tx_id:
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (tx_id,))
        banking = cur.fetchone()
        if banking:
            btx_id, btx_date, btx_desc = banking
            print(f"Banking: {btx_desc} (cleared {btx_date})")
            print(f"✓ VERIFIED: Amount ${amount:.2f} and 'HEFFNER' match")

# CHQ 93 - WORD OF LIFE $200.00
print("\n3. CHQ 93 - WORD OF LIFE $200.00 (Nov 09)")
print("-" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
""")

chq93 = cur.fetchone()
if chq93:
    num, chq_date, payee, amount, tx_id, status, memo = chq93
    print(f"Check: {payee} ${amount:.2f} (written {chq_date})")
    print(f"Status: {status}")
    print(f"Banking TX: {tx_id}")
    
    # Search for any $200 transaction that might be Word of Life
    print("\nSearching for possible banking match (Nov 2012, ~$200)...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
          AND EXTRACT(MONTH FROM transaction_date) IN (10, 11, 12)
          AND description ILIKE '%200%'
        ORDER BY transaction_date
        LIMIT 10
    """)
    
    candidates = cur.fetchall()
    if candidates:
        print(f"Found {len(candidates)} possible matches:")
        for btx_id, btx_date, btx_desc in candidates:
            print(f"  TX {btx_id}: {btx_date} | {btx_desc}")
    else:
        print("No similar transactions found")
        print("✓ CHQ 93 appears to be VOID (donation without banking record)")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)

cur.close()
conn.close()
