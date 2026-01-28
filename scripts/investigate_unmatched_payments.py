#!/usr/bin/env python3
"""
TRACK B: Investigate 205 unmatched orphaned payments

These 205 payments do NOT exist in LMS. Determine if they are:
1. Legitimate RETAINERS / ADVANCE DEPOSITS (OK to keep orphaned)
2. Data quality issues / duplicates (need cleanup)
3. Missing from LMS sync (need investigation)

Analysis will look for patterns:
- Round amounts (retainer indicators)
- Same customer payments
- Clustered dates (import batch issues)
- Duplicate amounts (potential duplicates)
"""

import os
import psycopg2
import pandas as pd
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def investigate_unmatched_payments():
    """Analyze the 205 unmatched payments for patterns"""
    
    # Read LMS export
    lms_df = pd.read_csv("reports/lms_payment_reserve_export.csv")
    lms_df['lms_datetime'] = pd.to_datetime(lms_df['date'])
    
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
    
    # Find unmatched (not in LMS)
    unmatched_ids = []
    for _, orphan in orphan_df.iterrows():
        orphan_ts = pd.Timestamp(orphan['payment_date'])
        lms_match = lms_df[
            (lms_df['amount'] == orphan['amount']) &
            ((lms_df['lms_datetime'] - orphan_ts).dt.days.abs() <= 3)
        ]
        if len(lms_match) == 0:
            unmatched_ids.append(orphan['payment_id'])
    
    unmatched_df = orphan_df[orphan_df['payment_id'].isin(unmatched_ids)].copy()
    
    print("\n" + "=" * 80)
    print("TRACK B: INVESTIGATING 205 UNMATCHED PAYMENTS")
    print("=" * 80)
    print(f"\nTotal unmatched payments: {len(unmatched_df)}\n")
    
    # Analysis 1: Round amounts (retainer indicators)
    print("1️⃣  AMOUNT ANALYSIS (Looking for retainer patterns):\n")
    
    round_amounts = unmatched_df[unmatched_df['amount'] % 100 == 0]
    print(f"   Round hundreds ($X00.00):      {len(round_amounts):3} ({100*len(round_amounts)/len(unmatched_df):5.1f}%)")
    
    round_5_amounts = unmatched_df[unmatched_df['amount'] % 50 == 0]
    print(f"   Round fifties/hundreds:        {len(round_5_amounts):3} ({100*len(round_5_amounts)/len(unmatched_df):5.1f}%)")
    
    # Distribution of amounts
    print(f"\n   Top 10 most common amounts:\n")
    amount_counts = unmatched_df['amount'].value_counts().head(10)
    for amt, count in amount_counts.items():
        print(f"      ${amt:>8,.2f}  ×{count} payments")
    
    # Analysis 2: Date clustering
    print(f"\n2️⃣  DATE DISTRIBUTION:\n")
    
    date_counts = unmatched_df['payment_date'].value_counts().sort_index()
    busiest_dates = date_counts.nlargest(10)
    print(f"   Top 10 busiest dates:\n")
    for date, count in busiest_dates.items():
        print(f"      {date}  {count:>3} payments")
    
    # Analysis 3: Duplicate amount detection
    print(f"\n3️⃣  POTENTIAL DUPLICATES (same amount, same date):\n")
    
    dup_check = unmatched_df.groupby(['amount', 'payment_date']).size().reset_index(name='count')
    potential_dups = dup_check[dup_check['count'] > 1].sort_values('count', ascending=False)
    
    if len(potential_dups) > 0:
        print(f"   Found {len(potential_dups)} potential duplicate pairs:\n")
        for _, row in potential_dups.head(10).iterrows():
            print(f"      ${row['amount']:>8,.2f} on {row['payment_date']}  ×{int(row['count'])} payments")
    else:
        print(f"   No obvious duplicates found\n")
    
    # Analysis 4: 'AUTO-MATCHED' note patterns
    print(f"\n4️⃣  AUTO-MATCHED NOTES ANALYSIS:\n")
    
    auto_matched = unmatched_df[unmatched_df['notes'].str.contains('AUTO-MATCHED', case=False, na=False)]
    print(f"   With 'AUTO-MATCHED' in notes:  {len(auto_matched):3} ({100*len(auto_matched)/len(unmatched_df):5.1f}%)")
    
    if len(auto_matched) > 0:
        print(f"\n   Sample AUTO-MATCHED notes:\n")
        for _, row in auto_matched.head(5).iterrows():
            note_snippet = row['notes'][:80] if len(row['notes']) > 80 else row['notes']
            print(f"      {row['payment_id']}: {note_snippet}...")
    
    # Analysis 5: Recommendation
    print(f"\n5️⃣  PRELIMINARY ASSESSMENT:\n")
    
    round_pct = 100 * len(round_5_amounts) / len(unmatched_df)
    
    if round_pct > 60:
        print(f"   🔵 LIKELY RETAINERS/DEPOSITS:")
        print(f"      {round_pct:.0f}% are round amounts → suggests advance deposits")
        print(f"      Recommendation: Leave as-is, track separately as 'unlinked deposits'")
    elif len(potential_dups) > 5:
        print(f"   🔴 LIKELY DUPLICATES:")
        print(f"      {len(potential_dups)} duplicate patterns found")
        print(f"      Recommendation: Manual review + deletion of true duplicates")
    else:
        print(f"   🟡 MIXED/UNCLEAR:")
        print(f"      Pattern suggests mix of retainers + other")
        print(f"      Recommendation: Finance review + categorization")
    
    # Write detailed CSV for manual review
    output_file = "reports/UNMATCHED_ORPHANED_PAYMENTS_DETAILED.csv"
    unmatched_sorted = unmatched_df.sort_values(['payment_date', 'amount'])
    unmatched_sorted.to_csv(output_file, index=False)
    print(f"\n📄 Detailed CSV for manual review: {output_file}\n")
    
    cur.close()
    conn.close()
    
    return unmatched_df


if __name__ == "__main__":
    unmatched = investigate_unmatched_payments()
    
    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print(f"""
1. Review the analysis above
2. Check: reports/UNMATCHED_ORPHANED_PAYMENTS_DETAILED.csv
3. Get Finance approval for categorization:
   - Are these legitimate retainers?
   - Are any true duplicates?
   - Which require further investigation?
4. Based on approval:
   - RETAINERS: Leave orphaned, mark with notation
   - DUPLICATES: Delete after verification
   - MISSING CHARTERS: Create or import from LMS
    """)
    print("=" * 80 + "\n")
