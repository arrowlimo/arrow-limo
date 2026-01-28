#!/usr/bin/env python3
"""
Scan Outlook PST for Charter Reservation / Confirmation Emails.

Goal:
  - Identify charter confirmation letters sent to clients that contain the reservation number
  - Extract non‑refundable deposit amounts mentioned
  - Capture client email and any payment/deposit phrasing

Extraction:
  - reserve_number: 6-digit numeric (e.g. 019708) or legacy REF format
  - deposit_amount: first monetary amount appearing near keywords (deposit, retainer, non-refundable)
  - total_amount: if an explicit total / balance line appears
  - client_email: first non-internal email found in body
  - client_name: name pattern in greeting lines (Dear/Hi/Hello <Name>)

Database target: email_financial_events (source = 'outlook_charter_confirmation', event_type='charter_confirmation')
Safe by default: dry-run unless --write supplied.
"""

import os
import re
import hashlib
import psycopg2
import win32com.client  # Requires Outlook installed
from datetime import datetime
from dotenv import load_dotenv
import argparse

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

PST_PATH = r"l:\limo\outlook backup\info@arrowlimo.ca.pst"

RESERVE_PATTERNS = [
    re.compile(r"\b(\d{6})\b"),             # pure 6-digit
    re.compile(r"\bREF0*(\d{3,6})\b", re.IGNORECASE),
    re.compile(r"Reservation\s*#\s*(\d{6})", re.IGNORECASE),
    re.compile(r"Reserve\s*Number\s*[:\-]?\s*(\d{6})", re.IGNORECASE),
]

AMOUNT_PATTERN = re.compile(r"\$\s?([\d,]+\.?\d{0,2})")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
NAME_PATTERNS = [
    re.compile(r"Dear\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})"),
    re.compile(r"Hi\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})"),
    re.compile(r"Hello\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})"),
]

DEPOSIT_KEYWORDS = ["deposit", "retainer", "non-refundable", "nonrefundable", "payment received"]


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def is_confirmation(subject: str, body: str) -> bool:
    s = subject.lower()
    b = body.lower()
    if any(k in s for k in ["confirmation", "reservation", "charter", "booking confirmed"]):
        return True
    # Body fallback
    if "reservation number" in b or "reserve number" in b:
        return True
    return False


def extract_first_amount_near_keywords(body: str) -> float | None:
    lower_body = body.lower()
    for kw in DEPOSIT_KEYWORDS:
        idx = lower_body.find(kw)
        if idx != -1:
            # Slice window around keyword
            window = body[max(0, idx - 120): idx + 200]
            m = AMOUNT_PATTERN.search(window)
            if m:
                try:
                    return float(m.group(1).replace(',', ''))
                except:  # noqa
                    continue
    return None


def extract_total_amount(body: str) -> float | None:
    # Look for phrases like Total:, Balance:, Amount Due:
    for label in ["total", "balance", "amount due", "total due"]:
        pattern = re.compile(rf"{label}[\s:]+\$\s?([\d,]+\.?\d{{0,2}})", re.IGNORECASE)
        m = pattern.search(body)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except:  # noqa
                continue
    return None


def extract_reserve(body: str) -> str | None:
    for pat in RESERVE_PATTERNS:
        m = pat.search(body)
        if m:
            val = m.group(1)
            # Normalize REF variant by zero-padding to 6 if needed
            if len(val) < 6:
                val = val.zfill(6)
            return val
    return None


def extract_client_email(body: str) -> str | None:
    for email in EMAIL_PATTERN.findall(body):
        e_lower = email.lower()
        if not any(dom in e_lower for dom in ["arrowlimo", "squareup", "payments.interac", "reply."]):
            return email
    return None


def extract_client_name(body: str) -> str | None:
    for pat in NAME_PATTERNS:
        m = pat.search(body)
        if m:
            return m.group(1).strip()
    return None


def scan_confirmations():
    if not os.path.exists(PST_PATH):
        print(f"[FAIL] PST not found: {PST_PATH}")
        return []
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    outlook.AddStore(PST_PATH)
    root_folder = None
    for store in outlook.Stores:
        if PST_PATH.lower() in store.FilePath.lower():
            root_folder = store.GetRootFolder()
            break
    if not root_folder:
        print("[FAIL] Unable to access PST root folder")
        return []

    confirmations = []

    def recurse(folder, depth=0):
        try:
            items = folder.Items
            items.Sort("[ReceivedTime]", True)
            for item in items:
                try:
                    if not hasattr(item, 'Subject'):
                        continue
                    subject = item.Subject or ''
                    body = item.Body or ''
                    if not body:
                        continue
                    if is_confirmation(subject, body):
                        reserve = extract_reserve(body)
                        deposit = extract_first_amount_near_keywords(body)
                        total = extract_total_amount(body)
                        client_email = extract_client_email(body)
                        client_name = extract_client_name(body)
                        received = item.ReceivedTime
                        hash_input = f"{received}|{subject}|{reserve}|{deposit}".encode('utf-8')
                        email_hash = hashlib.sha256(hash_input).hexdigest()
                        confirmations.append({
                            'received': received,
                            'subject': subject,
                            'reserve_number': reserve,
                            'deposit_amount': deposit,
                            'total_amount': total,
                            'client_email': client_email,
                            'client_name': client_name,
                            'folder': folder.Name,
                            'hash': email_hash,
                        })
                except Exception:
                    continue
            for sub in folder.Folders:
                recurse(sub, depth + 1)
        except Exception:
            pass

    recurse(root_folder)
    try:
        outlook.RemoveStore(root_folder)
    except Exception:
        pass
    return confirmations


def save(confirmations, write: bool):
    print("\n=== SUMMARY (Charter Confirmations) ===")
    print(f"Total confirmation-like emails: {len(confirmations)}")
    with_count_res = sum(1 for c in confirmations if c['reserve_number'])
    print(f"With reservation number: {with_count_res}")
    with_deposit = sum(1 for c in confirmations if c['deposit_amount'])
    print(f"With deposit amount: {with_deposit}")

    if not write:
        print("\n[DRY RUN] Skipping database insert. Use --write to persist.")
        # Show first 15 examples
        for c in confirmations[:15]:
            print(f"  {c['received'].strftime('%Y-%m-%d')} reserve={c['reserve_number'] or 'N/A'} deposit={c['deposit_amount'] or 'N/A'} total={c['total_amount'] or 'N/A'} email={c['client_email'] or 'N/A'}")
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name='email_financial_events'
        )
    """)
    if not cur.fetchone()[0]:
        print("[WARN] Table email_financial_events missing. Create schema first.")
        cur.close(); conn.close(); return

    # Load existing hashes
    cur.execute("SELECT notes FROM email_financial_events WHERE source='outlook_charter_confirmation' AND notes LIKE 'confirm_hash:%'")
    existing = set()
    for row in cur.fetchall():
        try:
            part = row[0].split('confirm_hash:')[1].split()[0]
            existing.add(part)
        except Exception:
            continue

    inserted = 0
    skipped = 0
    for c in confirmations:
        if c['hash'] in existing:
            skipped += 1
            continue
        notes_parts = [f"confirm_hash:{c['hash']}"]
        if c['client_name']:
            notes_parts.append(f"client:{c['client_name']}")
        if c['client_email']:
            notes_parts.append(f"email:{c['client_email']}")
        if c['reserve_number']:
            notes_parts.append(f"reserve:{c['reserve_number']}")
        notes_parts.append(f"subject:{c['subject'][:80]}")
        notes = " | ".join(notes_parts)
        sql = """
            INSERT INTO email_financial_events (
                source, entity, from_email, subject, email_date, event_type,
                amount, currency, status, notes, matched_account_number
            ) VALUES (
                'outlook_charter_confirmation', 'charter', %s, %s, %s, 'charter_confirmation',
                %s, 'CAD', 'processed', %s, %s
            )
        """
        # We use deposit_amount (if found) as amount; else NULL
        try:
            cur.execute(sql, (
                c['client_email'] or '',
                c['subject'],
                c['received'],
                c['deposit_amount'],
                notes,
                c['reserve_number']
            ))
            inserted += 1
        except Exception as e:
            print(f"  Insert error: {e}")
            skipped += 1
    conn.commit()
    print(f"Inserted: {inserted}  Skipped: {skipped}")
    cur.close(); conn.close()


def main():
    parser = argparse.ArgumentParser(description="Scan Outlook PST for charter confirmation emails")
    parser.add_argument('--write', action='store_true', help='Persist to database')
    args = parser.parse_args()
    confirmations = scan_confirmations()
    save(confirmations, write=args.write)


if __name__ == '__main__':
    main()
