#!/usr/bin/env python3
"""
Verify banking-to-receipt matching with rules for safe deduplication.

Rules:
1. One banking transaction → one receipt (1:1 ideal state)
2. Split receipts allowed (one banking → multiple receipts)
3. Multiple fees/charges from same banking → keep all (don't deduplicate)
4. NSF sequences → keep all (2-3 transactions per NSF cycle)
5. When receipt has multiple banking links → don't deduplicate
6. When duplicate receipts exist (both from banking) → delete least productive one (prefer GL codes, dates, descriptions)

Analysis produces:
- Healthy 1:1 matches (keep as-is)
- Split receipts (keep all - intentional)
- Multiple banking per receipt (keep all - don't delete)
- Duplicate pairs with 1:1 links (mark for safe deletion)
- NSF sequences (protect - don't delete)
"""

import psycopg2
from collections import defaultdict
import csv
from datetime import datetime, timedelta
import re

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def normalize_vendor(vendor_name):
    """Normalize vendor names for comparison."""
    if not vendor_name:
        return ""
    vendor = vendor_name.upper().strip()
    vendor = re.sub(r'\b(LTD|LIMITED|INC|INCORPORATED|CORP|CORPORATION|LLC)\b\.?', '', vendor)
    vendor = re.sub(r'[^\w\s]', '', vendor)
    vendor = re.sub(r'\s+', ' ', vendor).strip()
    return vendor

def is_nsf_related(description, vendor):
    """Check if receipt is NSF-related."""
    text = f"{description or ''} {vendor or ''}".upper()
    nsf_keywords = ['NSF', 'RETURNED', 'REVERSAL', 'AUTO-WITHDRAWAL', 'FAILED']
    return any(kw in text for kw in nsf_keywords)

def is_fee(description, vendor):
    """Check if receipt is a fee/charge."""
    text = f"{description or ''} {vendor or ''}".upper()
    fee_keywords = ['FEE', 'CHARGE', 'INTEREST', 'OVERDRAFT', 'SERVICE CHARGE', 'S/C']
    return any(kw in text for kw in fee_keywords)

def has_productive_gl(gl_code):
    """Check if GL code is 'productive' (not general/uncategorized)."""
    if not gl_code:
        return False
    # GL 5850 is general/uncategorized - least productive
    # GL 5920 is personal - also low productivity
    productive = not gl_code.endswith('850') and not gl_code.endswith('920')
    return productive

def analyze_matching():
    """Analyze banking-to-receipt matching patterns."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("BANKING-TO-RECEIPT MATCHING ANALYSIS")
    print("=" * 80)
    
    # STEP 1: Get all banking transactions with receipt linkages
    print("\nSTEP 1: Loading banking transactions and their receipt linkages...")
    
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            COUNT(DISTINCT r.receipt_id) as receipt_count,
            ARRAY_AGG(DISTINCT r.receipt_id) as receipt_ids,
            ARRAY_AGG(DISTINCT r.gross_amount) as receipt_amounts,
            ARRAY_AGG(DISTINCT r.vendor_name) as receipt_vendors,
            ARRAY_AGG(DISTINCT r.gl_account_code) as receipt_gl_codes,
            ARRAY_AGG(DISTINCT r.created_at::date) as receipt_created_dates
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '0228362'
        AND bt.debit_amount > 0
        GROUP BY bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount
        ORDER BY bt.transaction_date DESC
    """)
    
    banking_records = cur.fetchall()
    print(f"Found {len(banking_records)} banking debit transactions")
    
    # STEP 2: Categorize by matching pattern
    print("\nSTEP 2: Categorizing by matching pattern...")
    
    patterns = {
        'one_to_one_healthy': [],          # 1 banking → 1 receipt, no duplicates
        'one_to_one_duplicate': [],         # 1 banking → 2+ receipts (potential duplicates)
        'split_receipt': [],                # 1 banking → 2+ receipts (intentional split)
        'multiple_fees': [],                # 1 banking → multiple fee receipts (keep all)
        'nsf_sequence': [],                 # NSF/reversal receipts (keep all)
        'unmatched': []                     # Banking with no receipts
    }
    
    for record in banking_records:
        txn_id, txn_date, txn_desc, txn_amount, receipt_count, receipt_ids, receipt_amounts, receipt_vendors, receipt_gl_codes, receipt_dates = record
        
        if receipt_count == 0:
            # Unmatched banking transaction
            patterns['unmatched'].append({
                'banking_id': txn_id,
                'date': txn_date,
                'description': txn_desc,
                'amount': txn_amount,
                'note': 'No receipt found'
            })
        
        elif receipt_count == 1:
            # 1:1 match - check if healthy
            patterns['one_to_one_healthy'].append({
                'banking_id': txn_id,
                'date': txn_date,
                'description': txn_desc,
                'amount': txn_amount,
                'receipt_id': receipt_ids[0],
                'receipt_amount': receipt_amounts[0],
                'receipt_vendor': receipt_vendors[0],
                'receipt_gl': receipt_gl_codes[0],
                'receipt_date': receipt_dates[0]
            })
        
        else:
            # receipt_count > 1 - multiple receipts for one banking
            
            # Check if NSF-related
            vendors_str = ' '.join([v or '' for v in receipt_vendors])
            if is_nsf_related(txn_desc, vendors_str):
                patterns['nsf_sequence'].append({
                    'banking_id': txn_id,
                    'date': txn_date,
                    'description': txn_desc,
                    'amount': txn_amount,
                    'receipt_count': receipt_count,
                    'receipt_ids': receipt_ids,
                    'receipt_amounts': receipt_amounts,
                    'receipt_vendors': receipt_vendors,
                    'note': f'{receipt_count} receipts (NSF sequence - KEEP ALL)'
                })
            
            # Check if all are fees
            elif all(is_fee(rd or '', rv or '') for rd, rv in zip([txn_desc] * receipt_count, receipt_vendors)):
                patterns['multiple_fees'].append({
                    'banking_id': txn_id,
                    'date': txn_date,
                    'description': txn_desc,
                    'amount': txn_amount,
                    'receipt_count': receipt_count,
                    'receipt_ids': receipt_ids,
                    'receipt_amounts': receipt_amounts,
                    'receipt_vendors': receipt_vendors,
                    'note': f'{receipt_count} receipts (all fees - KEEP ALL)'
                })
            
            # Check if split receipt (amounts sum reasonably)
            elif abs(sum(receipt_amounts) - txn_amount) < 0.01:
                patterns['split_receipt'].append({
                    'banking_id': txn_id,
                    'date': txn_date,
                    'description': txn_desc,
                    'amount': txn_amount,
                    'receipt_count': receipt_count,
                    'receipt_ids': receipt_ids,
                    'receipt_amounts': receipt_amounts,
                    'receipt_vendors': receipt_vendors,
                    'total_receipt_amount': sum(receipt_amounts),
                    'note': f'{receipt_count} receipts (split receipt - KEEP ALL)'
                })
            
            else:
                # Potential duplicates
                patterns['one_to_one_duplicate'].append({
                    'banking_id': txn_id,
                    'date': txn_date,
                    'description': txn_desc,
                    'amount': txn_amount,
                    'receipt_count': receipt_count,
                    'receipt_ids': receipt_ids,
                    'receipt_amounts': receipt_amounts,
                    'receipt_vendors': receipt_vendors,
                    'receipt_gl_codes': receipt_gl_codes,
                    'note': f'{receipt_count} receipts (potential duplicates - REVIEW)'
                })
    
    # STEP 3: Display summary
    print("\n" + "=" * 80)
    print("MATCHING PATTERN SUMMARY")
    print("=" * 80)
    
    total_banking = len(banking_records)
    print(f"\nTotal banking debit transactions analyzed: {total_banking:,}")
    print(f"\nPattern Distribution:")
    print(f"  ✅ 1:1 Healthy matches:              {len(patterns['one_to_one_healthy']):>6,} ({len(patterns['one_to_one_healthy'])/total_banking*100:>5.1f}%)")
    print(f"  ⚠️  1:1 Duplicate candidates:        {len(patterns['one_to_one_duplicate']):>6,} ({len(patterns['one_to_one_duplicate'])/total_banking*100:>5.1f}%)")
    print(f"  📋 Split receipts (intentional):    {len(patterns['split_receipt']):>6,} ({len(patterns['split_receipt'])/total_banking*100:>5.1f}%)")
    print(f"  💰 Multiple fees (keep all):        {len(patterns['multiple_fees']):>6,} ({len(patterns['multiple_fees'])/total_banking*100:>5.1f}%)")
    print(f"  ⚡ NSF sequences (keep all):        {len(patterns['nsf_sequence']):>6,} ({len(patterns['nsf_sequence'])/total_banking*100:>5.1f}%)")
    print(f"  ❌ Unmatched banking:               {len(patterns['unmatched']):>6,} ({len(patterns['unmatched'])/total_banking*100:>5.1f}%)")
    
    # STEP 4: Analyze duplicate candidates for safe deletion
    print("\n" + "=" * 80)
    print("DUPLICATE CANDIDATES ANALYSIS")
    print("=" * 80)
    
    safe_deletes = []
    
    for dup in patterns['one_to_one_duplicate']:
        # Get full receipt details
        receipt_ids = dup['receipt_ids']
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                gl_account_code,
                description,
                created_at
            FROM receipts
            WHERE receipt_id = ANY(%s)
            ORDER BY created_at DESC
        """, (list(receipt_ids),))
        
        receipts = cur.fetchall()
        
        if len(receipts) == 2:
            # Compare the two receipts
            r1 = receipts[0]  # Newer
            r2 = receipts[1]  # Older
            
            r1_id, r1_date, r1_vendor, r1_amount, r1_gl, r1_desc, r1_created = r1
            r2_id, r2_date, r2_vendor, r2_amount, r2_gl, r2_desc, r2_created = r2
            
            # Scoring: which receipt is more productive for accounting?
            r1_score = 0
            r2_score = 0
            
            # GL code productivity
            if has_productive_gl(r1_gl):
                r1_score += 10
            if has_productive_gl(r2_gl):
                r2_score += 10
            
            # Has description
            if r1_desc and len(r1_desc) > 10:
                r1_score += 5
            if r2_desc and len(r2_desc) > 10:
                r2_score += 5
            
            # Amount matches exactly
            if r1_amount == dup['amount']:
                r1_score += 5
            if r2_amount == dup['amount']:
                r2_score += 5
            
            # Prefer earlier receipt (closer to actual date)
            if (r1_date - dup['date']).days <= 3:
                r1_score += 3
            if (r2_date - dup['date']).days <= 3:
                r2_score += 3
            
            # Determine which to keep
            keep_id = r1_id if r1_score >= r2_score else r2_id
            delete_id = r2_id if r1_score >= r2_score else r1_id
            
            safe_deletes.append({
                'banking_id': dup['banking_id'],
                'banking_date': dup['date'],
                'banking_amount': dup['amount'],
                'keep_receipt_id': keep_id,
                'delete_receipt_id': delete_id,
                'keep_reason': f"GL:{keep_id}_receipt.gl_account_code if keep_id==r1_id else r2_gl, productivity score: {r1_score if keep_id==r1_id else r2_score}",
                'delete_reason': f"Duplicate with lower productivity score: {r2_score if keep_id==r1_id else r1_score}"
            })
    
    print(f"\nFound {len(safe_deletes)} duplicate candidate pairs for potential deletion")
    print(f"(These are 1:1 banking matches with 2 receipts - safest to delete)")
    
    # Display examples
    if safe_deletes:
        print(f"\nFirst 10 safe deletion candidates:")
        for i, sd in enumerate(safe_deletes[:10], 1):
            print(f"  {i}. Banking {sd['banking_id']} ({sd['banking_date'].date()}): "
                  f"Keep receipt {sd['keep_receipt_id']}, Delete {sd['delete_receipt_id']}")
    
    # STEP 5: Export detailed results
    print("\n" + "=" * 80)
    print("EXPORTING RESULTS")
    print("=" * 80)
    
    # Export 1:1 healthy matches
    csv_file = f"l:\\limo\\reports\\banking_receipt_matching_healthy_1to1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['banking_id', 'date', 'description', 'amount', 'receipt_id', 'receipt_vendor', 'receipt_gl', 'status'])
        writer.writeheader()
        for record in patterns['one_to_one_healthy'][:1000]:  # Sample
            writer.writerow({
                'banking_id': record['banking_id'],
                'date': record['date'],
                'description': record['description'],
                'amount': record['amount'],
                'receipt_id': record['receipt_id'],
                'receipt_vendor': record['receipt_vendor'],
                'receipt_gl': record['receipt_gl'],
                'status': '✅ HEALTHY 1:1'
            })
    print(f"\n✅ Exported healthy 1:1 matches (sample of 1,000): {csv_file}")
    
    # Export NSF sequences
    csv_file = f"l:\\limo\\reports\\banking_receipt_matching_nsf_sequences_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['banking_id', 'date', 'description', 'amount', 'receipt_count', 'receipt_ids', 'status'])
        writer.writeheader()
        for record in patterns['nsf_sequence']:
            writer.writerow({
                'banking_id': record['banking_id'],
                'date': record['date'],
                'description': record['description'],
                'amount': record['amount'],
                'receipt_count': record['receipt_count'],
                'receipt_ids': '|'.join(str(rid) for rid in record['receipt_ids']),
                'status': '⚡ NSF SEQUENCE - KEEP ALL'
            })
    print(f"⚡ Exported NSF sequences (to PRESERVE): {csv_file}")
    
    # Export split receipts
    csv_file = f"l:\\limo\\reports\\banking_receipt_matching_splits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['banking_id', 'date', 'description', 'banking_amount', 'receipt_count', 'total_receipt_amount', 'status'])
        writer.writeheader()
        for record in patterns['split_receipt']:
            writer.writerow({
                'banking_id': record['banking_id'],
                'date': record['date'],
                'description': record['description'],
                'banking_amount': record['amount'],
                'receipt_count': record['receipt_count'],
                'total_receipt_amount': record['total_receipt_amount'],
                'status': '📋 SPLIT RECEIPT - KEEP ALL'
            })
    print(f"📋 Exported split receipts (to PRESERVE): {csv_file}")
    
    # Export multiple fees
    csv_file = f"l:\\limo\\reports\\banking_receipt_matching_fees_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['banking_id', 'date', 'description', 'amount', 'receipt_count', 'status'])
        writer.writeheader()
        for record in patterns['multiple_fees']:
            writer.writerow({
                'banking_id': record['banking_id'],
                'date': record['date'],
                'description': record['description'],
                'amount': record['amount'],
                'receipt_count': record['receipt_count'],
                'status': '💰 MULTIPLE FEES - KEEP ALL'
            })
    print(f"💰 Exported multiple fees (to PRESERVE): {csv_file}")
    
    # Export safe deletion candidates
    if safe_deletes:
        csv_file = f"l:\\limo\\reports\\banking_receipt_safe_deletes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['banking_id', 'banking_date', 'banking_amount', 'keep_receipt_id', 'delete_receipt_id', 'reason'])
            writer.writeheader()
            for record in safe_deletes:
                writer.writerow({
                    'banking_id': record['banking_id'],
                    'banking_date': record['banking_date'],
                    'banking_amount': record['banking_amount'],
                    'keep_receipt_id': record['keep_receipt_id'],
                    'delete_receipt_id': record['delete_receipt_id'],
                    'reason': f"Keep (higher GL productivity), Delete (lower productivity)"
                })
        print(f"🗑️  Exported safe deletion candidates: {csv_file}")
    
    # STEP 6: Final summary
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATIONS")
    print("=" * 80)
    
    print(f"\n✅ HEALTHY STATE (keep as-is):")
    print(f"   {len(patterns['one_to_one_healthy']):,} 1:1 matches - no action needed")
    
    print(f"\n📋 INTENTIONAL SPLITS (keep all):")
    print(f"   {len(patterns['split_receipt']):,} split receipt groups - don't deduplicate")
    
    print(f"\n💰 MULTIPLE FEES (keep all):")
    print(f"   {len(patterns['multiple_fees']):,} fee groups - don't deduplicate")
    
    print(f"\n⚡ NSF SEQUENCES (keep all):")
    print(f"   {len(patterns['nsf_sequence']):,} NSF groups - CRITICAL: don't deduplicate")
    
    print(f"\n🗑️  SAFE DELETIONS (verify before executing):")
    print(f"   {len(safe_deletes):,} duplicate pairs where 1 receipt is less productive")
    if safe_deletes:
        total_delete_amount = sum(sd['banking_amount'] for sd in safe_deletes)
        print(f"   Total duplicated amount: ${total_delete_amount:,.2f}")
        print(f"   Expected recovery: ~{len(safe_deletes)} duplicate receipts")
    
    print(f"\n❌ UNMATCHED BANKING (review):")
    print(f"   {len(patterns['unmatched']):,} banking transactions with no receipts")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)
    
    conn.close()

if __name__ == "__main__":
    analyze_matching()
