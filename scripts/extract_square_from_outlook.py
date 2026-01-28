#!/usr/bin/env python3
"""
Extract Square-related emails from Outlook (classic) via MAPI:
- Payouts: "Square has sent you $X"
- Payments received: "$X Payment" or "payment received"
- Loan payments: "Square loan payment summary" with amount

Output CSV: l:/limo/reports/square_emails.csv
Columns: uid,email_date,subject,from_email,from_name,amount,currency,type,message_excerpt,message_id

Usage:
  python scripts/extract_square_from_outlook.py [--store "Mailbox - info@arrowlimo.ca"] [--since-days 120]
"""
import os
import re
import csv
import argparse
from datetime import datetime, timedelta

try:
    import win32com.client  # type: ignore
except Exception:
    win32com = None


def parse_amount(text: str):
    m = re.search(r"\$?([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\.[0-9]{2}", text.replace("\u00a0"," "))
    if not m:
        return None
    try:
        return float(m.group(0).replace("$", "").replace(",", ""))
    except Exception:
        return None


def classify_type(subject: str, body: str) -> str | None:
    s = (subject or '').lower()
    b = (body or '').lower()
    if 'has sent you' in s and 'square' in s:
        return 'payout'
    if 'loan payment' in s and 'square' in s:
        return 'loan_payment'
    if 'payment received' in s or re.search(r"\$\s*\d[\d,]*\.\d{2}\s*payment", subject or '', re.I):
        return 'payment_received'
    # Refunds: require explicit 'refund' word, not 'returns'. Also require square context.
    if (re.search(r"\brefund(?:ed)?\b", s) and 'square' in s) or (re.search(r"\brefund(?:ed)?\b", b) and 'square' in b):
        return 'refund'
    # Fallback patterns in body
    if 'your automatic transfer' in b and 'square' in b:
        return 'payout'
    return None


def is_square_sender(sender: str) -> bool:
    s = (sender or '').lower()
    return any(x in s for x in ['@squareup.com', '@messaging.squareup.com'])


def walk_folder(folder, since_dt, rows, seen_ids, seen_business):
    try:
        items = folder.Items
        items.Sort("[ReceivedTime]", True)
        restriction = f"[ReceivedTime] >= '{since_dt.strftime('%m/%d/%Y %H:%M %p')}'"
        try:
            items = items.Restrict(restriction)
        except Exception:
            pass
        for item in items:
            try:
                subj = getattr(item, 'Subject', '') or ''
                sender = getattr(item, 'SenderEmailAddress', '') or ''
                if not is_square_sender(sender) and 'square' not in (subj.lower()):
                    continue
                body = ''
                try:
                    body = getattr(item, 'Body', '') or ''
                    if not body:
                        body = getattr(item, 'HTMLBody', '') or ''
                except Exception:
                    body = ''
                typ = classify_type(subj, body)
                if not typ:
                    continue
                amt = parse_amount(body) or parse_amount(subj)  # subject sometimes contains amount
                recvd = getattr(item, 'ReceivedTime', None)
                try:
                    email_date = recvd.Format('%Y-%m-%dT%H:%M:%S') if recvd else datetime.utcnow().isoformat()
                except Exception:
                    email_date = datetime.utcnow().isoformat()
                msg_id = getattr(item, 'InternetMessageID', '') or ''
                entry_id = str(getattr(item, 'EntryID', ''))
                day = (email_date[:10] if email_date else '')
                biz_key = (typ, f"{amt:.2f}" if isinstance(amt, (int, float)) and amt is not None else '', day)
                id_key = msg_id or entry_id
                if id_key and id_key in seen_ids:
                    continue
                if not id_key and biz_key in seen_business:
                    continue
                if id_key:
                    seen_ids.add(id_key)
                else:
                    seen_business.add(biz_key)
                rows.append({
                    'uid': entry_id,
                    'email_date': email_date,
                    'subject': subj,
                    'from_email': sender,
                    'from_name': getattr(item, 'SenderName', '') or '',
                    'amount': amt if amt is not None else '',
                    'currency': 'CAD',
                    'type': typ,
                    'message_excerpt': (body[:250] if body else ''),
                    'message_id': msg_id,
                })
            except Exception:
                continue
    except Exception:
        pass
    try:
        for sub in folder.Folders:
            walk_folder(sub, since_dt, rows, seen_ids, seen_business)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description='Extract Square-related emails (payouts, payments, loan payments)')
    ap.add_argument('--store', help='Root store display name (default: scan all stores)')
    ap.add_argument('--since-days', type=int, default=120)
    args = ap.parse_args()

    if win32com is None:
        print('pywin32 is not installed. Please install it in the virtualenv.')
        return

    outlook = win32com.client.Dispatch('Outlook.Application')
    ns = outlook.GetNamespace('MAPI')
    since_dt = datetime.utcnow() - timedelta(days=args.since_days)

    rows = []
    seen_ids = set()
    seen_business = set()

    stores = ns.Stores
    for i in range(1, stores.Count+1):
        store = stores.Item(i)
        try:
            display = store.DisplayName
        except Exception:
            display = ''
        if args.store and args.store.lower() not in (display or '').lower():
            continue
        root_folder = store.GetRootFolder()
        walk_folder(root_folder, since_dt, rows, seen_ids, seen_business)

    out = r"l:/limo/reports/square_emails.csv"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', newline='', encoding='utf-8') as fp:
        if rows:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        else:
            fp.write('')
    print(f"Wrote {len(rows)} Square email rows to {out}")


if __name__ == '__main__':
    main()
