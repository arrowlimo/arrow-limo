#!/usr/bin/env python3
"""
Compare Scotia Bank Oct 1, 2012 database transactions with actual statement.
Based on statement screenshot showing Sept 28 - Oct 31, 2012.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("SCOTIA BANK OCT 1, 2012 - DATABASE VS ACTUAL STATEMENT")
print("=" * 80)

# Get ALL Scotia transactions for late Sept to early Oct 2012
print("\nALL SCOTIA BANK TRANSACTIONS (Sept 28 - Oct 5, 2012):")
print("-" * 80)

cur.execute("""
    SELECT transaction_date, transaction_id,
           COALESCE(debit_amount, 0) as debit,
           COALESCE(credit_amount, 0) as credit,
           description
    FROM banking_transactions
    WHERE bank_id = 2
      AND transaction_date >= '2012-09-28' AND transaction_date <= '2012-10-05'
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"Found {len(transactions)} transactions\n")

for date, tx_id, debit, credit, desc in transactions:
    if debit > 0:
        print(f"{date} | TX {tx_id:6d} | DEBIT  ${debit:>10,.2f} | {desc}")
    else:
        print(f"{date} | TX {tx_id:6d} | CREDIT ${credit:>10,.2f} | {desc}")

# Focus on Oct 1, 2012
print("\n" + "=" * 80)
print("OCTOBER 1, 2012 ONLY:")
print("=" * 80)

cur.execute("""
    SELECT transaction_id,
           COALESCE(debit_amount, 0) as debit,
           COALESCE(credit_amount, 0) as credit,
           description
    FROM banking_transactions
    WHERE bank_id = 2
      AND transaction_date = '2012-10-01'
    ORDER BY transaction_id
""")

oct1_transactions = cur.fetchall()
print(f"\nDatabase has {len(oct1_transactions)} Oct 1, 2012 transactions:\n")

for tx_id, debit, credit, desc in oct1_transactions:
    if debit > 0:
        print(f"TX {tx_id:6d} | DEBIT  ${debit:>10,.2f} | {desc}")
    else:
        print(f"TX {tx_id:6d} | CREDIT ${credit:>10,.2f} | {desc}")

print("\n" + "=" * 80)
print("VERIFICATION NEEDED:")
print("=" * 80)
print("\nFrom the statement screenshot, check if these transactions appear:")
print("\n1. Cheques (CHQ 50, 51, 57, 59, 61)")
print("2. CENTEX purchases (~$54, $70, $154)")
print("3. Liquor Barn $173.02")
print("4. GNC $70.01")
print("5. PETRO CANADA $110.20")
print("6. ACE TRUCK RENTAL $2,695.40")
print("7. Card deposits (Vcard/Mcard)")
print("8. OD FEE $5.00")
print("\nDo you see these on the statement for Oct 1, 2012?")

cur.close()
conn.close()
