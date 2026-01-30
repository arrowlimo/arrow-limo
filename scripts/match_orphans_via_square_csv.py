#!/usr/bin/env python3
"""
Extract charter numbers from square_emails.csv and match to orphaned payments.
"""
import csv
import re
import psycopg2
from datetime import datetime, timedelta

# Read the extracted Square emails CSV
print("Reading square_emails.csv...")
with open('l:/limo/reports/square_emails.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Loaded {len(rows)} email rows from CSV\n")

# Extract charters and amounts from emails
charter_matches = {}  # key: (amount, email_date_date), value: charter
for row in rows:
    excerpt = row.get('message_excerpt', '')
    amount_str = row.get('amount', '')
    email_date = row.get('email_date', '')
    msg_type = row.get('type', '')
    
    try:
        amt = float(amount_str) if amount_str else None
    except:
        amt = None
    
    if not amt or not email_date:
        continue
    
    # Extract 6-digit charter from excerpt
    m = re.search(r'res(?:erve)?\s+(\d{6})|(\d{6})', excerpt, re.IGNORECASE)
    if m:
        charter = m.group(1) or m.group(2)
        email_date_only = email_date[:10]  # YYYY-MM-DD
        key = (amt, email_date_only)
        charter_matches[key] = charter

print(f"Extracted {len(charter_matches)} charter-amount-date matches from emails\n")

# Get orphaned payments and match
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()
cur.execute('''
    SELECT payment_id, amount, payment_date, square_payment_id
    FROM payments
    WHERE square_payment_id IS NOT NULL
    AND reserve_number IS NULL
    AND charter_id IS NULL
    ORDER BY payment_date DESC
''')
orphans = cur.fetchall()

print(f"Found {len(orphans)} orphaned Square payments\n")

matched = 0
for pid, amt, pdate, spid in orphans:
    key = (float(amt), pdate.strftime('%Y-%m-%d'))
    
    if key in charter_matches:
        charter = charter_matches[key]
        # Verify charter exists
        cur.execute('SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1', (charter,))
        result = cur.fetchone()
        if result:
            cur.execute(
                'UPDATE payments SET reserve_number = %s WHERE payment_id = %s',
                (charter, pid)
            )
            print(f"✅ payment_id={pid} amount=${amt} date={pdate.date()} -> reserve={charter}")
            matched += 1
        else:
            print(f"⚠️  payment_id={pid} amount=${amt} charter={charter} NOT IN DATABASE")
    else:
        print(f"❌ payment_id={pid} amount=${amt} date={pdate.date()} NO MATCH")

conn.commit()
cur.close()
conn.close()

print(f"\n=== SUMMARY ===")
print(f"Total orphans: {len(orphans)}")
print(f"Matched: {matched}")
print(f"Unmatched: {len(orphans) - matched}")
