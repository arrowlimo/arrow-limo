import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Get full details of the $49.05 transaction
cur.execute("""
    SELECT 
        transaction_id, 
        transaction_date, 
        account_number, 
        description,
        debit_amount,
        credit_amount,
        check_number,
        category
    FROM banking_transactions 
    WHERE transaction_id = 69335
""")

print("Transaction ID 69335 Full Details:")
row = cur.fetchone()
if row:
    print(f"  ID: {row[0]}")
    print(f"  Date: {row[1]}")
    print(f"  Account: {row[2]}")
    print(f"  Description: {row[3]}")
    print(f"  Debit: ${row[4]}")
    print(f"  Credit: ${row[5]}")
    print(f"  Check #: {row[6]}")
    print(f"  Category: {row[7]}")

# Check if linked to any receipt
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' AND column_name LIKE '%amount%'
    ORDER BY ordinal_position
""")
print("\nReceipt amount columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date
    FROM receipts r
    WHERE r.banking_transaction_id = 69335
""")

print("\nLinked Receipts:")
for row in cur.fetchall():
    print(f"  Receipt #{row[0]}: {row[1]}, ${row[2]}, {row[3]}")

if cur.rowcount == 0:
    print("  (None - unlinked)")

# Check for similar Fas Gas transactions nearby
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount
    FROM banking_transactions 
    WHERE transaction_date BETWEEN '2012-09-12' AND '2012-09-20'
      AND description ILIKE '%fas%gas%'
    ORDER BY transaction_date
""")

print("\nFas Gas transactions in same date range:")
for row in cur.fetchall():
    print(f"  ID={row[0]}, Date={row[1]}, Desc={row[2]}, Debit=${row[3]}")

conn.close()
