#!/usr/bin/env python3
"""
Insert a single INTERAC e-Transfer email event based on screenshot evidence.
Event details (from Outlook screenshot):
- Date: 2017-04-20
- From: notify@payments.interac.ca (INTERAC notification)
- Subject: INTERAC e-Transfer: PAUL RICHARD sent you money.
- Recipient name: Tenisha Woodridge ford
- Amount: 131.26 CAD
- Message: "pmt"
"""
import os
import psycopg2
from datetime import date

DB = dict(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***'),
)

def main():
    event = {
        'source': 'EMAIL_INTERAC',
        'entity': 'INTERAC',
        'from_email': 'notify@payments.interac.ca',
        'subject': 'INTERAC e-Transfer: PAUL RICHARD sent you money.',
        'email_date': date(2017,4,20),
        'event_type': 'etransfer_incoming',
        'amount': 131.26,
        'currency': 'CAD',
        'status': 'received',
        'notes': 'Recipient: Tenisha Woodridge ford; Message: pmt; Evidence: Outlook screenshot',
    }
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_financial_events
                (source, entity, from_email, subject, email_date, event_type, amount, currency, status, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    event['source'], event['entity'], event['from_email'], event['subject'],
                    event['email_date'], event['event_type'], event['amount'], event['currency'],
                    event['status'], event['notes']
                )
            )
            new_id = cur.fetchone()[0]
            print(f"Inserted email_financial_event ID {new_id} for {event['email_date']} amount ${event['amount']:.2f}")

if __name__ == '__main__':
    main()
