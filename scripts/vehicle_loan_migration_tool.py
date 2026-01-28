#!/usr/bin/env python3
"""
Vehicle Loan Migration Utility

This script creates a standardized view of all vehicle loans and payments across
multiple data sources, including banking transactions, lender statements,
and email financial events.

It performs the following:
1. Identifies vehicles with loans
2. Consolidates loan data from multiple sources
3. Creates or updates vehicle_loans and vehicle_loan_payments records
4. Generates reconciliation reports for review

Usage:
  python scripts/vehicle_loan_migration.py
"""

import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv('l:/limo/.env')

# Database connection parameters
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
}

# CIBC vehicle loans account number
VEHICLE_LOANS_ACCOUNT = '8314462'

# Heffner and other lenders to search for
LENDERS = ['HEFFNER', 'CMB', 'INSURANCE']

# Output directory
REPORTS_DIR = 'l:/limo/reports'
CONFIG_DIR = 'l:/limo/config'
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(**DB_CONFIG)

def get_vehicles():
    """Get all vehicles from the database."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT vehicle_id, year, make, model, vin_number, license_plate
        FROM vehicles
        ORDER BY vehicle_id
    """)
    
    vehicles = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return vehicles

def get_vehicle_loans():
    """Get existing vehicle loans from the database."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, vehicle_id, vehicle_name, lender, paid_by, opening_balance, 
               closing_balance, total_paid, total_interest, total_fees, total_penalties,
               total_sold_for, loan_start_date, loan_end_date, notes
        FROM vehicle_loans
        ORDER BY id
    """)
    
    loans = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return loans

def get_vehicle_loan_payments():
    """Get existing vehicle loan payments from the database."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, loan_id, payment_date, payment_amount, interest_amount,
               fee_amount, penalty_amount, paid_by, notes
        FROM vehicle_loan_payments
        ORDER BY payment_date, id
    """)
    
    payments = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return payments

def get_bank_loan_transactions():
    """Get banking transactions related to vehicle loans."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get transactions from vehicle loans account
    cursor.execute("""
        SELECT transaction_id, transaction_date, account_number, 
               description, vendor_extracted, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        ORDER BY transaction_date, transaction_id
    """, (VEHICLE_LOANS_ACCOUNT,))
    
    vehicle_account_tx = cursor.fetchall()
    
    # Get transactions from other accounts with lender keywords
    lender_patterns = []
    for lender in LENDERS:
        lender_patterns.append(f"%{lender}%")
    
    placeholders = ', '.join(['%s' for _ in lender_patterns])
    cursor.execute(f"""
        SELECT transaction_id, transaction_date, account_number, 
               description, vendor_extracted, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number != %s
          AND (
              {' OR '.join([f"UPPER(description) LIKE UPPER(%s)" for _ in lender_patterns])}
          )
        ORDER BY transaction_date, transaction_id
    """, (VEHICLE_LOANS_ACCOUNT, *lender_patterns))
    
    other_loan_tx = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'vehicle_account': vehicle_account_tx,
        'other_accounts': other_loan_tx
    }

def create_vehicle_loan_mapping():
    """Create mapping between banking transactions and vehicles based on patterns."""
    # Check if mapping file already exists
    mapping_file = os.path.join(CONFIG_DIR, 'vehicle_loan_mapping.csv')
    if os.path.exists(mapping_file):
        return
    
    # Get all vehicles
    vehicles = get_vehicles()
    
    # Get loan transactions
    bank_tx = get_bank_loan_transactions()
    
    # Extract unique amounts
    amounts = set()
    for tx in bank_tx['vehicle_account']:
        if tx['debit_amount'] and tx['debit_amount'] > 0:
            amounts.add(round(float(tx['debit_amount']), 2))
    
    # Create mapping template
    mapping_data = []
    for amount in sorted(amounts):
        mapping_data.append({
            'amount': amount,
            'account_number': VEHICLE_LOANS_ACCOUNT,
            'description_contains': '',
            'vehicle_id': '',
            'vehicle_name': '',
            'vin': ''
        })
    
    # Write template to CSV
    with open(mapping_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'amount', 'account_number', 'description_contains', 
            'vehicle_id', 'vehicle_name', 'vin'
        ])
        writer.writeheader()
        writer.writerows(mapping_data)
    
    print(f"Created vehicle loan mapping template at {mapping_file}")
    print("Please fill in the vehicle information for each payment amount")

def load_vehicle_loan_mapping():
    """Load vehicle loan mapping from CSV."""
    mapping_file = os.path.join(CONFIG_DIR, 'vehicle_loan_mapping.csv')
    if not os.path.exists(mapping_file):
        create_vehicle_loan_mapping()
        return {}
    
    mapping = {}
    with open(mapping_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['amount'] and row['vehicle_id']:
                key = (float(row['amount']), row.get('account_number', VEHICLE_LOANS_ACCOUNT))
                mapping[key] = {
                    'vehicle_id': int(row['vehicle_id']),
                    'vehicle_name': row['vehicle_name'],
                    'vin': row['vin']
                }
    
    return mapping

def upsert_vehicle_loans(mapping):
    """Create or update vehicle loans based on mapping."""
    if not mapping:
        print("No vehicle loan mapping available. Please fill out the mapping file.")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing loans
    existing_loans = {}
    cursor.execute("""
        SELECT id, vehicle_id, lender
        FROM vehicle_loans
    """)
    for loan_id, vehicle_id, lender in cursor.fetchall():
        existing_loans[(vehicle_id, lender)] = loan_id
    
    # Insert new loans for mapped vehicles
    new_loans = 0
    for (amount, account), vehicle_info in mapping.items():
        vehicle_id = vehicle_info['vehicle_id']
        vehicle_name = vehicle_info['vehicle_name']
        
        # Determine lender based on account number
        lender = "CIBC" if account == VEHICLE_LOANS_ACCOUNT else "Heffner"
        
        # Check if loan exists
        loan_id = existing_loans.get((vehicle_id, lender))
        
        if not loan_id:
            cursor.execute("""
                INSERT INTO vehicle_loans (
                    vehicle_id, vehicle_name, lender, paid_by, notes
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                vehicle_id, 
                vehicle_name, 
                lender, 
                "Arrow Limousine", 
                f"Auto-created from payment mapping for ${amount:.2f}"
            ))
            loan_id = cursor.fetchone()[0]
            existing_loans[(vehicle_id, lender)] = loan_id
            new_loans += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"Created {new_loans} new vehicle loans")
    return existing_loans

def create_loan_payments(mapping, existing_loans):
    """Create loan payments from banking transactions."""
    if not mapping or not existing_loans:
        print("Missing mapping or existing loans information.")
        return
    
    # Get bank transactions
    bank_tx = get_bank_loan_transactions()
    
    # Get existing payments to avoid duplicates
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existing_payments = set()
    cursor.execute("""
        SELECT loan_id, payment_date, payment_amount
        FROM vehicle_loan_payments
    """)
    for loan_id, payment_date, amount in cursor.fetchall():
        existing_payments.add((loan_id, payment_date, float(amount)))
    
    # Process transactions
    new_payments = 0
    for tx in bank_tx['vehicle_account']:
        if not tx['debit_amount'] or tx['debit_amount'] <= 0:
            continue
        
        amount = round(float(tx['debit_amount']), 2)
        account = tx['account_number']
        key = (amount, account)
        
        if key in mapping:
            vehicle_id = mapping[key]['vehicle_id']
            lender = "CIBC" if account == VEHICLE_LOANS_ACCOUNT else "Heffner"
            loan_id = existing_loans.get((vehicle_id, lender))
            
            if loan_id:
                payment_date = tx['transaction_date']
                
                # Skip if payment already exists
                if (loan_id, payment_date, amount) in existing_payments:
                    continue
                
                # Insert new payment
                cursor.execute("""
                    INSERT INTO vehicle_loan_payments (
                        loan_id, payment_date, payment_amount, interest_amount,
                        fee_amount, penalty_amount, paid_by, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    loan_id,
                    payment_date,
                    amount,
                    None,  # interest_amount
                    None,  # fee_amount
                    None,  # penalty_amount
                    "bank",
                    tx['description']
                ))
                
                new_payments += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"Created {new_payments} new loan payments")

def summarize_loan_data():
    """Generate summary of vehicle loan data."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get loan summary
    cursor.execute("""
        SELECT l.id, l.vehicle_id, l.vehicle_name, l.lender,
               COUNT(p.id) AS payment_count,
               SUM(p.payment_amount) AS total_paid,
               SUM(p.interest_amount) AS total_interest,
               SUM(p.fee_amount) AS total_fees,
               MIN(p.payment_date) AS first_payment,
               MAX(p.payment_date) AS last_payment
        FROM vehicle_loans l
        LEFT JOIN vehicle_loan_payments p ON l.id = p.loan_id
        GROUP BY l.id, l.vehicle_id, l.vehicle_name, l.lender
        ORDER BY l.vehicle_id
    """)
    
    loan_summary = cursor.fetchall()
    
    # Export to CSV
    summary_file = os.path.join(REPORTS_DIR, 'vehicle_loan_summary.csv')
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'loan_id', 'vehicle_id', 'vehicle_name', 'lender',
            'payment_count', 'total_paid', 'total_interest', 'total_fees',
            'first_payment', 'last_payment'
        ])
        
        for loan in loan_summary:
            writer.writerow([
                loan['id'], loan['vehicle_id'], loan['vehicle_name'], loan['lender'],
                loan['payment_count'], loan['total_paid'], loan['total_interest'], 
                loan['total_fees'], loan['first_payment'], loan['last_payment']
            ])
    
    print(f"Loan summary written to {summary_file}")
    
    # Update loan totals in the database
    updated = 0
    for loan in loan_summary:
        if loan['payment_count'] > 0:
            cursor.execute("""
                UPDATE vehicle_loans
                SET total_paid = %s,
                    total_interest = %s,
                    total_fees = %s,
                    loan_start_date = %s,
                    loan_end_date = %s
                WHERE id = %s
            """, (
                loan['total_paid'],
                loan['total_interest'],
                loan['total_fees'],
                loan['first_payment'],
                loan['last_payment'],
                loan['id']
            ))
            updated += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"Updated totals for {updated} vehicle loans")

def main():
    print("Starting Vehicle Loan Migration...")
    
    # Create mapping if it doesn't exist
    create_vehicle_loan_mapping()
    
    # Load mapping
    mapping = load_vehicle_loan_mapping()
    
    if not mapping:
        print("Please fill out the vehicle loan mapping file and run this script again.")
        return
    
    # Upsert vehicle loans
    existing_loans = upsert_vehicle_loans(mapping)
    
    # Create loan payments
    create_loan_payments(mapping, existing_loans)
    
    # Generate summary
    summarize_loan_data()
    
    print("Vehicle loan migration completed.")

if __name__ == "__main__":
    main()