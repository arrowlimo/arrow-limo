"""
Find GL codes for employee/driver pay
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("=" * 100)
print("GL CODES FOR EMPLOYEE/DRIVER PAY")
print("=" * 100)

# Search for pay-related accounts
cur.execute("""
    SELECT account_code, account_name, description, account_type
    FROM chart_of_accounts
    WHERE (
        account_name ILIKE '%pay%'
        OR account_name ILIKE '%wage%'
        OR account_name ILIKE '%salary%'
        OR account_name ILIKE '%employee%'
        OR account_name ILIKE '%driver%'
        OR account_name ILIKE '%labour%'
        OR account_name ILIKE '%labor%'
    )
    AND is_active = true
    ORDER BY account_code
""")

results = cur.fetchall()

if results:
    print(f"\nFound {len(results)} pay-related GL codes:\n")
    print(f"{'Code':<10} {'Account Name':<50} {'Type':<15} Description")
    print("-" * 100)
    
    for code, name, desc, acct_type in results:
        print(f"{code:<10} {name:<50} {acct_type:<15} {desc or ''}")
else:
    print("\nNo pay-related accounts found")

conn.close()
