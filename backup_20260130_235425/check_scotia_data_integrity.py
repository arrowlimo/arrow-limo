#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Check data integrity for Scotia banking reconciliation.

Validates:
- Receipt completeness and accuracy
- Banking transaction linkage
- GST calculations
- Amount matching between banking and receipts
"""

import psycopg2
from decimal import Decimal

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def check_data_integrity():
    """Run all data integrity checks."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 70)
    print("SCOTIA DATA INTEGRITY CHECKS")
    print("=" * 70)
    
    # 1. Count Scotia receipts
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2
    """)
    scotia_receipts = cur.fetchone()[0]
    print(f"\n1. Receipts from Scotia banking: {scotia_receipts:,}")
    
    # 2. Check for NULL gross amounts
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2 
        AND gross_amount IS NULL
    """)
    null_gross = cur.fetchone()[0]
    print(f"2. Receipts with NULL gross_amount: {null_gross:,} {'❌ ERROR' if null_gross > 0 else '✅ OK'}")
    
    # 3. Check for negative GST
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2 
        AND gst_amount < 0
    """)
    negative_gst = cur.fetchone()[0]
    print(f"3. Receipts with negative GST: {negative_gst:,} {'❌ ERROR' if negative_gst > 0 else '✅ OK'}")
    
    # 4. Check for missing vendor names
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2 
        AND (vendor_name IS NULL OR vendor_name = '')
    """)
    missing_vendor = cur.fetchone()[0]
    print(f"4. Receipts with missing vendor: {missing_vendor:,} {'❌ ERROR' if missing_vendor > 0 else '✅ OK'}")
    
    # 5. Check for orphaned banking links
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '903990106011'
        AND bm.receipt_id NOT IN (SELECT receipt_id FROM receipts)
    """)
    orphaned_links = cur.fetchone()[0]
    print(f"5. Orphaned banking links (no receipt): {orphaned_links:,} {'❌ ERROR' if orphaned_links > 0 else '✅ OK'}")
    
    # 6. Check for receipts without banking link
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts r
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2
        AND NOT EXISTS (
            SELECT 1 
            FROM banking_receipt_matching_ledger bm 
            WHERE bm.receipt_id = r.receipt_id
        )
    """)
    unlinked_receipts = cur.fetchone()[0]
    print(f"6. Receipts without banking link: {unlinked_receipts:,} {'❌ ERROR' if unlinked_receipts > 0 else '✅ OK'}")
    
    # 7. Financial totals validation
    cur.execute("""
        SELECT 
            SUM(gross_amount),
            SUM(gst_amount),
            SUM(net_amount)
        FROM receipts
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2
    """)
    row = cur.fetchone()
    gross_total = Decimal(str(row[0] or 0))
    gst_total = Decimal(str(row[1] or 0))
    net_total = Decimal(str(row[2] or 0))
    
    print(f"\n7. Financial totals:")
    print(f"   Gross amount: ${gross_total:,.2f}")
    print(f"   GST amount:   ${gst_total:,.2f}")
    print(f"   Net amount:   ${net_total:,.2f}")
    
    # Check if gross - gst = net
    calculated_net = gross_total - gst_total
    difference = abs(calculated_net - net_total)
    print(f"   Validation: Gross - GST = Net")
    print(f"   Difference: ${difference:.2f} {'✅ OK' if difference < Decimal('0.01') else '❌ ERROR'}")
    
    # 8. Check banking/receipt amount mismatches
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(ABS(bt.debit_amount - r.gross_amount))
        FROM banking_transactions bt
        JOIN banking_receipt_matching_ledger bm ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bt.account_number = '903990106011'
        AND bt.debit_amount > 0
        AND ABS(bt.debit_amount - r.gross_amount) > 0.01
    """)
    row = cur.fetchone()
    mismatched_amounts = row[0]
    total_mismatch = Decimal(str(row[1] or 0))
    print(f"\n8. Banking/receipt amount mismatches: {mismatched_amounts:,} {'❌ ERROR' if mismatched_amounts > 0 else '✅ OK'}")
    if mismatched_amounts > 0:
        print(f"   Total mismatch amount: ${total_mismatch:,.2f}")
    
    # 9. Check duplicate receipts (same date, vendor, amount)
    cur.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT receipt_date, vendor_name, gross_amount, COUNT(*) as cnt
            FROM receipts
            WHERE created_from_banking = TRUE 
            AND mapped_bank_account_id = 2
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) dups
    """)
    duplicate_groups = cur.fetchone()[0]
    print(f"\n9. Duplicate receipt groups (date+vendor+amount): {duplicate_groups:,} {'⚠️  WARNING' if duplicate_groups > 0 else '✅ OK'}")
    
    # 10. Check for receipts with invalid dates
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2
        AND (receipt_date < '2010-01-01' OR receipt_date > CURRENT_DATE)
    """)
    invalid_dates = cur.fetchone()[0]
    print(f"10. Receipts with invalid dates: {invalid_dates:,} {'❌ ERROR' if invalid_dates > 0 else '✅ OK'}")
    
    # 11. Sample receipts with issues
    print("\n" + "=" * 70)
    print("SAMPLE RECEIPTS WITH ISSUES")
    print("=" * 70)
    
    # Show mismatched amounts
    if mismatched_amounts > 0:
        print("\nAmount mismatches (showing first 5):")
        cur.execute("""
            SELECT 
                bt.transaction_date,
                bt.description,
                bt.debit_amount as bank_amount,
                r.gross_amount as receipt_amount,
                ABS(bt.debit_amount - r.gross_amount) as difference
            FROM banking_transactions bt
            JOIN banking_receipt_matching_ledger bm ON bt.transaction_id = bm.banking_transaction_id
            JOIN receipts r ON bm.receipt_id = r.receipt_id
            WHERE bt.account_number = '903990106011'
            AND bt.debit_amount > 0
            AND ABS(bt.debit_amount - r.gross_amount) > 0.01
            ORDER BY ABS(bt.debit_amount - r.gross_amount) DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  {row[0]} | {row[1][:40]:40s} | Bank: ${row[2]:8.2f} | Receipt: ${row[3]:8.2f} | Diff: ${row[4]:.2f}")
    
    # Show duplicate groups
    if duplicate_groups > 0:
        print("\nDuplicate receipt groups (showing first 5):")
        cur.execute("""
            SELECT 
                receipt_date, 
                vendor_name, 
                gross_amount, 
                COUNT(*) as cnt,
                STRING_AGG(receipt_id::text, ', ') as receipt_ids
            FROM receipts
            WHERE created_from_banking = TRUE 
            AND mapped_bank_account_id = 2
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  {row[0]} | {row[1][:30]:30s} | ${row[2]:8.2f} | {row[3]} duplicates | IDs: {row[4]}")
    
    # 12. Category distribution
    print("\n" + "=" * 70)
    print("EXPENSE CATEGORY DISTRIBUTION")
    print("=" * 70)
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2
        GROUP BY category
        ORDER BY SUM(gross_amount) DESC
    """)
    print("\n{:<25s} {:>10s} {:>15s}".format("Category", "Count", "Total Amount"))
    print("-" * 70)
    for row in cur.fetchall():
        category = row[0] or 'NULL'
        count = row[1]
        amount = Decimal(str(row[2] or 0))
        print(f"{category:<25s} {count:>10,} ${amount:>13,.2f}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("INTEGRITY CHECK COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    check_data_integrity()
