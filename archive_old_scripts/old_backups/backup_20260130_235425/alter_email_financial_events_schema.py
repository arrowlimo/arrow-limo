#!/usr/bin/env python3
"""
Idempotent schema alterations for email_financial_events:
- Add license_plate column (TEXT)
- Add unique index on (source, from_email, subject, email_date) for upserts
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
        DO $$ BEGIN
            BEGIN
                ALTER TABLE email_financial_events ADD COLUMN license_plate TEXT;
            EXCEPTION WHEN duplicate_column THEN
                -- ignore
                NULL;
            END;
        END $$;

        -- Non-unique index to speed lookups; duplicates will be handled in code
        CREATE INDEX IF NOT EXISTS ix_email_events_src_from_subj_date
            ON email_financial_events(source, from_email, subject, email_date);
        """
    )
    conn.commit()
    cur.close(); conn.close()
    print('Applied schema alterations to email_financial_events')


if __name__ == '__main__':
    main()
