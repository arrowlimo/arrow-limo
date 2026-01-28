#!/usr/bin/env python3
"""
Verify Oct 1, 2012 transactions against actual banking records.
Check if these exist in original bank statements.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("VERIFY OCT 1, 2012 AGAINST ACTUAL BANK STATEMENT DATA")
print("=" * 80)

# Check what import sources exist
print("\n1. CHECKING IMPORT SOURCES FOR OCT 2012:")
print("-" * 80)

cur.execute("""
    SELECT 
        CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
        reconciliation_status,
        COUNT(*) as count
    FROM banking_transactions
    WHERE transaction_date >= '2012-10-01' AND transaction_date <= '2012-10-31'
    GROUP BY bank_id, reconciliation_status
    ORDER BY bank_id, reconciliation_status
""")

for bank, status, count in cur.fetchall():
    print(f"  {bank:7} | {status or 'ACTIVE':20} | {count:4} transactions")

# Get the suspect transactions
print("\n\n2. OCT 1, 2012 TRANSACTIONS - DETAILED VERIFICATION:")
print("-" * 80)

tx_ids = [57852, 57853, 69387, 69388, 69389, 69390, 69391, 69392, 69393, 
          69394, 69395, 69396, 69397, 69398, 69399, 69400, 69401, 69402, 69403]

for tx_id in tx_ids:
    cur.execute("""
        SELECT transaction_date, debit_amount, credit_amount, description,
               CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
               reconciliation_status
        FROM banking_transactions
        WHERE transaction_id = %s
    """, (tx_id,))
    
    result = cur.fetchone()
    if not result:
        continue
    
    date, debit, credit, desc, bank, status = result
    amount = debit if debit else credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    
    print(f"\nTX {tx_id:6d} | {bank:7} | {date} | {tx_type:6} | ${amount:>10,.2f}")
    print(f"  Description: {desc}")
    
    # Look for matching transactions on same date with similar amount/description
    cur.execute("""
        SELECT transaction_id, description,
               CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
               reconciliation_status,
               CASE WHEN debit_amount IS NOT NULL THEN 'DEBIT' ELSE 'CREDIT' END as type
        FROM banking_transactions
        WHERE transaction_date = %s
          AND ((debit_amount = %s AND %s IS NOT NULL) OR (credit_amount = %s AND %s IS NULL))
          AND transaction_id != %s
    """, (date, amount, debit, amount, debit, tx_id))
    
    matches = cur.fetchall()
    if matches:
        print(f"  ⚠️  MATCHING TRANSACTIONS (same date/amount):")
        for m_id, m_desc, m_bank, m_status, m_type in matches:
            print(f"     TX {m_id:6d} | {m_bank:7} | {m_type:6} | {m_desc[:50]} [{m_status or 'ACTIVE'}]")
    
    # Check if this looks like QB import
    is_qb_pattern = (
        bank == 'Unknown' or
        'Cheque Expense' in desc or
        status == 'QB_DUPLICATE'
    )
    
    # Check if Scotia Bank (should be fully verified)
    if bank == 'SCOTIA':
        print(f"  ⚠️  SCOTIA BANK - Should be fully matched. No receipt = likely QB duplicate")
    elif bank == 'CIBC':
        print(f"  ℹ️  CIBC 8362 - Not fully verified. Might be real unmatched transaction")

# Check for PDF/CSV source verification
print("\n\n3. CHECKING FOR ORIGINAL BANK STATEMENT VERIFICATION:")
print("-" * 80)

print("\nScotia Bank Oct 2012 statement files:")
import glob
scotia_files = glob.glob("L:/limo/**/Scotia*2012*10*.pdf", recursive=True)
scotia_files.extend(glob.glob("L:/limo/**/Scotia*Oct*2012*.csv", recursive=True))
scotia_files.extend(glob.glob("L:/limo/**/*903990106011*2012*10*.pdf", recursive=True))

if scotia_files:
    for f in scotia_files[:5]:
        print(f"  Found: {f}")
else:
    print("  No Scotia Oct 2012 statement files found")

print("\nCIBC Oct 2012 statement files:")
cibc_files = glob.glob("L:/limo/**/CIBC*2012*10*.pdf", recursive=True)
cibc_files.extend(glob.glob("L:/limo/**/CIBC*Oct*2012*.csv", recursive=True))
cibc_files.extend(glob.glob("L:/limo/**/*0228362*2012*10*.pdf", recursive=True))

if cibc_files:
    for f in cibc_files[:5]:
        print(f"  Found: {f}")
else:
    print("  No CIBC Oct 2012 statement files found")

cur.close()
conn.close()
