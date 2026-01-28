#!/usr/bin/env python3
"""
RESTORE Scotia 2012 expense receipts - WITHOUT preserving receipt_ids (let DB auto-generate)
"""

import pandas as pd
import psycopg2
import sys

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

BACKUP_FILE = "L:/limo/backups/critical_backup_20251210_123930/scotia_2012_receipts_20251210_123930.csv"

print("=" * 80)
print("EMERGENCY RESTORE: Scotia 2012 Expense Receipts")
print("=" * 80)

# Load backup
print(f"\n📂 Loading backup: {BACKUP_FILE}")
df = pd.read_csv(BACKUP_FILE)
print(f"✅ Found {len(df)} receipts to restore")
print(f"   Columns: {list(df.columns)}")

# Connect to database
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Restore each receipt (without receipt_id - let DB auto-generate)
print(f"\n📝 Restoring receipts...")
restored = 0
errors = 0

for idx, row in df.iterrows():
    try:
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, description,
                gross_amount, gst_amount, net_amount, category,
                payment_method, banking_transaction_id,
                mapped_bank_account_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 2)
        """, (
            pd.to_datetime(row['receipt_date']).date(),
            str(row['vendor_name']),
            str(row['description']) if pd.notna(row['description']) else None,
            float(row['gross_amount']) if pd.notna(row['gross_amount']) else 0.0,
            float(row['gst_amount']) if pd.notna(row['gst_amount']) else 0.0,
            float(row['net_amount']) if pd.notna(row['net_amount']) else 0.0,
            str(row['category']) if pd.notna(row['category']) else None,
            str(row['payment_method']) if pd.notna(row['payment_method']) else 'unknown',
            int(row['banking_transaction_id']) if pd.notna(row['banking_transaction_id']) else None
        ))
        restored += 1
        
        if restored % 100 == 0:
            print(f"   Restored {restored} receipts...")
            conn.commit()
    except Exception as e:
        errors += 1
        if errors <= 10:
            print(f"⚠️  Row {idx}: {e}")
        if errors == 1:
            # Rollback and stop on first error
            conn.rollback()
            print(f"\n❌ Error encountered. Stopping restore.")
            print(f"   Error: {e}")
            cur.close()
            conn.close()
            sys.exit(1)

conn.commit()

print(f"\n✅ RESTORE COMPLETE:")
print(f"   Restored: {restored}")
print(f"   Errors: {errors}")

# Verify
cur.execute("""
    SELECT COUNT(*) FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
""")
count = cur.fetchone()[0]
print(f"\n✅ Scotia 2012 receipts now in database: {count}")

cur.close()
conn.close()
