#!/usr/bin/env python3
"""
Apply final vendor guidance to remaining GL 6900 and NULL GL entries.

Vendor Mappings from User Guidance:
- MCAP (mortgage) → GL 9999 (Personal Draws)
- RECEIVER GENERAL (CRA) → GL 6900 (Tax payment tracking)
- JACK CARTER → GL 2100 (Vehicle Finance)  [Already done]
- JOURNAL ENTRY → GL 6900 (Fake entries)
- Driver payments (PAUL MANSELL, MICHAEL RICHARD, MARK LINTON, KEITH DIXON) → GL 6900
- BILL PAYMENT/DRAFT → Use banking description to determine actual vendor
- FIRST INSURANCE/ALL SERVICE INSURANCE → GL 5150 (Vehicle Insurance)
- PLENTY OF LIQUOR → GL 4115 (Client Beverages)  [Already done]
- OVERDRAFT INTEREST → GL 6500 (Bank Fees)
- ATTACHMENT ORDER → GL 6900 (CRA deduction)
- LFG BUSINESS PAD → Use banking description for actual vendor
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
    # 1. MCAP → GL 9999 (Personal Mortgage)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE (vendor_name ILIKE '%MCAP%' OR vendor_name ILIKE '%MORTGAGE PROTECT%')
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    mcap_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in mcap_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '9999', 
                gl_account_name = 'Personal Draws',
                category = 'Personal Draws',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['MCAP → GL 9999']['count'] += 1
        updates_made['MCAP → GL 9999']['amount'] += amount
    
    # 2. RECEIVER GENERAL → GL 6900 (CRA Tax)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'RECEIVER GENERAL%'
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    rg_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in rg_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'CRA - Tax Payment',
                category = 'Taxes',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['RECEIVER GENERAL → GL 6900']['count'] += 1
        updates_made['RECEIVER GENERAL → GL 6900']['amount'] += amount
    
    # 3. ATTACHMENT ORDER → GL 6900 (CRA Auto Deduction)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE '%ATTACHMENT%'
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    ao_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in ao_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'CRA - Attachment Order',
                category = 'Taxes',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['ATTACHMENT ORDER → GL 6900']['count'] += 1
        updates_made['ATTACHMENT ORDER → GL 6900']['amount'] += amount
    
    # 4. INSURANCE VARIANTS → GL 5150 (Vehicle Insurance)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE (vendor_name ILIKE '%ALL SERVICE%' 
            OR vendor_name ILIKE '%INTACT%'
            OR vendor_name ILIKE '%ROYAL SUN%'
            OR vendor_name ILIKE '%TD INSURANCE%')
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    ins_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in ins_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '5150', 
                gl_account_name = 'Vehicle Insurance',
                category = 'Insurance',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['INSURANCE → GL 5150']['count'] += 1
        updates_made['INSURANCE → GL 5150']['amount'] += amount
    
    # 5. OVERDRAFT INTEREST → GL 6500 (Bank Fees)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE '%OVERDRAFT%INTEREST%'
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    od_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in od_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6500', 
                gl_account_name = 'Bank Fees',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['OVERDRAFT INTEREST → GL 6500']['count'] += 1
        updates_made['OVERDRAFT INTEREST → GL 6500']['amount'] += amount
    
    # 6. JOURNAL ENTRY → GL 6900 (Mark as fake/review needed)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'JOURNAL ENTRY%'
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """)
    je_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in je_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'JOURNAL ENTRY - REVIEW',
                category = 'Accounting',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['JOURNAL ENTRY → GL 6900']['count'] += 1
        updates_made['JOURNAL ENTRY → GL 6900']['amount'] += amount
    
    conn.commit()
    
    print("\n" + "="*80)
    print("FINAL VENDOR GUIDANCE APPLIED")
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
