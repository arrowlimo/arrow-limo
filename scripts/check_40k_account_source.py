#!/usr/bin/env python3
"""
Check which banking account the $40K transactions came from.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def check_40k_account_source():
    print("🏦 BANKING ACCOUNT SOURCE FOR ~$40K TRANSACTIONS")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get the large transactions with account details
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.account_number,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.balance
            FROM banking_transactions bt
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) >= 35000
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) <= 45000
            ORDER BY bt.account_number, bt.transaction_date
        """)
        
        transactions = cur.fetchall()
        
        print(f"Found {len(transactions)} transactions between $35K-$45K in 2012\n")
        
        # Group by account
        account_groups = {}
        for trans in transactions:
            trans_id, account, date, desc, debit, credit, balance = trans
            amount = debit if debit else credit
            
            if account not in account_groups:
                account_groups[account] = []
            account_groups[account].append({
                'id': trans_id,
                'date': date,
                'amount': float(amount),
                'desc': desc,
                'balance': float(balance) if balance else None
            })
        
        # Show by account
        for account_num in sorted(account_groups.keys()):
            transactions_list = account_groups[account_num]
            total_amount = sum(t['amount'] for t in transactions_list)
            
            print(f"🏦 ACCOUNT: {account_num}")
            print(f"   Total Large Transactions: {len(transactions_list)}")
            print(f"   Total Amount: ${total_amount:,.2f}")
            print()
            
            for i, trans in enumerate(sorted(transactions_list, key=lambda x: x['date'])):
                print(f"   {i+1}. {trans['date']} - ${trans['amount']:,.2f}")
                desc_short = (trans['desc'][:60] + '...') if trans['desc'] and len(trans['desc']) > 60 else trans['desc'] or 'No description'
                print(f"      {desc_short}")
                print(f"      Balance after: ${trans['balance']:,.2f}" if trans['balance'] else "      Balance: Not recorded")
                print(f"      Transaction ID: {trans['id']}")
                print()
            
            print(f"   {'-' * 50}")
            print()
        
        # Show account summary for context
        print("🔍 ACCOUNT CONTEXT ANALYSIS:")
        print("=" * 30)
        
        for account_num in sorted(account_groups.keys()):
            cur.execute("""
                SELECT 
                    MIN(transaction_date) as first_date,
                    MAX(transaction_date) as last_date,
                    COUNT(*) as total_transactions,
                    SUM(COALESCE(debit_amount, 0)) as total_debits,
                    SUM(COALESCE(credit_amount, 0)) as total_credits
                FROM banking_transactions 
                WHERE account_number = %s
            """, (account_num,))
            
            first_date, last_date, total_count, total_debits, total_credits = cur.fetchone()
            
            print(f"Account {account_num}:")
            print(f"  Active period: {first_date} to {last_date}")
            print(f"  Total transactions: {total_count:,}")
            print(f"  Total debits: ${float(total_debits or 0):,.2f}")
            print(f"  Total credits: ${float(total_credits or 0):,.2f}")
            print(f"  Net activity: ${float(total_credits or 0) - float(total_debits or 0):,.2f}")
            print()
        
        # Check account activity patterns
        print("💡 ACCOUNT TYPE ANALYSIS:")
        print("=" * 25)
        
        for account_num in sorted(account_groups.keys()):
            # Look for clues about account type
            cur.execute("""
                SELECT description, COUNT(*) as freq
                FROM banking_transactions 
                WHERE account_number = %s
                  AND description IS NOT NULL
                GROUP BY description
                ORDER BY freq DESC
                LIMIT 10
            """, (account_num,))
            
            common_descriptions = cur.fetchall()
            
            print(f"Account {account_num} - Common transaction types:")
            for desc, freq in common_descriptions:
                desc_short = desc[:50] + '...' if len(desc) > 50 else desc
                print(f"  {freq:3d}x: {desc_short}")
            
            # Analyze account patterns
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debit_count,
                    COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credit_count,
                    AVG(COALESCE(debit_amount, 0)) as avg_debit,
                    AVG(COALESCE(credit_amount, 0)) as avg_credit
                FROM banking_transactions 
                WHERE account_number = %s
                  AND EXTRACT(YEAR FROM transaction_date) = 2012
            """, (account_num,))
            
            debit_count, credit_count, avg_debit, avg_credit = cur.fetchone()
            
            print(f"  2012 Activity:")
            print(f"    Debits: {debit_count:,} (avg ${float(avg_debit or 0):,.2f})")
            print(f"    Credits: {credit_count:,} (avg ${float(avg_credit or 0):,.2f})")
            
            # Determine likely account type
            if debit_count > credit_count * 2:
                account_type = "Operating/Expense Account (mainly outgoing)"
            elif credit_count > debit_count * 2:
                account_type = "Revenue/Deposit Account (mainly incoming)"
            else:
                account_type = "Mixed Activity Account"
            
            print(f"    Type: {account_type}")
            print()
        
        # Final analysis
        print("🎯 SUMMARY:")
        print("=" * 15)
        
        total_40k_amount = sum(sum(t['amount'] for t in transactions_list) 
                              for transactions_list in account_groups.values())
        
        print(f"Total $40K+ transactions: ${total_40k_amount:,.2f}")
        print(f"Number of accounts involved: {len(account_groups)}")
        
        for account_num, transactions_list in account_groups.items():
            account_total = sum(t['amount'] for t in transactions_list)
            percentage = (account_total / total_40k_amount * 100) if total_40k_amount > 0 else 0
            print(f"  Account {account_num}: ${account_total:,.2f} ({percentage:.1f}%)")
        
        # Cross-reference with our earlier analysis
        if len(account_groups) == 1:
            single_account = list(account_groups.keys())[0]
            print(f"\n[OK] ALL $40K transactions came from SINGLE account: {single_account}")
            print("This confirms coordinated business activity from one main operating account.")
        else:
            print(f"\n📊 Transactions spread across {len(account_groups)} accounts")
            print("May indicate different business purposes or account types.")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    check_40k_account_source()

if __name__ == "__main__":
    main()