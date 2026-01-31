#!/usr/bin/env python3
"""
Check how many charters are properly matched and balanced
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print('=' * 80)
    print('CHARTER MATCHING AND BALANCE ANALYSIS')
    print('=' * 80)

    # Total non-cancelled charters
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE cancelled = false
        AND charter_date < CURRENT_DATE
    """)
    total_charters = cur.fetchone()[0]

    # Charters WITH payments linked
    cur.execute("""
        SELECT COUNT(DISTINCT c.charter_id)
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id 
            AND p.amount > 0
        )
    """)
    with_payments = cur.fetchone()[0]

    # Charters WITHOUT payments
    without_payments = total_charters - with_payments

    # Charters that are BALANCED (considering gratuity and charges)
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance = 0
        AND (
            -- Either no charges/gratuity, just rate
            (c.rate = 0 OR COALESCE(c.deposit, 0) >= c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ))
        )
    """)
    balanced = cur.fetchone()[0]

    # Charters WITH payments AND balanced
    cur.execute("""
        SELECT COUNT(DISTINCT c.charter_id)
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance = 0
        AND EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id 
            AND p.amount > 0
        )
        AND COALESCE(c.deposit, 0) >= c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
            (SELECT SUM(amount) 
             FROM charter_charges cc 
             WHERE cc.charter_id = c.charter_id 
             AND cc.charge_type != 'customer_tip'),
            0
        )
    """)
    matched_and_balanced = cur.fetchone()[0]

    # Charters WITH payments but NOT balanced
    cur.execute("""
        SELECT COUNT(DISTINCT c.charter_id)
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id 
            AND p.amount > 0
        )
        AND (
            c.balance > 0
            OR COALESCE(c.deposit, 0) < c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )
        )
    """)
    matched_not_balanced = cur.fetchone()[0]

    # Charters with balance = 0 but deposit doesn't match total
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance = 0
        AND COALESCE(c.deposit, 0) < c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
            (SELECT SUM(amount) 
             FROM charter_charges cc 
             WHERE cc.charter_id = c.charter_id 
             AND cc.charge_type != 'customer_tip'),
            0
        )
    """)
    balance_zero_deposit_short = cur.fetchone()[0]

    print('\nCHARTER STATISTICS:')
    print('-' * 80)
    print(f'Total Non-Cancelled Charters (past dates): {total_charters:,}')
    print()
    print(f'✓ Charters WITH payments linked:           {with_payments:,} ({with_payments/total_charters*100:.1f}%)')
    print(f'✗ Charters WITHOUT payments:               {without_payments:,} ({without_payments/total_charters*100:.1f}%)')
    print()
    print(f'✓ Charters BALANCED (balance = 0):         {balanced:,} ({balanced/total_charters*100:.1f}%)')
    print(f'✓ Matched AND Balanced:                    {matched_and_balanced:,} ({matched_and_balanced/total_charters*100:.1f}%)')
    print()
    print(f'[WARN]  Matched but NOT Balanced:                {matched_not_balanced:,} ({matched_not_balanced/total_charters*100:.1f}%)')
    print(f'[WARN]  Balance=0 but deposit < total:          {balance_zero_deposit_short:,} ({balance_zero_deposit_short/total_charters*100:.1f}%)')

    # Financial totals
    cur.execute("""
        SELECT 
            SUM(c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) as total_invoice,
            SUM(COALESCE(c.deposit, 0)) as total_paid,
            SUM(COALESCE(c.balance, 0)) as total_owing
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
    """)
    
    financial = cur.fetchone()
    total_invoice = financial[0] if financial[0] else 0
    total_paid = financial[1] if financial[1] else 0
    total_owing = financial[2] if financial[2] else 0

    print('\n\nFINANCIAL TOTALS:')
    print('-' * 80)
    print(f'Total Invoice Amount (all charters):  ${total_invoice:,.2f}')
    print(f'Total Paid (deposits):                ${total_paid:,.2f}')
    print(f'Total Balance Owing:                  ${total_owing:,.2f}')
    print(f'Payment Rate:                         {total_paid/total_invoice*100:.1f}%' if total_invoice > 0 else 'N/A')

    # Sample balanced charters
    print('\n\nSAMPLE MATCHED & BALANCED CHARTERS (latest 10):')
    print('-' * 80)
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate,
            COALESCE(c.driver_gratuity, 0) as gratuity,
            COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ) as charges,
            c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ) as total,
            COALESCE(c.deposit, 0) as deposit,
            c.balance,
            (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id) as payment_count
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance = 0
        AND EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id 
            AND p.amount > 0
        )
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    for s in samples:
        reserve = s[0]
        date = s[1]
        rate = s[2]
        gratuity = s[3]
        charges = s[4]
        total = s[5]
        deposit = s[6]
        balance = s[7]
        pay_count = s[8]
        
        status = '✓' if abs(total - deposit) < 0.01 else '[WARN]'
        print(f'{status} {reserve:8} {date} | Rate ${rate:.2f} + Grat ${gratuity:.2f} + Chrg ${charges:.2f} = ${total:.2f} | Deposit ${deposit:.2f} | {pay_count} payment(s)')

    cur.close()
    conn.close()

    print('\n' + '=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'{matched_and_balanced:,} out of {total_charters:,} charters ({matched_and_balanced/total_charters*100:.1f}%) are')
    print('properly MATCHED (have payments) AND BALANCED (fully paid)')

if __name__ == '__main__':
    main()
