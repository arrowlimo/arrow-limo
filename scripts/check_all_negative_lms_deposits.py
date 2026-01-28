#!/usr/bin/env python3
"""
Check ALL negative LMS deposits to see if they match refunds in charter_refunds.
Theory: All negative deposit amounts should correspond to refunds (total was reduced).
"""

import psycopg2
import pyodbc
import os

def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def get_lms_connection():
    """Get LMS Access database connection."""
    LMS_PATH = r'L:\oldlms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_all_negative_deposits(lms_conn):
    """Get all deposits with negative totals from LMS."""
    cur = lms_conn.cursor()
    
    cur.execute("""
        SELECT [Number], [Date], [Key], [Total], [Type], [Transact]
        FROM Deposit
        WHERE [Total] < 0
        ORDER BY [Total]
    """)
    
    results = cur.fetchall()
    cur.close()
    return results

def find_reserve_from_key(lms_conn, key):
    """Find reserve number using the Key from Payment table."""
    cur = lms_conn.cursor()
    
    try:
        cur.execute("""
            SELECT TOP 1 Reserve_No, Account_No, Amount, LastUpdated
            FROM Payment
            WHERE [Key] = ?
        """, (key,))
        
        result = cur.fetchone()
        return result
    finally:
        cur.close()

def check_in_charter_refunds(pg_conn, amount, date_str):
    """Check if refund exists in charter_refunds by amount and date."""
    cur = pg_conn.cursor()
    
    try:
        # Use positive amount for comparison
        pos_amount = abs(amount)
        
        cur.execute("""
            SELECT 
                cr.id,
                cr.refund_date,
                cr.amount,
                cr.reserve_number,
                cr.charter_id,
                cr.description,
                EXTRACT(EPOCH FROM (cr.refund_date::timestamp - %s::timestamp)) / 86400 as days_diff
            FROM charter_refunds cr
            WHERE ABS(cr.amount - %s) < 0.01
            AND ABS(EXTRACT(EPOCH FROM (cr.refund_date::timestamp - %s::timestamp))) < 30 * 86400
            ORDER BY ABS(EXTRACT(EPOCH FROM (cr.refund_date::timestamp - %s::timestamp)))
            LIMIT 1
        """, (date_str, pos_amount, date_str, date_str))
        
        return cur.fetchone()
    finally:
        cur.close()

def main():
    pg_conn = get_db_connection()
    lms_conn = get_lms_connection()
    
    print("=" * 100)
    print("ALL NEGATIVE LMS DEPOSITS - REFUND MATCHING ANALYSIS")
    print("=" * 100)
    
    # Get all negative deposits
    negative_deposits = get_all_negative_deposits(lms_conn)
    
    print(f"\nTotal negative deposits found: {len(negative_deposits)}")
    total_negative_amount = sum(abs(float(d[3])) for d in negative_deposits if d[3])
    print(f"Total negative amount: ${total_negative_amount:,.2f}")
    print()
    
    found_with_reserve = 0
    found_in_refunds = 0
    not_found_in_refunds = 0
    
    # Sample first 20 for detailed analysis
    print("ANALYZING FIRST 20 NEGATIVE DEPOSITS:")
    print("=" * 100)
    
    for i, deposit in enumerate(negative_deposits[:20], 1):
        deposit_num, date, key, total, dep_type, transact = deposit
        amount = abs(float(total)) if total else 0
        
        print(f"\n{i}. Deposit #{deposit_num or 'N/A'}")
        print(f"   Date: {date}, Amount: ${amount:,.2f}")
        print(f"   Type: {dep_type or 'N/A'}, Transact: {transact or 'N/A'}")
        print(f"   Key: {key}")
        
        # Find reserve number
        if key:
            lms_payment = find_reserve_from_key(lms_conn, key)
            if lms_payment:
                reserve_no, account_no, pay_amount, last_updated = lms_payment
                print(f"   → LMS Reserve: {reserve_no}, Account: {account_no}")
                found_with_reserve += 1
                
                # Check in charter_refunds
                if date:
                    date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
                    pg_match = check_in_charter_refunds(pg_conn, total, date_str)
                    
                    if pg_match:
                        ref_id, ref_date, ref_amt, ref_reserve, ref_charter, ref_desc, days_diff = pg_match
                        status = "[OK] LINKED" if ref_reserve else "[WARN] UNLINKED"
                        print(f"   → charter_refunds: {status} (ID: {ref_id}, Reserve: {ref_reserve or 'N/A'})")
                        found_in_refunds += 1
                    else:
                        print(f"   → charter_refunds: [FAIL] NOT FOUND")
                        not_found_in_refunds += 1
            else:
                print(f"   → LMS Payment: [FAIL] NOT FOUND")
        else:
            print(f"   → No Key provided")
    
    # Summary statistics for all
    print(f"\n{'=' * 100}")
    print("OVERALL STATISTICS (All Negative Deposits):")
    print(f"{'=' * 100}")
    print(f"Total negative deposits: {len(negative_deposits)}")
    print(f"Total negative amount: ${total_negative_amount:,.2f}")
    print(f"\nFrom sample of 20:")
    print(f"  Found with reserve in LMS: {found_with_reserve}")
    print(f"  Found in charter_refunds: {found_in_refunds}")
    print(f"  Not found in charter_refunds: {not_found_in_refunds}")
    
    # Count by transaction type
    print(f"\nNegative Deposits by Transaction Type:")
    transact_counts = {}
    type_counts = {}
    
    for deposit in negative_deposits:
        transact = deposit[5] or 'N/A'
        dep_type = deposit[4] or 'N/A'
        amount = abs(float(deposit[3])) if deposit[3] else 0
        
        transact_counts[transact] = transact_counts.get(transact, 0) + 1
        type_counts[dep_type] = type_counts.get(dep_type, {'count': 0, 'amount': 0})
        type_counts[dep_type]['count'] += 1
        type_counts[dep_type]['amount'] += amount
    
    print("\nBy Transaction Code (Transact):")
    for transact, count in sorted(transact_counts.items(), key=lambda x: -x[1]):
        print(f"  {transact}: {count}")
    
    print("\nBy Type:")
    for dep_type, data in sorted(type_counts.items(), key=lambda x: -x[1]['amount']):
        print(f"  {dep_type}: {data['count']} deposits, ${data['amount']:,.2f}")
    
    lms_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    main()
