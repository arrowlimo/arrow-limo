#!/usr/bin/env python3
"""Sync 2025 reserve_number from LMS to PostgreSQL payments"""
import pyodbc
import psycopg2
from datetime import timedelta

# LMS connection
lms_conn = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\New folder\lms.mdb')
lms_cur = lms_conn.cursor()

# PostgreSQL connection
pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print("\n" + "="*80)
print("SYNCING RESERVE_NUMBER FROM LMS TO POSTGRESQL (2025)")
print("="*80)

# Get PostgreSQL 2025 payments missing reserve_number
pg_cur.execute("""
    SELECT 
        payment_id,
        amount,
        payment_date,
        payment_method,
        account_number
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2025
    AND reserve_number IS NULL
    ORDER BY payment_date
""")

pg_payments = pg_cur.fetchall()
print(f"\n📊 PostgreSQL 2025 payments missing reserve_number: {len(pg_payments):,}")

if len(pg_payments) == 0:
    print("✅ All 2025 payments already have reserve_number!")
    lms_conn.close()
    pg_conn.close()
    exit(0)

# Get all LMS payments
lms_cur.execute("""
    SELECT 
        Account_No,
        Amount,
        Reserve_No
    FROM Payment
    WHERE Reserve_No IS NOT NULL
    AND Reserve_No <> ''
""")

# Build lookup: (account, amount) -> list of reserve_numbers
lms_payments = {}
for acct, amt, reserve in lms_cur.fetchall():
    key = (acct, amt)
    if key not in lms_payments:
        lms_payments[key] = []
    lms_payments[key].append(reserve)

print(f"📊 LMS payment combinations (Account+Amount): {len(lms_payments):,}")

# Match PostgreSQL to LMS
matches = []
ambiguous = []
for pg_id, pg_amt, pg_date, pg_method, pg_acct in pg_payments:
    # Match by account + amount
    key = (pg_acct, pg_amt)
    if key in lms_payments:
        reserves = lms_payments[key]
        if len(reserves) == 1:
            # Unambiguous match
            matches.append((pg_id, reserves[0], pg_amt, pg_date, 'unique'))
        else:
            # Multiple possible reserves - skip for manual review
            ambiguous.append((pg_id, pg_amt, pg_date, len(reserves)))

print(f"\n🔗 Matching Results:")
print(f"   Unique matches: {len(matches):,}")
print(f"   Ambiguous (multiple reserves): {len(ambiguous):,}")
print(f"   Unmatched: {len(pg_payments) - len(matches) - len(ambiguous):,}")

# Show sample matches
print(f"\n📋 Sample Matches (first 10):")
print(f"{'PG ID':<10} {'Reserve':<10} {'Amount':<12} {'Date':<12} {'Match Type'}")
print("-" * 70)
for pg_id, reserve, amt, date, match_type in matches[:10]:
    print(f"{pg_id:<10} {reserve:<10} ${amt:<11,.2f} {str(date):<12} {match_type}")

# Apply updates
print(f"\n" + "="*80)
response = input(f"Update {len(matches):,} payments with reserve_number from LMS? (yes/no): ").strip().lower()

if response == 'yes':
    updated = 0
    for pg_id, reserve, amt, date, match_type in matches:
        pg_cur.execute("""
            UPDATE payments
            SET reserve_number = %s
            WHERE payment_id = %s
        """, (reserve, pg_id))
        updated += pg_cur.rowcount
    
    pg_conn.commit()
    print(f"\n✅ Updated {updated:,} payments with reserve_number")
    
    # Verify
    pg_cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) = 2025
    """)
    total, no_res = pg_cur.fetchone()
    print(f"\n📈 2025 Payment Status After Sync:")
    print(f"   Total: {total:,}")
    print(f"   With reserve_number: {total - no_res:,} ({(total-no_res)/total*100:.1f}%)")
    print(f"   Missing reserve_number: {no_res:,} ({no_res/total*100:.1f}%)")
else:
    pg_conn.rollback()
    print("❌ No changes made")

lms_conn.close()
pg_conn.close()

print("\n" + "="*80)
