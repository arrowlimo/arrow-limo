#!/usr/bin/env python3
"""
Ingest car loan payments from David's Excel file.
These are payments David made personally that need to be recorded as loans.
"""

import pandas as pd
import psycopg2
from datetime import datetime
from decimal import Decimal
import re

# Read the Excel file
print("=" * 120)
print("INGESTING CAR LOAN PAYMENTS FROM DAVID'S FILE")
print("=" * 120)
print("\nFile: DAVID UPLOADS/L-5 car loan paid by david_0001.xlsx")
print("These are payments David made personally that need to be recorded as loans to the business.\n")

# Read all sheets from the workbook
xl = pd.ExcelFile('DAVID UPLOADS/L-5 car loan paid by david_0001.xlsx')
print(f"Found {len(xl.sheet_names)} sheets in workbook")
print(f"Sheet names: {', '.join(xl.sheet_names)}\n")

# Look for payment patterns in the data
# Pattern: "Posting Date Description ... installment Payment ... Amount"
payments = []

print("Scanning all sheets for payment transactions...")
print("-" * 120)

for sheet_name in xl.sheet_names:
    print(f"\nProcessing sheet: {sheet_name}")
    df = pd.read_excel('DAVID UPLOADS/L-5 car loan paid by david_0001.xlsx', sheet_name=sheet_name, header=None)
    
    for idx, row in df.iterrows():
        row_str = ' '.join([str(x) for x in row if pd.notna(x)])
        
        # Look for "Installment Payment" or "installment Payment"
        if 'nstallment Payment' in row_str or 'INSTALLMENT PAYMENT' in row_str.upper():
            # Extract date and amount from the row text
            # Pattern: Date ... Installment Payment ... Amount
            
            # Try to find date pattern (MMM DD,YYYY)
            date_match = re.search(r'([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{4})', row_str)
            
            # Try to find amount pattern
            amount_match = re.search(r'(\d+[\d,]*\.?\d*)\s*$', row_str)
            
            if date_match and amount_match:
                month_str = date_match.group(1)
                day = int(date_match.group(2))
                year = int(date_match.group(3))
                amount_str = amount_match.group(1).replace(',', '')
                
                try:
                    payment_date = datetime.strptime(f"{month_str} {day}, {year}", "%b %d, %Y")
                    amount = Decimal(amount_str)
                    
                    payments.append({
                        'date': payment_date,
                        'amount': amount,
                        'description': f'Car Loan Payment - Paid by David Richard',
                        'raw_text': row_str[:100],
                        'sheet': sheet_name
                    })
                    print(f"  Found: {payment_date.strftime('%Y-%m-%d')} - ${amount:,.2f}")
                except Exception as e:
                    print(f"  Error parsing row {idx}: {e}")

print(f"\nTotal payments found: {len(payments)}")

if len(payments) == 0:
    print("\nNo payments found. Let me show you the raw data structure:")
    print("\nFirst 20 rows of Sheet1:")
    df_sample = pd.read_excel('DAVID UPLOADS/L-5 car loan paid by david_0001.xlsx', sheet_name='Sheet1', header=None)
    for idx in range(min(20, len(df_sample))):
        row_data = [str(x) for x in df_sample.iloc[idx] if pd.notna(x)]
        if row_data:
            print(f"Row {idx}: {' | '.join(row_data[:5])}")
    
    print("\n" + "=" * 120)
    print("MANUAL REVIEW REQUIRED")
    print("=" * 120)
    print("Please review the Excel file structure and update the parsing logic.")
    exit(0)

# Calculate totals
total_amount = sum(p['amount'] for p in payments)
date_range = f"{min(p['date'] for p in payments).strftime('%Y-%m-%d')} to {max(p['date'] for p in payments).strftime('%Y-%m-%d')}"

print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print(f"Total payments: {len(payments)}")
print(f"Total amount: ${total_amount:,.2f}")
print(f"Date range: {date_range}")
print(f"Average payment: ${total_amount / len(payments):,.2f}")

# Ask for confirmation
print("\n" + "=" * 120)
print("READY TO INGEST")
print("=" * 120)
print("\nThese payments will be recorded as:")
print("  - Loans FROM David Richard TO the business")
print("  - Category: Loan Payable - David Richard - Vehicle Loan")
print("  - Each payment increases the amount owed to David")
print("\nFirst 5 payments to be ingested:")
for p in sorted(payments, key=lambda x: x['date'])[:5]:
    print(f"  {p['date'].strftime('%Y-%m-%d')}: ${p['amount']:,.2f}")

if len(payments) > 5:
    print(f"  ... and {len(payments) - 5} more payments")

print("\n" + "=" * 120)

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check if we have a david_richard_loans table
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'david_richard_vehicle_loans'
    )
""")
table_exists = cur.fetchone()[0]

if not table_exists:
    print("\nCreating table: david_richard_vehicle_loans")
    cur.execute("""
        CREATE TABLE david_richard_vehicle_loans (
            id SERIAL PRIMARY KEY,
            payment_date DATE NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            description TEXT,
            loan_type VARCHAR(100) DEFAULT 'Vehicle Loan Payment',
            source_file VARCHAR(500),
            raw_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(payment_date, amount)
        )
    """)
    conn.commit()
    print("✓ Table created successfully")

# Insert payments
print("\nInserting payments into database...")
inserted = 0
skipped = 0

for payment in sorted(payments, key=lambda x: x['date']):
    try:
        cur.execute("""
            INSERT INTO david_richard_vehicle_loans 
            (payment_date, amount, description, loan_type, source_file, raw_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (payment_date, amount) DO NOTHING
            RETURNING id
        """, (
            payment['date'],
            payment['amount'],
            payment['description'],
            'Vehicle Loan Payment',
            'DAVID UPLOADS/L-5 car loan paid by david_0001.xlsx',
            payment['raw_text']
        ))
        
        if cur.fetchone():
            inserted += 1
            print(f"  ✓ Inserted: {payment['date'].strftime('%Y-%m-%d')} ${payment['amount']:,.2f}")
        else:
            skipped += 1
            print(f"  ⊘ Skipped (duplicate): {payment['date'].strftime('%Y-%m-%d')} ${payment['amount']:,.2f}")
            
    except Exception as e:
        print(f"  ✗ Error inserting {payment['date']}: {e}")

conn.commit()

print("\n" + "=" * 120)
print("INGESTION COMPLETE")
print("=" * 120)
print(f"\nInserted: {inserted} payments")
print(f"Skipped (duplicates): {skipped} payments")
print(f"Total amount ingested: ${sum(p['amount'] for p in payments[:inserted]):,.2f}")

# Update loan summary
print("\n" + "=" * 120)
print("UPDATED DAVID RICHARD LOAN SUMMARY")
print("=" * 120)

# Get vehicle loan total
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount,
        MIN(payment_date) as first_payment,
        MAX(payment_date) as last_payment
    FROM david_richard_vehicle_loans
""")
vehicle_loan = cur.fetchone()

# Get e-transfer loan total from banking_transactions
cur.execute("""
    SELECT 
        SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as from_david,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as to_david
    FROM banking_transactions
    WHERE description ILIKE '%david%richard%'
       OR description ILIKE '%davidwr@shaw%'
       OR description ILIKE '%davidrichard%'
""")
etransfer_totals = cur.fetchone()

print(f"\n1. VEHICLE LOAN PAYMENTS (from this file):")
if vehicle_loan[0] > 0:
    print(f"   Payments: {vehicle_loan[0]}")
    print(f"   Total: ${vehicle_loan[1]:,.2f}")
    print(f"   Period: {vehicle_loan[2]} to {vehicle_loan[3]}")
else:
    print("   No vehicle loan payments recorded")

print(f"\n2. E-TRANSFER LOANS (from banking transactions):")
print(f"   From David: ${etransfer_totals[0] or 0:,.2f}")
print(f"   To David: ${etransfer_totals[1] or 0:,.2f}")
print(f"   Net e-transfer: ${(etransfer_totals[0] or 0) - (etransfer_totals[1] or 0):,.2f}")

print(f"\n3. TOTAL AMOUNT OWED TO DAVID RICHARD:")
total_vehicle = vehicle_loan[1] or Decimal('0')
total_etransfer = (etransfer_totals[0] or Decimal('0')) - (etransfer_totals[1] or Decimal('0'))
grand_total = total_vehicle + total_etransfer
print(f"   Vehicle loan payments: ${total_vehicle:,.2f}")
print(f"   E-transfer net: ${total_etransfer:,.2f}")
print(f"   TOTAL OWED: ${grand_total:,.2f}")

print("\n" + "=" * 120)
print("NEXT STEPS")
print("=" * 120)
print("""
1. Create GL account: 2110 - Loan Payable - David Richard - Vehicle Loan
2. Record vehicle loan payments in general ledger
3. Combine with e-transfer loans for total David Richard liability
4. Generate formal loan agreement documenting all amounts
5. Set up repayment plan
""")

cur.close()
conn.close()

print("\n" + "=" * 120)
print("SCRIPT COMPLETE")
print("=" * 120)
