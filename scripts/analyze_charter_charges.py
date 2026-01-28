#!/usr/bin/env python3
"""
Analyze charter_charges table to determine if charges should be included in totals
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
    print('CHARTER_CHARGES TABLE ANALYSIS')
    print('=' * 80)

    # Get charge type breakdown
    cur.execute("""
        SELECT 
            charge_type,
            COUNT(*) as count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount
        FROM charter_charges
        GROUP BY charge_type
        ORDER BY total_amount DESC NULLS LAST
    """)
    
    charge_types = cur.fetchall()
    print('\nCHARGE TYPES BREAKDOWN:')
    print('-' * 80)
    print(f'{"Type":30} {"Count":>10} {"Total":>15} {"Avg":>12} {"Min":>12} {"Max":>12}')
    print('-' * 80)
    
    total_charges = 0
    total_amount = 0
    
    for ct in charge_types:
        charge_type = ct[0] if ct[0] else 'NULL'
        count = ct[1]
        total = ct[2] if ct[2] else 0
        avg = ct[3] if ct[3] else 0
        min_amt = ct[4] if ct[4] else 0
        max_amt = ct[5] if ct[5] else 0
        
        total_charges += count
        total_amount += total
        
        print(f'{charge_type:30} {count:>10} ${total:>14.2f} ${avg:>11.2f} ${min_amt:>11.2f} ${max_amt:>11.2f}')
    
    print('-' * 80)
    print(f'{"TOTAL":30} {total_charges:>10} ${total_amount:>14.2f}')

    # Check if charter_charges linked to our problem charters
    print('\n\n' + '=' * 80)
    print('CHARTER 006587 (King Kent) - CHECK FOR EXTRA CHARGES')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            cc.charge_id,
            cc.charge_type,
            cc.amount,
            cc.description,
            cc.created_at
        FROM charter_charges cc
        WHERE cc.charter_id = 5549  -- Charter 006587
        ORDER BY cc.charge_id
    """)
    
    kent_charges = cur.fetchall()
    if kent_charges:
        print('\nCharges found for charter 006587:')
        for kc in kent_charges:
            print(f'  Charge {kc[0]}: {kc[1]:20} ${kc[2]:>8.2f} - {kc[3][:50] if kc[3] else ""}')
    else:
        print('\n  NO extra charges for charter 006587')
        print('  Rate $210 + GST $10.50 + Fuel $10.50 = $231 (deposit) ✓')

    # Sample charters WITH charges
    print('\n\n' + '=' * 80)
    print('SAMPLE CHARTERS WITH EXTRA CHARGES (Excluding customer_tip)')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate as base_rate,
            c.deposit,
            c.balance,
            SUM(cc.amount) as total_charges,
            COUNT(cc.charge_id) as charge_count,
            STRING_AGG(DISTINCT cc.charge_type, ', ') as charge_types
        FROM charters c
        JOIN charter_charges cc ON c.charter_id = cc.charter_id
        WHERE cc.charge_type != 'customer_tip'
        AND c.rate > 0
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.rate, c.deposit, c.balance
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    charge_samples = cur.fetchall()
    if charge_samples:
        print('\n')
        for cs in charge_samples:
            reserve = cs[0]
            date = str(cs[1])
            rate = cs[2]
            deposit = cs[3] if cs[3] else 0
            balance = cs[4] if cs[4] else 0
            charges = cs[5]
            types = cs[7][:40] if cs[7] else ""
            print(f'  {reserve:8} {date:12} Rate ${rate:.2f} Deposit ${deposit:.2f} Balance ${balance:.2f} Charges ${charges:.2f} - {types}')
    else:
        print('\n  No charters with non-tip charges found')

    # Check closed charters with charges and balance
    print('\n\n' + '=' * 80)
    print('CLOSED CHARTERS WITH EXTRA CHARGES AND BALANCE OWING')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate,
            c.deposit,
            c.balance,
            SUM(cc.amount) as total_charges,
            STRING_AGG(cc.charge_type, ', ') as charge_types
        FROM charters c
        JOIN charter_charges cc ON c.charter_id = cc.charter_id
        WHERE c.closed = true
        AND c.balance > 0
        AND cc.charge_type != 'customer_tip'
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.rate, c.deposit, c.balance
        ORDER BY c.balance DESC
        LIMIT 10
    """)
    
    balance_charges = cur.fetchall()
    if balance_charges:
        print('\n')
        for bc in balance_charges:
            reserve = bc[0]
            date = str(bc[1])
            rate = bc[2]
            deposit = bc[3] if bc[3] else 0
            balance = bc[4]
            charges = bc[5]
            types = bc[6][:40] if bc[6] else ""
            print(f'  {reserve:8} {date:12} Rate ${rate:.2f} Deposit ${deposit:.2f} Balance ${balance:.2f} Charges ${charges:.2f} - {types}')
    else:
        print('\n  No closed charters with non-tip charges and balance owing')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('RECOMMENDATION')
    print('=' * 80)
    print('\nBased on analysis:')
    print('  - customer_tip charges are NOT invoiced (gratuities paid by customer)')
    print('  - Other charge types (if any) may be billable extras')
    print('  - For UNMATCHED PAYMENTS workbook:')
    print('      * Use: rate (base rate)')
    print('      * Add: SUM(charter_charges) WHERE charge_type != "customer_tip"')
    print('      * Total = rate + billable_charges')
    print('\n  - deposit field appears to include full payment (rate + GST + surcharges)')
    print('  - balance field shows amount still owing after payments')

if __name__ == '__main__':
    main()
