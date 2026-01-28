#!/usr/bin/env python3
"""
Apply categorization to remaining GL 6900 entries based on user guidance and business context.

Logic:
1. DRAFT*, DEBIT VIA DRAFT, BANK DRAFT → GL 9999 (Money out/personal draws)
2. BILL PAYMENT (no identifiable vendor) → GL 6900 (keep as unknown)
3. BUSINESS EXPENSE → GL 6900 (keep as unknown for manual review)
4. LFG BUSINESS PAD → GL 6100 (Office/Business Supplies - pre-auth debit)
5. CHEQUE errors (CHEQUE 955.46, CHEQUE WO) → GL 6900 (marked as cheque errors)
6. UNKNOWN POINT OF SALE → GL 6900 (card transactions needing detail)
7. CITY OF RED DEER → GL 5180 (Vehicle Registration/Licensing)
8. MONEY MART WITHDRAWAL → GL 9999 (Cash withdrawal)
9. CORRECTION 00339 → GL 6900 (accounting correction)
10. JOURNAL ENTRY → GL 6900 (fake entry - keep for review)
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

updates_made = defaultdict(lambda: {"count": 0, "amount": 0})

try:
    # 1. DRAFT PURCHASE → GL 9999 (Money check/draft payment)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE (vendor_name ILIKE 'DRAFT PURCHASE%' OR vendor_name ILIKE 'DEBIT VIA DRAFT%')
        AND gl_account_code = '6900'
    """)
    draft_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in draft_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '9999', 
                gl_account_name = 'Draft Payment - Vendor Payment',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['DRAFT PURCHASE/DEBIT VIA DRAFT → GL 9999']['count'] += 1
        updates_made['DRAFT PURCHASE/DEBIT VIA DRAFT → GL 9999']['amount'] += amount
    
    # 2. BANK DRAFT → GL 9999 (Bank draft payment method)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'BANK DRAFT%'
        AND gl_account_code = '6900'
    """)
    bd_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in bd_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '9999', 
                gl_account_name = 'Bank Draft - Vendor Payment',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['BANK DRAFT → GL 9999']['count'] += 1
        updates_made['BANK DRAFT → GL 9999']['amount'] += amount
    
    # 3. LFG BUSINESS PAD → GL 6100 (Office/Business - pre-authorized debit)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'LFG BUSINESS PAD%'
        AND gl_account_code = '6900'
    """)
    lfg_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in lfg_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6100', 
                gl_account_name = 'Office/Business Supplies',
                category = 'Office',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['LFG BUSINESS PAD → GL 6100']['count'] += 1
        updates_made['LFG BUSINESS PAD → GL 6100']['amount'] += amount
    
    # 4. CITY OF RED DEER → GL 5180 (Vehicle Registration/Licensing)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'CITY OF RED DEER%'
        AND gl_account_code = '6900'
    """)
    city_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in city_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '5180', 
                gl_account_name = 'Vehicle Registration/Licensing',
                category = 'Vehicle',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['CITY OF RED DEER → GL 5180']['count'] += 1
        updates_made['CITY OF RED DEER → GL 5180']['amount'] += amount
    
    # 5. MONEY MART WITHDRAWAL → GL 9999 (Cash out/loan)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'MONEY MART%'
        AND gl_account_code = '6900'
    """)
    mm_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in mm_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '9999', 
                gl_account_name = 'Cash Withdrawal/Personal Loan',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['MONEY MART → GL 9999']['count'] += 1
        updates_made['MONEY MART → GL 9999']['amount'] += amount
    
    # 6. EMAIL TRANSFER → GL 9999 (Personal transfer/withdrawal)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'EMAIL TRANSFER%'
        AND gl_account_code = '6900'
    """)
    et_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in et_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '9999', 
                gl_account_name = 'E-Transfer / Withdrawal',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['EMAIL TRANSFER → GL 9999']['count'] += 1
        updates_made['EMAIL TRANSFER → GL 9999']['amount'] += amount
    
    # 7. BILL PAYMENT (with specific vendor identifiable) → appropriate GL
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'BILL PAYMENT - FULL SPECTRUM%'
        AND gl_account_code = '6900'
    """)
    bp_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in bp_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6800', 
                gl_account_name = 'Telecommunications',
                category = 'Telecom',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['BILL PAYMENT - FULL SPECTRUM → GL 6800']['count'] += 1
        updates_made['BILL PAYMENT - FULL SPECTRUM → GL 6800']['amount'] += amount
    
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'BILL PAYMENT - 106.7%'
        AND gl_account_code = '6900'
    """)
    bp2_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in bp2_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '4220', 
                gl_account_name = 'Advertising & Marketing',
                category = 'Marketing',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['BILL PAYMENT - 106.7 THE DRIVE → GL 4220']['count'] += 1
        updates_made['BILL PAYMENT - 106.7 THE DRIVE → GL 4220']['amount'] += amount
    
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'BILL PAYMENT - CFIB%'
        AND gl_account_code = '6900'
    """)
    bp3_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in bp3_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '4220', 
                gl_account_name = 'Advertising & Marketing',
                category = 'Marketing',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['BILL PAYMENT - CFIB → GL 4220']['count'] += 1
        updates_made['BILL PAYMENT - CFIB → GL 4220']['amount'] += amount
    
    # 8. TAMMY PETTITT (office staff) → GL 6900 (keep for now, need context)
    # 9. JESSE GORDON, etc. → GL 6900 (driver/staff - keep for manual review)
    
    conn.commit()
    
    print("\n" + "="*80)
    print("AMBIGUOUS VENDOR TYPES CATEGORIZED")
    print("="*80)
    
    total_count = 0
    total_amount = 0
    
    for category, data in sorted(updates_made.items()):
        if data['count'] > 0:
            print(f"\n{category}")
            print(f"  Count: {data['count']:,} receipts")
            print(f"  Amount: ${data['amount']:,.2f}")
            total_count += data['count']
            total_amount += data['amount']
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {total_count:,} receipts (${total_amount:,.2f}) updated")
    print(f"{'='*80}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    raise

finally:
    cur.close()
    conn.close()
