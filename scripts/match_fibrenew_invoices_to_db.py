#!/usr/bin/env python3
"""
Compare Fibrenew Excel invoices to database receipts by year (2012-2016).
Check if each invoice exists in database and if it was paid off.
"""

import pandas as pd
import psycopg2
from decimal import Decimal
from datetime import datetime
import os
from collections import defaultdict

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
            
            # Skip if date is None or in year 3013 (date error)
            if inv_date and inv_date.year <= 2016:
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
            
            # Extract invoice references
            invoice_refs = []
            if pmt_notes and ',' in pmt_notes and any(c.isdigit() for c in pmt_notes):
                parts = pmt_notes.split(',')
                i = 0
                while i < len(parts) - 1:
                    try:
                        inv = parts[i].strip()
                        amt = Decimal(parts[i+1].strip())
                        invoice_refs.append({'invoice': inv, 'amount': amt})
                        i += 2
                    except:
                        i += 1
            
            if pmt_date and pmt_date.year <= 2016:
                excel_payments.append({
                    'date': pmt_date, 
                    'amount': pmt_amt, 
                    'notes': pmt_notes,
                    'invoice_refs': invoice_refs
                })
    
    # Parse statements (March 2015)
    excel_statements = []
    for idx in range(108, min(115, len(df))):
        if str(df.iloc[idx, 0]).strip().lower() == 'statement':
            stmt_date = parse_date(df.iloc[idx, 1])
            detail = str(df.iloc[idx, 2]) if not pd.isna(df.iloc[idx, 2]) else ''
            if ',' in detail:
                parts = detail.split(',')
                if len(parts) >= 2:
                    try:
                        inv = parts[0].strip()
                        amt = Decimal(parts[1].strip())
                        excel_statements.append({
                            'date': stmt_date,
                            'invoice': inv,
                            'amount': amt
                        })
                    except:
                        pass
    
    # Parse balance summary (August 2015)
    balance_summary = {}
    balance_detail_str = str(df.iloc[90, 3])
    parts = balance_detail_str.split(',')
    i = 0
    while i < len(parts) - 1:
        try:
            inv = parts[i].strip()
            amt = Decimal(parts[i+1].strip())
            balance_summary[inv] = amt
            i += 2
        except:
            i += 1
    
    # Group by year
    by_year = defaultdict(list)
    for inv in excel_invoices:
        by_year[inv['date'].year].append(inv)
    
    print("="*80)
    print("FIBRENEW INVOICE COMPARISON BY YEAR")
    print("="*80)
    print()
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all Fibrenew receipts grouped by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date)::int as year,
            receipt_date,
            vendor_name,
            gross_amount,
            description
        FROM receipts
        WHERE LOWER(vendor_name) LIKE %s
        ORDER BY receipt_date
    """, ('%fibrenew%',))
    
    db_receipts_raw = cur.fetchall()
    db_receipts_by_year = defaultdict(list)
    for row in db_receipts_raw:
        db_receipts_by_year[row[0]].append({
            'date': row[1],
            'vendor': row[2],
            'amount': row[3],
            'description': row[4]
        })
    
    # Get all Fibrenew banking transactions
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date)::int as year,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE LOWER(description) LIKE %s
        ORDER BY transaction_date
    """, ('%fibrenew%',))
    
    db_banking_raw = cur.fetchall()
    db_banking_by_year = defaultdict(list)
    for row in db_banking_raw:
        db_banking_by_year[row[0]].append({
            'date': row[1],
            'description': row[2],
            'debit': row[3] or Decimal('0'),
            'credit': row[4] or Decimal('0')
        })
    
    # Process each year
    for year in sorted(by_year.keys()):
        invoices = by_year[year]
        db_receipts = db_receipts_by_year.get(year, [])
        db_banking = db_banking_by_year.get(year, [])
        
        print("="*80)
        print(f"YEAR {year}")
        print("="*80)
        
        inv_total = sum(inv['amount'] for inv in invoices if inv['amount'])
        print(f"\nExcel invoices: {len(invoices)} (${inv_total:,.2f})")
        
        if db_receipts:
            db_total = sum(r['amount'] for r in db_receipts if r['amount'])
            print(f"DB receipts:    {len(db_receipts)} (${db_total:,.2f})")
        else:
            print(f"DB receipts:    0 ($0.00)")
        
        if db_banking:
            debit_total = sum(b['debit'] for b in db_banking)
            credit_total = sum(b['credit'] for b in db_banking)
            print(f"DB banking:     {len(db_banking)} (DR ${debit_total:,.2f} / CR ${credit_total:,.2f})")
        else:
            print(f"DB banking:     0")
        
        # Check each invoice
        print(f"\nInvoice details:")
        for inv in invoices:
            inv_num = inv['number']
            inv_date = inv['date']
            inv_amt = inv['amount']
            
            # Find matching receipt
            matches = [r for r in db_receipts if r['date'] == inv_date and r['amount'] == inv_amt]
            
            # Check if in balance summary (Aug 2015)
            in_balance = inv_num in balance_summary
            balance_amt = balance_summary.get(inv_num)
            
            # Check if in statements (Mar 2015)
            stmt_match = [s for s in excel_statements if s['invoice'] == inv_num]
            
            # Check payment notes
            payment_match = []
            for pmt in excel_payments:
                if pmt['invoice_refs']:
                    for ref in pmt['invoice_refs']:
                        if ref['invoice'] == inv_num:
                            payment_match.append({'date': pmt['date'], 'amount': ref['amount']})
            
            status = "✓ IN DB" if matches else "✗ NOT FOUND"
            amt_str = f"${inv_amt:,.2f}" if inv_amt else "[no amount]"
            
            print(f"  #{inv_num} | {inv_date} | {amt_str:>12} | {status}")
            
            if in_balance:
                print(f"         → Aug 2015 balance: ${balance_amt:,.2f} UNPAID")
            elif stmt_match:
                print(f"         → Mar 2015 statement: ${stmt_match[0]['amount']:,.2f}")
            
            if payment_match:
                for pm in payment_match:
                    print(f"         → Payment ref: {pm['date']} ${pm['amount']:,.2f}")
            
            if matches:
                print(f"         → DB has {len(matches)} matching receipt(s)")
        
        print()
    
    # 2016 payments (accountant note)
    payments_2016 = [p for p in excel_payments if p['date'].year == 2016]
    if payments_2016:
        print("="*80)
        print("2016 PAYMENTS (ACCOUNTANT NOTES)")
        print("="*80)
        for pmt in payments_2016:
            print(f"{pmt['date']} | ${pmt['amount']:,.2f} | {pmt['notes']}")
        print()
    
    # Summary
    print("="*80)
    print("PAYMENT STATUS SUMMARY")
    print("="*80)
    
    total_invoiced = sum(inv['amount'] for inv in excel_invoices if inv['amount'])
    total_payments = sum(pmt['amount'] for pmt in excel_payments)
    balance_total = sum(balance_summary.values())
    
    print(f"\nTotal invoiced (2012-2016): ${total_invoiced:,.2f}")
    print(f"Total payments recorded:    ${total_payments:,.2f}")
    print(f"Balance per Aug 2015 summary: ${balance_total:,.2f}")
    print(f"\nInvoices in Aug 2015 balance: {len(balance_summary)}")
    for inv_num, amt in sorted(balance_summary.items()):
        print(f"  #{inv_num}: ${amt:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
