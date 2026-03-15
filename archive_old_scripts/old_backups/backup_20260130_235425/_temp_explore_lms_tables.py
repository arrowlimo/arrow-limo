import pyodbc
import csv

# Connect to LMS Access database
lms_path = r"L:\limo\lms.mdb"
conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};')
cur = conn.cursor()

print("=== LMS DATABASE TABLES ===\n")

# List all tables
tables = [row.table_name for row in cur.tables(tableType='TABLE') if not row.table_name.startswith('MSys')]
print(f"Total tables: {len(tables)}\n")

# Find payment-related tables
payment_tables = [t for t in tables if 'payment' in t.lower() or 'pay' in t.lower()]
print("PAYMENT-RELATED TABLES:")
for t in sorted(payment_tables):
    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cur.fetchone()[0]
    print(f"  {t:<40s} {count:>8,} rows")

# Find relationship/ID tables
id_tables = [t for t in tables if any(x in t.lower() for x in ['id', 'relationship', 'link', 'match', 'mapping'])]
print("\nID/RELATIONSHIP TABLES:")
for t in sorted(id_tables):
    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cur.fetchone()[0]
    print(f"  {t:<40s} {count:>8,} rows")

# Find tables with "banking" or "transaction"
banking_tables = [t for t in tables if any(x in t.lower() for x in ['bank', 'transaction', 'deposit'])]
print("\nBANKING/TRANSACTION TABLES:")
for t in sorted(banking_tables):
    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cur.fetchone()[0]
    print(f"  {t:<40s} {count:>8,} rows")

# Check E_Payment tables specifically
e_payment_tables = [t for t in tables if t.lower().startswith('e_') or 'e_payment' in t.lower()]
print("\nE_PAYMENT TABLES:")
for t in sorted(e_payment_tables):
    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cur.fetchone()[0]
    print(f"  {t:<40s} {count:>8,} rows")
    
    # Show columns
    cur.execute(f"SELECT TOP 1 * FROM [{t}]")
    columns = [desc[0] for desc in cur.description]
    print(f"    Columns: {', '.join(columns[:10])}")
    if len(columns) > 10:
        print(f"             {', '.join(columns[10:])}")

conn.close()

print("\n\n💡 Will examine these tables for payment-banking relationship data...")
