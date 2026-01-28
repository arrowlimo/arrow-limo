#!/usr/bin/env python3
"""
Search for RBC 9016 account patterns in 2012 banking data.
"""

import psycopg2

def search_rbc_patterns():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata', 
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    print('🔍 SEARCHING FOR RBC 9016 ACCOUNT PATTERNS IN 2012')
    print('=' * 60)

    # Check for various RBC 9016 patterns
    patterns = ['%9016%', '%RBC%']
    
    for pattern in patterns:
        cur.execute("""
            SELECT DISTINCT 
                account_number,
                COUNT(*) as count,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date,
                SUM(COALESCE(debit_amount, 0)) as debits,
                SUM(COALESCE(credit_amount, 0)) as credits
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND account_number LIKE %s
            GROUP BY account_number
            ORDER BY count DESC
        """, (pattern,))
        
        results = cur.fetchall()
        if results:
            print(f'\nPattern {pattern}:')
            for acc, count, first, last, debits, credits in results:
                print(f'  {acc}: {count} transactions, {first} to {last}')
                print(f'    Debits: ${debits:,.2f}, Credits: ${credits:,.2f}')
        else:
            print(f'\nPattern {pattern}: No matches found')

    # Check if main accounts have RBC indicators
    print(f'\n🏦 CHECKING FOR RBC INDICATORS IN MAIN ACCOUNTS:')
    cur.execute("""
        SELECT 
            account_number,
            COUNT(*) as total_transactions,
            COUNT(*) FILTER (WHERE LOWER(description) LIKE '%rbc%') as rbc_mentions,
            COUNT(*) FILTER (WHERE LOWER(description) LIKE '%royal%') as royal_mentions
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
          AND account_number IN ('0228362', '903990106011', '3648117')
        GROUP BY account_number
    """)

    main_accounts = cur.fetchall()
    for acc, total, rbc_count, royal_count in main_accounts:
        print(f'  Account {acc}: {total:,} transactions')
        print(f'    RBC mentions: {rbc_count}, Royal mentions: {royal_count}')
        
        if rbc_count > 0 or royal_count > 0:
            print(f'    *** POTENTIAL RBC ACCOUNT ***')

    # Check for credit card patterns (9016 might be last 4 of card)
    print(f'\n💳 CHECKING FOR CREDIT CARD 9016 PATTERNS:')
    cur.execute("""
        SELECT 
            account_number,
            COUNT(*) as total_matches,
            COUNT(*) FILTER (WHERE card_last4_detected = '9016') as exact_card_matches,
            string_agg(DISTINCT card_last4_detected, ', ') as detected_cards
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
          AND (card_last4_detected = '9016' 
               OR LOWER(description) LIKE '%9016%')
        GROUP BY account_number
    """)

    card_results = cur.fetchall()
    if card_results:
        for acc, total, exact, cards in card_results:
            print(f'  Account {acc}: {exact} exact 9016 matches')
            print(f'    All detected cards: {cards}')
    else:
        print('  No credit card 9016 patterns found')

    # Look for account numbers ending in 9016
    print(f'\n🔢 CHECKING ACCOUNT NUMBERS ENDING IN 9016:')
    cur.execute("""
        SELECT DISTINCT account_number, COUNT(*) as transaction_count
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
          AND account_number LIKE '%9016'
        GROUP BY account_number
        ORDER BY transaction_count DESC
    """)

    ending_9016 = cur.fetchall()
    if ending_9016:
        for acc, count in ending_9016:
            print(f'  {acc}: {count:,} transactions')
    else:
        print('  No accounts ending in 9016 found')

    # Show sample transactions from main accounts to identify bank
    print(f'\n📄 SAMPLE TRANSACTIONS TO IDENTIFY BANKS:')
    cur.execute("""
        SELECT 
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
          AND account_number IN ('0228362', '903990106011', '3648117')
          AND (LOWER(description) LIKE '%fee%' 
               OR LOWER(description) LIKE '%charge%'
               OR LOWER(description) LIKE '%bank%'
               OR LOWER(description) LIKE '%interest%')
        ORDER BY account_number, transaction_date
        LIMIT 15
    """)

    samples = cur.fetchall()
    current_account = None
    for acc, date, desc, debit, credit in samples:
        if acc != current_account:
            print(f'\n  Account {acc}:')
            current_account = acc
        amount = debit if debit else credit
        print(f'    {date}: {desc[:50]}... (${amount:.2f})')

    conn.close()

if __name__ == '__main__':
    search_rbc_patterns()