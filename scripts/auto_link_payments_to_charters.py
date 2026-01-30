#!/usr/bin/env python3
"""
auto_link_payments_to_charters.py
Automatically links unlinked payment records to charters using reserve_number, charter_date, and client_id.
"""
import psycopg2
from datetime import datetime

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def link_payments():
    conn = get_connection()
    cur = conn.cursor()
    # Manually link Square payment to reservation 019527
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", ("019527",))
    charter_row = cur.fetchone()
    if charter_row:
        charter_id = charter_row[0]
        cur.execute("""
            UPDATE payments SET charter_id = %s WHERE payment_key = %s
        """, (charter_id, "LzbUFckE7ikXsVUG5NbeCHlpTfTZY"))
        print("Manually linked Square payment LzbUFckE7ikXsVUG5NbeCHlpTfTZY to reservation 019527.")
    conn = get_connection()
    cur = conn.cursor()
    # Special case: manually link Square payment to reservation 019493
    # Find charter_id for reserve_number 019493
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", ("019493",))
    charter_row = cur.fetchone()
    if charter_row:
        charter_id = charter_row[0]
        # Update payment with payment_key 'JwCoxKHG7i6JBezXDGpasRSZidQZY'
        cur.execute("""
            UPDATE payments SET charter_id = %s WHERE payment_key = %s
        """, (charter_id, "JwCoxKHG7i6JBezXDGpasRSZidQZY"))
        print("Manually linked Square payment JwCoxKHG7i6JBezXDGpasRSZidQZY to reservation 019493.")

    # Continue with normal auto-linking
    cur.execute('''
        SELECT payment_id, reserve_number, payment_date, amount, client_id
        FROM payments
        WHERE reserve_number IS NULL AND reserve_number IS NOT NULL
    ''')
    payments = cur.fetchall()
    linked = 0
    for payment_id, reserve_number, payment_date, amount, client_id in payments:
        cur.execute('''
            SELECT charter_id FROM charters
            WHERE reserve_number = %s
        ''', (reserve_number,))
        row = cur.fetchone()
        if row:
            charter_id = row[0]
            cur.execute('''
                UPDATE payments SET charter_id = %s WHERE payment_id = %s
            ''', (charter_id, payment_id))
            linked += 1
            continue
        if payment_date and client_id:
            cur.execute('''
                SELECT charter_id FROM charters
                WHERE charter_date = %s AND client_id = %s
            ''', (payment_date, client_id))
            row = cur.fetchone()
            if row:
                charter_id = row[0]
                cur.execute('''
                    UPDATE payments SET charter_id = %s WHERE payment_id = %s
                ''', (charter_id, payment_id))
                linked += 1
    conn.commit()
    print(f"Linked {linked} payments to charters.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    link_payments()
