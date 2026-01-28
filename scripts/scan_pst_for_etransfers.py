#!/usr/bin/env python3
"""
Scan PST file using Outlook COM to extract INTERAC e-Transfer emails.
Requires Outlook installed on Windows and pywin32.

Usage:
  python scripts/scan_pst_for_etransfers.py --pst "l:/limo/outlook backup/info@arrowlimo.ca.pst"
"""
import os
import re
import csv
import argparse
from datetime import datetime

try:
    import win32com.client as win32client
except ImportError:
    print("ERROR: win32com not installed. Run: pip install pywin32")
    exit(1)

# E-transfer patterns
ETRANSFER_SUBJECTS = [
    r'INTERAC e-Transfer',
    r'Interac e-Transfer',
    r'e-Transfer',
    r'EMAIL TRANSFER',
    r'Email Money Transfer'
]

AMOUNT_RE = re.compile(r'\$\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2}))')
RECIPIENT_RE = re.compile(r'(?:sent you money|to|deposited)\s*\.?\s*([A-Z][A-Za-z\s\.&]+?)(?:\s+was|\s+sent|\s*$)', re.I)
REFERENCE_RE = re.compile(r'Reference Number:?\s*([A-Z0-9-]+)', re.I)

def is_etransfer_email(subject: str, sender: str) -> bool:
    """Check if email is an e-transfer notification."""
    if 'notify@payments.interac.ca' in sender.lower():
        return True
    
    subject_lower = subject.lower()
    for pattern in ETRANSFER_SUBJECTS:
        if re.search(pattern, subject_lower, re.I):
            return True
    
    return False

def parse_etransfer_details(subject: str, body: str, received_time):
    """Extract e-transfer details from email."""
    
    # Determine direction
    if 'sent you money' in subject.lower() or 'received' in subject.lower():
        direction = 'RECEIVED'
    elif 'deposited' in subject.lower() or 'you sent' in subject.lower():
        direction = 'SENT'
    else:
        direction = 'UNKNOWN'
    
    # Extract amount
    amounts = []
    for m in AMOUNT_RE.finditer(body):
        try:
            num = float(m.group(1).replace(',', ''))
            amounts.append(num)
        except:
            continue
    
    # Use body if no amounts in subject
    if not amounts:
        for m in AMOUNT_RE.finditer(subject):
            try:
                num = float(m.group(1).replace(',', ''))
                amounts.append(num)
            except:
                continue
    
    amount = amounts[0] if amounts else None
    
    # Extract recipient/sender name
    name = None
    
    # Pattern 1: "NAME sent you money"
    match = re.search(r'([A-Z][A-Za-z\s\.&]+?)\s+sent you money', subject, re.I)
    if match:
        name = match.group(1).strip()
    
    # Pattern 2: "to NAME was deposited"
    if not name:
        match = re.search(r'to\s+([A-Z][A-Za-z\s\.&]+?)\s+was deposited', subject, re.I)
        if match:
            name = match.group(1).strip()
    
    # Pattern 3: Look in body for "From: NAME" or "To: NAME"
    if not name:
        match = re.search(r'(?:From|To):\s*([A-Z][A-Za-z\s\.&]+)', body, re.I)
        if match:
            name = match.group(1).strip()
    
    # Extract reference number
    ref_match = REFERENCE_RE.search(body)
    reference = ref_match.group(1) if ref_match else None
    
    return {
        'direction': direction,
        'amount': amount,
        'name': name,
        'reference': reference,
        'date': received_time
    }

def walk_folder(folder, results: list, min_date=None, max_date=None):
    """Recursively walk folder looking for e-transfer emails."""
    
    try:
        items = folder.Items
        try:
            items.Sort("[ReceivedTime]", False)  # Newest first
        except:
            pass
        
        count = 0
        for item in items:
            try:
                if not hasattr(item, 'Subject'):
                    continue
                
                subject = item.Subject or ""
                sender = item.SenderEmailAddress or ""
                received_time = item.ReceivedTime
                
                # Skip if outside date range
                if min_date and received_time < min_date:
                    continue
                if max_date and received_time > max_date:
                    continue
                
                # Check if e-transfer
                if not is_etransfer_email(subject, sender):
                    continue
                
                # Extract body
                try:
                    body = item.Body or ""
                except:
                    body = ""
                
                # Parse details
                details = parse_etransfer_details(subject, body, received_time)
                
                results.append({
                    'email_date': received_time,
                    'subject': subject,
                    'from_email': sender,
                    'from_name': item.SenderName or "",
                    'direction': details['direction'],
                    'amount': details['amount'],
                    'name': details['name'],
                    'reference': details['reference'],
                    'body_excerpt': body[:200]
                })
                
                count += 1
                if count % 100 == 0:
                    print(f"  Found {count} e-transfers in {folder.Name}...")
            
            except Exception as e:
                continue
        
        if count > 0:
            print(f"  ✅ {folder.Name}: {count} e-transfers")
        
        # Recurse into subfolders
        for subfolder in folder.Folders:
            walk_folder(subfolder, results, min_date, max_date)
    
    except Exception as e:
        print(f"  ⚠️  Error scanning {folder.Name}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Scan PST for e-transfer emails")
    parser.add_argument('--pst', required=True, help='Path to PST file')
    parser.add_argument('--min-date', help='Min date YYYY-MM-DD (default: 2012-01-01)')
    parser.add_argument('--max-date', help='Max date YYYY-MM-DD (default: 2025-12-31)')
    parser.add_argument('--output', default='l:/limo/reports/etransfer_emails_full_scan.csv', 
                        help='Output CSV file')
    
    args = parser.parse_args()
    
    # Parse date range
    min_date = datetime.strptime(args.min_date, "%Y-%m-%d") if args.min_date else datetime(2012, 1, 1)
    max_date = datetime.strptime(args.max_date, "%Y-%m-%d") if args.max_date else datetime(2025, 12, 31)
    
    print("E-TRANSFER PST SCANNER")
    print("="*80)
    print(f"PST file: {args.pst}")
    print(f"Date range: {min_date.date()} to {max_date.date()}")
    print(f"Output: {args.output}")
    print()
    
    if not os.path.exists(args.pst):
        print(f"ERROR: PST file not found: {args.pst}")
        return 1
    
    print("Starting Outlook COM...")
    outlook = win32client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    
    print(f"Opening PST file...")
    try:
        outlook.AddStore(args.pst)
    except Exception as e:
        print(f"ERROR: Could not open PST: {e}")
        return 1
    
    # Find the PST store
    pst_store = None
    for store in outlook.Stores:
        if args.pst.lower() in store.FilePath.lower():
            pst_store = store
            break
    
    if not pst_store:
        print("ERROR: Could not find PST store")
        return 1
    
    print(f"Scanning: {pst_store.DisplayName}")
    print()
    
    results = []
    
    # Walk all folders
    root_folder = pst_store.GetRootFolder()
    walk_folder(root_folder, results, min_date, max_date)
    
    print()
    print(f"="*80)
    print(f"FOUND {len(results)} e-transfer emails")
    print(f"="*80)
    
    if results:
        # Show summary
        received = [r for r in results if r['direction'] == 'RECEIVED']
        sent = [r for r in results if r['direction'] == 'SENT']
        unknown = [r for r in results if r['direction'] == 'UNKNOWN']
        
        print(f"\nDirection breakdown:")
        print(f"  RECEIVED: {len(received)} transfers")
        print(f"  SENT: {len(sent)} transfers")
        print(f"  UNKNOWN: {len(unknown)} transfers")
        
        # Date range
        dates = [r['email_date'] for r in results]
        print(f"\nDate range found:")
        print(f"  {min(dates).date()} to {max(dates).date()}")
        
        # Write to CSV
        print(f"\nWriting to {args.output}...")
        with open(args.output, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'email_date', 'subject', 'from_email', 'from_name', 
                'direction', 'amount', 'name', 'reference', 'body_excerpt'
            ])
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ Saved {len(results)} e-transfers to {args.output}")
    
    # Close PST
    try:
        outlook.RemoveStore(root_folder)
    except:
        pass
    
    return 0

if __name__ == '__main__':
    exit(main())
