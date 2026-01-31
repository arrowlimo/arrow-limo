#!/usr/bin/env python3
"""Check Liquor Town and Wholesale Club database variants."""

import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Check variants
cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as count,
        ROUND(SUM(debit_amount)::numeric, 2) as total,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IN ('Liquor Town', 'LiquorT own', 'Wholesale Club', 'Wholesale Cluq')
    GROUP BY vendor_extracted
    ORDER BY vendor_extracted;
""")

print("\n=== LIQUOR TOWN & WHOLESALE CLUB VARIANTS ===\n")
for row in cur.fetchall():
    vendor, count, total, first, last = row
    print(f"{vendor:25} | Count: {count:2} | Total: ${total:>10.2f} | {first} to {last}")

# Also check if there are any similar naming issues
print("\n=== CHECKING FOR TYPOS ===\n")

typos = {
    'Wholesale Cluq': 'Wholesale Club',
    'LiquorT own': 'Liquor Town'
}

for typo, correct in typos.items():
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '0228362'
        AND vendor_extracted = %s
    """, (typo,))
    count = cur.fetchone()[0]
    if count > 0:
        print(f"✓ Found {count} transactions with typo '{typo}' → should be '{correct}'")

conn.close()
