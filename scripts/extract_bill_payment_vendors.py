#!/usr/bin/env python3
"""Extract vendor names from banking descriptions for BILL PAYMENT receipts."""

import os
import psycopg2
from dotenv import load_dotenv
import re

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Find BILL PAYMENT receipts with NULL banking_transaction_id
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.description, r.gross_amount, r.receipt_date
    FROM receipts r
    WHERE r.vendor_name LIKE '%BILL PAYMENT%'
    AND r.banking_transaction_id IS NULL
    ORDER BY r.receipt_date DESC
    LIMIT 20
""")
bill_payments = cur.fetchall()

print("=" * 100)
print("BILL PAYMENT RECEIPTS WITH NO BANKING LINK")
print("=" * 100)
print(f"\nFound {len(bill_payments)} BILL PAYMENT receipts:\n")

for receipt_id, vendor, desc, amount, date in bill_payments:
    print(f"Receipt {receipt_id} | {date} | ${amount:.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  Desc: {desc}")
    
    # Try to extract vendor name from description
    if desc:
        # Patterns for BILL PAYMENT descriptions
        patterns = [
            r'BILL PAYMENT\s+-\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\d{2,4}|$)',
            r'BILL PAYMENT\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\d{2,4}|$)',
            r'([A-Z][A-Za-z\s&,\.]+?)\s+BILL PAYMENT',
        ]
        
        extracted = None
        for pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Clean up
                extracted = re.sub(r'\s+', ' ', extracted)
                extracted = extracted.rstrip(',').strip()
                break
        
        if extracted and extracted.lower() != "bill payment":
            print(f"  🎯 Extracted: {extracted}")
        elif extracted:
            print(f"  ❌ Could not extract specific vendor")
    print()

# Check for banking transactions with "BILL PAYMENT" descriptions
print("\n" + "=" * 100)
print("BANKING TRANSACTIONS WITH BILL PAYMENT DESCRIPTIONS")
print("=" * 100 + "\n")

cur.execute("""
    SELECT bt.transaction_id, bt.transaction_date, bt.description, 
           bt.debit_amount, bt.credit_amount
    FROM banking_transactions bt
    WHERE bt.description LIKE '%BILL PAYMENT%'
    ORDER BY bt.transaction_date DESC
    LIMIT 20
""")
bank_bills = cur.fetchall()

print(f"Found {len(bank_bills)} banking transactions:\n")

for trans_id, date, desc, debit, credit in bank_bills:
    amount = debit if debit > 0 else credit
    print(f"Transaction {trans_id} | {date} | ${amount:.2f}")
    print(f"  Desc: {desc}")
    
    # Try to extract vendor from banking description
    if desc:
        patterns = [
            r'BILL PAYMENT\s+-\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\d{2,4}|$)',
            r'BILL PAYMENT\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\d{2,4}|$)',
            r'([A-Z][A-Za-z\s&,\.]+?)\s+BILL PAYMENT',
        ]
        
        extracted = None
        for pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                extracted = re.sub(r'\s+', ' ', extracted)
                extracted = extracted.rstrip(',').strip()
                break
        
        if extracted and extracted.lower() != "bill payment":
            print(f"  🎯 Extracted: {extracted}")
    print()

cur.close()
conn.close()

print("✅ Analysis complete")
