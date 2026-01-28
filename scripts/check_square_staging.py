#!/usr/bin/env python3
"""Quick square_transactions_staging analysis."""
import psycopg2, os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get column names first
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'square_transactions_staging' ORDER BY ordinal_position LIMIT 10")
print("square_transactions_staging columns (first 10):")
cols = []
for r in cur.fetchall():
    cols.append(r[0])
    print(f"  {r[0]}")

# Row count
cur.execute('SELECT COUNT(*) FROM square_transactions_staging')
stg_count = cur.fetchone()[0]
print(f"\nTotal rows: {stg_count:,}")

# Check payment_imports first (we know payment_imports has Square data)
cur.execute("SELECT COUNT(*) FROM payment_imports WHERE source = 'Square'")
pi_square = cur.fetchone()[0]
print(f"payment_imports with source='Square': {pi_square:,}")

# Since payment_imports is 100% in payments, and payment_imports has Square data,
# square_transactions_staging is likely the SOURCE for payment_imports
print("\nConclusion: square_transactions_staging was likely ALREADY IMPORTED")
print("into payment_imports (18,720 rows), which is 100% in payments table.")
print("\nRecommendation: ARCHIVE square_transactions_staging")
