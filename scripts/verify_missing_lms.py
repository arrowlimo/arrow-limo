#!/usr/bin/env python3
"""
Verify 24 ALMS charters against LMS payment data - SIMPLER APPROACH
Check if LMS has payment records for charters that show paid_amount but have no charter_payments
"""

import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# 24 charters with missing payments
MISSING_PAYMENT_CHARTERS = [
    '019551', '019718', '007346', '006856', '019495', '019216', '019418', '008454',
    '007362', '019268', '008005', '019298', '019423', '007980', '019618', '019657',
    '007358', '019228', '019358', '008427', '019212', '008301', '006190', '007801',
]

try:
    conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
    cur = conn.cursor()
    
    print("="*120)
    print("VERIFY 24 CHARTERS WITH MISSING PAYMENTS AGAINST LMS DATA")
    print("="*120)
    
    placeholders = ','.join([f"'{r}'" for r in MISSING_PAYMENT_CHARTERS])
    
    # Get ALMS charter data (simpler query without join)
    print("\nALMS CHARTERS WITH PAID_AMOUNT")
    print("-"*120)
    
    query = f"""
    SELECT 
        reserve_number,
        charter_date::date,
        total_amount_due,
        paid_amount,
        (total_amount_due - COALESCE(paid_amount, 0)) as balance
    FROM charters
    WHERE reserve_number IN ({placeholders})
    ORDER BY paid_amount DESC
    """
    
    cur.execute(query)
    alms_data = cur.fetchall()
    
    alms_dict = {}
    total_alms_paid = Decimal('0.00')
    
    for row in alms_data:
        reserve_no, charter_date, total_due, paid_amount, balance = row
        paid_amount = paid_amount or Decimal('0.00')
        total_alms_paid += paid_amount
        alms_dict[reserve_no] = (paid_amount, total_due, charter_date)
        print(f"{reserve_no:10} | Date: {str(charter_date):12} | Total: ${total_due:12.2f} | Paid: ${paid_amount:12.2f} | Balance: ${balance:12.2f}")
    
    print(f"\nTotal ALMS paid_amount (24 charters):        ${total_alms_paid:12.2f}")
    
    # Check LMS for these reserves
    print("\n" + "="*120)
    print("LMS PAYMENT DATA FOR SAME RESERVES")
    print("-"*120)
    
    query = f"""
    SELECT 
        reserve_no,
        COUNT(*) as payment_count,
        SUM(amount) as total_lms_payments,
        MIN(payment_date)::date as first_payment,
        MAX(payment_date)::date as last_payment,
        STRING_AGG(DISTINCT payment_method, ', ') as payment_methods
    FROM lms2026_payments
    WHERE reserve_no IN ({placeholders})
    GROUP BY reserve_no
    ORDER BY total_lms_payments DESC
    """
    
    cur.execute(query)
    lms_data = cur.fetchall()
    
    total_lms = Decimal('0.00')
    lms_dict = {}
    for row in lms_data:
        reserve_no, count, total_lms_payments, first_payment, last_payment, methods = row
        total_lms_payments = total_lms_payments or Decimal('0.00')
        total_lms += total_lms_payments
        lms_dict[reserve_no] = total_lms_payments
        print(f"{reserve_no:10} | Payments: {count:3} | Total: ${total_lms_payments:12.2f} | First: {str(first_payment):12} | Last: {str(last_payment):12} | Methods: {methods}")
    
    print(f"\nTotal LMS payments (24 charters):            ${total_lms:12.2f}")
    
    # Compare
    print("\n" + "="*120)
    print("COMPARISON: ALMS PAID_AMOUNT vs LMS PAYMENTS")
    print("-"*120)
    
    match_count = 0
    mismatch_count = 0
    no_lms_count = 0
    
    for reserve_no, (paid_amount, total_due, charter_date) in alms_dict.items():
        lms_total = lms_dict.get(reserve_no, Decimal('0.00'))
        discrepancy = abs(paid_amount - lms_total)
        
        if lms_total == 0:
            status = "❌ NO LMS DATA"
            no_lms_count += 1
        elif discrepancy < Decimal('0.01'):
            status = "✅ MATCH"
            match_count += 1
        else:
            status = f"⚠️  DIFF: ${discrepancy:8.2f}"
            mismatch_count += 1
        
        print(f"{reserve_no:10} | ALMS: ${paid_amount:12.2f} | LMS: ${lms_total:12.2f} | {status}")
    
    # Summary
    print("\n" + "="*120)
    print("SUMMARY")
    print("="*120)
    print(f"Total ALMS paid_amount (24 charters):        ${total_alms_paid:12.2f}")
    print(f"Total LMS payments (found in LMS):           ${total_lms:12.2f}")
    print(f"Unaccounted for (missing in charter_payments): ${(total_alms_paid - total_lms):12.2f}")
    print(f"\nBreakdown:")
    print(f"  Charters matching LMS to ALMS:              {match_count}")
    print(f"  Charters with discrepancies:                {mismatch_count}")
    print(f"  Charters with NO LMS payment data:          {no_lms_count}")
    
    if no_lms_count > 0:
        print(f"\n⚠️  {no_lms_count} charters have ALMS paid_amount but NO payment data in LMS")
        print("   These may be: cash payments, check payments, or internal adjustments")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
