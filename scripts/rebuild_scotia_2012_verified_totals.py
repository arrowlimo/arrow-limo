#!/usr/bin/env python
"""
Rebuild Scotia 2012 from verified statement totals.

Verified Statement Summary:
- Opening balance (Jan 1, 2012): $40.00
- Closing balance (Dec 31, 2012): $952.04
- Total debits: $51,004.12
- Total credits: $51,950.93

Current database has corrupted/inflated balances. 
This script will use the verified totals to identify and correct transactions.
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

VERIFIED_OPENING = 40.00
VERIFIED_CLOSING = 952.04
VERIFIED_DEBITS = 51004.12
VERIFIED_CREDITS = 51950.93

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_current_data():
    """Analyze current Scotia 2012 data vs verified totals."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("SCOTIA 2012 ANALYSIS - Current vs Verified")
    print("=" * 100)
    
    # Get current totals
    cur.execute("""
        SELECT 
            COUNT(*) as txn_count,
            COALESCE(SUM(COALESCE(debit_amount, 0)), 0) as total_debits,
            COALESCE(SUM(COALESCE(credit_amount, 0)), 0) as total_credits,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    txn_count, curr_debits, curr_credits, min_bal, max_bal, first_date, last_date = cur.fetchone()
    
    # Convert Decimal to float
    curr_debits = float(curr_debits)
    curr_credits = float(curr_credits)
    min_bal = float(min_bal) if min_bal else 0
    max_bal = float(max_bal) if max_bal else 0
    
    print(f"\nCurrent Database State:")
    print(f"  Transactions: {txn_count:,}")
    print(f"  Total debits: ${curr_debits:,.2f}")
    print(f"  Total credits: ${curr_credits:,.2f}")
    print(f"  Balance range: ${min_bal:,.2f} to ${max_bal:,.2f}")
    print(f"  Date range: {first_date} to {last_date}")
    
    print(f"\nVerified Statement State:")
    print(f"  Opening balance: ${VERIFIED_OPENING:,.2f}")
    print(f"  Closing balance: ${VERIFIED_CLOSING:,.2f}")
    print(f"  Total debits: ${VERIFIED_DEBITS:,.2f}")
    print(f"  Total credits: ${VERIFIED_CREDITS:,.2f}")
    print(f"  Net change: ${VERIFIED_CLOSING - VERIFIED_OPENING:+,.2f}")
    
    # Calculate expected closing from math
    expected_from_math = VERIFIED_OPENING + VERIFIED_CREDITS - VERIFIED_DEBITS
    
    print(f"\nVerification Math:")
    print(f"  Opening: ${VERIFIED_OPENING:,.2f}")
    print(f"  + Credits: ${VERIFIED_CREDITS:,.2f}")
    print(f"  - Debits: ${VERIFIED_DEBITS:,.2f}")
    print(f"  = Expected closing: ${expected_from_math:,.2f}")
    print(f"  = Actual closing: ${VERIFIED_CLOSING:,.2f}")
    print(f"  Match: {'✓ YES' if abs(expected_from_math - VERIFIED_CLOSING) < 0.01 else '✗ NO (data inconsistency)'}")
    
    print(f"\nDifferences from Current Database:")
    debit_diff = curr_debits - VERIFIED_DEBITS
    credit_diff = curr_credits - VERIFIED_CREDITS
    print(f"  Debits excess: ${debit_diff:+,.2f} ({debit_diff/VERIFIED_DEBITS*100:+.1f}%)")
    print(f"  Credits excess: ${credit_diff:+,.2f} ({credit_diff/VERIFIED_CREDITS*100:+.1f}%)")
    
    # Get first and last balance
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id LIMIT 1
    """)
    first_bal = cur.fetchone()
    first_bal = first_bal[0] if first_bal else None
    
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1
    """)
    last_bal = cur.fetchone()
    last_bal = last_bal[0] if last_bal else None
    
    print(f"\nDatabase Recorded Balances:")
    print(f"  First recorded: ${first_bal:,.2f} (verified should be: ${VERIFIED_OPENING:,.2f})")
    print(f"  Last recorded: ${last_bal:,.2f} (verified should be: ${VERIFIED_CLOSING:,.2f})")
    
    cur.close()
    conn.close()
    
    return {
        'txn_count': txn_count,
        'curr_debits': curr_debits,
        'curr_credits': curr_credits,
        'first_bal': first_bal,
        'last_bal': last_bal
    }

def recalculate_balances():
    """Recalculate all balances starting from verified opening."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("RECALCULATING BALANCES")
    print("=" * 100)
    
    # Get all transactions in order
    cur.execute("""
        SELECT transaction_id, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = cur.fetchall()
    
    # Convert Decimal to float for transaction amounts
    transactions = [(txn_id, float(debit) if debit else 0, float(credit) if credit else 0) 
                    for txn_id, debit, credit in transactions]
    
    # Recalculate balances
    running_balance = VERIFIED_OPENING
    updates = []
    
    for txn_id, debit, credit in transactions:
        # Apply transaction
        if debit:
            running_balance -= debit
        if credit:
            running_balance += credit
        
        updates.append((round(running_balance, 2), txn_id))
    
    # Apply all balance updates
    print(f"\nUpdating {len(updates):,} transaction balances...")
    
    for new_balance, txn_id in updates:
        cur.execute("""
            UPDATE banking_transactions
            SET balance = %s
            WHERE transaction_id = %s
        """, (new_balance, txn_id))
    
    conn.commit()
    
    # Verify final balance
    final_balance = updates[-1][0] if updates else VERIFIED_OPENING
    
    print(f"\nBalance Recalculation Results:")
    print(f"  Transactions updated: {len(updates):,}")
    print(f"  Calculated closing: ${final_balance:,.2f}")
    print(f"  Verified closing: ${VERIFIED_CLOSING:,.2f}")
    print(f"  Difference: ${final_balance - VERIFIED_CLOSING:+,.2f}")
    
    if abs(final_balance - VERIFIED_CLOSING) < 0.01:
        print(f"  ✓ PERFECT MATCH!")
    else:
        print(f"  ⚠ Mismatch of ${abs(final_balance - VERIFIED_CLOSING):,.2f}")
        print(f"    This suggests transactions may be missing or incorrect in source data.")
    
    cur.close()
    conn.close()
    
    return final_balance

def verify_final_state():
    """Verify final state matches verified statement."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("FINAL VERIFICATION")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as txn_count,
            COALESCE(SUM(COALESCE(debit_amount, 0)), 0) as total_debits,
            COALESCE(SUM(COALESCE(credit_amount, 0)), 0) as total_credits
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    txn_count, curr_debits, curr_credits = cur.fetchone()
    
    # Convert Decimal to float
    curr_debits = float(curr_debits)
    curr_credits = float(curr_credits)
    
    # Get first and last balance
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id LIMIT 1
    """)
    first_bal = cur.fetchone()[0]
    
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1
    """)
    last_bal = cur.fetchone()[0]
    
    print(f"\nFinal State:")
    print(f"  Transaction count: {txn_count:,} (source file had 786)")
    print(f"  Opening balance: ${first_bal:,.2f} (verified: ${VERIFIED_OPENING:,.2f})")
    print(f"  Closing balance: ${last_bal:,.2f} (verified: ${VERIFIED_CLOSING:,.2f})")
    print(f"  Total debits: ${curr_debits:,.2f} (verified: ${VERIFIED_DEBITS:,.2f})")
    print(f"  Total credits: ${curr_credits:,.2f} (verified: ${VERIFIED_CREDITS:,.2f})")
    
    # Check matches
    opening_ok = abs(first_bal - VERIFIED_OPENING) < 0.01
    closing_ok = abs(last_bal - VERIFIED_CLOSING) < 0.01
    debits_ok = abs(curr_debits - VERIFIED_DEBITS) < 1.00  # Allow $1 variance for rounding
    credits_ok = abs(curr_credits - VERIFIED_CREDITS) < 1.00
    
    print(f"\nVerification:")
    print(f"  {'✓' if opening_ok else '✗'} Opening balance matches")
    print(f"  {'✓' if closing_ok else '✗'} Closing balance matches")
    print(f"  {'✓' if debits_ok else '✗'} Total debits match (within $1)")
    print(f"  {'✓' if credits_ok else '✗'} Total credits match (within $1)")
    
    if opening_ok and closing_ok:
        print(f"\n✓ Scotia 2012 successfully rebuilt with verified balances!")
    else:
        print(f"\n⚠ Balances do not fully match verified statement.")
        print(f"  This may indicate missing or incorrect transactions in source data.")
    
    cur.close()
    conn.close()

def main():
    print("\nSCOTIA 2012 REBUILD FROM VERIFIED STATEMENT TOTALS")
    print("Account: 903990106011")
    print()
    
    # Step 1: Analyze
    analyze_current_data()
    
    # Step 2: Ask for confirmation
    print("\n" + "=" * 100)
    response = input("\nRecalculate all balances from verified opening of $40.00? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return
    
    # Step 3: Recalculate
    recalculate_balances()
    
    # Step 4: Verify
    verify_final_state()

if __name__ == '__main__':
    main()
