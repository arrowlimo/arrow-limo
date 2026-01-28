#!/usr/bin/env python3
"""Link CHQ 22 WITH THIS RING to correct banking TX"""

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
print("LINK CHQ 22 WITH THIS RING TO BANKING TX")
print("=" * 80)

# Find banking TX for bridal show ~$682.50
print("\nSearching for WITH THIS RING bridal show transaction...")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%RING%' 
       OR description ILIKE '%BRIDAL%'
       OR description ILIKE '%GALA%'
    ORDER BY transaction_date DESC
    LIMIT 5
""")

matches = cur.fetchall()
if matches:
    print(f"Found {len(matches)} matching transactions:")
    for tx_id, tx_date, desc in matches:
        print(f"  TX {tx_id}: {tx_date} | {desc}")
        
        # Use the first match (most recent)
        if "RING" in desc.upper() or "GALA" in desc.upper():
            print(f"\n✓ Using TX {tx_id} for CHQ 22")
            cur.execute("""
                UPDATE cheque_register
                SET banking_transaction_id = %s,
                    status = 'CLEARED'
                WHERE cheque_number ~ '^[0-9]+$'
                  AND cheque_number::INTEGER = 22
            """, (tx_id,))
            conn.commit()
            print(f"✓ CHQ 22 linked to TX {tx_id}")
            break
else:
    print("No exact match found")
    print("\nChecking all Sep 2012 transactions for ~$682.50...")
    
    cur.execute("""
        SELECT transaction_id, transaction_date, description
        FROM banking_transactions
        WHERE EXTRACT(MONTH FROM transaction_date) = 9
          AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date
        LIMIT 20
    """)
    
    sep_trans = cur.fetchall()
    print(f"\nSep 2012 transactions ({len(sep_trans)} total):")
    for tx_id, tx_date, desc in sep_trans:
        print(f"  TX {tx_id}: {tx_date} | {desc}")

# Final verification
print("\n" + "=" * 80)
print("CHQ 22 FINAL STATE")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
""")

chq22 = cur.fetchone()
if chq22:
    num, chq_date, payee, amount, tx_id, status = chq22
    tx_str = f"TX {tx_id}" if tx_id else "NO TX"
    print(f"CHQ {num}: {payee} ${amount} ({chq_date}) | {tx_str} | {status}")

cur.close()
conn.close()
