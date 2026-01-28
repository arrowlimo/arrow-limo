#!/usr/bin/env python3
"""
Verify which CIBC accounts were downloaded from banking files for pre-2025 periods.
"""
import psycopg2

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*80)
    print("CIBC ACCOUNTS IN BANKING_TRANSACTIONS (Pre-2025)")
    print("="*80)
    
    # Get all CIBC account variations
    cur.execute("""
        SELECT 
            account_number,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as tx_count,
            COUNT(DISTINCT EXTRACT(YEAR FROM transaction_date)) as year_count,
            array_agg(DISTINCT EXTRACT(YEAR FROM transaction_date) ORDER BY EXTRACT(YEAR FROM transaction_date)) as years
        FROM banking_transactions
        WHERE (account_number ILIKE '%CIBC%' 
            OR account_number LIKE '%228%' 
            OR account_number LIKE '%616%'
            OR account_number LIKE '%0228362%')
        AND transaction_date < '2025-01-01'
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    cibc_accounts = cur.fetchall()
    
    if not cibc_accounts:
        print("\n❌ No CIBC accounts found in banking_transactions")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(cibc_accounts)} CIBC account variations:\n")
    print(f"{'Account Number':<25} {'Earliest':<12} {'Latest':<12} {'Tx Count':>10} {'Years'}")
    print("-" * 90)
    
    for acc_num, earliest, latest, tx_count, year_count, years in cibc_accounts:
        years_str = str(years).replace('{', '').replace('}', '').replace('.0', '') if years else ''
        print(f"{acc_num:<25} {str(earliest):<12} {str(latest):<12} {tx_count:>10} {years_str}")
    
    # Check source files
    print("\n" + "="*80)
    print("SOURCE FILES FOR CIBC TRANSACTIONS")
    print("="*80 + "\n")
    
    cur.execute("""
        SELECT 
            source_file,
            account_number,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as tx_count
        FROM banking_transactions
        WHERE (account_number ILIKE '%CIBC%' 
            OR account_number LIKE '%228%' 
            OR account_number LIKE '%616%'
            OR account_number LIKE '%0228362%')
        AND transaction_date < '2025-01-01'
        AND source_file IS NOT NULL
        GROUP BY source_file, account_number
        ORDER BY source_file, account_number
    """)
    
    source_files = cur.fetchall()
    
    if source_files:
        print(f"{'Source File':<50} {'Account':<15} {'Earliest':<12} {'Latest':<12} {'Count':>8}")
        print("-" * 110)
        for src_file, acc_num, earliest, latest, tx_count in source_files:
            print(f"{src_file:<50} {acc_num:<15} {str(earliest):<12} {str(latest):<12} {tx_count:>8}")
    else:
        print("⚠️  No source_file metadata found for CIBC transactions")
    
    # Check mapped_bank_account_id
    print("\n" + "="*80)
    print("MAPPED BANK ACCOUNT IDs")
    print("="*80 + "\n")
    
    cur.execute("""
        SELECT 
            mapped_bank_account_id,
            account_number,
            COUNT(*) as tx_count
        FROM banking_transactions
        WHERE (account_number ILIKE '%CIBC%' 
            OR account_number LIKE '%228%' 
            OR account_number LIKE '%616%'
            OR account_number LIKE '%0228362%')
        AND transaction_date < '2025-01-01'
        GROUP BY mapped_bank_account_id, account_number
        ORDER BY mapped_bank_account_id, account_number
    """)
    
    mapped_ids = cur.fetchall()
    
    print(f"{'Mapped ID':<12} {'Account Number':<25} {'Tx Count':>10}")
    print("-" * 50)
    for mapped_id, acc_num, tx_count in mapped_ids:
        print(f"{str(mapped_id):<12} {acc_num:<25} {tx_count:>10}")
    
    # Summary recommendation
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print("\n✅ Accounts to mark as VERIFIED and LOCKED (from downloaded banking files):")
    
    for acc_num, earliest, latest, tx_count, year_count, years in cibc_accounts:
        years_str = str(years).replace('{', '').replace('}', '').replace('.0', '') if years else ''
        print(f"   • {acc_num} ({years_str}): {tx_count:,} transactions")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
