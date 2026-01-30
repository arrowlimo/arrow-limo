#!/usr/bin/env python3
"""
Quick Data Check for 2013-2015
==============================
"""

import psycopg2

def check_data_availability():
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    
    print('🔍 CHECKING DATA AVAILABILITY FOR 2013-2015')
    print('=' * 45)
    
    years = [2013, 2014, 2015]
    
    for year in years:
        print(f'\n📅 YEAR {year}:')
        
        # Check receipts
        cur.execute('SELECT COUNT(*) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = %s', (year,))
        receipt_count = cur.fetchone()[0]
        
        # Check payroll
        cur.execute('SELECT COUNT(*) FROM driver_payroll WHERE year = %s', (year,))
        payroll_count = cur.fetchone()[0]
        
        # Check banking
        cur.execute('SELECT COUNT(*) FROM banking_transactions WHERE EXTRACT(YEAR FROM transaction_date) = %s', (year,))
        banking_count = cur.fetchone()[0]
        
        print(f'  Receipts: {receipt_count:,}')
        print(f'  Payroll: {payroll_count:,}') 
        print(f'  Banking: {banking_count:,}')
        
        if receipt_count == 0 and payroll_count == 0 and banking_count == 0:
            print(f'  [WARN] No data found for {year}')
    
    # Check column structure for receipts table
    print(f'\n📋 RECEIPTS TABLE COLUMNS:')
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    for col, dtype in columns[:10]:  # Show first 10 columns
        print(f'  {col}: {dtype}')
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_data_availability()