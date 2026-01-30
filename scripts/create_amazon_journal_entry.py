#!/usr/bin/env python3
"""
Create journal entry for Amazon invoices paid by David.
Add $8,617.98 to GL 2020 (Notes Payable - David)
"""
import os, psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*70)
print("CREATING JOURNAL ENTRY FOR AMAZON INVOICES")
print("="*70 + "\n")

amazon_amount = 8617.98
txn_date = datetime.now().date()
description = "Amazon invoices for vehicle maintenance/repairs/parts (2022-2025) - David payment"

print(f"Adding $8,617.98 to GL 2020 (Notes Payable - David)")
print(f"Date: {txn_date}")
print(f"Description: {description}\n")

# Get next journal_id
cur.execute("SELECT COALESCE(MAX(journal_id), 0) + 1 FROM journal")
next_id = cur.fetchone()[0]

# Debit GL 5300 (Office Equipment/Supplies)
cur.execute("""
    INSERT INTO journal (
        journal_id, "Date", "Account", "Name", "Memo/Description", "Debit", "Credit"
    ) VALUES (
        %s, %s, '5300', 'Office Equipment & Supplies', %s, %s, NULL
    )
""", (next_id, txn_date, description, amazon_amount))

print(f"✅ DR GL 5300 Office Equipment: ${amazon_amount:,.2f} (journal id: {next_id})")

# Credit GL 2020 (Notes Payable - David)
next_id += 1
cur.execute("""
    INSERT INTO journal (
        journal_id, "Date", "Account", "Name", "Memo/Description", "Debit", "Credit"
    ) VALUES (
        %s, %s, '2020', 'Notes Payable - David', %s, NULL, %s
    )
""", (next_id, txn_date, description, amazon_amount))

print(f"✅ CR GL 2020 Notes Payable - David: ${amazon_amount:,.2f} (journal id: {next_id})")

conn.commit()

# Get updated GL 2020 balance
cur.execute("""
    SELECT 
        COALESCE(SUM("Credit"), 0) - COALESCE(SUM("Debit"), 0) as balance
    FROM journal
    WHERE "Account" = '2020'
""")
gl_2020_balance = cur.fetchone()[0]

print(f"\n✅ JOURNAL ENTRY CREATED")
print(f"   GL 2020 Total Balance Owed to David: ${gl_2020_balance:,.2f}")
print("="*70 + "\n")

conn.close()
