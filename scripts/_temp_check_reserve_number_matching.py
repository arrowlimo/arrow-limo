import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=== RESERVE_NUMBER MATCHING STATUS ===\n")

# Check payments with reserve_number
cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(reserve_number) as with_reserve_number,
        COUNT(DISTINCT reserve_number) as unique_reserves,
        COUNT(charter_id) as with_charter_id,
        COUNT(banking_transaction_id) as with_banking_txn_id
    FROM payments
""")

total, with_reserve, unique_reserves, with_charter, with_banking = cur.fetchone()

print(f"Total payments: {total:,}")
print(f"With reserve_number: {with_reserve:,} ({with_reserve/total*100:.1f}%)")
print(f"Unique reserve numbers: {unique_reserves:,}")
print(f"With charter_id: {with_charter:,} ({with_charter/total*100:.1f}%)")
print(f"With banking_transaction_id: {with_banking:,} ({with_banking/total*100:.1f}%)")

# Check if we can match payments to charters via reserve_number
print("\n=== CHARTER-PAYMENT LINKAGE VIA RESERVE_NUMBER ===\n")

cur.execute("""
    SELECT 
        COUNT(DISTINCT p.payment_id) as payments_with_matching_charter,
        COUNT(DISTINCT c.charter_id) as charters_with_payments
    FROM payments p
    INNER JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.reserve_number IS NOT NULL
""")

payments_matched, charters_matched = cur.fetchone()
print(f"Payments that match a charter (via reserve_number): {payments_matched:,}")
print(f"Charters that have payments (via reserve_number): {charters_matched:,}")

# Check if charters have banking transaction links
print("\n=== CHARTER-BANKING LINKAGE ===\n")

cur.execute("""
    SELECT 
        COUNT(DISTINCT c.charter_id) as total_charters,
        COUNT(DISTINCT CASE WHEN r.receipt_id IS NOT NULL THEN c.charter_id END) as charters_with_receipts,
        COUNT(DISTINCT CASE WHEN r.banking_transaction_id IS NOT NULL THEN c.charter_id END) as charters_with_banking
    FROM charters c
    LEFT JOIN receipts r ON r.banking_transaction_id IS NOT NULL
    WHERE c.charter_date >= '2020-01-01'
""")

total_charters, with_receipts, with_banking = cur.fetchone()
print(f"Total charters (since 2020): {total_charters:,}")
print(f"Charters with receipts: {with_receipts:,}")
print(f"Charters with banking link: {with_banking:,}")

# THE KEY QUESTION: Can we link payments to banking via charter reserve_number?
print("\n=== POTENTIAL PAYMENT-BANKING MATCHES VIA RESERVE_NUMBER ===\n")

cur.execute("""
    WITH charter_deposits AS (
        SELECT DISTINCT
            c.reserve_number,
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            b.transaction_id as banking_transaction_id,
            b.transaction_date,
            b.credit_amount
        FROM charters c
        INNER JOIN banking_transactions b ON 
            b.credit_amount > 0
            AND b.transaction_date BETWEEN c.charter_date - INTERVAL '7 days' AND c.charter_date + INTERVAL '14 days'
            AND ABS(c.total_amount_due - b.credit_amount) < 10.00
        WHERE c.reserve_number IS NOT NULL
    )
    SELECT 
        COUNT(DISTINCT p.payment_id) as matchable_payments,
        SUM(p.amount) as matchable_amount
    FROM payments p
    INNER JOIN charter_deposits cd ON cd.reserve_number = p.reserve_number
    WHERE p.banking_transaction_id IS NULL
""")

matchable_payments, matchable_amount = cur.fetchone()

if matchable_payments:
    print(f"✅ FOUND {matchable_payments:,} payments that can be matched to banking via charter deposits!")
    print(f"   Total amount: ${matchable_amount:,.2f}")
    print(f"\n   Strategy: Link payment → charter (via reserve_number) → banking deposit")
else:
    print("❌ No direct charter-banking deposit matches found")

# Check for existing relationship tables
print("\n=== CHECKING FOR RELATIONSHIP TABLES ===\n")

relationship_tables = [
    'charter_payment_links',
    'payment_banking_links', 
    'banking_payment_links',
    'charter_banking_links',
    'payment_charter_mapping',
    'reserve_payment_mapping'
]

for table_name in relationship_tables:
    cur.execute(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        )
    """)
    exists = cur.fetchone()[0]
    
    if exists:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"✅ {table_name}: {count:,} rows")
        
        # Show columns
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        print(f"   Columns: {', '.join(columns)}")
    else:
        print(f"❌ {table_name}: not found")

conn.close()

print("\n" + "="*80)
print("NEXT STEP: Extract reserve_number → banking matches and restore to payments")
print("="*80)
