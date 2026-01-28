#!/usr/bin/env python3
"""
Corrected NSF Cost Analysis - Filter out false positives
Identify actual NSF charges, not regular transactions that happen to contain amounts
"""

import os
import re
import csv
from pathlib import Path
from datetime import datetime

def analyze_actual_nsf_charges():
    """Analyze CIBC banking files for ACTUAL NSF charges, not regular transactions."""
    
    print("=== Analyzing for ACTUAL NSF Charges (Corrected Analysis) ===")
    
    cibc_path = Path("l:/limo/CIBC UPLOADS")
    if not cibc_path.exists():
        print("CIBC uploads folder not found")
        return []
    
    actual_nsf_records = []
    
    # Account folders to check
    account_folders = [
        "0228362 (CIBC checking account)",
        "3648117 (CIBC Business Deposit account, alias for 0534)",
        "8314462 (CIBC vehicle loans)"
    ]
    
    for folder in account_folders:
        folder_path = cibc_path / folder
        if not folder_path.exists():
            continue
            
        print(f"  Checking {folder}...")
        
        # Look for CSV files (bank statements)
        for csv_file in folder_path.rglob("*.csv"):
            try:
                print(f"    Analyzing {csv_file.name}...")
                
                with open(csv_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                    for line_num, line in enumerate(lines):
                        line_upper = line.upper()
                        
                        # Look for ACTUAL NSF fee descriptions (not just amounts)
                        actual_nsf_indicators = [
                            'NSF FEE', 'NSF CHARGE', 'INSUFFICIENT FUND FEE',
                            'NON-SUFFICIENT FUND FEE', 'RETURNED ITEM FEE',
                            'BOUNCED CHEQUE FEE', 'OVERDRAFT FEE',
                            'SERVICE CHARGE - NSF', 'RETURNED PAYMENT FEE',
                            'DISHONORED ITEM', 'INSUFFICIENT FUNDS CHARGE'
                        ]
                        
                        # Also look for banking fees (but exclude e-transfers)
                        banking_fee_indicators = [
                            'MONTHLY SERVICE CHARGE', 'ACCOUNT MAINTENANCE FEE',
                            'TRANSACTION FEE', 'INTERAC FEE', 'WIRE FEE'
                        ]
                        
                        # Skip if this is clearly an e-transfer or regular transaction
                        exclude_patterns = [
                            'E-TRANSFER', 'ETRANSFER', 'DEPOSIT', 'WITHDRAWAL',
                            'PAYMENT TO', 'TRANSFER TO', 'INTERNET BANKING',
                            'CHEQUE #', 'DEBIT CARD', 'CREDIT CARD'
                        ]
                        
                        # Skip excluded patterns
                        if any(pattern in line_upper for pattern in exclude_patterns):
                            continue
                        
                        # Check for actual NSF indicators
                        found_nsf_indicator = None
                        for indicator in actual_nsf_indicators + banking_fee_indicators:
                            if indicator in line_upper:
                                found_nsf_indicator = indicator
                                break
                        
                        if found_nsf_indicator:
                            # Extract amounts from this line
                            amount_matches = re.findall(r'[-]?\$?([\d,]+\.?\d{0,2})', line)
                            
                            for amount_str in amount_matches:
                                try:
                                    amount = float(amount_str.replace(',', ''))
                                    
                                    # NSF fees are typically $5-$50, banking fees $5-$30
                                    if 2 <= amount <= 100:
                                        
                                        # Try to extract date
                                        date_patterns = [
                                            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                                            r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                                            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2})'
                                        ]
                                        
                                        transaction_date = None
                                        for date_pattern in date_patterns:
                                            date_match = re.search(date_pattern, line)
                                            if date_match:
                                                transaction_date = date_match.group(1)
                                                break
                                        
                                        actual_nsf_records.append({
                                            'file_name': csv_file.name,
                                            'account_folder': folder,
                                            'transaction_date': transaction_date,
                                            'fee_type': found_nsf_indicator,
                                            'amount': amount,
                                            'description': line.strip(),
                                            'line_number': line_num + 1
                                        })
                                        
                                except ValueError:
                                    continue
                        
            except Exception as e:
                print(f"    Error processing {csv_file}: {e}")
                continue
    
    print(f"Found {len(actual_nsf_records)} ACTUAL NSF/banking fee records")
    return actual_nsf_records

def sample_bank_statements_for_patterns():
    """Sample a few lines from bank statements to identify actual fee patterns."""
    
    print("\n=== Sampling Bank Statements for Fee Patterns ===")
    
    cibc_path = Path("l:/limo/CIBC UPLOADS/0228362 (CIBC checking account)")
    if not cibc_path.exists():
        print("CIBC checking account folder not found")
        return
    
    # Look at a recent statement to understand the format
    recent_files = list(cibc_path.glob("*.csv"))[-3:]  # Last 3 files
    
    fee_patterns_found = []
    
    for csv_file in recent_files:
        print(f"  Sampling {csv_file.name}...")
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # Look for lines with small amounts that might be fees
                for line in lines[:50]:  # Sample first 50 lines
                    # Look for small amounts (typical fee range)
                    small_amounts = re.findall(r'[-]?\$?([\d]+\.?\d{0,2})', line)
                    for amount_str in small_amounts:
                        try:
                            amount = float(amount_str)
                            if 5 <= amount <= 50:  # Typical fee range
                                fee_patterns_found.append({
                                    'file': csv_file.name,
                                    'amount': amount,
                                    'line': line.strip()
                                })
                        except ValueError:
                            continue
                            
        except Exception as e:
            print(f"    Error sampling {csv_file}: {e}")
            continue
    
    print(f"Found {len(fee_patterns_found)} potential fee patterns")
    
    # Show some examples
    if fee_patterns_found:
        print("\nSample potential fee lines:")
        for pattern in fee_patterns_found[:10]:
            print(f"  ${pattern['amount']:,.2f}: {pattern['line'][:100]}")
    
    return fee_patterns_found

def calculate_realistic_nsf_estimate():
    """Calculate a realistic estimate of NSF costs based on business size."""
    
    print("\n=== Calculating Realistic NSF Estimate ===")
    
    # For a business with:
    # - $300K in outstanding loans
    # - Multiple bank accounts  
    # - Regular payment obligations
    # - 8 years of operations
    
    realistic_estimates = {
        'typical_nsf_fee': 45.00,  # CIBC NSF fee is around $45
        'typical_monthly_service_charge': 16.95,  # Business account monthly fee
        'estimated_nsf_incidents_per_year': 2,  # Conservative estimate
        'years_of_operation': 8,
        'number_of_accounts': 3
    }
    
    # Calculate estimated costs
    annual_nsf = realistic_estimates['estimated_nsf_incidents_per_year'] * realistic_estimates['typical_nsf_fee']
    total_nsf_8_years = annual_nsf * realistic_estimates['years_of_operation']
    
    annual_service_charges = realistic_estimates['typical_monthly_service_charge'] * 12 * realistic_estimates['number_of_accounts']
    total_service_charges_8_years = annual_service_charges * realistic_estimates['years_of_operation']
    
    total_estimated_banking_costs = total_nsf_8_years + total_service_charges_8_years
    
    print(f"Realistic NSF Cost Estimate:")
    print(f"  Typical NSF fee: ${realistic_estimates['typical_nsf_fee']:.2f}")
    print(f"  Estimated NSF incidents per year: {realistic_estimates['estimated_nsf_incidents_per_year']}")
    print(f"  Annual NSF costs: ${annual_nsf:.2f}")
    print(f"  8-year NSF total: ${total_nsf_8_years:.2f}")
    print(f"")
    print(f"  Monthly service charge per account: ${realistic_estimates['typical_monthly_service_charge']:.2f}")
    print(f"  Annual service charges (3 accounts): ${annual_service_charges:.2f}")
    print(f"  8-year service charges total: ${total_service_charges_8_years:.2f}")
    print(f"")
    print(f"  TOTAL ESTIMATED BANKING COSTS (8 years): ${total_estimated_banking_costs:.2f}")
    
    return {
        'annual_nsf_costs': annual_nsf,
        'total_nsf_costs': total_nsf_8_years,
        'annual_service_charges': annual_service_charges,
        'total_service_charges': total_service_charges_8_years,
        'total_banking_costs': total_estimated_banking_costs
    }

def generate_corrected_nsf_report():
    """Generate corrected NSF analysis report."""
    
    print("\n=== Generating Corrected NSF Report ===")
    
    # Get actual NSF records
    actual_nsf = analyze_actual_nsf_charges()
    
    # Sample for patterns
    sample_patterns = sample_bank_statements_for_patterns()
    
    # Calculate realistic estimate
    realistic_estimate = calculate_realistic_nsf_estimate()
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"l:/limo/reports/corrected_nsf_analysis_{timestamp}.csv"
    
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow(['CORRECTED NSF COST ANALYSIS REPORT'])
        writer.writerow([f'Generated: {datetime.now()}'])
        writer.writerow([''])
        
        # Actual NSF records found
        writer.writerow(['ACTUAL NSF RECORDS IDENTIFIED'])
        writer.writerow(['Date', 'Fee Type', 'Amount', 'Description', 'Source File'])
        
        total_actual_nsf = 0
        for record in actual_nsf:
            writer.writerow([
                record.get('transaction_date', 'Unknown'),
                record['fee_type'],
                f"${record['amount']:.2f}",
                record['description'][:100],
                record['file_name']
            ])
            total_actual_nsf += record['amount']
        
        writer.writerow([''])
        writer.writerow(['ACTUAL NSF TOTAL', '', f"${total_actual_nsf:.2f}", '', ''])
        writer.writerow([''])
        
        # Realistic estimates
        writer.writerow(['REALISTIC COST ESTIMATES'])
        writer.writerow(['Category', 'Annual Cost', '8-Year Total', 'Notes'])
        writer.writerow([
            'NSF Fees',
            f"${realistic_estimate['annual_nsf_costs']:.2f}",
            f"${realistic_estimate['total_nsf_costs']:.2f}",
            'Based on 2 incidents/year at $45/fee'
        ])
        writer.writerow([
            'Service Charges',
            f"${realistic_estimate['annual_service_charges']:.2f}",
            f"${realistic_estimate['total_service_charges']:.2f}",
            '3 accounts at $16.95/month each'
        ])
        writer.writerow([
            'TOTAL BANKING COSTS',
            f"${realistic_estimate['annual_nsf_costs'] + realistic_estimate['annual_service_charges']:.2f}",
            f"${realistic_estimate['total_banking_costs']:.2f}",
            'Estimated total for 8-year period'
        ])
        
        writer.writerow([''])
        writer.writerow(['ANALYSIS NOTES'])
        writer.writerow(['Previous Analysis Error', 'Incorrectly identified e-transfers as NSF fees'])
        writer.writerow(['Corrected Method', 'Look for actual fee descriptions, exclude regular transactions'])
        writer.writerow(['Actual NSF Records', f'{len(actual_nsf)} confirmed records found'])
        writer.writerow(['Data Quality', 'Banking statements may not contain all fee details'])
    
    summary = {
        'actual_nsf_found': len(actual_nsf),
        'actual_nsf_total': total_actual_nsf,
        'realistic_estimate': realistic_estimate,
        'report_path': report_path
    }
    
    print(f"\nCorrected NSF Analysis Complete:")
    print(f"Actual NSF records found: {len(actual_nsf)}")
    print(f"Actual NSF total: ${total_actual_nsf:.2f}")
    print(f"Realistic 8-year estimate: ${realistic_estimate['total_banking_costs']:.2f}")
    print(f"Report: {report_path}")
    
    return summary

def main():
    """Main execution function."""
    
    print("=" * 80)
    print("CORRECTED NSF COST ANALYSIS")
    print("Filtering out false positives from previous analysis")
    print("=" * 80)
    
    summary = generate_corrected_nsf_report()
    
    print("\n" + "=" * 50)
    print("CORRECTED ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"Previous analysis error: Identified e-transfers as NSF fees")
    print(f"Corrected analysis: {summary['actual_nsf_found']} actual NSF records")
    print(f"Realistic estimate: ${summary['realistic_estimate']['total_banking_costs']:,.2f} over 8 years")
    
    return summary

if __name__ == "__main__":
    summary = main()