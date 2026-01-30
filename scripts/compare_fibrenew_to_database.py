#!/usr/bin/env python3
"""
Compare Fibrenew Excel data to existing database records.
"""

import pandas as pd
import psycopg2
from decimal import Decimal
from datetime import datetime
import os

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except:
                continue
    return None

def main():
    # Read Excel file
    df = pd.read_excel(EXCEL_FILE, header=None)
    
    # Parse invoices
    excel_invoices = []
    for idx, row in df.iterrows():
        col0 = str(row[0]).strip()
        if col0 and col0 not in ['inv', 'pmt', 'statement', 'nan'] and not 'balance' in str(row[1]).lower():
            inv_date = parse_date(row[1])
            try:
                inv_amt = Decimal(str(row[2])) if not pd.isna(row[2]) else None
            except:
                inv_amt = None
            excel_invoices.append({
                'number': col0, 
                'date': inv_date, 
                'amount': inv_amt,
                'notes': str(row[3]) if not pd.isna(row[3]) else ''
            })
    
    # Parse payments
    excel_payments = []
    for idx in range(91, len(df)):
        if str(df.iloc[idx, 0]).strip().lower() == 'pmt':
            pmt_date = parse_date(df.iloc[idx, 1])
            try:
                pmt_amt = abs(Decimal(str(df.iloc[idx, 2]).replace('$', '').replace(',', '').strip()))
            except:
                pmt_amt = Decimal('0')
            pmt_notes = str(df.iloc[idx, 3]) if not pd.isna(df.iloc[idx, 3]) else ''
            excel_payments.append({
                'date': pmt_date, 
                'amount': pmt_amt, 
                'notes': pmt_notes
            })
    
    print("="*80)
    print("FIBRENEW EXCEL DATA")
    print("="*80)
    print(f"Invoices: {len(excel_invoices)}")
    excel_inv_total = sum(inv['amount'] for inv in excel_invoices if inv['amount'])
    print(f"Total: ${excel_inv_total:,.2f}")
    print(f"\nPayments: {len(excel_payments)}")
    excel_pmt_total = sum(pmt['amount'] for pmt in excel_payments)
    print(f"Total: ${excel_pmt_total:,.2f}")
    print()
    
    # Check database
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("DATABASE SEARCH - Receipts")
    print("="*80)
    
    # Search for Fibrenew in receipts
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, description
        FROM receipts
        WHERE LOWER(vendor_name) LIKE %s
        OR LOWER(description) LIKE %s
        ORDER BY receipt_date
    """, ('%fibrenew%', '%fibrenew%'))
    
    db_receipts = cur.fetchall()
    print(f"Found {len(db_receipts)} receipts with 'Fibrenew'")
    if db_receipts:
        db_receipt_total = sum(row[3] for row in db_receipts if row[3])
        print(f"Total: ${db_receipt_total:,.2f}")
        print("\nSample receipts:")
        for row in db_receipts[:10]:
            print(f"  {row[1]} | ${row[3]:,.2f} | {row[2][:40]}")
    print()
    
    # Search for Fibrenew in payments
    print("="*80)
    print("DATABASE SEARCH - Payments")
    print("="*80)
    
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_key, reserve_number
        FROM payments
        WHERE LOWER(payment_key) LIKE %s
        ORDER BY payment_date
    """, ('%fibrenew%',))
    
    db_payments = cur.fetchall()
    print(f"Found {len(db_payments)} payments with 'Fibrenew'")
    if db_payments:
        db_pmt_total = sum(row[2] for row in db_payments if row[2])
        print(f"Total: ${db_pmt_total:,.2f}")
        print("\nAll payments:")
        for row in db_payments:
            print(f"  {row[1]} | ${row[2]:,.2f} | Rsv {row[4]} | {row[3][:50] if row[3] else ''}")
    print()
    
    # Search banking transactions
    print("="*80)
    print("DATABASE SEARCH - Banking Transactions")
    print("="*80)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE LOWER(description) LIKE %s
        ORDER BY transaction_date
    """, ('%fibrenew%',))
    
    db_banking = cur.fetchall()
    print(f"Found {len(db_banking)} banking transactions with 'Fibrenew'")
    if db_banking:
        db_debit_total = sum(row[3] for row in db_banking if row[3])
        db_credit_total = sum(row[4] for row in db_banking if row[4])
        print(f"Total debits: ${db_debit_total:,.2f}")
        print(f"Total credits: ${db_credit_total:,.2f}")
        print("\nSample transactions:")
        for row in db_banking[:10]:
            amt = row[3] if row[3] else row[4]
            typ = 'DR' if row[3] else 'CR'
            print(f"  {row[1]} | {typ} ${amt:,.2f} | {row[2][:50]}")
    print()
    
    # Search charters
    print("="*80)
    print("DATABASE SEARCH - Charters")
    print("="*80)
    
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, account_number, total_amount_due
        FROM charters
        WHERE LOWER(account_number) LIKE %s
        OR LOWER(client_notes) LIKE %s
        ORDER BY charter_date
    """, ('%fibrenew%', '%fibrenew%'))
    
    db_charters = cur.fetchall()
    print(f"Found {len(db_charters)} charters with 'Fibrenew'")
    if db_charters:
        db_charter_total = sum(row[4] for row in db_charters if row[4])
        print(f"Total: ${db_charter_total:,.2f}")
        print("\nSample charters:")
        for row in db_charters[:10]:
            print(f"  {row[2]} | Rsv {row[1]} | ${row[4]:,.2f} | {row[3][:40]}")
    print()
    
    # Summary comparison
    print("="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    receipt_total_str = f"${db_receipt_total:,.2f}" if db_receipts else "$0.00"
    payment_total_str = f"${db_pmt_total:,.2f}" if db_payments else "$0.00"
    debit_total_str = f"${db_debit_total:,.2f}" if db_banking else "$0.00"
    credit_total_str = f"${db_credit_total:,.2f}" if db_banking else "$0.00"
    charter_total_str = f"${db_charter_total:,.2f}" if db_charters else "$0.00"
    
    print(f"\nExcel invoices: {len(excel_invoices)} (${excel_inv_total:,.2f})")
    print(f"DB receipts:    {len(db_receipts)} ({receipt_total_str})")
    print(f"\nExcel payments: {len(excel_payments)} (${excel_pmt_total:,.2f})")
    print(f"DB payments:    {len(db_payments)} ({payment_total_str})")
    print(f"\nDB banking:     {len(db_banking)} (DR {debit_total_str} / CR {credit_total_str})")
    print(f"DB charters:    {len(db_charters)} ({charter_total_str})")
    
    if db_receipts:
        print("\n⚠ Fibrenew data already exists in receipts table")
        print("   Recommendation: Review for duplicates before importing Excel data")
    else:
        print("\n✓ No Fibrenew receipts in database - safe to import Excel invoices")
    
    if db_payments:
        print("\n⚠ Fibrenew data already exists in payments table")
        print("   Recommendation: Review payment matching strategy")
    else:
        print("\n✓ No Fibrenew payments in database")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
