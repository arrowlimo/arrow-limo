#!/usr/bin/env python3
"""
Fetch Interac e-Transfer receipt emails via IMAP and extract linking details.

Supports IONOS/1&1 Exchange or any IMAP server. Reads credentials from environment
variables and writes a normalized CSV:

  l:/limo/reports/etransfer_emails.csv

Columns:
- uid, email_date, subject, from_email, from_name, amount, currency, interac_ref,
  code4, message_excerpt, message_id

Environment (.env):
- IMAP_HOST (e.g., imap.ionos.com)
- IMAP_PORT (default 993)
- IMAP_USER
- IMAP_PASSWORD
- IMAP_FOLDER (default "INBOX")
- IMAP_SINCE_DAYS (default 365)  # lookback window

Filtering:
- Searches for likely Interac receipts by SUBJECT and FROM patterns.
  You can widen patterns by setting ETRANSFER_SUBJECT_HINTS / ETRANSFER_FROM_HINTS
  as comma-separated lists.
"""
import os
import re
import imaplib
import email
from email.header import decode_header, make_header
from email.message import Message
from email import utils as email_utils
from datetime import datetime, timedelta
import csv
from dotenv import load_dotenv


def env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


def decode_str(s):
    if s is None:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return str(s)


def parse_amount(text: str):
    # Find amounts like $1,234.56 or 1234.56
    m = re.search(r"\$?([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\.[0-9]{2}", text.replace("\u00a0"," "))
    if not m:
        return None
    try:
        return float(m.group(0).replace("$", "").replace(",", ""))
    except Exception:
        return None


def parse_interac_ref(text: str):
    # Interac confirmation/reference numbers appear in different forms; capture alnum tokens around 'reference'
    m = re.search(r"(reference|confirmation)[^\w]{0,10}([A-Za-z0-9\-]{6,})", text, re.IGNORECASE)
    if not m:
        # Sometimes 12-digit numeric ref embedded
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


def extract_text(msg: Message) -> str:
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    parts.append(payload.decode(charset, errors="replace"))
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))
        except Exception:
            pass
    # Merge, strip HTML tags crudely
    text = "\n\n".join(parts)
    # Remove basic HTML
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()

    host = os.getenv("IMAP_HOST", "")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER", "")
    pwd = os.getenv("IMAP_PASSWORD", "")
    folder = os.getenv("IMAP_FOLDER", "INBOX")
    since_days = int(os.getenv("IMAP_SINCE_DAYS", "365"))

    subj_hints = env_list("ETRANSFER_SUBJECT_HINTS", [
        "INTERAC e-Transfer",
        "You've received an INTERAC e-Transfer",
        "Autodeposit",
        "Money transfer",
        "Money request fulfilled",
        "You received a money transfer",
    ])
    from_hints = env_list("ETRANSFER_FROM_HINTS", [
        "interac",
        "payments.interac",
        "notify@",
        "etransfer",
        "no-reply@interac",
    ])

    if not host or not user or not pwd:
        print("Missing IMAP_HOST/IMAP_USER/IMAP_PASSWORD in environment; cannot fetch emails.")
        return

    cutoff = (datetime.utcnow() - timedelta(days=since_days)).strftime('%d-%b-%Y')
    os.makedirs('l:/limo/reports', exist_ok=True)

    with imaplib.IMAP4_SSL(host, port) as M:
        M.login(user, pwd)
        M.select(folder)
        # Search recent messages
        status, data = M.search(None, 'SINCE', cutoff)
        if status != 'OK':
            print('IMAP search failed:', status)
            return
        uids = data[0].split()
        print(f"Scanning {len(uids)} messages since {cutoff} ...")

        rows = []
        for uid in reversed(uids):  # newest first
            try:
                status, msg_data = M.fetch(uid, '(RFC822)')
                if status != 'OK' or not msg_data:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                subj = decode_str(msg.get('Subject'))
                from_raw = decode_str(msg.get('From'))
                from_email = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", from_raw)
                from_email = from_email[0] if from_email else ''
                from_name = from_raw.replace(f"<{from_email}>", '').strip().strip('"') if from_email else from_raw
                date_hdr = msg.get('Date') or ''
                try:
                    email_date = email_utils.parsedate_to_datetime(date_hdr)
                except Exception:
                    email_date = None

                text = extract_text(msg)

                # Quick filters
                subj_ok = any(h.lower() in (subj or '').lower() for h in subj_hints)
                from_ok = any(h.lower() in (from_email or '').lower() for h in from_hints)
                text_ok = ('INTERAC' in text.upper() or 'E-TRANSFER' in text.upper() or 'ETRANSFER' in text.upper())
                if not (subj_ok or from_ok or text_ok):
                    continue

                amt = parse_amount(text)
                ref = parse_interac_ref(text)
                code4 = first4(ref)
                msg_id = msg.get('Message-ID') or ''
                excerpt = text[:250]
                rows.append({
                    'uid': uid.decode('ascii') if isinstance(uid, bytes) else str(uid),
                    'email_date': (email_date or datetime.utcnow()).isoformat(),
                    'subject': subj,
                    'from_email': from_email,
                    'from_name': from_name,
                    'amount': amt if amt is not None else '',
                    'currency': 'CAD',
                    'interac_ref': ref or '',
                    'code4': code4 or '',
                    'message_excerpt': excerpt,
                    'message_id': msg_id,
                })
            except Exception:
                continue

    out = r"l:/limo/reports/etransfer_emails.csv"
    with open(out, 'w', newline='', encoding='utf-8') as f:
        if rows:
            fieldnames = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader(); w.writerows(rows)
        else:
            f.write('')
    print(f"Wrote {len(rows)} Interac email rows to {out}")


if __name__ == '__main__':
    main()
