#!/usr/bin/env python3
"""
TASK #10: Vendor Normalization from Verified Data
TASK #12: Smart Deduplication Engine
TASK #14: Reconciliation Report

This comprehensive script:
1. Extracts vendor patterns from VERIFIED/LOCKED banking transactions
2. Normalizes vendor names across all data
3. Identifies duplicates (excluding verified data, NSF charges, numbered variants)
4. Generates reconciliation report
"""
import psycopg2
from collections import defaultdict
import json
from datetime import datetime
from decimal import Decimal

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*100)
    print("TASKS #10, #12, #14: VENDOR NORMALIZATION & DEDUPLICATION & RECONCILIATION")
    print("="*100)
    
    # TASK #10: Build vendor normalization map from verified data
    print("\n📋 TASK #10: Building vendor normalization map from VERIFIED data...")
    
    cur.execute("""
        SELECT DISTINCT vendor_extracted, COUNT(*) as frequency
        FROM banking_transactions
        WHERE verified = TRUE 
        AND locked = TRUE
        AND vendor_extracted IS NOT NULL
        AND vendor_extracted != ''
        GROUP BY vendor_extracted
        ORDER BY frequency DESC
    """)
    
    verified_vendors = cur.fetchall()
    print(f"   ✅ Found {len(verified_vendors):,} unique verified vendors")
    
    # Create normalization map
    vendor_map = {}
    numbered_vendors = {}  # Track numbered variants like "Fas Gas 1", "Fas Gas 2"
    
    for vendor, freq in verified_vendors:
        # Check if this is a numbered variant
        base_name = vendor.rstrip('0123456789 ')
        if base_name != vendor and len(base_name) > 3:
            if base_name not in numbered_vendors:
                numbered_vendors[base_name] = []
            numbered_vendors[base_name].append(vendor)
        
        vendor_map[vendor.lower()] = vendor  # Canonical form
    
    print(f"   ℹ️  Found {len(numbered_vendors)} vendor groups with numbered locations")
    
    # Show top numbered variants
    print(f"\n   Top numbered vendor groups:")
    for base, variants in list(numbered_vendors.items())[:10]:
        print(f"      {base}: {', '.join(sorted(variants)[:5])}")
    
    # TASK #12: Smart Deduplication
    print("\n\n🔍 TASK #12: Smart Deduplication Engine...")
    
    # Find potential duplicates in banking transactions
    print("\n   Analyzing banking transactions for duplicates...")
    
    cur.execute("""
        WITH transaction_groups AS (
            SELECT 
                transaction_date,
                COALESCE(debit_amount, credit_amount) as amount,
                LOWER(TRIM(COALESCE(vendor_extracted, description))) as vendor_key,
                array_agg(transaction_id ORDER BY transaction_id) as tx_ids,
                array_agg(transaction_uid ORDER BY transaction_id) as uids,
                array_agg(verified ORDER BY transaction_id) as verified_flags,
                array_agg(locked ORDER BY transaction_id) as locked_flags,
                array_agg(is_nsf_charge ORDER BY transaction_id) as nsf_flags,
                COUNT(*) as dup_count
            FROM banking_transactions
            WHERE transaction_date IS NOT NULL
            AND (debit_amount > 0 OR credit_amount > 0)
            GROUP BY transaction_date, amount, vendor_key
            HAVING COUNT(*) > 1
        )
        SELECT * FROM transaction_groups
        ORDER BY dup_count DESC, transaction_date DESC
        LIMIT 500
    """)
    
    dup_groups = cur.fetchall()
    
    # Filter out protected transactions
    real_duplicates = []
    for date, amount, vendor, tx_ids, uids, verified, locked, nsf, count in dup_groups:
        # Skip if ANY transaction is verified/locked or NSF
        if any(verified) or any(locked) or any(nsf):
            continue
        
        # Skip if this looks like a numbered vendor variant
        is_numbered_variant = False
        for base in numbered_vendors:
            if base.lower() in vendor:
                is_numbered_variant = True
                break
        
        if is_numbered_variant:
            continue
        
        real_duplicates.append({
            'date': str(date),
            'amount': float(amount) if amount else 0,
            'vendor': vendor,
            'count': count,
            'transaction_uids': uids
        })
    
    print(f"   ✅ Found {len(real_duplicates):,} potential duplicate groups (after filtering)")
    print(f"   ℹ️  Excluded: verified/locked transactions, NSF charges, numbered variants")
    
    # Find receipt duplicates
    print("\n   Analyzing receipts for duplicates...")
    
    cur.execute("""
        WITH receipt_groups AS (
            SELECT 
                receipt_date,
                gross_amount,
                LOWER(TRIM(vendor_name)) as vendor_key,
                array_agg(receipt_id ORDER BY receipt_id) as receipt_ids,
                array_agg(source_hash ORDER BY receipt_id) as hashes,
                COUNT(*) as dup_count
            FROM receipts
            WHERE receipt_date IS NOT NULL
            AND gross_amount > 0
            AND vendor_name IS NOT NULL
            GROUP BY receipt_date, gross_amount, vendor_key
            HAVING COUNT(*) > 1
        )
        SELECT * FROM receipt_groups
        ORDER BY dup_count DESC, receipt_date DESC
        LIMIT 500
    """)
    
    receipt_dups = cur.fetchall()
    
    real_receipt_dups = []
    for date, amount, vendor, ids, hashes, count in receipt_dups:
        # Skip if hashes are different (different source = not a duplicate)
        unique_hashes = set(h for h in hashes if h)
        if len(unique_hashes) > 1:
            continue
        
        real_receipt_dups.append({
            'date': str(date),
            'amount': float(amount) if amount else 0,
            'vendor': vendor,
            'count': count,
            'receipt_ids': ids
        })
    
    print(f"   ✅ Found {len(real_receipt_dups):,} potential receipt duplicate groups")
    
    # TASK #14: Reconciliation Report
    print("\n\n📊 TASK #14: Generating Reconciliation Report...")
    
    # Get summary statistics
    cur.execute("""
        SELECT 
            COUNT(*) as total_transactions,
            COUNT(*) FILTER (WHERE verified = TRUE) as verified,
            COUNT(*) FILTER (WHERE locked = TRUE) as locked,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            COUNT(*) FILTER (WHERE gst_applicable = TRUE) as gst_applicable,
            COUNT(*) FILTER (WHERE gst_applicable = FALSE) as gst_exempt,
            COUNT(*) FILTER (WHERE gst_applicable IS NULL) as gst_unknown
        FROM banking_transactions
    """)
    
    banking_stats = cur.fetchone()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(*) FILTER (WHERE category = 'Unknown' OR category IS NULL) as unknown_category,
            SUM(gross_amount) as total_amount,
            SUM(gst_amount) as total_gst,
            COUNT(DISTINCT r.receipt_id) FILTER (
                WHERE EXISTS (
                    SELECT 1 FROM banking_receipt_matching_ledger bml 
                    WHERE bml.receipt_id = r.receipt_id
                )
            ) as matched_to_banking
        FROM receipts r
    """)
    
    receipt_stats = cur.fetchone()
    
    # Generate report
    report = {
        'generated_at': datetime.now().isoformat(),
        'banking_transactions': {
            'total': banking_stats[0],
            'verified': banking_stats[1],
            'locked': banking_stats[2],
            'total_debits': float(banking_stats[3]) if banking_stats[3] else 0,
            'total_credits': float(banking_stats[4]) if banking_stats[4] else 0,
            'gst_applicable': banking_stats[5],
            'gst_exempt': banking_stats[6],
            'gst_unknown': banking_stats[7]
        },
        'receipts': {
            'total': receipt_stats[0],
            'unknown_category': receipt_stats[1],
            'total_amount': float(receipt_stats[2]) if receipt_stats[2] else 0,
            'total_gst': float(receipt_stats[3]) if receipt_stats[3] else 0,
            'matched_to_banking': receipt_stats[4]
        },
        'vendor_normalization': {
            'verified_vendors': len(verified_vendors),
            'numbered_vendor_groups': len(numbered_vendors)
        },
        'duplicates': {
            'banking_duplicate_groups': len(real_duplicates),
            'receipt_duplicate_groups': len(real_receipt_dups),
            'banking_duplicates': real_duplicates[:50],  # Top 50
            'receipt_duplicates': real_receipt_dups[:50]
        }
    }
    
    # Save report
    report_file = 'l:\\limo\\data\\reconciliation_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"   ✅ Report saved to {report_file}")
    
    # Print summary
    print("\n" + "="*100)
    print("✅ TASKS #10, #12, #14 COMPLETE")
    print("="*100)
    
    print(f"\n📊 Summary:")
    print(f"   Banking Transactions: {banking_stats[0]:,}")
    print(f"      Verified/Locked: {banking_stats[2]:,} ({banking_stats[2]/banking_stats[0]*100:.1f}%)")
    print(f"      Debits: ${banking_stats[3] or 0:,.2f}")
    print(f"      Credits: ${banking_stats[4] or 0:,.2f}")
    print(f"      GST Unknown: {banking_stats[7]:,}")
    
    print(f"\n   Receipts: {receipt_stats[0]:,}")
    print(f"      Matched to Banking: {receipt_stats[4]:,} ({receipt_stats[4]/receipt_stats[0]*100:.1f}%)")
    print(f"      Unknown Category: {receipt_stats[1]:,}")
    print(f"      Total Amount: ${receipt_stats[2] or 0:,.2f}")
    
    print(f"\n   Vendor Normalization:")
    print(f"      Verified vendors: {len(verified_vendors):,}")
    print(f"      Numbered groups: {len(numbered_vendors)}")
    
    print(f"\n   Duplicates to Review:")
    print(f"      Banking: {len(real_duplicates):,} groups")
    print(f"      Receipts: {len(real_receipt_dups):,} groups")
    
    print(f"\n📁 Output: {report_file}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
