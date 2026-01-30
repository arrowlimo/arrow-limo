#!/usr/bin/env python3
"""
Analyze accounting-related tables in ALMS database.
Determine which tables are used, needed, or obsolete.
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Tables to analyze
TABLES_TO_ANALYZE = [
    'accounting_entries',
    'accounting_records',
    'accounting_periods',
    'accounting_system_verification',
    'accounting_books_final_verification',
    'chart_of_accounts',
    'account_categories',
    'account_number_aliases',
    'category_to_account_map',
    'bank_accounts',
    'vendor_accounts',
    'vendor_account_ledger',
    'qb_accounts',
    'qb_accounts_staging'
]


def analyze_table(conn, table_name):
    """Analyze a single table's structure and usage."""
    cur = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"TABLE: {table_name}")
    print(f"{'='*80}")
    
    # Get row count
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
        print(f"Row Count: {row_count:,}")
    except Exception as e:
        print(f"❌ Error accessing table: {e}")
        return
    
    # Get column info
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    columns = cur.fetchall()
    print(f"\nColumns ({len(columns)}):")
    for col in columns:
        nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
        default = f" DEFAULT {col[3]}" if col[3] else ""
        print(f"  {col[0]:30} {col[1]:20} {nullable}{default}")
    
    # Check for foreign keys
    cur.execute(f"""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = %s
    """, (table_name,))
    
    fkeys = cur.fetchall()
    if fkeys:
        print(f"\nForeign Keys:")
        for fk in fkeys:
            print(f"  {fk[1]} → {fk[2]}.{fk[3]}")
    
    # Check what references this table
    cur.execute(f"""
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = %s
    """, (table_name,))
    
    refs = cur.fetchall()
    if refs:
        print(f"\nReferenced By:")
        for ref in refs:
            print(f"  {ref[0]}.{ref[1]}")
    
    # Sample data
    if row_count > 0 and row_count < 1000:
        print(f"\nSample Data (first 3 rows):")
        col_names = [col[0] for col in columns[:5]]  # First 5 columns
        cur.execute(f"SELECT {', '.join(col_names)} FROM {table_name} LIMIT 3")
        rows = cur.fetchall()
        for row in rows:
            print(f"  {row}")
    
    # Date range if applicable
    date_cols = ['transaction_date', 'entry_date', 'date', 'created_at', 'imported_at']
    for date_col in date_cols:
        if any(c[0] == date_col for c in columns):
            cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table_name} WHERE {date_col} IS NOT NULL")
            dates = cur.fetchone()
            if dates[0]:
                print(f"\nDate Range ({date_col}): {dates[0]} to {dates[1]}")
            break


def analyze_usage_patterns(conn):
    """Analyze how tables are used together."""
    cur = conn.cursor()
    
    print(f"\n\n{'='*80}")
    print("USAGE ANALYSIS")
    print(f"{'='*80}")
    
    # Check accounting_entries usage
    cur.execute("""
        SELECT source_type, COUNT(*), MIN(entry_date), MAX(entry_date)
        FROM accounting_entries
        GROUP BY source_type
    """)
    
    print("\nAccounting Entries by Source Type:")
    for row in cur.fetchall():
        print(f"  {row[0] or 'NULL':30} {row[1]:5} records  {row[2]} to {row[3]}")
    
    # Check chart_of_accounts usage
    cur.execute("""
        SELECT account_type, COUNT(*), SUM(current_balance)
        FROM chart_of_accounts
        WHERE is_active = true
        GROUP BY account_type
        ORDER BY COUNT(*) DESC
    """)
    
    print("\nChart of Accounts by Type:")
    for row in cur.fetchall():
        balance = row[2] or 0
        print(f"  {row[0]:30} {row[1]:3} accounts  Balance: ${balance:,.2f}")


def recommend_action(conn):
    """Recommend which tables to keep/delete."""
    cur = conn.cursor()
    
    print(f"\n\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")
    
    recommendations = {
        'KEEP': [],
        'REVIEW': [],
        'DELETE': []
    }
    
    for table in TABLES_TO_ANALYZE:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            # Backup tables
            if 'backup' in table.lower():
                recommendations['DELETE'].append(f"{table} - Backup table ({count} rows)")
            
            # Staging tables
            elif 'staging' in table.lower():
                recommendations['REVIEW'].append(f"{table} - Staging table ({count} rows) - check if import complete")
            
            # Empty tables
            elif count == 0:
                recommendations['DELETE'].append(f"{table} - Empty table")
            
            # Core accounting tables
            elif table in ['chart_of_accounts', 'accounting_entries', 'bank_accounts']:
                recommendations['KEEP'].append(f"{table} - Core accounting ({count} rows)")
            
            # Verification tables
            elif 'verification' in table.lower():
                recommendations['DELETE'].append(f"{table} - One-time verification ({count} rows)")
            
            # QuickBooks tables
            elif table.startswith('qb_'):
                recommendations['REVIEW'].append(f"{table} - QuickBooks data ({count} rows) - assess if needed")
            
            else:
                recommendations['REVIEW'].append(f"{table} - ({count} rows) - manual review needed")
        
        except Exception as e:
            recommendations['REVIEW'].append(f"{table} - Error: {e}")
    
    print("\n✅ KEEP (Core tables for new system):")
    for item in recommendations['KEEP']:
        print(f"  {item}")
    
    print("\n⚠️ REVIEW (Assess if needed):")
    for item in recommendations['REVIEW']:
        print(f"  {item}")
    
    print("\n❌ DELETE (Not needed in new system):")
    for item in recommendations['DELETE']:
        print(f"  {item}")


def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        for table in TABLES_TO_ANALYZE:
            analyze_table(conn, table)
        
        analyze_usage_patterns(conn)
        recommend_action(conn)
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
