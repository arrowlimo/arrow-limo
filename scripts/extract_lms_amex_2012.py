#!/usr/bin/env python3
"""
Extract American Express cash receipts from LMS Deposit table for 2012.
Compare to the Cash Receipts Report screenshot.
"""

import pyodbc
from datetime import datetime

LMS_PATH = r'L:\limo\backups\lms.mdb'

def main():
    try:
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        
        print("=" * 100)
        print("LMS DEPOSIT TABLE - AMERICAN EXPRESS 2012")
        print("=" * 100)
        print()
        
        # Get American Express deposits from 2012
        cur.execute("""
            SELECT 
                [Date], 
                [Number], 
                [Key], 
                [Total],
                [Transact],
                [Type]
            FROM Deposit
            WHERE [Type] = 'American Express'
            AND [Date] >= #2012-01-01# 
            AND [Date] < #2012-02-01#
            ORDER BY [Date]
        """)
        
        deposits = cur.fetchall()
        
        print(f"American Express deposits in January 2012: {len(deposits)}")
        print()
        print(f"{'Date':<12} {'Number':<15} {'Key':<12} {'Total':<12} {'Transact':<10} {'Type':<20}")
        print("-" * 90)
        
        for date_val, number, key, total, transact, type_val in deposits:
            date_str = date_val.strftime('%Y-%m-%d') if date_val else 'N/A'
            number_str = str(number).strip() if number else ''
            key_str = str(key).strip() if key else ''
            total_val = float(total) if total else 0.0
            transact_str = str(transact).strip() if transact else ''
            type_str = str(type_val).strip() if type_val else ''
            
            print(f"{date_str:<12} {number_str:<15} {key_str:<12} ${total_val:<11.2f} {transact_str:<10} {type_str:<20}")
        
        # Now get full year 2012
        print()
        print("=" * 100)
        print("ALL AMERICAN EXPRESS 2012:")
        print("=" * 100)
        print()
        
        cur.execute("""
            SELECT COUNT(*), SUM([Total])
            FROM Deposit
            WHERE [Type] = 'American Express'
            AND [Date] >= #2012-01-01# 
            AND [Date] < #2013-01-01#
        """)
        
        count, total = cur.fetchone()
        print(f"Total American Express deposits in 2012: {count}")
        print(f"Total amount: ${float(total) if total else 0:,.2f}")
        print()
        
        # Check what fields link to Payment/Reserve tables
        print("=" * 100)
        print("DEPOSIT → PAYMENT LINKAGE:")
        print("=" * 100)
        print()
        
        # Check if Key field links to Payment table
        cur.execute("""
            SELECT TOP 10
                d.[Date],
                d.[Key],
                d.[Number],
                d.[Total],
                p.Account_No,
                p.Reserve_No,
                p.Amount
            FROM Deposit d
            LEFT JOIN Payment p ON d.[Key] = p.[Key]
            WHERE d.[Type] = 'American Express'
            AND d.[Date] >= #2012-01-01# 
            AND d.[Date] < #2012-02-01#
            ORDER BY d.[Date]
        """)
        
        print(f"{'Date':<12} {'Deposit Key':<12} {'Number':<12} {'Deposit $':<12} {'Account':<10} {'Reserve':<10} {'Payment $':<12}")
        print("-" * 90)
        
        for row in cur.fetchall():
            date_val, key, number, dep_total, account, reserve, pay_amount = row
            date_str = date_val.strftime('%Y-%m-%d') if date_val else 'N/A'
            key_str = str(key).strip() if key else ''
            number_str = str(number).strip() if number else ''
            dep_val = float(dep_total) if dep_total else 0.0
            account_str = str(account).strip() if account else ''
            reserve_str = str(reserve).strip() if reserve else ''
            pay_val = float(pay_amount) if pay_amount else 0.0
            
            print(f"{date_str:<12} {key_str:<12} {number_str:<12} ${dep_val:<11.2f} {account_str:<10} {reserve_str:<10} ${pay_val:<11.2f}")
        
        # Look for specific entries from screenshot
        print()
        print("=" * 100)
        print("MATCHING TO SCREENSHOT ENTRIES:")
        print("=" * 100)
        print()
        
        # Sample from screenshot: 2012-01-02, Account 01803, Reserve 005689, $517.50
        screenshot_samples = [
            ('2012-01-02', '01803', '005689', 517.50),
            ('2012-01-03', '02173', '005656', 267.50),
            ('2012-01-08', '02173', '005657', 472.50),
        ]
        
        for search_date, search_account, search_reserve, search_amount in screenshot_samples:
            # Look in Deposit table
            cur.execute("""
                SELECT d.[Date], d.[Key], d.[Number], d.[Total]
                FROM Deposit d
                WHERE d.[Date] = ?
                AND ABS(d.[Total] - ?) < 0.01
            """, (datetime.strptime(search_date, '%Y-%m-%d'), search_amount))
            
            deposit = cur.fetchone()
            if deposit:
                date_val, key, number, total = deposit
                print(f"[OK] Found deposit: {search_date}, Key={key}, Number={number}, ${float(total):.2f}")
                
                # Check if linked to Payment
                cur.execute("""
                    SELECT Account_No, Reserve_No, Amount
                    FROM Payment
                    WHERE [Key] = ?
                """, (key,))
                
                payment = cur.fetchone()
                if payment:
                    account, reserve, amount = payment
                    print(f"   → Linked to Payment: Account={account}, Reserve={reserve}, ${float(amount):.2f}")
                else:
                    print(f"   → No linked Payment record")
            else:
                print(f"[FAIL] Not found: {search_date}, ${search_amount:.2f}")
            print()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
