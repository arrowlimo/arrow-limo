#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', '5432'),
    )
    cur = conn.cursor()

    print('Tables with client/customer in name:')
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public'
          AND (table_name ILIKE '%client%' OR table_name ILIKE '%customer%')
        ORDER BY table_name
    """)
    for (t,) in cur.fetchall():
        print('  -', t)

    to_probe = [
        'clients','customers','lms_customers_enhanced','lms_customers','lms_unified_map',
        'charters','payments','square_customers','customer_name_mapping','customer_name_resolver',
        'payment_customer_links'
    ]
    for t in to_probe:
        try:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
            """, (t,))
            cols = cur.fetchall()
            if cols:
                print(f"\nColumns for {t}:")
                for name, dt in cols:
                    print(f"  - {name}: {dt}")
            else:
                print(f"\n{t}: (no columns found)")
        except Exception as e:
            print(f"\n{t}: not found ({e})")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
