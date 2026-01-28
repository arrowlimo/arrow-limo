#!/usr/bin/env python3
"""
Scan Outlook PST for INTERAC e-Transfer payment emails.

Targets typical sender domains / subjects:
  - notify@payments.interac.ca
  - auto@payments.interac.ca
  - INTERAC e-Transfer: <Name> sent you money.
  - You have received an Interac e-Transfer
  - Money transfer deposit completed

Extract:
  - amount
  - sender_name / sender_email
  - reserve_number (if appears in message or memo text)
  - transfer reference / confirmation number
  - message snippet

Insert (optional): email_financial_events with source='outlook_etransfer_payment', event_type='etransfer_received'
Dry-run by default; use --write to persist.
"""

import os
import re
import hashlib
import psycopg2
import win32com.client
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

SENDERS = ["payments.interac.ca", "interac.ca"]
SUBJECT_KEYWORDS = ["interac e-transfer", "e-transfer", "etransfer", "sent you money", "money transfer", "you have received"]

AMOUNT_PATTERN = re.compile(r"\$\s?([\d,]+\.?\d{0,2})")
RESERVE_PATTERN = re.compile(r"\b(\d{6})\b")
REFERENCE_PATTERN = re.compile(r"Reference\s*[:#]\s*([A-Za-z0-9\-]+)", re.IGNORECASE)
CONFIRM_PATTERN = re.compile(r"Confirmation\s*(?:Code|#|Number)?\s*[:#]\s*([A-Za-z0-9\-]+)", re.IGNORECASE)
MESSAGE_PATTERN = re.compile(r"Message\s*[:]\s*(.{0,120})", re.IGNORECASE)


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def is_etransfer(subject: str, sender: str, body: str) -> bool:
    s = subject.lower()
    b = body.lower()
    if any(dom in sender.lower() for dom in SENDERS):
        return True
    if any(k in s for k in SUBJECT_KEYWORDS):
        return True
    if any(k in b for k in SUBJECT_KEYWORDS):
        return True
    return False


def scan_etransfers():
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
        print("[FAIL] Could not access PST root folder")
        return []

    results = []

    def recurse(folder):
        try:
            items = folder.Items
            items.Sort("[ReceivedTime]", True)
            for item in items:
                try:
                    if not hasattr(item, 'Subject'):
                        continue
                    subject = item.Subject or ''
                    body = item.Body or ''
                    sender_email = getattr(item, 'SenderEmailAddress', '') or ''
                    if not body:
                        continue
                    if not is_etransfer(subject, sender_email, body):
                        continue
                    # Extract amount (first occurrence)
                    amt = None
                    m_amt = AMOUNT_PATTERN.search(body)
                    if m_amt:
                        try:
                            amt = float(m_amt.group(1).replace(',', ''))
                        except Exception:
                            pass
                    reserve = None
                    # Avoid false positives like 6-digit codes: only keep if also appears near words deposit/payment/reservation
                    for m_res in RESERVE_PATTERN.finditer(body):
                        window = body[max(0, m_res.start() - 50): m_res.end() + 50].lower()
                        if any(w in window for w in ["reserve", "reservation", "charter", "trip", "deposit"]):
                            reserve = m_res.group(1)
                            break
                    reference = None
                    m_ref = REFERENCE_PATTERN.search(body)
                    if m_ref:
                        reference = m_ref.group(1)
                    confirm = None
                    m_conf = CONFIRM_PATTERN.search(body)
                    if m_conf:
                        confirm = m_conf.group(1)
                    message_snippet = None
                    m_msg = MESSAGE_PATTERN.search(body)
                    if m_msg:
                        message_snippet = m_msg.group(1).strip()
                    received = item.ReceivedTime
                    hash_input = f"{received}|{sender_email}|{amt}|{reserve}|{reference}".encode('utf-8')
                    email_hash = hashlib.sha256(hash_input).hexdigest()
                    results.append({
                        'received': received,
                        'subject': subject,
                        'sender_email': sender_email,
                        'amount': amt,
                        'reserve_number': reserve,
                        'reference': reference,
                        'confirmation': confirm,
                        'message': message_snippet,
                        'hash': email_hash,
                    })
                except Exception:
                    continue
            for sub in folder.Folders:
                recurse(sub)
        except Exception:
            pass

    recurse(root_folder)
    try:
        outlook.RemoveStore(root_folder)
    except Exception:
        pass
    return results


def save(results, write: bool):
    print("\n=== SUMMARY (Interac e-Transfers) ===")
    print(f"Total e-transfer emails: {len(results)}")
    with_amt = sum(1 for r in results if r['amount'])
    print(f"With amount: {with_amt}")
    with_res = sum(1 for r in results if r['reserve_number'])
    print(f"With reservation number: {with_res}")
    with_ref = sum(1 for r in results if r['reference'])
    print(f"With reference code: {with_ref}")

    if not write:
        print("\n[DRY RUN] Showing first 15:")
        for r in results[:15]:
            print(f"  {r['received'].strftime('%Y-%m-%d')} amt={r['amount'] or 'N/A'} reserve={r['reserve_number'] or 'N/A'} ref={r['reference'] or 'N/A'} msg={(r['message'] or '')[:40]}")
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='email_financial_events')
    """)
    if not cur.fetchone()[0]:
        print("[WARN] email_financial_events table missing. Create schema first.")
        cur.close(); conn.close(); return

    # Load valid reserve numbers for filtering
    cur.execute("SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    valid_reserves = {row[0].strip() for row in cur.fetchall() if row[0]}
    print(f"Loaded {len(valid_reserves)} valid reserve numbers from charters table")

    cur.execute("SELECT notes FROM email_financial_events WHERE source='outlook_etransfer_payment' AND notes LIKE 'etransfer_hash:%'")
    existing_hashes = set()
    for row in cur.fetchall():
        try:
            existing_hashes.add(row[0].split('etransfer_hash:')[1].split()[0])
        except Exception:
            continue

    inserted = 0
    skipped = 0
    filtered = 0
    for r in results:
        # Filter: only insert if reserve_number is valid OR if no reserve_number extracted
        if r['reserve_number'] and r['reserve_number'] not in valid_reserves:
            filtered += 1
            continue
        if r['hash'] in existing_hashes:
            skipped += 1
            continue
        notes_parts = [f"etransfer_hash:{r['hash']}"]
        if r['reserve_number']:
            notes_parts.append(f"reserve:{r['reserve_number']}")
        if r['reference']:
            notes_parts.append(f"ref:{r['reference']}")
        if r['confirmation']:
            notes_parts.append(f"confirm:{r['confirmation']}")
        if r['message']:
            notes_parts.append(f"msg:{r['message'][:60]}")
        notes_parts.append(f"subject:{r['subject'][:80]}")
        notes = " | ".join(notes_parts)
        sql = """
            INSERT INTO email_financial_events (
                source, entity, from_email, subject, email_date, event_type,
                amount, currency, status, notes, matched_account_number
            ) VALUES (
                'outlook_etransfer_payment', 'etransfer', %s, %s, %s, 'etransfer_received',
                %s, 'CAD', 'processed', %s, %s
            )
        """
        try:
            cur.execute(sql, (
                r['sender_email'], r['subject'], r['received'], r['amount'],
                notes, r['reserve_number']
            ))
            inserted += 1
        except Exception as e:
            print(f"  Insert error: {e}")
            skipped += 1
    conn.commit()
    print(f"\nInsertion Results:")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Filtered (invalid reserve): {filtered}")
    cur.close(); conn.close()


def main():
    parser = argparse.ArgumentParser(description="Scan Outlook PST for Interac e-Transfer payment emails")
    parser.add_argument('--write', action='store_true', help='Persist to database')
    args = parser.parse_args()
    results = scan_etransfers()
    save(results, write=args.write)


if __name__ == '__main__':
    main()
