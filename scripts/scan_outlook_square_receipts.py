#!/usr/bin/env python3
"""
Scan Outlook PST for Square Payment Receipt Emails

Searches for emails containing:
- Square payment receipts (sent to customers)
- Square payment confirmations
- Square transaction notifications
- Square invoice payments
- Square online payment receipts

Extracts:
- Payment date/time
- Payment amount
- Customer name/email
- Last 4 digits of card
- Reserve number (if mentioned in receipt)
- Transaction ID
"""

import os
import sys
import win32com.client
from datetime import datetime
import psycopg2
from dotenv import load_dotenv
import re
import hashlib

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

PST_PATH = r"l:\limo\outlook backup\info@arrowlimo.ca.pst"

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def scan_pst_for_square_receipts():
    """Scan PST file for Square receipt emails."""
    
    print('=' * 100)
    print('SCANNING OUTLOOK PST FOR SQUARE PAYMENT RECEIPTS')
    print('=' * 100)
    
    if not os.path.exists(PST_PATH):
        print(f'\n[FAIL] ERROR: PST file not found: {PST_PATH}')
        return []
    
    print(f'\n✓ Opening PST: {PST_PATH}')
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        pst_folder = outlook.AddStore(PST_PATH)
        
        # Get the root folder
        root_folder = None
        for store in outlook.Stores:
            if PST_PATH.lower() in store.FilePath.lower():
                root_folder = store.GetRootFolder()
                break
        
        if not root_folder:
            print('[FAIL] Could not access PST root folder')
            return []
        
        print(f'✓ Opened PST: {root_folder.Name}')
        
    except Exception as e:
        print(f'[FAIL] Failed to open PST: {e}')
        return []
    
    # Search keywords for Square receipts
    # Square sends receipts from receipts@messaging.squareup.com or noreply@squareup.com
    square_senders = [
        'squareup.com',
        'square.com',
        'receipts@messaging.squareup.com',
        'noreply@squareup.com',
        'no-reply@squareup.com'
    ]
    
    receipt_keywords = [
        'receipt from Arrow Limousine',
        'payment receipt',
        'square receipt',
        'invoice from Arrow',
        'paid an invoice',
        'sent you a receipt',
        'payment confirmation'
    ]
    
    square_emails = []
    
    def search_folder(folder, depth=0):
        """Recursively search folder for Square receipt emails."""
        indent = '  ' * depth
        
        try:
            folder_name = folder.Name
            print(f'{indent}📁 Searching: {folder_name}')
            
            # Search messages in this folder
            items = folder.Items
            items.Sort("[ReceivedTime]", True)  # Newest first
            
            count = 0
            for item in items:
                try:
                    if not hasattr(item, 'Subject'):
                        continue
                    
                    subject = item.Subject or ''
                    body = item.Body or ''
                    sender = item.SenderEmailAddress or ''
                    sender_name = item.SenderName or ''
                    
                    # Check if from Square
                    is_square = any(sq_sender in sender.lower() for sq_sender in square_senders)
                    
                    # Or check for Square keywords in subject/body
                    combined_text = f'{subject} {body}'.lower()
                    has_keywords = any(kw in combined_text for kw in receipt_keywords)
                    
                    if is_square or has_keywords:
                        received_time = item.ReceivedTime
                        
                        square_emails.append({
                            'date': received_time,
                            'from': sender,
                            'from_name': sender_name,
                            'subject': subject,
                            'body': body,
                            'folder': folder_name
                        })
                        
                        count += 1
                        print(f'{indent}  ✓ Found: {received_time.strftime("%Y-%m-%d")} | {subject[:60]}')
                
                except Exception as e:
                    continue
            
            if count > 0:
                print(f'{indent}  → Found {count} Square emails in {folder_name}')
            
            # Search subfolders
            for subfolder in folder.Folders:
                search_folder(subfolder, depth + 1)
        
        except Exception as e:
            print(f'{indent}[FAIL] Error searching folder: {e}')
    
    # Start search from root
    print('\n' + '=' * 100)
    print('SEARCHING FOLDERS...')
    print('=' * 100 + '\n')
    
    search_folder(root_folder)
    
    # Close PST
    try:
        outlook.RemoveStore(root_folder)
    except:
        pass
    
    return square_emails

def extract_payment_details(emails):
    """Extract payment details from Square receipt emails."""
    
    print('\n' + '=' * 100)
    print('EXTRACTING PAYMENT DETAILS FROM RECEIPTS')
    print('=' * 100)
    
    extracted_payments = []
    
    for email in sorted(emails, key=lambda x: x['date']):
        body = email['body']
        subject = email['subject']
        
        # Extract payment amount
        # Patterns: "$123.45", "$1,234.56", "Total: $123.45", "Amount: $123.45"
        amount_patterns = [
            r'Total[:\s]+\$?([\d,]+\.?\d{0,2})',
            r'Amount[:\s]+\$?([\d,]+\.?\d{0,2})',
            r'Paid[:\s]+\$?([\d,]+\.?\d{0,2})',
            r'\$\s?([\d,]+\.?\d{2})'
        ]
        
        amount = None
        for pattern in amount_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    break
                except:
                    continue
        
        # Extract reserve number (6-digit or REF format)
        reserve_number = None
        reserve_patterns = [
            r'\b(\d{6})\b',  # 6-digit number like 019708
            r'REF\s?(\d{6})',  # REF format
            r'Reservation[:\s]+(\d{6})',
            r'Charter[:\s]+(\d{6})',
            r'#(\d{6})'
        ]
        
        for pattern in reserve_patterns:
            match = re.search(pattern, body)
            if match:
                reserve_number = match.group(1)
                break
        
        # Extract customer name
        customer_name = None
        name_patterns = [
            r'Receipt for ([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)',
            r'Hi ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)',
            r'Dear ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, body)
            if match:
                customer_name = match.group(1).strip()
                break
        
        # Extract customer email (if mentioned in body)
        customer_email = None
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_matches = re.findall(email_pattern, body)
        for email_addr in email_matches:
            if 'squareup.com' not in email_addr.lower() and 'arrowlimo' not in email_addr.lower():
                customer_email = email_addr
                break
        
        # Extract card last 4 digits
        card_last4 = None
        card_patterns = [
            r'ending in (\d{4})',
            r'card ending (\d{4})',
            r'xxxx-(\d{4})',
            r'\*\*\*\*\s?(\d{4})'
        ]
        
        for pattern in card_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                card_last4 = match.group(1)
                break
        
        # Extract card brand
        card_brand = None
        if 'visa' in body.lower():
            card_brand = 'VISA'
        elif 'mastercard' in body.lower() or 'master card' in body.lower():
            card_brand = 'MASTERCARD'
        elif 'american express' in body.lower() or 'amex' in body.lower():
            card_brand = 'AMERICAN_EXPRESS'
        elif 'discover' in body.lower():
            card_brand = 'DISCOVER'
        
        # Extract transaction ID / payment ID
        transaction_id = None
        trans_patterns = [
            r'Transaction ID[:\s]+([A-Za-z0-9-_]+)',
            r'Payment ID[:\s]+([A-Za-z0-9-_]+)',
            r'Receipt #[:\s]+([A-Za-z0-9-_]+)'
        ]
        
        for pattern in trans_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                transaction_id = match.group(1)
                break
        
        # Generate hash for deduplication
        hash_input = f"{email['date']}|{subject}|{email['from']}|{amount or 0}".encode('utf-8')
        email_hash = hashlib.sha256(hash_input).hexdigest()
        
        detail = {
            'email_date': email['date'],
            'email_subject': subject,
            'email_from': email['from'],
            'email_hash': email_hash,
            'payment_amount': amount,
            'reserve_number': reserve_number,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'card_last4': card_last4,
            'card_brand': card_brand,
            'transaction_id': transaction_id,
            'body_snippet': body[:500]  # First 500 chars for review
        }
        
        extracted_payments.append(detail)
        
        # Print extracted details
        print(f"\n{'─' * 100}")
        print(f"Date: {email['date'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Subject: {subject}")
        print(f"From: {email['from']}")
        
        if amount:
            print(f"Amount: ${amount:.2f}")
        else:
            print("Amount: [NOT FOUND]")
        
        if reserve_number:
            print(f"Reserve #: {reserve_number}")
        else:
            print("Reserve #: [NOT FOUND]")
        
        if customer_name:
            print(f"Customer: {customer_name}")
        
        if customer_email:
            print(f"Email: {customer_email}")
        
        if card_last4:
            print(f"Card: {card_brand or 'UNKNOWN'} ending {card_last4}")
        
        if transaction_id:
            print(f"Transaction ID: {transaction_id}")
    
    return extracted_payments

def save_to_database(payments, dry_run=True):
    """Save extracted payments to email_financial_events table."""
    
    print('\n' + '=' * 100)
    print('SAVING TO DATABASE')
    print('=' * 100)
    
    if dry_run:
        print('\n[DRY RUN] - No database changes will be made')
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    # Check if email_financial_events table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'email_financial_events'
        )
    """)
    
    if not cur.fetchone()[0]:
        print('\n[WARNING] email_financial_events table does not exist')
        print('Create it first with: python scripts/create_email_financial_events_schema.py')
        cur.close()
        conn.close()
        return
    
    # Check for existing records
    cur.execute("SELECT COUNT(*) FROM email_financial_events WHERE source = 'outlook_square_receipt'")
    existing_count = cur.fetchone()[0]
    print(f'\nExisting Square receipt records: {existing_count}')
    
    # Load existing hashes
    cur.execute("SELECT notes FROM email_financial_events WHERE source = 'outlook_square_receipt' AND notes LIKE 'email_hash:%'")
    existing_hashes = set()
    for row in cur.fetchall():
        if row[0] and 'email_hash:' in row[0]:
            hash_val = row[0].split('email_hash:')[1].split()[0]
            existing_hashes.add(hash_val)
    
    print(f'Loaded {len(existing_hashes)} existing email hashes for deduplication')
    
    # Process payments
    inserted = 0
    skipped = 0
    
    for payment in payments:
        # Check if already exists
        if payment['email_hash'] in existing_hashes:
            skipped += 1
            continue
        
        # Skip if no amount found
        if not payment['payment_amount']:
            print(f"  ⚠️  Skipping: No amount found in email from {payment['email_date'].strftime('%Y-%m-%d')}")
            skipped += 1
            continue
        
        # Build notes field
        notes_parts = [f"email_hash:{payment['email_hash']}"]
        if payment['customer_name']:
            notes_parts.append(f"customer:{payment['customer_name']}")
        if payment['customer_email']:
            notes_parts.append(f"email:{payment['customer_email']}")
        if payment['card_last4']:
            notes_parts.append(f"card:{payment['card_brand'] or 'UNKNOWN'} {payment['card_last4']}")
        if payment['transaction_id']:
            notes_parts.append(f"txn_id:{payment['transaction_id']}")
        notes_parts.append(f"subject:{payment['email_subject'][:100]}")
        
        notes = ' | '.join(notes_parts)
        
        # Prepare SQL
        sql = """
            INSERT INTO email_financial_events (
                source, entity, from_email, subject, email_date,
                event_type, amount, currency, status, notes,
                matched_account_number
            ) VALUES (
                'outlook_square_receipt', 'payment', %s, %s, %s,
                'square_receipt', %s, 'CAD', 'processed', %s,
                %s
            )
        """
        
        if dry_run:
            print(f"  [DRY RUN] Would insert: {payment['email_date'].strftime('%Y-%m-%d')} ${payment['payment_amount']:.2f} Reserve: {payment['reserve_number'] or 'N/A'}")
        else:
            try:
                cur.execute(sql, (
                    payment['email_from'],
                    payment['email_subject'],
                    payment['email_date'],
                    payment['payment_amount'],
                    notes,
                    payment['reserve_number']  # Store reserve number in matched_account_number if found
                ))
                inserted += 1
                print(f"  ✓ Inserted: {payment['email_date'].strftime('%Y-%m-%d')} ${payment['payment_amount']:.2f} Reserve: {payment['reserve_number'] or 'N/A'}")
            except Exception as e:
                print(f"  ✗ Error inserting: {e}")
                skipped += 1
    
    if not dry_run:
        conn.commit()
        print(f'\n✓ Committed {inserted} new Square receipt records to database')
    
    print(f'\nSummary:')
    print(f'  Total payments processed: {len(payments)}')
    print(f'  New records inserted: {inserted}')
    print(f'  Skipped (duplicates/invalid): {skipped}')
    
    cur.close()
    conn.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scan Outlook PST for Square payment receipts')
    parser.add_argument('--write', action='store_true', help='Write to database (default is dry-run)')
    parser.add_argument('--export-csv', type=str, help='Export to CSV file')
    
    args = parser.parse_args()
    
    # Scan PST for Square emails
    emails = scan_pst_for_square_receipts()
    
    if not emails:
        print('\n[INFO] No Square receipt emails found')
        return
    
    print(f'\n✓ Found {len(emails)} Square receipt emails')
    
    # Extract payment details
    payments = extract_payment_details(emails)
    
    print(f'\n✓ Extracted details from {len(payments)} emails')
    
    # Export to CSV if requested
    if args.export_csv:
        import csv
        
        with open(args.export_csv, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'email_date', 'payment_amount', 'reserve_number',
                'customer_name', 'customer_email', 'card_brand', 'card_last4',
                'transaction_id', 'email_subject', 'email_from'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for p in payments:
                writer.writerow({
                    'email_date': p['email_date'].strftime('%Y-%m-%d %H:%M:%S'),
                    'payment_amount': p['payment_amount'] or '',
                    'reserve_number': p['reserve_number'] or '',
                    'customer_name': p['customer_name'] or '',
                    'customer_email': p['customer_email'] or '',
                    'card_brand': p['card_brand'] or '',
                    'card_last4': p['card_last4'] or '',
                    'transaction_id': p['transaction_id'] or '',
                    'email_subject': p['email_subject'],
                    'email_from': p['email_from']
                })
        
        print(f'\n✓ Exported to CSV: {args.export_csv}')
    
    # Save to database
    save_to_database(payments, dry_run=not args.write)
    
    print('\n' + '=' * 100)
    print('SCAN COMPLETE')
    print('=' * 100)

if __name__ == '__main__':
    main()
