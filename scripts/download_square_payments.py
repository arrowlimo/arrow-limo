#!/usr/bin/env python3
"""
Download recent Square payment data via API and import to payments table.
Downloads payments from last import date through today.
"""
import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import re

# Load environment variables
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
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

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
        raise ValueError("SQUARE_ACCESS_TOKEN not set in environment")
    
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
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Square API error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

def extract_reserve_number(note):
    """Extract reserve number from payment note/description."""
    if not note:
        return None
    # Look for 5-6 digit numbers
    match = re.search(r'\b(\d{5,6})\b', note)
    return match.group(1) if match else None

def get_last_square_payment_date(conn):
    """Get the most recent Square payment date in database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(payment_date)::text
        FROM payments
        WHERE square_payment_id IS NOT NULL 
           OR square_transaction_id IS NOT NULL
    """)
    result = cur.fetchone()
    cur.close()
    
    if result and result[0]:
        return result[0]
    else:
        # Default to 120 days ago if no Square payments exist
        return (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

def download_square_payments(start_date, end_date, write_mode=False):
    """Download Square payments from API for date range."""
    
    print("\n" + "="*100)
    print("DOWNLOAD SQUARE PAYMENTS FROM API")
    print("="*100)
    print(f"\nDate range: {start_date} to {end_date}")
    print(f"Mode: {'WRITE' if write_mode else 'DRY RUN'}")
    
    if not write_mode:
        print("\n⚠️  DRY RUN - Use --write to import data\n")
    
    # Use list payments endpoint instead (search payments requires source_id)
    # List payments endpoint: GET /v2/payments with query params
    params = {
        "begin_time": f"{start_date}T00:00:00Z",
        "end_time": f"{end_date}T23:59:59Z",
        "limit": 100,
        "sort_order": "ASC"
    }
    
    all_payments = []
    cursor = None
    
    print("\nFetching payments from Square API...")
    
    while True:
        if cursor:
            params['cursor'] = cursor
        
        try:
            response = make_square_request('/v2/payments', params=params, method='GET')
        except Exception as e:
            print(f"\n✗ Failed to fetch payments: {e}")
            return 0
        
        payments = response.get('payments', [])
        all_payments.extend(payments)
        
        print(f"  Fetched {len(payments)} payments (total: {len(all_payments)})")
        
        cursor = response.get('cursor')
        if not cursor:
            break
    
    if not all_payments:
        print("\n✓ No new Square payments found")
        return 0
    
    print(f"\nTotal payments retrieved: {len(all_payments)}")
    
    # Process payments
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    imported = 0
    updated = 0
    skipped = 0
    
    for payment in all_payments:
        payment_id = payment.get('id')
        amount_money = payment.get('amount_money', {})
        amount = float(amount_money.get('amount', 0)) / 100  # Convert cents to dollars
        currency = amount_money.get('currency', 'CAD')
        
        # Arrow Limousine is Canadian - expect CAD payments
        if currency not in ['CAD', 'USD']:
            print(f"⚠️  Skipping non-CAD/USD payment: {payment_id} ({currency})")
            skipped += 1
            continue
        
        # Extract details
        created_at = payment.get('created_at', '')
        payment_date = created_at[:10] if created_at else None  # YYYY-MM-DD
        
        status = payment.get('status', '')
        if status != 'COMPLETED':
            print(f"⚠️  Skipping non-completed payment: {payment_id} (status: {status})")
            skipped += 1
            continue
        
        card_details = payment.get('card_details', {})
        card_brand = card_details.get('card', {}).get('card_brand')
        last_4 = card_details.get('card', {}).get('last_4')
        
        # Extract customer info
        customer_id = payment.get('customer_id')
        customer_email = None
        customer_name = None
        
        if customer_id:
            # Fetch customer details
            try:
                customer_response = make_square_request(f'/v2/customers/{customer_id}', method='GET')
                customer = customer_response.get('customer', {})
                customer_email = customer.get('email_address')
                given_name = customer.get('given_name', '')
                family_name = customer.get('family_name', '')
                if given_name or family_name:
                    customer_name = f"{given_name} {family_name}".strip()
            except Exception as e:
                print(f"    ⚠️  Failed to fetch customer {customer_id}: {e}")
        
        note = payment.get('note', '') or payment.get('reference_id', '') or ''
        reserve_number = extract_reserve_number(note)
        
        # Try to find charter
        charter_id = None
        if reserve_number:
            cur.execute('SELECT charter_id FROM charters WHERE reserve_number = %s', (reserve_number,))
            result = cur.fetchone()
            if result:
                charter_id = result['charter_id']
        
        # Check if payment already exists
        cur.execute("""
            SELECT payment_id FROM payments 
            WHERE square_payment_id = %s OR square_transaction_id = %s
        """, (payment_id, payment_id))
        
        existing = cur.fetchone()
        
        if write_mode:
            if existing:
                # Update existing
                cur.execute("""
                    UPDATE payments
                    SET amount = %s,
                        payment_date = %s,
                        charter_id = %s,
                        reserve_number = %s,
                        square_card_brand = %s,
                        square_last4 = %s,
                        square_customer_name = %s,
                        square_customer_email = %s,
                        notes = %s,
                        updated_at = NOW()
                    WHERE payment_id = %s
                """, (amount, payment_date, charter_id, reserve_number, card_brand, last_4, customer_name, customer_email, note, existing['payment_id']))
                updated += 1
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO payments (
                        amount, payment_date, payment_method,
                        charter_id, reserve_number,
                        square_payment_id, square_transaction_id,
                        square_card_brand, square_last4, square_status,
                        square_customer_name, square_customer_email,
                        notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, 'credit_card',
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, NOW(), NOW()
                    )
                """, (amount, payment_date, charter_id, reserve_number, 
                      payment_id, payment_id, card_brand, last_4, status,
                      customer_name, customer_email, note))
                imported += 1
        else:
            if existing:
                print(f"  Would update: {payment_id} ${amount:.2f} on {payment_date} (charter: {reserve_number or 'none'})")
                updated += 1
            else:
                print(f"  Would import: {payment_id} ${amount:.2f} on {payment_date} (charter: {reserve_number or 'none'})")
                imported += 1
    
    if write_mode:
        conn.commit()
        print(f"\n✓ COMMITTED:")
    else:
        print(f"\nDRY RUN summary:")
    
    print(f"  Imported: {imported}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Total processed: {len(all_payments)}")
    
    cur.close()
    conn.close()
    
    return imported + updated

def main():
    write_mode = '--write' in sys.argv
    
    if not SQUARE_ACCESS_TOKEN:
        print("✗ SQUARE_ACCESS_TOKEN not found in .env file")
        print("  Please add SQUARE_ACCESS_TOKEN to l:/limo/.env")
        sys.exit(1)
    
    conn = get_db_conn()
    
    # Get last payment date
    last_date = get_last_square_payment_date(conn)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Start from day after last payment
    start_date_obj = datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)
    start_date = start_date_obj.strftime('%Y-%m-%d')
    
    print(f"\nLast Square payment in database: {last_date}")
    print(f"Will download from: {start_date} to {today}")
    
    conn.close()
    
    # Download and import
    count = download_square_payments(start_date, today, write_mode)
    
    if count > 0 and not write_mode:
        print("\n✓ Run with --write to import these payments")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
