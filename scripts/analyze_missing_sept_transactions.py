#!/usr/bin/env python
"""
Add missing September 2012 transactions to Scotia account.

User provided transactions from statement page break:
Last entry on previous page: OVERDRAFT INTEREST w 4.65, 112.5, 592.20, 64.93 908.15 d 3817.00 prior balance 987.72

Continuation (next page):
- w 53.41 (withdrawal)
- 1044.52 (deposit) 
- 330.75 (deposit)
- 4.81 (deposit)
- 66.00 (deposit)
- d 500 (withdrawal)
- w 1475.25 (withdrawal)
- 1900.5 (withdrawal)
- 2525.25 (withdrawal)
- d 1360.68 (withdrawal)
- 1600.00 (withdrawal)
- w 9.00 (withdrawal)
- Balance: 4927.53

These transactions bridge the $4.65 variance found on Sept 28.
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

ACCOUNT_NUMBER = "903990106011"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_current_sept_state():
    """Analyze current Sept data to understand what's there."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CURRENT SEPTEMBER 2012 STATE")
    print("=" * 100)
    
    # Get Sept transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND EXTRACT(MONTH FROM transaction_date) = 9
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT_NUMBER,))
    
    transactions = cur.fetchall()
    print(f"\nCurrent September transactions: {len(transactions)}")
    print("\nLast 5 transactions:")
    for txn in transactions[-5:]:
        txn_id, date, desc, debit, credit, balance = txn
        print(f"  {date} | {desc[:50]:50} | D: ${float(debit):>10,.2f} | C: ${float(credit):>10,.2f} | Balance: ${float(balance):>10,.2f}")
    
    if transactions:
        last_balance = float(transactions[-1][5])
        print(f"\nLast recorded balance (Sept): ${last_balance:,.2f}")
        print(f"User provided final balance: $4,927.53")
        print(f"Difference: ${4927.53 - last_balance:+,.2f}")
    
    cur.close()
    conn.close()

def parse_user_transactions():
    """Parse the transactions user provided."""
    # User provided text to parse
    # Format varies: "w 4.65" = withdrawal $4.65, "1044.52" = deposit $1,044.52, "d 500" = withdrawal $500
    
    transaction_strings = [
        ("w", "4.65", "OVERDRAFT INTEREST"),
        ("", "112.5", ""),
        ("", "592.20", ""),
        ("", "64.93", ""),
        ("d", "3817.00", "WITHDRAWAL"),  # d means debit/withdrawal
        # Page break - prior balance 987.72
        ("w", "53.41", "WITHDRAWAL"),
        ("", "1044.52", "DEPOSIT"),
        ("", "330.75", "DEPOSIT"),
        ("", "4.81", "DEPOSIT"),
        ("", "66.00", "DEPOSIT"),
        ("d", "500", "WITHDRAWAL"),
        ("w", "1475.25", "WITHDRAWAL"),
        ("", "1900.5", "WITHDRAWAL"),
        ("", "2525.25", "WITHDRAWAL"),
        ("d", "1360.68", "WITHDRAWAL"),
        ("", "1600.00", "WITHDRAWAL"),
        ("w", "9.00", "WITHDRAWAL"),
    ]
    
    # Parse into proper transaction objects
    # Need to determine if amount is withdrawal (w/d) or deposit (nothing specified)
    transactions = []
    
    # Amounts from user input - need to figure out which are debits vs credits
    amounts = [
        4.65, 112.5, 592.20, 64.93, 3817.00,  # From first line
        53.41, 1044.52, 330.75, 4.81, 66.00, 500, 1475.25, 1900.5, 2525.25, 1360.68, 1600.00, 9.00
    ]
    
    # User's indicators:
    # "w" = withdrawal
    # "d" = debit/withdrawal  
    # blank = deposit
    
    # Let me parse more carefully based on user's input
    # "w 4.65, 112.5, 592.20, 64.93 908.15 d 3817.00" - this is confusing, looks like it might be multiple entries
    
    # Let me ask user to clarify the exact transactions
    print("Parsed transaction amounts from user input:")
    for i, amt in enumerate(amounts):
        print(f"  {i+1}. ${amt:,.2f}")
    
    return amounts

def analyze_sept_gap():
    """Analyze the gap between current Sept state and user's final balance."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("SEPTEMBER GAP ANALYSIS")
    print("=" * 100)
    
    # Get current Sept 28 balance (closest to user's checkpoint)
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date <= '2012-09-28'
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    """, (ACCOUNT_NUMBER,))
    
    result = cur.fetchone()
    current_sept_balance = float(result[0]) if result else 0
    user_provided_balance = 3122.29  # User's checkpoint
    
    print(f"\nCurrent database (Sept 28): ${current_sept_balance:,.2f}")
    print(f"User's verified checkpoint: ${user_provided_balance:,.2f}")
    print(f"Difference: ${current_sept_balance - user_provided_balance:+,.2f}")
    
    # Parse user's transaction amounts and figure out net impact
    # Withdrawals reduce balance, deposits increase balance
    
    # From user input, trying to parse:
    # Last recorded: 987.72
    # User says these transactions happened:
    # w 53.41, 1044.52, 330.75, 4.81, 66.00, d 500, w 1475.25, 1900.5, 2525.25, d 1360.68, 1600.00, w 9.00
    # Final: 4927.53
    
    # This doesn't match the sequence. Let me ask user to clarify.
    
    cur.close()
    conn.close()

def main():
    analyze_current_sept_state()
    
    print("\n" + "=" * 100)
    print("PARSING USER-PROVIDED TRANSACTIONS")
    print("=" * 100)
    
    amounts = parse_user_transactions()
    
    analyze_sept_gap()
    
    print("\n" + "=" * 100)
    print("NEXT STEPS")
    print("=" * 100)
    print("""
The user provided transaction amounts but the format is ambiguous. 
Need clarification on:

1. Which amounts are withdrawals (w/d) vs deposits?
2. What are the descriptions for each?
3. What are the transaction dates (all Sept 28 or spread across dates)?
4. In what order should they be applied?

Current understanding:
- Prior balance: $987.72
- Final balance after all transactions: $4,927.53
- Net change: $+3,939.81

To add the missing $4.65 to match Sept 28 checkpoint of $3,122.29:
- Current database shows: $3,126.94
- Need to remove: $4.65

This suggests ONE transaction of $4.65 is duplicated or one transaction 
of $4.65 needs to be removed.
""")

if __name__ == '__main__':
    main()
