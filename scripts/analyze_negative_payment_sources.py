"""Analyze all negative payments directly from the database to identify their sources.

Queries payments table for negative amounts and checks:
  1. Payment method distribution
  2. Square transaction linkage (via square_transaction_id, square_payment_id fields)
  3. Payment key patterns
  4. Date ranges

Outputs:
  reports/negative_payments_analysis.csv
  Console summary
"""

import os
import csv
import psycopg2
import psycopg2.extras
from collections import Counter


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Fetch all negative payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_key,
            reserve_number,
            charter_id,
            account_number,
            COALESCE(payment_amount, amount, 0) as amount,
            payment_method,
            payment_date,
            created_at,
            status,
            square_transaction_id,
            square_payment_id,
            authorization_code,
            notes,
            CASE 
                WHEN square_transaction_id IS NOT NULL OR square_payment_id IS NOT NULL THEN 'Square'
                WHEN payment_method ILIKE '%credit%' OR payment_method ILIKE '%card%' THEN 'CreditCard'
                WHEN payment_method ILIKE '%transfer%' OR payment_method = 'etransfer' THEN 'Transfer'
                WHEN payment_method ILIKE '%bank%' THEN 'BankTransfer'
                WHEN payment_method ILIKE '%check%' OR payment_method ILIKE '%cheque%' THEN 'Check'
                WHEN payment_method ILIKE '%cash%' THEN 'Cash'
                WHEN payment_method = 'trade_of_services' THEN 'Trade'
                ELSE 'Other/' || COALESCE(payment_method, 'Unknown')
            END as source_classification
        FROM payments
        WHERE COALESCE(payment_amount, amount, 0) < 0
        ORDER BY payment_date DESC NULLS LAST, payment_id DESC
    """)
    
    rows = cur.fetchall()
    print(f"🔍 Found {len(rows)} negative payments in database")
    
    # Analyze
    sources = Counter(r['source_classification'] for r in rows)
    methods = Counter(r['payment_method'] or 'NULL' for r in rows)
    has_square = sum(1 for r in rows if r['square_transaction_id'] or r['square_payment_id'])
    has_payment_key = sum(1 for r in rows if r['payment_key'])
    
    print(f"\n📊 Source Classification:")
    for src, count in sources.most_common():
        print(f"   {src}: {count}")
    
    print(f"\n📊 Payment Methods (raw):")
    for method, count in methods.most_common(10):
        print(f"   {method}: {count}")
    
    print(f"\n📊 Linkage:")
    print(f"   Has Square ID: {has_square}")
    print(f"   Has payment_key: {has_payment_key}")
    
    # Write CSV
    out_path = 'reports/negative_payments_analysis.csv'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    fieldnames = [
        'payment_id', 'payment_key', 'reserve_number', 'charter_id', 'amount',
        'payment_method', 'payment_date', 'status', 'square_transaction_id',
        'square_payment_id', 'source_classification', 'notes'
    ]
    
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
    
    print(f"\n✓ Analysis written to: {out_path}")
    
    # Show sample Square negatives
    square_negs = [r for r in rows if r['square_transaction_id'] or r['square_payment_id']]
    if square_negs:
        print(f"\n🔍 Sample Square-linked negatives (first 5):")
        for r in square_negs[:5]:
            print(f"   Payment {r['payment_id']}: ${r['amount']:.2f} on {r['payment_date']}")
            print(f"      Square TXN: {r['square_transaction_id']}, Square PAY: {r['square_payment_id']}")
            print(f"      Reserve: {r['reserve_number']}, Method: {r['payment_method']}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
