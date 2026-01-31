#!/usr/bin/env python3
"""
Check what Square payment data fields are available from the API.
Look for customer name, email, reference_id, note fields.
"""
import os
import sys
import requests
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import json

load_dotenv("l:/limo/.env")

SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "").strip()
SQUARE_API_BASE = 'https://connect.squareup.com'

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

def get_recent_square_payment_details():
    """Fetch a recent Square payment and show all available fields."""
    
    headers = {
        'Square-Version': '2024-11-20',
        'Authorization': f'Bearer {SQUARE_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Get recent payment
    params = {
        "limit": 1,
        "sort_order": "DESC"
    }
    
    url = f"{SQUARE_API_BASE}/v2/payments"
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    payments = data.get('payments', [])
    
    if not payments:
        print("No payments found")
        return
    
    payment = payments[0]
    
    print("\n" + "="*100)
    print("SQUARE PAYMENT API FIELDS")
    print("="*100)
    print(f"\nRecent payment: {payment.get('id')}")
    print(f"Amount: ${float(payment.get('amount_money', {}).get('amount', 0)) / 100:.2f}")
    print(f"Created: {payment.get('created_at')}")
    
    print("\n" + "-"*100)
    print("ALL AVAILABLE FIELDS:")
    print("-"*100)
    print(json.dumps(payment, indent=2))
    
    # Check database for what we have
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get a sample payment with all fields
    cur.execute("""
        SELECT *
        FROM payments
        WHERE square_payment_id IS NOT NULL
        ORDER BY payment_date DESC
        LIMIT 1
    """)
    
    db_payment = cur.fetchone()
    
    if db_payment:
        print("\n" + "-"*100)
        print("DATABASE PAYMENT FIELDS STORED:")
        print("-"*100)
        for key, value in db_payment.items():
            if value is not None and 'square' in key.lower():
                print(f"{key}: {value}")
    
    # Get customer details if customer_id exists
    customer_id = payment.get('customer_id')
    if customer_id:
        headers = {
            'Square-Version': '2024-11-20',
            'Authorization': f'Bearer {SQUARE_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        print("\n" + "-"*100)
        print("FETCHING CUSTOMER DETAILS:")
        print("-"*100)
        
        customer_url = f"{SQUARE_API_BASE}/v2/customers/{customer_id}"
        customer_response = requests.get(customer_url, headers=headers, timeout=30)
        customer_response.raise_for_status()
        
        customer_data = customer_response.json()
        customer = customer_data.get('customer', {})
        
        print(f"Customer ID: {customer_id}")
        print(f"Given Name: {customer.get('given_name')}")
        print(f"Family Name: {customer.get('family_name')}")
        print(f"Email: {customer.get('email_address')}")
        print(f"Phone: {customer.get('phone_number')}")
        print(f"Reference ID: {customer.get('reference_id')}")
        print(f"Note: {customer.get('note')}")
    
    # Get order details if order_id exists
    order_id = payment.get('order_id')
    if order_id:
        print("\n" + "-"*100)
        print("FETCHING ORDER DETAILS:")
        print("-"*100)
        
        order_url = f"{SQUARE_API_BASE}/v2/orders/{order_id}"
        order_response = requests.get(order_url, headers=headers, timeout=30)
        order_response.raise_for_status()
        
        order_data = order_response.json()
        order = order_data.get('order', {})
        
        print(f"Order ID: {order_id}")
        print(f"Reference ID: {order.get('reference_id')}")
        print(f"Line Items:")
        for item in order.get('line_items', []):
            print(f"  - {item.get('name')}: {item.get('note')}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        get_recent_square_payment_details()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
