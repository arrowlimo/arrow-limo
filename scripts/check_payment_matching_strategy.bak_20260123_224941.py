"""
Check credit card last 4 digits availability in ALMS and LMS databases.
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
print("CREDIT CARD LAST 4 DIGITS - PAYMENT MATCHING STRATEGY")
print("=" * 80)

# Check ALMS PostgreSQL
print("\n1. ALMS PostgreSQL - Payments Table Structure")
print("-" * 80)

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

# Get all payments columns
pg_cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'payments'
    ORDER BY ordinal_position
""")

all_columns = pg_cur.fetchall()
print("\nAll columns in payments table:")
for col, dtype in all_columns:
    print(f"  - {col:<30} ({dtype})")

# Check for specific matching columns
print("\n" + "=" * 80)
print("2. Key Matching Fields in ALMS Payments")
print("-" * 80)

matching_fields = {
    'reserve_number': 'Links to charter',
    'account_number': 'Client account',
    'payment_date': 'Transaction date',
    'amount': 'Payment amount',
    'payment_method': 'Payment type',
    'credit_card_last4': 'CC last 4 digits',
    'square_payment_id': 'Square transaction ID'
}

for field, description in matching_fields.items():
    pg_cur.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT({field}) as non_null,
            COUNT(DISTINCT {field}) as unique_vals
        FROM payments
        WHERE {field} IS NOT NULL
    """)
    stats = pg_cur.fetchone()
    if stats:
        print(f"\n{field}:")
        print(f"  Purpose: {description}")
        print(f"  Total rows: {stats[0]:,}")
        if stats[0] > 0:
            print(f"  Non-null: {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
        else:
            print(f"  Non-null: 0 (0.0%)")
        print(f"  Unique values: {stats[2]:,}")
        
        # Show samples for text fields
        if field in ['credit_card_last4', 'payment_method']:
            pg_cur.execute(f"""
                SELECT {field}, COUNT(*) as count
                FROM payments
                WHERE {field} IS NOT NULL
                GROUP BY {field}
                ORDER BY count DESC
                LIMIT 5
            """)
            samples = pg_cur.fetchall()
            if samples:
                print(f"  Top values: {', '.join(f'{s[0]} ({s[1]})' for s in samples)}")

# Check LMS Access Database
print("\n" + "=" * 80)
print("3. LMS Access Database - Payment Table")
print("-" * 80)

lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("\nPayment table columns:")
lms_columns = []
for row in lms_cur.columns(table='Payment'):
    lms_columns.append(row.column_name)
    print(f"  - {row.column_name} ({row.type_name})")

# Check payment counts
lms_cur.execute("SELECT COUNT(*) FROM Payment")
lms_total = lms_cur.fetchone()[0]
print(f"\nTotal LMS payments: {lms_total:,}")

# Check for reserve numbers
lms_cur.execute("SELECT COUNT(*) FROM Payment WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''")
with_reserve = lms_cur.fetchone()[0]
print(f"With Reserve_No: {with_reserve:,} ({with_reserve/lms_total*100:.1f}%)")

# Check matching strategy
print("\n" + "=" * 80)
print("4. PAYMENT-CHARTER MATCHING STRATEGY")
print("=" * 80)

# Check how many unmatched payments have reserve numbers
pg_cur.execute("""
    SELECT 
        COUNT(*) as total_unmatched,
        COUNT(reserve_number) as with_reserve,
        COUNT(account_number) as with_account,
        COUNT(square_payment_id) as with_square_id,
        COUNT(credit_card_last4) as with_cc_last4
    FROM payments
    WHERE charter_id IS NULL
""")

unmatched_stats = pg_cur.fetchone()

print(f"\nUnmatched payments: {unmatched_stats[0]:,}")
print(f"  With reserve_number: {unmatched_stats[1]:,} ({unmatched_stats[1]/unmatched_stats[0]*100:.1f}%)")
print(f"  With account_number: {unmatched_stats[2]:,} ({unmatched_stats[2]/unmatched_stats[0]*100:.1f}%)")
print(f"  With square_payment_id: {unmatched_stats[3]:,} ({unmatched_stats[3]/unmatched_stats[0]*100:.1f}%)")
print(f"  With credit_card_last4: {unmatched_stats[4]:,} ({unmatched_stats[4]/unmatched_stats[0]*100:.1f}%)")

# Matching priority
print("\n" + "=" * 80)
print("RECOMMENDED MATCHING STRATEGY")
print("=" * 80)
print("""
Priority 1: Direct Reserve Number Match
  - Match payments.reserve_number → charters.reserve_number
  - Highest confidence, most direct linkage
  
Priority 2: Account Number + Date + Amount
  - Match payments.account_number → charters.account_number
  - Within ±7 days of charter_date
  - Amount matches charter rate (±5%)
  
Priority 3: Square Payment Lookup
  - Use square_payment_id to find order/invoice
  - Extract reserve number from Square metadata
  
Priority 4: Credit Card Last 4 (Disambiguation)
  - When multiple charters on same date for same client
  - Use CC last 4 to identify correct charter
  
Priority 5: Manual Review
  - Payments with $0.00 amounts (adjustments)
  - Payments without identifiers
""")

# Sample unmatched payments
print("\n" + "=" * 80)
print("SAMPLE UNMATCHED PAYMENTS (with identifiers)")
print("=" * 80)

pg_cur.execute("""
    SELECT payment_id, payment_date, amount, reserve_number, account_number, 
           credit_card_last4, payment_method
    FROM payments
    WHERE charter_id IS NULL
    AND (reserve_number IS NOT NULL OR account_number IS NOT NULL)
    AND amount > 0
    ORDER BY amount DESC
    LIMIT 10
""")

samples = pg_cur.fetchall()
if samples:
    print(f"\n{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Reserve':<10} {'Account':<12} {'CC Last4':<10} {'Method':<15}")
    print("-" * 95)
    for row in samples:
        pid, date, amount, reserve, account, cc_last4, method = row
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        reserve_str = reserve or 'NULL'
        account_str = account or 'NULL'
        cc_str = cc_last4 or 'NULL'
        method_str = method or 'NULL'
        print(f"{pid:<12} {date_str:<12} ${float(amount):<11,.2f} {reserve_str:<10} {account_str:<12} {cc_str:<10} {method_str:<15}")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print("\n" + "=" * 80)
print("NEXT STEP: Create payment-charter matching script")
print("=" * 80)
