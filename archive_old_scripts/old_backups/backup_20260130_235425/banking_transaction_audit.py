#!/usr/bin/env python3
"""
Banking Transaction Audit - Link NSF and banking costs to actual banking files
Create detailed audit trail for every banking transaction related to vehicles
"""

import os
import csv
import glob
from datetime import datetime
from pathlib import Path
from decimal import Decimal

def analyze_banking_files_comprehensive():
    """Analyze all CIBC banking files for comprehensive transaction audit."""
    
    print("=== COMPREHENSIVE BANKING TRANSACTION AUDIT ===")
    
    banking_dirs = [
        "l:/limo/CIBC UPLOADS/0228362 (CIBC checking account)",
        "l:/limo/CIBC UPLOADS/3648117 (CIBC Business Deposit account, alias for 0534",
        "l:/limo/CIBC UPLOADS/8314462 (CIBC vehicle loans)"
    ]
    
    all_transactions = []
    vehicle_related_keywords = [
        'navigator', 'f550', 'f-550', 'ford', 'transit', 'camry', 'e350', 'e450',
        'toyota', 'mercedes', 'chevrolet', 'gmc', 'escalade', 'suburban',
        'heffner', 'pfeiffer', 'auto', 'lease', 'loan', 'finance',
        'vehicle', 'car', 'truck', 'van', 'limousine', 'limo'
    ]
    
    fee_keywords = [
        'nsf', 'overdraft', 'fee', 'charge', 'service charge', 'monthly fee',
        'transaction fee', 'insufficient funds', 'overdraft fee', 'banking fee',
        'account fee', 'maintenance fee'
    ]
    
    for banking_dir in banking_dirs:
        if not os.path.exists(banking_dir):
            continue
            
        print(f"Processing: {banking_dir}")
        csv_files = glob.glob(os.path.join(banking_dir, "*.csv"))
        
        for csv_file in csv_files:
            account_type = 'Checking'
            if '3648117' in csv_file:
                account_type = 'Business Deposit'
            elif '8314462' in csv_file:
                account_type = 'Vehicle Loans'
                
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    # Try to detect the format and headers
                    sample = f.read(1000)
                    f.seek(0)
                    
                    # Most CIBC files have headers like: Date, Description, Debit, Credit, Balance
                    reader = csv.reader(f)
                    headers = next(reader, None)
                    
                    if not headers:
                        continue
                    
                    for row_num, row in enumerate(reader, 2):
                        if len(row) < 3:
                            continue
                            
                        try:
                            # Try to parse date from first column
                            date_str = row[0].strip() if row[0] else ''
                            description = row[1].strip() if len(row) > 1 and row[1] else ''
                            
                            if not date_str or not description:
                                continue
                            
                            # Parse amounts - usually debit/credit in separate columns
                            debit_amount = 0.0
                            credit_amount = 0.0
                            
                            if len(row) > 2:
                                debit_str = row[2].strip().replace('$', '').replace(',', '') if row[2] else '0'
                                try:
                                    if debit_str and debit_str != '':
                                        debit_amount = float(debit_str)
                                except:
                                    pass
                            
                            if len(row) > 3:
                                credit_str = row[3].strip().replace('$', '').replace(',', '') if row[3] else '0'
                                try:
                                    if credit_str and credit_str != '':
                                        credit_amount = float(credit_str)
                                except:
                                    pass
                            
                            # Determine transaction type and categorization
                            desc_lower = description.lower()
                            
                            is_vehicle_related = any(keyword in desc_lower for keyword in vehicle_related_keywords)
                            is_fee = any(keyword in desc_lower for keyword in fee_keywords)
                            is_nsf = 'nsf' in desc_lower or 'insufficient funds' in desc_lower or 'overdraft' in desc_lower
                            
                            transaction_type = 'General Banking'
                            tax_category = 'Banking Transaction'
                            audit_category = 'Banking Transaction'
                            
                            if is_nsf or is_fee:
                                transaction_type = 'Banking Fee/NSF'
                                tax_category = 'Business Expense (Deductible)'
                                audit_category = 'NSF/Banking Fees'
                            elif is_vehicle_related:
                                transaction_type = 'Vehicle Related Payment'
                                tax_category = 'Vehicle Expense'
                                audit_category = 'Vehicle Payment'
                            
                            # Create transaction record
                            net_amount = debit_amount - credit_amount
                            if net_amount != 0:
                                all_transactions.append({
                                    'date': date_str,
                                    'account_type': account_type,
                                    'description': description[:200],  # Limit description length
                                    'debit_amount': debit_amount,
                                    'credit_amount': credit_amount,
                                    'net_amount': net_amount,
                                    'transaction_type': transaction_type,
                                    'audit_category': audit_category,
                                    'tax_category': tax_category,
                                    'vehicle_related': is_vehicle_related,
                                    'is_fee': is_fee,
                                    'is_nsf': is_nsf,
                                    'source_file': os.path.basename(csv_file),
                                    'source_path': csv_file
                                })
                        
                        except Exception as e:
                            continue  # Skip problematic rows
                            
            except Exception as e:
                print(f"Error processing {csv_file}: {e}")
                continue
    
    return all_transactions

def create_tax_categorized_report():
    """Create detailed tax-categorized report for all financial transactions."""
    
    print("\n=== CREATING TAX CATEGORIZED REPORT ===")
    
    # Get banking transactions
    banking_transactions = analyze_banking_files_comprehensive()
    
    # Categorize for tax purposes
    tax_categories = {
        'Vehicle Loans Principal': [],
        'Vehicle Loan Interest': [],
        'Banking Fees (Deductible)': [],
        'NSF Fees (Deductible)': [],
        'Insurance Premiums (Deductible)': [],
        'Insurance Recovery (Taxable Income)': [],
        'Vehicle Expenses': [],
        'General Banking': []
    }
    
    # Process banking transactions
    for transaction in banking_transactions:
        if transaction['is_nsf']:
            tax_categories['NSF Fees (Deductible)'].append(transaction)
        elif transaction['is_fee']:
            tax_categories['Banking Fees (Deductible)'].append(transaction)
        elif transaction['vehicle_related']:
            tax_categories['Vehicle Expenses'].append(transaction)
        else:
            tax_categories['General Banking'].append(transaction)
    
    # Generate tax report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tax_report_path = f"l:/limo/reports/tax_categorized_report_{timestamp}.csv"
    
    with open(tax_report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Tax Category', 'Date', 'Description', 'Debit Amount', 'Credit Amount',
            'Net Amount', 'Account Type', 'Transaction Type', 'Source File', 'Tax Notes'
        ])
        
        category_totals = {}
        
        for category, transactions in tax_categories.items():
            if not transactions:
                continue
                
            category_total = 0
            
            for transaction in transactions:
                tax_notes = ''
                if 'Deductible' in category:
                    tax_notes = 'Business expense - fully deductible'
                elif 'Income' in category:
                    tax_notes = 'Taxable business income'
                elif 'Principal' in category:
                    tax_notes = 'Loan principal - not deductible'
                elif 'Interest' in category:
                    tax_notes = 'Interest expense - deductible'
                
                writer.writerow([
                    category,
                    transaction['date'],
                    transaction['description'],
                    f"${transaction['debit_amount']:,.2f}",
                    f"${transaction['credit_amount']:,.2f}",
                    f"${transaction['net_amount']:,.2f}",
                    transaction['account_type'],
                    transaction['transaction_type'],
                    transaction['source_file'],
                    tax_notes
                ])
                
                category_total += transaction['net_amount']
            
            category_totals[category] = category_total
        
        # Add summary totals
        writer.writerow([''])
        writer.writerow(['TAX CATEGORY TOTALS'])
        for category, total in category_totals.items():
            writer.writerow([category, '', '', '', '', f"${total:,.2f}", '', '', '', ''])
    
    # Generate banking audit summary
    banking_summary_path = f"l:/limo/reports/banking_audit_summary_{timestamp}.csv"
    
    with open(banking_summary_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Account Type', 'Total Transactions', 'Total Debits', 'Total Credits',
            'NSF/Fee Count', 'NSF/Fee Amount', 'Vehicle Related Count', 'Vehicle Related Amount'
        ])
        
        account_summaries = {}
        
        for transaction in banking_transactions:
            account = transaction['account_type']
            if account not in account_summaries:
                account_summaries[account] = {
                    'count': 0, 'debits': 0, 'credits': 0,
                    'nsf_count': 0, 'nsf_amount': 0,
                    'vehicle_count': 0, 'vehicle_amount': 0
                }
            
            summary = account_summaries[account]
            summary['count'] += 1
            summary['debits'] += transaction['debit_amount']
            summary['credits'] += transaction['credit_amount']
            
            if transaction['is_nsf'] or transaction['is_fee']:
                summary['nsf_count'] += 1
                summary['nsf_amount'] += transaction['debit_amount']
            
            if transaction['vehicle_related']:
                summary['vehicle_count'] += 1
                summary['vehicle_amount'] += abs(transaction['net_amount'])
        
        total_transactions = 0
        total_debits = 0
        total_credits = 0
        total_nsf_amount = 0
        total_vehicle_amount = 0
        
        for account, summary in account_summaries.items():
            writer.writerow([
                account,
                summary['count'],
                f"${summary['debits']:,.2f}",
                f"${summary['credits']:,.2f}",
                summary['nsf_count'],
                f"${summary['nsf_amount']:,.2f}",
                summary['vehicle_count'],
                f"${summary['vehicle_amount']:,.2f}"
            ])
            
            total_transactions += summary['count']
            total_debits += summary['debits']
            total_credits += summary['credits']
            total_nsf_amount += summary['nsf_amount']
            total_vehicle_amount += summary['vehicle_amount']
        
        # Add totals
        writer.writerow([''])
        writer.writerow([
            'TOTALS',
            total_transactions,
            f"${total_debits:,.2f}",
            f"${total_credits:,.2f}",
            '',
            f"${total_nsf_amount:,.2f}",
            '',
            f"${total_vehicle_amount:,.2f}"
        ])
    
    results = {
        'total_transactions': len(banking_transactions),
        'tax_report_path': tax_report_path,
        'banking_summary_path': banking_summary_path,
        'category_totals': category_totals
    }
    
    print(f"Tax categorized report: {tax_report_path}")
    print(f"Banking audit summary: {banking_summary_path}")
    print(f"Total transactions processed: {len(banking_transactions)}")
    
    return results

def main():
    """Main execution function."""
    
    print("=" * 80)
    print("BANKING TRANSACTION AUDIT & TAX CATEGORIZATION")
    print("Linking all banking transactions to tax categories")
    print("=" * 80)
    
    results = create_tax_categorized_report()
    
    if results:
        print("\n" + "=" * 50)
        print("BANKING AUDIT COMPLETE")
        print("=" * 50)
        print(f"Total transactions analyzed: {results['total_transactions']}")
        print(f"Tax report: {results['tax_report_path']}")
        print(f"Banking summary: {results['banking_summary_path']}")
    
    return results

if __name__ == "__main__":
    results = main()