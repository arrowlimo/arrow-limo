#!/usr/bin/env python3
"""
Analyze NSF (Non-Sufficient Funds) Costs and Banking Fees
Extract bounced payment fees, overdraft charges, and NSF penalties from banking records
"""

import os
import re
import csv
import json
import extract_msg
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import DictCursor

def connect_to_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', '')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def analyze_cibc_banking_for_nsf():
    """Analyze CIBC banking files for NSF charges and banking fees."""
    
    print("=== Analyzing CIBC Banking Records for NSF and Fees ===")
    
    cibc_path = Path("l:/limo/CIBC UPLOADS")
    if not cibc_path.exists():
        print("CIBC uploads folder not found")
        return []
    
    nsf_records = []
    
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
                    content = f.read()
                    
                    # NSF and banking fee patterns
                    nsf_patterns = [
                        r'NSF[:\s]*\$?([\d,]+\.?\d*)',
                        r'Non[\s-]?Sufficient[\s-]?Funds[:\s]*\$?([\d,]+\.?\d*)',
                        r'Insufficient[\s-]?Funds[:\s]*\$?([\d,]+\.?\d*)',
                        r'Bounced[\s-]?Payment[:\s]*\$?([\d,]+\.?\d*)',
                        r'Returned[\s-]?Payment[:\s]*\$?([\d,]+\.?\d*)',
                        r'Overdraft[:\s]*\$?([\d,]+\.?\d*)',
                        r'Service[\s-]?Charge[:\s]*\$?([\d,]+\.?\d*)',
                        r'Banking[\s-]?Fee[:\s]*\$?([\d,]+\.?\d*)',
                        r'Monthly[\s-]?Fee[:\s]*\$?([\d,]+\.?\d*)',
                        r'Transaction[\s-]?Fee[:\s]*\$?([\d,]+\.?\d*)'
                    ]
                    
                    # Look for fee descriptions with amounts
                    fee_descriptions = [
                        'NSF', 'INSUFFICIENT FUNDS', 'NON-SUFFICIENT FUNDS',
                        'BOUNCED PAYMENT', 'RETURNED PAYMENT', 'OVERDRAFT',
                        'SERVICE CHARGE', 'BANKING FEE', 'MONTHLY FEE',
                        'TRANSACTION FEE', 'MAINTENANCE FEE', 'ACCOUNT FEE'
                    ]
                    
                    lines = content.split('\n')
                    
                    for i, line in enumerate(lines):
                        line_upper = line.upper()
                        
                        # Check for fee descriptions
                        for desc in fee_descriptions:
                            if desc in line_upper:
                                # Look for amounts in this line
                                amount_matches = re.findall(r'\$?([\d,]+\.?\d{2})', line)
                                
                                for amount_str in amount_matches:
                                    try:
                                        amount = float(amount_str.replace(',', ''))
                                        if 5 <= amount <= 1000:  # Reasonable fee range
                                            
                                            # Try to extract date from line
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
                                            
                                            nsf_records.append({
                                                'file_name': csv_file.name,
                                                'account_folder': folder,
                                                'transaction_date': transaction_date,
                                                'fee_type': desc,
                                                'amount': amount,
                                                'description': line.strip()[:200],
                                                'source': 'Bank Statement CSV'
                                            })
                                            
                                    except ValueError:
                                        continue
                        
                        # Also check with regex patterns
                        for pattern in nsf_patterns:
                            matches = re.findall(pattern, line, re.IGNORECASE)
                            for amount_str in matches:
                                try:
                                    amount = float(amount_str.replace(',', ''))
                                    if 5 <= amount <= 1000:
                                        nsf_records.append({
                                            'file_name': csv_file.name,
                                            'account_folder': folder,
                                            'transaction_date': None,
                                            'fee_type': 'Pattern Match',
                                            'amount': amount,
                                            'description': line.strip()[:200],
                                            'source': 'Regex Pattern'
                                        })
                                except ValueError:
                                    continue
                        
            except Exception as e:
                print(f"    Error processing {csv_file}: {e}")
                continue
    
    print(f"Found {len(nsf_records)} potential NSF/fee records")
    return nsf_records

def analyze_emails_for_nsf_notifications():
    """Check emails for NSF notifications and bounced payment alerts."""
    
    print("\n=== Analyzing Emails for NSF Notifications ===")
    
    # Check outlook backup for banking notifications
    outlook_path = Path("l:/limo/outlook backup")
    nsf_emails = []
    
    if outlook_path.exists():
        # Look for banking-related MSG files
        banking_patterns = [
            "*nsf*", "*insufficient*", "*bounced*", "*returned*payment*",
            "*overdraft*", "*cibc*", "*bank*fee*", "*service*charge*"
        ]
        
        for pattern in banking_patterns:
            for msg_file in outlook_path.rglob(f"**/{pattern}.msg"):
                try:
                    msg = extract_msg.Message(str(msg_file))
                    
                    subject = getattr(msg, 'subject', '')
                    body = getattr(msg, 'body', '')
                    date_sent = getattr(msg, 'date', '')
                    sender = getattr(msg, 'sender', '')
                    
                    if not body:
                        continue
                    
                    # Look for NSF-related content
                    nsf_keywords = [
                        'insufficient funds', 'non-sufficient funds', 'nsf',
                        'bounced payment', 'returned payment', 'overdraft',
                        'service charge', 'banking fee', 'account fee'
                    ]
                    
                    content_lower = (subject + ' ' + body).lower()
                    
                    for keyword in nsf_keywords:
                        if keyword in content_lower:
                            
                            # Extract amounts from email
                            amount_patterns = [
                                r'\$[\d,]+\.?\d*',
                                r'amount[:\s]*\$?([\d,]+\.?\d*)',
                                r'fee[:\s]*\$?([\d,]+\.?\d*)',
                                r'charge[:\s]*\$?([\d,]+\.?\d*)'
                            ]
                            
                            amounts_found = []
                            for pattern in amount_patterns:
                                matches = re.findall(pattern, body, re.IGNORECASE)
                                for match in matches:
                                    try:
                                        clean_amount = re.sub(r'[\$,]', '', str(match))
                                        amount = float(clean_amount)
                                        if 5 <= amount <= 1000:
                                            amounts_found.append(amount)
                                    except:
                                        continue
                            
                            nsf_emails.append({
                                'file_name': msg_file.name,
                                'subject': subject,
                                'date_sent': str(date_sent),
                                'sender': sender,
                                'keyword_matched': keyword,
                                'amounts_found': amounts_found,
                                'source': 'Email Analysis'
                            })
                            break  # Only count each email once
                            
                except Exception as e:
                    print(f"Error processing {msg_file}: {e}")
                    continue
    
    print(f"Found {len(nsf_emails)} NSF-related emails")
    return nsf_emails

def check_receipts_for_nsf_fees():
    """Check receipts folder for NSF fee records."""
    
    print("\n=== Checking Receipts for NSF Fee Records ===")
    
    receipts_path = Path("l:/limo/receipts")
    nsf_receipts = []
    
    if receipts_path.exists():
        # Look for CSV files in receipts
        for csv_file in receipts_path.rglob("*.csv"):
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Look for NSF-related entries
                    lines = content.split('\n')
                    for line in lines:
                        line_upper = line.upper()
                        
                        if any(keyword in line_upper for keyword in [
                            'NSF', 'INSUFFICIENT', 'BOUNCED', 'OVERDRAFT', 
                            'BANK FEE', 'SERVICE CHARGE'
                        ]):
                            # Extract amounts
                            amounts = re.findall(r'\$?([\d,]+\.?\d{2})', line)
                            for amount_str in amounts:
                                try:
                                    amount = float(amount_str.replace(',', ''))
                                    if 5 <= amount <= 1000:
                                        nsf_receipts.append({
                                            'file_name': csv_file.name,
                                            'amount': amount,
                                            'description': line.strip(),
                                            'source': 'Receipts CSV'
                                        })
                                except ValueError:
                                    continue
                        
            except Exception as e:
                continue
    
    print(f"Found {len(nsf_receipts)} NSF-related receipt entries")
    return nsf_receipts

def generate_nsf_cost_report():
    """Generate comprehensive NSF cost analysis report."""
    
    print("\n=== Generating NSF Cost Analysis Report ===")
    
    # Gather all NSF data
    banking_nsf = analyze_cibc_banking_for_nsf()
    email_nsf = analyze_emails_for_nsf_notifications()
    receipt_nsf = check_receipts_for_nsf_fees()
    
    # Combine all records
    all_nsf_records = []
    
    # Add banking records
    for record in banking_nsf:
        all_nsf_records.append({
            'date': record.get('transaction_date', 'Unknown'),
            'type': 'Banking Fee',
            'fee_category': record['fee_type'],
            'amount': record['amount'],
            'description': record['description'],
            'source': record['source'],
            'account': record.get('account_folder', 'Unknown')
        })
    
    # Add email notifications (may indicate fees not captured in banking)
    for record in email_nsf:
        for amount in record['amounts_found']:
            all_nsf_records.append({
                'date': record['date_sent'][:10] if record['date_sent'] else 'Unknown',
                'type': 'Email Notification',
                'fee_category': record['keyword_matched'],
                'amount': amount,
                'description': record['subject'],
                'source': 'Email Analysis',
                'account': 'Email Reference'
            })
    
    # Add receipt records
    for record in receipt_nsf:
        all_nsf_records.append({
            'date': 'Unknown',
            'type': 'Receipt Record',
            'fee_category': 'Banking Fee',
            'amount': record['amount'],
            'description': record['description'],
            'source': 'Receipts',
            'account': 'Receipt Entry'
        })
    
    # Sort by amount (highest first)
    all_nsf_records.sort(key=lambda x: x['amount'], reverse=True)
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"l:/limo/reports/nsf_cost_analysis_{timestamp}.csv"
    
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date', 'Type', 'Fee Category', 'Amount', 'Description', 
            'Source', 'Account/Reference'
        ])
        
        total_nsf_costs = 0
        fee_categories = {}
        
        for record in all_nsf_records:
            writer.writerow([
                record['date'],
                record['type'],
                record['fee_category'],
                f"${record['amount']:,.2f}",
                record['description'][:100],
                record['source'],
                record['account']
            ])
            
            total_nsf_costs += record['amount']
            
            # Track by category
            category = record['fee_category']
            if category not in fee_categories:
                fee_categories[category] = {'count': 0, 'total': 0}
            fee_categories[category]['count'] += 1
            fee_categories[category]['total'] += record['amount']
        
        # Add summary section
        writer.writerow(['', '', '', '', '', '', ''])
        writer.writerow(['SUMMARY', '', '', '', '', '', ''])
        writer.writerow(['Total NSF/Banking Costs', '', '', f"${total_nsf_costs:.2f}", '', '', ''])
        writer.writerow(['Total Records Found', '', '', str(len(all_nsf_records)), '', '', ''])
        writer.writerow(['', '', '', '', '', '', ''])
        
        # Category breakdown
        writer.writerow(['BREAKDOWN BY CATEGORY', '', '', '', '', '', ''])
        for category, data in fee_categories.items():
            writer.writerow([
                category, '', '', f"${data['total']:.2f}", 
                f"{data['count']} occurrences", '', ''
            ])
    
    # Generate summary statistics
    summary = {
        'total_nsf_costs': total_nsf_costs,
        'total_records': len(all_nsf_records),
        'banking_records': len(banking_nsf),
        'email_notifications': len(email_nsf),
        'receipt_entries': len(receipt_nsf),
        'average_fee': total_nsf_costs / len(all_nsf_records) if all_nsf_records else 0,
        'fee_categories': fee_categories,
        'report_path': report_path
    }
    
    print(f"\nNSF Cost Analysis Complete:")
    print(f"Total NSF/Banking Costs: ${total_nsf_costs:,.2f}")
    print(f"Total Records Found: {len(all_nsf_records)}")
    print(f"Average Fee Amount: ${summary['average_fee']:,.2f}")
    print(f"Report Generated: {report_path}")
    
    if fee_categories:
        print(f"\nTop Fee Categories:")
        sorted_categories = sorted(fee_categories.items(), key=lambda x: x[1]['total'], reverse=True)
        for category, data in sorted_categories[:5]:
            print(f"  {category}: ${data['total']:,.2f} ({data['count']} occurrences)")
    
    return all_nsf_records, summary

def main():
    """Main execution function."""
    
    print("=" * 80)
    print("NSF (NON-SUFFICIENT FUNDS) COST ANALYSIS")
    print("=" * 80)
    
    nsf_records, summary = generate_nsf_cost_report()
    
    print("\n" + "=" * 50)
    print("NSF ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"Total NSF/Banking Fees: ${summary['total_nsf_costs']:,.2f}")
    print(f"Records Analyzed: {summary['total_records']}")
    print(f"Detailed Report: {summary['report_path']}")
    
    return nsf_records, summary

if __name__ == "__main__":
    records, summary = main()