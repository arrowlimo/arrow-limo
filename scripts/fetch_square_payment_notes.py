#!/usr/bin/env python3
"""
Fetch Square payment notes via API and link orphaned payments to charters.
"""
import os
import re
import psycopg2
from square import Square
from dotenv import load_dotenv

# Load environment
load_dotenv('l:/limo/.env')

# Load Square config
token = os.getenv('SQUARE_ACCESS_TOKEN', '').strip()
if not token:
    print("ERROR: SQUARE_ACCESS_TOKEN not set")
    exit(1)

client = Square(token=token)

# Get all orphaned Square payments
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()
cur.execute('''
    SELECT payment_id, square_payment_id, amount, payment_date
    FROM payments
    WHERE square_payment_id IS NOT NULL
    AND reserve_number IS NULL
    AND charter_id IS NULL
    ORDER BY payment_date DESC
''')
orphans = cur.fetchall()
print(f"Found {len(orphans)} orphaned Square payments\n")

# Fetch payment notes from Square
linked = 0
for pid, spid, amt, pdate in orphans:
    try:
        result = client.payments.get(spid)
        # In Square SDK v2, result is directly the payment object
        payment = result.payment if hasattr(result, 'payment') else result
        
        if payment:
            note = payment.note if hasattr(payment, 'note') else payment.get('note', '')
            
            # Extract charter number from note (6 digits)
            charter_match = re.search(r'(\d{6})', note or '')
            if charter_match:
                charter = charter_match.group(1)
                # Verify charter exists
                cur.execute('SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1', (charter,))
                result_check = cur.fetchone()
                if result_check:
                    # Update payment with reserve_number
                    cur.execute(
                        'UPDATE payments SET reserve_number = %s, square_notes = %s WHERE payment_id = %s',
                        (charter, note, pid)
                    )
                    print(f"✅ payment_id={pid} amount=${amt} -> reserve={charter}")
                    linked += 1
                else:
                    print(f"⚠️  payment_id={pid} amount=${amt} charter={charter} NOT FOUND in database")
            else:
                print(f"❌ payment_id={pid} amount=${amt} no charter in note: {(note or '')[:50]}")
        else:
            print(f"❌ payment_id={pid} square_id={spid} no payment data returned")
    except Exception as e:
        print(f"❌ payment_id={pid} exception: {e}")

conn.commit()
cur.close()
conn.close()

print(f"\n=== SUMMARY ===")
print(f"Total orphans: {len(orphans)}")
print(f"Successfully linked: {linked}")
print(f"Unlinked: {len(orphans) - linked}")
