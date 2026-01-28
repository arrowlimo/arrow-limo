#!/usr/bin/env python3
"""
Verify Square payments are legitimate customer payments.
Check for: refunds, chargebacks, recurring patterns (loan payments).
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict
from datetime import timedelta

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== SQUARE PAYMENT VERIFICATION ===\n")

# Get all unmatched Square payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, notes
    FROM payments
    WHERE payment_method = 'credit_card'
      AND payment_key IS NOT NULL
      AND charter_id IS NULL
    ORDER BY payment_date, amount DESC
""")
unmatched = cur.fetchall()

print(f"Total unmatched: {len(unmatched)}")
print(f"Total amount: ${sum(float(p['amount']) for p in unmatched):,.2f}\n")

# 1. Check for negative amounts (refunds/chargebacks)
print("=== 1. REFUNDS / CHARGEBACKS CHECK ===")
negative = [p for p in unmatched if float(p['amount']) < 0]
if negative:
    print(f"❌ FOUND {len(negative)} NEGATIVE AMOUNTS:")
    for p in negative:
        print(f"   Payment {p['payment_id']}: ${float(p['amount']):,.2f} on {p['payment_date']}")
    print()
else:
    print("✓ PASS: No negative amounts found\n")

# 2. Check notes for problem keywords
print("=== 2. NOTES KEYWORD CHECK ===")
problem_keywords = ['refund', 'chargeback', 'dispute', 'reversal', 'void', 'cancel', 'denied', 'nsf', 'failed']
flagged = []
for p in unmatched:
    if p['notes']:
        notes_lower = p['notes'].lower()
        for kw in problem_keywords:
            if kw in notes_lower:
                flagged.append((p, kw))
                break

if flagged:
    print(f"❌ FOUND {len(flagged)} WITH PROBLEM KEYWORDS:")
    for p, kw in flagged:
        print(f"   Payment {p['payment_id']}: ${float(p['amount']):,.2f} - '{kw}' in notes")
        print(f"   Notes: {p['notes'][:100]}")
    print()
else:
    print("✓ PASS: No problem keywords in notes\n")

# 3. Check for recurring amounts (Square Capital loan repayments)
print("=== 3. RECURRING PAYMENT CHECK (Square Capital Loans) ===")
amount_frequency = defaultdict(list)
for p in unmatched:
    amt = round(float(p['amount']), 2)
    amount_frequency[amt].append(p)

recurring = [(amt, pays) for amt, pays in amount_frequency.items() if len(pays) >= 3]
if recurring:
    print(f"⚠️  FOUND {len(recurring)} AMOUNTS OCCURRING 3+ TIMES:")
    print("   (Possible Square Capital loan repayments)\n")
    for amt, pays in sorted(recurring, key=lambda x: -len(x[1]))[:10]:
        dates = [p['payment_date'] for p in pays]
        date_range = f"{min(dates)} to {max(dates)}"
        print(f"   ${amt:,.2f}: {len(pays)} occurrences ({date_range})")
        
        # Check if they're evenly spaced (typical of automated loan payments)
        if len(dates) >= 2:
            sorted_dates = sorted(dates)
            gaps = [(sorted_dates[i+1] - sorted_dates[i]).days for i in range(len(sorted_dates)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            if avg_gap > 0 and all(abs(g - avg_gap) <= 3 for g in gaps):
                print(f"      ⚠️  EVENLY SPACED (~{avg_gap:.0f} days) - LIKELY LOAN REPAYMENT")
    
    total_recurring = sum(float(p['amount']) for amt, pays in recurring for p in pays)
    print(f"\n   Total in recurring payments: ${total_recurring:,.2f}")
    print()
else:
    print("✓ PASS: No highly recurring payment amounts\n")

# 4. Check for small amounts (possible fees)
print("=== 4. SMALL AMOUNTS CHECK (Possible Fees) ===")
small = [p for p in unmatched if 0 < float(p['amount']) < 10.00]
if small:
    print(f"ℹ️  {len(small)} payments under $10:")
    for p in sorted(small, key=lambda x: float(x['amount'])):
        print(f"   ${float(p['amount']):,.2f} on {p['payment_date']} (key: {p['payment_key'][:20]}...)")
    print(f"   Total: ${sum(float(p['amount']) for p in small):,.2f}")
    print()
else:
    print("✓ No small amounts\n")

# 5. Compare to Square payouts (bank deposits)
print("=== 5. SQUARE PAYOUTS COMPARISON ===")
cur.execute("""
    SELECT COUNT(*) as count, SUM(amount) as total
    FROM square_payouts
""")
payout_stats = cur.fetchone()
print(f"Square payouts in DB: {payout_stats['count']}")
print(f"Total payout amount: ${float(payout_stats['total'] or 0):,.2f}\n")

# Check if any payment amounts match payout amounts
cur.execute("""
    SELECT p.payment_id, p.amount, p.payment_date,
           sp.id as payout_id, sp.amount as payout_amount, sp.arrival_date
    FROM payments p
    JOIN square_payouts sp ON ABS(p.amount - sp.amount) < 0.01
    WHERE p.payment_method = 'credit_card'
      AND p.payment_key IS NOT NULL
      AND p.charter_id IS NULL
      AND ABS((p.payment_date - sp.arrival_date)) <= 7
""")
payout_matches = cur.fetchall()

if payout_matches:
    print(f"⚠️  {len(payout_matches)} PAYMENTS MATCH PAYOUT AMOUNTS:")
    print("   (These might be bank deposits, not customer payments)\n")
    for pm in payout_matches[:10]:
        print(f"   Payment {pm['payment_id']}: ${float(pm['amount']):,.2f} on {pm['payment_date']}")
        print(f"   Payout {pm['payout_id']}: ${float(pm['payout_amount']):,.2f} on {pm['arrival_date']}")
    print()
else:
    print("✓ PASS: No payments match payout amounts/dates\n")

# FINAL SUMMARY
print("\n" + "="*60)
print("VERIFICATION SUMMARY")
print("="*60)

issues_found = []
if negative:
    issues_found.append(f"{len(negative)} refunds/chargebacks (negative amounts)")
if flagged:
    issues_found.append(f"{len(flagged)} with problem keywords")
if recurring:
    issues_found.append(f"{len(recurring)} recurring amounts (possible loans)")
if payout_matches:
    issues_found.append(f"{len(payout_matches)} matching payout amounts")

if not issues_found:
    print("\n✓✓✓ ALL CHECKS PASSED ✓✓✓")
    print(f"\nAll {len(unmatched)} unmatched Square payments appear to be")
    print("legitimate customer credit card payments.")
    print(f"\nTotal: ${sum(float(p['amount']) for p in unmatched):,.2f}")
    print("\nSafe to proceed with manual charter linking.")
else:
    print("\n⚠️  ISSUES FOUND:")
    for issue in issues_found:
        print(f"  - {issue}")
    
    # Calculate clean payments
    problem_ids = set()
    if negative:
        problem_ids.update(p['payment_id'] for p in negative)
    if flagged:
        problem_ids.update(p[0]['payment_id'] for p in flagged)
    if recurring:
        for amt, pays in recurring:
            problem_ids.update(p['payment_id'] for p in pays)
    if payout_matches:
        problem_ids.update(pm['payment_id'] for pm in payout_matches)
    
    clean = [p for p in unmatched if p['payment_id'] not in problem_ids]
    print(f"\nClean payments (after excluding issues): {len(clean)}")
    print(f"Total clean amount: ${sum(float(p['amount']) for p in clean):,.2f}")
    print(f"\nProblematic payments: {len(problem_ids)}")

cur.close()
conn.close()
