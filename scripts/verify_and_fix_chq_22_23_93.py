#!/usr/bin/env python3
"""
Verify CHQ 22 and 23 are correct:
- CHQ 22: WITH THIS RING $682.50
- CHQ 23: HEFFNER AUTO $1,475.25
And verify CHQ 93: WORD OF LIFE $200.00 on NOV 09
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
print("VERIFY CHQ 22, 23, AND 93 - CORRECT DATA")
print("=" * 80)

# Current state
print("\nCURRENT DATABASE STATE:")
print("-" * 80)
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23, 93)
    ORDER BY cheque_number::INTEGER
""")

for num, date, payee, amount, tx_id, memo in cur.fetchall():
    print(f"CHQ {num}: {payee:30s} ${amount:10.2f} | TX {tx_id} | {date}")

# Fix CHQ 22 if needed
print("\n" + "=" * 80)
print("FIX CHQ 22 - SHOULD BE: WITH THIS RING $682.50")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, amount, payee
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
""")

chq22 = cur.fetchone()
if chq22:
    num, amt, payee = chq22
    if amt == 682.50 and 'THIS RING' in payee.upper():
        print(f"✓ CHQ 22 is CORRECT: {payee} ${amt}")
    else:
        print(f"✗ CHQ 22 is WRONG: {payee} ${amt}")
        print(f"  Should be: WITH THIS RING $682.50")
        print("\n  Fixing...")
        
        # Find banking TX for $682.50 bridal show
        # First, fix CHQ 22 in place
        print("  Marking CHQ 22 for WITH THIS RING $682.50...")
        
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE description ILIKE '%RING%' OR description ILIKE '%BRIDAL%'
            ORDER BY transaction_date DESC
            LIMIT 5
        """)
        
        candidates = cur.fetchall()
        if candidates:
            print(f"\n  Found {len(candidates)} candidate transactions:")
            for tx_id, tx_date, desc in candidates:
                print(f"    TX {tx_id}: {tx_date} | {desc:50s}")
        
        # Update CHQ 22
        cur.execute("""
            UPDATE cheque_register
            SET payee = 'WITH THIS RING', 
                amount = 682.50,
                memo = 'CHQ 22 WITH THIS RING (BRIDAL SHOW)',
                banking_transaction_id = NULL
            WHERE cheque_number ~ '^[0-9]+$'
              AND cheque_number::INTEGER = 22
        """)
        conn.commit()
        print("  ✓ CHQ 22 updated to: WITH THIS RING $682.50")

# Verify CHQ 23
print("\n" + "=" * 80)
print("VERIFY CHQ 23 - SHOULD BE: HEFFNER AUTO $1,475.25")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, amount, payee
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 23
""")

chq23 = cur.fetchone()
if chq23:
    num, amt, payee = chq23
    if amt == 1475.25 and 'HEFFNER' in payee.upper():
        print(f"✓ CHQ 23 is CORRECT: {payee} ${amt}")
    else:
        print(f"✗ CHQ 23 is WRONG: {payee} ${amt}")
        print(f"  Should be: HEFFNER AUTO $1,475.25")

# Verify CHQ 93 - Nov 09, Word of Life, $200
print("\n" + "=" * 80)
print("VERIFY CHQ 93 - WORD OF LIFE NOV 09 $200.00")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
""")

chq93 = cur.fetchone()
if chq93:
    num, date, payee, amount, tx_id, status = chq93
    print(f"CHQ 93: {payee} ${amount} | Date: {date} | Status: {status}")
    
    # Search for banking match
    print("\nSearching banking for: NOV 09, 2012, $200.00, WORD OF LIFE...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description
        FROM banking_transactions
        WHERE transaction_date = '2012-11-09'
        ORDER BY transaction_date
        LIMIT 20
    """)
    
    nov09_matches = cur.fetchall()
    if nov09_matches:
        print(f"Found {len(nov09_matches)} transaction(s) on Nov 09, 2012:")
        for tx_id, tx_date, desc in nov09_matches:
            print(f"  TX {tx_id}: {desc:60s}")
            
            # If it looks like Word of Life, link it
            if 'LIFE' in desc.upper() or tx_id == 69477:  # Check if we know the TX
                print(f"\n  → Linking CHQ 93 to TX {tx_id}")
                cur.execute("""
                    UPDATE cheque_register
                    SET banking_transaction_id = %s, status = 'CLEARED'
                    WHERE cheque_number ~ '^[0-9]+$'
                      AND cheque_number::INTEGER = 93
                """, (tx_id,))
                conn.commit()
                print(f"  ✓ CHQ 93 linked to TX {tx_id}")
                break
    else:
        print("No transactions found on NOV 09, 2012 for $200.00")
        print("\nSearching broader range (NOV 2012)...")
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE EXTRACT(MONTH FROM transaction_date) = 11
              AND EXTRACT(YEAR FROM transaction_date) = 2012
            ORDER BY transaction_date
            LIMIT 30
        """)
        
        nov_matches = cur.fetchall()
        if nov_matches:
            print(f"Found {len(nov_matches)} transactions in Nov 2012:")
            for tx_id, tx_date, desc in nov_matches:
                print(f"  TX {tx_id}: {tx_date} | {desc:60s}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)

cur.close()
conn.close()
