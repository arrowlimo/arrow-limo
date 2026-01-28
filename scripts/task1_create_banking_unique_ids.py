#!/usr/bin/env python3
"""
Task #1: Create unique composite IDs for banking transactions
Format: account_last_4 + '-' + line_number (e.g., '8362-00001', '4462-00123')

This replaces the problematic hash system and provides human-readable unique identifiers.
"""
import psycopg2
from datetime import datetime

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*100)
    print("TASK #1: CREATE BANKING TRANSACTION UNIQUE IDS")
    print("="*100)
    
    # Step 1: Check if column exists
    print("\n1️⃣  Checking for existing transaction_uid column...")
    
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'banking_transactions' 
        AND column_name = 'transaction_uid'
    """)
    
    exists = cur.fetchone()
    
    if exists:
        print("   ⚠️  Column 'transaction_uid' already exists")
        
        # Check how many are populated
        cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE transaction_uid IS NOT NULL")
        populated = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions")
        total = cur.fetchone()[0]
        
        print(f"   📊 {populated:,} of {total:,} transactions have UIDs ({populated/total*100:.1f}%)")
        
        response = input("\n   Regenerate all UIDs? This will overwrite existing values (yes/no): ")
        if response.strip().lower() != 'yes':
            print("   ❌ Cancelled")
            cur.close()
            conn.close()
            return
    else:
        print("   ✅ Column does not exist, will create it")
    
    # Step 2: Add column if needed
    if not exists:
        print("\n2️⃣  Adding transaction_uid column...")
        
        cur.execute("""
            ALTER TABLE banking_transactions
            ADD COLUMN IF NOT EXISTS transaction_uid VARCHAR(20) UNIQUE
        """)
        conn.commit()
        print("   ✅ Column added")
    
    # Step 3: Generate UIDs per account
    print("\n3️⃣  Generating unique IDs for each account...")
    
    # Get all accounts
    cur.execute("""
        SELECT DISTINCT account_number, COUNT(*) as tx_count
        FROM banking_transactions
        WHERE account_number IS NOT NULL
        GROUP BY account_number
        ORDER BY tx_count DESC
    """)
    
    accounts = cur.fetchall()
    
    print(f"   Found {len(accounts)} unique account numbers")
    print(f"\n   {'Account':<20} {'Transactions':>15} {'Last 4':>10} {'UID Format'}")
    print("   " + "-"*70)
    
    total_updated = 0
    
    for account_num, tx_count in accounts:
        # Extract last 4 digits
        last_4 = str(account_num)[-4:] if account_num else 'UNKN'
        
        print(f"   {str(account_num):<20} {tx_count:>15,} {last_4:>10} {last_4}-XXXXX")
        
        # Update UIDs for this account
        cur.execute("""
            WITH numbered_transactions AS (
                SELECT 
                    transaction_id,
                    ROW_NUMBER() OVER (ORDER BY transaction_date, transaction_id) as row_num
                FROM banking_transactions
                WHERE account_number = %s
            )
            UPDATE banking_transactions bt
            SET transaction_uid = %s || '-' || LPAD(nt.row_num::TEXT, 5, '0')
            FROM numbered_transactions nt
            WHERE bt.transaction_id = nt.transaction_id
        """, (account_num, last_4))
        
        total_updated += cur.rowcount
        
        if (accounts.index((account_num, tx_count)) + 1) % 10 == 0:
            conn.commit()  # Commit every 10 accounts
    
    conn.commit()
    
    print(f"\n   ✅ Generated {total_updated:,} unique IDs")
    
    # Step 4: Verify uniqueness
    print("\n4️⃣  Verifying uniqueness...")
    
    cur.execute("""
        SELECT transaction_uid, COUNT(*)
        FROM banking_transactions
        WHERE transaction_uid IS NOT NULL
        GROUP BY transaction_uid
        HAVING COUNT(*) > 1
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        print(f"   ❌ Found {len(duplicates)} duplicate UIDs!")
        for uid, count in duplicates[:10]:
            print(f"      {uid}: {count} occurrences")
    else:
        print("   ✅ All UIDs are unique")
    
    # Step 5: Show samples
    print("\n5️⃣  Sample UIDs generated:")
    print(f"\n   {'UID':<15} {'Account':<20} {'Date':<12} {'Vendor':<30}")
    print("   " + "-"*85)
    
    cur.execute("""
        SELECT transaction_uid, account_number, transaction_date, vendor_extracted
        FROM banking_transactions
        WHERE transaction_uid IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    for uid, acc, date, vendor in samples:
        vendor_str = (vendor or '')[:28]
        print(f"   {uid:<15} {str(acc):<20} {str(date):<12} {vendor_str:<30}")
    
    # Step 6: Create index
    print("\n6️⃣  Creating index on transaction_uid...")
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_banking_transactions_uid 
        ON banking_transactions(transaction_uid)
    """)
    conn.commit()
    print("   ✅ Index created")
    
    # Summary
    print("\n" + "="*100)
    print("✅ TASK #1 COMPLETE")
    print("="*100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(transaction_uid) as with_uid,
            COUNT(DISTINCT transaction_uid) as unique_uids
        FROM banking_transactions
    """)
    
    total, with_uid, unique_uids = cur.fetchone()
    
    print(f"\n📊 Statistics:")
    print(f"   Total transactions: {total:,}")
    print(f"   With UID: {with_uid:,} ({with_uid/total*100:.1f}%)")
    print(f"   Unique UIDs: {unique_uids:,}")
    print(f"   Duplicates: {with_uid - unique_uids}")
    
    print(f"\n✅ Banking transactions now have unique composite IDs!")
    print(f"   Format: account_last_4 + '-' + line_number")
    print(f"   Example: 8362-00001, 4462-00123, 8117-02456")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
