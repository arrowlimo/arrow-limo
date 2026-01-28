#!/usr/bin/env python3
"""Verify final counts and regenerate workbooks."""

import psycopg2
import pandas as pd
import os

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("FINAL DATABASE STATUS - AFTER IMPORTING 2 MISSING SCOTIA TRANSACTIONS")
print("=" * 100)

# Verify counts
cur.execute("SELECT COUNT(*) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date)=2012")
total_2012_receipts = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date)=2012 AND mapped_bank_account_id=2")
scotia_receipts = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE EXTRACT(YEAR FROM transaction_date)=2012 AND account_number='903990106011'")
scotia_banking = cur.fetchone()[0]

print(f"\n2012 RECEIPTS:")
print(f"  Total: {total_2012_receipts}")
print(f"  Scotia (account_id 2): {scotia_receipts}")

print(f"\n2012 BANKING:")
print(f"  Scotia (account 903990106011): {scotia_banking}")

print(f"\n" + "=" * 100)
print("VERIFICATION: File vs Database Match")
print("=" * 100)

# Load the Scotia file to verify
df_file = pd.read_excel(r"L:\limo\data\2012_scotia_transactions_for_editing.xlsx")
df_file['year'] = pd.to_datetime(df_file['date'], errors='coerce').dt.year
df_file_2012 = df_file[df_file['year'] == 2012]

print(f"\nScotia editing file:")
print(f"  Total rows: {len(df_file)}")
print(f"  2012 rows: {len(df_file_2012)}")

print(f"\nDatabase Scotia 2012: {scotia_banking}")
print(f"File Scotia 2012: {len(df_file_2012)}")

if scotia_banking == len(df_file_2012):
    print(f"\n✓ MATCH! Database and file are synchronized")
else:
    diff = scotia_banking - len(df_file_2012)
    print(f"\n⚠️  Difference: {diff} transactions")

cur.close()
conn.close()

print("\n" + "=" * 100)
