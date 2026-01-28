#!/usr/bin/env python3
"""
Extract Interac e-Transfer emails from an Outlook PST/OST file and output
the same normalized CSV as fetch_etransfer_emails.py:

  l:/limo/reports/etransfer_emails.csv

Requires pypff (libpff). On Windows, install via prebuilt wheels if available or
build libpff. If installation is difficult, I can fall back to reading MSG/EML exports.

Usage:
  python scripts/extract_etransfers_from_pst.py --pst "l:/limo/outlook backup/info@arrowlimo.ca.pst"
"""
import os
import re
import csv
import argparse
from datetime import datetime

from dotenv import load_dotenv

# Try multiple module names for libpff/python bindings
pypff = None
_import_errors = []
for mod_name in ("pypff", "python_libpff", "libpff", "pypff_bindings"):
    try:
        pypff = __import__(mod_name)
        break
    except Exception as e:
        _import_errors.append((mod_name, str(e)))


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


def walk_items(folder, rows):
    for i in range(folder.number_of_sub_messages):
        msg = folder.get_sub_message(i)
        try:
            subject = msg.subject or ''
            sender = msg.sender_email_address or ''
            body = (msg.plain_text_body or msg.html_body or '')
            if not is_interac_like(subject, sender, body):
                continue
            amount = parse_amount(body)
            ref = parse_interac_ref(body)
            code4 = first4(ref)
            msg_id = msg.client_submit_time or msg.delivery_time or None
            dt = None
            try:
                dt = msg_id.as_datetime() if hasattr(msg_id, 'as_datetime') else None
            except Exception:
                dt = None
            if not dt:
                try:
                    dt = msg.delivery_time.as_datetime()
                except Exception:
                    dt = None
            rows.append({
                'uid': str(msg.record_index),
                'email_date': (dt or datetime.utcnow()).isoformat(),
                'subject': subject,
                'from_email': sender,
                'from_name': msg.sender_name or '',
                'amount': amount if amount is not None else '',
                'currency': 'CAD',
                'interac_ref': ref or '',
                'code4': code4 or '',
                'message_excerpt': (body[:250] if body else ''),
                'message_id': '',
            })
        except Exception:
            continue

    for j in range(folder.number_of_sub_folders):
        sub = folder.get_sub_folder(j)
        walk_items(sub, rows)


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    ap = argparse.ArgumentParser(description='Extract Interac e-transfers from PST/OST into CSV')
    ap.add_argument('--pst', required=False, default=r"l:/limo/outlook backup/info@arrowlimo.ca.pst")
    args = ap.parse_args()

    if pypff is None:
        print('pypff is not installed; cannot parse PST directly. Consider installing libpff/pypff or exporting relevant email folders to EML/MSG.')
        return

    pst_path = args.pst
    if not os.path.exists(pst_path):
        print('PST not found:', pst_path)
        return

    f = pypff.file()
    f.open(pst_path)
    root = f.get_root_folder()
    rows = []
    walk_items(root, rows)
    f.close()

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
