import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

# Search for receipts that should match the banking transaction
# The banking transaction is: ID 69335, RUN'N ON EMPTY, $49.05, 2012-09-17

# First, let's see what receipts are linked to banking transaction 69335
print("Receipts linked to banking transaction 69335:")
cur = conn.cursor()
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.banking_transaction_id,
        r.description
    FROM receipts r
    WHERE r.banking_transaction_id = 69335
    ORDER BY r.receipt_date
""")

for row in cur.fetchall():
    print(f"  Receipt #{row[0]}: {row[1]}, {row[2]}, ${row[3]:.2f}, banking_id={row[4]}")
    print(f"    Description: {row[5]}")

# Now search with empty vendor to see if they would appear
print("\n\nReceipts with vendor like '%run%empty%' (should find them):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.banking_transaction_id
    FROM receipts r
    WHERE r.vendor_name ILIKE '%run%empty%'
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

for row in cur.fetchall():
    print(f"  Receipt #{row[0]}: {row[1]}, {row[2]}, ${row[3]:.2f}, banking_id={row[4]}")

# Search with no filters (should show recent receipts)
print("\n\nMost recent receipts (no filters, just top 10):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.banking_transaction_id
    FROM receipts r
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

for row in cur.fetchall():
    print(f"  Receipt #{row[0]}: {row[1]}, {row[2]}, ${row[3]:.2f}, banking_id={row[4]}")

conn.close()
