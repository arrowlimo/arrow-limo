#!/usr/bin/env python3
"""
Download Square Capital Loan Details via API

Fetches comprehensive loan payment data including:
1. Loan details (amount, terms, status)
2. Payment history (including payout deductions)
3. Repayment schedule
4. Current balances

This will show the TRUE loan repayment amounts including daily payout deductions.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2

load_dotenv("l:/limo/.env")
load_dotenv()

SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "").strip()
SQUARE_ENV = os.getenv("SQUARE_ENV", "production").strip().lower()

if SQUARE_ENV == 'production':
    SQUARE_API_BASE = 'https://connect.squareup.com'
else:
    SQUARE_API_BASE = 'https://connect.squareupsandbox.com'

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def make_square_request(endpoint, params=None, method='GET', data=None):
    """Make authenticated request to Square API."""
    headers = {
        'Square-Version': '2024-11-20',
        'Authorization': f'Bearer {SQUARE_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = f'{SQUARE_API_BASE}{endpoint}'
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f'[FAIL] Square API request failed: {e}')
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f'   Response: {e.response.text}')
        return None

def main():
    print('=' * 100)
    print('DOWNLOADING SQUARE CAPITAL LOAN DATA')
    print('=' * 100)
    
    if not SQUARE_ACCESS_TOKEN:
        print('\n[FAIL] ERROR: SQUARE_ACCESS_TOKEN not found in environment')
        return
    
    print(f'\n✓ Using Square API: {SQUARE_ENV}')
    print(f'  Token: {SQUARE_ACCESS_TOKEN[:8]}...')
    
    # Try to fetch loans via API
    print('\n' + '=' * 100)
    print('FETCHING SQUARE CAPITAL LOANS')
    print('=' * 100)
    
    # Note: Square Capital loans endpoint
    # This may require special permissions/scope
    result = make_square_request('/v2/capital/loans')
    
    if result and 'loans' in result:
        loans = result.get('loans', [])
        print(f'\n✓ Found {len(loans)} loans via API')
        
        for loan in loans:
            print('\n' + '-' * 80)
            print(f'Loan ID: {loan.get("id")}')
            print(f'Status: {loan.get("status")}')
            
            # Loan amount
            amount_money = loan.get('loan_amount_money', {})
            loan_amount = amount_money.get('amount', 0) / 100
            print(f'Loan Amount: ${loan_amount:,.2f}')
            
            # Repayment info
            repaid_money = loan.get('repaid_money', {})
            repaid_amount = repaid_money.get('amount', 0) / 100
            print(f'Repaid Amount: ${repaid_amount:,.2f}')
            
            # Outstanding
            outstanding_money = loan.get('outstanding_money', {})
            outstanding_amount = outstanding_money.get('amount', 0) / 100
            print(f'Outstanding Balance: ${outstanding_amount:,.2f}')
            
            # Dates
            print(f'Created: {loan.get("created_at")}')
            if loan.get('approved_at'):
                print(f'Approved: {loan.get("approved_at")}')
            if loan.get('disbursed_at'):
                print(f'Disbursed: {loan.get("disbursed_at")}')
    else:
        print('\n⚠ Could not fetch loans via API')
        print('  This endpoint may require special Capital API permissions')
        print('  Error details:', result)
    
    # Alternative: Try to get loan payment info from payout entries
    print('\n\n' + '=' * 100)
    print('ANALYZING PAYOUT ENTRIES FOR LOAN DEDUCTIONS')
    print('=' * 100)
    
    print('\nFetching recent payouts...')
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    # Get payouts from database
    cur.execute("""
        SELECT id, arrival_date, amount, status
        FROM square_payouts
        WHERE arrival_date >= '2025-01-01'
        ORDER BY arrival_date DESC
        LIMIT 50
    """)
    
    payouts = cur.fetchall()
    print(f'  Found {len(payouts)} payouts since 2025-01-01')
    
    total_loan_deductions = 0
    payout_details = []
    
    for payout_id, arrival_date, payout_amount, status in payouts:
        print(f'\n  Analyzing payout {payout_id[:8]}... ({arrival_date})')
        
        # Fetch payout entries from Square API
        try:
            result = make_square_request(f'/v2/payouts/{payout_id}/entries', params={'limit': 100})
        except:
            # Try alternate endpoint
            try:
                result = make_square_request(f'/v2/payouts/{payout_id}/payout-entries', params={'limit': 100})
            except:
                result = None
        
        if not result or 'payout_entries' not in result:
            continue
        
        entries = result.get('payout_entries', [])
        
        gross_sales = 0
        processing_fees = 0
        loan_deductions = 0
        
        for entry in entries:
            entry_type = entry.get('type', '')
            amount_money = entry.get('amount_money', {})
            amount_cents = amount_money.get('amount', 0)
            amount = amount_cents / 100
            
            if entry_type == 'CHARGE':
                gross_sales += amount
            elif entry_type == 'FEE':
                processing_fees += abs(amount)
            elif 'REPAYMENT' in entry_type or 'LOAN' in entry_type or 'CAPITAL' in entry_type:
                loan_deductions += abs(amount)
                print(f'    → LOAN DEDUCTION: ${abs(amount):.2f} ({entry_type})')
        
        if loan_deductions > 0:
            total_loan_deductions += loan_deductions
            payout_details.append({
                'payout_id': payout_id,
                'date': arrival_date,
                'gross': gross_sales,
                'fees': processing_fees,
                'loan': loan_deductions,
                'net': payout_amount
            })
    
    if payout_details:
        print('\n\n' + '=' * 100)
        print('LOAN DEDUCTIONS FROM PAYOUTS')
        print('=' * 100)
        
        print(f'\n{"Date":<12} {"Payout ID":<20} {"Gross":>12} {"Fees":>10} {"Loan":>12} {"Net":>12}')
        print('-' * 80)
        
        for detail in payout_details:
            print(f'{detail["date"]!s:<12} {detail["payout_id"][:18]:<20} '
                  f'${detail["gross"]:>11,.2f} ${detail["fees"]:>9,.2f} '
                  f'${detail["loan"]:>11,.2f} ${detail["net"]:>11,.2f}')
        
        print('\n' + '=' * 80)
        print(f'TOTAL LOAN DEDUCTIONS FROM PAYOUTS: ${total_loan_deductions:,.2f}')
    else:
        print('\n⚠ No loan deductions found in payout entries')
        print('  Loan payments may be recorded differently or require dashboard access')
    
    # Summary with banking data
    print('\n\n' + '=' * 100)
    print('COMPLETE LOAN SUMMARY')
    print('=' * 100)
    
    cur.execute("""
        SELECT 
            SUM(credit_amount) as total_loans,
            SUM(debit_amount) as total_direct_payments
        FROM banking_transactions
        WHERE (description ILIKE '%SQ CAP%' 
           OR description ILIKE '%SQUARE CAP%')
    """)
    
    banking_summary = cur.fetchone()
    total_loans_received = banking_summary[0] or 0
    total_direct_payments = banking_summary[1] or 0
    
    print(f'\nLoans Received (Banking): ${total_loans_received:,.2f}')
    print(f'Direct Payments (Banking): ${total_direct_payments:,.2f}')
    
    if total_loan_deductions > 0:
        print(f'Payout Deductions (API): ${total_loan_deductions:,.2f}')
        print(f'\nTOTAL REPAID: ${total_direct_payments + total_loan_deductions:,.2f}')
        print(f'OUTSTANDING: ${total_loans_received - (total_direct_payments + total_loan_deductions):,.2f}')
    else:
        print(f'\n⚠ Payout deductions not available via API')
        print(f'  Please check Square Dashboard for accurate payment totals')
    
    cur.close()
    conn.close()
    
    print('\n' + '=' * 100)
    print('RECOMMENDATIONS')
    print('=' * 100)
    print('''
To get complete loan payment data:

1. Log into Square Dashboard: https://squareup.com/dashboard
2. Navigate to: Capital → Loans
3. For each loan, view full payment history
4. Download payment reports if available

The Square API may not expose Capital loan details without special permissions.
Contact Square support to enable Capital API access if needed.
''')

if __name__ == '__main__':
    main()
