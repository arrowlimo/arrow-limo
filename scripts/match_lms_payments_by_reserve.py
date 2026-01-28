#!/usr/bin/env python3
"""
Match LMS payments to PostgreSQL using proper reserve number linkage.

This script replaces the LMSDEP batch approach with direct matching via:
- LMS Payment table (PaymentID, Account_No, Reserve_No, Amount)
- PostgreSQL charters table (reserve_number, account_number)
- Direct reserve_number matching (no string parsing)

Author: AI Assistant
Date: 2025-11-11
"""

import sys
import os
import argparse
import pyodbc
import psycopg2
from datetime import datetime
from decimal import Decimal

# LMS connection
LMS_PATH = r'L:\New folder\lms.mdb'  # Most recent LMS (Nov 8, 2025)

def get_lms_connection():
    """Connect to LMS Access database."""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***',
        host='localhost'
    )

def normalize_reserve_number(reserve_no):
    """Normalize reserve number to 6-digit format."""
    if not reserve_no:
        return None
    
    # Remove any non-numeric characters
    numeric = ''.join(c for c in str(reserve_no) if c.isdigit())
    
    if not numeric:
        return None
    
    # Pad to 6 digits
    return numeric.zfill(6)

def get_lms_payments():
    """Get all payments from LMS Payment table."""
    conn = get_lms_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            PaymentID,
            Account_No,
            Reserve_No,
            Amount,
            [Key],
            LastUpdated,
            LastUpdatedBy
        FROM Payment
        WHERE Amount IS NOT NULL
        ORDER BY PaymentID
    """)
    
    payments = []
    for row in cur.fetchall():
        payment_id = row[0]
        account_no = row[1]
        reserve_no = normalize_reserve_number(row[2])
        amount = float(row[3]) if row[3] else 0.0
        payment_key = row[4]
        last_updated = row[5]
        last_updated_by = row[6]
        
        payments.append({
            'lms_payment_id': payment_id,
            'account_number': account_no,
            'reserve_number': reserve_no,
            'amount': amount,
            'payment_key': payment_key,
            'payment_date': last_updated,
            'last_updated_by': last_updated_by
        })
    
    cur.close()
    conn.close()
    
    return payments

def find_charter_id(pg_cur, reserve_number, account_number):
    """Find charter_id by reserve_number (and optionally account_number)."""
    
    # Try exact reserve_number match first
    pg_cur.execute("""
        SELECT charter_id, account_number 
        FROM charters 
        WHERE reserve_number = %s
    """, (reserve_number,))
    
    results = pg_cur.fetchall()
    
    if len(results) == 1:
        return results[0][0]  # charter_id
    
    if len(results) > 1:
        # Multiple charters with same reserve_number (shouldn't happen)
        # Try to disambiguate with account_number
        for charter_id, acct_no in results:
            if acct_no == account_number:
                return charter_id
        # If no account match, return first
        return results[0][0]
    
    # No match
    return None

def payment_exists(pg_cur, lms_payment_id):
    """Check if LMS payment already imported."""
    pg_cur.execute("""
        SELECT payment_id 
        FROM payments 
        WHERE payment_key = %s
    """, (f'LMS:{lms_payment_id}',))
    
    return pg_cur.fetchone() is not None

def insert_payment(pg_cur, lms_payment, charter_id):
    """Insert LMS payment into PostgreSQL."""
    
    # Generate unique payment_key
    payment_key = f'LMS:{lms_payment["lms_payment_id"]}'
    
    pg_cur.execute("""
    INSERT INTO payments (
            charter_id,
            reserve_number,
            account_number,
            client_id,
            amount,
            payment_key,
            payment_date,
            last_updated_by,
            created_at,
            payment_method,
            status,
            notes
        )
        VALUES (
            %s, %s, %s,
            (SELECT client_id FROM charters WHERE charter_id = %s),
            %s, %s, %s, %s, CURRENT_TIMESTAMP,
            'unknown', 'paid',
            %s
        )
        RETURNING payment_id
    """, (
        charter_id,
        lms_payment['reserve_number'],
        lms_payment['account_number'],
        charter_id,  # for client_id subquery
        lms_payment['amount'],
        payment_key,
        lms_payment['payment_date'],
        lms_payment['last_updated_by'],
        f"Imported from LMS Payment ID {lms_payment['lms_payment_id']}"
    ))
    
    return pg_cur.fetchone()[0]

def main():
    parser = argparse.ArgumentParser(description='Match LMS payments by reserve number')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of payments to process')
    args = parser.parse_args()
    
    print("=" * 80)
    print("LMS PAYMENT MATCHING BY RESERVE NUMBER")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Get LMS payments
    print("Loading LMS payments...")
    lms_payments = get_lms_payments()
    print(f"Found {len(lms_payments)} LMS payments")
    
    if args.limit:
        lms_payments = lms_payments[:args.limit]
        print(f"Limited to {len(lms_payments)} payments")
    
    # Connect to PostgreSQL
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    # Match statistics
    matched = 0
    already_imported = 0
    no_charter_match = 0
    inserted = 0
    
    no_reserve_payments = []
    no_charter_payments = []
    
    for lms_payment in lms_payments:
        reserve_no = lms_payment['reserve_number']
        
        # Check if already imported
        if payment_exists(pg_cur, lms_payment['lms_payment_id']):
            already_imported += 1
            continue
        
        # Check for reserve number
        if not reserve_no:
            no_reserve_payments.append(lms_payment)
            continue
        
        # Find charter
        charter_id = find_charter_id(pg_cur, reserve_no, lms_payment['account_number'])
        
        if not charter_id:
            no_charter_match += 1
            no_charter_payments.append(lms_payment)
            continue
        
        matched += 1
        
        # Insert payment
        if args.write:
            payment_id = insert_payment(pg_cur, lms_payment, charter_id)
            inserted += 1
    
    # Summary
    print()
    print("=" * 80)
    print("MATCHING SUMMARY")
    print("=" * 80)
    print(f"Total LMS payments:      {len(lms_payments)}")
    print(f"Already imported:        {already_imported}")
    print(f"No reserve number:       {len(no_reserve_payments)}")
    print(f"No charter match:        {no_charter_match}")
    print(f"Matched:                 {matched}")
    
    if args.write:
        print(f"Inserted:                {inserted}")
        pg_conn.commit()
        print("\n✓ Changes committed")
    else:
        print("\nDRY-RUN: No changes made")
    
    # Show samples
    if no_reserve_payments:
        print("\nSample payments with no reserve number:")
        for pmt in no_reserve_payments[:10]:
            print(f"  LMS Payment {pmt['lms_payment_id']}: "
                  f"Account {pmt['account_number']}, Amount ${pmt['amount']:.2f}")
    
    if no_charter_payments:
        print("\nSample payments with no charter match:")
        for pmt in no_charter_payments[:10]:
            print(f"  LMS Payment {pmt['lms_payment_id']}: "
                  f"Reserve {pmt['reserve_number']}, Amount ${pmt['amount']:.2f}")
    
    pg_cur.close()
    pg_conn.close()

if __name__ == '__main__':
    main()
