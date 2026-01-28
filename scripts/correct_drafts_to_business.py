#!/usr/bin/env python3
"""
CORRECTION: Reclassify draft/cash withdrawals as BUSINESS payments, not personal.

User guidance: 
- "bank drafts are business"
- "debit via draft is business"
- "all cash out is business"

Moving from GL 9999 (Personal Draws) to GL 6900 (Business - Unknown Vendor Type)
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
    # 1. DRAFT PURCHASE → GL 6900 (Business payment method - vendor unknown)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE (vendor_name ILIKE 'DRAFT PURCHASE%' OR vendor_name ILIKE 'DEBIT VIA DRAFT%')
        AND gl_account_code = '9999'
    """)
    draft_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in draft_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'Business Draft Payment - Unknown Vendor',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['DRAFT/DEBIT VIA DRAFT → GL 6900']['count'] += 1
        updates_made['DRAFT/DEBIT VIA DRAFT → GL 6900']['amount'] += amount
    
    # 2. BANK DRAFT → GL 6900 (Business draft payment)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'BANK DRAFT%'
        AND gl_account_code = '9999'
    """)
    bd_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in bd_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'Business Draft Payment - Unknown Vendor',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['BANK DRAFT → GL 6900']['count'] += 1
        updates_made['BANK DRAFT → GL 6900']['amount'] += amount
    
    # 3. EMAIL TRANSFER → GL 6900 (Business transfer/payment - vendor unknown)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'EMAIL TRANSFER%'
        AND gl_account_code = '9999'
        AND vendor_name NOT ILIKE '%EMAIL TRANSFER - %'
    """)
    et_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in et_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'Business E-Transfer - Unknown Vendor',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['EMAIL TRANSFER (generic) → GL 6900']['count'] += 1
        updates_made['EMAIL TRANSFER (generic) → GL 6900']['amount'] += amount
    
    # 4. MONEY MART WITHDRAWAL → GL 6900 (Business cash withdrawal)
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE 'MONEY MART%'
        AND gl_account_code = '9999'
    """)
    mm_rows = cur.fetchall()
    
    for receipt_id, vendor_name, amount in mm_rows:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '6900', 
                gl_account_name = 'Business Cash Withdrawal - Unknown Vendor',
                category = 'Banking',
                auto_categorized = true
            WHERE receipt_id = %s
        """, (receipt_id,))
        updates_made['MONEY MART → GL 6900']['count'] += 1
        updates_made['MONEY MART → GL 6900']['amount'] += amount
    
    conn.commit()
    
    print("\n" + "="*80)
    print("CORRECTION: BUSINESS DRAFT/CASH PAYMENTS RECLASSIFIED")
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
    print(f"TOTAL: {total_count:,} receipts (${total_amount:,.2f}) corrected to GL 6900")
    print(f"Note: These are business payments where specific vendor is unknown")
    print(f"{'='*80}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    raise

finally:
    cur.close()
    conn.close()
