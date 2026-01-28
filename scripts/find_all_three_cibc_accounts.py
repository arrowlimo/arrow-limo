#!/usr/bin/env python3
"""
Find all THREE CIBC accounts that have uploaded banking files:
- 8314462 (vehicle loans)
- 0228362 (checking account)
- 3648117 (business deposit, alias 0534)
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
    print("SEARCHING FOR ALL THREE CIBC ACCOUNTS WITH UPLOADED BANKING FILES")
    print("="*100)
    
    accounts_to_find = [
        ('8314462', 'CIBC vehicle loans'),
        ('0228362', 'CIBC checking account'),
        ('3648117', 'CIBC Business Deposit (alias 0534)'),
        ('0534', 'Possible alias for 3648117')
    ]
    
    found_accounts = []
    
    for acc_num, description in accounts_to_find:
        print(f"\n🔍 Searching for: {acc_num} ({description})")
        print("-" * 100)
        
        # Search for this account number
        cur.execute("""
            SELECT 
                account_number,
                MIN(transaction_date) as earliest,
                MAX(transaction_date) as latest,
                COUNT(*) as tx_count,
                COUNT(DISTINCT source_file) as file_count,
                array_agg(DISTINCT source_file ORDER BY source_file) FILTER (WHERE source_file IS NOT NULL) as files
            FROM banking_transactions
            WHERE account_number LIKE %s
            GROUP BY account_number
        """, (f'%{acc_num}%',))
        
        results = cur.fetchall()
        
        if results:
            for account, earliest, latest, count, fcount, files in results:
                print(f"✅ FOUND: {account}")
                print(f"   Period: {earliest} to {latest}")
                print(f"   Transactions: {count:,}")
                print(f"   Source files: {fcount}")
                if files:
                    for f in files[:10]:
                        print(f"      - {f}")
                    if len(files) > 10:
                        print(f"      ... and {len(files) - 10} more")
                
                found_accounts.append({
                    'number': account,
                    'description': description,
                    'earliest': earliest,
                    'latest': latest,
                    'count': count
                })
        else:
            print(f"❌ NOT FOUND in banking_transactions")
    
    # Search for any other CIBC-like patterns we might have missed
    print("\n\n🔍 OTHER CIBC PATTERNS IN DATABASE")
    print("-" * 100)
    
    cur.execute("""
        SELECT DISTINCT account_number, COUNT(*) as tx_count
        FROM banking_transactions
        WHERE (account_number ILIKE '%CIBC%' 
            OR account_number ~ '^[0-9]{7}$'  -- 7-digit account numbers
            OR account_number ~ '^[0-9]{4}$'  -- 4-digit like 0534
        )
        AND account_number NOT IN ('0228362')  -- Already found
        GROUP BY account_number
        ORDER BY tx_count DESC
        LIMIT 20
    """)
    
    other_accounts = cur.fetchall()
    
    if other_accounts:
        print(f"{'Account Number':<30} {'Transaction Count':>20}")
        print("-" * 55)
        for acc, count in other_accounts:
            print(f"{acc:<30} {count:>20,}")
    
    # SUMMARY
    print("\n\n" + "="*100)
    print("✅ VERIFIED CIBC ACCOUNTS TO MARK AS LOCKED")
    print("="*100)
    
    if found_accounts:
        for acc in found_accounts:
            print(f"\n🏦 {acc['number']} - {acc['description']}")
            print(f"   {acc['earliest']} to {acc['latest']}: {acc['count']:,} transactions")
    else:
        print("\n⚠️  No accounts found!")
    
    # Check Scotia too
    print("\n\n" + "="*100)
    print("✅ SCOTIA ACCOUNT TO MARK AS LOCKED")
    print("="*100)
    
    cur.execute("""
        SELECT 
            account_number,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as tx_count
        FROM banking_transactions
        WHERE account_number LIKE '%903990106011%'
        GROUP BY account_number
    """)
    
    scotia = cur.fetchone()
    if scotia:
        print(f"\n🏦 {scotia[0]} - Scotia Bank")
        print(f"   {scotia[1]} to {scotia[2]}: {scotia[3]:,} transactions")
        found_accounts.append({
            'number': scotia[0],
            'description': 'Scotia Bank',
            'earliest': scotia[1],
            'latest': scotia[2],
            'count': scotia[3]
        })
    
    print(f"\n\n📊 TOTAL ACCOUNTS TO LOCK: {len(found_accounts)}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
