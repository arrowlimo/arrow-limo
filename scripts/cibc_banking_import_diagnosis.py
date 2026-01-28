#!/usr/bin/env python3
"""
CIBC Banking Import Diagnosis & Coverage Report
===============================================
Comprehensive analysis of why CIBC banking statement amalgamation is challenging
and complete import coverage status.

Purpose:
1. Identify schema issues (column names, data types, FK relationships)
2. Detect coverage gaps (which months/accounts are missing)
3. Report on reconciliation status (matched vs unmatched)
4. Enumerate systemic issues (duplicates, date mismatches, amount mismatches)
"""

import psycopg2
import os
from decimal import Decimal
from collections import defaultdict
import json

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CIBC BANKING IMPORT DIAGNOSIS & COVERAGE REPORT")
    print("=" * 80)
    
    # Step 1: Schema Verification
    print("\n📋 STEP 1: DATABASE SCHEMA VERIFICATION")
    print("-" * 80)
    
    # Check banking_transactions table structure
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'banking_transactions'
        ORDER BY ordinal_position
    """)
    bt_columns = cur.fetchall()
    
    print(f"\n[OK] banking_transactions table exists with {len(bt_columns)} columns:")
    critical_cols = ['transaction_id', 'bank_id', 'trans_date', 'trans_description', 
                     'debit_amount', 'credit_amount', 'account_number']
    for col, dtype, nullable in bt_columns[:15]:  # Show first 15
        marker = "✓" if col in critical_cols else " "
        print(f"   {marker} {col:30} {dtype:20} NULL={nullable}")
    
    # Check if account_number is in banking_transactions or bank_accounts
    bt_col_names = [col[0] for col in bt_columns]
    has_account_number_direct = 'account_number' in bt_col_names
    
    print(f"\n🔍 Schema Pattern:")
    if has_account_number_direct:
        print(f"   [OK] account_number stored directly in banking_transactions")
    else:
        print(f"   [WARN] account_number NOT in banking_transactions")
        print(f"   → Must JOIN bank_accounts via bank_id FK")
    
    # Check bank_accounts table
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'bank_accounts'
        ORDER BY ordinal_position
    """)
    ba_columns = cur.fetchall()
    
    if ba_columns:
        print(f"\n[OK] bank_accounts table exists with {len(ba_columns)} columns:")
        for col, dtype in ba_columns[:10]:
            print(f"     {col:30} {dtype:20}")
    else:
        print(f"\n[FAIL] bank_accounts table NOT FOUND")
    
    # Step 2: Data Coverage Analysis
    print("\n\n📊 STEP 2: DATA COVERAGE ANALYSIS")
    print("-" * 80)
    
    # Total transactions and date range
    if has_account_number_direct:
        cur.execute("""
            SELECT COUNT(*), 
                   MIN(transaction_date) as earliest,
                   MAX(transaction_date) as latest,
                   COUNT(DISTINCT EXTRACT(YEAR FROM transaction_date)) as year_count,
                   COUNT(DISTINCT account_number) as account_count
            FROM banking_transactions
        """)
    else:
        cur.execute("""
            SELECT COUNT(*), 
                   MIN(bt.transaction_date) as earliest,
                   MAX(bt.transaction_date) as latest,
                   COUNT(DISTINCT EXTRACT(YEAR FROM bt.transaction_date)) as year_count,
                   COUNT(DISTINCT ba.account_number) as account_count
            FROM banking_transactions bt
            LEFT JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
        """)
    
    total, earliest, latest, years, accounts = cur.fetchone()
    
    print(f"\n💳 Overall Banking Data:")
    print(f"   Total transactions: {total:,}")
    print(f"   Date range: {earliest} to {latest}")
    print(f"   Years covered: {years}")
    print(f"   Distinct accounts: {accounts}")
    
    # Account-level breakdown
    print(f"\n🏦 Account Breakdown:")
    if has_account_number_direct:
        cur.execute("""
            SELECT account_number,
                   COUNT(*) as txn_count,
                   MIN(transaction_date) as first_txn,
                   MAX(transaction_date) as last_txn,
                   SUM(debit_amount) as total_debits,
                   SUM(credit_amount) as total_credits
            FROM banking_transactions
            GROUP BY account_number
            ORDER BY txn_count DESC
        """)
    else:
        cur.execute("""
            SELECT ba.account_number,
                   COUNT(*) as txn_count,
                   MIN(bt.transaction_date) as first_txn,
                   MAX(bt.transaction_date) as last_txn,
                   SUM(bt.debit_amount) as total_debits,
                   SUM(bt.credit_amount) as total_credits
            FROM banking_transactions bt
            LEFT JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
            GROUP BY ba.account_number
            ORDER BY txn_count DESC
        """)
    
    accounts_data = cur.fetchall()
    for acc, count, first, last, debits, credits in accounts_data:
        acc_label = acc or "NULL/Unknown"
        print(f"   {acc_label:20} | {count:6,} txns | {first} to {last}")
        print(f"      → Debits: ${debits:,.2f} | Credits: ${credits:,.2f}")
    
    # Step 3: CIBC-Specific Account Search
    print(f"\n\n🔍 STEP 3: CIBC-SPECIFIC ACCOUNT SEARCH")
    print("-" * 80)
    
    cibc_patterns = ['00339', '7461615', '0228362', '3648117', '8362', 'CIBC']
    
    for pattern in cibc_patterns:
        if has_account_number_direct:
            cur.execute("""
                SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
                FROM banking_transactions
                WHERE account_number LIKE %s
            """, (f'%{pattern}%',))
        else:
            cur.execute("""
                SELECT COUNT(*), MIN(bt.transaction_date), MAX(bt.transaction_date)
                FROM banking_transactions bt
                JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
                WHERE ba.account_number LIKE %s
            """, (f'%{pattern}%',))
        
        count, min_date, max_date = cur.fetchone()
        if count > 0:
            print(f"   [OK] Pattern '{pattern}': {count:,} transactions ({min_date} to {max_date})")
        else:
            print(f"   [FAIL] Pattern '{pattern}': NO MATCHES")
    
    # Step 4: Year/Month Coverage Matrix
    print(f"\n\n📅 STEP 4: YEAR/MONTH COVERAGE MATRIX")
    print("-" * 80)
    
    cur.execute("""
        SELECT EXTRACT(YEAR FROM transaction_date) as year,
               EXTRACT(MONTH FROM transaction_date) as month,
               COUNT(*) as txn_count
        FROM banking_transactions
        WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2013-12-31'
        GROUP BY year, month
        ORDER BY year, month
    """)
    
    coverage = cur.fetchall()
    if coverage:
        print(f"\n   2012-2013 Coverage (txn counts by month):")
        current_year = None
        for year, month, count in coverage:
            if year != current_year:
                print(f"\n   {int(year)}:")
                current_year = year
            print(f"      {int(month):02d}: {count:6,} transactions")
    else:
        print(f"\n   [FAIL] NO DATA for 2012-2013")
    
    # Step 5: Common Import Issues
    print(f"\n\n[WARN] STEP 5: COMMON IMPORT ISSUES DETECTED")
    print("-" * 80)
    
    issues = []
    
    # Issue 1: NULL descriptions
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE description IS NULL OR description = ''
    """)
    null_desc_count = cur.fetchone()[0]
    if null_desc_count > 0:
        issues.append(f"NULL/empty descriptions: {null_desc_count:,} transactions")
    
    # Issue 2: Both debit and credit > 0
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE debit_amount > 0 AND credit_amount > 0
    """)
    both_sides_count = cur.fetchone()[0]
    if both_sides_count > 0:
        issues.append(f"Both debit AND credit positive: {both_sides_count:,} transactions (data error)")
    
    # Issue 3: Both debit and credit = 0
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE debit_amount = 0 AND credit_amount = 0
    """)
    zero_amt_count = cur.fetchone()[0]
    if zero_amt_count > 0:
        issues.append(f"Zero-amount transactions: {zero_amt_count:,} (placeholders or fees)")
    
    # Issue 4: Potential duplicates by source_hash (if column exists)
    if 'source_hash' in bt_col_names:
        cur.execute("""
            SELECT source_hash, COUNT(*) as dupe_count
            FROM banking_transactions
            WHERE source_hash IS NOT NULL
            GROUP BY source_hash
            HAVING COUNT(*) > 1
            ORDER BY dupe_count DESC
            LIMIT 5
        """)
        dupes = cur.fetchall()
        if dupes:
            issues.append(f"Duplicate source_hash entries: {len(dupes)} hashes with multiple records")
    else:
        issues.append("No source_hash column (duplicate detection not possible)")
    
    # Issue 5: Unreconciled transactions
    if 'reconciliation_status' in bt_col_names:
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE reconciliation_status = 'unreconciled' OR reconciliation_status IS NULL
        """)
        unreconciled_count = cur.fetchone()[0]
        if unreconciled_count > 0:
            issues.append(f"Unreconciled transactions: {unreconciled_count:,} ({unreconciled_count/total*100:.1f}% of total)")
    else:
        issues.append("No reconciliation_status column (reconciliation not tracked)")
    
    if issues:
        for issue in issues:
            print(f"   [WARN] {issue}")
    else:
        print(f"   [OK] No major data quality issues detected")
    
    # Step 6: Recommendations
    print(f"\n\n💡 STEP 6: CIBC IMPORT CHALLENGES & RECOMMENDATIONS")
    print("-" * 80)
    
    challenges = [
        ("Schema Inconsistency", 
         "account_number may be in bank_accounts (FK join) or banking_transactions (direct)",
         "Always check schema before querying; use JOINs when needed"),
        
        ("Column Name Variations",
         "trans_date vs transaction_date, trans_description vs description",
         "Query information_schema first; create view with standardized names"),
        
        ("Account Number Formats",
         "CIBC accounts appear as: 00339, 7461615, 0228362, 00339-7461615",
         "Use LIKE '%pattern%' or REGEXP matching; normalize on import"),
        
        ("Debit/Credit Semantics",
         "debit_amount = money OUT (purchases, withdrawals); credit_amount = money IN",
         "Always check which column is non-zero; never assume side"),
        
        ("Date vs DateTime",
         "Some imports use DATE, others TIMESTAMP; comparisons may fail",
         "Cast to DATE when comparing: trans_date::date = '2012-05-07'"),
        
        ("Duplicate Imports",
         "Same CSV imported multiple times without source_hash deduplication",
         "Generate SHA256 hash from date+description+amount; check before INSERT"),
        
        ("NSF and Reversals",
         "NSF transactions post as debit, then reversed (credit), then re-attempted",
         "Tag NSF events; net reversals out in reconciliation; classify separately"),
        
        ("Posting Date Lag",
         "Card purchases post 1-3 days after transaction date",
         "Use ±1 day tolerance in matching; check near-date transactions"),
        
        ("Missing Account Linkage",
         "banking_transactions.bank_id may be NULL or point to wrong account",
         "Verify bank_accounts populated; backfill bank_id using account patterns"),
        
        ("Reconciliation Gaps",
         "Majority of transactions show 'unreconciled' status",
         "Run automated matching scripts; link to receipts/charters/payments")
    ]
    
    for i, (challenge, description, recommendation) in enumerate(challenges, 1):
        print(f"\n   {i}. {challenge}")
        print(f"      Problem: {description}")
        print(f"      Fix: {recommendation}")
    
    # Step 7: Import Script Status
    print(f"\n\n📂 STEP 7: IMPORT SCRIPT INVENTORY")
    print("-" * 80)
    
    import_scripts = [
        "import_banking_transactions.py",
        "import_banking_incremental.py",
        "scripts/import_banking_from_staged_csv.py",
        "scripts/import_banking_from_text.py"
    ]
    
    print(f"\n   Available import scripts:")
    for script in import_scripts:
        script_path = os.path.join("l:\\limo", script)
        if os.path.exists(script_path):
            print(f"      [OK] {script}")
        else:
            print(f"      [FAIL] {script} (not found)")
    
    # Summary
    print(f"\n\n" + "=" * 80)
    print(f"📊 SUMMARY")
    print(f"=" * 80)
    print(f"   Total banking transactions: {total:,}")
    print(f"   Coverage: {earliest} to {latest} ({years} years)")
    print(f"   Accounts: {accounts} distinct account numbers")
    print(f"   Data quality issues: {len(issues)}")
    print(f"   Import challenges identified: {len(challenges)}")
    
    if total == 0:
        print(f"\n   [WARN] CRITICAL: NO banking data in database!")
        print(f"   → Run import scripts to load CIBC statements")
    elif total < 1000:
        print(f"\n   [WARN] WARNING: Very limited data ({total} transactions)")
        print(f"   → Verify all CIBC statement files have been imported")
    else:
        print(f"\n   [OK] Substantial banking data present")
        print(f"   → Focus on reconciliation and gap-filling")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
