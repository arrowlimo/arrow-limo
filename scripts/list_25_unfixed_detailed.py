#!/usr/bin/env python3
"""
Detailed list of 25 unfixed receivables for review.
Shows charges, payments, and balance for each reserve.
"""

import psycopg2
import json

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

UNFIXED_RESERVES = [
    '015940', '014189', '017887', '001764', '015978', '014640', '005711',
    '015211', '015195', '015049', '017765', '018013', '015315', '015288',
    '015244', '015144', '017301', '017891', '013874'
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("DETAILED REVIEW: 25 Unfixed Receivables")
print("=" * 120)
print()

total_owed = 0.0

for i, reserve in enumerate(UNFIXED_RESERVES, 1):
    # Charter info
    cur.execute("""
        SELECT charter_date, status
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    row = cur.fetchone()
    if not row:
        print(f"{i}. {reserve}: NOT FOUND")
        continue
    
    charter_date, status = row
    customer_name = None
    location = None
    
    # Charges
    cur.execute("""
        SELECT description, amount, created_at
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY created_at DESC
    """, (reserve,))
    charges = cur.fetchall()
    total_charges = sum(float(c[1]) for c in charges)
    
    # Payments
    cur.execute("""
        SELECT payment_method, amount, payment_date
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date DESC
    """, (reserve,))
    payments = cur.fetchall()
    total_payments = sum(float(p[1]) for p in payments)
    
    balance = total_charges - total_payments
    total_owed += balance
    
    # Print charter info
    print(f"{i}. {reserve} | {charter_date if charter_date else '?'} | Status: {status or 'BLANK'}")
    print(f"   Customer: {customer_name or '?'} | Location: {location or '?'}")
    
    # Charges
    if charges:
        print(f"   CHARGES (${total_charges:,.2f}):")
        for desc, amt, created in charges[:5]:  # Show top 5
            date_str = str(created).split()[0] if created else '?'
            print(f"      - {desc:<40} ${float(amt):>10.2f}  ({date_str})")
        if len(charges) > 5:
            print(f"      ... and {len(charges) - 5} more")
    else:
        print(f"   CHARGES: (none)")
    
    # Payments
    if payments:
        print(f"   PAYMENTS (${total_payments:,.2f}):")
        for method, amt, paid in payments:
            date_str = str(paid).split()[0] if paid else '?'
            method_str = method or 'unknown'
            print(f"      - {method_str:<40} ${float(amt):>10.2f}  ({date_str})")
    else:
        print(f"   PAYMENTS: (none)")
    
    # Balance
    print(f"   BALANCE: ${balance:>10.2f}")
    
    # Decision note
    if 'cancel' in (status or '').lower():
        print(f"   NOTE: Marked CANCELLED but still has charges")
    elif status == 'UNCLOSED':
        print(f"   NOTE: UNCLOSED status - may still be in progress?")
    elif status == 'Closed' and balance > 0:
        print(f"   NOTE: Closed but unpaid balance remains")
    
    print()

print("=" * 120)
print(f"TOTAL 25 RESERVES: ${total_owed:,.2f} owed")
print("=" * 120)
print()
print("DECISION NEEDED:")
print("  These are aged receivables (mostly 2008-2023) with unpaid balances.")
print("  Following your LMS methodology (avoid tax on unreceived revenue),")
print("  should these be written down (charges removed) to zero out balances?")
print()
print("  Reply with decision:")
print("    - 'writedown all' = remove all 25 charges")
print("    - 'writedown cancelled' = remove only 4 cancelled reserves")
print("    - 'investigate' = review manually case-by-case")

cur.close()
conn.close()
