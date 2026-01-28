#!/usr/bin/env python
"""
Banking Data Coverage Report

Analyzes which years have banking data and which have QuickBooks data available
for potential enrichment.
"""

import psycopg2
import os
import glob

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def check_banking_coverage():
    """Check which years have banking data in the database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("BANKING DATA COVERAGE ANALYSIS")
    print("=" * 80)
    print()
    
    # Get banking transaction coverage by year and account
    print("Step 1: Banking Transactions in Database")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            account_number,
            COUNT(*) as txn_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            COUNT(CASE WHEN vendor_extracted IS NOT NULL AND vendor_extracted != '' THEN 1 END) as with_vendor
        FROM banking_transactions
        WHERE transaction_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date), account_number
        ORDER BY year, account_number
    """)
    
    banking_data = {}
    for row in cur.fetchall():
        year, account, count, debits, credits, first, last, vendors = row
        year = int(year)
        if year not in banking_data:
            banking_data[year] = []
        banking_data[year].append({
            'account': account,
            'count': count,
            'debits': float(debits or 0),
            'credits': float(credits or 0),
            'first': first,
            'last': last,
            'vendors': vendors
        })
    
    for year in sorted(banking_data.keys()):
        print(f"\n{year}:")
        total_txns = sum(acc['count'] for acc in banking_data[year])
        total_vendors = sum(acc['vendors'] for acc in banking_data[year])
        print(f"  Total transactions: {total_txns:,}")
        print(f"  With vendor data: {total_vendors:,} ({total_vendors/total_txns*100:.1f}%)")
        print(f"  Accounts:")
        for acc in banking_data[year]:
            print(f"    - {acc['account']}: {acc['count']:,} txns "
                  f"(${acc['debits']:,.2f} debits, ${acc['credits']:,.2f} credits)")
            print(f"      Date range: {acc['first']} to {acc['last']}")
    
    print()
    
    # Check for QuickBooks CSV files
    print("Step 2: Available QuickBooks Register Files")
    print("-" * 80)
    
    qb_files = glob.glob(r'l:\limo\exports\banking\*_qb_register_parsed.csv')
    
    if not qb_files:
        print("No QuickBooks register files found in l:\\limo\\exports\\banking\\")
    else:
        print(f"Found {len(qb_files)} QuickBooks register files:\n")
        
        import pandas as pd
        qb_data = {}
        
        for qb_file in sorted(qb_files):
            filename = os.path.basename(qb_file)
            year = filename.split('_')[0]
            
            try:
                df = pd.read_csv(qb_file)
                
                if len(df) == 0:
                    status = "EMPTY (header only)"
                else:
                    date_range = f"{df['date'].min()} to {df['date'].max()}"
                    vendors = df['name'].notna().sum()
                    memos = df['memo'].notna().sum()
                    status = f"{len(df)} rows, {vendors} vendors, {memos} memos"
                    qb_data[year] = len(df)
                
                print(f"  {filename}: {status}")
            except Exception as e:
                print(f"  {filename}: ERROR - {str(e)}")
    
    print()
    
    # Cross-reference: which years have both banking and QB data?
    print("Step 3: Enrichment Opportunities")
    print("-" * 80)
    
    all_years = sorted(set(list(banking_data.keys()) + [int(y) for y in qb_data.keys()]))
    
    print("\nYear-by-year analysis:")
    for year in all_years:
        has_banking = year in banking_data
        has_qb = str(year) in qb_data
        
        status_parts = []
        if has_banking:
            txn_count = sum(acc['count'] for acc in banking_data[year])
            vendor_count = sum(acc['vendors'] for acc in banking_data[year])
            vendor_pct = vendor_count/txn_count*100
            status_parts.append(f"Banking: {txn_count:,} txns ({vendor_pct:.1f}% with vendors)")
        else:
            status_parts.append("Banking: NONE")
        
        if has_qb:
            status_parts.append(f"QB: {qb_data[str(year)]} rows")
        else:
            status_parts.append("QB: NONE")
        
        # Enrichment recommendation
        if has_banking and has_qb:
            if vendor_pct < 50:
                recommendation = "✓ ENRICHMENT RECOMMENDED"
            else:
                recommendation = "✓ Already enriched"
        elif has_banking and not has_qb:
            recommendation = "⚠ No QB data available"
        elif not has_banking and has_qb:
            recommendation = "⚠ Banking data missing"
        else:
            recommendation = "✗ No data"
        
        print(f"\n  {year}: {recommendation}")
        print(f"    {status_parts[0]}")
        print(f"    {status_parts[1]}")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Years with banking data: {len(banking_data)}")
    print(f"Years with QB data: {len(qb_data)}")
    print(f"Years ready for enrichment: {len([y for y in banking_data.keys() if str(y) in qb_data])}")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_banking_coverage()
