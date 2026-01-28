#!/usr/bin/env python3
"""Check banking_receipt_matching_ledger table size and row count."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

# Row count
cur.execute("SELECT COUNT(*) FROM banking_receipt_matching_ledger")
row_count = cur.fetchone()[0]

# Total size (table + indexes)
cur.execute("SELECT pg_size_pretty(pg_total_relation_size('banking_receipt_matching_ledger'))")
total_size = cur.fetchone()[0]

# Table size only
cur.execute("SELECT pg_size_pretty(pg_relation_size('banking_receipt_matching_ledger'))")
table_size = cur.fetchone()[0]

# Index size
cur.execute("SELECT pg_size_pretty(pg_indexes_size('banking_receipt_matching_ledger'))")
index_size = cur.fetchone()[0]

print(f"banking_receipt_matching_ledger:")
print(f"  Rows:        {row_count:,}")
print(f"  Table size:  {table_size}")
print(f"  Index size:  {index_size}")
print(f"  Total size:  {total_size}")

cur.close()
conn.close()
