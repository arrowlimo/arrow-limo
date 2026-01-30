#!/usr/bin/env python3
"""
Investigate the massive credit discrepancies for specific reserves.
Compare LMS totals vs PostgreSQL totals to find root cause.
"""

import psycopg2
import os
import pyodbc

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_lms_connection():
    LMS_PATH = r'L:\limo\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def investigate_reserve(reserve_number):
    """Deep dive into a specific reserve's payments."""
    
    print("=" * 80)
    print(f"RESERVE {reserve_number} - DEEP INVESTIGATION")
    print("=" * 80)
    
    # PostgreSQL data
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    # Charter details
    pg_cur.execute("""
        SELECT 
            charter_date,
            total_amount_due,
            paid_amount,
            balance,
            deposit
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_number,))
    
    charter = pg_cur.fetchone()
    if charter:
        print(f"\nPostgreSQL Charter:")
        print(f"  Date: {charter[0]}")
        print(f"  Total Due: ${charter[1]:,.2f}")
        print(f"  Paid Amount: ${charter[2]:,.2f}")
        print(f"  Balance: ${charter[3]:,.2f}")
        print(f"  Deposit: ${charter[4]:,.2f}")
    else:
        print(f"\n✗ Charter not found in PostgreSQL")
        return
    
    # LMS data
    try:
        lms_conn = get_lms_connection()
        lms_cur = lms_conn.cursor()
        
        lms_cur.execute("""
            SELECT Rate, Balance, Deposit
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve_number,))
        
        lms_data = lms_cur.fetchone()
        if lms_data:
            print(f"\nLMS Charter:")
            print(f"  Rate: ${lms_data[0]:,.2f}")
            print(f"  Balance: ${lms_data[1]:,.2f}")
            print(f"  Deposit: ${lms_data[2]:,.2f}")
        else:
            print(f"\n✗ Charter not found in LMS")
        
        lms_cur.close()
        lms_conn.close()
    except Exception as e:
        print(f"\n⚠ Could not access LMS: {e}")
    
    # PostgreSQL payments
    print(f"\n{'=' * 80}")
    print(f"PostgreSQL Payments for {reserve_number}:")
    print(f"{'=' * 80}")
    
    pg_cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            payment_key,
            square_transaction_id,
            notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
    """, (reserve_number,))
    
    payments = pg_cur.fetchall()
    print(f"\nTotal payments: {len(payments)}")
    
    if payments:
        print(f"\n{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Method':<15} {'Batch':<10} {'Square':<10}")
        print("-" * 80)
        
        total = 0
        batch_payments = {}
        square_payments = []
        standalone_payments = []
        
        for p in payments:
            pid, pdate, amt, method, pkey, sq_txn, notes = p
            total += amt
            
            batch_key = pkey if pkey else "None"
            square_marker = "YES" if sq_txn else "No"
            
            print(f"{pid:<12} {str(pdate):<12} ${amt:<11,.2f} {str(method):<15} {batch_key:<10} {square_marker:<10}")
            
            # Categorize
            if pkey:
                if pkey not in batch_payments:
                    batch_payments[pkey] = []
                batch_payments[pkey].append((pid, amt))
            elif sq_txn:
                square_payments.append((pid, amt, pdate))
            else:
                standalone_payments.append((pid, amt, pdate))
        
        print(f"\n{'Total Paid (PostgreSQL):':<30} ${total:,.2f}")
        print(f"{'Expected (total_due):':<30} ${charter[1]:,.2f}")
        print(f"{'Discrepancy:':<30} ${total - charter[1]:,.2f}")
        
        # Analysis
        print(f"\n{'=' * 80}")
        print(f"PAYMENT BREAKDOWN:")
        print(f"{'=' * 80}")
        
        if batch_payments:
            print(f"\nPayments in BATCHES:")
            for batch_key, pmts in batch_payments.items():
                batch_total = sum(amt for _, amt in pmts)
                print(f"  Batch {batch_key}: {len(pmts)} payments = ${batch_total:,.2f}")
        
        if square_payments:
            print(f"\nSquare payments (no batch): {len(square_payments)} payments = ${sum(amt for _, amt, _ in square_payments):,.2f}")
        
        if standalone_payments:
            print(f"\nStandalone payments (no batch, no Square): {len(standalone_payments)} payments = ${sum(amt for _, amt, _ in standalone_payments):,.2f}")
        
        # Check for duplicates
        print(f"\n{'=' * 80}")
        print(f"DUPLICATE ANALYSIS:")
        print(f"{'=' * 80}")
        
        # Group by amount
        from collections import defaultdict
        by_amount = defaultdict(list)
        for p in payments:
            by_amount[p[2]].append(p)
        
        duplicates_found = False
        for amount, pmts in by_amount.items():
            if len(pmts) > 1:
                duplicates_found = True
                print(f"\n${amount:,.2f} appears {len(pmts)} times:")
                for p in pmts:
                    pid, pdate, amt, method, pkey, sq_txn, notes = p
                    source = "BATCH" if pkey else ("SQUARE" if sq_txn else "STANDALONE")
                    print(f"  Payment {pid}: {pdate} ({source})")
        
        if not duplicates_found:
            print("\n✓ No duplicate amounts found")
    
    else:
        print("\n✗ No payments found in PostgreSQL")
    
    pg_cur.close()
    pg_conn.close()

def main():
    reserves = ['005768', '002228']
    
    for reserve in reserves:
        investigate_reserve(reserve)
        print("\n")

if __name__ == '__main__':
    main()
