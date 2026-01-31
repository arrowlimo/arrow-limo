import psycopg2
from collections import Counter

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== PAYMENT BANKING_TRANSACTION_ID UPDATE HISTORY ===\n")

# Check if updated_at exists
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='payments' 
    AND column_name IN ('updated_at', 'last_updated')
""")
timestamp_cols = [row[0] for row in cur.fetchall()]
print(f"Timestamp columns: {timestamp_cols}")

if timestamp_cols:
    timestamp_col = timestamp_cols[0]
    
    # Get payments with banking_transaction_id and their update dates
    cur.execute(f"""
        SELECT 
            DATE({timestamp_col}) as update_date,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM payments
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY DATE({timestamp_col})
        ORDER BY update_date DESC
        LIMIT 20
    """)
    
    print(f"\n Payments with banking_transaction_id grouped by {timestamp_col}:")
    print(f"{'Date':<15} {'Count':>8} {'Amount':>15}")
    print("-" * 40)
    
    for update_date, count, total_amount in cur.fetchall():
        print(f"{str(update_date):<15} {count:>8,} ${total_amount:>13,.2f}")

# Check charter.paid_amount vs SUM(payments) - this shows if charters are properly matched
print("\n\n=== CHARTER PAYMENT RECONCILIATION STATUS ===\n")

cur.execute("""
    SELECT 
        COUNT(DISTINCT c.charter_id) as total_charters,
        COUNT(DISTINCT CASE WHEN c.paid_amount > 0 THEN c.charter_id END) as charters_with_payments,
        COUNT(DISTINCT p.charter_id) as charters_in_payments_table,
        COUNT(DISTINCT CASE WHEN p.banking_transaction_id IS NOT NULL THEN p.charter_id END) as charters_with_banking_link
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.charter_date >= '2020-01-01'
""")

result = cur.fetchone()
total_charters, with_payments, in_payments, with_banking = result

print(f"Total charters (since 2020): {total_charters:,}")
print(f"Charters with paid_amount > 0: {with_payments:,}")
print(f"Charters with payment records: {in_payments:,}")
print(f"Charters with banking link: {with_banking:,}")

if in_payments > 0:
    charter_match_pct = (with_banking / in_payments * 100)
    print(f"\nCharter payment-banking match rate: {charter_match_pct:.1f}%")

# Check for any matching work done recently
print("\n\n=== RECENT DATABASE ACTIVITY ===\n")

cur.execute("""
    SELECT 
        schemaname, tablename, 
        last_vacuum, last_autovacuum, 
        last_analyze, last_autoanalyze,
        n_tup_ins, n_tup_upd, n_tup_del
    FROM pg_stat_user_tables
    WHERE tablename = 'payments'
""")

result = cur.fetchone()
if result:
    schema, table, vac, autovac, analyze, autoanalyze, inserts, updates, deletes = result
    print(f"Table: {schema}.{table}")
    print(f"Inserts: {inserts:,}")
    print(f"Updates: {updates:,}")
    print(f"Deletes: {deletes:,}")
    print(f"Last analyzed: {autoanalyze or analyze}")

conn.close()
