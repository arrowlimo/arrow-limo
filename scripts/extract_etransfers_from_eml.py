#!/usr/bin/env python3
"""
Extract Interac e-Transfer emails from a folder of .eml and .msg files.
Outputs the same CSV as the IMAP/PST extractor:
  l:/limo/reports/etransfer_emails.csv

Usage:
  python scripts/extract_etransfers_from_eml.py --dir "l:/limo/outlook export/etransfers"
"""
import os
import re
import csv
import argparse
from datetime import datetime
from email import message_from_binary_file, message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

try:
    import extract_msg  # for .msg files
except Exception:
    extract_msg = None


def decode_str(s):
    if s is None:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return str(s)


def parse_amount(text: str):
    m = re.search(r"\$?([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\.[0-9]{2}", text.replace("\u00a0"," "))
    if not m:
        return None
    try:
        return float(m.group(0).replace("$", "").replace(",", ""))
    except Exception:
        return None


def parse_interac_ref(text: str):
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
    subj = subject or ''
    snd = (sender or '').lower()
    subj_lower = subj.lower()
    strong_subject = (
        'interac e-transfer' in subj_lower or
        "you've received an interac" in subj_lower or
        ('autodeposit' in subj_lower and 'interac' in subj_lower)
    )
    strong_sender = any(h in snd for h in ['@interac', 'payments.interac', 'no-reply@interac'])
    if strong_subject or strong_sender:
        return True
    text = body or ''
    if re.search(r"\bINTERAC\b", text, re.IGNORECASE) and re.search(r"\be[- ]?transfer\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bAutodeposit\b", text, re.IGNORECASE) and re.search(r"\bINTERAC\b", text, re.IGNORECASE):
        return True
    return False


def read_eml(path: str):
    with open(path, 'rb') as f:
        msg = message_from_binary_file(f)
    subject = decode_str(msg.get('Subject'))
    from_raw = decode_str(msg.get('From'))
    from_email = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", from_raw)
    from_email = from_email[0] if from_email else ''
    from_name = from_raw.replace(f"<{from_email}>", '').strip().strip('"') if from_email else from_raw
    date_hdr = msg.get('Date') or ''
    try:
        email_date = parsedate_to_datetime(date_hdr)
    except Exception:
        email_date = None

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
    text = "\n\n".join(parts)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return subject, from_email, from_name, (email_date or datetime.utcnow()).isoformat(), text


def read_msg(path: str):
    if extract_msg is None:
        raise RuntimeError("extract_msg is not installed; run 'pip install extract-msg' in the virtualenv")
    msg = extract_msg.Message(path)
    subject = msg.subject or ''
    from_email = (msg.sender or '')
    from_name = (msg.sender_name or '')
    try:
        email_date = msg.date
    except Exception:
        email_date = None
    body = (msg.body or msg.htmlBody or '')
    # normalize
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()
    return subject, from_email, from_name, (email_date or datetime.utcnow()).isoformat(), text


def main():
    ap = argparse.ArgumentParser(description='Extract Interac e-Transfers from .eml/.msg folder')
    ap.add_argument('--dir', required=True, help='Folder containing .eml and/or .msg files')
    args = ap.parse_args()

    rows = []
    for root, _, files in os.walk(args.dir):
        for fn in files:
            path = os.path.join(root, fn)
            try:
                if fn.lower().endswith('.eml'):
                    subject, from_email, from_name, email_date, text = read_eml(path)
                elif fn.lower().endswith('.msg'):
                    subject, from_email, from_name, email_date, text = read_msg(path)
                else:
                    continue
                if not is_interac_like(subject, from_email, text):
                    continue
                amt = parse_amount(text)
                ref = parse_interac_ref(text)
                code4 = first4(ref)
                rows.append({
                    'uid': os.path.basename(path),
                    'email_date': email_date,
                    'subject': subject,
                    'from_email': from_email,
                    'from_name': from_name,
                    'amount': amt if amt is not None else '',
                    'currency': 'CAD',
                    'interac_ref': ref or '',
                    'code4': code4 or '',
                    'message_excerpt': text[:250],
                    'message_id': '',
                })
            except Exception:
                continue

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
