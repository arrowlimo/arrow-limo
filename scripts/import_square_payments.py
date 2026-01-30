#!/usr/bin/env python3
"""
import_square_payments.py
Imports Square payment transactions from CSV, deduplicates by Payment ID, and links to charters using Notes/Details fields.
"""
import csv
import psycopg2
from datetime import datetime
import re

# Config
CSV_PATH = r"L:/limo/new_system/receipts/items-2025-07-01-2025-08-16.csv"
DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

def extract_reserve_number(notes):
    if not notes:
        return None
    m = re.search(r'\b(\d{5,6})\b', notes)
    if m:
        return m.group(1)
    return None

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def import_square_payments():
    seen_payment_ids = set()
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    conn = get_connection()
    cur = conn.cursor()
    imported = 0
    for row in rows:
        payment_id = row.get('Payment ID')
        if not payment_id or payment_id in seen_payment_ids:
            continue  # skip duplicates
        seen_payment_ids.add(payment_id)
        date = row.get('Date')
        amount_raw = row.get('Gross Sales') or row.get('Net Sales')
        # Clean amount: remove $ and commas, convert to float
        if amount_raw:
            amount_clean = amount_raw.replace('$','').replace(',','').strip()
            try:
                amount = float(amount_clean)
            except Exception:
                amount = None
        else:
            amount = None
        notes = row.get('Notes') or row.get('Details')
        reserve_number = extract_reserve_number(notes)
        # Try to find charter by reserve_number
        charter_id = None
        if reserve_number:
            cur.execute('SELECT charter_id FROM charters WHERE reserve_number = %s', (reserve_number,))
            res = cur.fetchone()
            if res:
                charter_id = res[0]
        # Insert or update payment record
        cur.execute('''
            SELECT payment_id FROM payments WHERE payment_key = %s
        ''', (payment_id,))
        exists = cur.fetchone()
        if exists:
            cur.execute('''
                UPDATE payments SET amount = %s, payment_date = %s, charter_id = %s WHERE payment_key = %s
            ''', (amount, date, charter_id, payment_id))
        else:
            cur.execute('''
                INSERT INTO payments (amount, payment_date, charter_id, payment_key, payment_method, last_updated, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ''', (amount, date, charter_id, payment_id, 'credit_card'))
        imported += 1
    conn.commit()
    print(f"Imported/updated {imported} Square payments.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    import_square_payments()
