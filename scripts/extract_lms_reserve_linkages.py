#!/usr/bin/env python3
"""
Extract LMS Payment.Reserve_No and update PostgreSQL payments.

Match strategy:
1. Amount + Account_No + Key (best match)
2. Amount + LastUpdated date (±7 days)
3. Export to CSV for manual review
"""

import pyodbc
import psycopg2
import csv
from datetime import datetime, timedelta

LMS_PATH = r'L:\New folder\lms.mdb'

def normalize_reserve(reserve):
    if not reserve:
        return None
    reserve = str(reserve).strip()
    return reserve.zfill(6) if reserve.isdigit() else None

print("="*80)
print("EXTRACT LMS PAYMENT RESERVE_NO LINKAGES")
print("="*80)

# Extract from LMS
print(f"\n📥 Extracting from LMS...")
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
lms_cur = lms_conn.cursor()

lms_cur.execute("""
    SELECT PaymentID, Account_No, Amount, Reserve_No, Key, LastUpdated
    FROM Payment
    WHERE Reserve_No IS NOT NULL AND Amount IS NOT NULL
    ORDER BY LastUpdated DESC
""")

lms_data = []
for row in lms_cur.fetchall():
    lms_data.append({
        'lms_id': row[0],
        'account': row[1],
        'amount': float(row[2]) if row[2] else 0,
        'reserve': normalize_reserve(row[3]),
        'key': row[4],
        'date': row[5]
    })

lms_cur.close()
lms_conn.close()

print(f"   Extracted {len(lms_data):,} LMS payments with Reserve_No")

# Get PostgreSQL payments missing reserve
print(f"\n🐘 Querying PostgreSQL...")
pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

pg_cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, account_number,
           notes, created_at
    FROM payments
    WHERE reserve_number IS NULL
""")

pg_missing = {}
for row in pg_cur.fetchall():
    pg_missing[row[0]] = {
        'amount': float(row[1]) if row[1] else 0,
        'date': row[2],
        'key': row[3],
        'account': row[4],
        'notes': row[5],
        'created': row[6]
    }

print(f"   PostgreSQL has {len(pg_missing):,} payments missing reserve_number")

# Export LMS data to CSV for review
csv_path = r'L:\limo\reports\lms_payment_reserve_export.csv'
print(f"\n💾 Exporting to CSV: {csv_path}")

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['lms_id', 'account', 'amount', 'reserve', 'key', 'date'])
    writer.writeheader()
    writer.writerows(lms_data)

print(f"   Exported {len(lms_data):,} records")

# Match by Key field
print(f"\n🔍 Matching LMS → PostgreSQL by Key...")
key_matches = []

for lms_pmt in lms_data:
    if not lms_pmt['key']:
        continue
    
    for pg_id, pg_pmt in pg_missing.items():
        if pg_pmt['key'] == lms_pmt['key']:
            # Verify amount within $0.10
            if abs(pg_pmt['amount'] - lms_pmt['amount']) < 0.10:
                key_matches.append((pg_id, lms_pmt['reserve'], lms_pmt['amount'], lms_pmt['key']))
                break

print(f"   Found {len(key_matches):,} matches by Key")

if key_matches:
    print(f"\n📋 Sample Key matches (first 20):")
    for pg_id, reserve, amt, key in key_matches[:20]:
        print(f"      Payment {pg_id} → Reserve {reserve} (${amt:.2f}, Key: {key})")

# Match by Amount + Account
print(f"\n🔍 Matching by Amount + Account...")
amount_matches = []

matched_pg_ids = set(m[0] for m in key_matches)

for lms_pmt in lms_data:
    if not lms_pmt['account']:
        continue
    
    for pg_id, pg_pmt in pg_missing.items():
        if pg_id in matched_pg_ids:
            continue
            
        if pg_pmt['account'] == lms_pmt['account']:
            if abs(pg_pmt['amount'] - lms_pmt['amount']) < 0.01:
                # Check date proximity if available
                date_ok = True
                if pg_pmt['date'] and lms_pmt['date']:
                    days_diff = abs((pg_pmt['date'] - lms_pmt['date']).days)
                    date_ok = days_diff <= 30
                
                if date_ok:
                    amount_matches.append((pg_id, lms_pmt['reserve'], lms_pmt['amount'], lms_pmt['account']))
                    matched_pg_ids.add(pg_id)
                    break

print(f"   Found {len(amount_matches):,} matches by Amount + Account")

# Summary
total_matches = len(key_matches) + len(amount_matches)
print(f"\n📈 TOTAL MATCHES: {total_matches:,}")

if total_matches > 0:
    response = input(f"\n💡 Apply {total_matches:,} reserve_number updates? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        print(f"\n💾 Applying updates...")
        
        all_matches = key_matches + amount_matches
        for i, (pg_id, reserve, amt, ref) in enumerate(all_matches, 1):
            pg_cur.execute("""
                UPDATE payments
                SET reserve_number = %s
                WHERE payment_id = %s
            """, (reserve, pg_id))
            
            if i % 100 == 0:
                print(f"   Updated {i:,} payments...")
        
        pg_conn.commit()
        print(f"\n✅ Committed {total_matches:,} reserve_number updates")
        
        # Verify
        pg_cur.execute("SELECT COUNT(*), COUNT(reserve_number) FROM payments")
        total, with_reserve = pg_cur.fetchone()
        print(f"\n📊 NEW STATE:")
        print(f"   Total: {total:,}")
        print(f"   With reserve: {with_reserve:,} ({with_reserve/total*100:.1f}%)")
        print(f"   Missing: {total-with_reserve:,}")
    else:
        print(f"\n❌ Cancelled - no changes made")

pg_cur.close()
pg_conn.close()

print(f"\n" + "="*80)
print("COMPLETE")
print("="*80)
print(f"\n💡 CSV export: {csv_path}")
print(f"   (Contains all 24,587 LMS Payment records with Reserve_No)")
