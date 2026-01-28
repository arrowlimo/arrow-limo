#!/usr/bin/env python3
"""
Compare Orphaned Square Payments to LMS Payment Data

Check: Of the 273 orphaned (NULL reserve_number) Square payments,
how many exist in the LMS payment export?

This will tell us:
1. If charters exist in LMS → We need to import/sync them
2. If not in LMS → Payments are truly orphaned (retainers, duplicates, errors)
"""

import pandas as pd
import os
from datetime import datetime

# Read LMS payment export (24,589 records)
lms_file = "reports/lms_payment_reserve_export.csv"
print(f"📂 Reading LMS data: {lms_file}")
lms_df = pd.read_csv(lms_file)
print(f"   {len(lms_df):,} LMS payments loaded\n")

# Read orphaned payments from database
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

# Get orphaned payments
cur.execute("""
SELECT p.payment_id, p.amount, DATE(p.payment_date) as payment_date, p.notes
FROM payments p
WHERE p.reserve_number IS NULL
  AND p.payment_date >= '2025-09-10'
  AND p.payment_method = 'credit_card'
ORDER BY p.payment_date, p.amount;
""")

orphans = cur.fetchall()
orphan_df = pd.DataFrame(orphans, columns=['payment_id', 'amount', 'payment_date', 'notes'])
print(f"📊 Orphaned Square payments: {len(orphan_df):,}\n")

# Convert dates to datetime for comparison
lms_df['lms_datetime'] = pd.to_datetime(lms_df['date'])
orphan_df['payment_datetime'] = pd.to_datetime(orphan_df['payment_date'])

# Strategy: Try to match orphaned payments to LMS payments
# Match on: amount + date (within ±3 days)

print("=" * 80)
print("COMPARISON: Orphaned Payments vs. LMS Payment Export")
print("=" * 80)
print(f"\n1️⃣  EXACT AMOUNT MATCH (same dollar amount):\n")

# Count exact amount matches in LMS
amount_matches = []
for _, orphan in orphan_df.iterrows():
    lms_match = lms_df[lms_df['amount'] == orphan['amount']]
    if len(lms_match) > 0:
        amount_matches.append({
            'payment_id': orphan['payment_id'],
            'amount': orphan['amount'],
            'payment_date': orphan['payment_date'],
            'lms_count': len(lms_match),
            'lms_reserves': lms_match['reserve'].unique().tolist()
        })

print(f"   Orphaned payments with EXACT amount in LMS: {len(amount_matches)} / {len(orphan_df)}")
print(f"   ({100*len(amount_matches)/len(orphan_df):.1f}%)\n")

# Breakdown: single match vs multiple
single_match = sum(1 for m in amount_matches if m['lms_count'] == 1)
multi_match = sum(1 for m in amount_matches if m['lms_count'] > 1)
print(f"   - Single LMS match: {single_match}")
print(f"   - Multiple LMS matches (ambiguous): {multi_match}\n")

# 2. Amount + Date matching (±3 days)
print(f"2️⃣  AMOUNT + DATE MATCH (amount + date ±3 days):\n")

amount_date_matches = []
for _, orphan in orphan_df.iterrows():
    # Find LMS records with same amount AND date within ±3 days
    lms_match = lms_df[
        (lms_df['amount'] == orphan['amount']) &
        (abs((lms_df['lms_datetime'] - orphan['payment_datetime']).dt.days) <= 3)
    ]
    if len(lms_match) > 0:
        amount_date_matches.append({
            'payment_id': orphan['payment_id'],
            'amount': orphan['amount'],
            'payment_date': orphan['payment_date'],
            'lms_count': len(lms_match),
            'lms_reserves': lms_match['reserve'].unique().tolist(),
            'lms_dates': lms_match['lms_datetime'].unique().tolist()
        })

print(f"   Orphaned payments with amount + date match in LMS: {len(amount_date_matches)} / {len(orphan_df)}")
print(f"   ({100*len(amount_date_matches)/len(orphan_df):.1f}%)\n")

single_ad = sum(1 for m in amount_date_matches if m['lms_count'] == 1)
multi_ad = sum(1 for m in amount_date_matches if m['lms_count'] > 1)
print(f"   - Single LMS match (confident): {single_ad}")
print(f"   - Multiple LMS matches (ambiguous): {multi_ad}\n")

# 3. Show sample matches
if len(amount_date_matches) > 0:
    print(f"3️⃣  SAMPLE MATCHES (first 10):\n")
    print(f"{'PaymentID':<10} {'Amount':<12} {'Payment Date':<12} {'LMS Reserve':<15} {'LMS Date':<12}")
    print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*15} {'-'*12}")
    for m in amount_date_matches[:10]:
        reserves_str = ", ".join(str(r) for r in m['lms_reserves'])
        dates_str = ", ".join([str(d.date() if hasattr(d, 'date') else d) for d in m['lms_dates']])
        print(f"{m['payment_id']:<10} ${m['amount']:<11,.2f} {str(m['payment_date']):<12} {reserves_str:<15} {dates_str:<12}")

# 4. Show unmatched
unmatched = [o for o in orphan_df.to_dict('records') if o['payment_id'] not in [m['payment_id'] for m in amount_date_matches]]
print(f"\n4️⃣  UNMATCHED IN LMS (amount + date ±3 days):\n")
print(f"   {len(unmatched)} / {len(orphan_df)} payments have NO match in LMS")
print(f"   ({100*len(unmatched)/len(orphan_df):.1f}%)\n")

if len(unmatched) > 0 and len(unmatched) <= 20:
    print(f"   These are the unmatched payments (likely retainers or errors):")
    for u in unmatched:
        print(f"     - Payment {u['payment_id']}: ${u['amount']:<8,.2f} on {u['payment_date']}")
elif len(unmatched) > 20:
    print(f"   Sample of unmatched (showing first 10):")
    for u in unmatched[:10]:
        print(f"     - Payment {u['payment_id']}: ${u['amount']:<8,.2f} on {u['payment_date']}")

# 5. Recommendations
print(f"\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)

if len(amount_date_matches) > len(orphan_df) * 0.8:
    print(f"""
✅ STRONG MATCH: {len(amount_date_matches)} / {len(orphan_df)} orphaned payments found in LMS

Action:
1. These payments ARE in the LMS system with reserve numbers
2. Charters likely exist in LMS but weren't imported to almsdata
3. Next step: Import missing charters from LMS
4. Then link these {len(amount_date_matches)} payments to their reserves

Timeline: 1-2 hours to import LMS charters + link payments
    """)
elif len(amount_date_matches) > len(orphan_df) * 0.5:
    print(f"""
🟡 PARTIAL MATCH: {len(amount_date_matches)} / {len(orphan_df)} orphaned payments found in LMS

Action:
1. {len(amount_date_matches)} payments ARE in LMS → import charters + link
2. {len(unmatched)} payments NOT in LMS → investigate (retainers? errors?)
3. Two-track approach:
   - Track A: Link the {len(amount_date_matches)} LMS-matched payments
   - Track B: Manually review {len(unmatched)} unmatched for next steps

Timeline: 2-3 hours
    """)
else:
    print(f"""
🔴 WEAK MATCH: Only {len(amount_date_matches)} / {len(orphan_df)} orphaned payments found in LMS

Action:
1. Most ({len(unmatched)}) orphaned payments are NOT in LMS at all
2. This suggests:
   - They are RETAINERS / ADVANCE DEPOSITS (not tied to specific charters)
   - OR they are data quality issues / duplicates
   - OR they are missing from LMS entirely

Recommended investigation:
   - Check Square dashboard for {len(unmatched)} unmatched payments
   - Look for patterns: Are they all same customer? Same amount? Same date?
   - Ask Finance: \"Are these retainers we're collecting upfront?\"
   - Determine if they belong to specific customers/reservations

Timeline: 3-4 hours of manual review
    """)

print("=" * 80 + "\n")

cur.close()
conn.close()

# Write detailed report
report_file = "reports/COMPARE_ORPHANED_TO_LMS.md"
with open(report_file, "w") as f:
    f.write(f"# Orphaned Payments vs. LMS Comparison\n\n")
    f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
    f.write(f"## Summary\n\n")
    f.write(f"- Orphaned Square payments: {len(orphan_df)}\n")
    f.write(f"- Amount + date match in LMS: {len(amount_date_matches)} ({100*len(amount_date_matches)/len(orphan_df):.1f}%)\n")
    f.write(f"- No match in LMS: {len(unmatched)} ({100*len(unmatched)/len(orphan_df):.1f}%)\n\n")
    
    f.write(f"## Matched to LMS\n\n")
    if len(amount_date_matches) > 0:
        f.write(f"| PaymentID | Amount | Date | Reserves |\n")
        f.write(f"|---|---|---|---|\n")
        for m in amount_date_matches:
            reserves = ", ".join(m['lms_reserves'])
            f.write(f"| {m['payment_id']} | ${m['amount']:.2f} | {m['payment_date']} | {reserves} |\n")
    else:
        f.write("None\n")

print(f"📄 Report saved: {report_file}\n")
