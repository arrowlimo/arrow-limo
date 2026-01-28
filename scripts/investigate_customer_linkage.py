#!/usr/bin/env python
"""
Investigate why urgent credit charters aren't linking to customer records.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("CUSTOMER LINKAGE INVESTIGATION")
print("=" * 80)

# Check sample urgent credit charters
cur.execute("""
    SELECT c.reserve_number, c.account_number, c.balance
    FROM charters c
    WHERE c.balance < -2000
    ORDER BY c.balance ASC
    LIMIT 10
""")

print("\nSample urgent credit charters:")
for reserve, account, balance in cur.fetchall():
    print(f"  {reserve}: account_number={account or 'NULL'}, balance=${float(balance):,.2f}")
    
    # Try to find client by different methods
    if account:
        # Try exact match
        cur.execute("SELECT client_id, account_number, client_name, company_name FROM clients WHERE account_number = %s", (account,))
        exact = cur.fetchone()
        if exact:
            print(f"    ✓ Found by account_number: {exact}")
        else:
            print(f"    ✗ No match for account_number={account}")
            
            # Try as client_id
            cur.execute("SELECT client_id, account_number, client_name, company_name FROM clients WHERE client_id::text = %s", (account,))
            by_id = cur.fetchone()
            if by_id:
                print(f"    ✓ Found by client_id: {by_id}")

# Check what account_number values look like in charters
print("\n" + "=" * 80)
print("ACCOUNT_NUMBER DISTRIBUTION IN URGENT CREDITS")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) FILTER(WHERE account_number IS NULL) AS null_acct,
        COUNT(*) FILTER(WHERE account_number IS NOT NULL) AS has_acct,
        COUNT(*) AS total
    FROM charters
    WHERE balance < -2000
""")

null_cnt, has_cnt, total = cur.fetchone()
print(f"\nUrgent credit charters:")
print(f"  NULL account_number: {null_cnt}")
print(f"  Has account_number: {has_cnt}")
print(f"  Total: {total}")

# Sample account numbers
if has_cnt > 0:
    cur.execute("""
        SELECT DISTINCT account_number
        FROM charters
        WHERE balance < -2000
        AND account_number IS NOT NULL
        LIMIT 20
    """)
    print(f"\nSample account_numbers (first 20):")
    for (acct,) in cur.fetchall():
        print(f"  '{acct}'")

cur.close()
conn.close()
