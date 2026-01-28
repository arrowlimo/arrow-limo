#!/usr/bin/env python3
"""
Extract CIBC INTERAC e-Transfer acceptance emails (e.g., to Willie Heffner) directly from PST via Outlook COM
and stage them into email_financial_events.

Usage:
  python scripts/extract_cibc_etransfers_from_pst_outlook.py --pst "l:/limo/outlook backup/info@arrowlimo.ca.pst"
"""
import os
import re
import argparse
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

try:
    from win32com.client import gencache, Dispatch, DispatchEx
except Exception:
    gencache = None

AMOUNT_RE = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2}))")
RECIPIENT_RE = re.compile(r"to\s+([^\n]+?)\s+accepted", re.I)


def find_store_root(ns, pst_path):
    for store in ns.Stores:
        try:
            if hasattr(store, 'FilePath') and os.path.normcase(store.FilePath) == os.path.normcase(pst_path):
                return store.GetRootFolder()
        except Exception:
            continue
    return None


def collect_etransfers(folder):
    rows = []
    try:
        items = folder.Items
        try:
            items.Sort("[ReceivedTime]", True)
        except Exception:
            pass
        for i in range(1, items.Count + 1):
            try:
                msg = items.Item(i)
                subject = str(getattr(msg, 'Subject', '') or '')
                sender = str(getattr(msg, 'SenderName', '') or '')
                if 'INTERAC' not in subject.upper() or 'ACCEPTED' not in subject.upper():
                    continue
                if 'CIBC' not in sender.upper() and 'CIBC' not in subject.upper():
                    continue
                body = str(getattr(msg, 'Body', '') or '')
                received = getattr(msg, 'ReceivedTime', None)
                try:
                    email_dt = datetime.fromtimestamp(received.timestamp()) if received else datetime.utcnow()
                except Exception:
                    email_dt = datetime.utcnow()

                # Parse amount and recipient
                m_amt = AMOUNT_RE.search(subject) or AMOUNT_RE.search(body)
                amount = float(m_amt.group(1).replace(',', '')) if m_amt else None
                m_rec = RECIPIENT_RE.search(subject) or RECIPIENT_RE.search(body)
                recipient = m_rec.group(1).strip() if m_rec else None

                note = None
                if recipient:
                    note = f"to {recipient}"

                rows.append({
                    'source': 'pst:cibc_etransfer',
                    'entity': 'CIBC',
                    'from_email': sender,
                    'subject': subject,
                    'email_date': email_dt.isoformat(),
                    'event_type': 'etransfer_sent',
                    'amount': amount,
                    'currency': 'CAD',
                    'due_date': None,
                    'status': 'accepted',
                    'vin': None,
                    'vehicle_name': None,
                    'lender_name': None,
                    'policy_number': None,
                    'loan_external_id': None,
                    'notes': note,
                })
            except Exception:
                continue
    except Exception:
        pass
    # Recurse
    try:
        for f in folder.Folders:
            try:
                rows.extend(collect_etransfers(f))
            except Exception:
                continue
    except Exception:
        pass
    return rows


def upsert(cur, row):
    # Dedupe by source+subject+email_date+amount
    cur.execute(
        """
        SELECT id FROM email_financial_events
         WHERE source=%s AND subject=%s AND email_date=%s AND COALESCE(amount,-1)=COALESCE(%s,-1)
        """,
        (row['source'], row['subject'], row['email_date'], row['amount'])
    )
    if cur.fetchone():
        return False
    cur.execute(
        """
        INSERT INTO email_financial_events(
            source, entity, from_email, subject, email_date, event_type,
            amount, currency, due_date, status, vin, vehicle_name,
            lender_name, loan_external_id, policy_number, notes
        ) VALUES (
            %(source)s, %(entity)s, %(from_email)s, %(subject)s, %(email_date)s, %(event_type)s,
            %(amount)s, %(currency)s, %(due_date)s, %(status)s, %(vin)s, %(vehicle_name)s,
            %(lender_name)s, %(loan_external_id)s, %(policy_number)s, %(notes)s
        )
        """,
        row,
    )
    return True


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('--pst', default=r'l:/limo/outlook backup/info@arrowlimo.ca.pst')
    args = ap.parse_args()

    if gencache is None:
        print('pywin32 not available')
        return
    try:
        outlook = gencache.EnsureDispatch('Outlook.Application')
    except Exception:
        try:
            outlook = DispatchEx('Outlook.Application')
        except Exception:
            outlook = Dispatch('Outlook.Application')
    ns = outlook.GetNamespace('MAPI')
    try:
        ns.AddStoreEx(args.pst, 1)
    except Exception:
        pass
    root = find_store_root(ns, args.pst)
    if root is None:
        print('Could not open PST store')
        return

    rows = collect_etransfers(root)
    print(f"Found {len(rows)} e-Transfer emails")

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    cur = conn.cursor()
    inserted = 0
    for r in rows:
        try:
            if upsert(cur, r):
                inserted += 1
        except Exception:
            conn.rollback()
            continue
    conn.commit()
    cur.close(); conn.close()
    print(f"Inserted {inserted} e-Transfer rows into email_financial_events")


if __name__ == '__main__':
    main()
