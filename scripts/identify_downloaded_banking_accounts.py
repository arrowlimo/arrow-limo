#!/usr/bin/env python3
"""
Identify which banking accounts came from DIRECT downloads (PDFs, CSVs) 
vs QuickBooks/General Ledger imports
"""
import psycopg2

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*100)
    print("BANKING ACCOUNTS: DIRECT DOWNLOADS vs QUICKBOOKS IMPORTS")
    print("="*100)
    
    # Identify accounts by source
    print("\n1️⃣  CIBC ACCOUNTS FROM PDF/CSV DOWNLOADS (NOT QuickBooks)")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            account_number,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as tx_count,
            array_agg(DISTINCT source_file ORDER BY source_file) FILTER (WHERE source_file IS NOT NULL) as files
        FROM banking_transactions
        WHERE (account_number LIKE '%228%' OR account_number LIKE '%616%' OR account_number ILIKE '%CIBC%')
        AND source_file IS NOT NULL
        AND source_file NOT ILIKE '%general_ledger%'
        AND source_file NOT ILIKE '%unified%'
        AND source_file NOT ILIKE '%quickbooks%'
        AND source_file NOT ILIKE '%GL%'
        AND transaction_date < '2025-01-01'
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    direct_cibc = cur.fetchall()
    
    if direct_cibc:
        for acc, earliest, latest, count, files in direct_cibc:
            print(f"\n📥 {acc}")
            print(f"   Dates: {earliest} to {latest}")
            print(f"   Transactions: {count:,}")
            if files:
                print(f"   Source files ({len(files)}):")
                for f in files[:5]:  # Show first 5
                    print(f"      - {f}")
                if len(files) > 5:
                    print(f"      ... and {len(files) - 5} more files")
    else:
        print("\n❌ No CIBC accounts found from direct downloads")
    
    # Scotia accounts
    print("\n\n2️⃣  SCOTIA ACCOUNTS FROM PDF/CSV DOWNLOADS (NOT QuickBooks)")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            account_number,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as tx_count,
            array_agg(DISTINCT source_file ORDER BY source_file) FILTER (WHERE source_file IS NOT NULL) as files
        FROM banking_transactions
        WHERE account_number ILIKE '%scotia%' 
            OR account_number LIKE '%903990%'
            OR account_number LIKE '%106011%'
        AND source_file IS NOT NULL
        AND source_file NOT ILIKE '%general_ledger%'
        AND source_file NOT ILIKE '%unified%'
        AND source_file NOT ILIKE '%quickbooks%'
        AND source_file NOT ILIKE '%GL%'
        AND transaction_date < '2025-01-01'
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    direct_scotia = cur.fetchall()
    
    if direct_scotia:
        for acc, earliest, latest, count, files in direct_scotia:
            print(f"\n📥 {acc}")
            print(f"   Dates: {earliest} to {latest}")
            print(f"   Transactions: {count:,}")
            if files:
                print(f"   Source files ({len(files)}):")
                for f in files[:5]:
                    print(f"      - {f}")
                if len(files) > 5:
                    print(f"      ... and {len(files) - 5} more files")
    else:
        print("\n❌ No Scotia accounts found from direct downloads")
    
    # QuickBooks/GL imports (for comparison)
    print("\n\n3️⃣  ACCOUNTS FROM QUICKBOOKS/GENERAL LEDGER (NOT direct downloads - DO NOT LOCK)")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            account_number,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as tx_count
        FROM banking_transactions
        WHERE (source_file ILIKE '%general_ledger%'
            OR source_file ILIKE '%unified%'
            OR source_file ILIKE '%GL%'
            OR source_file ILIKE '%quickbooks%')
        AND transaction_date < '2025-01-01'
        GROUP BY account_number
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    
    gl_accounts = cur.fetchall()
    
    if gl_accounts:
        print(f"\n{'Account':<30} {'Earliest':<12} {'Latest':<12} {'Count':>10}")
        print("-" * 70)
        for acc, earliest, latest, count in gl_accounts:
            print(f"{acc:<30} {str(earliest):<12} {str(latest):<12} {count:>10,}")
    
    # SUMMARY
    print("\n\n" + "="*100)
    print("✅ ACCOUNTS TO MARK AS VERIFIED & LOCKED (from direct bank downloads)")
    print("="*100)
    
    all_verified = []
    
    if direct_cibc:
        print("\n🏦 CIBC Accounts:")
        for acc, earliest, latest, count, files in direct_cibc:
            print(f"   • {acc} ({earliest} to {latest}): {count:,} transactions")
            all_verified.append(acc)
    
    if direct_scotia:
        print("\n🏦 Scotia Accounts:")
        for acc, earliest, latest, count, files in direct_scotia:
            print(f"   • {acc} ({earliest} to {latest}): {count:,} transactions")
            all_verified.append(acc)
    
    print(f"\n📊 Total verified accounts: {len(all_verified)}")
    
    if all_verified:
        print("\n💡 SQL to mark these as verified:")
        print(f"""
UPDATE banking_transactions
SET verified = TRUE, locked = TRUE
WHERE account_number IN ({', '.join(f"'{a}'" for a in all_verified)})
AND source_file NOT ILIKE '%general_ledger%'
AND source_file NOT ILIKE '%unified%'
AND source_file NOT ILIKE '%quickbooks%';
""")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
