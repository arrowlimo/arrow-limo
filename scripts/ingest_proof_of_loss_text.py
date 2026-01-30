#!/usr/bin/env python3
"""
Ingest an Automobile Proof of Loss text into email_financial_events.

Parses key fields:
- insurer/entity, policy number, insured name
- date of loss (as email_date), VIN, license plate
- amounts: total loss, deductible, claimed (uses claimed as amount)
- lender/lienholder notes

Usage:
  python scripts/ingest_proof_of_loss_text.py --file "l:/limo/reports/proof_of_loss_2019_s550.txt"
"""
import os
import re
import argparse
from datetime import datetime
from dotenv import load_dotenv
import psycopg2


VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b", re.I)
PLATE_RE = re.compile(r"Licence Plate No\.?\s*&\s*Province\s*([^\n\r]+)", re.I)
POLICY_RE = re.compile(r"POLICY\s*#\s*[:#]?\s*(\S+)", re.I)
INSURER_RE = re.compile(r"INSURER\s+UNDER\s+POLICY\s*#:?\s*(\S+)", re.I)
INSURER_NAME_RE = re.compile(r"\bThe\s+Nordic\s+Insurance\s+Company\s+of\s+Canada\b", re.I)
INSURED_RE = re.compile(r"\bINSURED\b[\s\S]{0,200}?\n([A-Z][^\n\r]+)", re.I)
DATE_LOSS_RE = re.compile(r"Date of Loss\s*\n?\s*([A-Za-z]+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", re.I)
AMOUNT_LOSS_RE = re.compile(r"total amount of loss or damage.*?\$\s*([\d,]+\.\d{2})", re.I)
DEDUCTIBLE_RE = re.compile(r"Deductible\s*-\$\s*([\d,]+\.\d{2})", re.I)
CLAIMED_RE = re.compile(r"total amount claimed.*?\$\s*([\d,]+\.\d{2})", re.I)


def parse_money(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.replace(',', ''))
    except Exception:
        return None


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    return None


def ingest(text: str) -> dict:
    """Extract fields from provided text and return row dict for email_financial_events."""
    vin = None
    vins = VIN_RE.findall(text)
    if vins:
        vin = vins[0]

    plate_match = PLATE_RE.search(text)
    license_plate = plate_match.group(1).strip() if plate_match else None

    # Prefer explicit insurer name if present
    insurer_name = None
    if INSURER_NAME_RE.search(text):
        insurer_name = "The Nordic Insurance Company of Canada"

    # Fallback to entity detected around policy header
    policy_number = None
    m_pol = POLICY_RE.search(text)
    if m_pol:
        policy_number = m_pol.group(1).strip()
    else:
        m_pol2 = INSURER_RE.search(text)
        if m_pol2:
            policy_number = m_pol2.group(1).strip()

    m_insured = INSURED_RE.search(text)
    insured_name = m_insured.group(1).strip() if m_insured else None

    m_date = DATE_LOSS_RE.search(text)
    loss_dt = parse_date(m_date.group(1)) if m_date else None

    total_loss = parse_money((AMOUNT_LOSS_RE.search(text) or [None, None])[1] if AMOUNT_LOSS_RE.search(text) else None)
    deductible = parse_money((DEDUCTIBLE_RE.search(text) or [None, None])[1] if DEDUCTIBLE_RE.search(text) else None)
    claimed = parse_money((CLAIMED_RE.search(text) or [None, None])[1] if CLAIMED_RE.search(text) else None)

    # Notes capture lienholders etc.
    notes = []
    for key in ("RIFCO", "Her Majesty the Queen in Right of Canada", "Drayden Insurance"):
        if re.search(key, text, re.I):
            notes.append(key)
    notes_str = "; ".join(notes) if notes else None

    row = {
        'source': 'manual',
        'entity': insurer_name or 'Insurance',
        'from_email': None,
        'subject': 'Automobile Proof of Loss',
        'email_date': (loss_dt or datetime(2019, 3, 29)).isoformat(),
        'event_type': 'insurance_claim',
        'amount': claimed or total_loss,
        'currency': 'CAD',
        'due_date': None,
        'status': 'claim filed',
        'vin': vin,
        'vehicle_name': '2007 MERCEDES-BENZ S550V' if 'MERCEDES' in text.upper() else None,
        'lender_name': None,
        'policy_number': policy_number,
        'loan_external_id': None,
        'notes': notes_str,
        # Optional extended columns if present in schema
        'license_plate': license_plate,
    }
    return row


def upsert_row(cur, row: dict):
    # Ensure optional column license_plate exists; ignore errors
    try:
        cur.execute("ALTER TABLE email_financial_events ADD COLUMN IF NOT EXISTS license_plate TEXT")
    except Exception:
        cur.connection.rollback()
    # Insert simple row (no ON CONFLICT since manual unique key not defined)
    cur.execute(
        """
        INSERT INTO email_financial_events(
            source, entity, from_email, subject, email_date, event_type,
            amount, currency, due_date, status, vin, vehicle_name,
            lender_name, loan_external_id, policy_number, notes, license_plate
        ) VALUES (
            %(source)s, %(entity)s, %(from_email)s, %(subject)s, %(email_date)s, %(event_type)s,
            %(amount)s, %(currency)s, %(due_date)s, %(status)s, %(vin)s, %(vehicle_name)s,
            %(lender_name)s, %(loan_external_id)s, %(policy_number)s, %(notes)s, %(license_plate)s
        )
        """,
        row,
    )


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    ap = argparse.ArgumentParser(description='Ingest Automobile Proof of Loss text')
    ap.add_argument('--file', required=True, help='Path to text file containing the proof-of-loss content')
    args = ap.parse_args()

    if not os.path.exists(args.file):
        raise FileNotFoundError(args.file)

    with open(args.file, 'r', encoding='utf-8', errors='ignore') as fh:
        text = fh.read()

    row = ingest(text)

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )
    cur = conn.cursor()
    try:
        upsert_row(cur, row)
        conn.commit()
        print('Inserted 1 proof-of-loss row into email_financial_events')
    except Exception as e:
        conn.rollback()
        print('Failed to insert proof-of-loss row:', e)
        raise
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    main()
