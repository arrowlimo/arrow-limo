#!/usr/bin/env python3
"""
Check if 2012 charter payments are recorded in income ledger.
"""

import psycopg2

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Check if income_ledger table exists and what it contains
print("=== Checking income_ledger table ===")
schema_query = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'income_ledger'
ORDER BY ordinal_position;
"""
try:
    cur.execute(schema_query)
    cols = cur.fetchall()
    if cols:
        print("income_ledger columns:")
        for col_name, data_type in cols:
            print(f"  {col_name}: {data_type}")
    else:
        print("income_ledger table does not exist or is empty")
except Exception as e:
    print(f"income_ledger error: {e}")

# Check for 2012 entries in income_ledger
print("\n=== 2012 entries in income_ledger ===")
cur.close()
conn.close()

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

try:
    query = """
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) as total
    FROM income_ledger
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012;
    """
    cur.execute(query)
    count, total = cur.fetchone()
    print(f"2012 income_ledger records: {count}")
    print(f"Total gross_amount: ${float(total):,.2f}")
except Exception as e:
    print(f"Query error: {e}")

# Check charter_payments link to income_ledger
print("\n=== charter_payments - are they linked to income_ledger? ===")
try:
    query = """
    SELECT COUNT(CASE WHEN income_ledger_id IS NOT NULL THEN 1 END) as with_ledger_id
    FROM charter_payments
    LIMIT 1;
    """
    cur.execute(query)
    has_col = cur.fetchone()
    if has_col and has_col[0] is not None:
        print("income_ledger_id column exists in charter_payments")
    else:
        print("income_ledger_id column likely does not exist in charter_payments")
except Exception as e:
    print(f"Query error: charter_payments structure check failed")

query2 = """
SELECT COUNT(*) as total_2012_payments
FROM charter_payments
WHERE EXTRACT(YEAR FROM payment_date) = 2012;
"""
cur.execute(query2)
total = cur.fetchone()[0]
print(f"Total 2012 charter_payments: {total}")

# Check if charters have income_ledger_id
print("\n=== charters - are they linked to income_ledger? ===")
try:
    query = """
    SELECT COUNT(CASE WHEN income_ledger_id IS NOT NULL THEN 1 END) as has_ledger_id
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    LIMIT 1;
    """
    cur.execute(query)
    result = cur.fetchone()
    if result and result[0] > 0:
        print("2012 charters have income_ledger_id links")
        query_count = """
        SELECT COUNT(CASE WHEN income_ledger_id IS NOT NULL THEN 1 END) as linked,
               COUNT(*) as total
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012;
        """
        cur.execute(query_count)
        linked, total = cur.fetchone()
        print(f"  Linked: {linked} out of {total}")
    else:
        print("2012 charters do NOT have income_ledger_id links")
except Exception as e:
    print(f"Query error: {e}")

# Check for T2 extraction exports or tables
print("\n=== Checking for T2/tax tables ===")
tax_tables_query = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name ILIKE '%tax%' OR table_name ILIKE '%t2%' OR table_name ILIKE '%extract%')
ORDER BY table_name;
"""
try:
    cur.execute(tax_tables_query)
    tables = cur.fetchall()
    if tables:
        print("Found tax-related tables:")
        for (table,) in tables:
            print(f"  {table}")
    else:
        print("No tax-related tables found")
except Exception as e:
    print(f"Query error: {e}")

cur.close()
conn.close()
