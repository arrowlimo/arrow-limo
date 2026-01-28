#!/usr/bin/env python3
"""
Find duplicate/similar accounting tables for deduplication and cleanup.
Identifies tables that might be redundant after creating comprehensive chart_of_accounts.
"""

import psycopg2
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def analyze_accounting_tables():
    """Find all accounting-related tables and analyze for duplicates."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("ACCOUNTING TABLE DEDUPLICATION ANALYSIS")
    print("="*100)
    
    # Find all potentially duplicate tables
    cur.execute("""
        SELECT 
            table_name,
            (SELECT COUNT(*) FROM information_schema.columns 
             WHERE table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        AND (
            table_name LIKE '%account%' OR
            table_name LIKE '%chart%' OR
            table_name LIKE '%ledger%' OR
            table_name LIKE '%journal%' OR
            table_name LIKE '%category%' OR
            table_name LIKE '%receipt_cat%' OR
            table_name LIKE '%expense_cat%'
        )
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    
    print(f"\nFound {len(tables)} accounting-related tables:\n")
    print(f"{'Table Name':50} {'Columns':>10} {'Row Count':>15}")
    print("-" * 100)
    
    table_details = {}
    
    for table_name, col_count in tables:
        # Get row count
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cur.fetchone()[0]
        except:
            row_count = 0
        
        print(f"{table_name:50} {col_count:10} {row_count:15,}")
        table_details[table_name] = {'columns': col_count, 'rows': row_count}
    
    # Analyze specific table groups
    print("\n" + "="*100)
    print("DETAILED ANALYSIS BY CATEGORY")
    print("="*100)
    
    # Chart of Accounts tables
    chart_tables = [t for t in table_details.keys() if 'chart' in t or 'account' in t]
    if chart_tables:
        print("\n📊 CHART OF ACCOUNTS TABLES:")
        analyze_table_group(cur, chart_tables, table_details)
    
    # Ledger tables
    ledger_tables = [t for t in table_details.keys() if 'ledger' in t]
    if ledger_tables:
        print("\n📒 LEDGER TABLES:")
        analyze_table_group(cur, ledger_tables, table_details)
    
    # Journal tables
    journal_tables = [t for t in table_details.keys() if 'journal' in t]
    if journal_tables:
        print("\n📓 JOURNAL TABLES:")
        analyze_table_group(cur, journal_tables, table_details)
    
    # Category tables
    category_tables = [t for t in table_details.keys() if 'category' in t or 'categ' in t]
    if category_tables:
        print("\n🏷️  CATEGORY TABLES:")
        analyze_table_group(cur, category_tables, table_details)
    
    # Generate recommendations
    print("\n" + "="*100)
    print("DEDUPLICATION RECOMMENDATIONS")
    print("="*100)
    
    recommendations = generate_recommendations(cur, table_details)
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec['action']}")
        print(f"   Table: {rec['table']}")
        print(f"   Reason: {rec['reason']}")
        if rec.get('merge_to'):
            print(f"   Merge to: {rec['merge_to']}")
        if rec.get('rows') == 0:
            print(f"   ✅ SAFE TO DROP (empty table)")
        elif rec.get('rows', 0) > 0:
            print(f"   ⚠️  Contains {rec['rows']:,} rows - verify before dropping")
    
    conn.close()

def analyze_table_group(cur, tables, table_details):
    """Analyze a group of related tables."""
    for table in sorted(tables):
        details = table_details[table]
        print(f"\n  • {table} ({details['columns']} columns, {details['rows']:,} rows)")
        
        # Get column names
        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
            LIMIT 10
        """)
        cols = cur.fetchall()
        
        print(f"    Columns: {', '.join([c[0] for c in cols[:5]])}")
        if len(cols) > 5:
            print(f"             ... and {len(cols)-5} more")

def generate_recommendations(cur, table_details):
    """Generate deduplication recommendations."""
    recommendations = []
    
    # Check for empty tables
    for table, details in table_details.items():
        if details['rows'] == 0:
            recommendations.append({
                'action': 'DROP',
                'table': table,
                'reason': 'Empty table with no data',
                'rows': 0
            })
    
    # Check for staging tables with data
    staging_tables = [t for t in table_details.keys() if 'staging' in t or 'temp' in t]
    for table in staging_tables:
        if table_details[table]['rows'] > 0:
            recommendations.append({
                'action': 'REVIEW & MERGE',
                'table': table,
                'reason': 'Staging table with data that may need to be promoted',
                'rows': table_details[table]['rows']
            })
    
    # Check for duplicate account tables
    account_tables = [t for t in table_details.keys() 
                     if 'account' in t and t != 'chart_of_accounts']
    for table in account_tables:
        if table_details[table]['rows'] > 0:
            # Check if columns overlap with chart_of_accounts
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                AND column_name IN (
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'chart_of_accounts'
                )
            """)
            common_cols = len(cur.fetchall())
            
            if common_cols > 2:
                recommendations.append({
                    'action': 'MERGE TO chart_of_accounts',
                    'table': table,
                    'reason': f'Has {common_cols} columns in common with chart_of_accounts',
                    'merge_to': 'chart_of_accounts',
                    'rows': table_details[table]['rows']
                })
    
    # Check for old category tables
    if 'receipt_categories' in table_details and table_details['receipt_categories']['rows'] == 0:
        recommendations.append({
            'action': 'CREATE & POPULATE',
            'table': 'receipt_categories',
            'reason': 'Needed for receipt categorization system (currently empty)',
            'rows': 0
        })
    
    return recommendations

if __name__ == '__main__':
    analyze_accounting_tables()
