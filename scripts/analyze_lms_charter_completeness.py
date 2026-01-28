#!/usr/bin/env python3
"""
Analyze LMS Charter/Reservation Data Completeness
================================================

Analyzes charter/reservation data from LMS backup and PostgreSQL to ensure no missing data
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
    print('🔍 LMS CHARTER/RESERVATION DATA COMPLETENESS ANALYSIS')
    print('=' * 70)

    try:
        lms_conn = connect_lms()
        pg_conn = connect_pg()
        
        lms_cur = lms_conn.cursor()
        pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Analyze LMS Reserve table structure and completeness
        print('📊 LMS RESERVE TABLE ANALYSIS:')
        
        # Get LMS Reserve table structure
        lms_cur.execute("SELECT * FROM Reserve WHERE 1=0")  # Get structure without data
        lms_columns = [desc[0] for desc in lms_cur.description]
        print(f'   LMS Reserve columns: {lms_columns}')
        
        # Get total LMS reservations
        lms_cur.execute("SELECT COUNT(*) FROM Reserve")
        total_lms_reserves = lms_cur.fetchone()[0]
        print(f'   📊 Total LMS reservations: {total_lms_reserves:,}')
        
        # Analyze LMS reserve data completeness
        print(f'\n📋 LMS RESERVE DATA COMPLETENESS:')
        
        # Check key fields (Access-compatible queries)
        key_fields = ['Reserve_No', 'Account_No', 'PU_Date', 'Rate', 'Balance', 'Name']
        for field in key_fields:
            if field in lms_columns:
                try:
                    lms_cur.execute(f"SELECT COUNT(*) FROM Reserve WHERE {field} IS NOT NULL")
                    non_null_count = lms_cur.fetchone()[0]
                    percentage = (non_null_count / total_lms_reserves * 100) if total_lms_reserves > 0 else 0
                    print(f'   {field:<15}: {non_null_count:>8,}/{total_lms_reserves:,} ({percentage:>5.1f}%)')
                except Exception as e:
                    print(f'   {field:<15}: ERROR - {e}')
        
        # Analyze reservation amounts and dates
        print(f'\n💰 LMS RESERVATION FINANCIAL ANALYSIS:')
        
        # Get basic stats separately for Access compatibility
        lms_cur.execute("SELECT COUNT(*) FROM Reserve")
        total_reserves = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT COUNT(*) FROM Reserve WHERE Rate IS NOT NULL AND Rate <> 0")
        non_zero_rates = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT SUM(Rate) FROM Reserve WHERE Rate IS NOT NULL")
        total_rate = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT AVG(Rate) FROM Reserve WHERE Rate IS NOT NULL")
        avg_rate = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT MIN(Rate) FROM Reserve WHERE Rate IS NOT NULL")
        min_rate = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT MAX(Rate) FROM Reserve WHERE Rate IS NOT NULL")
        max_rate = lms_cur.fetchone()[0]
        
        print(f'   Total reservations: {total_reserves:,}')
        print(f'   Non-zero rates: {non_zero_rates:,} ({non_zero_rates/total_reserves*100:.1f}%)')
        print(f'   Total rate value: ${total_rate:,.2f}' if total_rate else '   Total rate value: NULL')
        print(f'   Average rate: ${avg_rate:.2f}' if avg_rate else '   Average rate: NULL')
        print(f'   Rate range: ${min_rate:.2f} to ${max_rate:.2f}' if min_rate and max_rate else '   Rate range: NULL')
        
        # Balance analysis
        lms_cur.execute("SELECT SUM(Balance) FROM Reserve WHERE Balance IS NOT NULL")
        total_balance = lms_cur.fetchone()[0]
        
        lms_cur.execute("SELECT COUNT(*) FROM Reserve WHERE Balance IS NOT NULL AND Balance <> 0")
        non_zero_balance = lms_cur.fetchone()[0]
        
        print(f'   Total outstanding balance: ${total_balance:.2f}' if total_balance else '   Total balance: NULL')
        print(f'   Reservations with balance: {non_zero_balance:,} ({non_zero_balance/total_reserves*100:.1f}%)')
        
        # 2. Compare with PostgreSQL charters
        print(f'\n📊 POSTGRESQL CHARTERS COMPARISON:')
        
        pg_cur.execute("SELECT COUNT(*) FROM charters")
        total_pg_charters = pg_cur.fetchone()['count']
        print(f'   📊 Total PostgreSQL charters: {total_pg_charters:,}')
        
        # PostgreSQL charter completeness
        pg_cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                COUNT(CASE WHEN rate IS NOT NULL AND rate <> 0 THEN 1 END) as non_zero_rates,
                SUM(rate) as total_rate,
                AVG(rate) as avg_rate,
                MIN(rate) as min_rate,
                MAX(rate) as max_rate,
                COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve_number,
                COUNT(CASE WHEN account_number IS NOT NULL THEN 1 END) as with_account_number,
                COUNT(CASE WHEN client_id IS NOT NULL THEN 1 END) as with_client_id,
                SUM(balance) as total_balance,
                COUNT(CASE WHEN balance IS NOT NULL AND balance <> 0 THEN 1 END) as non_zero_balance
            FROM charters
        """)
        
        pg_stats = pg_cur.fetchone()
        
        print(f'   Non-zero rates: {pg_stats["non_zero_rates"]:,} ({pg_stats["non_zero_rates"]/pg_stats["total_charters"]*100:.1f}%)')
        print(f'   Total rate value: ${pg_stats["total_rate"]:.2f}' if pg_stats["total_rate"] else '   Total rate: NULL')
        print(f'   Average rate: ${pg_stats["avg_rate"]:.2f}' if pg_stats["avg_rate"] else '   Average rate: NULL')
        print(f'   Rate range: ${pg_stats["min_rate"]:.2f} to ${pg_stats["max_rate"]:.2f}' if pg_stats["min_rate"] and pg_stats["max_rate"] else '   Rate range: NULL')
        print(f'   With reserve_number: {pg_stats["with_reserve_number"]:,} ({pg_stats["with_reserve_number"]/pg_stats["total_charters"]*100:.1f}%)')
        print(f'   With account_number: {pg_stats["with_account_number"]:,} ({pg_stats["with_account_number"]/pg_stats["total_charters"]*100:.1f}%)')
        print(f'   With client_id: {pg_stats["with_client_id"]:,} ({pg_stats["with_client_id"]/pg_stats["total_charters"]*100:.1f}%)')
        print(f'   Total balance: ${pg_stats["total_balance"]:.2f}' if pg_stats["total_balance"] else '   Total balance: NULL')
        print(f'   With outstanding balance: {pg_stats["non_zero_balance"]:,} ({pg_stats["non_zero_balance"]/pg_stats["total_charters"]*100:.1f}%)')
        
        # 3. Identify missing reservations
        print(f'\n🔍 MISSING RESERVATION ANALYSIS:')
        
        # Get LMS reserve numbers
        lms_cur.execute("SELECT Reserve_No, Account_No, Rate, Balance, Name FROM Reserve WHERE Reserve_No IS NOT NULL")
        lms_reserves = {}
        for row in lms_cur.fetchall():
            reserve_no, account_no, rate, balance, name = row
            lms_reserves[str(reserve_no)] = {
                'account_no': account_no,
                'rate': rate,
                'balance': balance,
                'name': name
            }
        
        print(f'   LMS reservations with numbers: {len(lms_reserves):,}')
        
        # Get PostgreSQL reserve numbers
        pg_cur.execute("SELECT reserve_number, account_number, rate, balance, client_id FROM charters WHERE reserve_number IS NOT NULL")
        pg_reserves = {}
        for row in pg_cur.fetchall():
            reserve_no, account_no, rate, balance, client_id = row
            pg_reserves[str(reserve_no)] = {
                'account_number': account_no,
                'rate': rate,
                'balance': balance,
                'client_id': client_id
            }
        
        print(f'   PostgreSQL charters with numbers: {len(pg_reserves):,}')
        
        # Find missing reservations
        lms_only = set(lms_reserves.keys()) - set(pg_reserves.keys())
        pg_only = set(pg_reserves.keys()) - set(lms_reserves.keys())
        
        print(f'   🔴 In LMS but not PostgreSQL: {len(lms_only):,}')
        print(f'   🔴 In PostgreSQL but not LMS: {len(pg_only):,}')
        
        if lms_only:
            print(f'\n📝 SAMPLE MISSING FROM POSTGRESQL (first 10):')
            for i, reserve_no in enumerate(list(lms_only)[:10]):
                reserve = lms_reserves[reserve_no]
                try:
                    rate_str = f"${float(reserve['rate']):.2f}" if reserve['rate'] and str(reserve['rate']).replace('.','').replace('-','').isdigit() else "NULL"
                except (ValueError, TypeError):
                    rate_str = f"{reserve['rate']}" if reserve['rate'] else "NULL"
                try:
                    balance_str = f"${float(reserve['balance']):.2f}" if reserve['balance'] and str(reserve['balance']).replace('.','').replace('-','').isdigit() else "NULL"
                except (ValueError, TypeError):
                    balance_str = f"{reserve['balance']}" if reserve['balance'] else "NULL"
                print(f'      Reserve {reserve_no}: Rate {rate_str}, Balance {balance_str}, Account {reserve["account_no"]}, Name: {reserve["name"]}')
        
        if pg_only:
            print(f'\n📝 SAMPLE EXTRA IN POSTGRESQL (first 10):')
            for i, reserve_no in enumerate(list(pg_only)[:10]):
                reserve = pg_reserves[reserve_no]
                try:
                    rate_str = f"${float(reserve['rate']):.2f}" if reserve['rate'] and str(reserve['rate']).replace('.','').replace('-','').isdigit() else "NULL"
                except (ValueError, TypeError):
                    rate_str = f"{reserve['rate']}" if reserve['rate'] else "NULL"
                try:
                    balance_str = f"${float(reserve['balance']):.2f}" if reserve['balance'] and str(reserve['balance']).replace('.','').replace('-','').isdigit() else "NULL"
                except (ValueError, TypeError):
                    balance_str = f"{reserve['balance']}" if reserve['balance'] else "NULL"
                print(f'      Reserve {reserve_no}: Rate {rate_str}, Balance {balance_str}, Account {reserve["account_number"]}, Client ID: {reserve["client_id"]}')
        
        # 4. Check for data inconsistencies
        print(f'\n[WARN]  DATA CONSISTENCY CHECK:')
        
        common_reserves = set(lms_reserves.keys()) & set(pg_reserves.keys())
        print(f'   Common reservation numbers: {len(common_reserves):,}')
        
        rate_inconsistencies = 0
        balance_inconsistencies = 0
        inconsistency_samples = []
        
        for reserve_no in list(common_reserves)[:500]:  # Check first 500 for performance
            lms_reserve = lms_reserves[reserve_no]
            pg_reserve = pg_reserves[reserve_no]
            
            # Check rate differences
            if lms_reserve['rate'] and pg_reserve['rate']:
                lms_rate = float(lms_reserve['rate'])
                pg_rate = float(pg_reserve['rate'])
                
                if abs(lms_rate - pg_rate) > 0.01:  # More than 1 cent difference
                    rate_inconsistencies += 1
                    inconsistency_samples.append({
                        'reserve_no': reserve_no,
                        'type': 'rate',
                        'lms_value': lms_rate,
                        'pg_value': pg_rate,
                        'difference': abs(lms_rate - pg_rate)
                    })
            
            # Check balance differences
            if lms_reserve['balance'] and pg_reserve['balance']:
                lms_balance = float(lms_reserve['balance'])
                pg_balance = float(pg_reserve['balance'])
                
                if abs(lms_balance - pg_balance) > 0.01:
                    balance_inconsistencies += 1
                    inconsistency_samples.append({
                        'reserve_no': reserve_no,
                        'type': 'balance',
                        'lms_value': lms_balance,
                        'pg_value': pg_balance,
                        'difference': abs(lms_balance - pg_balance)
                    })
        
        print(f'   Rate inconsistencies found: {rate_inconsistencies}')
        print(f'   Balance inconsistencies found: {balance_inconsistencies}')
        
        if inconsistency_samples:
            print(f'\n📝 SAMPLE INCONSISTENCIES:')
            for inconsistency in inconsistency_samples[:5]:
                print(f'      Reserve {inconsistency["reserve_no"]} ({inconsistency["type"]}): LMS ${inconsistency["lms_value"]:.2f} vs PG ${inconsistency["pg_value"]:.2f} (diff: ${inconsistency["difference"]:.2f})')
        
        # 5. Date range analysis
        print(f'\n📅 DATE RANGE ANALYSIS:')
        
        # LMS date range
        lms_cur.execute("SELECT MIN(PU_Date), MAX(PU_Date) FROM Reserve WHERE PU_Date IS NOT NULL")
        lms_date_range = lms_cur.fetchone()
        if lms_date_range[0] and lms_date_range[1]:
            print(f'   LMS date range: {lms_date_range[0]} to {lms_date_range[1]}')
        
        # PostgreSQL date range
        pg_cur.execute("SELECT MIN(charter_date), MAX(charter_date) FROM charters WHERE charter_date IS NOT NULL")
        pg_date_range = pg_cur.fetchone()
        if pg_date_range['min'] and pg_date_range['max']:
            print(f'   PostgreSQL date range: {pg_date_range["min"]} to {pg_date_range["max"]}')
        
        # 6. Summary and recommendations
        print(f'\n📊 CHARTER/RESERVATION DATA SUMMARY:')
        print(f'   🎯 LMS Reserve Records: {total_lms_reserves:,}')
        print(f'   🎯 PostgreSQL Charter Records: {total_pg_charters:,}')
        print(f'   🎯 Data Coverage: {(len(common_reserves)/max(len(lms_reserves), len(pg_reserves))*100):.1f}%')
        
        if len(lms_only) == 0 and len(pg_only) == 0:
            print(f'   [OK] Perfect synchronization - no missing reservations')
        else:
            print(f'   [WARN]  Synchronization gaps detected')
            
        if rate_inconsistencies == 0 and balance_inconsistencies == 0:
            print(f'   [OK] Financial data consistent')
        else:
            print(f'   [WARN]  {rate_inconsistencies + balance_inconsistencies} financial inconsistencies found')
            
        print(f'\n[OK] Charter/Reservation analysis completed successfully!')
        
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