#!/usr/bin/env python3
"""
AMEND RECEIPT VENDOR INFORMATION - Phase 1
Extract real vendor names from banking transaction descriptions and fix:
1. Bank account numbers (000000XXXX) → Extract real vendor
2. EMAIL TRANSFER (missing recipient) → Extract recipient from banking
3. Bill Payment entries → Add vendor from banking description
4. Louise Berglund consolidation
"""

import psycopg2
import os
import re
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

updates_made = defaultdict(lambda: {"count": 0, "vendors": []})

try:
    print("\n" + "="*100)
    print("AMENDING RECEIPT VENDOR INFORMATION FROM BANKING DESCRIPTIONS")
    print("="*100)
    
    # 1. Fix BANK ACCOUNT NUMBERS - Extract real vendor from banking description
    print("\n1. FIXING BANK ACCOUNT VENDOR NAMES (57 receipts)...")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, bt.description, r.gross_amount
        FROM receipts r
        JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name LIKE '000000%'
        ORDER BY r.gross_amount DESC
    """)
    
    ba_results = cur.fetchall()
    for receipt_id, old_vendor, banking_desc, amount in ba_results:
        # Try to extract vendor name from banking description
        new_vendor = None
        
        # Pattern: Look for common vendor patterns in description
        if banking_desc:
            # Common patterns: "Debit ... - VENDOR NAME"
            patterns = [
                r'(?:Debit|Transfer|Payment)\s+(?:to|from)\s+(.+?)(?:\s*-|\s*$|$)',
                r'(?:Payment|Transfer)\s+(.+?)(?:\s*-|\s*$|$)',
                r'(?:Cheque|Check)\s+(?:to|for)\s+(.+?)(?:\s*-|\s*$|$)',
                r'(?:to|from|via)\s+(.+?)(?:\s*-|\s*$|$)',
                r'^([A-Z][A-Z0-9\s]+?)(?:\s*-|\s*$)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, banking_desc, re.IGNORECASE)
                if match:
                    extracted = match.group(1).strip()
                    # Only use if it looks like a real vendor name (not just numbers)
                    if extracted and len(extracted) > 3 and not extracted.isdigit():
                        new_vendor = extracted.upper()
                        break
        
        # If we found a vendor name, use it; otherwise mark for manual review
        if new_vendor and new_vendor != old_vendor:
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    auto_categorized = true
                WHERE receipt_id = %s
            """, (new_vendor, receipt_id))
            updates_made['BANK_ACCOUNT_FIXED']['count'] += 1
            updates_made['BANK_ACCOUNT_FIXED']['vendors'].append((old_vendor, new_vendor, amount))
            print(f"   Receipt {receipt_id}: {old_vendor} → {new_vendor} (${amount:,.2f})")
        else:
            # Use description as-is if extraction failed
            if banking_desc and banking_desc != old_vendor:
                cur.execute("""
                    UPDATE receipts
                    SET vendor_name = %s,
                        auto_categorized = true
                    WHERE receipt_id = %s
                """, (banking_desc[:60], receipt_id))
                updates_made['BANK_ACCOUNT_FALLBACK']['count'] += 1
                print(f"   Receipt {receipt_id}: {old_vendor} → {banking_desc[:40]}... (${amount:,.2f})")
            else:
                print(f"   Receipt {receipt_id}: COULD NOT FIX - {old_vendor} (Keep for manual review)")
    
    # 2. Fix EMAIL TRANSFER (missing recipient) - Extract from banking description
    print("\n2. FIXING EMAIL TRANSFER WITHOUT RECIPIENT (503 receipts)...")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, bt.description, r.gross_amount
        FROM receipts r
        JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name = 'EMAIL TRANSFER'
        AND r.banking_transaction_id IS NOT NULL
        LIMIT 100
    """)
    
    et_results = cur.fetchall()
    et_fixed = 0
    for receipt_id, old_vendor, banking_desc, amount in et_results:
        new_vendor = None
        
        # Extract recipient from banking description
        # Pattern: "E-TRANSFER TO RECIPIENT" or similar
        patterns = [
            r'(?:E-?TRANSFER|EMAIL TRANSFER)(?:\s+TO)?\s+(.+?)(?:\s+ID|\s*-|$)',
            r'(?:TO|FOR)\s+(.+?)(?:\s+ID|\s*-|$)',
            r'(?:INTERNET BANKING E-TRANSFER).*?([A-Z][A-Z0-9\s]+?)(?:\s+ID|\s*$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, banking_desc, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                if extracted and len(extracted) > 2:
                    new_vendor = f"EMAIL TRANSFER - {extracted.upper()}"
                    break
        
        if new_vendor:
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    auto_categorized = true
                WHERE receipt_id = %s
            """, (new_vendor, receipt_id))
            et_fixed += 1
            if et_fixed <= 5:  # Show first 5
                print(f"   Receipt {receipt_id}: {old_vendor} → {new_vendor[:50]}... (${amount:,.2f})")
    
    if et_fixed > 5:
        print(f"   ... and {et_fixed - 5} more EMAIL TRANSFER entries")
    updates_made['EMAIL_TRANSFER_FIXED']['count'] = et_fixed
    
    # 3. Consolidate Louise Berglund variants
    print("\n3. CONSOLIDATING LOUISE BERGLUND ENTRIES...")
    cur.execute("""
        UPDATE receipts
        SET vendor_name = 'LOUISE BERGLUND - ACCOUNTANT',
            auto_categorized = true
        WHERE (vendor_name ILIKE '%BERGLUND%' 
               OR vendor_name ILIKE '%LOUISE%')
        AND vendor_name NOT IN ('LOUISE BERGLUND - ACCOUNTANT')
        AND banking_transaction_id IS NOT NULL
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    lb_results = cur.fetchall()
    print(f"   Consolidated: {len(lb_results)} entries to 'LOUISE BERGLUND - ACCOUNTANT'")
    updates_made['LOUISE_BERGLUND']['count'] = len(lb_results)
    
    # 4. Fix BILL PAYMENT entries - Extract vendor from description
    print("\n4. FIXING BILL PAYMENT (Add vendor name from banking)...")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, bt.description, r.gross_amount
        FROM receipts r
        JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name = 'BILL PAYMENT'
        AND r.banking_transaction_id IS NOT NULL
    """)
    
    bp_results = cur.fetchall()
    bp_fixed = 0
    for receipt_id, old_vendor, banking_desc, amount in bp_results:
        new_vendor = None
        
        # Extract vendor from "Bill Payment (Cheque) - VENDOR NAME"
        patterns = [
            r'(?:Bill Payment|Payment).*?\(.*?\)\s*-\s*(.+?)(?:\s*$)',
            r'(?:Bill Payment|Payment)\s+(?:for|to)\s+(.+?)(?:\s*$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, banking_desc, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                if extracted and len(extracted) > 2:
                    new_vendor = f"BILL PAYMENT - {extracted.upper()}"
                    break
        
        if new_vendor and new_vendor != old_vendor:
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    auto_categorized = true
                WHERE receipt_id = %s
            """, (new_vendor, receipt_id))
            bp_fixed += 1
            if bp_fixed <= 5:
                print(f"   Receipt {receipt_id}: {old_vendor} → {new_vendor[:50]}... (${amount:,.2f})")
    
    if bp_fixed > 5:
        print(f"   ... and {bp_fixed - 5} more BILL PAYMENT entries")
    updates_made['BILL_PAYMENT_FIXED']['count'] = bp_fixed
    
    # 5. Standardize ETRANSFER FEE entries
    print("\n5. STANDARDIZING ETRANSFER FEE ENTRIES...")
    cur.execute("""
        UPDATE receipts
        SET vendor_name = 'ETRANSFER FEE',
            auto_categorized = true
        WHERE (vendor_name ILIKE 'EMAIL TRANSFER FEE%'
               OR vendor_name ILIKE 'ETRANSFER FEE%')
        AND vendor_name != 'ETRANSFER FEE'
    """)
    etf_count = cur.rowcount
    print(f"   Standardized {etf_count} ETRANSFER FEE entries")
    
    conn.commit()
    
    print("\n" + "="*100)
    print("VENDOR INFORMATION AMENDMENT SUMMARY")
    print("="*100)
    
    total_updated = 0
    for category, data in sorted(updates_made.items()):
        if data['count'] > 0:
            print(f"\n{category}: {data['count']} receipts updated")
            if data['vendors']:
                for old_v, new_v, amt in data['vendors'][:3]:
                    print(f"  {old_v} → {new_v} (${amt:,.2f})")
            total_updated += data['count']
    
    print(f"\n{'='*100}")
    print(f"TOTAL RECEIPTS AMENDED: {total_updated}")
    print(f"{'='*100}")
    print(f"\nNEXT STEP: Run analysis again to identify remaining issues")
    
except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise

finally:
    cur.close()
    conn.close()
