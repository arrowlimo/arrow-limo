#!/usr/bin/env python3
"""
Enhanced E-transfer to Charter Matching with Business Rules

Business Rules:
1. Barb Peacock etransfers are mostly personal transactions (exclude from charter matching)
2. Michael Richard is a driver (driver payments, not charter payments)
3. Refund etransfers should match charter refund amounts
4. David Richard etransfers are loan payments (not charter payments)
5. Match employee names using QuickBooks data if not in almsdata
"""

import os
import csv
import re
from datetime import timedelta, datetime
from typing import Dict, List, Tuple, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

# Business rule classifications
PERSONAL_CUSTOMERS = ['barb peacock', 'barbara peacock']
DRIVER_NAMES = ['michael richard', 'mike richard']
LOAN_RECIPIENTS = ['david richard', 'dave richard']

def extract_customer_name(email_subject: str, reference: str) -> str:
    """Extract customer name from email subject or reference"""
    # From email subject: "INTERAC e-Transfer: CUSTOMER NAME sent you money."
    if 'sent you money' in email_subject.lower():
        match = re.search(r':\s*([^:]+?)\s+sent you money', email_subject, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # From email subject: "Your money transfer to CUSTOMER NAME was deposited"
    if 'transfer to' in email_subject.lower():
        match = re.search(r'transfer to\s+([^:]+?)\s+was deposited', email_subject, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # From reference: extract name after E-TRANSFER
    ref_match = re.search(r'E-TRANSFER[^A-Za-z]*([A-Za-z\s]+)', reference, re.IGNORECASE)
    if ref_match:
        name = ref_match.group(1).strip()
        # Clean up common suffixes
        name = re.sub(r'\s+4506.*$', '', name)  # Remove card numbers
        return name.strip()
    
    return ''

def classify_etransfer(customer_name: str, amount: float, email_subject: str) -> str:
    """Classify etransfer based on business rules"""
    name_lower = customer_name.lower()
    
    if any(personal in name_lower for personal in PERSONAL_CUSTOMERS):
        return 'personal'
    
    if any(driver in name_lower for driver in DRIVER_NAMES):
        return 'driver_payment'
    
    if any(loan in name_lower for loan in LOAN_RECIPIENTS):
        return 'loan_payment'
    
    if 'refund' in email_subject.lower() or 'transfer to' in email_subject.lower():
        return 'refund'
    
    return 'charter_candidate'

def find_matching_charter(cur, customer_name: str, amount: float, transaction_date, classification: str) -> Optional[Dict]:
    """Find matching charter based on customer name, amount, and date"""
    
    if classification == 'refund':
        # Look for charter refunds
        cur.execute("""
            SELECT c.charter_id, c.reserve_number, c.client_name, c.rate, c.charter_date,
                   'refund_match' as match_type
            FROM charters c
            WHERE c.charter_date BETWEEN %s - INTERVAL '30 days' AND %s + INTERVAL '30 days'
              AND ABS(c.rate - %s) < 1.00
              AND (LOWER(c.client_name) LIKE %s OR LOWER(c.client_name) LIKE %s)
            ORDER BY ABS(c.rate - %s) ASC, ABS(c.charter_date - %s) ASC
            LIMIT 1
        """, (transaction_date, transaction_date, amount, 
              f'%{customer_name.split()[0].lower()}%', 
              f'%{customer_name.split()[-1].lower()}%',
              amount, transaction_date))
        
    else:
        # Look for regular charter payments
        cur.execute("""
            SELECT c.charter_id, c.reserve_number, c.client_name, c.rate, c.charter_date,
                   'payment_match' as match_type
            FROM charters c
            LEFT JOIN payments p ON c.charter_id = p.charter_id
            WHERE c.charter_date BETWEEN %s - INTERVAL '14 days' AND %s + INTERVAL '7 days'
              AND ABS(c.rate - %s) < 2.00
              AND (LOWER(c.client_name) LIKE %s OR LOWER(c.client_name) LIKE %s)
              AND (p.payment_id IS NULL OR c.rate > COALESCE(p.amount, 0))
            ORDER BY ABS(c.rate - %s) ASC, ABS(c.charter_date - %s) ASC
            LIMIT 1
        """, (transaction_date, transaction_date, amount,
              f'%{customer_name.split()[0].lower()}%',
              f'%{customer_name.split()[-1].lower()}%',
              amount, transaction_date))
    
    result = cur.fetchone()
    if result:
        return dict(result)
    return None

def check_employee_in_qb(cur, customer_name: str) -> bool:
    """Check if customer name exists in QuickBooks employee data"""
    try:
        # Check against QuickBooks transactions staging for employee names
        cur.execute("""
            SELECT COUNT(*) FROM qb_transactions_staging 
            WHERE LOWER(name) LIKE %s OR LOWER(name) LIKE %s
        """, (f'%{customer_name.lower()}%', f'%{customer_name.split()[-1].lower()}%'))
        
        count = cur.fetchone()[0]
        return count > 0
    except:
        return False

def process_etransfers():
    """Main processing function"""
    
    # Read reconciled etransfer data
    etransfer_file = 'l:/limo/reports/email_banking_reconciliation.csv'
    if not os.path.exists(etransfer_file):
        print(f"Error: {etransfer_file} not found")
        return
    
    results = {
        'charter_matches': [],
        'personal_excluded': [],
        'driver_payments': [],
        'loan_payments': [],
        'refunds': [],
        'unmatched': [],
        'qb_employees': []
    }
    
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    with open(etransfer_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if row.get('source', '').lower() != 'etransfer':
                continue
                
            try:
                amount = float(row.get('bank_amount', 0))
                bank_date = datetime.strptime(row['bank_date'], '%Y-%m-%d').date()
                email_subject = row.get('email_subject', '')
                reference = row.get('bank_desc', '')
                
                customer_name = extract_customer_name(email_subject, reference)
                if not customer_name:
                    continue
                
                classification = classify_etransfer(customer_name, amount, email_subject)
                
                record = {
                    'bank_txn_id': row['bank_txn_id'],
                    'customer_name': customer_name,
                    'amount': amount,
                    'date': bank_date,
                    'email_subject': email_subject,
                    'classification': classification
                }
                
                if classification == 'personal':
                    results['personal_excluded'].append(record)
                    
                elif classification == 'driver_payment':
                    results['driver_payments'].append(record)
                    
                elif classification == 'loan_payment':
                    results['loan_payments'].append(record)
                    
                elif classification in ['refund', 'charter_candidate']:
                    # Try to find matching charter
                    charter_match = find_matching_charter(cur, customer_name, amount, bank_date, classification)
                    
                    if charter_match:
                        record['charter_id'] = charter_match['charter_id']
                        record['reserve_number'] = charter_match['reserve_number']
                        record['charter_client'] = charter_match['client_name']
                        record['charter_rate'] = charter_match['rate']
                        record['match_type'] = charter_match['match_type']
                        
                        if classification == 'refund':
                            results['refunds'].append(record)
                        else:
                            results['charter_matches'].append(record)
                    else:
                        # Check if it's an employee in QuickBooks
                        if check_employee_in_qb(cur, customer_name):
                            record['found_in_qb'] = True
                            results['qb_employees'].append(record)
                        else:
                            results['unmatched'].append(record)
                            
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
    
    cur.close()
    conn.close()
    
    # Generate reports
    generate_reports(results)

def generate_reports(results: Dict):
    """Generate detailed reports"""
    
    reports_dir = 'l:/limo/reports'
    os.makedirs(reports_dir, exist_ok=True)
    
    print("\\n🎯 E-TRANSFER CLASSIFICATION RESULTS:")
    print(f"Charter Matches: {len(results['charter_matches'])}")
    print(f"Personal (excluded): {len(results['personal_excluded'])}")
    print(f"Driver Payments: {len(results['driver_payments'])}")
    print(f"Loan Payments: {len(results['loan_payments'])}")
    print(f"Refunds: {len(results['refunds'])}")
    print(f"QB Employees: {len(results['qb_employees'])}")
    print(f"Unmatched: {len(results['unmatched'])}")
    
    # Write charter matches
    with open(f'{reports_dir}/etransfer_charter_matches.csv', 'w', newline='', encoding='utf-8') as f:
        if results['charter_matches']:
            writer = csv.DictWriter(f, fieldnames=results['charter_matches'][0].keys())
            writer.writeheader()
            writer.writerows(results['charter_matches'])
    
    # Write classification summary
    with open(f'{reports_dir}/etransfer_classification_summary.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Classification', 'Count', 'Total_Amount'])
        
        for category, records in results.items():
            if records:
                total_amount = sum(r.get('amount', 0) for r in records)
                writer.writerow([category, len(records), f"{total_amount:.2f}"])
    
    # Write detailed breakdown
    for category, records in results.items():
        if records:
            filename = f'{reports_dir}/etransfer_{category}.csv'
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)
            print(f"Wrote {len(records)} records to {filename}")

if __name__ == '__main__':
    process_etransfers()