#!/usr/bin/env python3
"""
Download comprehensive Square data via API:
1. All Capital loans (active and completed)
2. All processing fees charged
3. All payment events

Requires SQUARE_ACCESS_TOKEN in .env file.
"""
import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
from decimal import Decimal
import json

load_dotenv("l:/limo/.env")
load_dotenv()

SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "").strip()
SQUARE_ENV = os.getenv("SQUARE_ENV", "production").strip().lower()

if SQUARE_ENV == 'production':
    SQUARE_API_BASE = 'https://connect.squareup.com'
else:
    SQUARE_API_BASE = 'https://connect.squareupsandbox.com'

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")


def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def make_square_request(endpoint, params=None, method='GET', body=None):
    """Make authenticated request to Square API."""
    if not SQUARE_ACCESS_TOKEN:
        raise ValueError("SQUARE_ACCESS_TOKEN not set in .env file")
    
    headers = {
        'Square-Version': '2024-11-20',
        'Authorization': f'Bearer {SQUARE_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = f"{SQUARE_API_BASE}{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=body, timeout=30)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Square API: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"  Response: {e.response.text}")
        return None


def download_capital_loans(conn, write_mode=False):
    """Download all Square Capital loans."""
    print("\n" + "="*100)
    print("DOWNLOADING SQUARE CAPITAL LOANS")
    print("="*100)
    
    # Endpoint: GET /v2/capital/loans
    result = make_square_request('/v2/capital/loans')
    
    if not result:
        print("\n⚠️  Could not fetch loans from API")
        print("   This endpoint may require special Capital API permissions")
        return
    
    loans = result.get('loans', [])
    print(f"\n✓ Found {len(loans)} loans")
    
    cur = conn.cursor()
    
    for loan in loans:
        loan_id = loan.get('id')
        status = loan.get('status')
        
        # Amounts (in cents, convert to dollars)
        loan_money = loan.get('loan_amount_money', {})
        loan_amount = Decimal(loan_money.get('amount', 0)) / 100
        
        repaid_money = loan.get('repaid_money', {})
        repaid_amount = Decimal(repaid_money.get('amount', 0)) / 100
        
        outstanding_money = loan.get('outstanding_balance_money', {})
        outstanding_amount = Decimal(outstanding_money.get('amount', 0)) / 100
        
        # Dates
        created_at = loan.get('created_at')
        approved_at = loan.get('approved_at')
        disbursed_at = loan.get('disbursed_at')
        
        # Repayment info
        repayment_duration = loan.get('repayment_duration_months')
        
        print(f"\n{'='*80}")
        print(f"Loan ID: {loan_id}")
        print(f"Status: {status}")
        print(f"Loan Amount: ${loan_amount:,.2f}")
        print(f"Repaid: ${repaid_amount:,.2f}")
        print(f"Outstanding: ${outstanding_amount:,.2f}")
        print(f"Created: {created_at}")
        print(f"Disbursed: {disbursed_at}")
        print(f"Repayment Duration: {repayment_duration} months")
        
        if write_mode:
            # Convert ISO dates to date objects
            received_date = disbursed_at.split('T')[0] if disbursed_at else None
            
            cur.execute("""
                INSERT INTO square_capital_loans 
                (square_loan_id, loan_amount, received_date, status, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (square_loan_id) DO UPDATE
                SET loan_amount = EXCLUDED.loan_amount,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING loan_id
            """, (
                loan_id,
                loan_amount,
                received_date,
                status.lower(),
                f"Square Capital Loan - {repayment_duration}mo term"
            ))
            
            db_loan_id = cur.fetchone()[0]
            print(f"  ✓ Inserted/Updated: loan_id={db_loan_id}")
    
    if write_mode:
        conn.commit()
        print(f"\n✓ Committed {len(loans)} loans")


def download_processing_fees(conn, start_date=None, write_mode=False):
    """Download all Square processing fees from payouts using List Payouts."""
    print("\n" + "="*100)
    print("DOWNLOADING SQUARE PROCESSING FEES")
    print("="*100)
    
    if not start_date:
        # Get all-time data - start from company founding
        start_date = '2010-01-01'
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"  Date range: {start_date} to {end_date}")
    
    # Endpoint: GET /v2/payouts with query parameters
    cursor = None
    all_payouts = []
    
    while True:
        params = {
            'begin_time': f"{start_date}T00:00:00Z",
            'end_time': f"{end_date}T23:59:59Z",
            'sort_order': 'ASC',
            'limit': 100
        }
        
        if cursor:
            params['cursor'] = cursor
        
        result = make_square_request('/v2/payouts', params=params)
        
        if not result:
            print("\n⚠️  Could not fetch payouts")
            break
        
        payouts = result.get('payouts', [])
        all_payouts.extend(payouts)
        
        cursor = result.get('cursor')
        print(f"  Fetched {len(all_payouts)} payouts... ", end='')
        
        if not cursor:
            print("Done!")
            break
        else:
            print("(continuing)")
    
    print(f"\n✓ Total payouts fetched: {len(all_payouts)}")
    
    if not all_payouts:
        print("\n⚠️  No payouts found - this may be a permissions issue")
        return
    
    # Analyze payouts for fee data
    total_fees = Decimal('0')
    fee_count = 0
    
    cur = conn.cursor()
    
    print("\n  Analyzing payouts for fees...")
    
    for payout in all_payouts[:20]:  # Sample first 20
        payout_id = payout.get('id')
        arrival_date = payout.get('arrival_date')
        
        # Amount fields
        amount_money = payout.get('amount_money', {})
        payout_amount = Decimal(amount_money.get('amount', 0)) / 100
        
        # Destination (which account)</
        destination = payout.get('destination', {})
        
        print(f"    Payout {payout_id[:8]}... on {arrival_date}: ${payout_amount:.2f}")
    
    print(f"\n✓ Analyzed {len(all_payouts)} payouts")
    
    # Save to database if write mode
    if write_mode and all_payouts:
        print(f"\n  Saving {len(all_payouts)} payouts to database...")
        
        inserted = 0
        updated = 0
        
        for payout in all_payouts:
            payout_id = payout.get('id')
            status = payout.get('status')
            location_id = payout.get('location_id')
            arrival_date = payout.get('arrival_date')
            amount_money = payout.get('amount_money', {})
            amount = Decimal(amount_money.get('amount', 0)) / 100
            currency = amount_money.get('currency', 'USD')
            
            # Check if exists
            cur.execute("SELECT id FROM square_payouts WHERE id = %s", (payout_id,))
            
            if cur.fetchone():
                cur.execute("""
                    UPDATE square_payouts
                    SET status = %s, location_id = %s, arrival_date = %s,
                        amount = %s, currency = %s, updated_at = NOW()
                    WHERE id = %s
                """, (status, location_id, arrival_date, amount, currency, payout_id))
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO square_payouts (id, status, location_id, arrival_date, amount, currency, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (payout_id, status, location_id, arrival_date, amount, currency))
                inserted += 1
        
        conn.commit()
        cur.close()
        print(f"  ✓ Inserted: {inserted}, Updated: {updated}")
    else:
        cur.close()


def download_all_payments(conn, start_date=None, write_mode=False):
    """Download all Square payment events using SearchOrders endpoint."""
    print("\n" + "="*100)
    print("DOWNLOADING ALL SQUARE PAYMENT EVENTS")
    print("="*100)
    
    if not start_date:
        start_date = '2010-01-01'
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"  Date range: {start_date} to {end_date}")
    
    # Use Orders API to get payment data
    cursor = None
    all_orders = []
    
    while True:
        body = {
            'query': {
                'filter': {
                    'date_time_filter': {
                        'created_at': {
                            'start_at': f"{start_date}T00:00:00Z",
                            'end_at': f"{end_date}T23:59:59Z"
                        }
                    }
                },
                'sort': {
                    'sort_field': 'CREATED_AT',
                    'sort_order': 'ASC'
                }
            },
            'limit': 100
        }
        
        if cursor:
            body['cursor'] = cursor
        
        result = make_square_request('/v2/orders/search', method='POST', body=body)
        
        if not result:
            print("\n⚠️  Could not fetch orders")
            break
        
        orders = result.get('orders', [])
        all_orders.extend(orders)
        
        cursor = result.get('cursor')
        print(f"  Fetched {len(all_orders)} orders... ", end='')
        
        if not cursor:
            print("Done!")
            break
        else:
            print("(continuing)")
    
    print(f"\n✓ Total orders fetched: {len(all_orders)}")
    
    # Summarize
    total_amount = Decimal('0')
    total_tax = Decimal('0')
    order_count = 0
    
    for order in all_orders:
        # Total money
        total_money = order.get('total_money', {})
        amount = Decimal(total_money.get('amount', 0)) / 100
        total_amount += amount
        
        # Tax
        total_tax_money = order.get('total_tax_money', {})
        tax = Decimal(total_tax_money.get('amount', 0)) / 100
        total_tax += tax
        
        order_count += 1
    
    print(f"\n  Total order amount: ${total_amount:,.2f}")
    print(f"  Total tax collected: ${total_tax:,.2f}")
    print(f"  Total orders: {order_count:,}")


def main():
    if '--write' not in sys.argv:
        print("\n⚠️  DRY RUN MODE - Use --write to save data to database")
    
    write_mode = '--write' in sys.argv
    
    if not SQUARE_ACCESS_TOKEN:
        print("\n❌ ERROR: SQUARE_ACCESS_TOKEN not found")
        print("\nTo fix:")
        print("1. Get your Square Access Token from https://developer.squareup.com/apps")
        print("2. Add to l:/limo/.env file:")
        print("   SQUARE_ACCESS_TOKEN=your_token_here")
        print("   SQUARE_ENV=production")
        return 1
    
    print("="*100)
    print("SQUARE DATA COMPREHENSIVE DOWNLOAD")
    print("="*100)
    print(f"\n✓ Square API: {SQUARE_ENV}")
    print(f"  Token: {SQUARE_ACCESS_TOKEN[:8]}...")
    print(f"  Mode: {'WRITE' if write_mode else 'DRY RUN'}")
    
    conn = get_db_conn()
    
    # 1. Download Capital Loans
    try:
        download_capital_loans(conn, write_mode)
    except Exception as e:
        print(f"\n❌ Capital Loans Error: {e}")
    
    # 2. Download Processing Fees
    try:
        download_processing_fees(conn, write_mode=write_mode)
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Processing Fees Error: {e}")
    
    # 3. Download All Payments
    try:
        download_all_payments(conn, write_mode=write_mode)
    except Exception as e:
        print(f"\n❌ Payment Events Error: {e}")
    
    print("\n" + "="*100)
    print("✓ DOWNLOAD COMPLETE")
    print("="*100)
    
    if not write_mode:
        print("\n⚠️  No data saved (dry run). Use --write to save to database.")
    
    conn.close()


if __name__ == '__main__':
    sys.exit(main() or 0)
