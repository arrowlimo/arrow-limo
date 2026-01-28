"""
Verify CIBC monthly opening/closing balances and transaction totals for 2012.

Compares PDF statement totals against database records to identify discrepancies.

Usage:
    python verify_cibc_monthly_totals_2012.py
"""

import psycopg2
from decimal import Decimal
import os


def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )


# PDF statement data - from user's screenshots
PDF_MONTHLY_DATA = {
    '2012-01': {
        'opening': Decimal('7177.34'),
        'withdrawals': Decimal('54203.83'),
        'deposits': Decimal('46977.32'),
        'closing': Decimal('-49.17'),
        'account': '0228362'  # CIBC account 74-61615
    },
    '2012-02': {
        'opening': Decimal('-49.17'),
        'withdrawals': Decimal('36119.68'),
        'deposits': Decimal('37183.34'),
        'closing': Decimal('1014.49'),
        'account': '00339'  # CIBC Unlimited Business (mapped to 0228362)
    },
    '2012-03': {
        'opening': Decimal('1014.49'),
        'withdrawals': Decimal('36293.08'),
        'deposits': Decimal('36217.65'),
        'closing': Decimal('939.06'),
        'account': '00339'
    },
    '2012-04': {
        'opening': Decimal('939.06'),
        'withdrawals': Decimal('71528.80'),
        'deposits': Decimal('72146.76'),
        'closing': Decimal('1557.02'),
        'account': '0228362'
    }
}


def get_monthly_totals(cur, year_month, account_number):
    """
    Get monthly totals from database for given year-month.
    
    Returns: (total_debits, total_credits, first_balance, last_balance, count)
    """
    # Get all transactions for the month
    cur.execute("""
        SELECT 
            transaction_date,
            debit_amount,
            credit_amount,
            balance,
            transaction_id
        FROM banking_transactions
        WHERE account_number = %s
        AND DATE_TRUNC('month', transaction_date) = %s::date
        ORDER BY transaction_date, transaction_id
    """, (account_number, f"{year_month}-01"))
    
    transactions = cur.fetchall()
    
    if not transactions:
        return None, None, None, None, 0
    
    # Calculate totals
    total_debits = sum(Decimal(str(t[1] or 0)) for t in transactions)
    total_credits = sum(Decimal(str(t[2] or 0)) for t in transactions)
    
    # First and last balances
    first_balance = transactions[0][3] if transactions[0][3] is not None else None
    last_balance = transactions[-1][3] if transactions[-1][3] is not None else None
    
    return total_debits, total_credits, first_balance, last_balance, len(transactions)


def verify_monthly_totals():
    """Verify all monthly totals against PDF statements."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*120)
    print("CIBC MONTHLY TOTALS VERIFICATION - 2012")
    print("="*120)
    print("\nComparing PDF statement totals against database records...\n")
    
    all_match = True
    
    for year_month in sorted(PDF_MONTHLY_DATA.keys()):
        pdf_data = PDF_MONTHLY_DATA[year_month]
        account = pdf_data['account']
        
        # Map account 00339 to 0228362 for database lookup
        db_account = '0228362' if account == '00339' else account
        
        print(f"\n{'='*120}")
        print(f"MONTH: {year_month} | Account: {account}")
        print(f"{'='*120}")
        
        # Get database totals
        db_debits, db_credits, db_first_bal, db_last_bal, db_count = get_monthly_totals(
            cur, year_month, db_account
        )
        
        if db_count == 0:
            print(f"⚠️  WARNING: No transactions found in database for {year_month}")
            all_match = False
            continue
        
        # Display PDF data
        print(f"\n📄 PDF STATEMENT:")
        print(f"  Opening Balance:    ${pdf_data['opening']:>12,.2f}")
        print(f"  Withdrawals:        ${pdf_data['withdrawals']:>12,.2f}")
        print(f"  Deposits:           ${pdf_data['deposits']:>12,.2f}")
        print(f"  Closing Balance:    ${pdf_data['closing']:>12,.2f}")
        
        # Display database data
        print(f"\n💾 DATABASE RECORDS:")
        print(f"  Transaction Count:  {db_count:>15}")
        print(f"  First Balance:      ${db_first_bal:>12,.2f}" if db_first_bal else "  First Balance:      NULL")
        print(f"  Total Debits:       ${db_debits:>12,.2f}")
        print(f"  Total Credits:      ${db_credits:>12,.2f}")
        print(f"  Last Balance:       ${db_last_bal:>12,.2f}" if db_last_bal else "  Last Balance:       NULL")
        
        # Compare withdrawals (debits)
        withdrawal_diff = abs(pdf_data['withdrawals'] - db_debits)
        withdrawal_match = withdrawal_diff < Decimal('0.01')
        
        # Compare deposits (credits)
        deposit_diff = abs(pdf_data['deposits'] - db_credits)
        deposit_match = deposit_diff < Decimal('0.01')
        
        # Compare opening balance (first transaction balance)
        opening_match = False
        opening_diff = None
        if db_first_bal is not None:
            opening_diff = abs(pdf_data['opening'] - db_first_bal)
            opening_match = opening_diff < Decimal('0.01')
        
        # Compare closing balance (last transaction balance)
        closing_match = False
        closing_diff = None
        if db_last_bal is not None:
            closing_diff = abs(pdf_data['closing'] - db_last_bal)
            closing_match = closing_diff < Decimal('0.01')
        
        # Display comparison
        print(f"\n🔍 COMPARISON:")
        print(f"  Withdrawals: {'✅ MATCH' if withdrawal_match else f'❌ DIFF ${withdrawal_diff:,.2f}'}")
        print(f"  Deposits:    {'✅ MATCH' if deposit_match else f'❌ DIFF ${deposit_diff:,.2f}'}")
        
        if db_first_bal is not None:
            print(f"  Opening Bal: {'✅ MATCH' if opening_match else f'❌ DIFF ${opening_diff:,.2f}'}")
        else:
            print(f"  Opening Bal: ⚠️  NULL in database")
        
        if db_last_bal is not None:
            print(f"  Closing Bal: {'✅ MATCH' if closing_match else f'❌ DIFF ${closing_diff:,.2f}'}")
        else:
            print(f"  Closing Bal: ⚠️  NULL in database")
        
        # Check balance continuity
        if year_month == '2012-02':
            # February opening should match January closing
            jan_closing = PDF_MONTHLY_DATA['2012-01']['closing']
            feb_opening = pdf_data['opening']
            continuity_match = abs(jan_closing - feb_opening) < Decimal('0.01')
            print(f"\n  Balance Continuity (Jan→Feb): {'✅ MATCH' if continuity_match else '❌ MISMATCH'}")
        elif year_month == '2012-03':
            # March opening should match February closing
            feb_closing = PDF_MONTHLY_DATA['2012-02']['closing']
            mar_opening = pdf_data['opening']
            continuity_match = abs(feb_closing - mar_opening) < Decimal('0.01')
            print(f"\n  Balance Continuity (Feb→Mar): {'✅ MATCH' if continuity_match else '❌ MISMATCH'}")
        elif year_month == '2012-04':
            # April opening should match March closing
            mar_closing = PDF_MONTHLY_DATA['2012-03']['closing']
            apr_opening = pdf_data['opening']
            continuity_match = abs(mar_closing - apr_opening) < Decimal('0.01')
            print(f"\n  Balance Continuity (Mar→Apr): {'✅ MATCH' if continuity_match else '❌ MISMATCH'}")
        
        if not (withdrawal_match and deposit_match and opening_match and closing_match):
            all_match = False
    
    # Summary
    print(f"\n{'='*120}")
    print("SUMMARY")
    print(f"{'='*120}")
    
    if all_match:
        print("✅ All monthly totals and balances MATCH between PDF statements and database!")
    else:
        print("❌ Discrepancies found between PDF statements and database")
        print("\nPossible causes:")
        print("  1. Missing transactions in database")
        print("  2. Duplicate transactions in database")
        print("  3. Incorrect balance calculations")
        print("  4. Account number mapping issues (00339 vs 0228362)")
    
    cur.close()
    conn.close()


def main():
    verify_monthly_totals()


if __name__ == '__main__':
    main()
