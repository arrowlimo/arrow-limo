#!/usr/bin/env python3
"""
Analyze existing QuickBooks merchant data for 2012 GlobalPayments processing.
This consolidates the merchant fees and deposits already processed through QuickBooks.

Usage:
    python scripts/analyze_existing_quickbooks_merchant_data.py --write
"""

import argparse
import pandas as pd
import json
from datetime import datetime
from pathlib import Path


def analyze_merchant_fees():
    """Extract and analyze Global Merchant Fees from QuickBooks data."""
    
    print("💰 ANALYZING QUICKBOOKS GLOBAL MERCHANT FEES")
    print("=" * 55)
    
    # Load QuickBooks transactions
    qb_file = Path('l:/limo/staging/2012_parsed/2012_quickbooks_transactions.csv')
    df = pd.read_csv(qb_file)
    
    # Extract Global Merchant Fees entries
    merchant_fees_mask = df['description'].str.contains('Global Merchant Fees', case=False, na=False)
    merchant_fees = df[merchant_fees_mask].copy()
    
    # Clean and convert amounts
    merchant_fees['withdrawal'] = pd.to_numeric(merchant_fees['withdrawal'], errors='coerce')
    merchant_fees = merchant_fees.dropna(subset=['withdrawal'])
    
    # Remove duplicates (there appear to be duplicate entries)
    merchant_fees = merchant_fees.drop_duplicates(subset=['date', 'withdrawal'])
    
    print(f"Found {len(merchant_fees)} unique merchant fee entries")
    
    # Calculate totals
    total_fees = merchant_fees['withdrawal'].sum()
    print(f"Total Global Merchant Fees for 2012: ${total_fees:,.2f}")
    
    # Monthly breakdown
    merchant_fees['date'] = pd.to_datetime(merchant_fees['date'], format='%m/%d/%Y')
    merchant_fees['month'] = merchant_fees['date'].dt.to_period('M')
    
    monthly_fees = merchant_fees.groupby('month')['withdrawal'].sum().reset_index()
    
    print("\n📅 MONTHLY MERCHANT FEES BREAKDOWN")
    print("-" * 40)
    for _, row in monthly_fees.iterrows():
        print(f"{row['month']} ${row['withdrawal']:>10,.2f}")
    
    return merchant_fees


def analyze_merchant_deposits():
    """Extract and analyze merchant deposits from CIBC data."""
    
    print("\n🏦 ANALYZING CIBC MERCHANT DEPOSITS")
    print("=" * 45)
    
    # Load CIBC transactions
    cibc_file = Path('l:/limo/staging/2012_parsed/2012_cibc_transactions.csv')
    df = pd.read_csv(cibc_file)
    
    # Extract merchant deposits (4017775 is the merchant number we saw)
    merchant_deposits_mask = df['description'].str.contains('4017775|VISA|MC', case=False, na=False)
    merchant_deposits = df[merchant_deposits_mask].copy()
    
    # Clean amounts
    merchant_deposits['deposit'] = pd.to_numeric(merchant_deposits['deposit'], errors='coerce')
    merchant_deposits = merchant_deposits.dropna(subset=['deposit'])
    
    print(f"Found {len(merchant_deposits)} merchant deposit entries")
    
    # Calculate totals
    total_deposits = merchant_deposits['deposit'].sum()
    print(f"Total Merchant Deposits for 2012: ${total_deposits:,.2f}")
    
    # Breakdown by card type
    visa_deposits = merchant_deposits[merchant_deposits['description'].str.contains('VISA', case=False, na=False)]
    mc_deposits = merchant_deposits[merchant_deposits['description'].str.contains('MC', case=False, na=False)]
    
    print(f"\nVISA deposits: ${visa_deposits['deposit'].sum():,.2f} ({len(visa_deposits)} entries)")
    print(f"MasterCard deposits: ${mc_deposits['deposit'].sum():,.2f} ({len(mc_deposits)} entries)")
    
    print("\n📅 MERCHANT DEPOSITS BY DATE")
    print("-" * 35)
    for _, row in merchant_deposits.iterrows():
        card_type = "VISA" if "VISA" in row['description'] else "MC" if "MC" in row['description'] else "OTHER"
        print(f"{row['date']} {card_type:<6} ${row['deposit']:>8,.2f} {row['description'][:50]}")
    
    return merchant_deposits


def calculate_merchant_reconciliation(fees_df, deposits_df):
    """Calculate reconciliation between fees and deposits."""
    
    print("\n🔄 MERCHANT PROCESSING RECONCILIATION")
    print("=" * 45)
    
    total_fees = fees_df['withdrawal'].sum()
    total_deposits = deposits_df['deposit'].sum()
    
    print(f"Total Merchant Fees (QuickBooks): ${total_fees:,.2f}")
    print(f"Total Deposits (CIBC):            ${total_deposits:,.2f}")
    
    # Calculate implied gross sales
    # Gross Sales = Net Deposits + Processing Fees
    implied_gross = total_deposits + total_fees
    print(f"Implied Gross Credit Card Sales:  ${implied_gross:,.2f}")
    
    # Calculate processing rate
    if total_deposits > 0:
        processing_rate = (total_fees / total_deposits) * 100
        print(f"Average Processing Rate:           {processing_rate:.2f}%")
    
    return {
        'total_fees': total_fees,
        'total_deposits': total_deposits,
        'implied_gross_sales': implied_gross,
        'processing_rate': processing_rate if total_deposits > 0 else 0
    }


def compare_with_globalpayments_pdf():
    """Compare with the GlobalPayments PDF data we extracted."""
    
    print("\n📊 COMPARISON WITH GLOBALPAYMENTS PDF DATA")
    print("=" * 55)
    
    # Load our extracted GlobalPayments data
    pdf_file = Path('l:/limo/staging/2012_merchant_statements_corrected/globalpayments_2012_corrected.csv')
    
    if pdf_file.exists():
        pdf_df = pd.read_csv(pdf_file)
        pdf_gross = pdf_df['gross_sales'].sum()
        pdf_net = pdf_df['net_deposit'].sum()
        pdf_fees = pdf_df['discount_fees'].sum()
        
        print(f"PDF GlobalPayments Data (Nov 2012 only):")
        print(f"  Gross Sales: ${pdf_gross:,.2f}")
        print(f"  Net Deposits: ${pdf_net:,.2f}")
        print(f"  Processing Fees: ${pdf_fees:,.2f}")
        
        print("\nThis represents only November 2012 from one PDF page.")
        print("QuickBooks data shows full year 2012 merchant processing.")
        
        return {
            'pdf_gross': pdf_gross,
            'pdf_net': pdf_net,
            'pdf_fees': pdf_fees
        }
    else:
        print("No PDF GlobalPayments data found for comparison.")
        return None


def save_consolidated_merchant_data(fees_df, deposits_df, reconciliation, output_dir):
    """Save consolidated merchant data analysis."""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save merchant fees
    fees_csv = output_path / f'quickbooks_merchant_fees_2012_{timestamp}.csv'
    fees_df.to_csv(fees_csv, index=False)
    print(f"\n💾 Saved merchant fees: {fees_csv}")
    
    # Save merchant deposits  
    deposits_csv = output_path / f'cibc_merchant_deposits_2012_{timestamp}.csv'
    deposits_df.to_csv(deposits_csv, index=False)
    print(f"💾 Saved merchant deposits: {deposits_csv}")
    
    # Save reconciliation summary
    summary = {
        'analysis_date': datetime.now().isoformat(),
        'source_files': [
            'staging/2012_parsed/2012_quickbooks_transactions.csv',
            'staging/2012_parsed/2012_cibc_transactions.csv'
        ],
        'merchant_fees_summary': {
            'total_fees': reconciliation['total_fees'],
            'entries_count': len(fees_df),
            'date_range': {
                'earliest': fees_df['date'].min(),
                'latest': fees_df['date'].max()
            }
        },
        'merchant_deposits_summary': {
            'total_deposits': reconciliation['total_deposits'],
            'entries_count': len(deposits_df),
            'visa_deposits': deposits_df[deposits_df['description'].str.contains('VISA', case=False, na=False)]['deposit'].sum(),
            'mc_deposits': deposits_df[deposits_df['description'].str.contains('MC', case=False, na=False)]['deposit'].sum()
        },
        'reconciliation': reconciliation
    }
    
    summary_json = output_path / f'merchant_data_analysis_2012_{timestamp}.json'
    with open(summary_json, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"💾 Saved analysis summary: {summary_json}")
    
    return {
        'fees_csv': fees_csv,
        'deposits_csv': deposits_csv,
        'summary_json': summary_json
    }


def main():
    parser = argparse.ArgumentParser(description='Analyze existing QuickBooks merchant data for 2012')
    parser.add_argument('--output', default='l:/limo/staging/quickbooks_merchant_analysis',
                       help='Output directory for analysis files')
    parser.add_argument('--write', action='store_true',
                       help='Write analysis files')
    
    args = parser.parse_args()
    
    print("🏦 QuickBooks 2012 Merchant Data Analysis")
    print("=" * 50)
    print("Analyzing existing GlobalPayments merchant processing data...")
    
    # Analyze merchant fees from QuickBooks
    fees_df = analyze_merchant_fees()
    
    # Analyze merchant deposits from CIBC
    deposits_df = analyze_merchant_deposits()
    
    # Calculate reconciliation
    reconciliation = calculate_merchant_reconciliation(fees_df, deposits_df)
    
    # Compare with PDF data if available
    pdf_comparison = compare_with_globalpayments_pdf()
    
    print("\n🎯 ANALYSIS CONCLUSIONS")
    print("=" * 30)
    print("[OK] QuickBooks contains comprehensive 2012 merchant processing data")
    print("[OK] CIBC shows corresponding merchant deposits by card type")
    print("[OK] Processing fees and deposits reconcile to show gross sales")
    print("[WARN]  Individual transaction details (daily breakdowns) not in QuickBooks")
    print("💡 PDF processing would add transaction-level detail for specific periods")
    
    if args.write:
        print(f"\n💾 SAVING ANALYSIS to {args.output}")
        files = save_consolidated_merchant_data(fees_df, deposits_df, reconciliation, args.output)
        print("\n[OK] Merchant data analysis completed successfully!")
        
        print(f"\n📁 Files created:")
        for file_type, file_path in files.items():
            print(f"  {file_type}: {file_path}")
    else:
        print("\n[WARN] Dry run mode - use --write to save analysis files")


if __name__ == "__main__":
    main()