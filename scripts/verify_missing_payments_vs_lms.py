#!/usr/bin/env python3
"""
Verify 24 ALMS charters against LMS payment data
Check if LMS has payment records for charters that show paid_amount but have $0.00 in charter_payments
"""

import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# 24 charters with missing payments (paid_amount > 0 but SUM(charter_payments) = $0.00)
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
    
    # Get ALMS charter data
    print("\n" + "="*120)
    print("ALMS CHARTERS WITH PAID_AMOUNT BUT NO PAYMENT TRANSACTIONS")
    print("="*120)
    
    query = f"""
    SELECT 
        c.reserve_number,
        c.charter_date::date as charter_date,
        c.total_amount_due,
        c.paid_amount,
        (c.total_amount_due - COALESCE(c.paid_amount, 0)) as balance,
        COALESCE(SUM(cp.amount), 0) as sum_charter_payments
    FROM charters c
    LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
    WHERE c.reserve_number IN ({placeholders})
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount
    ORDER BY c.paid_amount DESC
    """
    
    cur.execute(query)
    alms_data = cur.fetchall()
    
    total_missing = Decimal('0.00')
    for row in alms_data:
        reserve_no, charter_date, total_due, paid_amount, balance, sum_payments = row
        missing = (paid_amount or Decimal('0.00')) - (sum_payments or Decimal('0.00'))
        total_missing += missing
        print(f"{reserve_no:10} | {str(charter_date):12} | Total: ${total_due:12.2f} | Paid: ${paid_amount:12.2f} | Payments in DB: ${sum_payments:12.2f} | Missing: ${missing:12.2f}")
    
    print(f"\n{'TOTAL MISSING PAYMENTS':>60} ${total_missing:12.2f}")
    
    # Check LMS for these reserves
    print("\n" + "="*120)
    print("LMS PAYMENT DATA FOR SAME RESERVES")
    print("="*120)
    
    query = f"""
    SELECT 
        reserve_no,
        COUNT(*) as payment_count,
        SUM(amount) as total_lms_payments,
        MIN(payment_date) as first_payment,
        MAX(payment_date) as last_payment,
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
    
    print(f"\n{'TOTAL LMS PAYMENTS FOR 24 CHARTERS':>60} ${total_lms:12.2f}")
    
    # Compare
    print("\n" + "="*120)
    print("COMPARISON: ALMS PAID_AMOUNT VS LMS PAYMENTS")
    print("="*120)
    
    for row in alms_data:
        reserve_no, charter_date, total_due, paid_amount, balance, sum_payments = row
        lms_total = lms_dict.get(reserve_no, Decimal('0.00'))
        paid_amount = paid_amount or Decimal('0.00')
        discrepancy = paid_amount - lms_total
        
        status = "✅ MATCH" if abs(discrepancy) < Decimal('0.01') else f"❌ DIFF: ${discrepancy:12.2f}"
        print(f"{reserve_no:10} | ALMS: ${paid_amount:12.2f} | LMS: ${lms_total:12.2f} | {status}")
    
    # Check if LMS has payment data but ALMS doesn't
    print("\n" + "="*120)
    print("CHARTERS IN LMS BUT WITH $0.00 IN ALMS charter_payments")
    print("="*120)
    
    for reserve_no in MISSING_PAYMENT_CHARTERS:
        if reserve_no not in lms_dict:
            print(f"{reserve_no:10} | LMS: $0.00 (not found)")
        elif lms_dict[reserve_no] > 0:
            alms_sum = None
            for row in alms_data:
                if row[0] == reserve_no:
                    alms_sum = row[5]
                    break
            print(f"{reserve_no:10} | LMS: ${lms_dict[reserve_no]:12.2f} | ALMS charter_payments: ${alms_sum:12.2f}")
    
    # Summary
    print("\n" + "="*120)
    print("SUMMARY")
    print("="*120)
    print(f"Total ALMS paid_amount (24 charters):        ${total_missing + total_lms:12.2f}")
    print(f"Total LMS payments (24 charters):            ${total_lms:12.2f}")
    print(f"Charters with payment data in LMS:           {len(lms_data)}")
    print(f"Charters with NO payment data in LMS:        {len(MISSING_PAYMENT_CHARTERS) - len(lms_data)}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
