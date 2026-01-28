#!/usr/bin/env python3
"""
Find cheque transactions that don't have clear vendor/payee names.
"""

import psycopg2
import os
import re

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("CHEQUES WITHOUT VENDOR/PAYEE NAMES")
print("=" * 80)

# Get all DEBIT cheque transactions
cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description, 
           reconciliation_status,
           CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank
    FROM banking_transactions
    WHERE debit_amount IS NOT NULL
      AND (description ILIKE '%cheque%' OR description ILIKE '%chq%')
      AND reconciliation_status NOT IN ('NSF', 'RETURN', 'QB_DUPLICATE')
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"\nTotal DEBIT cheques (active): {len(transactions)}")

# Categorize by name presence
has_name = []
no_name = []
unclear = []

for tx_id, date, amount, desc, status, bank in transactions:
    desc_upper = desc.upper()
    
    # Remove cheque number patterns
    desc_clean = re.sub(r'\b(CHEQUE|CHQ|CHECK)\s*\d+\b', '', desc_upper, flags=re.IGNORECASE)
    desc_clean = re.sub(r'\b\d{8,}\b', '', desc_clean)  # Remove long numbers
    desc_clean = desc_clean.strip()
    
    # Check if there's a name (letters after cleaning)
    has_letters = re.search(r'[A-Z]{3,}', desc_clean)
    
    if not has_letters:
        no_name.append((tx_id, date, amount, desc, bank))
    elif len(desc_clean) < 10:
        unclear.append((tx_id, date, amount, desc, bank))
    else:
        has_name.append((tx_id, date, amount, desc, bank))

print()
print("=" * 80)
print(f"CATEGORIZATION:")
print("=" * 80)
print(f"  Has clear name: {len(has_name)}")
print(f"  No name (just cheque number): {len(no_name)}")
print(f"  Unclear/short description: {len(unclear)}")

# Show cheques with no name
if no_name:
    print()
    print("=" * 80)
    print(f"CHEQUES WITH NO VENDOR NAME ({len(no_name)}):")
    print("=" * 80)
    for tx_id, date, amount, desc, bank in no_name[:50]:  # Show first 50
        print(f"TX {tx_id:6d} | {date} | {bank:7} | ${amount:>10,.2f} | {desc}")
    
    if len(no_name) > 50:
        print(f"\n... and {len(no_name) - 50} more")

# Show unclear ones
if unclear:
    print()
    print("=" * 80)
    print(f"CHEQUES WITH UNCLEAR/SHORT DESCRIPTIONS ({len(unclear)}):")
    print("=" * 80)
    for tx_id, date, amount, desc, bank in unclear[:30]:  # Show first 30
        print(f"TX {tx_id:6d} | {date} | {bank:7} | ${amount:>10,.2f} | {desc}")
    
    if len(unclear) > 30:
        print(f"\n... and {len(unclear) - 30} more")

# Summary
print()
print("=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"Total cheques needing names: {len(no_name) + len(unclear)}")
print(f"  - No name at all: {len(no_name)}")
print(f"  - Unclear/short: {len(unclear)}")

cur.close()
conn.close()
