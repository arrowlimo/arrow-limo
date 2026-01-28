"""
Fix records with name='nan' by identifying their type and assigning appropriate names
"""
import psycopg2

def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )
    cur = conn.cursor()
    
    print("=" * 120)
    print("FIXING RECORDS WITH name='nan'")
    print("=" * 120)
    
    updated_counts = {}
    
    # 1. Fix Transfer transactions - mark as "Internal Transfer"
    print("\n1. Updating Transfer transactions...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Internal Transfer',
            account_name = 'Internal Transfer'
        WHERE name = 'nan'
        AND transaction_type = 'Transfer'
    """)
    count = cur.rowcount
    updated_counts['Transfer'] = count
    print(f"   Updated {count} Transfer records")
    
    # 2. Fix Square deposit account transfers
    print("\n2. Updating Square deposit account transactions...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Square Payments',
            account_name = 'Square Payments'
        WHERE name = 'nan'
        AND account LIKE '%Square%'
    """)
    count = cur.rowcount
    updated_counts['Square'] = count
    print(f"   Updated {count} Square records")
    
    # 3. Fix Deposit Clearing account - these are payment processing holds
    print("\n3. Updating Deposit Clearing account...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Payment Processing',
            account_name = 'Payment Processing'
        WHERE name = 'nan'
        AND account = '1095 Deposit Clearing'
    """)
    count = cur.rowcount
    updated_counts['Deposit Clearing'] = count
    print(f"   Updated {count} Deposit Clearing records")
    
    # 4. Fix Driver Advances
    print("\n4. Updating Driver Advances...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Driver Advance',
            account_name = 'Driver Advance'
        WHERE name = 'nan'
        AND account = '1375 Driver Advances'
    """)
    count = cur.rowcount
    updated_counts['Driver Advances'] = count
    print(f"   Updated {count} Driver Advance records")
    
    # 5. Fix Shareholder Loan
    print("\n5. Updating Shareholder Loan transactions...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Shareholder Loan',
            account_name = 'Shareholder Loan'
        WHERE name = 'nan'
        AND account = '2900 Shareholder Loan'
    """)
    count = cur.rowcount
    updated_counts['Shareholder Loan'] = count
    print(f"   Updated {count} Shareholder Loan records")
    
    # 6. Fix Suspense account - temporary holding
    print("\n6. Updating Suspense account...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Suspense/Unclassified',
            account_name = 'Suspense/Unclassified'
        WHERE name = 'nan'
        AND account = '1399 Suspense'
    """)
    count = cur.rowcount
    updated_counts['Suspense'] = count
    print(f"   Updated {count} Suspense records")
    
    # 7. Fix Payroll Liabilities
    print("\n7. Updating Payroll Liabilities...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Payroll Withholdings',
            account_name = 'Payroll Withholdings'
        WHERE name = 'nan'
        AND account = '2100 Payroll Liabilities'
    """)
    count = cur.rowcount
    updated_counts['Payroll Liabilities'] = count
    print(f"   Updated {count} Payroll Liabilities records")
    
    # 8. Fix Journal Entry transactions without specific account patterns
    print("\n8. Updating remaining Journal Entry transactions...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Journal Entry',
            account_name = 'Journal Entry'
        WHERE name = 'nan'
        AND transaction_type = 'Journal Entry'
    """)
    count = cur.rowcount
    updated_counts['Journal Entry'] = count
    print(f"   Updated {count} Journal Entry records")
    
    # 9. Fix Deposit transactions
    print("\n9. Updating Deposit transactions...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Bank Deposit',
            account_name = 'Bank Deposit'
        WHERE name = 'nan'
        AND transaction_type = 'Deposit'
    """)
    count = cur.rowcount
    updated_counts['Deposit'] = count
    print(f"   Updated {count} Deposit records")
    
    # 10. Fix any remaining with memo_description containing identifiable info
    print("\n10. Checking for memo_description with identifiable patterns...")
    
    # Flying J from memo
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Flying J',
            account_name = 'Flying J',
            supplier = 'Flying J'
        WHERE name = 'nan'
        AND memo_description LIKE '%FLYING J%'
    """)
    count = cur.rowcount
    updated_counts['Flying J (memo)'] = count
    print(f"   Updated {count} Flying J records from memo")
    
    # Shell from memo
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Shell',
            account_name = 'Shell',
            supplier = 'Shell'
        WHERE name = 'nan'
        AND memo_description LIKE '%SHELL%'
    """)
    count = cur.rowcount
    updated_counts['Shell (memo)'] = count
    print(f"   Updated {count} Shell records from memo")
    
    # 11. Fix remaining Expense/Cheque Expense by account type
    print("\n11. Updating remaining Expense transactions by account...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Fuel Purchase',
            account_name = 'Fuel Purchase'
        WHERE name = 'nan'
        AND account = '6925 Fuel'
    """)
    count = cur.rowcount
    updated_counts['Fuel'] = count
    print(f"   Updated {count} Fuel records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Vehicle Maintenance',
            account_name = 'Vehicle Maintenance'
        WHERE name = 'nan'
        AND account = '6900 Vehicle R&M'
    """)
    count = cur.rowcount
    updated_counts['Vehicle R&M'] = count
    print(f"   Updated {count} Vehicle R&M records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Hospitality Supplies',
            account_name = 'Hospitality Supplies'
        WHERE name = 'nan'
        AND account = '6751 Hospitality Supplies'
    """)
    count = cur.rowcount
    updated_counts['Hospitality'] = count
    print(f"   Updated {count} Hospitality Supplies records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Office Supplies',
            account_name = 'Office Supplies'
        WHERE name = 'nan'
        AND account = '6550 Office Supplies'
    """)
    count = cur.rowcount
    updated_counts['Office Supplies'] = count
    print(f"   Updated {count} Office Supplies records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Telephone',
            account_name = 'Telephone'
        WHERE name = 'nan'
        AND account = '6800 Telephone'
    """)
    count = cur.rowcount
    updated_counts['Telephone'] = count
    print(f"   Updated {count} Telephone records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Meals & Entertainment',
            account_name = 'Meals & Entertainment'
        WHERE name = 'nan'
        AND account = '6500 Meals and Entertainment'
    """)
    count = cur.rowcount
    updated_counts['Meals'] = count
    print(f"   Updated {count} Meals & Entertainment records")
    
    # 12. Fix income accounts
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Limousine Service',
            account_name = 'Limousine Service'
        WHERE name = 'nan'
        AND account = '4000 Limousine Service Income'
    """)
    count = cur.rowcount
    updated_counts['Limo Income'] = count
    print(f"   Updated {count} Limousine Service Income records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Gratuity Income',
            account_name = 'Gratuity Income'
        WHERE name = 'nan'
        AND account = '4300 Gratuity Income'
    """)
    count = cur.rowcount
    updated_counts['Gratuity'] = count
    print(f"   Updated {count} Gratuity Income records")
    
    # 13. GST/HST Payable - tax remittance
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Tax Remittance',
            account_name = 'Tax Remittance'
        WHERE name = 'nan'
        AND account = '2200 GST/HST Payable'
    """)
    count = cur.rowcount
    updated_counts['GST/HST'] = count
    print(f"   Updated {count} GST/HST records")
    
    # Commit all changes
    conn.commit()
    
    # Check remaining
    cur.execute("""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE name = 'nan'
    """)
    remaining = cur.fetchone()[0]
    
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print(f"\nTotal records updated:")
    total_updated = sum(updated_counts.values())
    for category, count in sorted(updated_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {category}: {count:,}")
    print(f"\nTotal: {total_updated:,}")
    print(f"\nRecords still with name='nan': {remaining:,}")
    
    if remaining > 0:
        print("\nRemaining records by account:")
        cur.execute("""
            SELECT account, COUNT(*) as count
            FROM general_ledger 
            WHERE name = 'nan'
            GROUP BY account
            ORDER BY count DESC
            LIMIT 10
        """)
        for account, count in cur.fetchall():
            print(f"  {account}: {count:,}")
    
    conn.close()
    print("\n" + "=" * 120)
    print("Update complete!")

if __name__ == "__main__":
    main()
