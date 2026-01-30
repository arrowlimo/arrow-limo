import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check the November 24 backup (before recent corruption)
backup_table = 'banking_transactions_scotia_backup_20251124_221239'

print(f"Checking backup: {backup_table}")
print("=" * 80)

for year in [2012, 2013, 2014]:
    cur.execute(f"""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            MIN(balance) as min_bal,
            MAX(balance) as max_bal
        FROM {backup_table}
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    stats = cur.fetchone()
    if stats[0] == 0:
        print(f"\n{year}: No records")
        continue
    
    print(f"\n{year}:")
    print(f"  Count: {stats[0]}")
    print(f"  Dates: {stats[1]} to {stats[2]}")
    if stats[3] is not None and stats[4] is not None:
        print(f"  Balance range: ${float(stats[3]):.2f} to ${float(stats[4]):.2f}")
    
    # Get last transaction
    cur.execute(f"""
        SELECT transaction_date, description, balance
        FROM {backup_table}
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
        AND balance IS NOT NULL
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    """, (year,))
    
    last = cur.fetchone()
    if last:
        print(f"  Last: {last[0]} - ${float(last[2]):.2f}")

conn.close()
