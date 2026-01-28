#!/usr/bin/env python3
"""
Comprehensive Payment Linking Pipeline

This script creates a complete data extraction and linking system:
1. Extract all LMS data (payments, deposits, charters) linked by reserve_number
2. Analyze payment types (cash, check, credit card, etc.)
3. Search email data for matching references (#codes, names, amounts)
4. Categorize payment sources (e-transfer, Square, refund, etc.)
5. Create definitive payment→charter links based on all evidence

Outputs comprehensive CSV reports for review and application.
"""
import os
import csv
import re
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def extract_lms_unified_data():
    """Extract and link all LMS data by reserve_number and keys"""
    print("Extracting unified LMS data...")
    
    unified_data = {}  # reserve_number -> data dict
    
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all charters
            cur.execute("""
                SELECT charter_id, reserve_number, charter_date, 
                       COALESCE(total_amount_due, rate, 0) as amount_due,
                       COALESCE(retainer, deposit, 0) as retainer,
                       payment_status, client_id
                FROM charters 
                WHERE reserve_number IS NOT NULL
                ORDER BY charter_id
            """)
            
            for charter in cur.fetchall():
                reserve = charter['reserve_number']
                unified_data[reserve] = {
                    'charter': dict(charter),
                    'lms_payments': [],
                    'lms_deposits': [],
                    'existing_payments': [],
                    'email_matches': [],
                    'suggested_links': []
                }
            
            # Get LMS payments (from staging)
            cur.execute("""
                SELECT * FROM lms_payments 
                WHERE reserve_id IS NOT NULL
                ORDER BY payment_id
            """)
            
            for payment in cur.fetchall():
                reserve = payment['reserve_id']
                if reserve in unified_data:
                    unified_data[reserve]['lms_payments'].append(dict(payment))
            
            # Get LMS deposits
            cur.execute("""
                SELECT * FROM lms_deposits 
                ORDER BY deposit_key
            """)
            
            for deposit in cur.fetchall():
                # Extract reserve from payment_key if available
                reserve = None
                if deposit['payment_key']:
                    # Format: LMSDEP:xxxxxxx:reserve_part
                    parts = deposit['payment_key'].split(':')
                    if len(parts) >= 3:
                        reserve_match = re.search(r'0\d{5}', parts[2])
                        if reserve_match:
                            reserve = reserve_match.group(0)
                
                if reserve and reserve in unified_data:
                    unified_data[reserve]['lms_deposits'].append(dict(deposit))
            
            # Get existing payments in the system
            cur.execute("""
                SELECT p.*, c.reserve_number
                FROM payments p
                JOIN charters c ON p.charter_id = c.charter_id
                WHERE c.reserve_number IS NOT NULL
                ORDER BY p.payment_id
            """)
            
            for payment in cur.fetchall():
                reserve = payment['reserve_number']
                if reserve in unified_data:
                    unified_data[reserve]['existing_payments'].append(dict(payment))
    
    print(f"Extracted data for {len(unified_data)} reserves")
    return unified_data

def analyze_payment_types(unified_data):
    """Analyze payment methods and extract searchable criteria"""
    print("Analyzing payment types and extracting search criteria...")
    
    search_criteria = []
    
    for reserve, data in unified_data.items():
        charter = data['charter']
        
        # Process LMS deposits for payment type analysis
        for deposit in data['lms_deposits']:
            payment_method = str(deposit.get('payment_method', '')).lower()
            number_field = str(deposit.get('number', ''))
            amount = deposit.get('amount', 0)
            date = deposit.get('deposit_date')
            
            criteria = {
                'reserve_number': reserve,
                'charter_id': charter['charter_id'],
                'source': 'lms_deposit',
                'deposit_key': deposit.get('deposit_key'),
                'amount': amount,
                'date': date,
                'payment_method': payment_method,
                'search_hints': []
            }
            
            # Extract search hints from number field
            if number_field:
                # 4-character codes like #RGbm
                four_char_codes = re.findall(r'#?([A-Za-z0-9]{4})', number_field)
                criteria['search_hints'].extend(four_char_codes)
                
                # Longer number sequences
                number_sequences = re.findall(r'\d{5,}', number_field)
                criteria['search_hints'].extend(number_sequences)
                
                # Names (likely client names)
                name_parts = re.findall(r'[A-Za-z]{3,}', number_field)
                criteria['search_hints'].extend(name_parts)
            
            # Categorize by payment method
            if 'cash' in payment_method:
                criteria['category'] = 'cash'
                criteria['email_search'] = False
            elif 'check' in payment_method:
                criteria['category'] = 'check'
                criteria['email_search'] = False
            elif 'credit' in payment_method:
                criteria['category'] = 'credit_card'
                criteria['email_search'] = True  # Could be Square
                criteria['search_hints'].append('square')
            else:
                criteria['category'] = 'electronic'
                criteria['email_search'] = True  # Likely e-transfer
            
            search_criteria.append(criteria)
            data['suggested_links'].append(criteria)
    
    print(f"Generated {len(search_criteria)} search criteria")
    return search_criteria

def search_email_matches(search_criteria):
    """Search email data for matching references"""
    print("Searching email data for matches...")
    
    email_data = {}
    
    # Load Interac email data
    interac_file = r"l:/limo/reports/etransfer_emails.csv"
    if os.path.exists(interac_file):
        with open(interac_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email_data[row.get('email_uid', '')] = {
                    'source': 'interac',
                    'subject': row.get('email_subject', ''),
                    'amount': float(row.get('amount', 0) or 0),
                    'date': row.get('email_date', ''),
                    'sender': row.get('sender_name', ''),
                    'reference': row.get('reference_number', ''),
                    **row
                }
    
    # Load Square email data
    square_file = r"l:/limo/reports/square_emails.csv"
    if os.path.exists(square_file):
        with open(square_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email_data[row.get('email_uid', '')] = {
                    'source': 'square',
                    'subject': row.get('email_subject', ''),
                    'amount': float(row.get('amount', 0) or 0),
                    'date': row.get('email_date', ''),
                    'reference': row.get('reference_number', ''),
                    'classification': row.get('classification', ''),
                    **row
                }
    
    print(f"Loaded {len(email_data)} email records")
    
    # Match criteria against email data
    matches = []
    
    for criteria in search_criteria:
        if not criteria.get('email_search', False):
            continue
            
        best_matches = []
        
        for email_uid, email in email_data.items():
            match_score = 0
            match_reasons = []
            
            # Amount matching (within tolerance)
            if abs(email['amount'] - criteria['amount']) <= 2.0:
                match_score += 100
                match_reasons.append(f"amount_match_${email['amount']}")
            
            # Date proximity (within 30 days)
            try:
                email_date = datetime.fromisoformat(email['date'].replace('Z', '+00:00')).date()
                criteria_date = criteria['date']
                if criteria_date and abs((email_date - criteria_date).days) <= 30:
                    match_score += 50
                    match_reasons.append(f"date_proximity_{abs((email_date - criteria_date).days)}d")
            except:
                pass
            
            # Search hint matching
            search_text = f"{email['subject']} {email.get('reference', '')} {email.get('sender', '')}"
            for hint in criteria['search_hints']:
                if hint.lower() in search_text.lower():
                    match_score += 25
                    match_reasons.append(f"hint_match_{hint}")
            
            # Reserve number matching
            if criteria['reserve_number'] in search_text:
                match_score += 200
                match_reasons.append(f"reserve_match_{criteria['reserve_number']}")
            
            if match_score > 50:  # Minimum threshold
                best_matches.append({
                    'email_uid': email_uid,
                    'email': email,
                    'score': match_score,
                    'reasons': match_reasons
                })
        
        # Sort by score and keep top matches
        best_matches.sort(key=lambda x: x['score'], reverse=True)
        criteria['email_matches'] = best_matches[:3]  # Top 3 matches
        
        if best_matches:
            matches.append(criteria)
    
    print(f"Found email matches for {len(matches)} criteria")
    return matches

def generate_linking_reports(unified_data, search_criteria):
    """Generate comprehensive CSV reports for review"""
    print("Generating linking reports...")
    
    os.makedirs('l:/limo/reports', exist_ok=True)
    
    # High-confidence links (ready for application)
    high_confidence = []
    # Medium-confidence links (needs review)
    medium_confidence = []
    # All data for comprehensive review
    comprehensive = []
    
    for reserve, data in unified_data.items():
        charter = data['charter']
        
        for criteria in data['suggested_links']:
            email_matches = criteria.get('email_matches', [])
            
            base_record = {
                'reserve_number': reserve,
                'charter_id': charter['charter_id'],
                'charter_amount_due': charter['amount_due'],
                'charter_retainer': charter['retainer'],
                'charter_date': charter['charter_date'],
                'payment_status': charter['payment_status'],
                'lms_amount': criteria['amount'],
                'lms_date': criteria['date'],
                'lms_method': criteria['payment_method'],
                'lms_category': criteria['category'],
                'search_hints': '|'.join(criteria['search_hints']),
                'existing_payments_count': len(data['existing_payments'])
            }
            
            if email_matches:
                best_match = email_matches[0]
                email = best_match['email']
                
                record = {
                    **base_record,
                    'email_source': email['source'],
                    'email_amount': email['amount'],
                    'email_date': email['date'],
                    'email_subject': email['subject'],
                    'email_uid': best_match['email_uid'],
                    'match_score': best_match['score'],
                    'match_reasons': '|'.join(best_match['reasons']),
                    'confidence': 'high' if best_match['score'] >= 200 else 'medium'
                }
                
                if best_match['score'] >= 200:
                    high_confidence.append(record)
                else:
                    medium_confidence.append(record)
                    
                comprehensive.append(record)
            else:
                # No email match found
                record = {
                    **base_record,
                    'email_source': 'none',
                    'email_amount': 0,
                    'email_date': '',
                    'email_subject': '',
                    'email_uid': '',
                    'match_score': 0,
                    'match_reasons': 'no_email_match',
                    'confidence': 'low'
                }
                comprehensive.append(record)
    
    # Write CSV files
    def write_csv(filename, data, title):
        if data:
            with open(f"l:/limo/reports/{filename}", 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                writer.writeheader()
                writer.writerows(data)
            print(f"  {title}: {len(data)} records -> {filename}")
        else:
            print(f"  {title}: 0 records")
    
    write_csv('payment_links_high_confidence.csv', high_confidence, 'High Confidence Links')
    write_csv('payment_links_medium_confidence.csv', medium_confidence, 'Medium Confidence Links')
    write_csv('payment_links_comprehensive.csv', comprehensive, 'Comprehensive Analysis')
    
    return {
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,
        'comprehensive': comprehensive
    }

def main():
    parser = argparse.ArgumentParser(description='Comprehensive Payment Linking Pipeline')
    parser.add_argument('--apply', action='store_true', help='Apply high-confidence links to database')
    args = parser.parse_args()
    
    print("=== Comprehensive Payment Linking Pipeline ===")
    
    # Step 1: Extract unified LMS data
    unified_data = extract_lms_unified_data()
    
    # Step 2: Analyze payment types and generate search criteria  
    search_criteria = analyze_payment_types(unified_data)
    
    # Step 3: Search email data for matches
    matched_criteria = search_email_matches(search_criteria)
    
    # Update unified_data with email matches
    for criteria in matched_criteria:
        reserve = criteria['reserve_number']
        if reserve in unified_data:
            # Find the corresponding criteria in unified_data and update it
            for link in unified_data[reserve]['suggested_links']:
                if (link['deposit_key'] == criteria.get('deposit_key') and 
                    link['amount'] == criteria['amount']):
                    link['email_matches'] = criteria.get('email_matches', [])
    
    # Step 4: Generate comprehensive reports
    reports = generate_linking_reports(unified_data, search_criteria)
    
    print(f"\n=== Summary ===")
    print(f"High Confidence Links: {len(reports['high_confidence'])}")
    print(f"Medium Confidence Links: {len(reports['medium_confidence'])}")
    print(f"Total Analysis Records: {len(reports['comprehensive'])}")
    
    if args.apply and reports['high_confidence']:
        print(f"\nApplying {len(reports['high_confidence'])} high-confidence links...")
        # TODO: Implement application logic
        print("Application logic to be implemented after review")
    
    print("\nReports generated in l:/limo/reports/")
    print("- payment_links_high_confidence.csv")
    print("- payment_links_medium_confidence.csv") 
    print("- payment_links_comprehensive.csv")

if __name__ == '__main__':
    main()