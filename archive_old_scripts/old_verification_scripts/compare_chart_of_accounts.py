#!/usr/bin/env python3
"""
Compare Chart of Accounts between Local and Neon databases
Shows differences in accounts, focusing on recently added 2910
"""

import psycopg2
from pathlib import Path
import os

# Database credentials
LOCAL_HOST = "localhost"
LOCAL_DB = "almsdata"
LOCAL_USER = "postgres"
LOCAL_PASSWORD = "ArrowLimousine"

NEON_HOST = "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"
NEON_DB = "neondb"
NEON_USER = "neondb_owner"
NEON_PASSWORD = "npg_rlL0yK9pvfCW"


def get_chart_of_accounts(conn, db_name):
    """Fetch all chart of accounts from a database"""
    cur = conn.cursor()
    cur.execute("""
        SELECT account_code, account_name, account_type, is_active, 
               parent_account, description
        FROM chart_of_accounts
        ORDER BY account_code
    """)
    rows = cur.fetchall()
    cur.close()
    
    # Convert to dict for easy comparison
    accounts = {}
    for row in rows:
        accounts[row[0]] = {
            'name': row[1],
            'type': row[2],
            'active': row[3],
            'parent': row[4],
            'description': row[5]
        }
    return accounts


def main():
    print("=" * 100)
    print("CHART OF ACCOUNTS COMPARISON: Local vs Neon")
    print("=" * 100)
    
    # Connect to local database
    print("\n1. Connecting to LOCAL database...")
    try:
        local_conn = psycopg2.connect(
            host=LOCAL_HOST,
            database=LOCAL_DB,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD
        )
        print(f"   ✓ Connected to {LOCAL_DB} on {LOCAL_HOST}")
    except Exception as e:
        print(f"   ✗ Failed to connect to local database: {e}")
        return
    
    # Connect to Neon database
    print("\n2. Connecting to NEON database...")
    try:
        neon_conn = psycopg2.connect(
            host=NEON_HOST,
            database=NEON_DB,
            user=NEON_USER,
            password=NEON_PASSWORD,
            sslmode='require',
            connect_timeout=10
        )
        print(f"   ✓ Connected to {NEON_DB} on Neon")
    except Exception as e:
        print(f"   ✗ Failed to connect to Neon database: {e}")
        local_conn.close()
        return
    
    # Get chart of accounts from both databases
    print("\n3. Fetching chart of accounts...")
    local_accounts = get_chart_of_accounts(local_conn, "local")
    neon_accounts = get_chart_of_accounts(neon_conn, "neon")
    
    print(f"   Local accounts: {len(local_accounts)}")
    print(f"   Neon accounts:  {len(neon_accounts)}")
    
    # Find differences
    local_codes = set(local_accounts.keys())
    neon_codes = set(neon_accounts.keys())
    
    only_local = local_codes - neon_codes
    only_neon = neon_codes - local_codes
    common = local_codes & neon_codes
    
    # Report differences
    print("\n" + "=" * 100)
    print("ACCOUNTS ONLY IN LOCAL (NOT IN NEON)")
    print("=" * 100)
    if only_local:
        print(f"\n{'Code':<10} {'Name':<40} {'Type':<15} {'Active'}")
        print("-" * 100)
        for code in sorted(only_local):
            acc = local_accounts[code]
            print(f"{code:<10} {acc['name']:<40} {acc['type']:<15} {acc['active']}")
        
        # Highlight 2910 if it's there
        if '2910' in only_local:
            print("\n⚠️  IMPORTANT: Account 2910 (ShareHolder Loan) exists in LOCAL but NOT in NEON!")
    else:
        print("\n✓ No accounts found only in local")
    
    print("\n" + "=" * 100)
    print("ACCOUNTS ONLY IN NEON (NOT IN LOCAL)")
    print("=" * 100)
    if only_neon:
        print(f"\n{'Code':<10} {'Name':<40} {'Type':<15} {'Active'}")
        print("-" * 100)
        for code in sorted(only_neon):
            acc = neon_accounts[code]
            print(f"{code:<10} {acc['name']:<40} {acc['type']:<15} {acc['active']}")
    else:
        print("\n✓ No accounts found only in Neon")
    
    # Check for mismatches in common accounts
    print("\n" + "=" * 100)
    print("COMMON ACCOUNTS WITH DIFFERENT DETAILS")
    print("=" * 100)
    mismatches = []
    for code in common:
        local_acc = local_accounts[code]
        neon_acc = neon_accounts[code]
        
        if (local_acc['name'] != neon_acc['name'] or 
            local_acc['type'] != neon_acc['type'] or
            local_acc['active'] != neon_acc['active']):
            mismatches.append((code, local_acc, neon_acc))
    
    if mismatches:
        for code, local_acc, neon_acc in mismatches:
            print(f"\nAccount {code}:")
            print(f"  LOCAL: {local_acc['name']} | {local_acc['type']} | Active={local_acc['active']}")
            print(f"  NEON:  {neon_acc['name']} | {neon_acc['type']} | Active={neon_acc['active']}")
    else:
        print("\n✓ All common accounts match")
    
    # Summary and recommendations
    print("\n" + "=" * 100)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 100)
    print(f"\n📊 Statistics:")
    print(f"   Total accounts in LOCAL: {len(local_accounts)}")
    print(f"   Total accounts in NEON:  {len(neon_accounts)}")
    print(f"   Common accounts:         {len(common)}")
    print(f"   Only in LOCAL:           {len(only_local)}")
    print(f"   Only in NEON:            {len(only_neon)}")
    print(f"   Mismatched details:      {len(mismatches)}")
    
    if only_local:
        print(f"\n⚠️  ACTION REQUIRED:")
        print(f"   To sync these {len(only_local)} accounts to Neon, run:")
        print(f"   python sync_chart_of_accounts_to_neon.py")
        
        if '2910' in only_local:
            print(f"\n   ⭐ This includes the newly created 2910 - ShareHolder Loan account")
    
    # Close connections
    local_conn.close()
    neon_conn.close()
    
    print("\n" + "=" * 100)
    print("COMPARISON COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
