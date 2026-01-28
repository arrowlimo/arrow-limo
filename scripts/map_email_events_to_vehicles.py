#!/usr/bin/env python3
"""
Map email_financial_events rows to vehicles by setting vehicle_id using VIN or license_plate.
Rules:
- Prefer VIN (full or last-8, case-insensitive)
- Fallback to normalized license plate match (remove non-alphanumerics, case-insensitive)
Filters:
- Only map rows where entity='CMB Insurance' (insurance emails tend to include identifiers)
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

    # Using two passes: VIN then plate
    print('Mapping by VIN (Heffner + CMB)...')
    cur.execute(
        """
        UPDATE email_financial_events e
           SET vehicle_id = v.vehicle_id
          FROM vehicles v
         WHERE e.entity IN ('CMB Insurance','Heffner')
           AND e.vehicle_id IS NULL
           AND e.vin IS NOT NULL
           AND (
                 regexp_replace(UPPER(COALESCE(v.vin_number,'')),'[^A-Z0-9]','','g')
                     = regexp_replace(UPPER(COALESCE(e.vin,'')),'[^A-Z0-9]','','g')
              OR RIGHT(regexp_replace(UPPER(COALESCE(v.vin_number,'')),'[^A-Z0-9]','','g'), 8)
                     = RIGHT(regexp_replace(UPPER(COALESCE(e.vin,'')),'[^A-Z0-9]','','g'), 8)
           )
        """
    )
    print('  updated:', cur.rowcount)

    print('Mapping by license_plate (Heffner + CMB)...')
    cur.execute(
        """
        UPDATE email_financial_events e
           SET vehicle_id = v.vehicle_id
          FROM vehicles v
         WHERE e.entity IN ('CMB Insurance','Heffner')
           AND e.vehicle_id IS NULL
           AND e.license_plate IS NOT NULL
           AND regexp_replace(UPPER(COALESCE(v.license_plate,'')),'[^A-Z0-9]','','g')
               = regexp_replace(UPPER(COALESCE(e.license_plate,'')),'[^A-Z0-9]','','g')
        """
    )
    print('  updated:', cur.rowcount)

    conn.commit()
    cur.close(); conn.close()
    print('Mapping complete.')


if __name__ == '__main__':
    main()
