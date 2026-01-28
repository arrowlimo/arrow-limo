#!/usr/bin/env python3
"""
Create qb_accounts reference table (if missing) and import distinct accounts
from qb_accounts_staging.

Idempotent: safe to run multiple times.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print('='*80)
    print('QB ACCOUNTS REFERENCE SETUP')
    print('='*80)

    # 1) Create table if not exists
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qb_accounts (
            id SERIAL PRIMARY KEY,
            qb_account_number TEXT,
            qb_name TEXT,
            qb_account_type TEXT,
            qb_bank_account_number TEXT,
            qb_description TEXT,
            source_serial INTEGER,
            source_imported_at TIMESTAMPTZ,
            UNIQUE(qb_account_number)
        )
        """
    )
    print('[OK] Ensured qb_accounts table exists')

    # 2) Insert distinct accounts from staging not already present
    cur.execute(
        """
        WITH distinct_accts AS (
            SELECT DISTINCT ON (qb_account_number)
                   qb_account_number, qb_name, qb_account_type,
                   qb_bank_account_number, qb_description, qb_serial_no
            FROM qb_accounts_staging
            WHERE qb_account_number IS NOT NULL AND qb_account_number <> ''
            ORDER BY qb_account_number, qb_serial_no
        )
        INSERT INTO qb_accounts (
            qb_account_number, qb_name, qb_account_type, qb_bank_account_number, qb_description, source_serial
        )
        SELECT d.qb_account_number, d.qb_name, d.qb_account_type, d.qb_bank_account_number, d.qb_description, d.qb_serial_no
        FROM distinct_accts d
        LEFT JOIN qb_accounts q ON q.qb_account_number = d.qb_account_number
        WHERE q.id IS NULL
        RETURNING id, qb_account_number, qb_name
        """
    )
    inserted = cur.fetchall()
    print(f'Inserted {len(inserted)} new qb accounts')
    for row in inserted[:5]:
        print(f"  + {row['qb_account_number']}: {row['qb_name']}")

    conn.commit()
    print('\n[OK] Commit complete')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
