#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Wix API client to retrieve invoices and billing information.
Requires: Wix API key stored in environment variable WIX_API_KEY
"""

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

class WixApiClient:
    """Wix API client for retrieving billing and invoice data."""
    
    BASE_URL = "https://www.wixapis.com/v1"
    
    def __init__(self, api_key):
        """Initialize Wix API client with API key."""
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_account_info(self):
        """Get account information."""
        endpoint = f"{self.BASE_URL}/accounts/account"
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting account info: {e}")
            return None
    
    def get_invoices(self):
        """Get all invoices from Wix account."""
        endpoint = f"{self.BASE_URL}/billing/invoices"
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get('invoices', [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting invoices: {e}")
            return []
    
    def get_invoice_details(self, invoice_id):
        """Get detailed information for a specific invoice."""
        endpoint = f"{self.BASE_URL}/billing/invoices/{invoice_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting invoice {invoice_id}: {e}")
            return None
    
    def download_invoice_pdf(self, invoice_id, output_dir):
        """Download invoice PDF."""
        endpoint = f"{self.BASE_URL}/billing/invoices/{invoice_id}/download-url"
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            download_url = data.get('downloadUrl')
            if not download_url:
                print(f"❌ No download URL for invoice {invoice_id}")
                return None
            
            # Download PDF
            pdf_response = requests.get(download_url)
            pdf_response.raise_for_status()
            
            # Save file
            output_path = Path(output_dir) / f"wix_invoice_{invoice_id}.pdf"
            with open(output_path, 'wb') as f:
                f.write(pdf_response.content)
            
            return str(output_path)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading PDF for {invoice_id}: {e}")
            return None

def main():
    """Main function to retrieve and download Wix invoices."""
    
    # Get API key from environment
    api_key = os.getenv('WIX_API_KEY')
    
    if not api_key:
        print("❌ ERROR: WIX_API_KEY environment variable not set")
        print("\nTo set up Wix API key:")
        print("  1. Login to Wix Dashboard")
        print("  2. Go to Settings → API & Extensions → API Keys")
        print("  3. Create/copy your API key")
        print("  4. Set environment variable: $env:WIX_API_KEY='your-api-key'")
        return False
    
    # Initialize client
    client = WixApiClient(api_key)
    
    print("🔗 Connecting to Wix API...")
    
    # Get account info
    account = client.get_account_info()
    if account:
        print(f"✅ Connected to Wix account: {account.get('name', 'N/A')}")
    else:
        print("❌ Failed to connect to Wix account")
        return False
    
    # Get invoices
    print("\n📋 Retrieving invoices...")
    invoices = client.get_invoices()
    
    if not invoices:
        print("❌ No invoices found")
        return False
    
    print(f"✅ Found {len(invoices)} invoices")
    
    # Create output directory
    output_dir = Path('l:\\limo\\wix')
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n💾 Saving to: {output_dir}")
    
    # Process each invoice
    invoice_data = []
    downloaded_count = 0
    
    for i, invoice in enumerate(invoices, 1):
        invoice_id = invoice.get('id')
        invoice_date = invoice.get('invoiceDate', 'N/A')
        amount = invoice.get('amount', {}).get('value', 0)
        status = invoice.get('status', 'unknown')
        
        print(f"\n{i}. Invoice {invoice_id}")
        print(f"   Date: {invoice_date}")
        print(f"   Amount: ${amount}")
        print(f"   Status: {status}")
        
        # Get detailed invoice
        details = client.get_invoice_details(invoice_id)
        if details:
            invoice_number = details.get('invoiceNumber', invoice_id)
            print(f"   Invoice #: {invoice_number}")
            
            # Download PDF
            pdf_path = client.download_invoice_pdf(invoice_id, output_dir)
            if pdf_path:
                print(f"   ✅ Downloaded: {Path(pdf_path).name}")
                downloaded_count += 1
            
            # Store data
            invoice_data.append({
                'invoice_id': invoice_id,
                'invoice_number': invoice_number,
                'date': invoice_date,
                'amount': amount,
                'status': status,
                'pdf_path': pdf_path
            })
    
    # Export to CSV
    print(f"\n📊 Exporting invoice summary...")
    
    csv_path = output_dir / 'wix_invoices_summary.csv'
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('Invoice ID,Invoice Number,Date,Amount,Status,PDF Path\n')
        for inv in invoice_data:
            f.write(f"{inv['invoice_id']},{inv['invoice_number']},{inv['date']},{inv['amount']},{inv['status']},{inv['pdf_path']}\n")
    
    print(f"✅ Summary exported to: {csv_path.name}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ WIX INVOICE RETRIEVAL COMPLETE")
    print(f"{'='*60}")
    print(f"Total invoices: {len(invoices)}")
    print(f"Downloaded PDFs: {downloaded_count}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}\n")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
