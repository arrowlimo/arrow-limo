"""
Verify if cleanup_cibc_banking.py successfully removed artifacts from database
Compare database state to Excel report
"""
import psycopg2
import os

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== Current Database State (After Cleanup) ===\n")

# Check for #dd patterns
cur.execute("""
    SELECT transaction_id, description, vendor_extracted
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description ILIKE '%#dd%'
    ORDER BY transaction_id DESC
    LIMIT 10
""")
dd_results = cur.fetchall()
print(f"#dd patterns still in database: {len(dd_results) if dd_results else 0}")
if dd_results:
    print("\nFirst 10 examples:")
    for row in dd_results:
        print(f"  TX {row[0]}: {row[1][:60]}... | Vendor: {row[2]}")
print()

# Check for descriptions ending with X
cur.execute("""
    SELECT transaction_id, description, vendor_extracted
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description ~ '\\sX$'
    ORDER BY transaction_id DESC
    LIMIT 10
""")
x_results = cur.fetchall()
print(f"\nDescriptions ending with ' X': {len(x_results) if x_results else 0}")
if x_results:
    print("\nFirst 10 examples:")
    for row in x_results:
        print(f"  TX {row[0]}: {row[1][:60]}... | Vendor: {row[2]}")
print()

# Check specific Hertz example
cur.execute("""
    SELECT transaction_id, description, vendor_extracted
    FROM banking_transactions
    WHERE transaction_id = 60079
""")
hertz = cur.fetchone()
print(f"\nSpecific Hertz example (TX 60079):")
if hertz:
    print(f"  Description: {hertz[1]}")
    print(f"  Vendor Extracted: {hertz[2]}")
else:
    print("  Not found!")
print()

# Summary comparison
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE description ILIKE '%#dd%') as dd_count,
        COUNT(*) FILTER (WHERE description ~ '\\sX$') as x_count,
        COUNT(*) FILTER (WHERE vendor_extracted IS NOT NULL) as vendor_extracted_count
    FROM banking_transactions
    WHERE account_number = '0228362'
""")
summary = cur.fetchone()
print(f"\n=== CIBC Account 0228362 Summary ===")
print(f"Transactions with #dd: {summary[0]}")
print(f"Transactions ending with X: {summary[1]}")
print(f"Transactions with vendor_extracted: {summary[2]}")

# Check if cleanup actually updated description field
cur.execute("""
    SELECT transaction_id, description, vendor_extracted
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    AND description ILIKE 'Cheque %'
    LIMIT 10
""")
cleaned = cur.fetchall()
print(f"\n=== Sample Cleaned Cheque Transactions ===")
print(f"Cheque transactions with vendor_extracted: {len(cleaned)}")
if cleaned:
    for row in cleaned:
        print(f"  TX {row[0]}: {row[1][:50]} | Vendor: {row[2]}")

cur.close()
conn.close()
