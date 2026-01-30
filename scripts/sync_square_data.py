#!/usr/bin/env python3
"""
Square API Integration - Download payments, loan data, and service fees

This script:
1. Connects to Square API
2. Downloads payment transactions with full details
3. Downloads loan payment information
4. Downloads service fee breakdown (processing fees, etc.)
5. Updates PostgreSQL database with new data

Requires:
- Square API access token in environment variable SQUARE_ACCESS_TOKEN
- Square API: https://developer.squareup.com/
"""

import os
import requests
import psycopg2
from datetime import datetime, timedelta
import json
from decimal import Decimal

# Square API Configuration
SQUARE_ACCESS_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
SQUARE_ENVIRONMENT = os.getenv('SQUARE_ENVIRONMENT', 'production')  # or 'sandbox'

if SQUARE_ENVIRONMENT == 'production':
    SQUARE_API_BASE = 'https://connect.squareup.com'
else:
    SQUARE_API_BASE = 'https://connect.squareupsandbox.com'

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def check_square_credentials():
    """Verify Square API credentials are configured."""
    if not SQUARE_ACCESS_TOKEN:
        print('[FAIL] ERROR: SQUARE_ACCESS_TOKEN environment variable not set')
        print('\nTo configure Square API access:')
        print('1. Log in to Square Developer Dashboard: https://developer.squareup.com/')
        print('2. Create an application or use existing one')
        print('3. Get your Access Token from the Credentials tab')
        print('4. Set environment variable:')
        print('   PowerShell: $env:SQUARE_ACCESS_TOKEN="your_token_here"')
        print('   CMD: set SQUARE_ACCESS_TOKEN=your_token_here')
        return False
    
    print(f'✓ Square API credentials configured')
    print(f'  Environment: {SQUARE_ENVIRONMENT}')
    print(f'  Token: {SQUARE_ACCESS_TOKEN[:8]}...')
    return True

def make_square_request(endpoint, params=None, method='GET', data=None):
    """Make authenticated request to Square API."""
    headers = {
        'Square-Version': '2024-11-20',  # Latest API version
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
        if hasattr(e.response, 'text'):
            print(f'   Response: {e.response.text}')
        return None

def get_square_locations():
    """Get all Square locations."""
    print('\n' + '=' * 100)
    print('FETCHING SQUARE LOCATIONS')
    print('=' * 100)
    
    result = make_square_request('/v2/locations')
    if not result:
        return []
    
    locations = result.get('locations', [])
    print(f'\nFound {len(locations)} location(s):')
    for loc in locations:
        print(f'  - {loc.get("name")} (ID: {loc.get("id")})')
        print(f'    Address: {loc.get("address", {}).get("address_line_1", "N/A")}')
    
    return locations

def get_square_payments(start_date=None, end_date=None):
    """Get Square payment transactions."""
    print('\n' + '=' * 100)
    print('FETCHING SQUARE PAYMENTS')
    print('=' * 100)
    
    if not start_date:
        # Default: last 90 days
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f'\nDate range: {start_date} to {end_date}')
    
    all_payments = []
    cursor = None
    
    while True:
        data = {
            'begin_time': f'{start_date}T00:00:00Z',
            'end_time': f'{end_date}T23:59:59Z',
            'sort_order': 'ASC',
            'limit': 100
        }
        
        if cursor:
            data['cursor'] = cursor
        
        result = make_square_request('/v2/payments', method='POST', data=data)
        if not result:
            break
        
        payments = result.get('payments', [])
        all_payments.extend(payments)
        
        print(f'  Fetched {len(payments)} payments... (total: {len(all_payments)})')
        
        cursor = result.get('cursor')
        if not cursor:
            break
    
    print(f'\n✓ Retrieved {len(all_payments)} total payments')
    return all_payments

def get_square_orders(start_date=None, end_date=None):
    """Get Square orders (for detailed breakdown)."""
    print('\n' + '=' * 100)
    print('FETCHING SQUARE ORDERS')
    print('=' * 100)
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f'\nDate range: {start_date} to {end_date}')
    
    # Note: Orders API requires location IDs
    locations = get_square_locations()
    if not locations:
        print('⚠ No locations found - skipping orders')
        return []
    
    all_orders = []
    for location in locations:
        location_id = location.get('id')
        cursor = None
        
        while True:
            data = {
                'location_ids': [location_id],
                'query': {
                    'filter': {
                        'date_time_filter': {
                            'created_at': {
                                'start_at': f'{start_date}T00:00:00Z',
                                'end_at': f'{end_date}T23:59:59Z'
                            }
                        }
                    }
                },
                'limit': 100
            }
            
            if cursor:
                data['cursor'] = cursor
            
            result = make_square_request('/v2/orders/search', method='POST', data=data)
            if not result:
                break
            
            orders = result.get('orders', [])
            all_orders.extend(orders)
            
            print(f'  Location {location.get("name")}: {len(orders)} orders... (total: {len(all_orders)})')
            
            cursor = result.get('cursor')
            if not cursor:
                break
    
    print(f'\n✓ Retrieved {len(all_orders)} total orders')
    return all_orders

def get_square_disputes():
    """Get Square disputes (chargebacks, etc.)."""
    print('\n' + '=' * 100)
    print('FETCHING SQUARE DISPUTES')
    print('=' * 100)
    
    all_disputes = []
    cursor = None
    
    while True:
        params = {'limit': 100}
        if cursor:
            params['cursor'] = cursor
        
        result = make_square_request('/v2/disputes', params=params)
        if not result:
            break
        
        disputes = result.get('disputes', [])
        all_disputes.extend(disputes)
        
        print(f'  Fetched {len(disputes)} disputes... (total: {len(all_disputes)})')
        
        cursor = result.get('cursor')
        if not cursor:
            break
    
    print(f'\n✓ Retrieved {len(all_disputes)} total disputes')
    return all_disputes

def get_square_payouts(start_date=None, end_date=None):
    """Get Square payouts (bank transfers)."""
    print('\n' + '=' * 100)
    print('FETCHING SQUARE PAYOUTS')
    print('=' * 100)
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f'\nDate range: {start_date} to {end_date}')
    
    # Get location IDs
    locations = get_square_locations()
    if not locations:
        print('⚠ No locations found')
        return []
    
    location_id = locations[0].get('id')
    
    all_payouts = []
    cursor = None
    
    while True:
        params = {
            'location_id': location_id,
            'begin_time': f'{start_date}T00:00:00Z',
            'end_time': f'{end_date}T23:59:59Z',
            'limit': 100
        }
        
        if cursor:
            params['cursor'] = cursor
        
        result = make_square_request('/v2/payouts', params=params)
        if not result:
            break
        
        payouts = result.get('payouts', [])
        all_payouts.extend(payouts)
        
        print(f'  Fetched {len(payouts)} payouts... (total: {len(all_payouts)})')
        
        cursor = result.get('cursor')
        if not cursor:
            break
    
    print(f'\n✓ Retrieved {len(all_payouts)} total payouts')
    return all_payouts

def calculate_service_fees(payments):
    """Calculate Square service fees from payment data."""
    print('\n' + '=' * 100)
    print('CALCULATING SQUARE SERVICE FEES')
    print('=' * 100)
    
    fee_summary = {
        'total_gross': 0,
        'total_fee': 0,
        'total_net': 0,
        'by_card_brand': {},
        'by_entry_method': {},
        'transactions': []
    }
    
    for payment in payments:
        payment_id = payment.get('id')
        amount_money = payment.get('amount_money', {})
        gross_amount = amount_money.get('amount', 0) / 100  # Convert cents to dollars
        
        # Extract fees
        processing_fee = sum(
            fee.get('amount_money', {}).get('amount', 0) / 100
            for fee in payment.get('processing_fee', [])
        )
        
        net_amount = gross_amount - processing_fee
        
        # Card details
        card_details = payment.get('card_details', {})
        card_brand = card_details.get('card', {}).get('card_brand', 'UNKNOWN')
        entry_method = card_details.get('entry_method', 'UNKNOWN')
        
        # Aggregate by card brand
        if card_brand not in fee_summary['by_card_brand']:
            fee_summary['by_card_brand'][card_brand] = {
                'count': 0,
                'gross': 0,
                'fee': 0,
                'net': 0
            }
        fee_summary['by_card_brand'][card_brand]['count'] += 1
        fee_summary['by_card_brand'][card_brand]['gross'] += gross_amount
        fee_summary['by_card_brand'][card_brand]['fee'] += processing_fee
        fee_summary['by_card_brand'][card_brand]['net'] += net_amount
        
        # Aggregate by entry method
        if entry_method not in fee_summary['by_entry_method']:
            fee_summary['by_entry_method'][entry_method] = {
                'count': 0,
                'gross': 0,
                'fee': 0,
                'net': 0
            }
        fee_summary['by_entry_method'][entry_method]['count'] += 1
        fee_summary['by_entry_method'][entry_method]['gross'] += gross_amount
        fee_summary['by_entry_method'][entry_method]['fee'] += processing_fee
        fee_summary['by_entry_method'][entry_method]['net'] += net_amount
        
        # Overall totals
        fee_summary['total_gross'] += gross_amount
        fee_summary['total_fee'] += processing_fee
        fee_summary['total_net'] += net_amount
        
        # Transaction detail
        fee_summary['transactions'].append({
            'payment_id': payment_id,
            'date': payment.get('created_at'),
            'gross': gross_amount,
            'fee': processing_fee,
            'net': net_amount,
            'card_brand': card_brand,
            'entry_method': entry_method
        })
    
    # Print summary
    print(f'\nOverall Summary:')
    print(f'  Total Transactions: {len(payments)}')
    print(f'  Gross Sales: ${fee_summary["total_gross"]:,.2f}')
    print(f'  Processing Fees: ${fee_summary["total_fee"]:,.2f}')
    print(f'  Net Revenue: ${fee_summary["total_net"]:,.2f}')
    print(f'  Average Fee %: {(fee_summary["total_fee"] / fee_summary["total_gross"] * 100):.2f}%' if fee_summary['total_gross'] > 0 else '  Average Fee %: N/A')
    
    print(f'\nBy Card Brand:')
    for brand, data in sorted(fee_summary['by_card_brand'].items()):
        avg_fee = (data['fee'] / data['gross'] * 100) if data['gross'] > 0 else 0
        print(f'  {brand}: {data["count"]} txns, Gross: ${data["gross"]:,.2f}, Fee: ${data["fee"]:.2f} ({avg_fee:.2f}%)')
    
    print(f'\nBy Entry Method:')
    for method, data in sorted(fee_summary['by_entry_method'].items()):
        avg_fee = (data['fee'] / data['gross'] * 100) if data['gross'] > 0 else 0
        print(f'  {method}: {data["count"]} txns, Gross: ${data["gross"]:,.2f}, Fee: ${data["fee"]:.2f} ({avg_fee:.2f}%)')
    
    return fee_summary

def save_square_data_to_db(payments, orders, payouts, disputes, fee_summary, dry_run=True):
    """Save Square data to PostgreSQL."""
    print('\n' + '=' * 100)
    print('SAVING DATA TO DATABASE' if not dry_run else 'DRY RUN - PREVIEW DATABASE UPDATES')
    print('=' * 100)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Update/insert payments
    print(f'\nProcessing {len(payments)} payments...')
    new_payments = 0
    updated_payments = 0
    
    for payment in payments[:10]:  # Show first 10 as sample
        payment_id = payment.get('id')
        amount = payment.get('amount_money', {}).get('amount', 0) / 100
        status = payment.get('status')
        created_at = payment.get('created_at')
        
        print(f'  Payment {payment_id}: ${amount:.2f}, Status: {status}, Date: {created_at}')
        
        if not dry_run:
            # Check if exists
            cur.execute("SELECT COUNT(*) FROM payments WHERE square_payment_id = %s", (payment_id,))
            exists = cur.fetchone()[0] > 0
            
            if exists:
                # Update existing
                cur.execute("""
                    UPDATE payments 
                    SET amount = %s,
                        square_status = %s,
                        payment_date = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE square_payment_id = %s
                """, (amount, status, created_at, payment_id))
                updated_payments += 1
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO payments 
                    (square_payment_id, amount, square_status, payment_date, payment_method, created_at)
                    VALUES (%s, %s, %s, %s, 'Square', CURRENT_TIMESTAMP)
                """, (payment_id, amount, status, created_at))
                new_payments += 1
    
    if len(payments) > 10:
        print(f'  ... and {len(payments) - 10} more payments')
    
    # Save fee summary
    print(f'\nService fee summary:')
    print(f'  Total Gross: ${fee_summary["total_gross"]:,.2f}')
    print(f'  Total Fees: ${fee_summary["total_fee"]:,.2f}')
    print(f'  Total Net: ${fee_summary["total_net"]:,.2f}')
    
    if not dry_run:
        conn.commit()
        print(f'\n✓ Committed to database:')
        print(f'  New payments: {new_payments}')
        print(f'  Updated payments: {updated_payments}')
    else:
        conn.rollback()
        print(f'\n✓ DRY RUN complete - no changes made')
    
    cur.close()
    conn.close()

def export_fee_report(fee_summary, filename=None):
    """Export service fee report to CSV."""
    if not filename:
        filename = f'L:\\limo\\reports\\Square_Service_Fees_{datetime.now().strftime("%Y%m%d")}.csv'
    
    print(f'\n' + '=' * 100)
    print('EXPORTING SERVICE FEE REPORT')
    print('=' * 100)
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Header
        f.write('Payment ID,Date,Gross Amount,Processing Fee,Net Amount,Card Brand,Entry Method\n')
        
        # Transactions
        for txn in fee_summary['transactions']:
            f.write(f'{txn["payment_id"]},{txn["date"]},')
            f.write(f'${txn["gross"]:.2f},${txn["fee"]:.2f},${txn["net"]:.2f},')
            f.write(f'{txn["card_brand"]},{txn["entry_method"]}\n')
        
        # Summary
        f.write('\n')
        f.write('SUMMARY\n')
        f.write(f'Total Transactions,{len(fee_summary["transactions"])}\n')
        f.write(f'Total Gross Sales,${fee_summary["total_gross"]:.2f}\n')
        f.write(f'Total Processing Fees,${fee_summary["total_fee"]:.2f}\n')
        f.write(f'Total Net Revenue,${fee_summary["total_net"]:.2f}\n')
        avg_pct = (fee_summary["total_fee"] / fee_summary["total_gross"] * 100) if fee_summary["total_gross"] > 0 else 0
        f.write(f'Average Fee Percentage,{avg_pct:.2f}%\n')
    
    print(f'✓ Service fee report exported to: {filename}')
    return filename

def main():
    print('=' * 100)
    print('SQUARE API DATA SYNC')
    print('=' * 100)
    
    # Check credentials
    if not check_square_credentials():
        return
    
    # Get date range from user or use default
    print('\nDate range for data sync:')
    start_date = input('  Start date (YYYY-MM-DD) [default: 90 days ago]: ').strip()
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    end_date = input('  End date (YYYY-MM-DD) [default: today]: ').strip()
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Fetch data
    locations = get_square_locations()
    payments = get_square_payments(start_date, end_date)
    orders = get_square_orders(start_date, end_date)
    payouts = get_square_payouts(start_date, end_date)
    disputes = get_square_disputes()
    
    # Calculate fees
    if payments:
        fee_summary = calculate_service_fees(payments)
        
        # Export fee report
        export_fee_report(fee_summary)
        
        # Save to database
        dry_run_input = input('\nSave to database? (yes/no) [default: no]: ').strip().lower()
        dry_run = dry_run_input != 'yes'
        
        save_square_data_to_db(payments, orders, payouts, disputes, fee_summary, dry_run=dry_run)
    
    print('\n' + '=' * 100)
    print('SQUARE DATA SYNC COMPLETE')
    print('=' * 100)

if __name__ == '__main__':
    main()
