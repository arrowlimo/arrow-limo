#!/usr/bin/env python3
"""
Analyze LMS Payment Data Completeness
====================================

Analyzes payment data from LMS backup and PostgreSQL to ensure no missing data
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict

load_dotenv()

# Database connections
LMS_PATH = r'L:\limo\backups\lms.mdb'
PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def connect_lms():
    """Connect to LMS Access database"""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def connect_pg():
    """Connect to PostgreSQL database"""
    return psycopg2.connect(**PG_CONFIG)

def main():
    print('🔍 LMS PAYMENT DATA COMPLETENESS ANALYSIS')
    print('=' * 60)

    # Connect to both databases
    try:
        lms_conn = connect_lms()
        pg_conn = connect_pg()
        
        lms_cur = lms_conn.cursor()
        pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Analyze LMS Payment table structure and completeness
        print('📊 LMS PAYMENT TABLE ANALYSIS:')
        
        # Get LMS Payment table structure
        lms_cur.execute("SELECT * FROM Payment WHERE 1=0")  # Get structure without data
        lms_columns = [desc[0] for desc in lms_cur.description]
        print(f'   LMS Payment columns: {lms_columns}')
        
        # Get total LMS payments
        lms_cur.execute("SELECT COUNT(*) FROM Payment")
        total_lms_payments = lms_cur.fetchone()[0]
        print(f'   📊 Total LMS payments: {total_lms_payments:,}')
        
        # Analyze LMS payment data completeness
        print(f'\n📋 LMS PAYMENT DATA COMPLETENESS:')
        
        # Check key fields
        key_fields = ['PaymentID', 'Amount', 'Account_No', 'Reserve_No', '[Key]', 'LastUpdated']
        for field in key_fields:
            if field in lms_columns:
                try:
                    if field == '[Key]':
                        lms_cur.execute(f"SELECT COUNT(*) FROM Payment WHERE [Key] IS NOT NULL")
                    else:
                        lms_cur.execute(f"SELECT COUNT(*) FROM Payment WHERE {field} IS NOT NULL")
                    non_null_count = lms_cur.fetchone()[0]
                    percentage = (non_null_count / total_lms_payments * 100) if total_lms_payments > 0 else 0
                    print(f'   {field:<15}: {non_null_count:>8,}/{total_lms_payments:,} ({percentage:>5.1f}%)')
                except Exception as e:
                    print(f'   {field:<15}: ERROR - {e}')
        
        # Analyze payment amounts - Use Access-compatible syntax
        print(f'\n💰 LMS PAYMENT AMOUNT ANALYSIS:')
        
        # Get basic stats separately for Access compatibility
        lms_cur.execute("SELECT COUNT(*) FROM Payment")
        total_payments = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT COUNT(*) FROM Payment WHERE Amount IS NOT NULL AND Amount <> 0")
        non_zero_amounts = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT SUM(Amount) FROM Payment WHERE Amount IS NOT NULL")
        total_amount = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT AVG(Amount) FROM Payment WHERE Amount IS NOT NULL")
        avg_amount = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT MIN(Amount) FROM Payment WHERE Amount IS NOT NULL")
        min_amount = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT MAX(Amount) FROM Payment WHERE Amount IS NOT NULL")
        max_amount = lms_cur.fetchone()[0]
        
        print(f'   Total payments: {total_payments:,}')
        print(f'   Non-zero amounts: {non_zero_amounts:,} ({non_zero_amounts/total_payments*100:.1f}%)')
        print(f'   Total amount: ${total_amount:,.2f}' if total_amount else '   Total amount: NULL')
        print(f'   Average amount: ${avg_amount:.2f}' if avg_amount else '   Average amount: NULL')
        print(f'   Amount range: ${min_amount:.2f} to ${max_amount:.2f}' if min_amount and max_amount else '   Amount range: NULL')
        
        # 2. Compare with PostgreSQL payments
        print(f'\n📊 POSTGRESQL PAYMENTS COMPARISON:')
        
        pg_cur.execute("SELECT COUNT(*) FROM payments")
        total_pg_payments = pg_cur.fetchone()['count']
        print(f'   📊 Total PostgreSQL payments: {total_pg_payments:,}')
        
        # PostgreSQL payment completeness
        pg_cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COUNT(CASE WHEN amount IS NOT NULL AND amount <> 0 THEN 1 END) as non_zero_amounts,
                SUM(amount) as total_amount,
                AVG(amount) as avg_amount,
                MIN(amount) as min_amount,
                MAX(amount) as max_amount,
                COUNT(CASE WHEN payment_key IS NOT NULL THEN 1 END) as with_payment_key,
                COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve_number,
                COUNT(CASE WHEN account_number IS NOT NULL THEN 1 END) as with_account_number
            FROM payments
        """)
        
        pg_stats = pg_cur.fetchone()
        total_pg = pg_stats['total_payments']
        non_zero_pg = pg_stats['non_zero_amounts'] 
        total_amt_pg = pg_stats['total_amount']
        avg_amt_pg = pg_stats['avg_amount']
        min_amt_pg = pg_stats['min_amount']
        max_amt_pg = pg_stats['max_amount']
        with_key = pg_stats['with_payment_key']
        with_reserve = pg_stats['with_reserve_number']
        with_account = pg_stats['with_account_number']
        
        print(f'   Non-zero amounts: {non_zero_pg:,} ({non_zero_pg/total_pg*100:.1f}%)')
        print(f'   Total amount: ${total_amt_pg:,.2f}' if total_amt_pg else '   Total amount: NULL')
        print(f'   Average amount: ${avg_amt_pg:.2f}' if avg_amt_pg else '   Average amount: NULL')
        print(f'   Amount range: ${min_amt_pg:.2f} to ${max_amt_pg:.2f}' if min_amt_pg and max_amt_pg else '   Amount range: NULL')
        print(f'   With payment_key: {with_key:,} ({with_key/total_pg*100:.1f}%)')
        print(f'   With reserve_number: {with_reserve:,} ({with_reserve/total_pg*100:.1f}%)')
        print(f'   With account_number: {with_account:,} ({with_account/total_pg*100:.1f}%)')
        
        # 3. Identify missing payments
        print(f'\n🔍 MISSING PAYMENT ANALYSIS:')
        
        # Get LMS payment keys
        lms_cur.execute("SELECT [Key], PaymentID, Amount, Account_No, Reserve_No FROM Payment WHERE [Key] IS NOT NULL")
        lms_payments = {}
        for row in lms_cur.fetchall():
            key, payment_id, amount, account, reserve = row
            lms_payments[str(key)] = {
                'payment_id': payment_id,
                'amount': amount,
                'account_no': account,
                'reserve_no': reserve
            }
        
        print(f'   LMS payments with keys: {len(lms_payments):,}')
        
        # Get PostgreSQL payment keys
        pg_cur.execute("SELECT payment_key, payment_id, amount, account_number, reserve_number FROM payments WHERE payment_key IS NOT NULL")
        pg_payments = {}
        for row in pg_cur.fetchall():
            key, payment_id, amount, account, reserve = row
            pg_payments[str(key)] = {
                'payment_id': payment_id,
                'amount': amount,
                'account_number': account,
                'reserve_number': reserve
            }
        
        print(f'   PostgreSQL payments with keys: {len(pg_payments):,}')
        
        # Find missing payments
        lms_only = set(lms_payments.keys()) - set(pg_payments.keys())
        pg_only = set(pg_payments.keys()) - set(lms_payments.keys())
        
        print(f'   🔴 In LMS but not PostgreSQL: {len(lms_only):,}')
        print(f'   🔴 In PostgreSQL but not LMS: {len(pg_only):,}')
        
        if lms_only:
            print(f'\n📝 SAMPLE MISSING FROM POSTGRESQL (first 10):')
            for i, key in enumerate(list(lms_only)[:10]):
                payment = lms_payments[key]
                print(f'      Key {key}: Amount ${payment["amount"]:.2f}, Account {payment["account_no"]}, Reserve {payment["reserve_no"]}')
        
        if pg_only:
            print(f'\n📝 SAMPLE EXTRA IN POSTGRESQL (first 10):')
            for i, key in enumerate(list(pg_only)[:10]):
                payment = pg_payments[key]
                amount_str = f"${float(payment['amount']):.2f}" if payment['amount'] else "NULL"
                print(f'      Key {key}: Amount {amount_str}, Account {payment["account_number"]}, Reserve {payment["reserve_number"]}')
        
        # 4. Check for data inconsistencies
        print(f'\n[WARN]  DATA CONSISTENCY CHECK:')
        
        common_keys = set(lms_payments.keys()) & set(pg_payments.keys())
        print(f'   Common payment keys: {len(common_keys):,}')
        
        inconsistencies = 0
        amount_differences = []
        
        for key in list(common_keys)[:100]:  # Check first 100 for performance
            lms_payment = lms_payments[key]
            pg_payment = pg_payments[key]
            
            # Check amount differences
            if lms_payment['amount'] and pg_payment['amount']:
                lms_amt = float(lms_payment['amount'])
                pg_amt = float(pg_payment['amount'])
                
                if abs(lms_amt - pg_amt) > 0.01:  # More than 1 cent difference
                    inconsistencies += 1
                    amount_differences.append({
                        'key': key,
                        'lms_amount': lms_amt,
                        'pg_amount': pg_amt,
                        'difference': abs(lms_amt - pg_amt)
                    })
        
        print(f'   Amount inconsistencies found: {inconsistencies}')
        
        if amount_differences:
            print(f'\n📝 SAMPLE AMOUNT DIFFERENCES:')
            for diff in amount_differences[:5]:
                print(f'      Key {diff["key"]}: LMS ${diff["lms_amount"]:.2f} vs PG ${diff["pg_amount"]:.2f} (diff: ${diff["difference"]:.2f})')
        
        # 5. Summary and recommendations
        print(f'\n📊 PAYMENT DATA COMPLETENESS SUMMARY:')
        print(f'   🎯 LMS Payment Records: {total_lms_payments:,}')
        print(f'   🎯 PostgreSQL Payment Records: {total_pg_payments:,}')
        print(f'   🎯 Data Coverage: {(len(common_keys)/max(len(lms_payments), len(pg_payments))*100):.1f}%')
        
        if len(lms_only) == 0 and len(pg_only) == 0:
            print(f'   [OK] Perfect synchronization - no missing payments')
        else:
            print(f'   [WARN]  Synchronization gaps detected')
            
        if inconsistencies == 0:
            print(f'   [OK] Amount data consistent')
        else:
            print(f'   [WARN]  {inconsistencies} amount inconsistencies found')
            
        print(f'\n[OK] Analysis completed successfully!')
        
    except Exception as e:
        print(f'[FAIL] Analysis failed: {e}')
        import traceback
        traceback.print_exc()
    finally:
        try:
            lms_conn.close()
            pg_conn.close()
        except:
            pass

if __name__ == "__main__":
    main()