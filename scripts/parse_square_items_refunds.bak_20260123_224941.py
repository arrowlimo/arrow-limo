#!/usr/bin/env python3
"""
Parse Square items-YYYY*.csv reports to extract refund transactions.

Expected columns:
- Date, Time, Time Zone
- Event Type (filter for 'Refund')
- Gross Sales (negative for refunds)
- Transaction ID, Payment ID
- Customer Name, Customer ID
- Notes (reason for refund)
- Card Brand, PAN Suffix

Output:
- Insert into charter_refunds table
- Generate summary CSV
"""
import os
import csv
import re
from datetime import datetime
from decimal import Decimal
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

REPORTS_DIR = r'L:\limo\Square reports'
OUTPUT_CSV = r'l:\limo\reports\square_refunds_extracted.csv'

RESERVE_RE = re.compile(r'\b(\d{6})\b')
MONEY_STRIP = ['$',',','CA']

def normalize_amount(v):
    if not v: return Decimal('0')
    s = str(v).strip()
    for ch in MONEY_STRIP: s = s.replace(ch,'')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    if s.startswith('-'):
        s = s[1:]  # Store as positive refund amount
    try:
        return Decimal(s)
    except Exception:
        return Decimal('0')

def parse_date(date_str, time_str):
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        return dt.date()
    except Exception:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def extract_reserve_from_notes(notes, customer_name):
    """Try to extract reserve number from notes or customer name."""
    combined = f"{notes or ''} {customer_name or ''}"
    m = RESERVE_RE.search(combined)
    if m:
        return m.group(1)
    return None

def link_to_charter(cur, reserve_number, payment_id_square):
    """Link refund to charter via reserve_number or square_payment_id."""
    charter_id = None
    payment_id = None
    
    if reserve_number:
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_number,))
        r = cur.fetchone()
        if r:
            charter_id = r[0]
    
    if payment_id_square:
        cur.execute("SELECT payment_id, reserve_number, charter_id FROM payments WHERE square_payment_id = %s LIMIT 1", (payment_id_square,))
        r = cur.fetchone()
        if r:
            payment_id = r[0]
            if not reserve_number and r[1]:
                reserve_number = r[1]
            if not charter_id and r[2]:
                charter_id = r[2]
            elif not charter_id and reserve_number:
                cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_number,))
                r2 = cur.fetchone()
                if r2:
                    charter_id = r2[0]
    
    return reserve_number, charter_id, payment_id

def parse_items_file(filepath):
    """Parse a single items-YYYY*.csv file for refunds."""
    refunds = []
    
    if not os.path.exists(filepath):
        return refunds
    
    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            event_type = row.get('Event Type', '').strip()
            if event_type != 'Refund':
                continue
            
            # Extract fields
            date_str = row.get('Date', '').strip()
            time_str = row.get('Time', '').strip()
            refund_date = parse_date(date_str, time_str)
            
            if not refund_date:
                continue
            
            gross_sales = row.get('Gross Sales', '').strip()
            amount = normalize_amount(gross_sales)
            
            if amount == 0:
                continue
            
            transaction_id = row.get('Transaction ID', '').strip()
            payment_id_square = row.get('Payment ID', '').strip()
            customer_name = row.get('Customer Name', '').strip()
            customer_id = row.get('Customer ID', '').strip()
            notes = row.get('Notes', '').strip()
            card_brand = row.get('Card Brand', '').strip()
            pan_suffix = row.get('PAN Suffix', '').strip()
            
            # Try to extract reserve number
            reserve_number = extract_reserve_from_notes(notes, customer_name)
            
            refunds.append({
                'refund_date': refund_date,
                'amount': amount,
                'reserve_number': reserve_number,
                'payment_id_square': payment_id_square,
                'transaction_id': transaction_id,
                'customer_name': customer_name,
                'customer_id': customer_id,
                'notes': notes,
                'card_brand': card_brand,
                'pan_suffix': pan_suffix,
                'source_file': os.path.basename(filepath)
            })
    
    return refunds

def import_refunds(write=False):
    """Scan all items-*.csv files and import refunds."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Scan for items-*.csv files
    files = []
    for fn in os.listdir(REPORTS_DIR):
        if fn.startswith('items-') and fn.endswith('.csv'):
            files.append(os.path.join(REPORTS_DIR, fn))
    
    files.sort()
    
    print(f"Found {len(files)} items-*.csv files")
    
    all_refunds = []
    for fp in files:
        print(f"  Parsing: {os.path.basename(fp)}")
        refunds = parse_items_file(fp)
        print(f"    → {len(refunds)} refunds")
        all_refunds.extend(refunds)
    
    print(f"\nTotal refunds extracted: {len(all_refunds)}")
    print(f"Total amount: ${sum(r['amount'] for r in all_refunds):,.2f}")
    
    # Link to charters and insert
    inserted = 0
    skipped_duplicate = 0
    
    for refund in all_refunds:
        reserve_number, charter_id, payment_id = link_to_charter(
            cur, 
            refund['reserve_number'], 
            refund['payment_id_square']
        )
        
        # Check if already exists
        cur.execute("""
            SELECT 1 FROM charter_refunds
            WHERE refund_date = %s 
              AND amount = %s 
              AND COALESCE(square_payment_id, '') = COALESCE(%s, '')
              AND source_file = %s
        """, (refund['refund_date'], refund['amount'], refund['payment_id_square'], refund['source_file']))
        
        if cur.fetchone():
            skipped_duplicate += 1
            continue
        
        # Insert
        description = f"{refund['notes']} | {refund['card_brand']} {refund['pan_suffix']}"
        
        cur.execute("""
            INSERT INTO charter_refunds
            (refund_date, amount, reserve_number, charter_id, payment_id, 
             square_payment_id, description, customer, source_file, reference)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            refund['refund_date'],
            refund['amount'],
            reserve_number,
            charter_id,
            payment_id,
            refund['payment_id_square'],
            description,
            refund['customer_name'],
            refund['source_file'],
            refund['transaction_id']
        ))
        
        inserted += 1
    
    if write:
        conn.commit()
        print(f"\n✓ Inserted {inserted} new refunds into charter_refunds")
        print(f"  Skipped {skipped_duplicate} duplicates")
    else:
        conn.rollback()
        print(f"\nDRY RUN: Would insert {inserted} new refunds")
        print(f"  Would skip {skipped_duplicate} duplicates")
    
    # Export to CSV
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'refund_date', 'amount', 'reserve_number', 'customer_name', 
            'customer_id', 'notes', 'payment_id_square', 'transaction_id', 
            'card_brand', 'pan_suffix', 'source_file'
        ])
        writer.writeheader()
        writer.writerows(all_refunds)
    
    print(f"\n✓ Exported to: {OUTPUT_CSV}")
    
    # Summary stats
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM charter_refunds")
    total_count, total_amount = cur.fetchone()
    print(f"\nCurrent charter_refunds table: {total_count} rows, ${total_amount:,.2f}")
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0) 
        FROM charter_refunds 
        WHERE charter_id IS NOT NULL
    """)
    linked_count, linked_amount = cur.fetchone()
    print(f"  Linked to charters: {linked_count} rows, ${linked_amount:,.2f}")
    
    cur.close()
    conn.close()

def main():
    import argparse
    ap = argparse.ArgumentParser(description='Parse Square items-*.csv for refunds')
    ap.add_argument('--write', action='store_true', help='Commit to database')
    args = ap.parse_args()
    
    print('=' * 100)
    print('PARSE SQUARE ITEMS REPORTS FOR REFUNDS')
    print('=' * 100)
    
    import_refunds(write=args.write)

if __name__ == '__main__':
    main()
