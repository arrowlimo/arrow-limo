#!/usr/bin/env python3
"""
Vehicle Loan Payment Reconciliation Tool

This script reconciles vehicle loan payments across multiple data sources:
1. Banking transactions (from CIBC vehicle loans account 8314462)
2. Lender statement transactions (from third-party lenders like Heffner)
3. Vehicle loan payments table
4. Email financial events related to loans

The script performs the following:
1. Identifies banking transactions related to vehicle loans
2. Matches transactions across different sources
3. Identifies potential duplicates or missing entries
4. Generates reports to help with reconciliation

Usage:
  python scripts/vehicle_loan_payment_reconciliation.py
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
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
}

# CIBC vehicle loans account number
VEHICLE_LOANS_ACCOUNT = '8314462'

# Output directory
REPORTS_DIR = 'l:/limo/reports'
os.makedirs(REPORTS_DIR, exist_ok=True)

def normalize_amount(x):
    """Convert various amount formats to a standardized float."""
    if x is None:
        return None
    if isinstance(x, Decimal):
        return round(float(x), 2)
    return round(float(x), 2)

def get_banking_transactions():
    """Retrieve banking transactions from the vehicle loans account."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT transaction_id, transaction_date, account_number, 
               description, vendor_extracted, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        ORDER BY transaction_date, transaction_id
    """, (VEHICLE_LOANS_ACCOUNT,))
    
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return transactions

def get_vehicle_loan_payments():
    """Retrieve vehicle loan payments from the database."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT p.id, p.loan_id, p.payment_date, p.payment_amount, 
               p.interest_amount, p.fee_amount, p.penalty_amount, 
               p.paid_by, p.notes,
               l.vehicle_id, l.vehicle_name, l.lender
        FROM vehicle_loan_payments p
        JOIN vehicle_loans l ON p.loan_id = l.id
        ORDER BY p.payment_date, p.id
    """)
    
    payments = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return payments

def get_lender_statement_transactions():
    """Retrieve lender statement transactions."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, txn_date, description, amount, balance
        FROM lender_statement_transactions
        ORDER BY txn_date, id
    """)
    
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return transactions

def get_email_financial_events():
    """Retrieve loan-related email financial events."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, email_date, subject, vin, event_type, entity, 
               lender_name, amount, vehicle_name
        FROM email_financial_events
        WHERE event_type IN ('loan_payment', 'nsf_fee', 'extra_payment')
        ORDER BY email_date, id
    """)
    
    events = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return events

def find_potential_matches(banking_tx, loan_payments, threshold_days=5):
    """Find potential matches between banking transactions and loan payments."""
    matches = []
    
    for bt in banking_tx:
        bt_date = bt['transaction_date']
        bt_amount = normalize_amount(bt['debit_amount'] or 0)
        
        if bt_amount <= 0:
            continue  # Skip credits or zero amounts
            
        for lp in loan_payments:
            lp_date = lp['payment_date']
            lp_amount = normalize_amount(lp['payment_amount'] or 0)
            
            # Check for date proximity and amount similarity
            date_diff = abs((bt_date - lp_date).days)
            amount_diff = abs(bt_amount - lp_amount)
            
            if date_diff <= threshold_days and amount_diff < 0.01:
                matches.append({
                    'bank_transaction_id': bt['transaction_id'],
                    'bank_date': bt_date,
                    'bank_description': bt['description'],
                    'bank_amount': bt_amount,
                    'payment_id': lp['id'],
                    'payment_date': lp_date,
                    'payment_amount': lp_amount,
                    'vehicle_name': lp['vehicle_name'],
                    'lender': lp['lender'],
                    'date_diff_days': date_diff,
                    'amount_diff': amount_diff
                })
                
    return matches

def find_unmatched_transactions(banking_tx, matched_bank_ids):
    """Identify banking transactions without a match in the loan payments table."""
    unmatched = []
    
    for bt in banking_tx:
        if bt['transaction_id'] not in matched_bank_ids and bt['debit_amount'] and bt['debit_amount'] > 0:
            unmatched.append({
                'transaction_id': bt['transaction_id'],
                'date': bt['transaction_date'],
                'description': bt['description'],
                'vendor': bt['vendor_extracted'],
                'amount': bt['debit_amount'],
                'account_number': bt['account_number']
            })
            
    return unmatched

def find_unmatched_payments(loan_payments, matched_payment_ids):
    """Identify loan payments without a matching banking transaction."""
    unmatched = []
    
    for lp in loan_payments:
        if lp['id'] not in matched_payment_ids:
            unmatched.append({
                'payment_id': lp['id'],
                'date': lp['payment_date'],
                'amount': float(lp['payment_amount'] or 0),
                'vehicle_name': lp['vehicle_name'],
                'lender': lp['lender'],
                'paid_by': lp['paid_by'],
                'notes': lp['notes']
            })
            
    return unmatched

def export_csv(path, data, headers):
    """Export data to CSV file."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in data:
            writer.writerow([row.get(h, '') for h in headers])

def main():
    print("Starting Vehicle Loan Payment Reconciliation...")
    
    # Get data from various sources
    banking_tx = get_banking_transactions()
    loan_payments = get_vehicle_loan_payments()
    lender_tx = get_lender_statement_transactions()
    email_events = get_email_financial_events()
    
    print(f"Retrieved {len(banking_tx)} banking transactions")
    print(f"Retrieved {len(loan_payments)} vehicle loan payments")
    print(f"Retrieved {len(lender_tx)} lender statement transactions")
    print(f"Retrieved {len(email_events)} email financial events")
    
    # Find potential matches between banking transactions and loan payments
    matches = find_potential_matches(banking_tx, loan_payments)
    
    # Track matched IDs
    matched_bank_ids = set(m['bank_transaction_id'] for m in matches)
    matched_payment_ids = set(m['payment_id'] for m in matches)
    
    # Find unmatched entries
    unmatched_bank_tx = find_unmatched_transactions(banking_tx, matched_bank_ids)
    unmatched_payments = find_unmatched_payments(loan_payments, matched_payment_ids)
    
    print(f"Found {len(matches)} matched transactions")
    print(f"Found {len(unmatched_bank_tx)} unmatched banking transactions")
    print(f"Found {len(unmatched_payments)} unmatched loan payments")
    
    # Export results to CSV
    export_csv(
        os.path.join(REPORTS_DIR, 'vehicle_loan_matched_transactions.csv'),
        matches,
        ['bank_transaction_id', 'bank_date', 'bank_description', 'bank_amount',
         'payment_id', 'payment_date', 'payment_amount', 'vehicle_name', 'lender',
         'date_diff_days', 'amount_diff']
    )
    
    export_csv(
        os.path.join(REPORTS_DIR, 'vehicle_loan_unmatched_bank_transactions.csv'),
        unmatched_bank_tx,
        ['transaction_id', 'date', 'description', 'vendor', 'amount', 'account_number']
    )
    
    export_csv(
        os.path.join(REPORTS_DIR, 'vehicle_loan_unmatched_payments.csv'),
        unmatched_payments,
        ['payment_id', 'date', 'amount', 'vehicle_name', 'lender', 'paid_by', 'notes']
    )
    
    print(f"Reports have been written to {REPORTS_DIR}")
    
    # Analyze potential duplicate payments
    payment_amounts = defaultdict(list)
    for lp in loan_payments:
        amount = float(lp['payment_amount'] or 0)
        if amount > 0:
            payment_amounts[amount].append(lp)
    
    potential_duplicates = []
    for amount, payments in payment_amounts.items():
        if len(payments) > 1:
            for i, p1 in enumerate(payments[:-1]):
                for p2 in payments[i+1:]:
                    date_diff = abs((p1['payment_date'] - p2['payment_date']).days)
                    if date_diff <= 15:  # Potential duplicates within 15 days
                        potential_duplicates.append({
                            'payment1_id': p1['id'],
                            'payment1_date': p1['payment_date'],
                            'payment1_vehicle': p1['vehicle_name'],
                            'payment1_lender': p1['lender'],
                            'payment2_id': p2['id'],
                            'payment2_date': p2['payment_date'],
                            'payment2_vehicle': p2['vehicle_name'],
                            'payment2_lender': p2['lender'],
                            'amount': amount,
                            'date_diff_days': date_diff
                        })
    
    if potential_duplicates:
        export_csv(
            os.path.join(REPORTS_DIR, 'vehicle_loan_potential_duplicates.csv'),
            potential_duplicates,
            ['payment1_id', 'payment1_date', 'payment1_vehicle', 'payment1_lender',
             'payment2_id', 'payment2_date', 'payment2_vehicle', 'payment2_lender',
             'amount', 'date_diff_days']
        )
        print(f"Found {len(potential_duplicates)} potential duplicate payments")
    else:
        print("No potential duplicate payments found")

if __name__ == "__main__":
    main()