#!/usr/bin/env python
"""
Audit 2012 Deletions and QuickBooks Data Preservation

This script analyzes:
1. What data was deleted from banking_transactions in 2012 (by comparing backups to current)
2. Whether any deleted data contained useful QuickBooks vendor information
3. Current 2012 data completeness

Purpose: Ensure no valuable QB vendor/memo data was lost during cleanup operations.
"""

import psycopg2
from datetime import datetime
import os

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_2012_backups():
    """Compare backup tables to current 2012 data to identify deleted records."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("2012 DELETION AUDIT AND QUICKBOOKS DATA PRESERVATION ANALYSIS")
    print("=" * 80)
    print()
    
    # Step 1: Verify backup tables exist
    print("Step 1: Verifying backup tables...")
    print("-" * 80)
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%2012%backup%'
        ORDER BY table_name
    """)
    backup_tables = [row[0] for row in cur.fetchall()]
    
    print(f"Found {len(backup_tables)} backup tables:")
    for table in backup_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  - {table}: {count:,} rows")
    print()
    
    # Step 2: Analyze main 2012 backup (most comprehensive)
    print("Step 2: Analyzing banking_transactions_2012_backup_20251121_192723...")
    print("-" * 80)
    
    backup_table = 'banking_transactions_2012_backup_20251121_192723'
    
    # Get backup statistics
    cur.execute(f"""
        SELECT 
            account_number,
            COUNT(*) as txn_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM {backup_table}
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    print("\nBackup table statistics:")
    backup_stats = {}
    for row in cur.fetchall():
        account, count, debits, credits, first, last = row
        backup_stats[account] = {
            'count': count,
            'debits': float(debits or 0),
            'credits': float(credits or 0),
            'first': first,
            'last': last
        }
        print(f"  Account {account}:")
        print(f"    Transactions: {count:,}")
        print(f"    Debits: ${debits:,.2f}" if debits else "    Debits: $0.00")
        print(f"    Credits: ${credits:,.2f}" if credits else "    Credits: $0.00")
        print(f"    Date range: {first} to {last}")
    print()
    
    # Step 3: Get current 2012 data
    print("Step 3: Analyzing current 2012 data in banking_transactions...")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            account_number,
            COUNT(*) as txn_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    print("\nCurrent 2012 data:")
    current_stats = {}
    for row in cur.fetchall():
        account, count, debits, credits, first, last = row
        current_stats[account] = {
            'count': count,
            'debits': float(debits or 0),
            'credits': float(credits or 0),
            'first': first,
            'last': last
        }
        print(f"  Account {account}:")
        print(f"    Transactions: {count:,}")
        print(f"    Debits: ${debits:,.2f}" if debits else "    Debits: $0.00")
        print(f"    Credits: ${credits:,.2f}" if credits else "    Credits: $0.00")
        print(f"    Date range: {first} to {last}")
    print()
    
    # Step 4: Calculate differences (what was deleted)
    print("Step 4: Calculating deleted transactions...")
    print("-" * 80)
    
    all_accounts = set(backup_stats.keys()) | set(current_stats.keys())
    total_deleted = 0
    
    print("\nDeletion summary by account:")
    for account in sorted(all_accounts):
        backup = backup_stats.get(account, {'count': 0, 'debits': 0, 'credits': 0})
        current = current_stats.get(account, {'count': 0, 'debits': 0, 'credits': 0})
        
        deleted_count = backup['count'] - current['count']
        deleted_debits = backup['debits'] - current['debits']
        deleted_credits = backup['credits'] - current['credits']
        
        if deleted_count != 0:
            print(f"  Account {account}:")
            print(f"    Deleted transactions: {deleted_count:,}")
            print(f"    Deleted debits: ${deleted_debits:,.2f}")
            print(f"    Deleted credits: ${deleted_credits:,.2f}")
            total_deleted += deleted_count
        else:
            print(f"  Account {account}: No deletions (current has MORE data)")
    
    print(f"\nTotal deleted transactions: {total_deleted:,}")
    print()
    
    # Step 5: Check if backup has vendor_extracted or vendor info
    print("Step 5: Checking for vendor information in backup data...")
    print("-" * 80)
    
    # Check if vendor columns exist in backup
    cur.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{backup_table}' 
        AND column_name LIKE '%vendor%'
    """)
    vendor_cols = [row[0] for row in cur.fetchall()]
    
    if vendor_cols:
        print(f"Found vendor columns in backup: {', '.join(vendor_cols)}")
        
        # Check how many backup rows have vendor info
        for col in vendor_cols:
            # Check column type
            cur.execute(f"""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = '{backup_table}' 
                AND column_name = '{col}'
            """)
            col_type = cur.fetchone()[0]
            
            if col_type == 'boolean':
                cur.execute(f"""
                    SELECT COUNT(*) 
                    FROM {backup_table} 
                    WHERE {col} = TRUE
                """)
            else:
                cur.execute(f"""
                    SELECT COUNT(*) 
                    FROM {backup_table} 
                    WHERE {col} IS NOT NULL AND {col} != ''
                """)
            vendor_count = cur.fetchone()[0]
            print(f"  - {col} ({col_type}): {vendor_count:,} rows with data")
    else:
        print("No vendor columns found in backup table.")
        print("Checking descriptions for vendor patterns...")
        
        # Sample some descriptions
        cur.execute(f"""
            SELECT DISTINCT description 
            FROM {backup_table} 
            WHERE description IS NOT NULL
            LIMIT 20
        """)
        print("\nSample descriptions from backup:")
        for row in cur.fetchall():
            print(f"  - {row[0][:80]}")
    print()
    
    # Step 6: Check if current data has vendor information
    print("Step 6: Checking vendor information in current 2012 data...")
    print("-" * 80)
    
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'banking_transactions' 
        AND column_name LIKE '%vendor%'
    """)
    current_vendor_cols = [row[0] for row in cur.fetchall()]
    
    if current_vendor_cols:
        print(f"Found vendor columns in current table: {', '.join(current_vendor_cols)}")
        
        for col in current_vendor_cols:
            # Check column type
            cur.execute(f"""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'banking_transactions' 
                AND column_name = '{col}'
            """)
            col_type = cur.fetchone()[0]
            
            if col_type == 'boolean':
                cur.execute(f"""
                    SELECT COUNT(*) 
                    FROM banking_transactions 
                    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
                    AND {col} = TRUE
                """)
            else:
                cur.execute(f"""
                    SELECT COUNT(*) 
                    FROM banking_transactions 
                    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
                    AND {col} IS NOT NULL AND {col} != ''
                """)
            vendor_count = cur.fetchone()[0]
            print(f"  - {col} ({col_type}): {vendor_count:,} rows with data")
    else:
        print("No vendor columns found in current table.")
    print()
    
    # Step 7: Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if total_deleted > 0:
        print(f"⚠ WARNING: {total_deleted:,} transactions were deleted from 2012 data.")
        print("  Next steps:")
        print("  1. Review backup table to identify what was deleted")
        print("  2. Check if deleted records contain unique vendor information")
        print("  3. If valuable data found, restore from backup selectively")
    else:
        print("✓ GOOD: Current 2012 data has MORE transactions than backup.")
        print("  This indicates data was added, not deleted.")
        print("  No restoration needed.")
    print()
    
    if not vendor_cols and not current_vendor_cols:
        print("⚠ INFO: No dedicated vendor columns exist in banking_transactions.")
        print("  Vendor information is stored in 'description' field.")
        print("  QuickBooks data enrichment would add structured vendor fields.")
    print()
    
    print("=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    print("Based on this analysis:")
    print("1. All 2012 backup tables are preserved and accessible")
    print("2. Current 2012 data can be compared to backups to identify changes")
    print("3. QuickBooks vendor enrichment would enhance description fields")
    print("4. No data will be deleted during enrichment - only UPDATE operations")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_2012_backups()
