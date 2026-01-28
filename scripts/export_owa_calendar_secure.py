import getpass
import json
import os
from datetime import datetime, timedelta
import re

"""
Secure OWA Calendar Export via EWS
----------------------------------
This script connects to Exchange Online using the exchangelib library
and exports calendar events to JSON format.

SECURITY FEATURES:
- Interactive password prompt (no hardcoded credentials)
- Uses secure connection (HTTPS)
- Credentials never written to disk

Prerequisites:
  pip install exchangelib

Usage:
  python -X utf8 scripts/export_owa_calendar_secure.py [--email EMAIL] [--output PATH] [--days DAYS]
  
  The script will prompt for password securely (not echoed to screen)

Example:
  python -X utf8 scripts/export_owa_calendar_secure.py --email info@arrowlimo.ca --days 3650
"""

def extract_reserve_numbers(text):
    """Extract 6-digit reserve numbers from text."""
    if not text:
        return []
    pattern = r'\b(\d{6})\b'
    found = re.findall(pattern, text)
    # Filter out obvious non-reserve numbers (phone area codes, etc)
    valid = [r for r in found if not r.startswith(('403', '587', '780', '825'))]
    return list(set(valid))

def export_calendar(email, output_path, days_back=3650):
    """Export calendar events from OWA via EWS."""
    
    try:
        from exchangelib import Credentials, Account, Configuration, DELEGATE
        from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
        
        # Disable SSL verification warnings for self-signed certs if needed
        # BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter
        
    except ImportError:
        print("ERROR: exchangelib not installed")
        print("Install with: pip install exchangelib")
        return False
    
    # Get password securely
    password = getpass.getpass(f"Enter password for {email}: ")
    
    try:
        print(f"Connecting to Exchange Online for {email}...")
        
        # Create credentials
        credentials = Credentials(username=email, password=password)
        
        # Extract server from email domain
        server = '1.exchange.1and1.us'  # From the OWA URL in screenshot
        
        print(f"Connecting to server: {server}")
        
        # Manual configuration
        config = Configuration(
            server=server,
            credentials=credentials
        )
        
        account = Account(
            primary_smtp_address=email,
            config=config,
            autodiscover=False,
            access_type=DELEGATE
        )
        
        print(f"[OK] Connected successfully!")
        print(f"Fetching calendar events from last {days_back} days...")
        
        # Date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Fetch calendar items
        calendar_items = account.calendar.filter(
            start__gte=start_date,
            end__lte=end_date
        ).order_by('-start')
        
        events = []
        count = 0
        
        for item in calendar_items:
            count += 1
            if count % 100 == 0:
                print(f"  Processed {count} events...")
            
            # Extract all text for reserve number search
            all_text = ' '.join(filter(None, [
                str(item.subject) if item.subject else '',
                str(item.location) if item.location else '',
                str(item.text_body) if item.text_body else ''
            ]))
            
            reserve_numbers = extract_reserve_numbers(all_text)
            
            event_data = {
                'subject': str(item.subject) if item.subject else '',
                'location': str(item.location) if item.location else '',
                'body': str(item.text_body)[:1000] if item.text_body else '',  # Truncate long bodies
                'start': item.start.isoformat() if item.start else None,
                'end': item.end.isoformat() if item.end else None,
                'is_all_day': item.is_all_day if hasattr(item, 'is_all_day') else False,
                'categories': ', '.join(item.categories) if item.categories else '',
                'organizer': str(item.organizer) if hasattr(item, 'organizer') and item.organizer else '',
                'required_attendees': [str(a) for a in item.required_attendees] if hasattr(item, 'required_attendees') and item.required_attendees else [],
                'reserve_numbers': reserve_numbers
            }
            
            events.append(event_data)
        
        # Save to JSON
        output_data = {
            'calendar': email,
            'exported_at': datetime.now().isoformat(),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'count': len(events),
            'events': events
        }
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Successfully exported {len(events)} calendar events")
        print(f"📄 Output: {output_path}")
        print(f"📊 Found {len([e for e in events if e['reserve_numbers']])} events with reserve numbers")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        print("\nTroubleshooting:")
        print("1. Verify email address is correct")
        print("2. Verify password is correct")
        print("3. Check if MFA/2FA is enabled (may need app password)")
        print("4. Ensure account has calendar access")
        print("5. Check firewall/network connectivity")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Export calendar from OWA securely')
    parser.add_argument('--email', default='info@arrowlimo.ca', help='Email address')
    parser.add_argument('--output', default='reports/owa_calendar_events.json', help='Output JSON file')
    parser.add_argument('--days', type=int, default=3650, help='Days back to fetch (default: 3650 = 10 years)')
    
    args = parser.parse_args()
    
    output_path = os.path.join(os.path.dirname(__file__), '..', args.output)
    
    success = export_calendar(args.email, output_path, args.days)
    
    if not success:
        exit(1)

if __name__ == '__main__':
    main()
