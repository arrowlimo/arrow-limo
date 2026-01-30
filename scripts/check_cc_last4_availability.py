"""
Check credit card last 4 digits availability in ALMS and LMS databases.

This will help us understand if we can use CC last 4 for payment matching.
"""

import pyodbc
import psycopg2

# LMS Connection
LMS_PATH = r'L:\oldlms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

print("=" * 80)
print("CREDIT CARD LAST 4 DIGITS AVAILABILITY CHECK")
print("=" * 80)

# Check ALMS PostgreSQL
print("\n1. ALMS PostgreSQL Database")
print("-" * 80)

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

# Check payments table for CC info
pg_cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'payments'
    AND (column_name ILIKE '%card%' OR column_name ILIKE '%credit%' OR column_name ILIKE '%last%')
    ORDER BY ordinal_position
""")

cc_columns = pg_cur.fetchall()

if cc_columns:
    print("\nPayments table - Credit card related columns:")
    for col, dtype in cc_columns:
        print(f"  - {col} ({dtype})")
        
        # Get sample data
        pg_cur.execute(f"""
            SELECT COUNT(*) as total,
                   COUNT({col}) as non_null,
                   COUNT(DISTINCT {col}) as unique_values
            FROM payments
            WHERE {col} IS NOT NULL AND {col} != ''
        """)
        stats = pg_cur.fetchone()
        if stats and stats[1] > 0:
            print(f"    Total rows: {stats[0]:,}, Non-null: {stats[1]:,}, Unique: {stats[2]:,}")
            
            # Show samples
            pg_cur.execute(f"SELECT DISTINCT {col} FROM payments WHERE {col} IS NOT NULL AND {col} != '' LIMIT 5")
            samples = pg_cur.fetchall()
            if samples:
                print(f"    Samples: {', '.join(str(s[0])[:20] for s in samples)}")
else:
    print("\nNo credit card columns found in payments table")

# Check square_transactions table
pg_cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'square_transactions'
    AND (column_name ILIKE '%card%' OR column_name ILIKE '%last%')
    ORDER BY ordinal_position
""")

square_cc = pg_cur.fetchall()
if square_cc:
    print("\nSquare_transactions table - Card columns:")
    for col, dtype in square_cc:
        print(f"  - {col} ({dtype})")
        
        pg_cur.execute(f"""
            SELECT COUNT(*) as total,
                   COUNT({col}) as non_null
            FROM square_transactions
            WHERE {col} IS NOT NULL AND {col} != ''
        """)
        stats = pg_cur.fetchone()
        if stats and stats[1] > 0:
            print(f"    Total: {stats[0]:,}, Non-null: {stats[1]:,}")

# Check LMS Access Database
print("\n" + "=" * 80)
print("2. LMS Access Database")
print("-" * 80)

lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Get Payment table columns
print("\nPayment table columns:")
for row in lms_cur.columns(table='Payment'):
    col_name = row.column_name
    col_type = row.type_name
    print(f"  - {col_name} ({col_type})")

# Check if there's any CC info in Payment table
lms_cur.execute("SELECT TOP 5 * FROM Payment WHERE Pymt_Type = 'Credit Card' OR Pymt_Type LIKE '%Visa%' OR Pymt_Type LIKE '%Master%'")
cc_payments = lms_cur.fetchall()

if cc_payments:
    print(f"\nFound {len(cc_payments)} credit card payments in LMS")
    print("Columns available:", [desc[0] for desc in lms_cur.description])
    
    print("\nSample credit card payment:")
    if cc_payments:
        sample = cc_payments[0]
        for i, col in enumerate(lms_cur.description):
            print(f"  {col[0]}: {sample[i]}")

# Check for Customer table (might have CC info)
try:
    lms_cur.execute("SELECT TOP 1 * FROM Customer")
    customer = lms_cur.fetchone()
    if customer:
        print("\nCustomer table columns:")
        for col in lms_cur.description:
            print(f"  - {col[0]}")
except:
    print("\nNo Customer table found in LMS")

# Check Deposit table
print("\nDeposit table columns:")
try:
    for row in lms_cur.columns(table='Deposit'):
        print(f"  - {row.column_name} ({row.type_name})")
except:
    print("  (Could not read Deposit table structure)")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

# ALMS summary
pg_cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(CASE WHEN credit_card_last4 IS NOT NULL AND credit_card_last4 != '' THEN 1 END) as with_cc_last4
    FROM payments
""")
alms_stats = pg_cur.fetchone()

print(f"\nALMS PostgreSQL:")
print(f"  Total payments: {alms_stats[0]:,}")
print(f"  With CC last 4: {alms_stats[1]:,} ({alms_stats[1]/alms_stats[0]*100:.1f}%)" if alms_stats[0] > 0 else "  With CC last 4: 0")

# LMS summary
lms_cur.execute("SELECT COUNT(*) FROM Payment")
lms_total = lms_cur.fetchone()[0]
print(f"\nLMS Access:")
print(f"  Total payments: {lms_total:,}")
print(f"  Note: LMS does not store CC last 4 digits in Payment table")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("\nFor payment-charter matching:")
print("  1. ALMS has credit_card_last4 column in payments table")
print("  2. Can match by: reserve_number, account_number, amount, date")
print("  3. CC last 4 can help disambiguate when multiple payments on same date")
print("  4. LMS Payment table has: Account_No, Reserve_No, Amount, LastUpdated")
print("  5. Main matching strategy: Reserve_No → charter.reserve_number")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
