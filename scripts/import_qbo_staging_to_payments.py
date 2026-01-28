#!/usr/bin/env python3
"""
Import all unmatched CIBC .qbo transactions from staging into the payments table.
"""
import os
import psycopg2
from datetime import datetime

STAGING_TABLE = "cibc_qbo_staging"
PAYMENTS_TABLE = "payments"

# Map QBO transaction types to payment methods
TRNTYPE_MAP = {
    'DEBIT': 'bank_transfer',
    'CREDIT': 'bank_transfer',
    'CHECK': 'check',
    'POS': 'debit_card',
    'ATM': 'debit_card',
    'FEE': 'bank_transfer',
    'SERVICE CHARGE': 'bank_transfer',
    'OVERDRAFT': 'bank_transfer',
}

def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', '')
    )

def import_unmatched_staging(conn):
    with conn.cursor() as cur:
        # Find unmatched staging records
        cur.execute(f"""
            SELECT s.id, s.file_name, s.trntype, s.dtposted, s.trnamt, s.fitid, s.name, s.memo
            FROM {STAGING_TABLE} s
            LEFT JOIN {PAYMENTS_TABLE} p
              ON s.dtposted = p.payment_date AND s.trnamt = p.amount
            WHERE p.payment_id IS NULL
        """)
        rows = cur.fetchall()
        print(f"Unmatched transactions to import: {len(rows)}")
        imported = 0
        for r in rows:
            _, file_name, trntype, dtposted, trnamt, fitid, name, memo = r
            payment_method = TRNTYPE_MAP.get(trntype.upper(), 'bank_transfer')
            # Insert into payments table
            cur.execute(f"""
                INSERT INTO {PAYMENTS_TABLE} (
                    account_number, amount, payment_date, payment_method, payment_key, notes, created_at, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                '903990106011',
                trnamt,
                dtposted,
                payment_method,
                fitid,
                f"QBO Import: {name} | {memo}",
                datetime.now(),
                'paid'
            ))
            imported += 1
        conn.commit()
        print(f"Imported {imported} transactions into payments table.")

def main():
    conn = connect_db()
    import_unmatched_staging(conn)
    conn.close()

if __name__ == "__main__":
    main()
