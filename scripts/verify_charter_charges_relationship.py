#!/usr/bin/env python3
"""
Verify if charter_charges INCLUDES rate or ADDS to rate
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
    print('CHARTER_CHARGES: INCLUDES vs ADDS TO RATE?')
    print('=' * 80)

    # Charter 006587 detailed breakdown
    print('\nCHARTER 006587 (King Kent):')
    print('-' * 80)
    
    cur.execute("""
        SELECT rate, deposit, balance
        FROM charters
        WHERE charter_id = 5549
    """)
    
    charter = cur.fetchone()
    print(f'Charter Rate: ${charter[0]:.2f}')
    print(f'Charter Deposit: ${charter[1]:.2f}' if charter[1] else 'NULL')
    print(f'Charter Balance: ${charter[2]:.2f}' if charter[2] else 'NULL')
    
    cur.execute("""
        SELECT charge_type, amount, description
        FROM charter_charges
        WHERE charter_id = 5549
        ORDER BY charge_id
    """)
    
    charges = cur.fetchall()
    print(f'\nCharter_charges breakdown:')
    total_charges = 0
    for c in charges:
        print(f'  {c[0]:20} ${c[1]:>8.2f} - {c[2]}')
        total_charges += c[1]
    
    print(f'\nTotal charter_charges: ${total_charges:.2f}')
    print(f'Charter rate field: ${charter[0]:.2f}')
    print()
    
    if abs(total_charges - charter[1]) < 0.01:
        print(f'✓ charter_charges total (${total_charges:.2f}) = deposit (${charter[1]:.2f})')
        print('  This means charter_charges ALREADY INCLUDES everything!')
    else:
        print(f'✗ Mismatch: charges ${total_charges:.2f} != deposit ${charter[1]:.2f}')
    
    # Check multiple charters
    print('\n\n' + '=' * 80)
    print('SAMPLE ANALYSIS: Rate vs Charter_Charges')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.rate,
            c.deposit,
            COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ) as billable_charges,
            COALESCE(
                (SELECT COUNT(*) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ) as charge_count
        FROM charters c
        WHERE c.cancelled = false
        AND EXISTS (
            SELECT 1 FROM charter_charges cc 
            WHERE cc.charter_id = c.charter_id
        )
        ORDER BY c.charter_date DESC
        LIMIT 20
    """)
    
    samples = cur.fetchall()
    
    print(f'\n{"Reserve":8} {"Rate":>10} {"Deposit":>10} {"Charges":>10} {"Chrg Cnt":>8} {"Relationship"}')
    print('-' * 80)
    
    includes_count = 0
    adds_count = 0
    
    for s in samples:
        reserve = s[0]
        rate = s[1]
        deposit = s[2] if s[2] else 0
        charges = s[3]
        count = s[4]
        
        # Determine relationship
        if abs(charges - deposit) < 0.01:
            relationship = '✓ Charges = Deposit'
            includes_count += 1
        elif abs(charges - rate) < 0.01:
            relationship = '✓ Charges = Rate'
            includes_count += 1
        elif abs(charges + rate - deposit) < 0.01:
            relationship = '[WARN]  Rate + Charges = Deposit'
            adds_count += 1
        elif charges > rate:
            relationship = f'Charges > Rate (+${charges - rate:.2f})'
            includes_count += 1
        else:
            relationship = 'Other'
        
        print(f'{reserve:8} ${rate:>9.2f} ${deposit:>9.2f} ${charges:>9.2f} {count:>8} {relationship}')
    
    print('\n' + '=' * 80)
    print('CONCLUSION')
    print('=' * 80)
    print(f'\nCharters where charges INCLUDE rate: {includes_count}/20')
    print(f'Charters where charges ADD TO rate: {adds_count}/20')
    print()
    
    if includes_count > adds_count:
        print('✓ charter_charges INCLUDES the rate (not addition)')
        print('  Correct formula: Invoice = charter_charges + gratuity')
        print('  OR if no charges: Invoice = rate + gratuity')
    else:
        print('[WARN]  charter_charges ADDS TO rate')
        print('  Correct formula: Invoice = rate + charter_charges + gratuity')

    conn.close()

if __name__ == '__main__':
    main()
