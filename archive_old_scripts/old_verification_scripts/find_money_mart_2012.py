#!/usr/bin/env python3
"""Find and analyze Money Mart prepaid Visa transaction from 2012."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("MONEY MART PREPAID VISA TRANSACTION - SEPTEMBER 12, 2012")
print("="*100)

# Search for the specific transaction
print("\n1. Searching for Money Mart transaction on 09/12/2012...")
print("-"*100)

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        gl_account_code,
        gl_account_name,
        description,
        banking_transaction_id
    FROM receipts
    WHERE vendor_name ILIKE '%money%mart%'
    AND receipt_date BETWEEN '2012-09-01' AND '2012-09-30'
    ORDER BY receipt_date
""")

sept_2012_transactions = cur.fetchall()

if sept_2012_transactions:
    print(f"{'ID':<10} {'Date':<12} {'Vendor':<25} {'Amount':<12} {'GL Code':<10} {'GL Name':<30}")
    print("-"*100)
    for rec_id, date, vendor, amount, gl_code, gl_name, desc, bank_id in sept_2012_transactions:
        vendor_display = (vendor or "")[:25]
        gl_name_display = (gl_name or "")[:30]
        print(f"{rec_id:<10} {str(date):<12} {vendor_display:<25} ${amount:<11,.2f} {gl_code or 'NONE':<10} {gl_name_display:<30}")
        if desc:
            print(f"  Description: {desc}")
else:
    print("No Money Mart transactions found in September 2012")
    
    # Try broader search
    print("\nSearching all Money Mart transactions near that date...")
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            gl_account_code,
            gl_account_name,
            description
        FROM receipts
        WHERE vendor_name ILIKE '%money%mart%'
        AND receipt_date BETWEEN '2012-08-01' AND '2012-10-31'
        AND (gross_amount BETWEEN 800 AND 1000 OR gross_amount BETWEEN 700 AND 800)
        ORDER BY receipt_date
    """)
    
    nearby = cur.fetchall()
    if nearby:
        print(f"\n{'ID':<10} {'Date':<12} {'Vendor':<25} {'Amount':<12} {'GL':<10} {'GL Name'}")
        print("-"*100)
        for rec_id, date, vendor, amount, gl_code, gl_name, desc in nearby:
            print(f"{rec_id:<10} {str(date):<12} {vendor[:25]:<25} ${amount:<11,.2f} {gl_code or 'NONE':<10} {gl_name or ''}")

# 2. Explain proper GL coding
print("\n" + "="*100)
print("2. PROPER GL CODING FOR MONEY MART PREPAID VISA LOADS")
print("="*100)

print("""
Money Mart prepaid Visa card loads are NOT expenses - they are ASSET TRANSFERS.

When you load money onto a prepaid Visa card:
  - You're converting cash → prepaid card balance
  - Both are ASSETS, not expenses
  - No impact on profit/loss

CORRECT GL CODING:
  GL 1135 - Prepaid Visa Cards (ASSET account)

TRANSACTION BREAKDOWN:
  Date: September 12, 2012
  Visa card load: $900.00
  Cash fee: $750.00 (unclear - is this a fee or another load?)
  
If $750 is a LOAD:
  - Debit GL 1135 (Prepaid Visa Cards): $900.00
  - Debit GL 1135 (Prepaid Visa Cards): $750.00
  - Credit GL 1010 (Cash): $1,650.00
  
If $750 is a FEE for the $900 load:
  - Debit GL 1135 (Prepaid Visa Cards): $900.00
  - Debit GL 5710 (Bank Fees): $750.00
  - Credit GL 1010 (Cash): $1,650.00
  
  (But $750 fee on $900 load = 83% fee - seems very high!)

Most likely: TWO separate loads
  - Load #1: $900.00 to prepaid Visa
  - Load #2: $750.00 to prepaid Visa (or cash withdrawn?)
""")

# 3. Check current GL code for Money Mart transactions
print("\n" + "="*100)
print("3. CURRENT GL CODING FOR ALL MONEY MART TRANSACTIONS")
print("="*100)

cur.execute("""
    SELECT 
        gl_account_code,
        gl_account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name ILIKE '%money%mart%'
    GROUP BY gl_account_code, gl_account_name
    ORDER BY count DESC
""")

print(f"{'GL Code':<10} {'GL Name':<45} {'Count':<10} {'Total Amount'}")
print("-"*100)

for gl_code, gl_name, count, total in cur.fetchall():
    gl_name_display = (gl_name or "NO NAME")[:45]
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"{gl_code or 'NONE':<10} {gl_name_display:<45} {count:<10} {total_str}")

# 4. Recommendation
print("\n" + "="*100)
print("4. RECOMMENDED ACTION")
print("="*100)

print("""
STEP 1: Find the specific transaction(s)
  - Search for Money Mart on 09/12/2012
  - Identify if it's one or two receipts ($900 + $750)

STEP 2: Recode to proper GL account
  If it's a prepaid card load:
    UPDATE receipts 
    SET gl_account_code = '1135',
        gl_account_name = 'Prepaid Visa Cards'
    WHERE receipt_id = [the receipt ID]
  
  If it's a cash withdrawal/advance:
    - Keep in personal draws or owner loan account

STEP 3: Verify GL 1135 exists
  - Check if GL 1135 (Prepaid Visa Cards) exists in chart_of_accounts
  - If not, create it as an Asset account

Would you like me to:
a) Search more broadly for this transaction?
b) Recode Money Mart prepaid loads to GL 1135?
c) Create the GL 1135 account if missing?
""")

conn.close()
