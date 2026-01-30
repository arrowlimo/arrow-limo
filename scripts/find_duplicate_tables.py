#!/usr/bin/env python3
"""
Find duplicate/redundant tables with different names.
Compares table structures and purposes.
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def get_table_structure(conn, table_name):
    """Get normalized table structure."""
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cur.fetchall()


def get_table_info(conn, table_name):
    """Get detailed table information."""
    cur = conn.cursor()
    
    # Row count
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]
    
    # Sample data
    cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
    sample = cur.fetchone()
    
    return {
        'row_count': row_count,
        'has_data': row_count > 0,
        'sample': sample
    }


def compare_tables(conn, table1, table2):
    """Compare two tables for similarity."""
    struct1 = get_table_structure(conn, table1)
    struct2 = get_table_structure(conn, table2)
    
    cols1 = set(c[0] for c in struct1)
    cols2 = set(c[0] for c in struct2)
    
    common_cols = cols1 & cols2
    similarity = len(common_cols) / max(len(cols1), len(cols2)) * 100
    
    return {
        'similarity': similarity,
        'common_columns': common_cols,
        'unique_to_1': cols1 - cols2,
        'unique_to_2': cols2 - cols1
    }


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Get all account-related tables
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND tablename LIKE '%account%'
        ORDER BY tablename
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    
    print("="*80)
    print("POTENTIAL DUPLICATE TABLES ANALYSIS")
    print("="*80)
    
    # Group tables by similar purpose
    groups = {
        'Bank Accounts': ['bank_accounts', 'cibc_accounts', 'banking_inter_account_transfers'],
        'Chart of Accounts': ['chart_of_accounts', 'account_categories', 'category_to_account_map'],
        'Accounting Entries': ['accounting_entries', 'accounting_records'],
        'Account Mapping': ['account_number_aliases', 'epson_pay_accounts_map'],
        'Vendor Accounts': ['vendor_accounts', 'vendor_account_ledger'],
        'Misc': ['david_account_tracking', 'deferred_wage_accounts', 'owner_equity_accounts', 
                 'etransfer_accounting_assessment', 'accounting_periods']
    }
    
    for group_name, group_tables in groups.items():
        existing = [t for t in group_tables if t in tables]
        if len(existing) > 1:
            print(f"\n{group_name}:")
            for table in existing:
                info = get_table_info(conn, table)
                print(f"  {table:45} {info['row_count']:6} rows")
            
            # Compare first two tables in group
            if len(existing) >= 2:
                comparison = compare_tables(conn, existing[0], existing[1])
                print(f"    Similarity: {comparison['similarity']:.1f}%")
                if comparison['similarity'] > 50:
                    print(f"    ⚠️  HIGH SIMILARITY - may be duplicates")
                    print(f"    Common columns: {', '.join(sorted(list(comparison['common_columns'])[:5]))}")
    
    # Check for backup tables
    print(f"\n{'='*80}")
    print("BACKUP/TEMPORARY TABLES:")
    print("="*80)
    cur.execute("""
        SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND (tablename LIKE '%backup%' 
            OR tablename LIKE '%temp%' 
            OR tablename LIKE '%old%'
            OR tablename LIKE '%_20%')
        ORDER BY tablename
    """)
    
    backups = cur.fetchall()
    if backups:
        for table, size in backups:
            info = get_table_info(conn, table)
            print(f"  {table:50} {info['row_count']:8} rows  {size}")
    else:
        print("  ✓ No backup tables found")
    
    # Find exact duplicates (same column structure)
    print(f"\n{'='*80}")
    print("EXACT STRUCTURAL DUPLICATES:")
    print("="*80)
    
    structures = {}
    for table in tables:
        struct = tuple(get_table_structure(conn, table))
        if struct in structures:
            structures[struct].append(table)
        else:
            structures[struct] = [table]
    
    found_duplicates = False
    for struct, table_list in structures.items():
        if len(table_list) > 1:
            found_duplicates = True
            print(f"\n  Same structure:")
            for table in table_list:
                info = get_table_info(conn, table)
                print(f"    {table:40} {info['row_count']:6} rows")
    
    if not found_duplicates:
        print("  ✓ No exact structural duplicates found")
    
    conn.close()


if __name__ == '__main__':
    main()
