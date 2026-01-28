#!/usr/bin/env python3
"""
Scan Outlook PST for Square Capital Loan Emails

Searches for emails related to:
- Square Capital loan approvals
- Square Capital payment confirmations
- Square Capital loan statements
- Square Capital balance updates
"""

import os
import sys
import win32com.client
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

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

def scan_pst_for_square_capital():
    """Scan PST file for Square Capital emails."""
    
    print('=' * 100)
    print('SCANNING OUTLOOK PST FOR SQUARE CAPITAL EMAILS')
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
    
    # Search keywords for Square Capital
    keywords = [
        'square capital',
        'capital loan',
        'CAP1622',
        'CAP9152',
        'capital advance',
        'repayment',
        'capital payment',
        'loan approved',
        'capital offer',
        'capital balance'
    ]
    
    capital_emails = []
    
    def search_folder(folder, depth=0):
        """Recursively search folder for Square Capital emails."""
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
                    
                    # Check for Square Capital keywords
                    combined_text = f'{subject} {body} {sender}'.lower()
                    
                    if any(kw in combined_text for kw in keywords):
                        received_time = item.ReceivedTime
                        
                        capital_emails.append({
                            'date': received_time,
                            'from': sender,
                            'subject': subject,
                            'body': body[:2000],  # First 2000 chars
                            'folder': folder_name
                        })
                        
                        count += 1
                        print(f'{indent}  ✓ Found: {received_time} | {subject[:60]}')
                
                except Exception as e:
                    continue
            
            if count > 0:
                print(f'{indent}  → Found {count} Capital emails in {folder_name}')
            
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
    
    return capital_emails

def extract_loan_details(emails):
    """Extract loan details from email content."""
    
    print('\n' + '=' * 100)
    print('EXTRACTING LOAN DETAILS')
    print('=' * 100)
    
    loan_details = []
    
    for email in sorted(emails, key=lambda x: x['date']):
        body = email['body'].lower()
        subject = email['subject'].lower()
        combined = f'{subject} {body}'
        
        # Look for loan IDs
        loan_id = None
        if 'cap1622' in combined:
            loan_id = 'CAP1622'
        elif 'cap9152' in combined:
            loan_id = 'CAP9152'
        
        # Look for amounts
        import re
        
        # Pattern for dollar amounts
        amount_pattern = r'\$[\d,]+\.?\d*'
        amounts = re.findall(amount_pattern, combined)
        
        # Look for payment/balance keywords
        is_payment = any(word in combined for word in [
            'payment', 'repayment', 'deducted', 'withheld', 'paid'
        ])
        
        is_balance = any(word in combined for word in [
            'balance', 'remaining', 'outstanding', 'owed'
        ])
        
        is_approval = any(word in combined for word in [
            'approved', 'offer', 'advance', 'deposit', 'funded'
        ])
        
        detail = {
            'date': email['date'],
            'subject': email['subject'],
            'loan_id': loan_id,
            'amounts': amounts,
            'is_payment': is_payment,
            'is_balance': is_balance,
            'is_approval': is_approval,
            'folder': email['folder']
        }
        
        loan_details.append(detail)
        
        print(f"\n{email['date'].strftime('%Y-%m-%d')} | {email['subject'][:80]}")
        if loan_id:
            print(f"  Loan: {loan_id}")
        if amounts:
            print(f"  Amounts: {', '.join(amounts[:5])}")
        if is_payment:
            print(f"  Type: PAYMENT")
        elif is_balance:
            print(f"  Type: BALANCE")
        elif is_approval:
            print(f"  Type: APPROVAL")
    
    return loan_details

def save_to_database(emails):
    """Save Capital emails to database."""
    
    print('\n' + '=' * 100)
    print('SAVING TO DATABASE')
    print('=' * 100)
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    # Create table if needed
    cur.execute("""
        CREATE TABLE IF NOT EXISTS square_capital_emails (
            id SERIAL PRIMARY KEY,
            email_date TIMESTAMP NOT NULL,
            sender VARCHAR(500),
            subject TEXT,
            body TEXT,
            folder_name VARCHAR(200),
            loan_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    inserted = 0
    for email in emails:
        # Check if already exists
        cur.execute("""
            SELECT id FROM square_capital_emails 
            WHERE email_date = %s AND subject = %s
        """, (email['date'], email['subject']))
        
        if cur.fetchone():
            continue
        
        cur.execute("""
            INSERT INTO square_capital_emails 
            (email_date, sender, subject, body, folder_name)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            email['date'],
            email['from'],
            email['subject'],
            email['body'],
            email['folder']
        ))
        
        inserted += 1
    
    conn.commit()
    
    print(f'\n✓ Inserted {inserted} new emails')
    print(f'  Total in database: {len(emails)}')
    
    cur.close()
    conn.close()

def main():
    print('\nStarting Square Capital email scan...\n')
    
    # Scan PST
    emails = scan_pst_for_square_capital()
    
    if not emails:
        print('\n[FAIL] No Square Capital emails found')
        return
    
    print(f'\n✓ Found {len(emails)} Square Capital emails')
    
    # Extract loan details
    details = extract_loan_details(emails)
    
    # Save to database
    save_to_database(emails)
    
    # Summary
    print('\n' + '=' * 100)
    print('SUMMARY')
    print('=' * 100)
    
    print(f'\nTotal Capital Emails: {len(emails)}')
    
    # Group by loan
    cap1622_count = sum(1 for d in details if d['loan_id'] == 'CAP1622')
    cap9152_count = sum(1 for d in details if d['loan_id'] == 'CAP9152')
    other_count = sum(1 for d in details if not d['loan_id'])
    
    print(f'  CAP1622 emails: {cap1622_count}')
    print(f'  CAP9152 emails: {cap9152_count}')
    print(f'  Other/General: {other_count}')
    
    # Group by type
    payment_emails = sum(1 for d in details if d['is_payment'])
    balance_emails = sum(1 for d in details if d['is_balance'])
    approval_emails = sum(1 for d in details if d['is_approval'])
    
    print(f'\n  Payment emails: {payment_emails}')
    print(f'  Balance emails: {balance_emails}')
    print(f'  Approval emails: {approval_emails}')
    
    # Date range
    if emails:
        dates = [e['date'] for e in emails]
        min_date = min(dates)
        max_date = max(dates)
        print(f'\n  Date range: {min_date.strftime("%Y-%m-%d")} to {max_date.strftime("%Y-%m-%d")}')
    
    print('\n✓ Scan complete - check database table: square_capital_emails')

if __name__ == '__main__':
    main()
