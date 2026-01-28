#!/usr/bin/env python3
"""Check what tables exist related to receipts"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Check for split tables
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE 'receipt%'
    ORDER BY table_name
""")

print("\n" + "=" * 60)
print("RECEIPT-RELATED TABLES IN DATABASE")
print("=" * 60)

tables = cur.fetchall()
for row in tables:
    print(f"  ✓ {row[0]}")

if not tables:
    print("  (none found)")

# Also check for the split migration tables
print("\n" + "=" * 60)
print("CHECKING FOR SPLIT RECEIPT TABLES")
print("=" * 60)

for table_name in ['receipt_splits', 'receipt_banking_links', 'receipt_cashbox_links', 'audit_log']:
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = %s
    """, (table_name,))
    exists = cur.fetchone()[0]
    status = "✅ EXISTS" if exists else "❌ MISSING"
    print(f"  {status}: {table_name}")

# Check split_status column in receipts
cur.execute("""
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_name = 'receipts' AND column_name = 'split_status'
""")
exists = cur.fetchone()[0]
status = "✅ EXISTS" if exists else "❌ MISSING"
print(f"  {status}: receipts.split_status column")

cur.close()
conn.close()

print("\n" + "=" * 60)
print("STATUS")
print("=" * 60)
print("""
If split receipt tables are MISSING:
  → Run migration: scripts/migrate_split_receipt_schema.py
  
If split receipt tables exist but are EMPTY:
  → Create test split via UI: Click [✂️ Create Split] button
  
If split receipt tables exist and have data:
  → Split receipt UI is ready for testing!
""")
