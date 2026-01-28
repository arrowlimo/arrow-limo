#!/usr/bin/env python3
"""
Check LMS deposit refunds against charter_refunds table.
Uses the Key number to link to LMS Payment table to find reserve numbers.
"""

import psycopg2
import pyodbc
import os
from decimal import Decimal

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

# LMS Deposit refunds from the provided data (negative amounts)
# Format: (deposit_number, date, key, description, amount, type)
LMS_REFUNDS = [
    ('0009982', '2014-07-02', '0009982', '(no description)', 1760.00, 'Visa'),
    ('0019479', '2023-01-17', '0019479', 'Refunded', 1458.00, 'Write Off'),
    ('0019363', '2022-12-08', '0019363', 'Reunded', 1302.00, 'Write Off'),
    ('0015394', '2018-11-12', '0015394', 'Refund', 985.57, 'Visa'),
    ('0022091', '2025-04-30', '0022091', 'Refund', 816.00, 'Visa'),
    ('0021302', '2024-07-22', '0021302', '', 720.00, 'Refund'),
    ('0020670', '2023-12-07', '0020670', 'Refund', 231.00, 'Refund'),
    ('0021305', '2024-07-22', '0021305', '07/22/24', 239.85, 'Refund'),
    ('0021292', '2024-07-17', '0021292', 'Remb Cab Fare/meal', 200.00, 'Refund'),
    ('0022319', '2025-07-15', '0022319', 'Wanted Tip Back Paid', 173.25, 'Refund'),
    ('0022341', '2025-07-21', '0022341', '', 150.93, 'Refund'),
    ('0020858', '2024-02-12', '0020858', '', 31.50, 'Refund'),
]

def find_reserve_from_lms_payment(lms_conn, payment_key):
    """Find reserve number from LMS Payment table using the Key."""
    cur = lms_conn.cursor()
    
    try:
        # Try to find payment with matching Key
        cur.execute("""
            SELECT Reserve_No, Account_No, Amount, LastUpdated
            FROM Payment
            WHERE [Key] = ?
        """, (payment_key,))
        
        results = cur.fetchall()
        if results:
            if len(results) == 1:
                return ('single', results[0])
            else:
                return ('multiple', results)
        
        return None
        
    finally:
        cur.close()

def check_in_charter_refunds(pg_conn, amount, date_str):
    """Check if refund exists in charter_refunds."""
    cur = pg_conn.cursor()
    
    try:
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
            LIMIT 3
        """, (date_str, amount, date_str, date_str))
        
        return cur.fetchall()
        
    finally:
        cur.close()

def main():
    pg_conn = get_db_connection()
    lms_conn = get_lms_connection()
    
    print("=" * 100)
    print("LMS DEPOSIT REFUNDS - RESERVE NUMBER LOOKUP")
    print("=" * 100)
    print(f"\nTotal LMS refunds to check: {len(LMS_REFUNDS)}")
    print(f"Total amount: ${sum(r[4] for r in LMS_REFUNDS):,.2f}")
    print()
    
    found_with_reserve = 0
    found_in_db = 0
    not_found = 0
    
    for i, (deposit_num, date, key, desc, amount, pay_type) in enumerate(LMS_REFUNDS, 1):
        print(f"\n{'='*100}")
        print(f"Refund {i}/{len(LMS_REFUNDS)}: Deposit #{deposit_num}")
        print(f"{'='*100}")
        print(f"Date: {date}")
        print(f"Amount: ${amount:,.2f}")
        print(f"Description: '{desc}'")
        print(f"Type: {pay_type}")
        print(f"Key: {key}")
        
        # Find reserve number from LMS Payment table
        print(f"\n🔍 Searching LMS Payment table for Key: {key}...")
        lms_result = find_reserve_from_lms_payment(lms_conn, key)
        
        if lms_result:
            result_type, data = lms_result
            
            if result_type == 'single':
                # Single exact match
                reserve_no, account_no, lms_amount, last_updated = data
                print(f"[OK] FOUND IN LMS PAYMENT:")
                print(f"  Reserve Number: {reserve_no}")
                print(f"  Account Number: {account_no}")
                try:
                    amt_val = abs(float(lms_amount)) if lms_amount else 0
                    print(f"  Amount: ${amt_val:,.2f}")
                except (ValueError, TypeError):
                    print(f"  Amount: {lms_amount}")
                print(f"  Last Updated: {last_updated}")
                found_with_reserve += 1
                
                # Now check if it's in charter_refunds
                pg_matches = check_in_charter_refunds(pg_conn, amount, date)
                if pg_matches:
                    print(f"\n[OK] FOUND IN charter_refunds:")
                    for match in pg_matches:
                        ref_id, ref_date, ref_amt, ref_reserve, ref_charter, ref_desc, days_diff = match
                        status = "[OK] LINKED" if ref_reserve else "[WARN] UNLINKED"
                        print(f"  {status}")
                        print(f"    Refund ID: {ref_id}")
                        print(f"    Date: {ref_date} (days diff: {days_diff:.1f})")
                        print(f"    Amount: ${ref_amt:,.2f}")
                        print(f"    Reserve: {ref_reserve or 'NOT LINKED'}")
                        print(f"    Charter ID: {ref_charter or 'NOT LINKED'}")
                        
                        if ref_reserve and ref_reserve != reserve_no:
                            print(f"    [WARN] MISMATCH: LMS says {reserve_no}, DB says {ref_reserve}")
                    found_in_db += 1
                else:
                    print(f"\n[FAIL] NOT FOUND in charter_refunds")
                    print(f"  💡 Should be added with Reserve: {reserve_no}")
                    not_found += 1
                    
            elif result_type == 'multiple':
                # Multiple matches
                print(f"[WARN] MULTIPLE MATCHES IN LMS PAYMENT ({len(data)}):")
                for j, match in enumerate(data[:5], 1):
                    reserve_no, account_no, lms_amount, last_updated = match
                    print(f"  Match {j}:")
                    print(f"    Reserve: {reserve_no}")
                    print(f"    Account: {account_no}")
                    try:
                        amt_val = abs(float(lms_amount)) if lms_amount else 0
                        print(f"    Amount: ${amt_val:,.2f}")
                    except (ValueError, TypeError):
                        print(f"    Amount: {lms_amount}")
                    print(f"    Date: {last_updated}")
        else:
            print(f"[FAIL] NOT FOUND in LMS Payment table")
            
            # Still check PostgreSQL
            pg_matches = check_in_charter_refunds(pg_conn, amount, date)
            if pg_matches:
                print(f"\n[OK] FOUND IN charter_refunds (without LMS link):")
                for match in pg_matches:
                    ref_id, ref_date, ref_amt, ref_reserve, ref_charter, ref_desc, days_diff = match
                    status = "[OK] LINKED" if ref_reserve else "[WARN] UNLINKED"
                    print(f"  {status}")
                    print(f"    Refund ID: {ref_id}")
                    print(f"    Reserve: {ref_reserve or 'NOT LINKED'}")
                    print(f"    Amount: ${ref_amt:,.2f}")
                found_in_db += 1
            else:
                print(f"[FAIL] NOT FOUND anywhere")
                not_found += 1
    
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    print(f"Total LMS refunds checked: {len(LMS_REFUNDS)}")
    print(f"Found with reserve number in LMS: {found_with_reserve}")
    print(f"Found in charter_refunds: {found_in_db}")
    print(f"Not found / Need to add: {not_found}")
    
    lms_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    main()
