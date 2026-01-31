import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Check banking_transactions columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")
print("=== banking_transactions columns ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check if cash_box_transactions exists and what it contains
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'cash_box_transactions'
    ORDER BY ordinal_position
""")
print("\n=== cash_box_transactions columns ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check if CASH BOX account exists in chart_of_accounts
cur.execute("""
    SELECT account_code, account_name, account_type 
    FROM chart_of_accounts 
    WHERE account_name ILIKE '%CASH%' OR account_code ILIKE '%CASH%'
    ORDER BY account_code
""")
print("\n=== CASH-related GL accounts ===")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"  {row[0]}: {row[1]} ({row[2]})")
else:
    print("  [None found]")

# Check bank_accounts structure and content
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'bank_accounts'
    ORDER BY ordinal_position
""")
print("\n=== bank_accounts columns ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check bank_accounts content
cur.execute("""SELECT * FROM bank_accounts""")
print("\n=== bank_accounts content ===")
cols = [desc[0] for desc in cur.description]
for row in cur.fetchall():
    print(f"  {dict(zip(cols, row))}")

# Check for cash-related banking transactions
cur.execute("""
    SELECT DISTINCT description 
    FROM banking_transactions 
    WHERE description ILIKE '%CASH%' OR description ILIKE '%PETTY%'
    ORDER BY description
    LIMIT 20
""")
print("\n=== Descriptions containing CASH/PETTY in banking_transactions ===")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
