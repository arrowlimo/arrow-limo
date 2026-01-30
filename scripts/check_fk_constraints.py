#!/usr/bin/env python3
"""Check foreign key constraints for deletion."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Check foreign key constraints
print("FOREIGN KEY CONSTRAINTS:")
cur.execute("""
    SELECT constraint_name, table_name, column_name
    FROM information_schema.key_column_usage
    WHERE table_name = 'banking_transactions' AND constraint_name LIKE 'fk_%'
""")
for row in cur.fetchall():
    print(f"  {row}")

# Check if HEFFNER NULL receipts are referenced
print("\nHEFFNER NULL receipts referenced in banking_transactions:")
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount
    FROM receipts r
    WHERE r.vendor_name LIKE 'HEFFNER%' AND r.gross_amount IS NULL
    AND EXISTS (SELECT 1 FROM banking_transactions bt WHERE bt.receipt_id = r.receipt_id)
""")
for row in cur.fetchall():
    print(f"  Receipt {row[0]}: {row[1]} - {row[2]}")

cur.close()
conn.close()
