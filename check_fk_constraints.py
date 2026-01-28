#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Check banking_transactions columns
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='banking_transactions' 
    AND (column_name ILIKE '%receipt%' OR column_name ILIKE '%banking%')
    ORDER BY ordinal_position
""")
print("=== banking_transactions columns with 'receipt' or 'banking' ===")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Check foreign key constraints referencing receipts/payments/charters
print("\n=== Foreign keys referencing receipts/payments/charters ===")
cur.execute("""
    SELECT 
        con.conname AS constraint_name,
        rel.relname AS table_name,
        att.attname AS column_name,
        frel.relname AS referenced_table
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_class frel ON frel.oid = con.confrelid
    JOIN unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON TRUE
    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ck.attnum
    WHERE con.contype = 'f'
      AND frel.relname IN ('receipts', 'payments', 'charters')
    ORDER BY frel.relname, rel.relname, con.conname
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}.{row[2]} -> {row[3]}")

# Check what's in banking_receipt_matching_ledger
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='banking_receipt_matching_ledger'
    ORDER BY ordinal_position
""")
print("\n=== banking_receipt_matching_ledger columns ===")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
