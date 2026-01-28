import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("SEARCHING FOR SQUARE LOAN DATA")
print("="*80)
print()

# 1. Check for square-related tables
print("Square-related tables:")
print("-"*80)
cur.execute("""
    SELECT table_name, 
           (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as col_count
    FROM information_schema.tables t
    WHERE table_schema = 'public' 
    AND table_name ILIKE '%square%'
    ORDER BY table_name
""")

square_tables = cur.fetchall()
for table, cols in square_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    print(f"  {table:<40} {row_count:>8,} rows  ({cols} columns)")

# 2. Check banking_transactions for Square loans
print("\n" + "="*80)
print("BANKING TRANSACTIONS - Square Loan Activity")
print("="*80)

cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date), SUM(amount)
    FROM banking_transactions
    WHERE description ILIKE '%square%loan%' 
       OR description ILIKE '%square capital%'
       OR vendor_name ILIKE '%square%loan%'
       OR vendor_name ILIKE '%square capital%'
""")

result = cur.fetchone()
print(f"\nTransactions matching 'Square Loan/Capital':")
print(f"  Count: {result[0]:,}")
print(f"  Date range: {result[1]} to {result[2]}")
print(f"  Total amount: ${result[3]:,.2f}" if result[3] else "  Total amount: $0.00")

# 3. Sample Square loan transactions
cur.execute("""
    SELECT transaction_date, description, vendor_name, amount, account_name
    FROM banking_transactions
    WHERE description ILIKE '%square%loan%' 
       OR description ILIKE '%square capital%'
       OR vendor_name ILIKE '%square%loan%'
       OR vendor_name ILIKE '%square capital%'
    ORDER BY transaction_date DESC
    LIMIT 20
""")

samples = cur.fetchall()
if samples:
    print("\nRecent Square Loan transactions:")
    print(f"{'Date':<12} {'Description':<35} {'Vendor':<25} {'Amount':>12} {'Account'}")
    print("-"*120)
    for row in samples:
        desc = (row[1] or '')[:35]
        vendor = (row[2] or '')[:25]
        acct = (row[4] or '')[:20]
        print(f"{str(row[0]):<12} {desc:<35} {vendor:<25} ${row[3]:>11.2f} {acct}")

# 4. Check receipts for Square loans
print("\n" + "="*80)
print("RECEIPTS - Square Loan Expenses")
print("="*80)

cur.execute("""
    SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date), SUM(amount)
    FROM receipts
    WHERE vendor_name ILIKE '%square%loan%' 
       OR vendor_name ILIKE '%square capital%'
       OR description ILIKE '%square%loan%'
       OR description ILIKE '%square capital%'
""")

result = cur.fetchone()
print(f"\nReceipts matching 'Square Loan/Capital':")
print(f"  Count: {result[0]:,}")
if result[0] > 0:
    print(f"  Date range: {result[1]} to {result[2]}")
    print(f"  Total amount: ${result[3]:,.2f}" if result[3] else "  Total amount: $0.00")

# 5. Check financing_sources table
print("\n" + "="*80)
print("FINANCING SOURCES")
print("="*80)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name ILIKE '%financing%' OR table_name ILIKE '%loan%')
    ORDER BY table_name
""")

financing_tables = [row[0] for row in cur.fetchall()]
for table in financing_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table:<40} {count:>8,} rows")
    
    # If it has data, sample it
    if count > 0 and 'loan' in table.lower():
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        print(f"    Sample data: {cur.fetchall()[:1]}")

cur.close()
conn.close()
