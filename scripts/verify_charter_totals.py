#!/usr/bin/env python3
"""
Verify correct financial totals for charters CSV
Check which columns should be used: rate, balance, deposit, paid_amount, total_amount_due
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
    print('CHARTERS TABLE FINANCIAL COLUMNS VERIFICATION')
    print('=' * 80)

    # Get financial column definitions
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'charters' 
        AND column_name IN ('rate', 'balance', 'deposit', 'paid_amount', 'total_amount_due')
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    print('\nFINANCIAL COLUMNS IN CHARTERS TABLE:')
    print('-' * 80)
    for col in columns:
        print(f'  {col[0]:20} {col[1]:20} Nullable: {col[2]}')

    # Sample some charters with different scenarios
    print('\n\n' + '=' * 80)
    print('SAMPLE CHARTERS - COMPARING TOTALS')
    print('=' * 80)

    # Charter 006587 (King Kent) - known example
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            rate,
            balance,
            deposit,
            paid_amount,
            total_amount_due,
            closed,
            (SELECT SUM(amount) FROM payments p WHERE p.charter_id = c.charter_id) as actual_payments
        FROM charters c
        WHERE reserve_number IN ('006587', '015808', '019672')
        ORDER BY charter_date
    """)
    
    samples = cur.fetchall()
    print('\nSAMPLE CHARTERS:')
    print('-' * 80)
    for s in samples:
        print(f'\nReserve: {s[0]} | Date: {s[1]} | Closed: {s[7]}')
        print(f'  rate:             ${s[2]:>10.2f}' if s[2] else '  rate:             $      NULL')
        print(f'  balance:          ${s[3]:>10.2f}' if s[3] else '  balance:          $      NULL')
        print(f'  deposit:          ${s[4]:>10.2f}' if s[4] else '  deposit:          $      NULL')
        print(f'  paid_amount:      ${s[5]:>10.2f}' if s[5] else '  paid_amount:      $      NULL')
        print(f'  total_amount_due: ${s[6]:>10.2f}' if s[6] else '  total_amount_due: $      NULL')
        print(f'  actual_payments:  ${s[8]:>10.2f}' if s[8] else '  actual_payments:  $      NULL')

    # Statistics on which columns are populated
    print('\n\n' + '=' * 80)
    print('COLUMN POPULATION STATISTICS')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(rate) as has_rate,
            COUNT(balance) as has_balance,
            COUNT(deposit) as has_deposit,
            COUNT(paid_amount) as has_paid_amount,
            COUNT(total_amount_due) as has_total_amount_due,
            SUM(CASE WHEN rate IS NOT NULL AND rate > 0 THEN 1 ELSE 0 END) as rate_nonzero,
            SUM(CASE WHEN balance IS NOT NULL AND balance > 0 THEN 1 ELSE 0 END) as balance_nonzero,
            SUM(CASE WHEN deposit IS NOT NULL AND deposit > 0 THEN 1 ELSE 0 END) as deposit_nonzero
        FROM charters
        WHERE cancelled = false
    """)
    
    stats = cur.fetchone()
    print(f'\nTotal Charters (non-cancelled): {stats[0]}')
    print(f'\nColumn Population:')
    print(f'  rate:             {stats[1]:>6} ({stats[1]/stats[0]*100:>5.1f}%) | Non-zero: {stats[6]:>6} ({stats[6]/stats[0]*100:>5.1f}%)')
    print(f'  balance:          {stats[2]:>6} ({stats[2]/stats[0]*100:>5.1f}%) | Non-zero: {stats[7]:>6} ({stats[7]/stats[0]*100:>5.1f}%)')
    print(f'  deposit:          {stats[3]:>6} ({stats[3]/stats[0]*100:>5.1f}%) | Non-zero: {stats[8]:>6} ({stats[8]/stats[0]*100:>5.1f}%)')
    print(f'  paid_amount:      {stats[4]:>6} ({stats[4]/stats[0]*100:>5.1f}%)')
    print(f'  total_amount_due: {stats[5]:>6} ({stats[5]/stats[0]*100:>5.1f}%)')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('RECOMMENDATION FOR CSV EXPORT')
    print('=' * 80)
    print('\nFor "unmatched charters" CSV, the CORRECT total to use is:')
    print('  ✓ rate - Base charter rate (what customer should pay)')
    print('  ✓ balance - Amount still owing')
    print('  ✓ deposit - Advance payment received')
    print('')
    print('INCORRECT columns (mostly NULL or unreliable):')
    print('  ✗ paid_amount - Rarely populated')
    print('  ✗ total_amount_due - Not consistently used')
    print('')
    print('BEST PRACTICE:')
    print('  Total Amount = rate')
    print('  Amount Owing = balance')
    print('  Amount Paid = (SELECT SUM(amount) FROM payments WHERE charter_id = c.charter_id)')
    print('')
    print('For charter 006587:')
    print('  rate = $210.00 (base rate)')
    print('  deposit = $231.00 (total paid including GST + fuel surcharge)')
    print('  balance = $0.00 (fully paid)')
    print('')
    print('The deposit field appears to include the FULL amount paid (rate + GST + fees).')

if __name__ == '__main__':
    main()
