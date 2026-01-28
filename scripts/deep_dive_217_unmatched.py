#!/usr/bin/env python3
"""
Deep analysis: What are the 217 unmatched payments really?

Current state (after Track A linking):
- Started with 283 orphaned Square payments
- Linked 56 via LMS matching
- Now 217 remain

Question: Are these legitimate retainers/deposits or true orphans?
"""

import psycopg2
import pandas as pd
import os
from datetime import datetime, timedelta

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def main():
    print("\n" + "=" * 80)
    print("DEEP DIVE: 217 UNMATCHED SQUARE PAYMENTS")
    print("=" * 80)
    
    conn = connect_db()
    cur = conn.cursor()
    
    # Get all details on unmatched
    cur.execute("""
        SELECT 
            payment_id, amount, payment_date, 
            square_customer_name, square_customer_email,
            square_transaction_id, square_status, notes,
            created_at, last_updated
        FROM payments
        WHERE reserve_number IS NULL
        AND payment_method = 'credit_card'
        ORDER BY payment_date
    """)
    
    payments = cur.fetchall()
    
    print(f"\n✅ Total unmatched: {len(payments)} payments")
    
    # Analyze by date
    print(f"\n1️⃣ CHRONOLOGICAL DISTRIBUTION")
    print("─" * 80)
    
    df = pd.DataFrame(payments, columns=[
        'payment_id', 'amount', 'payment_date', 'square_name', 'square_email',
        'square_txid', 'square_status', 'notes', 'created_at', 'last_updated'
    ])
    
    df['payment_date'] = pd.to_datetime(df['payment_date'])
    df['month'] = df['payment_date'].dt.to_period('M')
    
    monthly = df.groupby('month').agg({
        'payment_id': 'count',
        'amount': ['sum', 'mean', 'min', 'max']
    }).round(2)
    
    print("\nMonth-by-month breakdown:")
    for month, row in monthly.iterrows():
        count = row[('payment_id', 'count')]
        total = row[('amount', 'sum')]
        avg = row[('amount', 'mean')]
        print(f"  {month}: {count:3.0f} payments | ${total:10,.2f} | avg ${avg:7,.2f}")
    
    # Analyze by amount
    print(f"\n2️⃣ AMOUNT DISTRIBUTION")
    print("─" * 80)
    
    print(f"\nAmount statistics:")
    print(f"  Total: ${df['amount'].sum():,.2f}")
    print(f"  Average: ${df['amount'].mean():,.2f}")
    print(f"  Median: ${df['amount'].median():,.2f}")
    print(f"  Min: ${df['amount'].min():,.2f}")
    print(f"  Max: ${df['amount'].max():,.2f}")
    
    # Round amounts analysis
    df['is_round'] = df['amount'].apply(lambda x: (x % 100 == 0) or (x % 50 == 0))
    round_count = df['is_round'].sum()
    print(f"\nRound amounts (retainer indicators): {round_count} ({round_count/len(df)*100:.1f}%)")
    
    # Duplicate amount analysis
    print(f"\n3️⃣ DUPLICATE AMOUNT PATTERNS")
    print("─" * 80)
    
    dup_amts = df['amount'].value_counts()
    dup_amts = dup_amts[dup_amts > 1].head(15)
    
    print(f"\nMost repeated amounts (same amount, different transactions):")
    for amt, count in dup_amts.items():
        sample_payments = df[df['amount'] == amt]['payment_id'].tolist()
        print(f"  ${amt:10.2f}: {count} times | Payments: {sample_payments[:3]}")
    
    # Same date + amount (actual duplicates)
    print(f"\n4️⃣ POTENTIAL TRUE DUPLICATES (same amount + same date)")
    print("─" * 80)
    
    df['date_amt_key'] = df['payment_date'].astype(str) + '_' + df['amount'].astype(str)
    dup_dates = df['date_amt_key'].value_counts()
    dup_dates = dup_dates[dup_dates > 1]
    
    print(f"\nFound {len(dup_dates)} unique date+amount combinations with duplicates:")
    for key, count in dup_dates.head(10).items():
        date_str, amt_str = key.rsplit('_', 1)
        matching = df[df['date_amt_key'] == key]['payment_id'].tolist()
        print(f"  {date_str} at ${float(amt_str):10.2f}: {count} payments {matching}")
    
    # Square email analysis
    print(f"\n5️⃣ SQUARE CUSTOMER EMAIL DATA")
    print("─" * 80)
    
    has_email = df['square_email'].notna().sum()
    print(f"\nPayments with Square customer email: {has_email} ({has_email/len(df)*100:.1f}%)")
    print(f"Payments without Square email: {len(df) - has_email}")
    
    if has_email > 0:
        print(f"\nUnique Square emails:")
        for email, count in df[df['square_email'].notna()]['square_email'].value_counts().head(10).items():
            print(f"  {email[:40]:40s}: {count}")
    
    # Square transaction ID analysis
    print(f"\n6️⃣ SQUARE TRANSACTION ID DATA")
    print("─" * 80)
    
    has_txid = df['square_txid'].notna().sum()
    print(f"\nPayments with Square transaction ID: {has_txid} ({has_txid/len(df)*100:.1f}%)")
    print(f"Payments without transaction ID: {len(df) - has_txid}")
    
    # Check if any txid appears multiple times (refunds, fees, etc.)
    if has_txid > 0:
        txid_counts = df[df['square_txid'].notna()]['square_txid'].value_counts()
        multi_part = txid_counts[txid_counts > 1]
        print(f"\nTransaction IDs with multiple entries: {len(multi_part)}")
        if len(multi_part) > 0:
            print(f"Examples:")
            for txid, count in multi_part.head(5).items():
                matching = df[df['square_txid'] == txid][['payment_id', 'amount', 'square_status']].values
                print(f"  TxID {txid[:20]}: {count} entries")
                for pid, amt, status in matching:
                    print(f"    → Payment {pid}: ${amt:10.2f} ({status})")
    
    # Square status analysis
    print(f"\n7️⃣ SQUARE PAYMENT STATUS")
    print("─" * 80)
    
    statuses = df['square_status'].value_counts()
    print(f"\nPayment statuses:")
    for status, count in statuses.items():
        if pd.isna(status):
            print(f"  NULL: {count}")
        else:
            print(f"  {status}: {count}")
    
    # Notes analysis
    print(f"\n8️⃣ NOTES/COMMENTS PATTERNS")
    print("─" * 80)
    
    print(f"\nPayments with notes: {df['notes'].notna().sum()}")
    
    # Look for specific patterns in notes
    patterns = {
        'AUTO-MATCHED': 0,
        'refund': 0,
        'fee': 0,
        'deposit': 0,
        'retainer': 0,
        'advance': 0,
    }
    
    for idx, row in df.iterrows():
        notes_lower = str(row['notes']).lower() if pd.notna(row['notes']) else ''
        for pattern in patterns.keys():
            if pattern in notes_lower:
                patterns[pattern] += 1
    
    print(f"\nKeyword patterns in notes:")
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  '{pattern}': {count} ({count/len(df)*100:.1f}%)")
    
    # FINAL SUMMARY
    print(f"\n" + "=" * 80)
    print("🎯 SUMMARY: WHAT ARE THESE 217 PAYMENTS?")
    print("=" * 80)
    
    print(f"""
Analysis suggests:

✅ LIKELY LEGITIMATE (keep):
   • {round_count} round-amount payments (retainers/deposits)
   • No duplicate true duplicates requiring deletion
   • Scattered across months (not batch upload error)

❓ QUESTIONABLE:
   • {len(dup_dates)} date+amount duplicate patterns
     (but verify these aren't legitimate recurring charges)
   
   • {len(df) - has_email} payments without Square email
     (harder to verify legitimacy)
   
   • {len(df) - has_txid} payments without transaction ID
     (data quality issue in Square import)

🤔 THE CORE QUESTION:
   These 217 unmatched payments fall into TWO categories:
   
   1. LEGITIMATE ORPHANS: Customer payments toward future charters
      (retainers, deposits, advance payments with no existing booking)
      
   2. MISSING CHARTER RECORDS: Payments for real charters that exist
      in LMS but were never imported into current database
      
   Decision needed: Which are which?
      """)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
