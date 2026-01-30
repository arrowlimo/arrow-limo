#!/usr/bin/env python3
"""
Extract charter numbers from Square emails and match to orphaned payments.
"""
import csv
import re
import psycopg2
from datetime import datetime

# Read Square emails
with open('l:/limo/reports/square_emails.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    square_data = list(reader)

# Extract charter/reserve from message_excerpt
charter_pattern = re.compile(r'(?:Note|note|Ref|ref|#|Charter|Reserve|Order)[\s:]*(\d{6})')
charter_matches = {}

for row in square_data:
    excerpt = row.get('message_excerpt', '')
    amount = row.get('amount', '')
    email_date = row.get('email_date', '')
    msg_type = row.get('type', '')
    
    # Extract charter number
    m = charter_pattern.search(excerpt)
    charter = m.group(1) if m else None
    
    if charter and amount:
        try:
            amt_float = float(amount)
            # Use amount as key for matching
            key = (amt_float, email_date[:10])  # amount + date
            if key not in charter_matches:
                charter_matches[key] = charter
        except:
            pass

print(f"Extracted {len(charter_matches)} charter-amount-date combos from Square emails\n")

# Match to orphans
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
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

matches_found = 0
for pid, amt, pdate, spid in orphans:
    key = (float(amt), pdate.strftime('%Y-%m-%d'))
    if key in charter_matches:
        charter = charter_matches[key]
        print(f"MATCH: payment_id={pid} amount=${amt} date={pdate} -> charter={charter}")
        matches_found += 1
    else:
        print(f"NO MATCH: payment_id={pid} amount=${amt} date={pdate} square_id={spid}")

print(f"\n=== SUMMARY ===")
print(f"Total orphans: {len(orphans)}")
print(f"Matched: {matches_found}")
print(f"Unmatched: {len(orphans) - matches_found}")

cur.close()
conn.close()
