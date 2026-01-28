#!/usr/bin/env python3
"""
Extract Square-LMS matches and apply to orphaned payments.
"""
import csv
import psycopg2

# Read the latest Square-LMS matches (Jan 7 file with correct structure)
matches = {}  # key: payment_id, value: reserve_number
with open('l:/limo/reports/square_lms_matches_postgres_20260107_233316.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        payment_id_str = row.get('payment_id', '').strip()
        reserve_num = row.get('reserve_number', '').strip()
        
        if payment_id_str and reserve_num:
            try:
                matches[int(payment_id_str)] = reserve_num
            except:
                pass

print(f"Loaded {len(matches)} payment → reserve mappings from file\n")

# Get orphaned payments
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()
cur.execute('''
    SELECT payment_id, amount
    FROM payments
    WHERE square_payment_id IS NOT NULL
    AND reserve_number IS NULL
    AND charter_id IS NULL
    ORDER BY payment_id DESC
''')
orphans = cur.fetchall()
print(f"Found {len(orphans)} orphaned payments\n")

# Apply matches
applied = 0
for payment_id, amt in orphans:
    if payment_id in matches:
        reserve_number = matches[payment_id]
        # Verify charter exists
        cur.execute(
            'SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1',
            (reserve_number,)
        )
        if cur.fetchone():
            cur.execute(
                'UPDATE payments SET reserve_number = %s WHERE payment_id = %s',
                (reserve_number, payment_id)
            )
            print(f"✅ payment_id={payment_id} amount=${amt} -> reserve={reserve_number}")
            applied += 1
        else:
            print(f"⚠️  payment_id={payment_id} reserve={reserve_number} NOT IN DATABASE")

conn.commit()
cur.close()
conn.close()

print(f"\n=== SUMMARY ===")
print(f"Total orphans: {len(orphans)}")
print(f"Applied from matches: {applied}")
print(f"Still unmatched: {len(orphans) - applied}")
