#!/usr/bin/env python3
"""
Analyze gl_transactions_staging table (50,947 rows).

Purpose:
- Determine date range and data completeness
- Compare to unified_general_ledger for duplicates
- Check data quality (amounts, accounts, descriptions)
- Recommend promotion vs archive strategy
"""

import psycopg2
from datetime import datetime
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("GL_TRANSACTIONS_STAGING ANALYSIS - 50K Rows")
    print("=" * 80)
    
    # 1. Basic statistics
    print("\n1. BASIC STATISTICS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT transaction_date) as unique_dates,
            MIN(transaction_date) as min_date,
            MAX(transaction_date) as max_date,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
            SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits,
            SUM(debit_amount) - SUM(credit_amount) as net_balance
        FROM gl_transactions_staging
    """)
    
    stats = cur.fetchone()
    print(f"Total rows: {stats[0]:,}")
    print(f"Unique dates: {stats[1]:,}")
    print(f"Date range: {stats[2]} to {stats[3]}")
    print(f"Total debits: ${stats[4]:,.2f}")
    print(f"Total credits: ${stats[5]:,.2f}")
    print(f"Net balance: ${stats[6]:,.2f}")
    
    # 2. Table structure
    print("\n2. TABLE STRUCTURE")
    print("-" * 80)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'gl_transactions_staging'
        ORDER BY ordinal_position
    """)
    
    print("Columns:")
    for col_name, col_type in cur.fetchall():
        print(f"  {col_name:30} {col_type}")
    
    # 3. Compare with unified_general_ledger
    print("\n3. COMPARISON WITH UNIFIED_GENERAL_LEDGER")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as rows,
            MIN(transaction_date) as min_date,
            MAX(transaction_date) as max_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM unified_general_ledger
    """)
    
    ugl_stats = cur.fetchone()
    print(f"\nunified_general_ledger:")
    print(f"  Rows: {ugl_stats[0]:,}")
    print(f"  Date range: {ugl_stats[1]} to {ugl_stats[2]}")
    print(f"  Total debits: ${ugl_stats[3]:,.2f}")
    print(f"  Total credits: ${ugl_stats[4]:,.2f}")
    
    # Check date overlap
    print(f"\nDate overlap analysis:")
    print(f"  Staging: {stats[2]} to {stats[3]}")
    print(f"  UGL:     {ugl_stats[1]} to {ugl_stats[2]}")
    
    if stats[2] >= ugl_stats[1] and stats[3] <= ugl_stats[2]:
        print("  Status: Staging dates WITHIN UGL range (likely duplicates)")
    elif stats[3] > ugl_stats[2]:
        print(f"  Status: Staging has NEWER data (after {ugl_stats[2]})")
    elif stats[2] < ugl_stats[1]:
        print(f"  Status: Staging has OLDER data (before {ugl_stats[1]})")
    
    # 4. Data quality checks
    print("\n4. DATA QUALITY CHECKS")
    print("-" * 80)
    
    # Check for NULL values
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE transaction_date IS NULL) as null_dates,
            COUNT(*) FILTER (WHERE debit_amount IS NULL) as null_debits,
            COUNT(*) FILTER (WHERE credit_amount IS NULL) as null_credits,
            COUNT(*) FILTER (WHERE account_name IS NULL) as null_accounts,
            COUNT(*) FILTER (WHERE description IS NULL) as null_descriptions
        FROM gl_transactions_staging
    """)
    
    null_stats = cur.fetchone()
    print(f"NULL value counts:")
    print(f"  Dates: {null_stats[0]:,}")
    print(f"  Debits: {null_stats[1]:,}")
    print(f"  Credits: {null_stats[2]:,}")
    print(f"  Accounts: {null_stats[3]:,}")
    print(f"  Descriptions: {null_stats[4]:,}")
    
    # Check for zero-amount rows
    cur.execute("""
        SELECT COUNT(*) 
        FROM gl_transactions_staging 
        WHERE (debit_amount = 0 OR debit_amount IS NULL) 
          AND (credit_amount = 0 OR credit_amount IS NULL)
    """)
    
    zero_count = cur.fetchone()[0]
    print(f"\nZero-amount rows: {zero_count:,} ({zero_count/stats[0]*100:.1f}%)")
    
    # 5. Account distribution
    print("\n5. ACCOUNT DISTRIBUTION (Top 10)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            account_name,
            COUNT(*) as txn_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM gl_transactions_staging
        WHERE account_name IS NOT NULL
        GROUP BY account_name
        ORDER BY txn_count DESC
        LIMIT 10
    """)
    
    print(f"{'Account':<40} {'Txns':>8} {'Debits':>15} {'Credits':>15}")
    print("-" * 80)
    for account, count, debits, credits in cur.fetchall():
        print(f"{account:<40} {count:>8,} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f}")
    
    # 6. Yearly breakdown
    print("\n6. YEARLY BREAKDOWN")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as transactions,
            SUM(debit_amount) as debits,
            SUM(credit_amount) as credits
        FROM gl_transactions_staging
        WHERE transaction_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    print(f"{'Year':<6} {'Txns':>10} {'Debits':>18} {'Credits':>18}")
    print("-" * 60)
    for year, count, debits, credits in cur.fetchall():
        print(f"{int(year):<6} {count:>10,} ${debits or 0:>15,.2f} ${credits or 0:>15,.2f}")
    
    # 7. Sample transactions
    print("\n7. SAMPLE TRANSACTIONS (First 10)")
    print("-" * 80)
    
    cur.execute("""
        SELECT transaction_date, account_name, description, debit_amount, credit_amount
        FROM gl_transactions_staging
        ORDER BY transaction_date
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        txn_date, account, desc, debit, credit = row
        print(f"{txn_date} | {account or 'N/A':30} | Dr: ${debit or 0:>10,.2f} Cr: ${credit or 0:>10,.2f}")
        if desc:
            print(f"  Desc: {desc[:70]}")
    
    # 8. Duplicate detection
    print("\n8. DUPLICATE DETECTION")
    print("-" * 80)
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM (
            SELECT transaction_date, account_name, debit_amount, credit_amount, COUNT(*)
            FROM gl_transactions_staging
            GROUP BY transaction_date, account_name, debit_amount, credit_amount
            HAVING COUNT(*) > 1
        ) duplicates
    """)
    
    dup_count = cur.fetchone()[0]
    print(f"Duplicate transaction groups (by date, account, amounts): {dup_count:,}")
    
    if dup_count > 0:
        cur.execute("""
            SELECT transaction_date, account_name, debit_amount, credit_amount, COUNT(*) as dup_count
            FROM gl_transactions_staging
            GROUP BY transaction_date, account_name, debit_amount, credit_amount
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """)
        
        print("\nTop duplicate patterns:")
        for txn_date, account, debit, credit, count in cur.fetchall():
            print(f"  {txn_date} | {account or 'N/A':30} | Dr: ${debit or 0:,.2f} Cr: ${credit or 0:,.2f} | {count} times")
    
    cur.close()
    conn.close()
    
    # 9. Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    print("""
Based on analysis:

1. Date Range Comparison:
   - Check if staging dates overlap with unified_general_ledger
   - Identify NEW vs DUPLICATE data

2. Data Quality:
   - Review NULL value counts
   - Check zero-amount transactions
   - Validate account codes

3. Duplicate Detection:
   - If high duplicate rate → likely already imported
   - If low duplicates → may have new data to promote

4. Promotion Strategy:
   A. If mostly NEW data → Promote to unified_general_ledger
   B. If mostly DUPLICATES → Archive and mark processed
   C. If MIXED → Selective promotion (new records only)

5. Next Steps:
   - Run detailed duplicate comparison against unified_general_ledger
   - Check source_system provenance
   - Create promotion or archive script
""")

if __name__ == '__main__':
    main()
