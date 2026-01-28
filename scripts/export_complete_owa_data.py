import getpass
import json
import os
from datetime import datetime, timedelta
import re

"""
Complete OWA Data Extraction
-----------------------------
Extracts all calendar events and emails from OWA, with focus on:
- Calendar appointments with reserve numbers
- Interac e-transfer emails
- Square payment notifications
- Banking/payment related emails

Tries multiple server configurations:
1. 1.exchange.1and1.us (primary from OWA URL)
2. exchange2019.ionos.com (alternative)

Usage:
  python -X utf8 scripts/export_complete_owa_data.py --email info@arrowlimo.ca --days 3650
"""

def extract_reserve_numbers(text):
    """Extract 6-digit reserve numbers from text."""
    if not text:
        return []
    pattern = r'\b(\d{6})\b'
    found = re.findall(pattern, text)
    # Filter out obvious non-reserve numbers
    valid = [r for r in found if not r.startswith(('403', '587', '780', '825', '111', '222', '333', '444', '555', '666', '777', '888', '999'))]
    return list(set(valid))

def extract_money_amounts(text):
    """Extract dollar amounts from text."""
    if not text:
        return []
    pattern = r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
    amounts = re.findall(pattern, text)
    return [float(a.replace(',', '')) for a in amounts]

def is_etransfer_email(subject, body):
    """Detect Interac e-transfer emails."""
    keywords = ['interac', 'e-transfer', 'etransfer', 'money transfer', 'autodeposit']
    text = (subject + ' ' + (body or '')).lower()
    return any(k in text for k in keywords)

def is_square_email(subject, body, sender):
    """Detect Square payment emails."""
    keywords = ['square', 'receipt', 'payment received']
    text = (subject + ' ' + (body or '') + ' ' + (sender or '')).lower()
    return any(k in text for k in keywords) or 'squareup.com' in (sender or '').lower()

def is_banking_email(subject, body, sender):
    """Detect banking/payment related emails."""
    keywords = ['bank', 'payment', 'deposit', 'withdrawal', 'transaction', 'cibc', 'td', 'rbc', 'scotiabank']
    text = (subject + ' ' + (body or '') + ' ' + (sender or '')).lower()
    return any(k in text for k in keywords)

def try_connect(email, password, server):
    """Try to connect to Exchange server."""
    try:
        from exchangelib import Credentials, Account, Configuration, DELEGATE
        
        print(f"  Trying server: {server}")
        
        credentials = Credentials(username=email, password=password)
        config = Configuration(server=server, credentials=credentials)
        
        account = Account(
            primary_smtp_address=email,
            config=config,
            autodiscover=False,
            access_type=DELEGATE
        )
        
        # Test connection
        _ = account.root
        
        print(f"  [OK] Connected to {server}")
        return account
        
    except Exception as e:
        print(f"  [FAIL] Failed: {str(e)[:100]}")
        return None

def export_complete_data(email, output_path, days_back=3650, password=None, password_env=None, username=None, auth=None, ews_url=None):
    """Export all calendar and email data from OWA.

    password: direct password string (discouraged unless using app password)
    password_env: name of environment variable containing password/app password
    If neither provided, falls back to interactive getpass prompt.
    """
    
    try:
        from exchangelib import Credentials, Account, Configuration, DELEGATE, FolderCollection
        from exchangelib.folders import Calendar, Inbox
    except ImportError:
        print("ERROR: exchangelib not installed")
        print("Install with: pip install exchangelib")
        return False
    
    # Resolve password precedence: explicit string > env var > interactive prompt
    resolved_password = None
    if password:
        resolved_password = password
    elif password_env:
        env_val = os.getenv(password_env)
        if not env_val:
            print(f"WARNING: Environment variable '{password_env}' not set; falling back to interactive prompt.")
        else:
            resolved_password = env_val
    if not resolved_password:
        resolved_password = getpass.getpass(f"Enter password/app password for {email}: ")
    password = resolved_password
    
    # Try multiple servers
    # Allow explicit server override via environment or CLI later
    servers = [
        os.getenv('EXCHANGE_SERVER_OVERRIDE') or '',  # optional override
        '1.exchange.1and1.us',               # observed OWA host pattern
        'exchange2019.ionos.com',            # alternative ionos naming
        'exchange.ionos.com',                # generic ionos exchange
        'outlook.office365.com'              # Microsoft 365 (in case account migrated)
    ]
    # Remove empty entries
    servers = [s for s in servers if s]
    
    account = None
    print(f"Connecting to Exchange for {email}...")
    
    # If direct EWS URL provided, attempt that first
    if ews_url:
        try:
            from exchangelib import Credentials, Account, Configuration, DELEGATE, BaseProtocol
            if auth:
                BaseProtocol.DEFAULT_AUTH_TYPE = auth
            creds_obj = Credentials(username=username or email, password=password)
            print(f"Trying direct EWS URL: {ews_url}")
            config = Configuration(service_endpoint=ews_url, credentials=creds_obj)
            account = Account(primary_smtp_address=email, config=config, autodiscover=False, access_type=DELEGATE)
            _ = account.root
            print(f"  [OK] Connected via direct EWS URL")
        except Exception as e:
            print(f"  [FAIL] Direct EWS URL failed: {str(e)[:120]}")
            account = None

    if not account:
        for server in servers:
            # username override support
            if auth:
                try:
                    from exchangelib import BaseProtocol
                    BaseProtocol.DEFAULT_AUTH_TYPE = auth
                except Exception:
                    pass
            account = try_connect(username or email, password, server)
            if account:
                break
    
    # If all direct servers failed, attempt autodiscover as last resort
    if not account:
        try:
            from exchangelib import Credentials, Account, DELEGATE
            print("Attempting fallback autodiscover...")
            credentials = Credentials(username=email, password=password)
            account = Account(primary_smtp_address=email, credentials=credentials, autodiscover=True, access_type=DELEGATE)
            print("  [OK] Autodiscover succeeded")
        except Exception as e:
            print(f"  [FAIL] Autodiscover failed: {str(e)[:120]}")
    
    if not account:
        print("\n[FAIL] Could not connect to any Exchange server")
        print("Tried servers:", ', '.join(servers))
        return False
    
    try:
        # Date range
        from exchangelib import UTC, EWSDateTime
        end_date_naive = datetime.now()
        start_date_naive = end_date_naive - timedelta(days=days_back)
        # Make timezone-aware (UTC) using EWSDateTime
        end_date = EWSDateTime.from_datetime(end_date_naive.replace(tzinfo=UTC))
        start_date = EWSDateTime.from_datetime(start_date_naive.replace(tzinfo=UTC))
        
        print(f"\nFetching data from {start_date.date()} to {end_date.date()}...")
        
        # ====================
        # CALENDAR EXTRACTION
        # ====================
        print("\n📅 Extracting calendar events...")
        # Use start/end inclusive filter; ensure fields are UTC aware
        calendar_items = account.calendar.filter(
            start__gte=start_date,
            end__lte=end_date
        ).order_by('-start')
        
        calendar_events = []
        for idx, item in enumerate(calendar_items, 1):
            if idx % 50 == 0:
                print(f"  Calendar: {idx} events processed...")
            
            all_text = ' '.join(filter(None, [
                str(item.subject) if item.subject else '',
                str(item.location) if item.location else '',
                str(item.text_body) if item.text_body else ''
            ]))
            
            event_data = {
                'subject': str(item.subject) if item.subject else '',
                'location': str(item.location) if item.location else '',
                'body': str(item.text_body)[:2000] if item.text_body else '',
                'start': item.start.isoformat() if item.start else None,
                'end': item.end.isoformat() if item.end else None,
                'is_all_day': item.is_all_day if hasattr(item, 'is_all_day') else False,
                'categories': ', '.join(item.categories) if item.categories else '',
                'organizer': str(item.organizer) if hasattr(item, 'organizer') and item.organizer else '',
                'reserve_numbers': extract_reserve_numbers(all_text),
                'amounts': extract_money_amounts(all_text)
            }
            
            calendar_events.append(event_data)
        
        print(f"  [OK] Extracted {len(calendar_events)} calendar events")
        
        # ====================
        # EMAIL EXTRACTION
        # ====================
        print("\n📧 Extracting emails...")
        
        # Get inbox items
        inbox_items = account.inbox.filter(
            datetime_received__gte=start_date
        ).order_by('-datetime_received')
        
        emails = []
        etransfer_count = 0
        square_count = 0
        banking_count = 0
        
        for idx, item in enumerate(inbox_items, 1):
            if idx % 100 == 0:
                print(f"  Emails: {idx} processed...")
            
            subject = str(item.subject) if item.subject else ''
            body = str(item.text_body)[:5000] if item.text_body else ''
            sender = str(item.sender.email_address) if item.sender else ''
            
            # Check if financial email
            is_etransfer = is_etransfer_email(subject, body)
            is_square = is_square_email(subject, body, sender)
            is_banking = is_banking_email(subject, body, sender)
            
            if is_etransfer:
                etransfer_count += 1
            if is_square:
                square_count += 1
            if is_banking:
                banking_count += 1
            
            # Extract financial data
            all_text = subject + ' ' + body
            reserve_numbers = extract_reserve_numbers(all_text)
            amounts = extract_money_amounts(all_text)
            
            email_data = {
                'subject': subject,
                'from': sender,
                'to': ', '.join([str(r.email_address) for r in item.to_recipients]) if item.to_recipients else '',
                'received': item.datetime_received.isoformat() if item.datetime_received else None,
                'body': body,
                'is_etransfer': is_etransfer,
                'is_square': is_square,
                'is_banking': is_banking,
                'reserve_numbers': reserve_numbers,
                'amounts': amounts,
                'has_attachments': item.has_attachments if hasattr(item, 'has_attachments') else False
            }
            
            # Only store financial emails or emails with reserve numbers
            if is_etransfer or is_square or is_banking or reserve_numbers:
                emails.append(email_data)
        
        print(f"  [OK] Extracted {len(emails)} financial/relevant emails")
        print(f"     - E-transfers: {etransfer_count}")
        print(f"     - Square payments: {square_count}")
        print(f"     - Banking emails: {banking_count}")
        
        # ====================
        # SAVE TO JSON
        # ====================
        output_data = {
            'extracted_at': datetime.now().isoformat(),
            'email_account': email,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'calendar': {
                'count': len(calendar_events),
                'events_with_reserve_numbers': len([e for e in calendar_events if e['reserve_numbers']]),
                'events': calendar_events
            },
            'emails': {
                'count': len(emails),
                'etransfer_count': etransfer_count,
                'square_count': square_count,
                'banking_count': banking_count,
                'items': emails
            }
        }
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Successfully exported all OWA data")
        print(f"📄 Output: {output_path}")
        print(f"\n📊 Summary:")
        print(f"   Calendar events: {len(calendar_events)}")
        print(f"   - With reserve numbers: {len([e for e in calendar_events if e['reserve_numbers']])}")
        print(f"   Financial emails: {len(emails)}")
        print(f"   - E-transfers: {etransfer_count}")
        print(f"   - Square: {square_count}")
        print(f"   - Banking: {banking_count}")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Export complete OWA data (calendar + emails)')
    parser.add_argument('--email', default='info@arrowlimo.ca', help='Email address')
    parser.add_argument('--output', default='reports/owa_complete_export.json', help='Output JSON file')
    parser.add_argument('--days', type=int, default=3650, help='Days back to fetch')
    parser.add_argument('--password', help='Password or app password (optional; prefer using --password-env)')
    parser.add_argument('--password-env', help='Name of environment variable holding password/app password')
    parser.add_argument('--debug', action='store_true', help='Enable exchangelib debug logging')
    parser.add_argument('--username', help='Explicit auth username or DOMAIN\\user for on-prem Exchange')
    parser.add_argument('--auth', choices=['BASIC','NTLM','OAUTH2','GSSAPI','NOAUTH'], help='Force specific auth type')
    parser.add_argument('--ews-url', help='Direct EWS endpoint (https://host/EWS/Exchange.asmx)')
    
    args = parser.parse_args()
    
    output_path = os.path.join(os.path.dirname(__file__), '..', args.output)
    
    if args.debug:
        try:
            import logging
            logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
            # reduce requests noise if overwhelming later
        except Exception:
            print('WARNING: Could not initialize debug logging')

    success = export_complete_data(
        args.email,
        output_path,
        args.days,
        password=args.password,
        password_env=args.password_env,
        username=args.username,
        auth=args.auth,
        ews_url=args.ews_url
    )
    
    if not success:
        exit(1)

if __name__ == '__main__':
    main()
