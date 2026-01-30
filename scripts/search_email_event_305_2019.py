#!/usr/bin/env python3
import os
import psycopg2

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email_date, from_email, subject, amount, entity
            FROM email_financial_events
            WHERE email_date >= DATE '2019-01-01'
              AND email_date < DATE '2019-03-01'
              AND ROUND(CAST(amount AS numeric), 2) = 305.89
            ORDER BY email_date
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("No matching email financial events found for $305.89 in Jan-Feb 2019.")
        else:
            print("Matches for $305.89 (Jan-Feb 2019):")
            for r in rows:
                print(f"  ID {r[0]} | {r[1]} | {r[2]} | {r[3]} | ${r[4]} | entity={r[5]}")
