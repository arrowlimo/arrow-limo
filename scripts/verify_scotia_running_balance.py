#!/usr/bin/env python3
"""
Verify Scotia Bank December 2013 running balances line-by-line.
This will show exactly where our data differs from the bank statement.
"""

import os
import psycopg2
from decimal import Decimal

ACCOUNT = '903990106011'

# Bank statement transactions with running balances from screenshots
# Format: (date, description, withdrawal, deposit, statement_balance)
STATEMENT_WITH_BALANCES = [
    ('2013-12-31', 'Overdraft Charge', 5.23, None, 6404.87),
    ('2013-12-31', 'Service Charge', 112.50, None, None),
    ('2013-12-31', 'Cheque 289', 492.26, None, None),
    ('2013-12-31', 'Cheque 288', 1706.25, None, None),
    ('2013-12-31', 'Debit Memo OTHER', 1200.00, None, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1868.50, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 830.00, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 67.52, 7222.61),
    ('2013-12-30', 'Bill Payment PC-SCOTIABANK VALUE VISA 39813660', 600.00, None, None),
    ('2013-12-30', 'Service Charge', 7.50, None, None),
    # Add more as we verify each section
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    print("\n" + "="*80)
    print("SCOTIA BANK DECEMBER 2013 RUNNING BALANCE VERIFICATION")
    print("="*80)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all December 2013 transactions from database in chronological order
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT,))
    
    db_transactions = cur.fetchall()
    
    print(f"\nDatabase has {len(db_transactions)} transactions")
    print(f"\nStatement ending balance: $6,404.87")
    
    # Calculate running balance from database
    # We need the opening balance first
    print(f"\n{'='*80}")
    print("NEED OPENING BALANCE")
    print(f"{'='*80}")
    print("Please provide the opening balance for December 1, 2013")
    print("(This should be the November 30, 2013 closing balance)")
    
    # For now, let's work backwards from the known ending balance
    print(f"\n{'='*80}")
    print("WORKING BACKWARDS FROM ENDING BALANCE")
    print(f"{'='*80}")
    
    ending_balance = Decimal('6404.87')
    total_debits = sum(Decimal(str(t[2] or 0)) for t in db_transactions)
    total_credits = sum(Decimal(str(t[3] or 0)) for t in db_transactions)
    
    calculated_opening = ending_balance - total_credits + total_debits
    
    print(f"Known ending balance: ${ending_balance:,.2f}")
    print(f"Total debits in DB: ${total_debits:,.2f}")
    print(f"Total credits in DB: ${total_credits:,.2f}")
    print(f"Calculated opening balance: ${calculated_opening:,.2f}")
    print(f"\nFormula: Opening = Ending - Credits + Debits")
    print(f"         Opening = {ending_balance} - {total_credits} + {total_debits}")
    print(f"         Opening = {calculated_opening}")
    
    # Now let's verify a few key transactions we can see in screenshots
    print(f"\n{'='*80}")
    print("KEY TRANSACTION VERIFICATION FROM SCREENSHOTS")
    print(f"{'='*80}")
    
    # December 30 - we can see balance of 7,222.61 in screenshot
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date = '2013-12-30'
        ORDER BY transaction_id
    """, (ACCOUNT,))
    
    dec30_txns = cur.fetchall()
    print(f"\nDecember 30 transactions in database: {len(dec30_txns)}")
    for txn in dec30_txns:
        date, desc, debit, credit = txn
        print(f"  {desc[:50]:<50} W:${float(debit or 0):>10,.2f} D:${float(credit or 0):>10,.2f}")
    
    dec30_debits = sum(Decimal(str(t[2] or 0)) for t in dec30_txns)
    dec30_credits = sum(Decimal(str(t[3] or 0)) for t in dec30_txns)
    
    print(f"\nDec 30 totals - Withdrawals: ${dec30_debits:,.2f}, Deposits: ${dec30_credits:,.2f}")
    print(f"Screenshot shows Dec 30 ending balance: $7,222.61")
    
    # Let's also check what the statement says for total withdrawals and deposits
    print(f"\n{'='*80}")
    print("STATEMENT TOTALS COMPARISON")
    print(f"{'='*80}")
    print(f"Statement shows: $59,578.37 withdrawals, $70,463.81 deposits")
    print(f"Database shows:  ${total_debits:,.2f} withdrawals, ${total_credits:,.2f} deposits")
    print(f"Missing:         ${Decimal('59578.37') - total_debits:,.2f} withdrawals, ${Decimal('70463.81') - total_credits:,.2f} deposits")
    
    # Show daily breakdown
    print(f"\n{'='*80}")
    print("DAILY TRANSACTION SUMMARY")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT 
            transaction_date,
            COUNT(*) as count,
            SUM(debit_amount) as debits,
            SUM(credit_amount) as credits
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        GROUP BY transaction_date
        ORDER BY transaction_date
    """, (ACCOUNT,))
    
    daily = cur.fetchall()
    
    print(f"\n{'Date':<12} {'Count':<6} {'Withdrawals':>15} {'Deposits':>15}")
    print("-" * 60)
    for date, count, debits, credits in daily:
        print(f"{date} {count:<6} ${float(debits or 0):>13,.2f} ${float(credits or 0):>13,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Verify the opening balance (calculated as ${:,.2f})".format(calculated_opening))
    print("2. Check specific dates where transactions might be missing")
    print("3. Look for merchant deposits that should be credits but might be missing")
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
