#!/usr/bin/env python3
"""
Check for beverage and extra charge columns in charters table
Verify if rate includes all charges or if extras are separate
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
    print('BEVERAGE AND EXTRA CHARGES ANALYSIS')
    print('=' * 80)

    # Find beverage/charge related columns
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns 
        WHERE table_name = 'charters' 
        AND (column_name LIKE '%beverage%' 
             OR column_name LIKE '%charge%' 
             OR column_name LIKE '%extra%' 
             OR column_name LIKE '%fee%')
        ORDER BY column_name
    """)
    
    columns = cur.fetchall()
    print('\nBEVERAGE/CHARGE/FEE COLUMNS IN CHARTERS TABLE:')
    print('-' * 80)
    if columns:
        for col in columns:
            print(f'  {col[0]:40} {col[1]}')
    else:
        print('  No beverage/charge/fee columns found')

    # Check charter_charges table
    print('\n\n' + '=' * 80)
    print('CHECKING charter_charges TABLE')
    print('=' * 80)
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%charge%'
    """)
    
    charge_tables = cur.fetchall()
    if charge_tables:
        print('\nCHARGE-RELATED TABLES:')
        for t in charge_tables:
            print(f'  {t[0]}')
            
            # Get columns for charter_charges if it exists
            if t[0] == 'charter_charges':
                cur.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'charter_charges'
                    ORDER BY ordinal_position
                """)
                charge_cols = cur.fetchall()
                print(f'\n  Columns in charter_charges:')
                for cc in charge_cols:
                    print(f'    {cc[0]:30} {cc[1]}')
                
                # Sample data
                cur.execute("""
                    SELECT 
                        cc.charge_id,
                        cc.charter_id,
                        c.reserve_number,
                        cc.charge_type,
                        cc.amount,
                        cc.description
                    FROM charter_charges cc
                    JOIN charters c ON cc.charter_id = c.charter_id
                    ORDER BY cc.charge_id DESC
                    LIMIT 10
                """)
                samples = cur.fetchall()
                if samples:
                    print(f'\n  Sample charter_charges (latest 10):')
                    print('  ' + '-' * 76)
                    for s in samples:
                        print(f'    ID {s[0]} | Charter {s[2]} | {s[3]:20} | ${s[4]:>8.2f} | {s[5][:30] if s[5] else ""}')
    else:
        print('\n  No charge-related tables found')

    # Check for beverage_service column and sample data
    print('\n\n' + '=' * 80)
    print('BEVERAGE SERVICE ANALYSIS')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN beverage_service_required = true THEN 1 ELSE 0 END) as beverage_required,
            SUM(CASE WHEN beverage_service_required = false THEN 1 ELSE 0 END) as beverage_not_required
        FROM charters
        WHERE cancelled = false
    """)
    
    bev_stats = cur.fetchone()
    print(f'\nBeverage Service Statistics:')
    print(f'  Total Charters: {bev_stats[0]}')
    print(f'  Beverage Required: {bev_stats[1]} ({bev_stats[1]/bev_stats[0]*100:.1f}%)')
    print(f'  Beverage NOT Required: {bev_stats[2]} ({bev_stats[2]/bev_stats[0]*100:.1f}%)')

    # Sample charters with beverage service
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate,
            c.deposit,
            c.balance,
            c.beverage_service_required,
            cl.client_name
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.beverage_service_required = true
        AND c.rate > 0
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    bev_samples = cur.fetchall()
    if bev_samples:
        print(f'\n  Sample Charters WITH Beverage Service (latest 10):')
        print('  ' + '-' * 76)
        for s in bev_samples:
            print(f'  {s[0]} | {s[1]} | Rate ${s[2]:>7.2f} | Deposit ${s[3]:>7.2f if s[3] else 0:>7.2f} | {s[6][:30] if s[6] else "Unknown":30}')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('CONCLUSION')
    print('=' * 80)
    print('\nFor ACCURATE totals, we need to determine:')
    print('  1. Does "rate" include ALL charges (base + beverages + extras)?')
    print('  2. OR are beverages/extras tracked separately in charter_charges table?')
    print('  3. Does "deposit" include the full amount (rate + GST + surcharges + extras)?')
    print('')
    print('If charter_charges table exists with separate line items:')
    print('  Total Amount = rate + SUM(charter_charges.amount)')
    print('')
    print('If rate already includes everything:')
    print('  Total Amount = rate (as currently used)')

if __name__ == '__main__':
    main()
