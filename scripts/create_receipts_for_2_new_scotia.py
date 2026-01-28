#!/usr/bin/env python3
"""Create receipts for the 2 newly imported Scotia transactions."""

import psycopg2
import pandas as pd
import os

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def categorize_banking_transaction(description):
    """Auto-categorize Scotia banking transactions."""
    desc_upper = description.upper()
    
    if any(x in desc_upper for x in ['CHQ', 'CHEQUE', 'CHECK']):
        return 'Cheque Payment'
    elif any(x in desc_upper for x in ['ATM', 'CASH WITH', 'WITHDRAWAL']):
        return 'Cash Withdrawal'
    elif any(x in desc_upper for x in ['FEE', 'CHARGE', 'OD FEE']):
        return 'Bank Fees'
    elif any(x in desc_upper for x in ['DEPOSIT', 'TRANSFER IN', 'PAYMENT']):
        return 'Deposit'
    elif any(x in desc_upper for x in ['TRANSFER', 'INTER-ACCOUNT']):
        return 'Inter-Account Transfer'
    elif any(x in desc_upper for x in ['DEBIT', 'MCARD', 'VCARD']):
        return 'Debit Card'
    else:
        return 'Business Expense'

def calculate_gst(gross_amount):
    """Calculate GST from gross amount (GST included in total)."""
    gross_amount = float(gross_amount)
    if gross_amount == 0:
        return 0, 0
    gst = gross_amount * 0.05 / 1.05
    net = gross_amount - gst
    return round(gst, 2), round(net, 2)

# Connect to database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("CREATING RECEIPTS FOR 2 NEW SCOTIA TRANSACTIONS")
print("=" * 100)

# Get the 2 newly imported transactions
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
      AND (description LIKE '%Run%N On Empty%' OR description LIKE '%Cash Withdrawal%')
      AND transaction_date IN ('2012-12-03'::date, '2012-12-14'::date)
    ORDER BY transaction_date
""")

rows = cur.fetchall()

print(f"\nFound {len(rows)} new Scotia transactions:\n")

created = 0
for tx_id, tx_date, description, debit, credit in rows:
    # Determine if debit (expense) or credit (income)
    if debit and debit > 0:
        gross_amount = debit
        receipt_type = 'Debit'
    else:
        gross_amount = credit
        receipt_type = 'Credit'
    
    # Calculate GST
    gst, net = calculate_gst(abs(gross_amount))
    
    # Categorize
    category = categorize_banking_transaction(description)
    
    print(f"  {tx_date} | {description:30s} | ${gross_amount:>8.2f}")
    print(f"    Category: {category}")
    print(f"    GST: ${gst:.2f}, Net: ${net:.2f}")
    
    # Insert receipt
    try:
        cur.execute("""
            INSERT INTO receipts
            (receipt_date, vendor_name, description, gross_amount, gst_amount, net_amount, 
             category, mapped_bank_account_id, banking_transaction_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING receipt_id
        """, (
            tx_date,
            description[:50],
            description,
            abs(gross_amount),
            gst,
            net,
            category,
            2,  # Scotia account_id
            tx_id
        ))
        
        receipt_id = cur.fetchone()[0]
        print(f"    ✓ Receipt ID: {receipt_id}\n")
        created += 1
    except Exception as e:
        print(f"    ❌ Error: {e}\n")

try:
    conn.commit()
    print("=" * 100)
    print(f"✓ CREATED {created} RECEIPTS")
    print("=" * 100)
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
          AND mapped_bank_account_id = 2
    """)
    total = cur.fetchone()[0]
    print(f"\nDatabase now has {total} Scotia 2012 receipts")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Commit failed: {e}")

finally:
    cur.close()
    conn.close()
