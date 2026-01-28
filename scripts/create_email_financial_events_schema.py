#!/usr/bin/env python3
"""
Create staging table for financial events parsed from emails (Heffner/CMB, etc.).

Table: email_financial_events
"""
import os
import psycopg2
from dotenv import load_dotenv


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS email_financial_events (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,                 -- pst | eml | imap
            entity TEXT,                          -- Heffner | CMB Insurance | other
            from_email TEXT,
            subject TEXT,
            email_date TIMESTAMP,
            event_type TEXT,                      -- loan_payment | amount_owing | nsf_fee | loan_opened | loan_closed | insurance_payment | coverage_change | downpayment | extra_payment
            amount NUMERIC(14,2),
            currency TEXT,
            due_date DATE,
            status TEXT,                          -- paid | due | overdue | missed | completed | canceled
            vin TEXT,
            vehicle_name TEXT,
            vehicle_id INT,
            lender_name TEXT,
            loan_external_id TEXT,                -- loan number/policy number
            policy_number TEXT,
            notes TEXT,
            banking_transaction_id INT,
            matched_account_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_email_events_email_date ON email_financial_events(email_date);
        CREATE INDEX IF NOT EXISTS idx_email_events_entity ON email_financial_events(entity);
        CREATE INDEX IF NOT EXISTS idx_email_events_event_type ON email_financial_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_email_events_amount ON email_financial_events(amount);
        """
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Created/verified table email_financial_events")


if __name__ == '__main__':
    main()
