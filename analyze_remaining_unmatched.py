#!/usr/bin/env python3
"""
Analyze remaining unmatched banking transactions - categorize by type
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("\n" + "=" * 120)
    print("REMAINING UNMATCHED E-TRANSFERS - CATEGORIZATION")
    print("=" * 120)
    
    # Get all unmatched
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        ORDER BY ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) DESC
    """)
    
    all_trans = cur.fetchall()
    print(f"\nTotal unmatched: {len(all_trans)}")
    
    # Analyze by description patterns
    vendors_insurance = []
    large_payments = []
    medium_payments = []
    small_payments = []
    heffner_type = []
    chargebacks = []
    
    for trans_id, date, credit, debit, desc in all_trans:
        amount = (credit if credit else 0) + (debit if debit else 0)
        amount = abs(amount)
        
        desc_upper = desc.upper() if desc else ""
        
        # Categorize
        if any(x in desc_upper for x in ['HEFFNER', 'CENTRATECH', 'GLOBAL', 'INSURANCE', 'INSURANCE']):
            vendors_insurance.append((trans_id, date, amount, desc))
        elif any(x in desc_upper for x in ['CHARGEBACK', 'REVERSAL', 'REFUND', 'CLAIM']):
            chargebacks.append((trans_id, date, amount, desc))
        elif amount >= 10000:
            large_payments.append((trans_id, date, amount, desc))
        elif amount >= 1000:
            medium_payments.append((trans_id, date, amount, desc))
        else:
            small_payments.append((trans_id, date, amount, desc))
    
    print(f"\n📊 CATEGORIZATION SUMMARY:")
    print("-" * 120)
    print(f"Vendor/Insurance type      : {len(vendors_insurance):5d} trans | ${sum(x[2] for x in vendors_insurance):>12,.2f}")
    print(f"Chargebacks/Reversals      : {len(chargebacks):5d} trans | ${sum(x[2] for x in chargebacks):>12,.2f}")
    print(f"Large payments (≥$10K)     : {len(large_payments):5d} trans | ${sum(x[2] for x in large_payments):>12,.2f}")
    print(f"Medium payments ($1K-$10K) : {len(medium_payments):5d} trans | ${sum(x[2] for x in medium_payments):>12,.2f}")
    print(f"Small payments (<$1K)      : {len(small_payments):5d} trans | ${sum(x[2] for x in small_payments):>12,.2f}")
    print("-" * 120)
    print(f"TOTAL                      : {len(all_trans):5d} trans | ${sum(x[2] for x in vendors_insurance + chargebacks + large_payments + medium_payments + small_payments):>12,.2f}")
    
    # Sample from each category
    print(f"\n📋 SAMPLES:")
    print("-" * 120)
    
    if vendors_insurance:
        print(f"\n🏢 VENDOR/INSURANCE (first 5):")
        for trans_id, date, amt, desc in vendors_insurance[:5]:
            print(f"   {trans_id:8d} | {date} | ${amt:10,.2f} | {desc[:60]}")
    
    if chargebacks:
        print(f"\n💳 CHARGEBACKS/REVERSALS (first 5):")
        for trans_id, date, amt, desc in chargebacks[:5]:
            print(f"   {trans_id:8d} | {date} | ${amt:10,.2f} | {desc[:60]}")
    
    if large_payments:
        print(f"\n💰 LARGE PAYMENTS (first 5):")
        for trans_id, date, amt, desc in large_payments[:5]:
            print(f"   {trans_id:8d} | {date} | ${amt:10,.2f} | {desc[:60]}")
    
    if medium_payments:
        print(f"\n📊 MEDIUM PAYMENTS (first 5):")
        for trans_id, date, amt, desc in medium_payments[:5]:
            print(f"   {trans_id:8d} | {date} | ${amt:10,.2f} | {desc[:60]}")
    
    print("\n" + "=" * 120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
