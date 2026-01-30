#!/usr/bin/env python
"""List all banking vendors."""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get all banking vendors sorted by amount
cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as txn_count,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_spent
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted NOT IN ('Customer', 'Square', 'Business Expense', 'Sales', 
                                 'Unknown', 'Cheque', 'Deposit', 'Transfer', 
                                 'Banking', 'Fee', 'Interest')
    AND vendor_extracted NOT LIKE '%Cheque%'
    GROUP BY vendor_extracted
    ORDER BY total_spent DESC
""")

vendors = cur.fetchall()

print("\n" + "=" * 80)
print("COMPLETE VENDOR LIST - BANKING TRANSACTIONS (CIBC Account 0228362)")
print("=" * 80 + "\n")

for i, vendor in enumerate(vendors, 1):
    print(f"{i:3}. {vendor['vendor_extracted']:45} | {vendor['txn_count']:4} txn | ${vendor['total_spent']:12,.2f}")

print(f"\n{'-' * 80}")
print(f"Total unique vendors: {len(vendors)}")
print(f"Total transactions: {sum(v['txn_count'] for v in vendors)}")
print(f"Total spent: ${sum(v['total_spent'] for v in vendors):,.2f}")
print("=" * 80 + "\n")

conn.close()
