#!/usr/bin/env python3
"""
Extract GlobalPayments merchant statement data properly from PDF.
This extracts actual credit card transaction data from card readers.

Usage:
    python scripts/extract_globalpayments_merchant_data.py --pdf "path/to/merchant_statement.pdf" --write
"""

import argparse
import json
import csv
import re
from datetime import datetime
import PyPDF2
import pandas as pd
from pathlib import Path


def extract_merchant_statement_data(pdf_path):
    """Extract credit card transaction data from GlobalPayments merchant statement."""
    
    print(f"📄 Processing GlobalPayments merchant statement: {pdf_path}")
    
    # Initialize data structures
    deposits_data = []
    card_summary = {}
    statement_info = {}
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            full_text = ""
            
            # Extract text from all pages
            for page in pdf_reader.pages:
                full_text += page.extract_text() + "\n"
        
        print("📊 Extracting statement information...")
        
        # Extract statement header info
        statement_date_match = re.search(r'Statement Date\s+(\d{1,2}/\d{1,2}/\d{2,4})', full_text)
        if statement_date_match:
            statement_info['statement_date'] = statement_date_match.group(1)
        
        chain_number_match = re.search(r'Chain Number\s+(\d{3}-\d{2}-\d{3}-\d{3}-\d{3})', full_text)
        if chain_number_match:
            statement_info['chain_number'] = chain_number_match.group(1)
        
        merchant_number_match = re.search(r'Merchant Number\s+(\d+)', full_text)
        if merchant_number_match:
            statement_info['merchant_number'] = merchant_number_match.group(1)
        
        print("💳 Extracting daily deposits...")
        
        # Extract deposits section - this contains daily credit card sales
        deposits_pattern = r'Day\s+Ref No\s+Items\s+Sales\s+Returns\s+Non-funded\s+Discount\s+Net Deposit\s*((?:\d{2}\s+\d+\s+\d+\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s*)+)'
        
        deposits_match = re.search(deposits_pattern, full_text, re.MULTILINE)
        if deposits_match:
            deposits_text = deposits_match.group(1)
            
            # Parse individual deposit lines
            deposit_lines = re.findall(r'(\d{2})\s+(\d+)\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)', deposits_text)
            
            for line in deposit_lines:
                day, ref_no, items, sales, returns, non_funded, discount, net_deposit = line
                
                # Convert statement date + day to full date
                if statement_info.get('statement_date'):
                    try:
                        stmt_date = datetime.strptime(statement_info['statement_date'], '%m/%d/%y')
                        full_date = stmt_date.replace(day=int(day))
                        
                        deposits_data.append({
                            'transaction_date': full_date.strftime('%Y-%m-%d'),
                            'day': int(day),
                            'ref_number': ref_no,
                            'item_count': int(items),
                            'gross_sales': float(sales.replace(',', '')),
                            'returns': float(returns.replace(',', '')),
                            'non_funded': float(non_funded.replace(',', '')),
                            'discount_fees': float(discount.replace(',', '')),
                            'net_deposit': float(net_deposit.replace(',', ''))
                        })
                    except ValueError as e:
                        print(f"[WARN] Date parsing error for day {day}: {e}")
        
        print("💳 Extracting card type summary...")
        
        # Extract card summary section
        card_summary_pattern = r'Day\s+Visa\s+Debit\s+MasterCard\s+Amex\s+Diners\s+Others\s*((?:\d{2}\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s*)+)'
        
        card_match = re.search(card_summary_pattern, full_text, re.MULTILINE)
        if card_match:
            card_text = card_match.group(1)
            
            # Parse card type totals
            card_totals = {'VISA': 0, 'DEBIT': 0, 'MASTERCARD': 0, 'AMEX': 0, 'DINERS': 0, 'OTHERS': 0}
            
            card_lines = re.findall(r'(\d{2})\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)', card_text)
            
            for line in card_lines:
                day, visa, debit, mastercard, amex, diners, others = line
                card_totals['VISA'] += float(visa.replace(',', ''))
                card_totals['DEBIT'] += float(debit.replace(',', ''))
                card_totals['MASTERCARD'] += float(mastercard.replace(',', ''))
                card_totals['AMEX'] += float(amex.replace(',', ''))
                card_totals['DINERS'] += float(diners.replace(',', ''))
                card_totals['OTHERS'] += float(others.replace(',', ''))
            
            card_summary = card_totals
        
        print("💰 Extracting discount/fee details...")
        
        # Extract discount section for processing fees
        discount_pattern = r'Description\s+Items\s+Amount\s+Avg Ticket\s+Disc Rate\s+Item Rate\s+Fee Amount\s*((?:.*?\s+\d+\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s*)+)'
        
        # This would extract processing fee details by card type
        
        return {
            'statement_info': statement_info,
            'deposits': deposits_data,
            'card_summary': card_summary,
            'total_transactions': len(deposits_data),
            'total_gross_sales': sum(d['gross_sales'] for d in deposits_data),
            'total_net_deposits': sum(d['net_deposit'] for d in deposits_data),
            'total_fees': sum(d['discount_fees'] for d in deposits_data)
        }
        
    except Exception as e:
        print(f"[FAIL] Error processing PDF: {e}")
        return None


def save_extracted_data(data, output_dir):
    """Save extracted data to CSV and JSON files."""
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Save deposits as CSV for easy import
    deposits_csv = output_path / 'globalpayments_deposits_corrected.csv'
    if data['deposits']:
        df = pd.DataFrame(data['deposits'])
        df.to_csv(deposits_csv, index=False)
        print(f"💾 Saved deposits data: {deposits_csv}")
    
    # Save card summary as CSV
    card_csv = output_path / 'globalpayments_card_summary.csv'
    if data['card_summary']:
        card_df = pd.DataFrame([data['card_summary']])
        card_df.to_csv(card_csv, index=False)
        print(f"💾 Saved card summary: {card_csv}")
    
    # Save complete data as JSON
    json_file = output_path / 'globalpayments_complete_data.json'
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"💾 Saved complete data: {json_file}")
    
    return {
        'deposits_csv': deposits_csv,
        'card_csv': card_csv,
        'json_file': json_file
    }


def main():
    parser = argparse.ArgumentParser(description='Extract GlobalPayments merchant statement data')
    parser.add_argument('--pdf', default=r'l:/limo/CIBC UPLOADS/2012 merchant statement globalpayments.pdf',
                       help='Path to GlobalPayments merchant statement PDF')
    parser.add_argument('--output', default=r'l:/limo/staging/2012_merchant_statements_corrected',
                       help='Output directory for extracted data')
    parser.add_argument('--write', action='store_true',
                       help='Write extracted data to files')
    
    args = parser.parse_args()
    
    print("🏦 GlobalPayments Merchant Statement Data Extractor")
    print("=" * 60)
    
    # Check if PDF exists
    if not Path(args.pdf).exists():
        print(f"[FAIL] PDF file not found: {args.pdf}")
        return
    
    # Extract data from PDF
    data = extract_merchant_statement_data(args.pdf)
    
    if not data:
        print("[FAIL] Failed to extract data from PDF")
        return
    
    # Display summary
    print("\n📊 EXTRACTION SUMMARY")
    print("-" * 40)
    print(f"Statement Date: {data['statement_info'].get('statement_date', 'Unknown')}")
    print(f"Chain Number: {data['statement_info'].get('chain_number', 'Unknown')}")
    print(f"Merchant Number: {data['statement_info'].get('merchant_number', 'Unknown')}")
    print(f"Total Transactions: {data['total_transactions']}")
    print(f"Total Gross Sales: ${data['total_gross_sales']:,.2f}")
    print(f"Total Net Deposits: ${data['total_net_deposits']:,.2f}")
    print(f"Total Processing Fees: ${data['total_fees']:,.2f}")
    
    if data['card_summary']:
        print("\n💳 CARD TYPE BREAKDOWN")
        print("-" * 30)
        for card_type, amount in data['card_summary'].items():
            if amount > 0:
                print(f"{card_type}: ${amount:,.2f}")
    
    if args.write:
        print("\n💾 SAVING DATA FILES...")
        files = save_extracted_data(data, args.output)
        print("[OK] Data extraction completed successfully!")
        
        print(f"\n📁 Files created:")
        for file_type, file_path in files.items():
            print(f"  {file_type}: {file_path}")
    else:
        print("\n[WARN] Dry run mode - use --write to save files")


if __name__ == "__main__":
    main()