"""
Audit 2013 CIBC banking and Mastercard statements.
Verify hardcoded balances against transaction data and check for missing data.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def audit_banking_balances(cur):
    """Audit running balances against transactions."""
    print("\n" + "=" * 80)
    print("AUDITING 2013 BANKING BALANCES")
    print("=" * 80)
    
    # Get all 2013 transactions ordered by date
    cur.execute("""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2013
        ORDER BY account_number, transaction_date, transaction_id
    """)
    
    transactions = cur.fetchall()
    
    # Group by account
    accounts = defaultdict(list)
    for txn in transactions:
        accounts[txn['account_number']].append(txn)
    
    results = []
    
    for account_number, txns in accounts.items():
        print(f"\n📊 ACCOUNT: {account_number}")
        print("-" * 80)
        
        if not txns:
            print("  No transactions found")
            continue
        
        # Track balance errors
        balance_errors = []
        missing_balances = 0
        
        # Calculate running balance
        prev_balance = None
        expected_balance = None
        
        for i, txn in enumerate(txns):
            debit = txn['debit_amount'] or Decimal('0')
            credit = txn['credit_amount'] or Decimal('0')
            recorded_balance = txn['balance']
            
            # Calculate expected balance
            if i == 0:
                # First transaction - use recorded balance as starting point
                if recorded_balance is not None:
                    expected_balance = recorded_balance
                    prev_balance = recorded_balance
                else:
                    missing_balances += 1
                    continue
            else:
                # Calculate from previous balance
                if prev_balance is not None:
                    expected_balance = prev_balance + credit - debit
                else:
                    missing_balances += 1
                    continue
            
            # Check if recorded balance matches expected
            if recorded_balance is not None:
                diff = abs(recorded_balance - expected_balance)
                if diff > Decimal('0.01'):  # More than 1 cent difference
                    balance_errors.append({
                        'date': txn['transaction_date'],
                        'description': txn['description'][:50],
                        'expected': expected_balance,
                        'recorded': recorded_balance,
                        'difference': recorded_balance - expected_balance
                    })
                
                prev_balance = recorded_balance
            else:
                missing_balances += 1
                prev_balance = expected_balance
        
        # Report results
        print(f"  Total Transactions: {len(txns)}")
        print(f"  Date Range: {txns[0]['transaction_date']} to {txns[-1]['transaction_date']}")
        print(f"  Opening Balance: ${prev_balance if i == 0 and prev_balance else 'N/A'}")
        print(f"  Closing Balance: ${prev_balance or 'N/A'}")
        
        if missing_balances > 0:
            print(f"\n  ⚠️  Missing Balances: {missing_balances} transactions")
        
        if balance_errors:
            print(f"\n  ❌ Balance Errors Found: {len(balance_errors)}")
            print("\n  Top 5 Balance Discrepancies:")
            # Sort by absolute difference
            balance_errors.sort(key=lambda x: abs(x['difference']), reverse=True)
            for error in balance_errors[:5]:
                print(f"    {error['date']} | {error['description']}")
                print(f"      Expected: ${error['expected']:,.2f}")
                print(f"      Recorded: ${error['recorded']:,.2f}")
                print(f"      Difference: ${error['difference']:,.2f}")
        else:
            print("\n  ✅ All balances match expected values")
        
        results.append({
            'account': account_number,
            'transaction_count': len(txns),
            'balance_errors': len(balance_errors),
            'missing_balances': missing_balances
        })
    
    return results

def check_data_completeness(cur):
    """Check for missing months or gaps in data."""
    print("\n" + "=" * 80)
    print("DATA COMPLETENESS CHECK")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            account_number,
            EXTRACT(MONTH FROM transaction_date) as month,
            COUNT(*) as transaction_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2013
        GROUP BY account_number, EXTRACT(MONTH FROM transaction_date)
        ORDER BY account_number, month
    """)
    
    monthly_data = cur.fetchall()
    
    # Check for missing months
    accounts = {}
    for row in monthly_data:
        acc = row['account_number']
        if acc not in accounts:
            accounts[acc] = set()
        accounts[acc].add(int(row['month']))
    
    print("\n📅 MONTHLY COVERAGE:")
    print("-" * 80)
    for account, months in accounts.items():
        missing_months = set(range(1, 13)) - months
        print(f"\nAccount {account}:")
        print(f"  Months with data: {sorted(months)}")
        if missing_months:
            print(f"  ⚠️  Missing months: {sorted(missing_months)}")
        else:
            print(f"  ✅ Complete (all 12 months)")
    
    # Show monthly breakdown
    print("\n📊 MONTHLY TRANSACTION SUMMARY:")
    print("-" * 80)
    current_account = None
    for row in monthly_data:
        if row['account_number'] != current_account:
            current_account = row['account_number']
            print(f"\n  Account {current_account}:")
        
        month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][int(row['month']) - 1]
        debits = row['total_debits'] or Decimal('0')
        credits = row['total_credits'] or Decimal('0')
        print(f"    {month_name}: {row['transaction_count']:3d} txns | "
              f"Debits: ${debits:>10,.2f} | "
              f"Credits: ${credits:>10,.2f}")

def check_duplicate_transactions(cur):
    """Check for duplicate transactions."""
    print("\n" + "=" * 80)
    print("DUPLICATE TRANSACTION CHECK")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            COUNT(*) as duplicate_count
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2013
        GROUP BY account_number, transaction_date, description, debit_amount, credit_amount
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, debit_amount DESC NULLS LAST
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} potential duplicate transaction groups")
        print("\nTop 10 Duplicates:")
        print("-" * 80)
        for dup in duplicates[:10]:
            amount = dup['debit_amount'] or dup['credit_amount']
            txn_type = 'Debit' if dup['debit_amount'] else 'Credit'
            print(f"\n  {dup['transaction_date']} | {dup['account_number']}")
            print(f"  {dup['description'][:60]}")
            print(f"  {txn_type}: ${amount:,.2f} | Duplicates: {dup['duplicate_count']}")
    else:
        print("\n✅ No duplicate transactions found")

def check_mastercard_data(cur):
    """Check for Mastercard/credit card data."""
    print("\n" + "=" * 80)
    print("MASTERCARD / CREDIT CARD DATA CHECK")
    print("=" * 80)
    
    # Check cibc_card_transactions table
    try:
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(amount) as total,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date
            FROM cibc_card_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = 2013
        """)
        result = cur.fetchone()
        
        if result['count'] > 0:
            print(f"\n✅ CIBC Card Transactions Table:")
            print(f"  Transactions: {result['count']}")
            print(f"  Total Amount: ${result['total']:,.2f}")
            print(f"  Date Range: {result['first_date']} to {result['last_date']}")
        else:
            print("\n⚠️  No 2013 data in cibc_card_transactions table")
    except Exception as e:
        print(f"\n⚠️  cibc_card_transactions table error: {e}")
    
    # Check receipts for credit card expenses
    try:
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(gross_amount) as total
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2013
            AND category IN ('credit_card_payment', 'bank_fees')
        """)
        result = cur.fetchone()
        
        if result['count'] > 0:
            print(f"\n✅ Credit Card Payments in Receipts:")
            print(f"  Payments: {result['count']}")
            print(f"  Total: ${result['total']:,.2f}")
        else:
            print("\n⚠️  No credit card payment receipts found for 2013")
    except Exception as e:
        print(f"\n⚠️  Receipts query error: {e}")

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("2013 BANKING STATEMENT AUDIT")
    print("=" * 80)
    print("\nThis audit will:")
    print("  1. Verify running balances against transaction data")
    print("  2. Check for missing months or data gaps")
    print("  3. Identify duplicate transactions")
    print("  4. Check for Mastercard/credit card data")
    
    # Run audits
    balance_results = audit_banking_balances(cur)
    check_data_completeness(cur)
    check_duplicate_transactions(cur)
    check_mastercard_data(cur)
    
    # Final summary
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    
    total_errors = sum(r['balance_errors'] for r in balance_results)
    total_missing = sum(r['missing_balances'] for r in balance_results)
    
    if total_errors == 0 and total_missing == 0:
        print("\n✅ AUDIT PASSED - No balance discrepancies or missing data")
    else:
        print(f"\n⚠️  ISSUES FOUND:")
        if total_errors > 0:
            print(f"  - {total_errors} balance discrepancies")
        if total_missing > 0:
            print(f"  - {total_missing} transactions missing balance data")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
