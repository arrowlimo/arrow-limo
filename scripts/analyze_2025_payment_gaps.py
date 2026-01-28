#!/usr/bin/env python3
"""Check 2025 payment status - what's missing reserve_number and why"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "="*80)
print("2025 PAYMENT STATUS ANALYSIS")
print("="*80)

# Overall 2025 breakdown
cur.execute("""
    SELECT 
        payment_method,
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) as no_banking,
        COUNT(CASE WHEN payment_key LIKE 'ETR:%' THEN 1 END) as etr_payments,
        SUM(amount) as total_amount
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2025
    GROUP BY payment_method
    ORDER BY total DESC
""")

print("\n📊 2025 Payments by Method:")
print(f"{'Method':<20} {'Total':<8} {'No Reserve':<12} {'No Banking':<12} {'ETR Keys':<10} {'Amount':<15}")
print("-"*90)

total_2025 = 0
total_no_reserve = 0
total_no_banking = 0
total_etr = 0

for method, total, no_res, no_bank, etr, amt in cur.fetchall():
    total_2025 += total
    total_no_reserve += no_res
    total_no_banking += no_bank
    total_etr += etr
    
    method_name = method or 'NULL'
    print(f"{method_name:<20} {total:<8,} {no_res:<12,} {no_bank:<12,} {etr:<10,} ${amt:>13,.2f}")

print("-"*90)
print(f"{'TOTAL':<20} {total_2025:<8,} {total_no_reserve:<12,} {total_no_banking:<12,} {total_etr:<10,}")

print(f"\n📈 2025 Summary:")
print(f"   Missing reserve_number: {total_no_reserve:,} ({total_no_reserve/total_2025*100:.1f}%)")
print(f"   Missing banking_transaction_id: {total_no_banking:,} ({total_no_banking/total_2025*100:.1f}%)")
print(f"   ETR payments (from emails): {total_etr:,}")

# Check Square payments
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN square_transaction_id IS NOT NULL THEN 1 END) as has_square_id,
        SUM(amount) as total_amount
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2025
    AND (payment_method ILIKE '%square%' OR square_transaction_id IS NOT NULL)
""")

sq_total, sq_no_res, sq_has_id, sq_amt = cur.fetchone()
if sq_total:
    print(f"\n💳 Square Payments (2025):")
    print(f"   Total: {sq_total:,} (${sq_amt:,.2f})")
    print(f"   Missing reserve: {sq_no_res:,} ({sq_no_res/sq_total*100:.1f}%)")
    print(f"   With square_transaction_id: {sq_has_id:,}")

# Check email-based payments (ETR:)
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        MIN(payment_date) as earliest,
        MAX(payment_date) as latest,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
    AND EXTRACT(YEAR FROM payment_date) = 2025
""")

etr_total, etr_no_res, etr_earliest, etr_latest, etr_amt = cur.fetchone()
if etr_total:
    print(f"\n📧 Email E-Transfer Payments (ETR:) in 2025:")
    print(f"   Total: {etr_total:,} (${etr_amt:,.2f})")
    print(f"   Missing reserve: {etr_no_res:,} ({etr_no_res/etr_total*100:.1f}% if etr_total else 0)")
    print(f"   Date range: {etr_earliest} to {etr_latest}")

# What needs to be imported
print(f"\n" + "="*80)
print("WHAT NEEDS TO BE UPDATED FOR 2025")
print("="*80)

print(f"\n📥 Import Tasks:")
print(f"   1. Square payments for 2025: Need to reconcile Square payouts → banking")
print(f"   2. Email E-Transfers for 2025: Scan Outlook PST for 2025 Interac emails")
print(f"   3. After import: Sync from LMS to get reserve_number linkage")

# Check latest LMS backup date
print(f"\n💾 LMS Backup Status:")
print(f"   Latest LMS: L:\\New folder\\lms.mdb")

import os
lms_path = r'L:\New folder\lms.mdb'
if os.path.exists(lms_path):
    mtime = os.path.getmtime(lms_path)
    from datetime import datetime
    lms_date = datetime.fromtimestamp(mtime)
    print(f"   Last modified: {lms_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    days_old = (datetime.now() - lms_date).days
    if days_old > 30:
        print(f"   ⚠️  LMS is {days_old} days old - may not have 2025 data")
    else:
        print(f"   ✅ LMS is {days_old} days old - likely has 2025 data")

cur.close()
conn.close()

print(f"\n" + "="*80)
print("NEXT STEPS")
print("="*80)
print(f"""
1. Import 2025 Square payments:
   - Run: python scripts/reconcile_square_payouts_complete.py
   - Or: Import Square CSV exports for 2025

2. Import 2025 E-Transfer emails:
   - Run: python scripts/analyze_etransfer_reserve_numbers.py
   - Scans Outlook PST for Interac emails
   - Extracts reserve numbers from email bodies

3. Sync from LMS to link payments to charters:
   - After importing Square & E-Transfers
   - LMS will have reserve_number linkage
   - Run: python scripts/match_lms_payments_by_reserve.py

4. Banking matching:
   - After reserve_number populated
   - Run: python scripts/restore_reserve_number_matching.py --write
""")

print("="*80)
