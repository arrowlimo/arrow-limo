#!/usr/bin/env python
"""
Safe QuickBooks Vendor Enrichment for Banking Data

This script:
1. Reads QuickBooks register CSV (2012 or 2013)
2. Matches to banking_transactions by date + amount
3. UPDATES matched rows with QB vendor name and memo
4. NEVER deletes any existing data
5. Supports dry-run mode for validation

Purpose: Enrich banking transaction descriptions with structured QB vendor data.
"""

import psycopg2
import pandas as pd
import os
from datetime import datetime
import argparse

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def clean_amount(amt_str):
    """Convert QuickBooks amount string to float."""
    if pd.isna(amt_str) or amt_str == '':
        return 0.0
    # Remove commas and quotes
    amt_str = str(amt_str).replace(',', '').replace('"', '').strip()
    try:
        return float(amt_str)
    except:
        return 0.0

def enrich_banking_with_qb(qb_csv_path, year, dry_run=True):
    """Enrich banking transactions with QuickBooks vendor data."""
    
    print("=" * 80)
    print(f"QUICKBOOKS VENDOR ENRICHMENT FOR {year}")
    print("Mode: DRY-RUN" if dry_run else "Mode: WRITE TO DATABASE")
    print("=" * 80)
    print()
    
    # Step 1: Load QuickBooks data
    print(f"Step 1: Loading QuickBooks data from {qb_csv_path}...")
    print("-" * 80)
    
    df = pd.read_csv(qb_csv_path)
    print(f"Loaded {len(df)} QuickBooks transactions")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Non-empty vendor names: {df['name'].notna().sum()}")
    print(f"Non-empty memos: {df['memo'].notna().sum()}")
    print()
    
    # Step 2: Parse amounts
    print("Step 2: Parsing QuickBooks amounts...")
    print("-" * 80)
    
    df['debit_parsed'] = df['debit'].apply(clean_amount)
    df['credit_parsed'] = df['credit'].apply(clean_amount)
    
    print(f"Parsed debits: {(df['debit_parsed'] > 0).sum()} transactions")
    print(f"Parsed credits: {(df['credit_parsed'] > 0).sum()} transactions")
    print()
    
    # Step 3: Connect to database
    print("Step 3: Connecting to database...")
    print("-" * 80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current banking transactions for year
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            account_number,
            vendor_extracted
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date
    """, (year,))
    
    banking_txns = cur.fetchall()
    print(f"Found {len(banking_txns)} banking transactions in {year}")
    print()
    
    # Step 4: Match QB to banking
    print("Step 4: Matching QuickBooks to banking transactions...")
    print("-" * 80)
    
    matches = []
    
    for idx, qb_row in df.iterrows():
        qb_date = pd.to_datetime(qb_row['date']).date() if pd.notna(qb_row['date']) else None
        qb_debit = qb_row['debit_parsed']
        qb_credit = qb_row['credit_parsed']
        qb_name = qb_row['name'] if pd.notna(qb_row['name']) else ''
        qb_memo = qb_row['memo'] if pd.notna(qb_row['memo']) else ''
        
        if not qb_date:
            continue
        
        # Try to match against banking transactions
        for bank_txn in banking_txns:
            bank_id, bank_date, bank_desc, bank_debit, bank_credit, bank_acct, bank_vendor = bank_txn
            
            # Match criteria: same date AND (same debit OR same credit)
            date_match = (bank_date == qb_date)
            debit_match = (abs(float(bank_debit or 0) - qb_debit) < 0.01) if qb_debit > 0 else False
            credit_match = (abs(float(bank_credit or 0) - qb_credit) < 0.01) if qb_credit > 0 else False
            
            if date_match and (debit_match or credit_match):
                matches.append({
                    'bank_id': bank_id,
                    'bank_date': bank_date,
                    'bank_desc': bank_desc,
                    'bank_vendor': bank_vendor,
                    'qb_name': qb_name,
                    'qb_memo': qb_memo,
                    'amount': qb_debit if qb_debit > 0 else qb_credit
                })
    
    print(f"Found {len(matches)} matches between QB and banking")
    print()
    
    # Step 5: Analyze matches
    print("Step 5: Analyzing enrichment opportunities...")
    print("-" * 80)
    
    # Count how many would be enriched
    new_vendors = 0
    enhanced_descriptions = 0
    
    for match in matches:
        # Would add vendor if currently empty and QB name is valid
        if not match['bank_vendor'] or match['bank_vendor'].strip() == '':
            if match['qb_name'] and match['qb_name'].strip() not in ['Ö', '', 'WD']:
                clean_name = match['qb_name'].replace('Ö', '').strip()
                if clean_name:
                    new_vendors += 1
        
        # Would enhance description if QB has valid memo
        if match['qb_memo'] and match['qb_memo'].strip() not in ['Ö', '', 'WD']:
            clean_memo = match['qb_memo'].replace('Ö', '').strip()
            if clean_memo:
                enhanced_descriptions += 1
    
    print(f"Enrichment statistics:")
    print(f"  - Would add {new_vendors} new vendor names")
    print(f"  - Would enhance {enhanced_descriptions} descriptions with QB memos")
    print()
    
    # Show sample matches
    print("Sample enrichment (first 10 matches):")
    for i, match in enumerate(matches[:10], 1):
        print(f"\n  Match {i}:")
        print(f"    Date: {match['bank_date']}")
        print(f"    Amount: ${match['amount']:.2f}")
        print(f"    Current desc: {match['bank_desc'][:60]}")
        print(f"    Current vendor: {match['bank_vendor'] or '(empty)'}")
        print(f"    QB vendor: {match['qb_name']}")
        print(f"    QB memo: {match['qb_memo']}")
    print()
    
    # Step 6: Apply updates (if not dry-run)
    if not dry_run:
        print("Step 6: Applying enrichment updates...")
        print("-" * 80)
        
        updated_vendors = 0
        updated_descriptions = 0
        
        for match in matches:
            updates = []
            values = []
            
            # Update vendor_extracted if QB has name and current is empty
            # Filter out encoding garbage and generic placeholders
            if match['qb_name'] and match['qb_name'].strip() not in ['Ö', '', 'WD']:
                clean_name = match['qb_name'].replace('Ö', '').strip()
                if clean_name and (not match['bank_vendor'] or match['bank_vendor'].strip() == ''):
                    updates.append("vendor_extracted = %s")
                    values.append(clean_name)
                    updated_vendors += 1
            
            # Prepend QB memo to description if available
            # Filter out encoding garbage and generic placeholders
            if match['qb_memo'] and match['qb_memo'].strip() not in ['Ö', '', 'WD']:
                clean_memo = match['qb_memo'].replace('Ö', '').strip()
                if clean_memo:
                    new_desc = f"[QB: {clean_memo}] {match['bank_desc']}"
                    updates.append("description = %s")
                    values.append(new_desc)
                    updated_descriptions += 1
            
            if updates:
                values.append(match['bank_id'])
                update_sql = f"""
                    UPDATE banking_transactions
                    SET {', '.join(updates)}
                    WHERE transaction_id = %s
                """
                cur.execute(update_sql, values)
        
        conn.commit()
        
        print(f"Enrichment complete:")
        print(f"  ✓ Updated {updated_vendors} vendor names")
        print(f"  ✓ Enhanced {updated_descriptions} descriptions")
        print()
    else:
        print("Step 6: Skipped (dry-run mode)")
        print("-" * 80)
        print("Run with --write to apply changes")
        print()
    
    # Step 7: Summary
    print("=" * 80)
    print("ENRICHMENT SUMMARY:")
    print("=" * 80)
    print(f"QuickBooks transactions: {len(df)}")
    print(f"Banking transactions: {len(banking_txns)}")
    print(f"Matched: {len(matches)}")
    print(f"Match rate: {len(matches)/len(df)*100:.1f}%")
    print()
    print("Data safety:")
    print("  ✓ No transactions deleted")
    print("  ✓ Only UPDATE operations performed")
    print("  ✓ Existing data preserved")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Enrich banking with QuickBooks vendor data')
    parser.add_argument('--qb-csv', required=True, help='Path to QuickBooks register CSV')
    parser.add_argument('--year', type=int, required=True, help='Year to enrich (2012, 2013, etc)')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    
    args = parser.parse_args()
    
    enrich_banking_with_qb(args.qb_csv, args.year, dry_run=not args.write)
