#!/usr/bin/env python3
"""
Show Flagged Records Analysis
============================

Shows records that would be flagged as not in LMS backup
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def main():
    print('🚩 FLAGGED RECORDS ANALYSIS')
    print('=' * 50)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            # Check what records would be flagged
            print('Records that would be flagged (in PostgreSQL but not in LMS):')
            
            # Show audit and reference records
            cur.execute("""
                SELECT reserve_number, client_id, charter_date, rate, balance, account_number
                FROM charters 
                WHERE reserve_number LIKE 'AUDIT%' OR reserve_number LIKE 'REF%'
                ORDER BY reserve_number
                LIMIT 20
            """)
            
            examples = cur.fetchall()
            if examples:
                print()
                print('Reserve#        Client ID    Date         Rate      Balance   Account#')
                print('-' * 75)
                for record in examples:
                    reserve_num = record[0] or 'None'
                    client_id = record[1] or 'None'
                    charter_date = record[2] or 'None'
                    rate = record[3] or 0
                    balance = record[4] or 0
                    account_num = record[5] or 'None'
                    print(f'{str(reserve_num):<14} {str(client_id):<12} {str(charter_date):<12} ${rate:>7.2f} ${balance:>9.2f} {str(account_num):<12}')
            
            # Show payment method breakdown
            print('\n💰 PAYMENT METHOD SUMMARY:')
            cur.execute("""
                SELECT payment_method, COUNT(*), SUM(amount), AVG(amount)
                FROM payments 
                WHERE payment_method IS NOT NULL
                GROUP BY payment_method
                ORDER BY COUNT(*) DESC
            """)
            
            payment_methods = cur.fetchall()
            print()
            print('Method           Count      Total Amount    Avg Amount')
            print('-' * 60)
            for pm in payment_methods:
                method = pm[0] or 'Unknown'
                count = pm[1]
                total = pm[2] or 0
                avg = pm[3] or 0
                print(f'{method:<15} {count:>8,} ${total:>12,.2f} ${avg:>10.2f}')
            
            # Show multi-charter payments
            print('\n🔄 MULTI-CHARTER PAYMENTS (Top 10):')
            cur.execute("""
                SELECT payment_key, COUNT(DISTINCT charter_id) as charter_count,
                       SUM(amount) as total_amount
                FROM payments 
                WHERE payment_key IS NOT NULL AND charter_id IS NOT NULL
                GROUP BY payment_key
                HAVING COUNT(DISTINCT charter_id) > 1
                ORDER BY charter_count DESC
                LIMIT 10
            """)
            
            multi_payments = cur.fetchall()
            if multi_payments:
                print()
                print('Payment Key    Charters    Total Amount')
                print('-' * 40)
                for mp in multi_payments:
                    print(f'{mp[0]:<12} {mp[1]:>8} ${mp[2]:>12,.2f}')
            
            print('\nNote: These are the records identified in the dry-run analysis.')
            print('The flagging has not been applied to the database yet.')

if __name__ == "__main__":
    main()