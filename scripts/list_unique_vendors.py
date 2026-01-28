"""
List all unique vendor names grouped for review
Exclude: cash withdrawals, interest, fees, bank charges
"""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== UNIQUE VENDOR NAMES (Excluding Bank Operations) ===\n")

# Get all unique vendor names, excluding bank operations
cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as transaction_count,
        SUM(debit_amount) as total_spent,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    AND vendor_extracted !~ '(?i)(cash|withdrawal|interest|fee|charge|service|overdraft|correction|reversal|memo|transfer|deposit|payment)'
    GROUP BY vendor_extracted
    ORDER BY vendor_extracted
""")

vendors = cur.fetchall()

print(f"Total unique vendors: {len(vendors)}\n")
print("=" * 120)
print(f"{'Vendor Name':<50} {'Count':>6} {'Total Spent':>15} {'First':>12} {'Last':>12}")
print("=" * 120)

# Group by first letter for easier review
current_letter = ''
vendor_count_by_letter = {}

for vendor, count, total, first, last in vendors:
    first_letter = vendor[0].upper() if vendor else '?'
    
    if first_letter != current_letter:
        if current_letter:
            print()  # Blank line between letter groups
        current_letter = first_letter
        print(f"\n--- {current_letter} ---")
    
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"{vendor:<50} {count:>6} {total_str:>15} {first!s:>12} {last!s:>12}")
    
    # Track counts by letter
    if first_letter not in vendor_count_by_letter:
        vendor_count_by_letter[first_letter] = 0
    vendor_count_by_letter[first_letter] += 1

# Summary by letter
print("\n" + "=" * 120)
print("\n=== VENDOR COUNT BY LETTER ===\n")

for letter in sorted(vendor_count_by_letter.keys()):
    count = vendor_count_by_letter[letter]
    print(f"{letter}: {count:>3} vendors")

print(f"\nTotal: {len(vendors)} unique vendors")

# Also show vendors with most transactions
print("\n\n=== TOP 30 VENDORS BY TRANSACTION COUNT ===\n")
print("=" * 100)
print(f"{'Vendor Name':<50} {'Transactions':>12} {'Total Spent':>15}")
print("=" * 100)

cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as transaction_count,
        SUM(debit_amount) as total_spent
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    AND vendor_extracted !~ '(?i)(cash|withdrawal|interest|fee|charge|service|overdraft|correction|reversal|memo|transfer|deposit|payment)'
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
    LIMIT 30
""")

top_vendors = cur.fetchall()

for vendor, count, total in top_vendors:
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"{vendor:<50} {count:>12,} {total_str:>15}")

# Export to CSV for easier review
print("\n\n=== EXPORTING TO CSV ===\n")

import csv
from datetime import datetime

csv_file = f"l:\\limo\\reports\\unique_vendors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Vendor Name', 'Transaction Count', 'Total Spent', 'First Date', 'Last Date'])
    
    cur.execute("""
        SELECT 
            vendor_extracted,
            COUNT(*) as transaction_count,
            SUM(debit_amount) as total_spent,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND vendor_extracted IS NOT NULL
        AND vendor_extracted != ''
        AND vendor_extracted !~ '(?i)(cash|withdrawal|interest|fee|charge|service|overdraft|correction|reversal|memo|transfer|deposit|payment)'
        GROUP BY vendor_extracted
        ORDER BY vendor_extracted
    """)
    
    for row in cur.fetchall():
        writer.writerow(row)

print(f"✓ Exported to: {csv_file}")

cur.close()
conn.close()
