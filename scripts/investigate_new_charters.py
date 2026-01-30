#!/usr/bin/env python3
"""
Investigate the 3 'new' charters and their customers.
"""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("="*80)
print("INVESTIGATING 3 'NEW' CHARTERS")
print("="*80)

# Find the 3 new charters
print("\n1. NEW CHARTERS FROM STAGING (not in main table)")
cur.execute("""
    SELECT 
        lsr.reserve_no,
        lsr.raw_data->>'PU_Date' as pu_date,
        lsr.raw_data->>'Account_No' as account_no,
        lsr.raw_data->>'Name' as customer_name,
        lsr.raw_data->>'Rate' as rate,
        lsr.raw_data->>'Balance' as balance,
        lsr.raw_data->>'Vehicle' as vehicle
    FROM lms_staging_reserve lsr
    WHERE NOT EXISTS (
        SELECT 1 FROM charters c 
        WHERE lsr.reserve_no = c.reserve_number
    )
    ORDER BY (lsr.raw_data->>'PU_Date')::DATE
""")
rows = cur.fetchall()
print(f"\nFound {len(rows)} new charters:")
print(f"{'Reserve#':<10} {'Date':<12} {'Account':<10} {'Customer':<30} {'Rate':<12} {'Balance':<12}")
print("-"*90)

new_accounts = set()
for row in rows:
    rate = float(row[4]) if row[4] else 0
    balance = float(row[5]) if row[5] else 0
    print(f"{row[0]:<10} {row[1]:<12} {row[2]:<10} {row[3]:<30} ${rate:>10,.2f} ${balance:>10,.2f}")
    if row[2]:
        new_accounts.add(row[2])

# Check if these account numbers exist in clients table
print(f"\n2. CUSTOMER ANALYSIS FOR NEW CHARTERS")
print(f"   Unique account numbers in new charters: {len(new_accounts)}")

for account in sorted(new_accounts):
    print(f"\n   Account: {account}")
    
    # Check in clients table
    cur.execute("""
        SELECT client_id, client_name, account_number
        FROM clients
        WHERE account_number = %s
    """, (account,))
    client = cur.fetchone()
    
    if client:
        print(f"   [OK] Customer EXISTS in clients table")
        print(f"      Client ID: {client[0]} | Name: {client[1]}")
    else:
        print(f"   [FAIL] Customer NOT FOUND in clients table")
        
        # Check if customer is in staging
        cur.execute("""
            SELECT raw_data->>'Name', raw_data->>'Phone', raw_data->>'Email'
            FROM lms_staging_customer
            WHERE raw_data->>'Account_No' = %s
        """, (account,))
        staging = cur.fetchone()
        
        if staging:
            print(f"   📋 Found in STAGING: {staging[0]} | Phone: {staging[1]} | Email: {staging[2]}")
        else:
            print(f"   [WARN]  Not in staging either!")

# Check all unique account numbers in staging reserves vs clients table
print("\n3. ALL ACCOUNT NUMBERS IN STAGING RESERVES")
cur.execute("""
    SELECT COUNT(DISTINCT raw_data->>'Account_No') as total_accounts
    FROM lms_staging_reserve
    WHERE raw_data->>'Account_No' IS NOT NULL 
    AND raw_data->>'Account_No' != ''
""")
total = cur.fetchone()[0]
print(f"   Total unique account numbers in staging reserves: {total:,}")

cur.execute("""
    SELECT COUNT(DISTINCT lsr.raw_data->>'Account_No')
    FROM lms_staging_reserve lsr
    WHERE lsr.raw_data->>'Account_No' IS NOT NULL 
    AND lsr.raw_data->>'Account_No' != ''
    AND NOT EXISTS (
        SELECT 1 FROM clients c
        WHERE c.account_number = lsr.raw_data->>'Account_No'
    )
""")
missing = cur.fetchone()[0]
print(f"   Account numbers NOT in clients table: {missing:,}")

if missing > 0:
    print(f"\n   Sample missing account numbers:")
    cur.execute("""
        SELECT DISTINCT 
            lsr.raw_data->>'Account_No' as account,
            lsr.raw_data->>'Name' as name,
            COUNT(*) as charter_count
        FROM lms_staging_reserve lsr
        WHERE lsr.raw_data->>'Account_No' IS NOT NULL 
        AND lsr.raw_data->>'Account_No' != ''
        AND NOT EXISTS (
            SELECT 1 FROM clients c
            WHERE c.account_number = lsr.raw_data->>'Account_No'
        )
        GROUP BY lsr.raw_data->>'Account_No', lsr.raw_data->>'Name'
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    print(f"\n   {'Account':<15} {'Customer Name':<40} {'Charters':<10}")
    print("   " + "-"*70)
    for row in cur.fetchall():
        print(f"   {row[0]:<15} {row[1]:<40} {row[2]:<10}")

cur.close()
conn.close()
