#!/usr/bin/env python3
"""
Verify e-transfer payment matching status.
Previous runs achieved 98% match rate - check current status.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== E-TRANSFER PAYMENT MATCHING STATUS ===\n")

# Get e-transfer payment stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(charter_id) as matched,
        COUNT(*) - COUNT(charter_id) as unmatched,
        SUM(amount) as total_amount,
        SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unmatched_amount
    FROM payments
    WHERE payment_method = 'bank_transfer'
""")
stats = cur.fetchone()

if stats['total'] == 0:
    print("⚠️  NO E-TRANSFER PAYMENTS FOUND IN DATABASE")
    print("   Payment method might be recorded differently")
    print("\nChecking alternative payment method values...\n")
    
    cur.execute("""
        SELECT payment_method, COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE payment_method IS NOT NULL
        GROUP BY payment_method
        ORDER BY count DESC
    """)
    all_methods = cur.fetchall()
    
    print("Payment methods in database:")
    for m in all_methods:
        print(f"  {m['payment_method']}: {m['count']} payments (${float(m['total'] or 0):,.2f})")
    
else:
    total = stats['total']
    matched = stats['matched']
    unmatched = stats['unmatched']
    match_rate = (matched / total * 100) if total > 0 else 0
    
    print(f"Total e-transfers: {total}")
    print(f"Matched to charters: {matched}")
    print(f"Unmatched: {unmatched}")
    print(f"Match rate: {match_rate:.1f}%")
    print(f"\nTotal amount: ${float(stats['total_amount'] or 0):,.2f}")
    print(f"Unmatched amount: ${float(stats['unmatched_amount'] or 0):,.2f}")
    
    if match_rate < 95:
        print(f"\n⚠️  MATCH RATE BELOW EXPECTED 98%")
        print(f"   Previous: ~98%, Current: {match_rate:.1f}%")
        print(f"   Difference: {98 - match_rate:.1f}% points")
    else:
        print(f"\n✓ Match rate is good ({match_rate:.1f}%)")
    
    # Get unmatched details
    if unmatched > 0:
        print(f"\n=== UNMATCHED E-TRANSFERS ===\n")
        cur.execute("""
            SELECT payment_id, amount, payment_date, reserve_number, notes
            FROM payments
            WHERE payment_method = 'bank_transfer'
              AND charter_id IS NULL
            ORDER BY amount DESC
            LIMIT 20
        """)
        unmatched_list = cur.fetchall()
        
        for i, p in enumerate(unmatched_list, 1):
            print(f"{i}. Payment {p['payment_id']}: ${float(p['amount']):,.2f} on {p['payment_date']}")
            if p['reserve_number']:
                print(f"   Reserve: {p['reserve_number']}")
            if p['notes']:
                print(f"   Notes: {p['notes'][:80]}")
            print()

cur.close()
conn.close()
