#!/usr/bin/env python3
"""
Link cash and trade_of_services payments (Fibrenew, etc.) to charters.
These are often missed in automated matching.

Usage:
  python -X utf8 scripts/link_trade_of_services_payments.py         # dry run
  python -X utf8 scripts/link_trade_of_services_payments.py --write # apply
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

write = '--write' in sys.argv

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== TRADE OF SERVICES / CASH PAYMENT LINKING ===\n")

# Get unmatched trade_of_services and cash payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_method, 
           reserve_number, notes
    FROM payments
    WHERE payment_method IN ('trade_of_services', 'cash')
      AND charter_id IS NULL
    ORDER BY payment_method, payment_date DESC
""")
unmatched = cur.fetchall()

if not unmatched:
    print("✓ All trade_of_services and cash payments are already linked")
    cur.close()
    conn.close()
    sys.exit(0)

print(f"Found {len(unmatched)} unmatched payments:")

by_method = {}
for p in unmatched:
    method = p['payment_method']
    if method not in by_method:
        by_method[method] = []
    by_method[method].append(p)

for method, payments in by_method.items():
    total = sum(float(p['amount']) for p in payments)
    print(f"  {method}: {len(payments)} payments (${total:,.2f})")

print()

# Try to link by reserve_number
linked = 0
failed = 0

for p in unmatched:
    print(f"Payment {p['payment_id']}: ${float(p['amount']):,.2f} ({p['payment_method']})")
    print(f"  Date: {p['payment_date']}")
    if p['notes']:
        print(f"  Notes: {p['notes'][:80]}")
    
    if p['reserve_number']:
        # Find charter by reserve_number
        cur.execute("""
            SELECT charter_id, reserve_number, total_amount_due, balance
            FROM charters
            WHERE reserve_number = %s
        """, (p['reserve_number'],))
        
        charter = cur.fetchone()
        
        if charter:
            print(f"  ✓ Found charter: {charter['charter_id']} (reserve {charter['reserve_number']})")
            print(f"    Balance: ${float(charter['balance'] or 0):,.2f}")
            
            if write:
                # Link payment to charter
                cur.execute("""
                    UPDATE payments
                    SET charter_id = %s,
                        notes = COALESCE(notes, '') || %s,
                        last_updated = NOW()
                    WHERE payment_id = %s
                """, (
                    charter['charter_id'],
                    f" [AUTO-LINKED: reserve_number match on {p['payment_date']}]",
                    p['payment_id']
                ))
                
                # Recalculate charter balance
                cur.execute("""
                    WITH payment_sum AS (
                        SELECT COALESCE(SUM(amount), 0) AS total_paid
                        FROM payments
                        WHERE reserve_number = %s
                    )
                    UPDATE charters AS c
                    SET paid_amount = ps.total_paid,
                        balance = COALESCE(total_amount_due, 0) - ps.total_paid,
                        updated_at = NOW()
                    FROM payment_sum ps
                    WHERE c.reserve_number = %s
                """, (p['reserve_number'], p['reserve_number']))
                
                linked += 1
                print(f"    → Linked and balance updated")
            else:
                print(f"    → Would link (use --write to apply)")
                linked += 1
        else:
            print(f"  ✗ No charter found for reserve {p['reserve_number']}")
            failed += 1
    else:
        print(f"  ⚠️  No reserve_number - manual review needed")
        failed += 1
    
    print()

if write:
    conn.commit()
    print(f"\n✓ COMMITTED: Linked {linked} payments")
else:
    print(f"\nDRY RUN: Would link {linked} payments")
    print(f"Run with --write to apply")

if failed > 0:
    print(f"\nFailed to link: {failed} payments (need manual review)")

cur.close()
conn.close()
