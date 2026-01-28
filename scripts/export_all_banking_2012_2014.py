#!/usr/bin/env python3
"""
Export all banking transactions for 2012-2014 by account (excluding Scotia which is already validated)
"""

import pandas as pd
import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# Get all banking accounts with transaction counts for 2012-2014
query_accounts = """
    SELECT 
        account_number,
        MIN(transaction_date) as first_trans,
        MAX(transaction_date) as last_trans,
        COUNT(*) as total_trans,
        SUM(CASE WHEN EXTRACT(YEAR FROM transaction_date) = 2012 THEN 1 ELSE 0 END) as count_2012,
        SUM(CASE WHEN EXTRACT(YEAR FROM transaction_date) = 2013 THEN 1 ELSE 0 END) as count_2013,
        SUM(CASE WHEN EXTRACT(YEAR FROM transaction_date) = 2014 THEN 1 ELSE 0 END) as count_2014
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
      AND account_number != '903990106011'  -- Exclude Scotia (already validated)
    GROUP BY account_number
    ORDER BY account_number
"""

df_accounts = pd.read_sql_query(query_accounts, conn)

print("="*80)
print("BANKING ACCOUNTS WITH 2012-2014 TRANSACTIONS (Excluding Scotia)")
print("="*80)
print(df_accounts.to_string(index=False))

# Export each account to a separate sheet in Excel
output_file = "L:/limo/data/banking_2012_2014_for_validation.xlsx"

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    
    # Summary sheet
    df_accounts.to_excel(writer, sheet_name='Summary', index=False)
    
    # Export each account's transactions
    for idx, row in df_accounts.iterrows():
        account_num = row['account_number']
        
        # Get all transactions for this account
        query_trans = """
            SELECT 
                transaction_date as date,
                description,
                debit_amount as "debit/withdrawal",
                credit_amount as "deposit/credit",
                balance,
                source_file,
                import_batch
            FROM banking_transactions
            WHERE account_number = %s
              AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
            ORDER BY transaction_date, transaction_id
        """
        
        df_trans = pd.read_sql_query(query_trans, conn, params=(account_num,))
        
        # Calculate running balance if balance column is NULL
        if df_trans['balance'].isna().any():
            running_balance = 0
            balances = []
            for _, trans in df_trans.iterrows():
                debit = trans['debit/withdrawal'] if pd.notna(trans['debit/withdrawal']) else 0
                credit = trans['deposit/credit'] if pd.notna(trans['deposit/credit']) else 0
                running_balance = running_balance + credit - debit
                balances.append(running_balance)
            df_trans['calculated_balance'] = balances
        
        # Create sheet name (max 31 chars for Excel)
        sheet_name = account_num[:31] if len(account_num) <= 31 else account_num[:28] + "..."
        
        df_trans.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"✅ Exported {len(df_trans)} transactions for account {account_num}")

print(f"\n{'='*80}")
print(f"✅ Report saved to: {output_file}")
print(f"{'='*80}")

# Print summary statistics
print("\nSUMMARY BY ACCOUNT:")
print(f"{'Account':<20} {'2012':<8} {'2013':<8} {'2014':<8} {'Total':<8}")
print("-" * 60)

for _, row in df_accounts.iterrows():
    print(f"{row['account_number']:<20} {int(row['count_2012']):<8} {int(row['count_2013']):<8} {int(row['count_2014']):<8} {int(row['total_trans']):<8}")

print("-" * 60)
print(f"{'TOTAL':<20} {int(df_accounts['count_2012'].sum()):<8} {int(df_accounts['count_2013'].sum()):<8} {int(df_accounts['count_2014'].sum()):<8} {int(df_accounts['total_trans'].sum()):<8}")

conn.close()
