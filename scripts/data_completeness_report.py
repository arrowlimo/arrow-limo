"""
Comprehensive check of missing data in general_ledger
"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

print("=" * 120)
print("GENERAL LEDGER DATA COMPLETENESS REPORT")
print("=" * 120)

# Total records
cur.execute("SELECT COUNT(*) FROM general_ledger")
total = cur.fetchone()[0]
print(f"\nTotal records in general_ledger: {total:,}")

# Missing name field
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE (name IS NULL OR name = '' OR name = 'nan')
""")
missing_name = cur.fetchone()[0]
print(f"\nMissing 'name' field: {missing_name:,} ({missing_name/total*100:.2f}%)")

# Missing name field in 2025
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE (name IS NULL OR name = '' OR name = 'nan')
    AND EXTRACT(YEAR FROM date) = 2025
""")
missing_name_2025 = cur.fetchone()[0]
print(f"  - In 2025: {missing_name_2025:,}")

# Missing account_name field
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE account_name IS NULL
""")
missing_account_name = cur.fetchone()[0]
print(f"\nMissing 'account_name' field: {missing_account_name:,} ({missing_account_name/total*100:.2f}%)")

# Missing account_name field in 2025
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE account_name IS NULL
    AND EXTRACT(YEAR FROM date) = 2025
""")
missing_account_name_2025 = cur.fetchone()[0]
print(f"  - In 2025: {missing_account_name_2025:,}")

# Records with supplier data
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE supplier IS NOT NULL AND supplier != '' AND supplier != 'nan'
""")
with_supplier = cur.fetchone()[0]
print(f"\nRecords with 'supplier' data: {with_supplier:,} ({with_supplier/total*100:.2f}%)")

# Records with supplier data in 2025
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE supplier IS NOT NULL AND supplier != '' AND supplier != 'nan'
    AND EXTRACT(YEAR FROM date) = 2025
""")
with_supplier_2025 = cur.fetchone()[0]
print(f"  - In 2025: {with_supplier_2025:,}")

# Sample of remaining records with NULL account_name
print("\n" + "=" * 120)
print("Sample records still with NULL account_name:")
print("=" * 120)
cur.execute("""
    SELECT id, date, account_name, name, account, supplier, debit, credit
    FROM general_ledger 
    WHERE account_name IS NULL
    ORDER BY date DESC
    LIMIT 10
""")

for row in cur.fetchall():
    gl_id, date, acct_name, name, account, supplier, debit, credit = row
    amount = debit if debit else credit
    print(f"ID {gl_id}: {date} | account_name={acct_name} | name={name} | supplier={supplier} | account={account} | ${amount}")

conn.close()

print("\n" + "=" * 120)
print("Report complete!")
