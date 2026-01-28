#!/usr/bin/env python3
"""
Generate comprehensive Square payment review report for manual linking.
Includes: email, name, payment_key (hash), date, amount, suggested matches.
"""
import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get unmatched Square payments with customer details
cur.execute("""
    SELECT p.payment_id, p.amount, p.payment_date, p.payment_key, 
           p.square_payment_id, p.notes,
           p.square_customer_name, p.square_customer_email
    FROM payments p
    WHERE p.payment_method = 'credit_card'
      AND p.payment_key IS NOT NULL
      AND p.charter_id IS NULL
    ORDER BY p.payment_date DESC, p.amount DESC
""")
unmatched = cur.fetchall()

print(f"=== GENERATING SQUARE REVIEW REPORT ===\n")
print(f"Total unmatched: {len(unmatched)}")
print(f"Total amount: ${sum(float(p['amount']) for p in unmatched):,.2f}\n")

# Identify recurring (suspicious)
amount_groups = defaultdict(list)
for p in unmatched:
    amt = round(float(p['amount']), 2)
    amount_groups[amt].append(p)

recurring_amounts = {amt for amt, pays in amount_groups.items() if len(pays) >= 3}

# Build output report
output_file = r'l:\limo\reports\SQUARE_PAYMENTS_MANUAL_REVIEW_2026-01-08.csv'
rows = []

for p in unmatched:
    amt = round(float(p['amount']), 2)
    
    # Determine status
    if amt in recurring_amounts:
        status = "RECURRING"
        action = "Verify if Square Capital loan repayment"
    else:
        status = "CLEAN"
        action = "Find matching charter and link"
    
    # Get potential charter matches (within 10% amount tolerance)
    cur.execute("""
        SELECT charter_id, reserve_number,
               total_amount_due, balance, paid_amount
        FROM charters
        WHERE ABS(total_amount_due - %s) / NULLIF(total_amount_due, 0) <= 0.10
           OR ABS(balance - %s) / NULLIF(ABS(balance), 0) <= 0.10
        ORDER BY ABS(total_amount_due - %s)
        LIMIT 3
    """, (amt, amt, amt))
    
    potential_matches = cur.fetchall()
    suggested_reserves = ', '.join([m['reserve_number'] for m in potential_matches]) if potential_matches else 'None'
    
    rows.append({
        'payment_id': p['payment_id'],
        'amount': float(p['amount']),
        'payment_date': p['payment_date'],
        'payment_key': p['payment_key'],
        'square_payment_id': p['square_payment_id'] or '',
        'customer_email': p['square_customer_email'] or '',
        'customer_name': p['square_customer_name'] or '',
        'notes': (p['notes'] or '')[:100],
        'status': status,
        'suggested_reserves': suggested_reserves,
        'action_needed': action
    })

# Write CSV
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['payment_id', 'amount', 'payment_date', 'payment_key', 'square_payment_id',
                  'customer_email', 'customer_name', 'notes', 
                  'status', 'suggested_reserves', 'action_needed']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✓ Report saved: {output_file}")
print(f"\nBreakdown:")
clean = [r for r in rows if r['status'] == 'CLEAN']
recurring = [r for r in rows if r['status'] == 'RECURRING']
print(f"  Clean payments: {len(clean)} (${sum(r['amount'] for r in clean):,.2f})")
print(f"  Recurring (suspicious): {len(recurring)} (${sum(r['amount'] for r in recurring):,.2f})")

cur.close()
conn.close()
