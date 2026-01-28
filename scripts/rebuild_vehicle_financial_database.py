#!/usr/bin/env python3
"""
Complete Vehicle Loan Rebuild from Heffner Email History (2017-2025)
Extract ALL vehicles and payments including paid off, sold, retired, collision write-offs
"""

import os
import re
import json
import csv
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

def extract_comprehensive_vehicle_data(msg_file_path):
    """Extract all vehicle and financial data from MSG file."""
    try:
        msg = extract_msg.Message(str(msg_file_path))
        
        subject = getattr(msg, 'subject', '')
        body = getattr(msg, 'body', '')
        sender = getattr(msg, 'sender', '')
        date = getattr(msg, 'date', '')
        
        # Extract year from filename for chronological context
        filename = msg_file_path.name
        year_match = re.search(r'^(\d{4})_', filename)
        email_year = int(year_match.group(1)) if year_match else None
        
        financial_data = {
            'file_name': filename,
            'subject': subject,
            'date': str(date),
            'email_year': email_year,
            'sender': sender,
            'vehicles_found': [],
            'loan_amounts': [],
            'payment_amounts': [],
            'balances': [],
            'buyouts': [],
            'lease_references': [],
            'vins_found': [],
            'account_numbers': [],
            'status_indicators': []
        }
        
        if not body:
            return financial_data
        
        # Enhanced VIN extraction
        vin_pattern = r'[A-HJ-NPR-Z0-9]{17}'
        vins = re.findall(vin_pattern, body)
        financial_data['vins_found'] = list(set(vins))
        
        # Vehicle identification patterns
        vehicle_patterns = [
            # Year + Make + Model combinations
            r'(\d{4})\s+(Ford|Honda|Toyota|Chevrolet|Cadillac|Lincoln|Mercedes|BMW|Kia|International)\s+([\w\s]+?)(?=\s|$|\.|,)',
            # Specific vehicle models
            r'\b(E350|E450|F550|F250|F350|Transit|Escalade|Navigator|Excursion|Expedition|Town Car|S550|K900|Camry)\b',
            # Limo/bus specific
            r'\b(limo|limousine|bus|sedan|stretch|party\s+bus|shuttle)\b',
            # Vehicle descriptions
            r'\b(\d+)[\s-]+(pass|passenger)\b'
        ]
        
        for pattern in vehicle_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    vehicle_desc = ' '.join([str(m) for m in match if m])
                else:
                    vehicle_desc = str(match)
                financial_data['vehicles_found'].append(vehicle_desc)
        
        # Comprehensive amount extraction
        amount_patterns = [
            r'\$[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*dollars?',
            r'amount[:\s]*\$?[\d,]+\.?\d*',
            r'payment[:\s]*\$?[\d,]+\.?\d*',
            r'balance[:\s]*\$?[\d,]+\.?\d*',
            r'monthly[:\s]*\$?[\d,]+\.?\d*',
            r'buyout[:\s]*\$?[\d,]+\.?\d*',
            r'outstanding[:\s]*\$?[\d,]+\.?\d*',
            r'owing[:\s]*\$?[\d,]+\.?\d*',
            r'residual[:\s]*\$?[\d,]+\.?\d*'
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if 'buyout' in pattern:
                financial_data['buyouts'].extend(matches)
            elif 'balance' in pattern or 'outstanding' in pattern or 'owing' in pattern:
                financial_data['balances'].extend(matches)
            elif 'payment' in pattern or 'monthly' in pattern:
                financial_data['payment_amounts'].extend(matches)
            else:
                financial_data['loan_amounts'].extend(matches)
        
        # Lease/Account reference extraction
        lease_patterns = [
            r'[HF]\d{4}[A-Z]?[-]?[A-Z]?',  # H4551, F2351, H4552A-B format
            r'lease\s+#?[\d-]+',
            r'account\s+#?[\d-]+',
            r'contract\s+#?[\d-]+'
        ]
        
        for pattern in lease_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            financial_data['lease_references'].extend(matches)
        
        # Status indicators
        status_patterns = [
            r'\b(paid\s+off|buyout|sold|retired|written\s+off|collision|total\s+loss|accident)\b',
            r'\b(active|current|ongoing|new\s+lease)\b',
            r'\b(returned|repo|repossession)\b'
        ]
        
        for pattern in status_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            financial_data['status_indicators'].extend(matches)
        
        # Clean up duplicates
        for key in financial_data:
            if isinstance(financial_data[key], list):
                financial_data[key] = list(set(financial_data[key]))
        
        return financial_data
        
    except Exception as e:
        print(f"Error analyzing {msg_file_path}: {e}")
        return None

def rebuild_vehicle_database(financial_records):
    """Rebuild complete vehicle and loan database from email data."""
    
    conn = connect_to_db()
    if not conn:
        return
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Create a comprehensive mapping of all vehicles mentioned
        vehicle_registry = {}
        lease_registry = {}
        
        print("=== Building Vehicle Registry from Email History ===")
        
        for record in financial_records:
            email_year = record.get('email_year', 'unknown')
            subject = record.get('subject', '')
            
            # Map VINs to vehicle info
            for vin in record.get('vins_found', []):
                if vin not in vehicle_registry:
                    vehicle_registry[vin] = {
                        'vin': vin,
                        'first_mentioned': email_year,
                        'vehicles_described': [],
                        'lease_refs': [],
                        'amounts': [],
                        'status_history': []
                    }
                
                vehicle_registry[vin]['vehicles_described'].extend(record.get('vehicles_found', []))
                vehicle_registry[vin]['lease_refs'].extend(record.get('lease_references', []))
                vehicle_registry[vin]['amounts'].extend(record.get('loan_amounts', []))
                vehicle_registry[vin]['status_history'].extend(record.get('status_indicators', []))
            
            # Map lease references to financial data
            for lease_ref in record.get('lease_references', []):
                if lease_ref not in lease_registry:
                    lease_registry[lease_ref] = {
                        'lease_ref': lease_ref,
                        'first_mentioned': email_year,
                        'last_mentioned': email_year,
                        'amounts': [],
                        'payments': [],
                        'balances': [],
                        'buyouts': [],
                        'vehicles': [],
                        'status_changes': []
                    }
                else:
                    lease_registry[lease_ref]['last_mentioned'] = email_year
                
                lease_registry[lease_ref]['amounts'].extend(record.get('loan_amounts', []))
                lease_registry[lease_ref]['payments'].extend(record.get('payment_amounts', []))
                lease_registry[lease_ref]['balances'].extend(record.get('balances', []))
                lease_registry[lease_ref]['buyouts'].extend(record.get('buyouts', []))
                lease_registry[lease_ref]['vehicles'].extend(record.get('vehicles_found', []))
                lease_registry[lease_ref]['status_changes'].extend(record.get('status_indicators', []))
        
        # Generate comprehensive report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Vehicle registry report
        vehicle_report_path = f"l:/limo/heffner_emails_complete/extracted_data/vehicle_registry_{timestamp}.csv"
        with open(vehicle_report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'VIN', 'First Mentioned Year', 'Vehicle Descriptions', 'Lease References', 
                'Amounts Found', 'Status History', 'Needs Database Entry'
            ])
            
            for vin, data in vehicle_registry.items():
                # Check if vehicle exists in database
                cur.execute("SELECT vehicle_id FROM vehicles WHERE vin_number = %s", (vin,))
                exists = cur.fetchone()
                
                writer.writerow([
                    vin,
                    data['first_mentioned'],
                    '; '.join(data['vehicles_described'][:10]),  # Limit output
                    '; '.join(data['lease_refs'][:5]),
                    '; '.join(data['amounts'][:10]),
                    '; '.join(data['status_history'][:5]),
                    'No' if exists else 'Yes'
                ])
        
        # Lease registry report  
        lease_report_path = f"l:/limo/heffner_emails_complete/extracted_data/lease_registry_{timestamp}.csv"
        with open(lease_report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Lease Reference', 'First Year', 'Last Year', 'Duration Years', 
                'Loan Amounts', 'Payment Amounts', 'Outstanding Balances', 
                'Buyout Amounts', 'Vehicles', 'Status Changes', 'Needs Loan Record'
            ])
            
            for lease_ref, data in lease_registry.items():
                duration = data['last_mentioned'] - data['first_mentioned'] if isinstance(data['last_mentioned'], int) and isinstance(data['first_mentioned'], int) else 0
                
                # Check for existing loan record
                cur.execute("SELECT id FROM vehicle_loans WHERE notes LIKE %s", (f'%{lease_ref}%',))
                exists = cur.fetchone()
                
                writer.writerow([
                    lease_ref,
                    data['first_mentioned'],
                    data['last_mentioned'],
                    duration,
                    '; '.join(data['amounts'][:10]),
                    '; '.join(data['payments'][:10]), 
                    '; '.join(data['balances'][:10]),
                    '; '.join(data['buyouts'][:5]),
                    '; '.join(data['vehicles'][:10]),
                    '; '.join(data['status_changes'][:5]),
                    'No' if exists else 'Yes'
                ])
        
        # Summary statistics
        summary = {
            'scan_date': datetime.now().isoformat(),
            'total_emails_processed': len(financial_records),
            'unique_vins_found': len(vehicle_registry),
            'unique_lease_references': len(lease_registry),
            'vins_needing_database_entry': len([v for v in vehicle_registry.values() if not cur.execute("SELECT 1 FROM vehicles WHERE vin_number = %s", (v['vin'],)) or not cur.fetchone()]),
            'active_lease_periods': len([l for l in lease_registry.values() if 'buyout' not in ' '.join(l['status_changes']).lower() and 'paid off' not in ' '.join(l['status_changes']).lower()])
        }
        
        summary_path = f"l:/limo/heffner_emails_complete/extracted_data/rebuild_summary_{timestamp}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\n=== Vehicle Database Rebuild Analysis Complete ===")
        print(f"Unique VINs found: {summary['unique_vins_found']}")
        print(f"Unique lease references: {summary['unique_lease_references']}")
        print(f"Vehicle registry: {vehicle_report_path}")
        print(f"Lease registry: {lease_report_path}")
        print(f"Summary: {summary_path}")
        
        conn.close()
        
        return vehicle_registry, lease_registry, summary
        
    except Exception as e:
        print(f"Database rebuild error: {e}")
        if conn:
            conn.close()
        return None, None, None

def main():
    """Main execution function."""
    print("=== Complete Vehicle Loan Database Rebuild ===")
    
    # Process all MSG files
    msg_folder = Path("l:/limo/heffner_emails_complete/msg_files")
    
    if not msg_folder.exists():
        print(f"MSG folder not found: {msg_folder}")
        return
    
    msg_files = list(msg_folder.glob("*.msg"))
    print(f"Processing {len(msg_files)} MSG files for complete financial rebuild...")
    
    financial_records = []
    
    for i, msg_file in enumerate(msg_files):
        if i % 25 == 0:
            print(f"  Processed {i}/{len(msg_files)} files...")
            
        record = extract_comprehensive_vehicle_data(msg_file)
        if record and (record['vehicles_found'] or record['vins_found'] or record['lease_references']):
            financial_records.append(record)
    
    print(f"Extracted financial data from {len(financial_records)} relevant emails")
    
    # Rebuild database
    vehicle_registry, lease_registry, summary = rebuild_vehicle_database(financial_records)
    
    if vehicle_registry:
        print(f"\n=== Rebuild Complete ===")
        print(f"Found {len(vehicle_registry)} unique vehicles")
        print(f"Found {len(lease_registry)} unique lease accounts")
        print("Review the generated CSV files to identify missing database entries")
    
    return financial_records, vehicle_registry, lease_registry

if __name__ == "__main__":
    records, vehicles, leases = main()