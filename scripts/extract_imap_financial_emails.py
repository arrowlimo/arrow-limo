import imaplib
import email
import os
import json
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re

"""
IMAP Financial Email Extractor
---------------------------------
Pulls emails via IMAP and extracts financial-relevant messages:
- Interac e-transfer notifications
- Square payment notifications
- Banking/payment related emails

Outputs JSON compatible with link_owa_data.py (emails.items[] only).

Usage (PowerShell):
  $env:IMAP_PASS="SECRET"
  python -X utf8 scripts\extract_imap_financial_emails.py \
    --email info@arrowlimo.ca --username info@arrowlimo.ca --password-env IMAP_PASS \
    --host imap.ionos.com --days 3650 --output reports/imap_financial_emails.json
"""


def extract_reserve_numbers(text: str):
    if not text:
        return []
    pattern = r"\b(\d{6})\b"
    found = re.findall(pattern, text)
    valid = [r for r in found if not r.startswith((
        '403','587','780','825','111','222','333','444','555','666','777','888','999'
    ))]
    return list(set(valid))

def extract_money_amounts(text: str):
    if not text:
        return []
    pattern = r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"
    amounts = re.findall(pattern, text)
    return [float(a.replace(',', '')) for a in amounts]

def is_etransfer_email(subject, body):
    keywords = ['interac', 'e-transfer', 'etransfer', 'money transfer', 'autodeposit']
    text = (subject + ' ' + (body or '')).lower()
    return any(k in text for k in keywords)

def is_square_email(subject, body, sender):
    keywords = ['square', 'receipt', 'payment received']
    text = (subject + ' ' + (body or '') + ' ' + (sender or '')).lower()
    return any(k in text for k in keywords) or 'squareup.com' in (sender or '').lower()

def is_banking_email(subject, body, sender):
    keywords = ['bank', 'payment', 'deposit', 'withdrawal', 'transaction', 'cibc', 'td', 'rbc', 'scotiabank']
    text = (subject + ' ' + (body or '') + ' ' + (sender or '')).lower()
    return any(k in text for k in keywords)

def decode_str(value):
    if value is None:
        return ''
    try:
        parts = decode_header(value)
        decoded = ''
        for text, enc in parts:
            if isinstance(text, bytes):
                decoded += text.decode(enc or 'utf-8', errors='replace')
            else:
                decoded += text
        return decoded
    except Exception:
        return str(value)

def get_text_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = part.get('Content-Disposition','') or ''
            if ctype == 'text/plain' and 'attachment' not in disp.lower():
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                except Exception:
                    try:
                        return part.get_payload(decode=True).decode('utf-8', errors='replace')
                    except Exception:
                        continue
    else:
        if msg.get_content_type() == 'text/plain':
            try:
                return msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
            except Exception:
                return msg.get_payload()
    # Fallback: try text from first part even if HTML
    for part in msg.walk():
        if part.get_content_type() in ('text/html','text/plain'):
            try:
                return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
            except Exception:
                continue
    return ''

def imap_connect(host, username, password, port=993, starttls=False):
    if starttls:
        M = imaplib.IMAP4(host, port)
        M.starttls()
    else:
        M = imaplib.IMAP4_SSL(host, port)
    M.login(username, password)
    return M

def fetch_folder_items(M, folder, since_date):
    items = []
    try:
        typ, _ = M.select(folder)
        if typ != 'OK':
            return items
        # SINCE format: 17-Nov-2025
        criteria = f'(SINCE {since_date.strftime("%d-%b-%Y")})'
        typ, data = M.search(None, criteria)
        if typ != 'OK':
            return items
        ids = data[0].split()
        for i, msg_id in enumerate(ids, 1):
            typ, msg_data = M.fetch(msg_id, '(RFC822)')
            if typ != 'OK' or not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            try:
                msg = email.message_from_bytes(raw)
            except Exception:
                continue
            subject = decode_str(msg.get('Subject'))
            sender = decode_str(msg.get('From'))
            tos = decode_str(msg.get('To'))
            date_hdr = msg.get('Date')
            try:
                recvd_dt = parsedate_to_datetime(date_hdr).isoformat() if date_hdr else None
            except Exception:
                recvd_dt = None
            body = get_text_body(msg) or ''

            # Classification
            is_e = is_etransfer_email(subject, body)
            is_s = is_square_email(subject, body, sender)
            is_b = is_banking_email(subject, body, sender)

            all_text = subject + ' ' + body
            reserves = extract_reserve_numbers(all_text)
            amounts = extract_money_amounts(all_text)

            if is_e or is_s or is_b or reserves:
                items.append({
                    'subject': subject,
                    'from': sender,
                    'to': tos,
                    'received': recvd_dt,
                    'body': body[:5000],
                    'is_etransfer': is_e,
                    'is_square': is_s,
                    'is_banking': is_b,
                    'reserve_numbers': reserves,
                    'amounts': amounts,
                    'has_attachments': False
                })
    except Exception:
        pass
    return items

def main():
    import argparse
    p = argparse.ArgumentParser(description='Extract financial-relevant emails via IMAP')
    p.add_argument('--email', required=True, help='Mailbox email (info@arrowlimo.ca)')
    p.add_argument('--username', help='IMAP username; defaults to --email')
    p.add_argument('--password', help='Password/app password (discouraged; prefer env)')
    p.add_argument('--password-env', help='Env var name with password/app password')
    p.add_argument('--host', default='imap.ionos.com', help='IMAP host (default imap.ionos.com)')
    p.add_argument('--port', type=int, default=993, help='IMAP port (993 SSL or 143 STARTTLS)')
    p.add_argument('--starttls', action='store_true', help='Use STARTTLS on plain IMAP (port 143)')
    p.add_argument('--days', type=int, default=3650, help='How many days back to fetch')
    p.add_argument('--output', default='reports/imap_financial_emails.json', help='Output JSON path')
    p.add_argument('--folders', default='INBOX,Junk Email', help='Comma-separated folder names to scan')
    args = p.parse_args()

    username = args.username or args.email
    password = args.password or (args.password_env and os.getenv(args.password_env))
    if not password:
        import getpass
        password = getpass.getpass(f'IMAP password/app password for {username}: ')

    since = datetime.now() - timedelta(days=args.days)

    M = imap_connect(args.host, username, password, port=args.port, starttls=args.starttls)
    try:
        all_items = []
        for folder in [f.strip() for f in args.folders.split(',') if f.strip()]:
            items = fetch_folder_items(M, folder, since)
            all_items.extend(items)

        out = {
            'extracted_at': datetime.now().isoformat(),
            'email_account': args.email,
            'emails': {
                'count': len(all_items),
                'etransfer_count': sum(1 for x in all_items if x.get('is_etransfer')),
                'square_count': sum(1 for x in all_items if x.get('is_square')),
                'banking_count': sum(1 for x in all_items if x.get('is_banking')),
                'items': all_items
            }
        }

        os.makedirs(os.path.dirname(os.path.join(os.path.dirname(__file__), '..', args.output)), exist_ok=True)
        output_path = os.path.join(os.path.dirname(__file__), '..', args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"[OK] Saved {len(all_items)} relevant emails to {output_path}")
    finally:
        try:
            M.logout()
        except Exception:
            pass

if __name__ == '__main__':
    main()
