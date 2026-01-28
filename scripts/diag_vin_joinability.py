#!/usr/bin/env python3
"""
Quick diagnostics: measure VIN presence in email_financial_events and joinability to vehicles.
Prints counts and a few sample values to guide extraction/join fixes.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
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
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print('Email events counts:')
    cur.execute("SELECT COUNT(*) AS c FROM email_financial_events")
    print('  total:', cur.fetchone()['c'])
    cur.execute("SELECT COUNT(*) AS c FROM email_financial_events WHERE vin IS NOT NULL")
    print('  with vin:', cur.fetchone()['c'])
    cur.execute("SELECT COUNT(*) AS c FROM email_financial_events WHERE vin IS NOT NULL AND length(vin)=17")
    print('  vin len=17:', cur.fetchone()['c'])
    cur.execute("SELECT COUNT(*) AS c FROM email_financial_events WHERE vin IS NOT NULL AND length(vin)=8")
    print('  vin len=8:', cur.fetchone()['c'])

    print('\nSample VINs from email_financial_events:')
    cur.execute("""
        SELECT vin, subject
          FROM email_financial_events
         WHERE vin IS NOT NULL
         GROUP BY vin, subject
         ORDER BY 1 NULLS LAST
         LIMIT 20
    """)
    for row in cur.fetchall():
        print('  vin:', row['vin'], '| subj:', (row['subject'] or '')[:70])

    print('\nVehicles table:')
    try:
        cur.execute("SELECT COUNT(*) AS c FROM vehicles")
        print('  vehicles count:', cur.fetchone()['c'])
        cur.execute("""
            SELECT vin_number, license_plate, make, model
              FROM vehicles
             WHERE vin_number IS NOT NULL
             LIMIT 10
        """)
        for r in cur.fetchall():
            print('  veh vin:', r['vin_number'], '| plate:', r.get('license_plate'), '|', r.get('make'), r.get('model'))

        print('\nJoinability (full or last-8):')
        cur.execute("""
            SELECT COUNT(*) AS c
              FROM email_financial_events e
              JOIN vehicles v
                ON (e.vin IS NOT NULL AND (UPPER(v.vin_number) = UPPER(e.vin)
                    OR RIGHT(UPPER(v.vin_number), 8) = RIGHT(UPPER(e.vin), 8)))
        """)
        print('  joinable rows:', cur.fetchone()['c'])
    except Exception as ex:
        print('  vehicles table check failed:', ex)

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
