#!/usr/bin/env python3
"""
Review bank_accounts and cibc_accounts to determine what should be added to chart_of_accounts.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("BANK ACCOUNTS REVIEW")
    print("="*80)
    
    # 1. bank_accounts table
    print("\n1. BANK_ACCOUNTS TABLE (3 rows)")
    print("-"*80)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'bank_accounts' 
        ORDER BY ordinal_position
    """)
    
    print("\nColumns:")
    for col, dtype in cur.fetchall():
        print(f"  • {col}: {dtype}")
    
    cur.execute("SELECT * FROM bank_accounts ORDER BY account_number")
    cols = [desc[0] for desc in cur.description]
    
    print(f"\nAll data:")
    for row in cur.fetchall():
        print(f"\n  Account {row[cols.index('account_number')]}:")
        for i, col in enumerate(cols):
            if row[i] is not None:
                print(f"    {col}: {row[i]}")
    
    # 2. cibc_accounts table
    print("\n\n2. CIBC_ACCOUNTS TABLE (6 rows)")
    print("-"*80)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'cibc_accounts' 
        ORDER BY ordinal_position
    """)
    
    print("\nColumns:")
    for col, dtype in cur.fetchall():
        print(f"  • {col}: {dtype}")
    
    cur.execute("SELECT * FROM cibc_accounts ORDER BY account_number")
    cols = [desc[0] for desc in cur.description]
    
    print(f"\nAll data:")
    for row in cur.fetchall():
        acct_num_idx = cols.index('account_number') if 'account_number' in cols else 0
        print(f"\n  {row[0]} - {row[1] if len(row) > 1 else 'No name'} ({row[acct_num_idx] if len(row) > acct_num_idx else 'No number'})")
    
    # 3. Check chart_of_accounts
    print("\n\n3. CURRENT BANK ACCOUNTS IN CHART_OF_ACCOUNTS")
    print("-"*80)
    
    cur.execute("""
        SELECT account_code, account_name, bank_account_number
        FROM chart_of_accounts
        WHERE account_type = 'Asset'
        AND account_code BETWEEN '1010' AND '1020'
        ORDER BY account_code
    """)
    
    print(f"\n{'GL Code':<10} {'Account Name':<40} {'Bank Account #':<20}")
    print("-"*80)
    for code, name, bank_num in cur.fetchall():
        print(f"{code:<10} {name:<40} {bank_num or 'None':<20}")
    
    # 4. Identify missing accounts
    print("\n\n4. MISSING BANK ACCOUNTS")
    print("-"*80)
    
    print("\n⚠️  Account 3648117 - CIBC Business Deposit (Merchant Processing)")
    print("   • This is the MERCHANT PROCESSING account for credit card deposits")
    print("   • CREDIT MEMO transactions (Visa/MC/Amex batch deposits)")
    print("   • Should be added as 1013 CIBC Merchant Processing")
    
    print("\n⚠️  Account 8314462 - CIBC Vehicle Loans")
    print("   • This appears to be a LOAN account, not a bank account")
    print("   • Could be LIABILITY (2200s Vehicle Loans) or ASSET if this is a loan receivable")
    print("   • Need to verify: Is this money WE owe or money OWED TO US?")
    
    # 5. Check banking_transactions usage
    print("\n\n5. BANKING_TRANSACTIONS USAGE")
    print("-"*80)
    
    accounts_to_check = ['3648117', '8314462']
    
    for acct in accounts_to_check:
        cur.execute("""
            SELECT COUNT(*), 
                   MIN(transaction_date), 
                   MAX(transaction_date),
                   SUM(debit_amount) as total_debits,
                   SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE account_number = %s
        """, (acct,))
        
        result = cur.fetchone()
        if result and result[0] > 0:
            count, min_date, max_date, debits, credits = result
            print(f"\nAccount {acct}:")
            print(f"  Transactions: {count}")
            print(f"  Date range: {min_date} to {max_date}")
            print(f"  Total debits: ${debits:,.2f}" if debits else "  Total debits: $0.00")
            print(f"  Total credits: ${credits:,.2f}" if credits else "  Total credits: $0.00")
            
            # Sample transactions
            cur.execute("""
                SELECT transaction_date, description, debit_amount, credit_amount
                FROM banking_transactions
                WHERE account_number = %s
                ORDER BY transaction_date DESC
                LIMIT 3
            """, (acct,))
            
            print("  Sample transactions:")
            for date, desc, debit, credit in cur.fetchall():
                desc_short = (desc[:50] + '...') if len(desc) > 53 else desc
                if debit and debit > 0:
                    print(f"    {date} | {desc_short:<53} | Debit: ${debit:,.2f}")
                else:
                    print(f"    {date} | {desc_short:<53} | Credit: ${credit:,.2f}")
        else:
            print(f"\nAccount {acct}: No transactions found")
    
    # 6. Recommendation
    print("\n\n6. RECOMMENDATION")
    print("="*80)
    
    print("\n✓ ADD TO CHART_OF_ACCOUNTS:")
    print("\n  1. Account 3648117 - CIBC Merchant Processing")
    print("     GL Code: 1013")
    print("     Type: Asset - Bank Account")
    print("     Purpose: Credit card merchant deposits (Square/Moneris)")
    
    print("\n  2. Account 8314462 - Vehicle Loans/Financing")
    print("     GL Code: 2210 (if LIABILITY) or 1450 (if loan receivable)")
    print("     Type: Need to verify - check if debits or credits predominate")
    print("     Purpose: Vehicle financing arrangements")
    
    print("\n✓ THEN DROP REDUNDANT TABLES:")
    print("   • bank_accounts (3 rows) - data will be in chart_of_accounts")
    print("   • cibc_accounts (6 rows) - data will be in chart_of_accounts")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
