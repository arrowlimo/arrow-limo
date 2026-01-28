"""
Check if NULL reserve_number charges link to actual charters via charter_id.
If they do, check charter status (cancelled vs active).
"""
import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("NULL RESERVE_NUMBER CHARGES - CHARTER LINKAGE ANALYSIS")
print("=" * 80)

# Count by charter linkage status
print("\nCharter linkage status:")
cur.execute("""
    SELECT 
        CASE 
            WHEN charter_id IS NULL THEN 'No charter_id'
            ELSE 'Has charter_id'
        END as linkage_status,
        COUNT(*) as charge_count,
        SUM(amount) as total_amount
    FROM charter_charges
    WHERE reserve_number IS NULL OR reserve_number = ''
    GROUP BY 
        CASE 
            WHEN charter_id IS NULL THEN 'No charter_id'
            ELSE 'Has charter_id'
        END
    ORDER BY charge_count DESC
""")

for row in cur.fetchall():
    status, count, total = row
    print(f"  {status:20s} {count:6,d} charges ${total:15,.2f}")

# For charges with charter_id, check charter status
print("\nCharter status breakdown (for charges WITH charter_id):")
cur.execute("""
    SELECT 
        c.status,
        COUNT(*) as charge_count,
        SUM(cc.amount) as total_amount
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.reserve_number IS NULL OR cc.reserve_number = ''
    GROUP BY c.status
    ORDER BY charge_count DESC
""")

rows = cur.fetchall()
if rows:
    for status, count, total in rows:
        print(f"  {status or 'NULL':20s} {count:6,d} charges ${total:15,.2f}")
else:
    print("  No charges found with charter_id")

# Sample charges with charter_id to see what they look like
print("\nSample charges WITH charter_id (showing charter details):")
cur.execute("""
    SELECT 
        cc.charter_id,
        c.reserve_number,
        c.status,
        c.charter_date,
        cc.description,
        cc.amount,
        cc.charge_type
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.reserve_number IS NULL OR cc.reserve_number = ''
    ORDER BY cc.amount DESC
    LIMIT 10
""")

rows = cur.fetchall()
if rows:
    for charter_id, reserve_num, status, charter_date, desc, amount, charge_type in rows:
        desc_short = (desc[:40] + '...') if desc and len(desc) > 40 else (desc or 'NULL')
        print(f"  Charter ID: {charter_id:6d} | Reserve: {reserve_num or 'NULL':7s} | Status: {status or 'NULL':10s}")
        print(f"    Date: {charter_date} | {desc_short:40s} | ${amount:10,.2f} | {charge_type or 'NULL'}")
else:
    print("  No charges found with charter_id")

# Check if there are charges with BOTH NULL charter_id AND NULL reserve_number
print("\nCharges with NULL charter_id AND NULL reserve_number:")
cur.execute("""
    SELECT 
        COUNT(*) as charge_count,
        SUM(amount) as total_amount
    FROM charter_charges
    WHERE (reserve_number IS NULL OR reserve_number = '')
      AND charter_id IS NULL
""")

count, total = cur.fetchone()
print(f"  {count:6,d} charges ${total:15,.2f}")

if count > 0:
    print("\nSample charges with BOTH NULL:")
    cur.execute("""
        SELECT 
            account_number,
            description,
            amount,
            charge_type,
            created_date
        FROM charter_charges
        WHERE (reserve_number IS NULL OR reserve_number = '')
          AND charter_id IS NULL
        ORDER BY amount DESC
        LIMIT 5
    """)
    
        for acct, desc, amount, charge_type, created_date in cur.fetchall():
            desc_short = (desc[:40] + '...') if desc and len(desc) > 40 else (desc or 'NULL')
            print(f"  Account: {acct or 'NULL':10s} | {desc_short:40s} | ${amount:10,.2f} | {charge_type or 'NULL'} | {created_date}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
