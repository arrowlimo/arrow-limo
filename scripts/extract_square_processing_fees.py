#!/usr/bin/env python3
"""
Extract and import Square processing fees from downloaded payout data.
Creates receipt records for all Square merchant processing fees.
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from decimal import Decimal

load_dotenv("l:/limo/.env")
load_dotenv()

SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "").strip()
SQUARE_API_BASE = 'https://connect.squareup.com'

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")


def make_square_request(endpoint, params=None):
    """Make authenticated request to Square API."""
    if not SQUARE_ACCESS_TOKEN:
        raise ValueError("SQUARE_ACCESS_TOKEN not set")
    
    headers = {
        'Square-Version': '2024-11-20',
        'Authorization': f'Bearer {SQUARE_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = f"{SQUARE_API_BASE}{endpoint}"
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def download_payouts():
    """Download all Square payouts with fee data."""
    print("📥 Downloading Square payouts...")
    
    all_payouts = []
    cursor = None
    
    params = {
        'begin_time': '2020-01-01T00:00:00Z',
        'end_time': '2026-01-29T23:59:59Z',
        'sort_order': 'ASC',
        'limit': 100
    }
    
    while True:
        if cursor:
            params['cursor'] = cursor
        
        result = make_square_request('/v2/payouts', params=params)
        
        payouts = result.get('payouts', [])
        all_payouts.extend(payouts)
        
        cursor = result.get('cursor')
        if not cursor:
            break
        
        if len(all_payouts) % 100 == 0:
            print(f"  Fetched {len(all_payouts)} payouts...")
    
    print(f"✓ Downloaded {len(all_payouts)} payouts")
    return all_payouts


def extract_payout_fees(payouts):
    """Extract processing fee data from payouts."""
    print("\n📊 Analyzing payouts for fees...")
    
    fee_records = []
    
    for payout in payouts:
        payout_id = payout.get('id')
        arrival_date_str = payout.get('arrival_date')  # YYYY-MM-DD
        
        # Parse payout entries for fees
        payout_entries = payout.get('payout_entries', [])
        
        # Amount is in cents
        amount_cents = payout.get('amount_money', {}).get('amount', 0)
        amount = Decimal(amount_cents) / 100
        
        # Get detailed fee breakdown if available
        fee_cents = 0
        for entry in payout_entries:
            if entry.get('type') == 'CHARGE':
                # This has fee details
                fee_money = entry.get('gross_amount_money', {})
                fee_cents += fee_money.get('amount', 0)
        
        # For now, we'll need to get individual payout details
        # The summary doesn't include fees - need to fetch payout details
        
        fee_records.append({
            'payout_id': payout_id,
            'date': arrival_date_str,
            'payout_amount': amount
        })
    
    return fee_records


def get_payout_details(payout_id):
    """Get detailed payout information including fees."""
    try:
        result = make_square_request(f'/v2/payouts/{payout_id}')
        payout = result.get('payout', {})
        
        # Extract fee information
        # Fee = gross sales - net payout
        return payout
    except Exception as e:
        print(f"  Error fetching payout {payout_id}: {e}")
        return None


def import_fees_as_receipts(conn, fee_records, dry_run=True):
    """Import Square processing fees as receipts."""
    cur = conn.cursor()
    vendor_name = 'SQUARE PROCESSING FEES'
    
    try:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing processing fees...")
        
        # Check existing
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE UPPER(vendor_name) = %s
        """, (vendor_name.upper(),))
        
        existing = cur.fetchone()[0]
        print(f"💾 Existing fee receipts: {existing}")
        
        # For now, just show summary since we need detailed payout data
        print(f"\n⚠️  Note: Square payout API doesn't include fee breakdown in list")
        print(f"   Need to fetch each payout individually to extract fees")
        print(f"   This would require {len(fee_records)} API calls")
        print(f"\n   Alternative: Calculate fees from banking reconciliation")
        
        return 0, 0
        
    finally:
        cur.close()


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    print("=" * 70)
    print("SQUARE PROCESSING FEES EXTRACTION")
    print("=" * 70)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --write to apply changes\n")
    
    try:
        # Download payouts
        payouts = download_payouts()
        
        # Extract fee data
        fee_records = extract_payout_fees(payouts)
        
        # Sample: get detailed data for first few payouts
        print(f"\n🔍 Sampling first 3 payouts for fee structure...")
        for i in range(min(3, len(payouts))):
            payout = payouts[i]
            payout_id = payout.get('id')
            print(f"\n  Payout {payout_id}:")
            print(f"    Arrival: {payout.get('arrival_date')}")
            print(f"    Amount: ${Decimal(payout.get('amount_money', {}).get('amount', 0)) / 100:.2f}")
            print(f"    Status: {payout.get('status')}")
            
            # Get details
            details = get_payout_details(payout_id)
            if details:
                print(f"    Type: {details.get('type')}")
                # Show what data is available
                if 'payout_fee' in details:
                    fee_cents = details['payout_fee'].get('amount_money', {}).get('amount', 0)
                    print(f"    Fee: ${Decimal(fee_cents) / 100:.2f}")
        
        # Connect to DB
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        try:
            # Import fees
            import_fees_as_receipts(conn, fee_records, dry_run)
            
            print("\n" + "=" * 70)
            print("✓ ANALYSIS COMPLETE")
            print("=" * 70)
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
