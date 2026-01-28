#!/usr/bin/env python3
"""Analyze Interac e-Transfer emails for valid charter (reserve) numbers before import.

This script reuses the scanning logic (independent of insertion) to:
  1. Enumerate all 6-digit numbers captured as potential reserve numbers in e-transfer emails.
  2. Cross-check each against existing `charters.reserve_number` entries.
  3. Produce summary counts (total e-transfer emails, emails with amount, with candidate reserve, valid reserve matches).
  4. List top unmatched candidate numbers (could be false positives or future/unimported).
  5. Provide guidance for next steps (import vs pattern refinement).

Dry-run only (no DB writes). Safe to run multiple times.
"""

import os
import re
import psycopg2
import win32com.client  # Requires Outlook desktop
from collections import Counter
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

PST_PATH = r"l:\limo\outlook backup\info@arrowlimo.ca.pst"

RESERVE_PATTERN = re.compile(r"\b(\d{6})\b")
SUBJECT_KEYWORDS = ["interac e-transfer", "e-transfer", "etransfer", "sent you money", "you have received", "money transfer"]
SENDERS = ["payments.interac.ca", "interac.ca"]
AMOUNT_PATTERN = re.compile(r"\$\s?([\d,]+\.?\d{0,2})")


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


def scan_emails():
    if not os.path.exists(PST_PATH):
        print(f"[FAIL] PST path not found: {PST_PATH}")
        return []
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    outlook.AddStore(PST_PATH)
    root_folder = None
    for store in outlook.Stores:
        if PST_PATH.lower() in store.FilePath.lower():
            root_folder = store.GetRootFolder()
            break
    if not root_folder:
        print("[FAIL] Could not access root folder for PST")
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
                    amt = None
                    m_amt = AMOUNT_PATTERN.search(body)
                    if m_amt:
                        try:
                            amt = float(m_amt.group(1).replace(',', ''))
                        except Exception:
                            pass
                    # Collect any 6-digit numbers but only keep if contextual keywords nearby
                    candidates = []
                    for m in RESERVE_PATTERN.finditer(body):
                        window = body[max(0, m.start() - 60): m.end() + 60].lower()
                        if any(w in window for w in ["reserve", "reservation", "charter", "trip", "booking", "deposit"]):
                            candidates.append(m.group(1))
                    results.append({
                        'amount': amt,
                        'reserves': candidates,
                        'sender': sender_email,
                        'subject': subject,
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


def load_existing_reserves():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    existing = {row[0].strip() for row in cur.fetchall() if row[0]}
    cur.close(); conn.close()
    return existing


def main():
    print("Scanning e-transfer emails for candidate reserve numbers (dry-run)...")
    data = scan_emails()
    existing_reserves = load_existing_reserves()
    total_emails = len(data)
    with_amount = sum(1 for r in data if r['amount'] is not None)
    candidate_reserve_occurrences = []
    for r in data:
        candidate_reserve_occurrences.extend(r['reserves'])

    unique_candidates = set(candidate_reserve_occurrences)
    valid_matches = [c for c in unique_candidates if c in existing_reserves]
    unmatched = [c for c in unique_candidates if c not in existing_reserves]

    print("\n=== E-Transfer Reserve Number Analysis ===")
    print(f"Total e-transfer classified emails: {total_emails}")
    print(f"Emails with amount: {with_amount}")
    print(f"Candidate reserve numbers (occurrences): {len(candidate_reserve_occurrences)}")
    print(f"Unique candidate reserve numbers: {len(unique_candidates)}")
    print(f"Valid reserve numbers (exist in charters): {len(valid_matches)}")
    print(f"Unmatched / potentially invalid candidates: {len(unmatched)}")

    # Frequency of valid matches
    freq = Counter(candidate_reserve_occurrences)
    top_valid = sorted(valid_matches, key=lambda x: -freq[x])[:15]
    top_unmatched = sorted(unmatched, key=lambda x: -freq[x])[:15]

    print("\nTop valid reserve numbers (with counts):")
    for rv in top_valid:
        print(f"  {rv} -> {freq[rv]} occurrences")

    print("\nTop unmatched candidates (with counts):")
    for rv in top_unmatched:
        print(f"  {rv} -> {freq[rv]} occurrences")

    # Guidance
    print("\nGuidance:")
    print("  - Valid matches can be safely used to link payments to charters.")
    print("  - Unmatched candidates may be: future bookings, cancelled, or false positives (numeric codes).")
    print("  - Recommend filtering insertion to only valid reserve numbers present in charters.")
    print("  - Next: run scan_outlook_etransfer_payments.py with --write after filtering logic refinement.")


if __name__ == '__main__':
    main()
