#!/usr/bin/env python3
"""
Quick test: Can we improve matching by relaxing date window?
Test with ±7 days instead of ±3 days
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("TEST: Amount-Date Matching with Different Tolerances")
print("=" * 80)

# Test 1: Exact amount, ±0 days (must be same day)
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount = c.total_amount_due
  AND DATE(p.payment_date) = DATE(c.charter_date)
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
exact_same_day = cur.fetchone()[0]

# Test 2: Exact amount, ±1 day
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount = c.total_amount_due
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 1 AND DATE(c.charter_date) + 1
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
exact_1day = cur.fetchone()[0]

# Test 3: Exact amount, ±3 days (current)
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount = c.total_amount_due
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 3 AND DATE(c.charter_date) + 3
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
exact_3day = cur.fetchone()[0]

# Test 4: Exact amount, ±7 days
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount = c.total_amount_due
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 7 AND DATE(c.charter_date) + 7
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
exact_7day = cur.fetchone()[0]

# Test 5: Exact amount, ±14 days
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount = c.total_amount_due
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 14 AND DATE(c.charter_date) + 14
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
exact_14day = cur.fetchone()[0]

# Test 6: Relax amount: ±$25
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount BETWEEN c.total_amount_due - 25 AND c.total_amount_due + 25
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 3 AND DATE(c.charter_date) + 3
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
relax_25_3day = cur.fetchone()[0]

# Test 7: Relax amount: ±$50
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount BETWEEN c.total_amount_due - 50 AND c.total_amount_due + 50
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 3 AND DATE(c.charter_date) + 3
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
relax_50_3day = cur.fetchone()[0]

# Test 8: Both relaxed: ±7 days AND ±$25
cur.execute("""
SELECT COUNT(*) FROM payments p
LEFT JOIN charters c ON 
  p.amount BETWEEN c.total_amount_due - 25 AND c.total_amount_due + 25
  AND DATE(p.payment_date) BETWEEN DATE(c.charter_date) - 7 AND DATE(c.charter_date) + 7
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND c.charter_id IS NOT NULL;
""")
relax_both = cur.fetchone()[0]

print("\n📊 MATCHING WINDOW TESTS (out of 273 orphaned Square payments):\n")
print("Date Matching (Exact Amount):")
print(f"  ±0 days (same day only):      {exact_same_day:3} ({100*exact_same_day/273:5.1f}%)")
print(f"  ±1 day:                       {exact_1day:3} ({100*exact_1day/273:5.1f}%)")
print(f"  ±3 days (CURRENT):            {exact_3day:3} ({100*exact_3day/273:5.1f}%)")
print(f"  ±7 days:                      {exact_7day:3} ({100*exact_7day/273:5.1f}%)")
print(f"  ±14 days:                     {exact_14day:3} ({100*exact_14day/273:5.1f}%)")

print(f"\nAmount Matching (±3 days date window):")
print(f"  Exact amount:                 {exact_3day:3} ({100*exact_3day/273:5.1f}%)")
print(f"  Within ±$25:                  {relax_25_3day:3} ({100*relax_25_3day/273:5.1f}%)")
print(f"  Within ±$50:                  {relax_50_3day:3} ({100*relax_50_3day/273:5.1f}%)")

print(f"\nCombined Relaxation:")
print(f"  ±7 days AND ±$25:             {relax_both:3} ({100*relax_both/273:5.1f}%)")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)

if exact_7day > exact_3day * 1.5:
    print(f"✅ Expanding to ±7 days would help (+{exact_7day - exact_3day} more matches)")
else:
    print(f"❌ Expanding to ±7 days doesn't help much (+{exact_7day - exact_3day} more matches)")

if relax_both > exact_3day * 1.5:
    print(f"✅ Relaxing both date AND amount would help (+{relax_both - exact_3day} more matches)")
else:
    print(f"❌ Even relaxed matching helps little (+{relax_both - exact_3day} more matches)")

if exact_7day > 200:
    print(f"\n🟢 Strong case for matching: {exact_7day}/273 = {100*exact_7day/273:.1f}% would match with ±7 day window")
elif exact_7day > 150:
    print(f"\n🟡 Moderate case: {exact_7day}/273 = {100*exact_7day/273:.1f}% would match (still need investigation)")
else:
    print(f"\n🔴 WEAK matching: Only {exact_7day}/273 = {100*exact_7day/273:.1f}% would match")
    print(f"   → Strong evidence that {273 - exact_7day} payments are RETAINERS or MISSING CHARTERS")
    print(f"   → RECOMMEND: Full LMS investigation before any linking")

print("=" * 80 + "\n")

cur.close()
conn.close()
