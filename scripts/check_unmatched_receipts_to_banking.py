#!/usr/bin/env python3
"""
Check how many receipts (deposits, cash withdrawals, purchases) have not been 
matched to CIBC or Scotia banking transactions.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("UNMATCHED RECEIPTS TO BANKING ANALYSIS")
    print("="*80)
    
    # Check if receipts table has banking linkage columns
    print("\n1. Checking receipts table schema for banking links...")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name IN ('banking_transaction_id', 'mapped_bank_account_id', 'created_from_banking')
        ORDER BY column_name
    """)
    
    banking_columns = cur.fetchall()
    if banking_columns:
        print("   Found banking columns in receipts:")
        for col, dtype in banking_columns:
            print(f"   - {col} ({dtype})")
    else:
        print("   No direct banking columns in receipts table")
    
    # Check for junction table
    print("\n2. Checking for receipt-banking junction table...")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%receipt%' 
        AND table_name LIKE '%banking%'
    """)
    
    junction_tables = cur.fetchall()
    if junction_tables:
        print(f"   Found junction table(s): {', '.join([t[0] for t in junction_tables])}")
    else:
        print("   No receipt-banking junction table found")
    
    # Get total receipts count
    print("\n3. Overall receipts statistics...")
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN business_personal = 'Business' THEN 1 END) as business_receipts,
            COUNT(CASE WHEN business_personal = 'Personal' THEN 1 END) as personal_receipts,
            ROUND(SUM(CASE WHEN business_personal = 'Business' THEN gross_amount ELSE 0 END)::numeric, 2) as business_total,
            ROUND(SUM(CASE WHEN business_personal = 'Personal' THEN gross_amount ELSE 0 END)::numeric, 2) as personal_total
        FROM receipts
    """)
    
    total_stats = cur.fetchone()
    print(f"\n   Total receipts:     {total_stats[0]:,}")
    print(f"   Business receipts:  {total_stats[1]:,} (${total_stats[3]:,.2f})")
    print(f"   Personal receipts:  {total_stats[2]:,} (${total_stats[4]:,.2f})")
    
    # Check receipts with mapped_bank_account_id
    if 'mapped_bank_account_id' in [col[0] for col in banking_columns]:
        print("\n4. Checking receipts with mapped_bank_account_id...")
        cur.execute("""
            SELECT 
                COUNT(*) as with_account,
                COUNT(CASE WHEN business_personal = 'Business' THEN 1 END) as business_with_account,
                ROUND(SUM(CASE WHEN business_personal = 'Business' THEN gross_amount ELSE 0 END)::numeric, 2) as business_amount
            FROM receipts
            WHERE mapped_bank_account_id IS NOT NULL
        """)
        
        mapped = cur.fetchone()
        print(f"   Receipts with bank account: {mapped[0]:,}")
        print(f"   Business receipts with account: {mapped[1]:,} (${mapped[2]:,.2f})")
        
        # Get unmapped receipts
        cur.execute("""
            SELECT 
                COUNT(*) as without_account,
                COUNT(CASE WHEN business_personal = 'Business' THEN 1 END) as business_without_account,
                ROUND(SUM(CASE WHEN business_personal = 'Business' THEN gross_amount ELSE 0 END)::numeric, 2) as business_amount
            FROM receipts
            WHERE mapped_bank_account_id IS NULL
        """)
        
        unmapped = cur.fetchone()
        print(f"\n   Receipts WITHOUT bank account: {unmapped[0]:,}")
        print(f"   Business receipts WITHOUT account: {unmapped[1]:,} (${unmapped[2]:,.2f})")
    
    # Check junction table linkage if it exists
    if junction_tables:
        junction_table = junction_tables[0][0]
        print(f"\n5. Checking {junction_table} linkage...")
        
        cur.execute(f"""
            SELECT 
                COUNT(DISTINCT receipt_id) as linked_receipts
            FROM {junction_table}
        """)
        
        linked = cur.fetchone()[0]
        print(f"   Receipts linked via junction table: {linked:,}")
        
        # Get unlinked receipts
        cur.execute(f"""
            SELECT 
                COUNT(*) as unlinked,
                COUNT(CASE WHEN business_personal = 'Business' THEN 1 END) as business_unlinked,
                ROUND(SUM(CASE WHEN business_personal = 'Business' THEN gross_amount ELSE 0 END)::numeric, 2) as business_amount
            FROM receipts r
            WHERE NOT EXISTS (
                SELECT 1 FROM {junction_table} j 
                WHERE j.receipt_id = r.receipt_id
            )
        """)
        
        unlinked = cur.fetchone()
        print(f"\n   Receipts NOT linked via junction: {unlinked[0]:,}")
        print(f"   Business receipts NOT linked: {unlinked[1]:,} (${unlinked[2]:,.2f})")
    
    # Check banking transactions (CIBC and Scotia)
    print("\n6. Banking transactions by account...")
    cur.execute("""
        SELECT 
            account_number,
            COUNT(*) as transaction_count,
            MIN(transaction_date) as earliest_date,
            MAX(transaction_date) as latest_date,
            ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_debits,
            ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2) as total_credits
        FROM banking_transactions
        WHERE account_number IN ('0228362', '3714081')  -- CIBC and Scotia
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    banking_stats = cur.fetchall()
    for acct, count, earliest, latest, debits, credits in banking_stats:
        bank_name = 'CIBC' if acct == '0228362' else 'Scotia'
        print(f"\n   {bank_name} ({acct}):")
        print(f"   - Transactions: {count:,}")
        print(f"   - Date range: {earliest} to {latest}")
        print(f"   - Total debits: ${debits:,.2f}")
        print(f"   - Total credits: ${credits:,.2f}")
    
    # Check for receipts that match banking transaction patterns
    print("\n7. Analyzing receipt categories for banking matches...")
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as receipt_count,
            ROUND(SUM(gross_amount)::numeric, 2) as total_amount
        FROM receipts
        WHERE business_personal = 'Business'
        AND category IS NOT NULL
        GROUP BY category
        ORDER BY total_amount DESC
        LIMIT 20
    """)
    
    categories = cur.fetchall()
    print("\n   Top 20 business receipt categories:")
    print(f"   {'Category':<30} {'Count':>8} {'Amount':>15}")
    print(f"   {'-'*30} {'-'*8} {'-'*15}")
    for cat, count, amount in categories:
        print(f"   {cat[:30]:<30} {count:>8,} ${amount:>13,.2f}")
    
    # Check receipts by vendor for potential banking matches
    print("\n8. Checking receipts by vendor (potential banking matches)...")
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as receipt_count,
            ROUND(SUM(gross_amount)::numeric, 2) as total_amount
        FROM receipts
        WHERE business_personal = 'Business'
        AND vendor_name IS NOT NULL
        AND vendor_name != ''
        GROUP BY vendor_name
        HAVING COUNT(*) >= 5
        ORDER BY total_amount DESC
        LIMIT 20
    """)
    
    vendors = cur.fetchall()
    print("\n   Top 20 vendors (5+ receipts):")
    print(f"   {'Vendor':<40} {'Count':>8} {'Amount':>15}")
    print(f"   {'-'*40} {'-'*8} {'-'*15}")
    for vendor, count, amount in vendors:
        print(f"   {vendor[:40]:<40} {count:>8,} ${amount:>13,.2f}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if junction_tables and unlinked:
        unmatched_count = unlinked[1]
        unmatched_amount = unlinked[2]
        match_rate = ((total_stats[1] - unmatched_count) / total_stats[1] * 100) if total_stats[1] > 0 else 0
        
        print(f"\nBusiness Receipts NOT matched to banking:")
        print(f"  Count: {unmatched_count:,} of {total_stats[1]:,} ({100-match_rate:.1f}%)")
        print(f"  Amount: ${unmatched_amount:,.2f} of ${total_stats[3]:,.2f}")
        print(f"\nBusiness Receipts MATCHED to banking:")
        print(f"  Count: {total_stats[1] - unmatched_count:,} ({match_rate:.1f}%)")
        print(f"  Amount: ${total_stats[3] - unmatched_amount:,.2f}")
    elif 'mapped_bank_account_id' in [col[0] for col in banking_columns] and unmapped:
        unmatched_count = unmapped[1]
        unmatched_amount = unmapped[2]
        match_rate = ((total_stats[1] - unmatched_count) / total_stats[1] * 100) if total_stats[1] > 0 else 0
        
        print(f"\nBusiness Receipts WITHOUT bank account mapping:")
        print(f"  Count: {unmatched_count:,} of {total_stats[1]:,} ({100-match_rate:.1f}%)")
        print(f"  Amount: ${unmatched_amount:,.2f} of ${total_stats[3]:,.2f}")
        print(f"\nBusiness Receipts WITH bank account mapping:")
        print(f"  Count: {total_stats[1] - unmatched_count:,} ({match_rate:.1f}%)")
        print(f"  Amount: ${total_stats[3] - unmatched_amount:,.2f}")
    else:
        print("\nNo banking linkage method detected in receipts table")
        print("All receipts are effectively unmatched to banking transactions")
    
    print("\n" + "="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
