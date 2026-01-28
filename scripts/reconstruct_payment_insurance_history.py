#!/usr/bin/env python3
"""
Reconstruct Complete Payment & Insurance Payout History
Extract all payments, insurance claims, settlements, and payouts for all vehicles
"""

import os
import re
import csv
import json
import extract_msg
from pathlib import Path
from datetime import datetime, date
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

def extract_payment_data_from_emails():
    """Extract payment information from all Heffner emails."""
    
    print("=== Extracting Payment Data from 245 Heffner Emails ===")
    
    msg_folder = Path("l:/limo/heffner_emails_complete/msg_files")
    if not msg_folder.exists():
        print(f"MSG folder not found: {msg_folder}")
        return []
    
    msg_files = list(msg_folder.glob("*.msg"))
    payment_records = []
    
    for i, msg_file in enumerate(msg_files):
        if i % 25 == 0:
            print(f"  Processing emails {i}/{len(msg_files)}...")
        
        try:
            msg = extract_msg.Message(str(msg_file))
            
            subject = getattr(msg, 'subject', '')
            body = getattr(msg, 'body', '')
            date_sent = getattr(msg, 'date', '')
            sender = getattr(msg, 'sender', '')
            
            if not body:
                continue
            
            # Extract year from filename for chronological context
            filename = msg_file.name
            year_match = re.search(r'^(\d{4})_', filename)
            email_year = int(year_match.group(1)) if year_match else None
            
            payment_info = {
                'file_name': filename,
                'date_sent': str(date_sent),
                'email_year': email_year,
                'subject': subject,
                'sender': sender,
                'payments_found': [],
                'insurance_references': [],
                'settlement_amounts': [],
                'lease_references': [],
                'vehicle_references': []
            }
            
            # Payment amount patterns
            payment_patterns = [
                r'payment[:\s]*\$?([\d,]+\.?\d*)',
                r'monthly[:\s]*\$?([\d,]+\.?\d*)',
                r'paid[:\s]*\$?([\d,]+\.?\d*)',
                r'remittance[:\s]*\$?([\d,]+\.?\d*)',
                r'amount[:\s]*paid[:\s]*\$?([\d,]+\.?\d*)',
                r'due[:\s]*\$?([\d,]+\.?\d*)',
                r'balance[:\s]*owing[:\s]*\$?([\d,]+\.?\d*)',
                r'received[:\s]*\$?([\d,]+\.?\d*)'
            ]
            
            # Insurance/settlement patterns
            insurance_patterns = [
                r'insurance[:\s]*\$?([\d,]+\.?\d*)',
                r'settlement[:\s]*\$?([\d,]+\.?\d*)',
                r'claim[:\s]*\$?([\d,]+\.?\d*)',
                r'payout[:\s]*\$?([\d,]+\.?\d*)',
                r'collision[:\s]*\$?([\d,]+\.?\d*)',
                r'total[\s]*loss[:\s]*\$?([\d,]+\.?\d*)',
                r'settlement[\s]*amount[:\s]*\$?([\d,]+\.?\d*)',
                r'insurance[\s]*proceeds[:\s]*\$?([\d,]+\.?\d*)'
            ]
            
            # Extract payment amounts with context
            for pattern in payment_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE)
                for match in matches:
                    amount = float(re.sub(r'[,]', '', match))
                    if 10 <= amount <= 100000:  # Reasonable payment range
                        payment_info['payments_found'].append({
                            'amount': amount,
                            'context': pattern.split('[')[0],  # Get the keyword
                            'raw_text': match
                        })
            
            # Extract insurance amounts with context
            for pattern in insurance_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE)
                for match in matches:
                    amount = float(re.sub(r'[,]', '', match))
                    if 1000 <= amount <= 500000:  # Reasonable insurance range
                        payment_info['settlement_amounts'].append({
                            'amount': amount,
                            'context': pattern.split('[')[0],
                            'raw_text': match
                        })
            
            # Extract lease references
            lease_patterns = [
                r'[HF]\d{4}[A-Z]?[-]?[A-Z]?',
                r'lease\s+#?[\d-]+',
                r'account\s+#?[\d-]+'
            ]
            
            for pattern in lease_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE)
                payment_info['lease_references'].extend(matches)
            
            # Extract vehicle references
            vehicle_patterns = [
                r'\b(E350|E450|F550|F250|F350|Transit|Escalade|Navigator|Excursion|Camry|K900)\b',
                r'(\d{4})\s+(Ford|Honda|Toyota|Chevrolet|Cadillac|Lincoln|Mercedes|BMW|Kia)'
            ]
            
            for pattern in vehicle_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        vehicle_ref = ' '.join([str(m) for m in match if m])
                    else:
                        vehicle_ref = str(match)
                    payment_info['vehicle_references'].append(vehicle_ref)
            
            # Check for insurance keywords
            insurance_keywords = [
                'insurance', 'claim', 'settlement', 'collision', 'accident', 
                'total loss', 'write off', 'payout', 'deductible', 'coverage'
            ]
            
            for keyword in insurance_keywords:
                if keyword in body.lower():
                    payment_info['insurance_references'].append(keyword)
            
            # Only keep records with relevant financial data
            if (payment_info['payments_found'] or 
                payment_info['settlement_amounts'] or 
                payment_info['insurance_references']):
                payment_records.append(payment_info)
                
        except Exception as e:
            print(f"Error processing {msg_file}: {e}")
            continue
    
    print(f"Extracted payment data from {len(payment_records)} relevant emails")
    return payment_records

def scan_documents_for_insurance_claims():
    """Scan all CIBC uploads and documents for insurance records."""
    
    print("\n=== Scanning Documents for Insurance Claims & Settlements ===")
    
    # Directories to scan
    scan_dirs = [
        "l:/limo/CIBC UPLOADS",
        "l:/limo/receipts",
        "l:/limo/audit_records"
    ]
    
    insurance_records = []
    
    for scan_dir in scan_dirs:
        scan_path = Path(scan_dir)
        if not scan_path.exists():
            continue
            
        print(f"  Scanning {scan_dir}...")
        
        # Look for insurance-related files
        file_patterns = [
            "**/*insurance*",
            "**/*claim*", 
            "**/*settlement*",
            "**/*collision*",
            "**/*accident*",
            "**/*payout*"
        ]
        
        for pattern in file_patterns:
            for file_path in scan_path.glob(pattern):
                if file_path.is_file():
                    insurance_records.append({
                        'file_path': str(file_path),
                        'file_name': file_path.name,
                        'file_type': file_path.suffix.lower(),
                        'directory': scan_dir,
                        'pattern_matched': pattern.replace('**/*', '').replace('*', '')
                    })
    
    print(f"Found {len(insurance_records)} insurance-related files")
    return insurance_records

def reconstruct_td_bank_payments():
    """Extract TD Bank Navigator payment history from bank records."""
    
    print("\n=== Reconstructing TD Bank Navigator Payment History ===")
    
    # We know from the database there's a TD Bank loan for Navigator
    # Look for bank statements or transaction records
    
    bank_records = []
    
    # Check CIBC uploads for TD Bank references
    cibc_path = Path("l:/limo/CIBC UPLOADS")
    if cibc_path.exists():
        for file_path in cibc_path.rglob("*"):
            if file_path.is_file():
                file_name_lower = file_path.name.lower()
                if any(keyword in file_name_lower for keyword in ['td', 'navigator', 'lincoln', 'bank']):
                    bank_records.append({
                        'file_path': str(file_path),
                        'file_name': file_path.name,
                        'match_reason': 'TD/Navigator/Lincoln reference'
                    })
    
    # Estimate payment history based on known loan details
    # From database: $122,321.48 original, $112,820.05 current, $1,727.84 monthly
    
    estimated_payments = []
    original_amount = 122321.48
    current_balance = 112820.05
    monthly_payment = 1727.84
    
    # Calculate estimated payments made
    amount_paid = original_amount - current_balance
    payments_made = round(amount_paid / monthly_payment)
    
    print(f"  Estimated {payments_made} payments of ${monthly_payment:,.2f}")
    print(f"  Total paid: ${amount_paid:,.2f}")
    print(f"  Found {len(bank_records)} potentially related files")
    
    return bank_records, {
        'estimated_payments_made': payments_made,
        'monthly_payment': monthly_payment,
        'total_paid': amount_paid,
        'original_amount': original_amount,
        'current_balance': current_balance
    }

def build_comprehensive_payment_timeline(payment_data, insurance_files, bank_data):
    """Build complete chronological payment and settlement timeline."""
    
    print("\n=== Building Comprehensive Payment Timeline ===")
    
    conn = connect_to_db()
    if not conn:
        return None
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Get all loans for reference
        cur.execute("""
            SELECT id, vehicle_name, lender, opening_balance, closing_balance, 
                   loan_start_date, notes
            FROM vehicle_loans 
            WHERE opening_balance > 0
            ORDER BY opening_balance DESC
        """)
        
        loans = cur.fetchall()
        
        timeline_events = []
        
        # Process email payment data
        for record in payment_data:
            for payment in record['payments_found']:
                timeline_events.append({
                    'date': record['date_sent'][:10] if record['date_sent'] else f"{record['email_year']}-01-01",
                    'type': 'Payment',
                    'amount': payment['amount'],
                    'description': f"Payment: ${payment['amount']:,.2f} ({payment['context']})",
                    'source': f"Email: {record['file_name']}",
                    'vehicle_refs': record['vehicle_references'],
                    'lease_refs': record['lease_references']
                })
            
            for settlement in record['settlement_amounts']:
                timeline_events.append({
                    'date': record['date_sent'][:10] if record['date_sent'] else f"{record['email_year']}-01-01",
                    'type': 'Insurance',
                    'amount': settlement['amount'],
                    'description': f"Insurance: ${settlement['amount']:,.2f} ({settlement['context']})",
                    'source': f"Email: {record['file_name']}",
                    'vehicle_refs': record['vehicle_references'],
                    'lease_refs': record['lease_references']
                })
        
        # Add known payments from database
        cur.execute("""
            SELECT vlp.payment_date, vlp.payment_amount, vlp.paid_by, vlp.notes,
                   vl.vehicle_name, vl.lender
            FROM vehicle_loan_payments vlp
            JOIN vehicle_loans vl ON vlp.loan_id = vl.id
            ORDER BY vlp.payment_date
        """)
        
        existing_payments = cur.fetchall()
        
        for payment in existing_payments:
            timeline_events.append({
                'date': str(payment['payment_date']),
                'type': 'Confirmed Payment',
                'amount': float(payment['payment_amount']),
                'description': f"Confirmed Payment: ${payment['payment_amount']:,.2f} - {payment['vehicle_name']}",
                'source': f"Database Record - {payment['lender']}",
                'vehicle_refs': [payment['vehicle_name']],
                'lease_refs': [],
                'notes': payment['notes']
            })
        
        # Sort timeline by date
        timeline_events.sort(key=lambda x: x['date'])
        
        # Generate timeline report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timeline_path = f"l:/limo/reports/complete_payment_insurance_timeline_{timestamp}.csv"
        
        with open(timeline_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Date', 'Type', 'Amount', 'Description', 'Source', 
                'Vehicle References', 'Lease References', 'Notes'
            ])
            
            for event in timeline_events:
                writer.writerow([
                    event['date'],
                    event['type'], 
                    f"${event['amount']:,.2f}",
                    event['description'],
                    event['source'],
                    '; '.join(event['vehicle_refs'][:5]),
                    '; '.join(event['lease_refs'][:3]),
                    event.get('notes', '')
                ])
        
        print(f"Timeline report generated: {timeline_path}")
        print(f"Total events: {len(timeline_events)}")
        
        # Summary statistics
        payment_total = sum(e['amount'] for e in timeline_events if e['type'] in ['Payment', 'Confirmed Payment'])
        insurance_total = sum(e['amount'] for e in timeline_events if e['type'] == 'Insurance')
        
        summary = {
            'total_events': len(timeline_events),
            'total_payments': payment_total,
            'total_insurance_settlements': insurance_total,
            'date_range': f"{timeline_events[0]['date']} to {timeline_events[-1]['date']}" if timeline_events else "No events",
            'payment_events': len([e for e in timeline_events if e['type'] in ['Payment', 'Confirmed Payment']]),
            'insurance_events': len([e for e in timeline_events if e['type'] == 'Insurance'])
        }
        
        return timeline_events, timeline_path, summary
        
    except Exception as e:
        print(f"Error building timeline: {e}")
        return None, None, None
    finally:
        if conn:
            conn.close()

def main():
    """Main execution function."""
    
    print("=" * 80)
    print("RECONSTRUCTING COMPLETE PAYMENT & INSURANCE PAYOUT HISTORY")
    print("=" * 80)
    
    # Step 1: Extract payment data from emails
    payment_data = extract_payment_data_from_emails()
    
    # Step 2: Scan for insurance documents
    insurance_files = scan_documents_for_insurance_claims()
    
    # Step 3: Reconstruct TD Bank payment history
    bank_files, bank_estimates = reconstruct_td_bank_payments()
    
    # Step 4: Build comprehensive timeline
    timeline, timeline_path, summary = build_comprehensive_payment_timeline(
        payment_data, insurance_files, bank_estimates
    )
    
    if summary:
        print(f"\n" + "=" * 50)
        print("RECONSTRUCTION COMPLETE")
        print("=" * 50)
        print(f"Total financial events: {summary['total_events']}")
        print(f"Payment events: {summary['payment_events']} (${summary['total_payments']:,.2f})")
        print(f"Insurance events: {summary['insurance_events']} (${summary['total_insurance_settlements']:,.2f})")
        print(f"Date range: {summary['date_range']}")
        print(f"Timeline report: {timeline_path}")
        print(f"Insurance files found: {len(insurance_files)}")
    
    return payment_data, insurance_files, bank_estimates, timeline

if __name__ == "__main__":
    payment_data, insurance_files, bank_data, timeline = main()