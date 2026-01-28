#!/usr/bin/env python3
"""
Import complete 2013 banking data for BOTH CIBC and Scotia accounts.
Then analyze patterns, errors, and data quality across the full year.
"""

import os
import sys
import psycopg2
from collections import defaultdict
from decimal import Decimal

DRY_RUN = '--write' not in sys.argv

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    print("\n" + "="*80)
    print("2013 FULL YEAR BANKING IMPORT - BOTH ACCOUNTS")
    print("="*80)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check current 2013 data
    print("\nCURRENT 2013 DATA IN DATABASE:")
    print("-"*80)
    
    for account_name, account_num in [('CIBC', '0228362'), ('Scotia', '903990106011')]:
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM transaction_date)::int as month,
                COUNT(*),
                SUM(debit_amount),
                SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            GROUP BY EXTRACT(MONTH FROM transaction_date)
            ORDER BY month
        """, (account_num,))
        
        rows = cur.fetchall()
        
        print(f"\n{account_name} Account {account_num}:")
        if len(rows) == 0:
            print("  No data in database")
        else:
            print(f"  {'Month':<10} {'Count':>8} {'Debits':>15} {'Credits':>15}")
            total_count = 0
            total_debits = 0
            total_credits = 0
            
            for month, count, debits, credits in rows:
                print(f"  {month:02d}/2013    {count:>8} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f}")
                total_count += count
                total_debits += float(debits or 0)
                total_credits += float(credits or 0)
            
            print(f"  {'-'*48}")
            print(f"  {'TOTAL':<10} {total_count:>8} ${total_debits:>13,.2f} ${total_credits:>13,.2f}")
    
    # Check available PDFs
    print("\n" + "="*80)
    print("AVAILABLE SOURCE FILES:")
    print("="*80)
    
    pdf_dir = r'l:\limo\pdf\2013'
    
    cibc_files = [
        'cibc 2013 jan.pdf',
        'cbic 2013 feb.pdf',
        'cibc 3013 mar.pdf',
        'cibc 3013 apr -jul.pdf',
        'cibc 2013 aug-dec.pdf'
    ]
    
    scotia_files = [
        'scotiabank 2013 december -sept.pdf'
    ]
    
    print("\nCIBC Files:")
    for f in cibc_files:
        exists = os.path.exists(os.path.join(pdf_dir, f))
        status = "✓" if exists else "✗"
        print(f"  {status} {f}")
    
    print("\nScotia Files:")
    for f in scotia_files:
        exists = os.path.exists(os.path.join(pdf_dir, f))
        status = "✓" if exists else "✗"
        print(f"  {status} {f}")
    
    # Check for existing import scripts
    print("\n" + "="*80)
    print("AVAILABLE IMPORT SCRIPTS:")
    print("="*80)
    
    scripts_dir = r'l:\limo\scripts'
    
    import_scripts = []
    for filename in os.listdir(scripts_dir):
        if filename.startswith('import_') and '2013' in filename and filename.endswith('.py'):
            import_scripts.append(filename)
    
    cibc_scripts = [s for s in import_scripts if 'cibc' in s.lower()]
    scotia_scripts = [s for s in import_scripts if 'scotia' in s.lower()]
    
    print(f"\nCIBC Import Scripts ({len(cibc_scripts)}):")
    for s in sorted(cibc_scripts):
        print(f"  • {s}")
    
    print(f"\nScotia Import Scripts ({len(scotia_scripts)}):")
    for s in sorted(scotia_scripts):
        print(f"  • {s}")
    
    # Analyze patterns in current data
    print("\n" + "="*80)
    print("DATA QUALITY ANALYSIS:")
    print("="*80)
    
    # Check for gaps in monthly coverage
    print("\nMONTHLY COVERAGE GAPS:")
    
    for account_name, account_num in [('CIBC', '0228362'), ('Scotia', '903990106011')]:
        cur.execute("""
            SELECT EXTRACT(MONTH FROM transaction_date)::int as month
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            GROUP BY EXTRACT(MONTH FROM transaction_date)
            ORDER BY month
        """, (account_num,))
        
        months_with_data = {row[0] for row in cur.fetchall()}
        missing_months = set(range(1, 13)) - months_with_data
        
        print(f"\n{account_name} Account {account_num}:")
        print(f"  Months with data: {sorted(months_with_data)}")
        print(f"  Missing months: {sorted(missing_months)}")
        
        if len(missing_months) > 0:
            print(f"  ⚠️ {len(missing_months)} months need importing")
    
    # Check for transaction categorization
    print("\n" + "="*80)
    print("TRANSACTION CATEGORIZATION STATUS:")
    print("="*80)
    
    for account_name, account_num in [('CIBC', '0228362'), ('Scotia', '903990106011')]:
        cur.execute("""
            SELECT 
                category,
                COUNT(*),
                SUM(debit_amount),
                SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """, (account_num,))
        
        rows = cur.fetchall()
        
        print(f"\n{account_name} Account {account_num}:")
        if len(rows) == 0:
            print("  No data")
        else:
            uncategorized = sum(r[1] for r in rows if not r[0])
            total = sum(r[1] for r in rows)
            
            print(f"  Total transactions: {total}")
            print(f"  Uncategorized: {uncategorized} ({uncategorized/total*100:.1f}%)")
            
            if len(rows) <= 10:
                print(f"\n  {'Category':<30} {'Count':>8} {'Debits':>15} {'Credits':>15}")
                for cat, count, debits, credits in rows:
                    cat_name = cat or '(uncategorized)'
                    print(f"  {cat_name:<30} {count:>8} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f}")
    
    # Check for vendor_extracted
    print("\n" + "="*80)
    print("VENDOR EXTRACTION STATUS:")
    print("="*80)
    
    for account_name, account_num in [('CIBC', '0228362'), ('Scotia', '903990106011')]:
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(vendor_extracted) as with_vendor,
                COUNT(*) - COUNT(vendor_extracted) as without_vendor
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2013
        """, (account_num,))
        
        total, with_vendor, without_vendor = cur.fetchone()
        
        print(f"\n{account_name} Account {account_num}:")
        if total == 0:
            print("  No data")
        else:
            print(f"  Total transactions: {total}")
            print(f"  With vendor: {with_vendor} ({with_vendor/total*100:.1f}%)")
            print(f"  Without vendor: {without_vendor} ({without_vendor/total*100:.1f}%)")
    
    # Recommendations
    print("\n" + "="*80)
    print("IMPORT RECOMMENDATIONS:")
    print("="*80)
    
    print("\n1. CIBC Account (0228362):")
    print("   - Jan 2013: Use import_jan_2013_cibc_verified.py (if exists)")
    print("   - Feb 2013: Use import_feb_2013_cibc_verified.py (if exists)")
    print("   - Mar 2013: Use import_mar_2013_cibc_verified.py (if exists)")
    print("   - Apr-Jul 2013: Extract from 'cibc 3013 apr -jul.pdf'")
    print("   - Aug-Dec 2013: Use import_aug_sep_oct_2013_batch.py or similar")
    
    print("\n2. Scotia Account (903990106011):")
    print("   - Sep-Dec 2013: Extract from 'scotiabank 2013 december -sept.pdf'")
    print("   - Dec 2013: Use import_scotia_dec2013_blended.py (ready)")
    print("   - Jan-Aug 2013: Need to locate source or use QuickBooks")
    
    print("\n3. Data Quality Improvements:")
    print("   - Run categorization script on all imported transactions")
    print("   - Extract vendor names from descriptions")
    print("   - Apply JOURNAL_ENTRY vs INVOICE classification")
    print("   - Match to receipts where possible")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Review existing verified import scripts (Jan-Mar 2013)")
    print("2. Run existing imports first (low-hanging fruit)")
    print("3. Extract remaining months from PDFs")
    print("4. Apply comprehensive categorization")
    print("5. Generate full year analysis report")
    print("="*80)

if __name__ == '__main__':
    main()
