#!/usr/bin/env python3
"""
Check verification and reconciliation columns in key tables
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*80)
print("VERIFICATION/RECONCILIATION COLUMNS")
print("="*80 + "\n")

tables = ['banking_transactions', 'receipts', 'payments', 'charters']

for table in tables:
    print(f"\n📋 {table.upper()}:")
    print("-" * 80)
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND (column_name LIKE '%%verif%%' OR column_name LIKE '%%reconcil%%')
        ORDER BY ordinal_position
    """, (table,))
    
    rows = cur.fetchall()
    if rows:
        for col, dtype, nullable in rows:
            print(f"   {col:40s} {dtype:20s} nullable={nullable}")
    else:
        print("   (no verification/reconciliation columns)")

cur.close()
conn.close()
