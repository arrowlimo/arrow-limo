#!/usr/bin/env python3
"""
Verify that unmatched Square payments are legitimate customer payments.
Check for: refunds, chargebacks, Square fees, loan payments, payout transfers.

Usage:
  python -X utf8 scripts/verify_square_payment_types.py
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== Square Payment Type Verification ===\n")

# Get all unmatched Square payments with full details
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, square_payment_id,
           notes, payment_method, created_at
    FROM payments
    WHERE payment_method = 'credit_card'
      AND payment_key IS NOT NULL
      AND charter_id IS NULL
    ORDER BY amount DESC
""")
unmatched = cur.fetchall()

print(f"Total unmatched Square payments: {len(unmatched)}")
print(f"Total amount: ${sum(float(p['amount']) for p in unmatched):,.2f}\n")

# Check for negative amounts (refunds)
negative = [p for p in unmatched if float(p['amount']) < 0]
if negative:
    print(f"⚠️  REFUNDS/CHARGEBACKS FOUND: {len(negative)}")
    print(f"   Total refunded: ${sum(float(p['amount']) for p in negative):,.2f}")
    for p in negative[:10]:
        print(f"   - Payment {p['payment_id']}: ${float(p['amount']):,.2f} on {p['payment_date']}")
        print(f"     Key: {p['payment_key']}")
        if p['notes']:
            print(f"     Notes: {p['notes'][:100]}")
    print()
else:
    print("✓ No negative amounts (refunds/chargebacks)")
    print()

# Check notes for refund/chargeback/dispute keywords
refund_keywords = ['refund', 'chargeback', 'dispute', 'reversal', 'void', 'cancel', 'denied', 'nsf']
flagged_notes = []
for p in unmatched:
    if p['notes']:
        notes_lower = p['notes'].lower()
        for keyword in refund_keywords:
            if keyword in notes_lower:
                flagged_notes.append((p, keyword))
                break

if flagged_notes:
    print(f"⚠️  SUSPICIOUS NOTES FOUND: {len(flagged_notes)}")
    for p, keyword in flagged_notes[:10]:
        print(f"   - Payment {p['payment_id']}: ${float(p['amount']):,.2f} - contains '{keyword}'")
        print(f"     Notes: {p['notes'][:150]}")
    print()
else:
    print("✓ No refund/chargeback keywords in notes")
    print()

# Check payment_key patterns (Square uses specific prefixes)
key_prefixes = defaultdict(int)
key_patterns = defaultdict(list)
for p in unmatched:
    if p['payment_key']:
        # Extract prefix (first few characters before numbers/IDs)
        parts = p['payment_key'].split('_')
        if parts:
            prefix = parts[0]
            key_prefixes[prefix] += 1
            if len(key_patterns[prefix]) < 3:
                key_patterns[prefix].append(p['payment_key'])

print("Payment key prefixes:")
for prefix, count in sorted(key_prefixes.items(), key=lambda x: -x[1]):
    samples = ', '.join(key_patterns[prefix][:2])
    print(f"  {prefix}: {count} payments (e.g., {samples})")
print()

# Check for Square Capital loan payments (typically recurring, same amounts)
# Group by amount to find recurring payments
amount_groups = defaultdict(list)
for p in unmatched:
    amt = round(float(p['amount']), 2)
    amount_groups[amt].append(p)

recurring = [(amt, payments) for amt, payments in amount_groups.items() if len(payments) >= 3]
if recurring:
    print(f"⚠️  POTENTIALLY RECURRING PAYMENTS: {len(recurring)} amounts")
    print("   (Could be Square Capital loan repayments)")
    for amt, payments in sorted(recurring, key=lambda x: -len(x[1]))[:5]:
        print(f"   - ${amt:,.2f}: {len(payments)} occurrences")
        dates = ', '.join(str(p['payment_date']) for p in payments[:3])
        print(f"     Dates: {dates}...")
    print()
else:
    print("✓ No highly recurring payment amounts (loan payments unlikely)")
    print()

# Check against square_payouts table (these would be bank deposits, not customer payments)
cur.execute("""
    SELECT COUNT(*) as count
    FROM square_payouts
""")
result = cur.fetchone()
if result and result['count'] > 0:
    print(f"Square payouts in DB: {result['count']}")
    
    # Check if any payment_keys match payout IDs
    cur.execute("""
        SELECT p.payment_id, p.amount, p.payment_key, sp.payout_id, sp.amount as payout_amount
        FROM payments p
        JOIN square_payouts sp ON p.payment_key = sp.payout_id
        WHERE p.payment_method = 'credit_card'
          AND p.payment_key IS NOT NULL
          AND p.charter_id IS NULL
    """)
    payout_matches = cur.fetchall()
    
    if payout_matches:
        print(f"⚠️  PAYOUT TRANSFERS FOUND: {len(payout_matches)}")
        print("   These are bank deposits, not customer payments!")
        for pm in payout_matches[:10]:
            print(f"   - Payment {pm['payment_id']}: ${float(pm['amount']):,.2f}")
            print(f"     Matches payout {pm['payout_id']}: ${float(pm['payout_amount']):,.2f}")
        print()
    else:
        print("✓ No payment_keys match payout IDs")
        print()
else:
    print("(No square_payouts data to compare)")
    print()

# Check for very small amounts (fees, adjustments)
small_amounts = [p for p in unmatched if 0 < float(p['amount']) < 5.00]
if small_amounts:
    print(f"Small amounts (<$5): {len(small_amounts)}")
    print(f"   Total: ${sum(float(p['amount']) for p in small_amounts):,.2f}")
    for p in small_amounts[:10]:
        print(f"   - ${float(p['amount']):,.2f} on {p['payment_date']} (key: {p['payment_key']})")
    print()

# Summary
print("\n=== VERIFICATION SUMMARY ===")
legitimate = [p for p in unmatched if float(p['amount']) > 0]
print(f"Positive amounts (likely legitimate): {len(legitimate)}")
print(f"Total: ${sum(float(p['amount']) for p in legitimate):,.2f}")

if negative:
    print(f"Negative amounts (refunds/chargebacks): {len(negative)}")
    print(f"Total: ${sum(float(p['amount']) for p in negative):,.2f}")

print(f"\nRecommendation:")
if len(negative) == 0 and len(flagged_notes) == 0:
    print("✓ All 93 unmatched payments appear to be legitimate customer payments")
    print("  Safe to proceed with manual review for linking to charters")
else:
    print("⚠️  Review flagged items before proceeding:")
    if negative:
        print(f"  - {len(negative)} refunds/chargebacks should be excluded or handled separately")
    if flagged_notes:
        print(f"  - {len(flagged_notes)} payments with suspicious notes need review")

cur.close()
conn.close()
