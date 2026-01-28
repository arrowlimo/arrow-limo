#!/usr/bin/env python3
"""
Extract Interac e-Transfer receipts directly from Outlook (classic) via MAPI.

Requirements:
- Windows with Outlook desktop installed & configured for the target profile (default profile opened).
- pywin32 installed in the active virtual environment.

Output:
- l:/limo/reports/etransfer_emails.csv (same schema as IMAP/PST/EML extractors)

Usage:
  python scripts/extract_etransfers_from_outlook.py [--store "Mailbox - info@arrowlimo.ca"] [--since-days 365]
"""
import os
import re
import csv
import argparse
from datetime import datetime, timedelta

try:
    import win32com.client  # type: ignore
    from win32com.client import constants
except Exception as e:
    win32com = None


def parse_amount(text: str):
    m = re.search(r"\$?([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\.[0-9]{2}", text.replace("\u00a0"," "))
    if not m:
        return None
    try:
        return float(m.group(0).replace("$", "").replace(",", ""))
    except Exception:
        return None


def parse_interac_ref(text: str):
    # Match "Reference" or "Confirmation" as whole words, then a separator and an ID
    m = re.search(r"\b(reference|confirmation)\b[^A-Za-z0-9]{0,10}([A-Za-z0-9\-]{6,})", text, re.IGNORECASE)
    if not m:
        m2 = re.search(r"\b(\d{12})\b", text)
        if m2:
            return m2.group(1)
        return None
    return m.group(2)


def first4(alnum: str | None):
    if not alnum:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9]", "", alnum)
    return cleaned[:4].upper() if cleaned else None


def is_interac_like(subject: str, sender: str, body: str) -> bool:
    # Strong signals: subject mentions INTERAC e-Transfer, or sender includes interac domain
    subj = subject or ''
    snd = (sender or '').lower()
    subj_lower = subj.lower()
    strong_subject = (
        'interac e-transfer' in subj_lower or
        ("you've received an interac" in subj_lower and 'e-transfer' in subj_lower) or
        ('autodeposit' in subj_lower and 'interac' in subj_lower)
    )
    strong_sender = any(h in snd for h in ['@interac', 'payments.interac', 'no-reply@interac'])

    if strong_subject or strong_sender:
        return True

    # Body-based fallback must be very conservative to avoid marketing spam
    text = body or ''
    has_interac = re.search(r"\bINTERAC\b", text, re.IGNORECASE)
    has_etransfer = re.search(r"\be[- ]?transfer\b", text, re.IGNORECASE)
    has_autodeposit = re.search(r"\bauto[- ]?deposit\b", text, re.IGNORECASE)
    return bool(has_interac and (has_etransfer or has_autodeposit))


def is_deposit_confirmation(subject: str, body: str, include_claim: bool = False) -> bool:
    """Return True only for deposit confirmations, not requests/reminders/cancelled notices.
    Tight rules: require deposit language plus INTERAC context; exclude generic marketing.
    """
    subj = (subject or '').lower()
    text = f"{subject}\n{body}".lower()

    # Negative filters first
    negative = [
        'request', 'requested', 'money request', 'reminder', 'pending', 'cancelled', 'canceled', 'declined', 'expired',
        # 'sent you money' is excluded unless include_claim is True
    ]
    if any(n in text for n in negative):
        return False

    # Strong deposit phrases
    deposit_phrases = [
        'has been deposited', 'was deposited', 'deposited to', 'deposit complete', 'funds deposited',
        'has been automatically deposited', 'auto-deposit', 'autodeposit', 'deposit notification'
    ]
    has_deposit_phrase = any(p in text for p in deposit_phrases) or (' deposit ' in f" {subj} ")

    # Require clear INTERAC e-Transfer context in subject
    interac_subject = 'interac e-transfer' in subj or 'e-transfer' in subj

    if has_deposit_phrase and interac_subject:
        return True

    # Optional: include claim/awaiting-acceptance notifications (incoming funds not yet deposited)
    if include_claim:
        claim_signals = [
            'sent you', 'claim your deposit', 'your funds await', 'select your financial institution to deposit',
        ]
        if interac_subject and any(c in text for c in claim_signals):
            return True

    return False


def walk_folder(folder, since_dt, rows, seen_ids, seen_business, include_claim=False):
    try:
        items = folder.Items
        # Sort newest first and restrict by date for speed
        items.Sort("[ReceivedTime]", True)
        restriction = f"[ReceivedTime] >= '{since_dt.strftime('%m/%d/%Y %H:%M %p')}'"
        try:
            items = items.Restrict(restriction)
        except Exception:
            pass
        for item in items:
            try:
                # MailItem only
                subj = getattr(item, 'Subject', '') or ''
                sender = getattr(item, 'SenderEmailAddress', '') or ''
                btxt = ''
                try:
                    btxt = getattr(item, 'Body', '') or ''
                    if not btxt:
                        btxt = getattr(item, 'HTMLBody', '') or ''
                except Exception:
                    btxt = ''
                if not is_interac_like(subj, sender, btxt):
                    continue
                # Deposit-only filter to reduce duplicates
                if not is_deposit_confirmation(subj, btxt, include_claim=include_claim):
                    continue
                amt = parse_amount(btxt)
                ref = parse_interac_ref(btxt)
                code4 = first4(ref)
                recvd = getattr(item, 'ReceivedTime', None)
                try:
                    email_date = recvd.Format('%Y-%m-%dT%H:%M:%S') if recvd else datetime.utcnow().isoformat()
                except Exception:
                    email_date = datetime.utcnow().isoformat()
                # De-duplication: prefer message_id/entryid; fallback to (ref, amount, date)
                msg_id = getattr(item, 'InternetMessageID', '') or ''
                entry_id = str(getattr(item, 'EntryID', ''))
                day = (email_date[:10] if email_date else '')
                biz_key = (ref or '', f"{amt:.2f}" if isinstance(amt, (int, float)) and amt is not None else '', day)
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
                    'interac_ref': ref or '',
                    'code4': code4 or '',
                    'message_excerpt': (btxt[:250] if btxt else ''),
                    'message_id': msg_id,
                })
            except Exception:
                continue
    except Exception:
        pass

    # Recurse
    try:
        for sub in folder.Folders:
            walk_folder(sub, since_dt, rows, seen_ids, seen_business, include_claim=include_claim)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description='Extract Interac e-Transfers from Outlook MAPI')
    ap.add_argument('--store', help='Root store display name (default: scan all stores)')
    ap.add_argument('--since-days', type=int, default=365)
    ap.add_argument('--deposit-only', action='store_true', default=True, help='Only include deposit confirmations (recommended)')
    ap.add_argument('--include-claim', action='store_true', help='Also include claim/awaiting-acceptance notifications (incoming funds)')
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
    walk_folder(root_folder, since_dt, rows, seen_ids, seen_business, include_claim=args.include_claim)

    out = r"l:/limo/reports/etransfer_emails.csv"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', newline='', encoding='utf-8') as fp:
        if rows:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        else:
            fp.write('')
    print(f"Wrote {len(rows)} Interac email rows to {out}")


if __name__ == '__main__':
    main()
