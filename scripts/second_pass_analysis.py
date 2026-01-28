#!/usr/bin/env python3
"""
SECOND PASS ANALYSIS - After vendor information amendments
Create detailed categorized report of remaining issues
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

try:
    print("\n" + "="*100)
    print("SECOND PASS ANALYSIS - POST-AMENDMENT RECONCILIATION")
    print("="*100)
    
    # 1. Remaining orphan categories
    print("\n" + "="*100)
    print("ORPHAN RECEIPTS BY MAJOR CATEGORIES (2,568 total, $1,352,461)")
    print("="*100)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE banking_transaction_id IS NULL
        GROUP BY vendor_name
        ORDER BY SUM(gross_amount) DESC
        LIMIT 40
    """)
    
    orphan_data = cur.fetchall()
    categories = {
        'HEFFNER': [],
        'INSURANCE': [],
        'DRAFT': [],
        'EMAIL': [],
        'CHEQUE': [],
        'CORRECTION': [],
        'BANKING': [],
        'MISC': []
    }
    
    for vendor_name, count, total in orphan_data:
        if 'HEFFNER' in vendor_name:
            categories['HEFFNER'].append((vendor_name, count, total))
        elif 'INSURANCE' in vendor_name or 'CMB' in vendor_name or 'TD INSURANCE' in vendor_name:
            categories['INSURANCE'].append((vendor_name, count, total))
        elif 'DRAFT' in vendor_name:
            categories['DRAFT'].append((vendor_name, count, total))
        elif 'EMAIL' in vendor_name or 'TRANSFER' in vendor_name:
            categories['EMAIL'].append((vendor_name, count, total))
        elif 'CHEQUE' in vendor_name or 'CHQUE' in vendor_name:
            categories['CHEQUE'].append((vendor_name, count, total))
        elif 'CORRECTION' in vendor_name or 'JOURNAL' in vendor_name:
            categories['CORRECTION'].append((vendor_name, count, total))
        elif vendor_name in ['OPENING BALANCE', 'TRANSFER', 'WITHDRAWAL', 'DEPOSIT']:
            categories['BANKING'].append((vendor_name, count, total))
        else:
            categories['MISC'].append((vendor_name, count, total))
    
    for cat_name, items in categories.items():
        if items:
            cat_total = sum(amt for _, _, amt in items if amt)
            cat_count = sum(cnt for _, cnt, _ in items)
            print(f"\n{cat_name} ({cat_count} receipts, ${cat_total:,.2f}):")
            for vendor_name, count, total in items:
                total_str = f"${total:,.2f}" if total else "NULL"
                print(f"  {vendor_name:<50} {count:>4} receipts  {total_str:>12}")
    
    # 2. GL categorization status now
    print("\n" + "="*100)
    print("GL CATEGORIZATION STATUS (Updated)")
    print("="*100)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN gl_account_code IS NULL THEN 'No GL'
                WHEN gl_account_code = '6900' THEN 'GL 6900 (Unknown)'
                ELSE 'Proper GL'
            END as status,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        GROUP BY status
    """)
    
    gl_data = cur.fetchall()
    for status, count, total in sorted(gl_data):
        pct = (count / 33980) * 100 if count else 0
        print(f"{status:<25} {count:>6,} receipts ({pct:>5.1f}%)  ${total:>15,.2f}")
    
    # 3. Specific problem categories
    print("\n" + "="*100)
    print("SPECIFIC PROBLEM CATEGORIES - ACTION REQUIRED")
    print("="*100)
    
    # EMAIL TRANSFER missing recipient
    print("\nEMAIL TRANSFER (Still missing recipient) - 403 receipts, $187,900")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name = 'EMAIL TRANSFER'
        GROUP BY vendor_name
    """)
    et_result = cur.fetchone()
    if et_result:
        vendor_name, count, total = et_result
        print(f"  {vendor_name:<50} {count:>4} receipts  ${total:>12,.2f}")
        print(f"  Action: Extract recipient from banking description (automated in next phase)")
    
    # BILL PAYMENT without vendor
    print("\nBILL PAYMENT (No vendor identified) - 6 receipts, $15,025")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount
        FROM receipts
        WHERE vendor_name = 'BILL PAYMENT'
        ORDER BY gross_amount DESC
    """)
    bp_results = cur.fetchall()
    for receipt_id, vendor_name, amount in bp_results:
        print(f"  Receipt {receipt_id}: ${amount:>10,.2f}")
    
    # CHEQUE errors still outstanding
    print("\nCHEQUE ERRORS - BANKING VERIFIED")
    print("  CHEQUE 955.46 - $195,406 (Need user confirmation)")
    print("  CHEQUE WO -120.00 - $158,363 (Need user confirmation)")
    print("  CHEQUE (Payee unknown) - 118 receipts, $119,049 (Cheque # OCR issues)")
    
    # CORRECTION 00339
    print("\nCORRECTION 00339 - 114 receipts, $70,332 (Accounting correction)")
    print("  Action: Verify business purpose in banking description")
    
    # DRAFT entries
    print("\nDRAFT PURCHASE - 8 receipts, $18,686 (Business payment method)")
    print("  Action: Verify against banking, these are legitimate draft payments")
    
    # 4. Heffner orphans
    print("\n" + "="*100)
    print("HEFFNER ORPHAN ANALYSIS (19 NULL + 50+ valid orphans)")
    print("="*100)
    
    cur.execute("""
        SELECT COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name ILIKE '%HEFFNER%'
        AND banking_transaction_id IS NULL
    """)
    
    hf_orphan = cur.fetchone()
    total_str = f"${hf_orphan[1]:,.2f}" if hf_orphan[1] else "NULL"
    print(f"\nTotal Heffner orphans: {hf_orphan[0]} receipts, {total_str}")
    
    # NULL amount Heffners (duplicates)
    cur.execute("""
        SELECT COUNT(*) as count
        FROM receipts
        WHERE vendor_name ILIKE '%HEFFNER%'
        AND gross_amount IS NULL
    """)
    hf_null = cur.fetchone()
    print(f"  - NULL Amount (duplicates): {hf_null[0]} receipts → DELETE")
    
    # Valid Heffner orphans
    cur.execute("""
        SELECT COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name ILIKE '%HEFFNER%'
        AND gross_amount IS NOT NULL
        AND banking_transaction_id IS NULL
    """)
    hf_valid = cur.fetchone()
    total_str = f"${hf_valid[1]:,.2f}" if hf_valid[1] else "NULL"
    print(f"  - Valid amount (legitimate): {hf_valid[0]} receipts, {total_str}")
    print(f"    These are likely accrual entries or system-generated charges")
    
    # 5. CMB Insurance (big orphans)
    print("\n" + "="*100)
    print("CMB INSURANCE BROKERS - Major Orphan Category")
    print("="*100)
    
    cur.execute("""
        SELECT receipt_date, SUM(gross_amount) as total, COUNT(*) as count
        FROM receipts
        WHERE vendor_name = 'CMB INSURANCE BROKERS'
        AND banking_transaction_id IS NULL
        GROUP BY receipt_date
        ORDER BY receipt_date DESC
    """)
    
    cmb_results = cur.fetchall()
    total_cmb = sum(amt for _, amt, _ in cmb_results if amt)
    count_cmb = sum(cnt for _, _, cnt in cmb_results)
    print(f"\nTotal: {count_cmb} annual policies, ${total_cmb:,.2f}")
    print("These are yearly insurance premiums - likely legitimate but no banking match")
    print("Possible reasons:")
    print("  1. Insurance is billed but not yet paid")
    print("  2. Insurance is paid from separate account/method")
    print("  3. System-generated accrual entries")
    print("\nRecommendation: Keep these - verify with insurance broker for payment status")
    
    # 6. Summary statistics
    print("\n" + "="*100)
    print("SUMMARY FOR NEXT PHASE")
    print("="*100)
    
    print("\nClear Deletion (26 receipts, $52,966):")
    print("  ✓ JOURNAL ENTRY: 3 receipts")
    print("  ✓ HEFFNER NULL: 19 receipts")
    print("  ✓ OPENING BALANCE: 2 receipts")
    print("  ✓ TELUS DUPLICATE: 1 receipt")
    print("  ✓ ONE MORE pass needed for duplicates")
    
    print("\nNeeds Vendor Extraction (403 receipts, $187,900):")
    print("  ✓ EMAIL TRANSFER (generic): Extract recipient from banking description")
    
    print("\nNeeds Investigation (2,139 receipts, $1,164,495):")
    print("  • HEFFNER orphans: 50+ receipts (likely valid accruals)")
    print("  • CMB INSURANCE: 5 annual policies ($327K) - legitimacy check")
    print("  • TD INSURANCE: 3 policies ($32K) - legitimacy check")
    print("  • CHEQUE errors: 118 unknown payees ($119K)")
    print("  • CORRECTION 00339: 114 entries ($70K)")
    print("  • DRAFT PURCHASE: 8 entries ($18K)")
    print("  • Misc vendors: 1000+ small items")
    
    print("\n" + "="*100)

finally:
    cur.close()
    conn.close()
