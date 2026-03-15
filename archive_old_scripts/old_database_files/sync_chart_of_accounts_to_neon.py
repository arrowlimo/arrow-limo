#!/usr/bin/env python3
"""
Sync Chart of Accounts from Local to Neon
Adds missing accounts to Neon database
"""

import psycopg2

# Database credentials
LOCAL_HOST = "localhost"
LOCAL_DB = "almsdata"
LOCAL_USER = "postgres"
LOCAL_PASSWORD = "ArrowLimousine"

NEON_HOST = "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"
NEON_DB = "neondb"
NEON_USER = "neondb_owner"
NEON_PASSWORD = "npg_rlL0yK9pvfCW"


def main():
    print("=" * 100)
    print("SYNC CHART OF ACCOUNTS: Local → Neon")
    print("=" * 100)
    
    # Connect to local
    print("\n1. Connecting to LOCAL database...")
    local_conn = psycopg2.connect(
        host=LOCAL_HOST, database=LOCAL_DB,
        user=LOCAL_USER, password=LOCAL_PASSWORD
    )
    print(f"   ✓ Connected to {LOCAL_DB}")
    
    # Connect to Neon
    print("\n2. Connecting to NEON database...")
    neon_conn = psycopg2.connect(
        host=NEON_HOST, database=NEON_DB,
        user=NEON_USER, password=NEON_PASSWORD,
        sslmode='require', connect_timeout=10
    )
    print(f"   ✓ Connected to {NEON_DB}")
    
    # Get account 2910 from local
    print("\n3. Fetching account 2910 from local...")
    local_cur = local_conn.cursor()
    local_cur.execute("""
        SELECT account_code, account_name, account_type, is_active,
               parent_account, description, normal_balance, 
               is_header_account, account_level
        FROM chart_of_accounts
        WHERE account_code = '2910'
    """)
    account = local_cur.fetchone()
    
    if not account:
        print("   ✗ Account 2910 not found in local database!")
        return
    
    print(f"   ✓ Found: {account[0]} - {account[1]}")
    
    # Insert into Neon
    print("\n4. Adding account 2910 to Neon...")
    neon_cur = neon_conn.cursor()
    
    try:
        neon_cur.execute("""
            INSERT INTO chart_of_accounts (
                account_code, account_name, account_type, is_active,
                parent_account, description, normal_balance,
                is_header_account, account_level
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (account_code) DO UPDATE SET
                account_name = EXCLUDED.account_name,
                account_type = EXCLUDED.account_type,
                is_active = EXCLUDED.is_active,
                parent_account = EXCLUDED.parent_account,
                description = EXCLUDED.description,
                normal_balance = EXCLUDED.normal_balance,
                is_header_account = EXCLUDED.is_header_account,
                account_level = EXCLUDED.account_level
            RETURNING account_code, account_name
        """, account)
        
        result = neon_cur.fetchone()
        neon_conn.commit()
        
        print(f"   ✓ Successfully added: {result[0]} - {result[1]}")
        
    except Exception as e:
        neon_conn.rollback()
        print(f"   ✗ Error: {e}")
        return
    finally:
        neon_cur.close()
        local_cur.close()
    
    # Verify
    print("\n5. Verifying sync...")
    neon_cur = neon_conn.cursor()
    neon_cur.execute("""
        SELECT account_code, account_name, account_type, is_active
        FROM chart_of_accounts
        WHERE account_code = '2910'
    """)
    verify = neon_cur.fetchone()
    neon_cur.close()
    
    if verify:
        print(f"   ✓ Verified in Neon: {verify[0]} - {verify[1]} ({verify[2]}, Active={verify[3]})")
    else:
        print("   ✗ Verification failed!")
    
    # Close connections
    local_conn.close()
    neon_conn.close()
    
    print("\n" + "=" * 100)
    print("SYNC COMPLETE ✓")
    print("=" * 100)
    print("\nThe 2910 - ShareHolder Loan account is now available in both databases!")
    print("You can now use it in your cloud-based receipt entry system.")


if __name__ == "__main__":
    main()
