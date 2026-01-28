#!/usr/bin/env python3
"""
Re-check matched and balanced charters with CORRECT formula (no double-counting)
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

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print('=' * 80)
    print('CHARTER MATCHING AND BALANCE ANALYSIS (CORRECTED FORMULA)')
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

    without_payments = total_charters - with_payments

    # Charters that are BALANCED (CORRECT formula)
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance = 0
        AND COALESCE(c.deposit, 0) >= GREATEST(c.rate, COALESCE(
            (SELECT SUM(amount) 
             FROM charter_charges cc 
             WHERE cc.charter_id = c.charter_id 
             AND cc.charge_type != 'customer_tip'),
            0
        )) + COALESCE(c.driver_gratuity, 0)
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
        AND COALESCE(c.deposit, 0) >= GREATEST(c.rate, COALESCE(
            (SELECT SUM(amount) 
             FROM charter_charges cc 
             WHERE cc.charter_id = c.charter_id 
             AND cc.charge_type != 'customer_tip'),
            0
        )) + COALESCE(c.driver_gratuity, 0)
    """)
    matched_and_balanced = cur.fetchone()[0]

    # Charters WITH payments but NOT balanced
    matched_not_balanced = with_payments - matched_and_balanced

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

    # Financial totals (CORRECT formula)
    cur.execute("""
        SELECT 
            SUM(GREATEST(c.rate, COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) + COALESCE(c.driver_gratuity, 0)) as total_invoice,
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

    print('\n\nFINANCIAL TOTALS (CORRECTED):')
    print('-' * 80)
    print(f'Total Invoice Amount (all charters):  ${total_invoice:,.2f}')
    print(f'Total Paid (deposits):                ${total_paid:,.2f}')
    print(f'Total Balance Owing:                  ${total_owing:,.2f}')
    print(f'Payment Rate:                         {total_paid/total_invoice*100:.1f}%' if total_invoice > 0 else 'N/A')

    # Compare to LMS
    print('\n\nCOMPARISON TO LMS:')
    print('-' * 80)
    print('LMS Total Rate:        $5,050,631')
    print('LMS Total Deposit:     $9,435,676')
    print('LMS Total Balance:       $116,331')
    print('LMS Payment Rate:           186.8%')
    print()
    print(f'PG Total Invoice:      ${total_invoice:,.2f}')
    print(f'PG Total Deposit:      ${total_paid:,.2f}')
    print(f'PG Total Balance:        ${total_owing:,.2f}')
    print(f'PG Payment Rate:           {total_paid/total_invoice*100:.1f}%')
    print()
    if abs(total_invoice - 5050631) / 5050631 < 0.05:
        print('✓ Invoice totals now match LMS within 5%!')
    else:
        print('[WARN]  Invoice totals still differ from LMS')

    cur.close()
    conn.close()

    print('\n' + '=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'{matched_and_balanced:,} out of {total_charters:,} charters ({matched_and_balanced/total_charters*100:.1f}%) are')
    print('properly MATCHED (have payments) AND BALANCED (fully paid)')

if __name__ == '__main__':
    main()
