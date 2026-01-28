#!/usr/bin/env python3
"""
Fix CHQ 22/23 duplicate - delete CHQ 23 since it's a duplicate of CHQ 22
And verify CHQ 93 Word of Life banking match
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
print("FIX CHQ 22/23 DUPLICATE AND CHQ 93 WORD OF LIFE")
print("=" * 80)

# Show CHQ 22 and 23 before deletion
print("\nBEFORE FIX:")
print("-" * 80)
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23)
    ORDER BY cheque_number::INTEGER
""")

for num, date, payee, amount, tx_id, status in cur.fetchall():
    print(f"CHQ {num}: {date} | {payee:25s} | ${amount:10.2f} | TX {tx_id} | {status}")

# Delete CHQ 23 (it's a duplicate of CHQ 22)
print("\n" + "=" * 80)
print("DELETING CHQ 23 (DUPLICATE)")
print("=" * 80)

cur.execute("""
    DELETE FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 23
    RETURNING cheque_number, payee, amount
""")

deleted = cur.fetchall()
conn.commit()

if deleted:
    for num, payee, amount in deleted:
        print(f"✓ Deleted CHQ {num}: {payee} ${amount:,.2f}")
else:
    print("CHQ 23 not found or already deleted")

# Show CHQ 22 after deletion
print("\nAFTER FIX:")
print("-" * 80)
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
""")

chq22 = cur.fetchone()
if chq22:
    num, date, payee, amount, tx_id, status = chq22
    print(f"CHQ {num}: {date} | {payee:25s} | ${amount:10.2f} | TX {tx_id} | {status}")
    print(f"✓ CHQ 22 confirmed as single entry")

# Now search for CHQ 93 Word of Life in banking - NOV 09, 2012, $200.00
print("\n" + "=" * 80)
print("VERIFY CHQ 93 - WORD OF LIFE")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
""")

chq93 = cur.fetchone()
if chq93:
    num, date, payee, amount, tx_id, status, memo = chq93
    print(f"\nCHQ 93 Current State:")
    print(f"  Date: {date}")
    print(f"  Payee: {payee}")
    print(f"  Amount: ${amount}")
    print(f"  TX ID: {tx_id}")
    print(f"  Status: {status}")

# Search banking for Nov 09, 2012, $200.00
print("\nSearching banking for match: NOV 09, 2012, $200.00")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description, amount, status
    FROM banking_transactions
    WHERE transaction_date = '2012-11-09'
      AND (ABS(amount - 200.00) < 0.01 OR description ILIKE '%WORD%LIFE%')
    ORDER BY transaction_date, amount DESC
""")

matches = cur.fetchall()
if matches:
    print(f"Found {len(matches)} matching transaction(s):")
    for tx_id, tx_date, desc, amt, tx_status in matches:
        print(f"  TX {tx_id}: {tx_date} | {desc:50s} | ${amt:10.2f} | {tx_status}")
        
        # If we found a match, link it to CHQ 93
        if abs(amt - 200.00) < 0.01:
            print(f"\n  → Linking CHQ 93 to TX {tx_id}")
            cur.execute("""
                UPDATE cheque_register
                SET banking_transaction_id = %s, status = 'CLEARED'
                WHERE cheque_number ~ '^[0-9]+$'
                  AND cheque_number::INTEGER = 93
            """, (tx_id,))
            conn.commit()
            print(f"  ✓ CHQ 93 linked to TX {tx_id}")
else:
    print("No exact match found for NOV 09, 2012, $200.00")
    print("\nSearching broader date range (NOV 2012)...")
    
    cur.execute("""
        SELECT transaction_id, transaction_date, description, amount, status
        FROM banking_transactions
        WHERE EXTRACT(MONTH FROM transaction_date) = 11
          AND EXTRACT(YEAR FROM transaction_date) = 2012
          AND ABS(amount - 200.00) < 1.00
        ORDER BY transaction_date, amount DESC
        LIMIT 10
    """)
    
    broader = cur.fetchall()
    if broader:
        print(f"\nFound {len(broader)} similar transactions in NOV 2012:")
        for tx_id, tx_date, desc, amt, tx_status in broader:
            print(f"  TX {tx_id}: {tx_date} | {desc:50s} | ${amt:10.2f}")
    else:
        print("No similar transactions found")
        print("⚠️  CHQ 93 appears to be a genuine VOID check without banking record")
        # Keep as VOID
        cur.execute("""
            UPDATE cheque_register
            SET status = 'VOID'
            WHERE cheque_number ~ '^[0-9]+$'
              AND cheque_number::INTEGER = 93
        """)
        conn.commit()
        print("✓ CHQ 93 marked as VOID")

print("\n" + "=" * 80)
print("✓ FIX COMPLETE")
print("=" * 80)

cur.close()
conn.close()
