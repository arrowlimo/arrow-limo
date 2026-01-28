#!/usr/bin/env python3
"""
Compare charter balances between PostgreSQL and LMS Access database.
Verify if the balance sync issue exists in source LMS data or was introduced during migration.
"""

import psycopg2
import pyodbc

# Connect to LMS Access database
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

print("=" * 120)
print("COMPARING CHARTER BALANCES: PostgreSQL vs LMS.mdb")
print("=" * 120)

try:
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    pg_cur = pg_conn.cursor()
    
    # Get sample charter from LMS (006491 example)
    print("\nChecking LMS Reserve table for sample charter 006491:")
    print("-" * 120)
    
    try:
        lms_cur.execute("""
            SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, Pymt_Type
            FROM Reserve
            WHERE Reserve_No = '006491'
        """)
        
        lms_charter = lms_cur.fetchone()
        if lms_charter:
            reserve_no, account, pu_date, rate, balance, deposit, pymt_type = lms_charter
            print(f"\nLMS Data:")
            print(f"  Reserve_No: {reserve_no}")
            print(f"  Account_No: {account}")
            print(f"  PU_Date: {pu_date}")
            rate_val = rate if rate else 0
            balance_val = balance if balance else 0
            deposit_val = deposit if deposit else 0
            print(f"  Rate: ${rate_val:.2f}")
            print(f"  Balance: ${balance_val:.2f}")
            print(f"  Deposit: ${deposit_val:.2f}")
            print(f"  Pymt_Type: {pymt_type}")
        else:
            print("  Charter 006491 not found in LMS")
    except Exception as e:
        print(f"  Error querying LMS: {e}")
    
    # Get PostgreSQL data for comparison
    pg_cur.execute("""
        SELECT 
            reserve_number,
            account_number,
            charter_date,
            rate,
            balance,
            deposit,
            payment_status
        FROM charters
        WHERE reserve_number = '006491'
    """)
    
    pg_charter = pg_cur.fetchone()
    if pg_charter:
        print(f"\nPostgreSQL Data:")
        print(f"  reserve_number: {pg_charter[0]}")
        print(f"  account_number: {pg_charter[1]}")
        print(f"  charter_date: {pg_charter[2]}")
        print(f"  rate: ${pg_charter[3]:.2f if pg_charter[3] else 0}")
        print(f"  balance: ${pg_charter[4]:.2f if pg_charter[4] else 0}")
        print(f"  deposit: ${pg_charter[5]:.2f if pg_charter[5] else 0}")
        print(f"  payment_status: {pg_charter[6]}")
    
    # Get payments from LMS
    print("\n" + "=" * 120)
    print("LMS Payment Records for 006491:")
    print("-" * 120)
    
    try:
        lms_cur.execute("""
            SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated
            FROM Payment
            WHERE Reserve_No = '006491'
            ORDER BY LastUpdated
        """)
        
        lms_payments = lms_cur.fetchall()
        if lms_payments:
            print(f"{'PaymentID':<12} {'Account':<12} {'Reserve':<12} {'Amount':<12} {'Key':<12} {'Date':<20}")
            print("-" * 120)
            lms_total = 0
            for pay in lms_payments:
                pay_id, account, reserve, amount, key, date = pay
                lms_total += (amount if amount else 0)
                print(f"{pay_id or 'N/A':<12} {account or 'N/A':<12} {reserve or 'N/A':<12} ${amount or 0:>9.2f} {key or 'N/A':<12} {str(date) if date else 'N/A':<20}")
            print(f"\nLMS Total payments: ${lms_total:.2f}")
        else:
            print("  No payments found in LMS for this charter")
    except Exception as e:
        print(f"  Error querying LMS payments: {e}")
    
    # Check if LMS balance matches rate - payments
    if lms_charter and lms_payments:
        lms_rate = lms_charter[3] if lms_charter[3] else 0
        lms_balance = lms_charter[4] if lms_charter[4] else 0
        expected_balance = lms_rate - lms_total
        
        print("\n" + "=" * 120)
        print("LMS BALANCE CALCULATION CHECK")
        print("=" * 120)
        print(f"LMS Rate: ${lms_rate:.2f}")
        print(f"LMS Total Payments: ${lms_total:.2f}")
        print(f"Expected Balance (Rate - Payments): ${expected_balance:.2f}")
        print(f"LMS Stored Balance: ${lms_balance:.2f}")
        
        if abs(lms_balance - expected_balance) < 0.01:
            print("\n✓ LMS balance field MATCHES calculated balance")
            print("→ Balance sync issue was introduced during PostgreSQL migration or after")
        else:
            print("\n✗ LMS balance field does NOT match calculated balance")
            print(f"→ Difference: ${lms_balance - expected_balance:.2f}")
            print("→ Balance sync issue exists in original LMS database")
    
    # Sample comparison of multiple charters
    print("\n" + "=" * 120)
    print("SAMPLE COMPARISON (10 charters)")
    print("=" * 120)
    
    try:
        lms_cur.execute("""
            SELECT TOP 10 Reserve_No, Rate, Balance
            FROM Reserve
            WHERE PU_Date >= #2012-01-01# AND PU_Date < #2013-01-01#
            ORDER BY Reserve_No
        """)
        
        print(f"{'Reserve':<12} {'LMS Rate':<12} {'LMS Balance':<12} {'PG Balance':<12} {'Match':<10}")
        print("-" * 120)
        
        for lms_row in lms_cur.fetchall():
            reserve_no, lms_rate, lms_bal = lms_row
            
            # Get PG balance
            pg_cur.execute("SELECT balance FROM charters WHERE reserve_number = %s", (reserve_no,))
            pg_row = pg_cur.fetchone()
            pg_bal = pg_row[0] if pg_row else None
            
            if pg_bal is not None:
                match = "✓" if abs((lms_bal or 0) - pg_bal) < 0.01 else "✗"
                print(f"{reserve_no or 'N/A':<12} ${lms_rate or 0:>9.2f} ${lms_bal or 0:>10.2f} ${pg_bal:>10.2f} {match:<10}")
    except Exception as e:
        print(f"Error in comparison: {e}")
    
    lms_cur.close()
    lms_conn.close()
    pg_cur.close()
    pg_conn.close()
    
    print("\n" + "=" * 120)

except Exception as e:
    print(f"\nError connecting to LMS database: {e}")
    print("Make sure the LMS.mdb file exists at: L:\\limo\\backups\\lms.mdb")
