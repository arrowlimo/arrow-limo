#!/usr/bin/env python3
"""
Extract Insurance Claims and Payouts from Email Files
Parse specific insurance emails for claim amounts, settlement figures, and payout details
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

def extract_insurance_claims_from_emails():
    """Extract detailed insurance claim information from outlook backup emails."""
    
    print("=== Extracting Insurance Claims from Email Archives ===")
    
    # Look for insurance-related MSG files
    outlook_backup = Path("l:/limo/outlook backup")
    if not outlook_backup.exists():
        print("Outlook backup folder not found")
        return []
    
    insurance_records = []
    
    # Find all MSG files with insurance keywords
    insurance_patterns = [
        "*insurance*", "*claim*", "*settlement*", "*payout*", 
        "*collision*", "*total*loss*", "*intact*", "*nordic*"
    ]
    
    for pattern in insurance_patterns:
        for msg_file in outlook_backup.rglob(f"**/{pattern}.msg"):
            try:
                msg = extract_msg.Message(str(msg_file))
                
                subject = getattr(msg, 'subject', '')
                body = getattr(msg, 'body', '')
                date_sent = getattr(msg, 'date', '')
                sender = getattr(msg, 'sender', '')
                
                if not body:
                    continue
                
                # Extract claim numbers
                claim_patterns = [
                    r'claim\s*#?\s*(\d+)',
                    r'claim\s*number\s*(\d+)',
                    r'clm\s*#?\s*(\d+)',
                    r'policy\s*#?\s*(\d+)'
                ]
                
                claims_found = []
                for pattern in claim_patterns:
                    matches = re.findall(pattern, body, re.IGNORECASE)
                    claims_found.extend(matches)
                
                # Extract dollar amounts
                amount_patterns = [
                    r'\$[\d,]+\.?\d*',
                    r'amount[:\s]*\$?([\d,]+\.?\d*)',
                    r'settlement[:\s]*\$?([\d,]+\.?\d*)',
                    r'payout[:\s]*\$?([\d,]+\.?\d*)',
                    r'deductible[:\s]*\$?([\d,]+\.?\d*)',
                    r'total\s*loss[:\s]*\$?([\d,]+\.?\d*)'
                ]
                
                amounts_found = []
                for pattern in amount_patterns:
                    matches = re.findall(pattern, body, re.IGNORECASE)
                    for match in matches:
                        try:
                            # Clean up amount
                            clean_amount = re.sub(r'[\$,]', '', str(match))
                            amount = float(clean_amount)
                            if 100 <= amount <= 1000000:  # Reasonable insurance range
                                amounts_found.append(amount)
                        except:
                            continue
                
                # Extract vehicle references
                vehicle_patterns = [
                    r'(\d{4})\s+(Ford|Toyota|Cadillac|Lincoln|Mercedes)',
                    r'\b(E350|E450|F550|Transit|Navigator|Escalade|Camry|K900)\b',
                    r'VIN[:\s]*([A-HJ-NPR-Z0-9]{17})'
                ]
                
                vehicles_found = []
                for pattern in vehicle_patterns:
                    matches = re.findall(pattern, body, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            vehicle_desc = ' '.join([str(m) for m in match if m])
                        else:
                            vehicle_desc = str(match)
                        vehicles_found.append(vehicle_desc)
                
                # Look for claim status
                status_keywords = [
                    'total loss', 'write off', 'settlement', 'closed', 'paid',
                    'approved', 'denied', 'pending', 'under investigation'
                ]
                
                status_found = []
                for keyword in status_keywords:
                    if keyword in body.lower():
                        status_found.append(keyword)
                
                if claims_found or amounts_found or any(keyword in subject.lower() for keyword in ['claim', 'insurance', 'settlement']):
                    insurance_records.append({
                        'file_name': msg_file.name,
                        'file_path': str(msg_file),
                        'subject': subject,
                        'date_sent': str(date_sent),
                        'sender': sender,
                        'claim_numbers': list(set(claims_found)),
                        'amounts': list(set(amounts_found)),
                        'vehicles': list(set(vehicles_found)),
                        'status_keywords': list(set(status_found))
                    })
                    
            except Exception as e:
                print(f"Error processing {msg_file}: {e}")
                continue
    
    print(f"Extracted {len(insurance_records)} insurance-related records")
    return insurance_records

def analyze_specific_claims():
    """Analyze specific high-value claims mentioned in emails."""
    
    print("\n=== Analyzing Specific Insurance Claims ===")
    
    # Based on the file search, we have specific claims to investigate
    known_claims = [
        {
            'claim_number': '1032888901',
            'incident_date': '2018-09-21', 
            'description': 'Arrow Sedan claim',
            'status': 'Follow-up needed'
        },
        {
            'claim_number': '7032874403', 
            'incident_date': '2018-09-21',
            'description': 'Arrow Sedan follow-up',
            'status': 'March 2020 follow-up'
        },
        {
            'claim_number': '9032385029',
            'incident_date': '2019-03-29', 
            'description': 'Market research related',
            'status': 'Under investigation'
        },
        {
            'claim_number': '8032663047',
            'incident_date': '2019-10-26',
            'description': 'Total Loss - F2467',
            'status': 'Settlement paid'
        },
        {
            'claim_number': '4031146355',
            'incident_date': '2017-01-07',
            'description': 'Arrow Sedan claim',
            'status': 'Processed'
        },
        {
            'claim_number': '1114786',
            'incident_date': 'Unknown',
            'description': 'Wawanesa claim',
            'status': 'Unknown'
        }
    ]
    
    print(f"Found {len(known_claims)} specific insurance claims:")
    for claim in known_claims:
        print(f"  Claim {claim['claim_number']}: {claim['description']} ({claim['incident_date']})")
    
    return known_claims

def extract_square_payouts():
    """Extract Square payout information from existing reports."""
    
    print("\n=== Analyzing Square Payout Records ===")
    
    # Look for existing square payout file
    payout_file = Path("l:/limo/reports/square_payout_breakdown.csv")
    if not payout_file.exists():
        print("Square payout file not found")
        return []
    
    square_payouts = []
    
    try:
        with open(payout_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                square_payouts.append({
                    'payout_date': row.get('payout_date', ''),
                    'gross_amount': float(row.get('gross_amount', 0)),
                    'fees': float(row.get('fees', 0)),
                    'net_amount': float(row.get('net_amount', 0)),
                    'description': row.get('description', '')
                })
    except Exception as e:
        print(f"Error reading square payouts: {e}")
    
    print(f"Found {len(square_payouts)} Square payout records")
    return square_payouts

def build_insurance_payment_database():
    """Create comprehensive database of all insurance and payment records."""
    
    print("\n=== Building Comprehensive Insurance & Payment Database ===")
    
    # Extract all data sources
    insurance_emails = extract_insurance_claims_from_emails()
    specific_claims = analyze_specific_claims()
    square_payouts = extract_square_payouts()
    
    # Get existing vehicle loan payments
    conn = connect_to_db()
    existing_payments = []
    
    if conn:
        try:
            cur = conn.cursor(cursor_factory=DictCursor)
            
            cur.execute("""
                SELECT vlp.payment_date, vlp.payment_amount, vlp.interest_amount,
                       vlp.fee_amount, vlp.penalty_amount, vlp.paid_by, vlp.notes,
                       vl.vehicle_name, vl.lender
                FROM vehicle_loan_payments vlp
                JOIN vehicle_loans vl ON vlp.loan_id = vl.id
                ORDER BY vlp.payment_date
            """)
            
            existing_payments = cur.fetchall()
            conn.close()
            
        except Exception as e:
            print(f"Database error: {e}")
            if conn:
                conn.close()
    
    # Combine all records
    all_records = []
    
    # Add insurance records
    for record in insurance_emails:
        all_records.append({
            'type': 'Insurance Email',
            'date': record['date_sent'][:10] if record['date_sent'] else 'Unknown',
            'description': record['subject'],
            'amounts': record['amounts'],
            'source': record['file_name'],
            'details': {
                'claims': record['claim_numbers'],
                'vehicles': record['vehicles'],
                'status': record['status_keywords']
            }
        })
    
    # Add specific claims
    for claim in specific_claims:
        all_records.append({
            'type': 'Insurance Claim',
            'date': claim['incident_date'],
            'description': f"Claim #{claim['claim_number']}: {claim['description']}",
            'amounts': [],
            'source': 'Email Analysis',
            'details': {
                'claim_number': claim['claim_number'],
                'status': claim['status']
            }
        })
    
    # Add square payouts
    for payout in square_payouts:
        all_records.append({
            'type': 'Square Payout',
            'date': payout['payout_date'],
            'description': f"Square payout: ${payout['net_amount']:.2f}",
            'amounts': [payout['gross_amount'], payout['net_amount']],
            'source': 'Square Reports',
            'details': {
                'gross': payout['gross_amount'],
                'fees': payout['fees'],
                'net': payout['net_amount']
            }
        })
    
    # Add existing loan payments
    for payment in existing_payments:
        all_records.append({
            'type': 'Loan Payment',
            'date': str(payment['payment_date']),
            'description': f"Loan payment: {payment['vehicle_name']}",
            'amounts': [float(payment['payment_amount'])],
            'source': 'Database Record',
            'details': {
                'lender': payment['lender'],
                'interest': payment['interest_amount'],
                'fees': payment['fee_amount'],
                'notes': payment['notes']
            }
        })
    
    # Sort by date
    all_records.sort(key=lambda x: x['date'])
    
    # Generate comprehensive report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"l:/limo/reports/complete_insurance_payment_reconstruction_{timestamp}.csv"
    
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date', 'Type', 'Description', 'Primary Amount', 'All Amounts', 
            'Source', 'Details'
        ])
        
        total_insurance_amounts = 0
        total_payment_amounts = 0
        
        for record in all_records:
            primary_amount = record['amounts'][0] if record['amounts'] else 0
            all_amounts = '; '.join([f'${amt:,.2f}' for amt in record['amounts']])
            
            if record['type'] in ['Insurance Email', 'Insurance Claim']:
                total_insurance_amounts += sum(record['amounts'])
            elif record['type'] in ['Loan Payment', 'Square Payout']:
                total_payment_amounts += sum(record['amounts'])
            
            writer.writerow([
                record['date'],
                record['type'],
                record['description'][:100],  # Truncate long descriptions
                f"${primary_amount:,.2f}" if primary_amount else "",
                all_amounts,
                record['source'],
                str(record['details'])[:200]  # Truncate long details
            ])
        
        # Add summary row
        writer.writerow(['', '', '', '', '', '', ''])
        writer.writerow([
            'SUMMARY',
            f'{len(all_records)} total records',
            f'Insurance: ${total_insurance_amounts:,.2f}',
            f'Payments: ${total_payment_amounts:,.2f}',
            '',
            '',
            f'Generated: {datetime.now()}'
        ])
    
    print(f"\nComprehensive report generated: {report_path}")
    print(f"Total records: {len(all_records)}")
    print(f"Insurance-related amounts: ${total_insurance_amounts:,.2f}")
    print(f"Payment amounts: ${total_payment_amounts:,.2f}")
    
    return all_records, report_path

def main():
    """Main execution function."""
    
    print("=" * 80)
    print("COMPREHENSIVE INSURANCE & PAYMENT RECONSTRUCTION")
    print("=" * 80)
    
    records, report_path = build_insurance_payment_database()
    
    print("\n" + "=" * 50)
    print("RECONSTRUCTION COMPLETE")
    print("=" * 50)
    print(f"Comprehensive report: {report_path}")
    
    return records

if __name__ == "__main__":
    records = main()