#!/usr/bin/env python3
"""
Parse Fibrenew Excel file with proper structure:
- Header row (inv, date, amount, paid info)
- Invoice rows
- Balance summary row (indicated by 'balances' in column 1)
- Payment rows (indicated by 'pmt' in column 0)
- Statement rows (indicated by 'statement' in column 0)

Output structured data for invoices, balance summary, and payments.
"""

import pandas as pd
import re
from datetime import datetime
from decimal import Decimal

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

def parse_date(val):
    """Parse date from various formats."""
    if pd.isna(val):
        return None
    
    if isinstance(val, datetime):
        return val.date()
    
    if isinstance(val, str):
        # Try DD/MM/YYYY format
        for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except:
                continue
    
    return None

def parse_amount(val):
    """Parse amount handling negatives and NaN."""
    if pd.isna(val) or val == '':
        return None
    
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    
    if isinstance(val, str):
        clean = val.replace('$', '').replace(',', '').strip()
        if clean.startswith('-'):
            return -Decimal(clean[1:])
        try:
            return Decimal(clean)
        except:
            return None
    
    return None

def parse_balance_detail(detail_str):
    """Parse balance detail string like '5977,383.84,5978,144.13,...'"""
    if pd.isna(detail_str) or not isinstance(detail_str, str):
        return []
    
    parts = detail_str.split(',')
    balances = []
    
    i = 0
    while i < len(parts) - 1:
        try:
            inv_num = parts[i].strip()
            amount = Decimal(parts[i+1].strip())
            balances.append({'invoice': inv_num, 'balance': amount})
            i += 2
        except:
            i += 1
    
    return balances

def parse_statement_detail(detail_str):
    """Parse statement detail like '5797,104.89' into invoice# and amount."""
    if pd.isna(detail_str) or not isinstance(detail_str, str):
        return None, None
    
    parts = detail_str.split(',')
    if len(parts) >= 2:
        try:
            inv_num = parts[0].strip()
            amount = Decimal(parts[1].strip())
            return inv_num, amount
        except:
            pass
    
    return None, None

def extract_invoice_references(notes_str):
    """Extract invoice numbers from payment notes like '5028 cheque 195' or '5797,104.89,5802,895.11'."""
    if pd.isna(notes_str) or not isinstance(notes_str, str):
        return []
    
    # Check if it's a comma-separated list (invoice,amount pairs)
    if ',' in notes_str:
        parts = notes_str.split(',')
        invoices = []
        i = 0
        while i < len(parts) - 1:
            try:
                inv_num = parts[i].strip()
                amount = Decimal(parts[i+1].strip())
                invoices.append({'invoice': inv_num, 'amount': amount})
                i += 2
            except:
                i += 1
        if invoices:
            return invoices
    
    # Otherwise look for 4-digit invoice numbers
    inv_pattern = re.compile(r'\b(\d{4,5})\b')
    matches = inv_pattern.findall(notes_str)
    return [{'invoice': m, 'amount': None} for m in matches]

def main():
    print("="*80)
    print("FIBRENEW EXCEL PARSER - Correct Structure")
    print("="*80)
    
    # Read Excel file
    df = pd.read_excel(EXCEL_FILE, header=None)
    
    print(f"\nTotal rows: {len(df)}")
    
    # Find sections
    invoices = []
    balance_summary = None
    payments = []
    statements = []
    
    for idx, row in df.iterrows():
        col0 = str(row[0]).strip().lower() if not pd.isna(row[0]) else ''
        col1 = str(row[1]).strip().lower() if not pd.isna(row[1]) else ''
        
        # Skip header row
        if col0 == 'inv':
            continue
        
        # Balance summary row (column 1 says 'balances')
        elif 'balance' in col1:
            balance_date = parse_date(row[0])
            balance_total = parse_amount(row[2])
            balance_details = parse_balance_detail(row[3])
            
            balance_summary = {
                'date': balance_date,
                'total': balance_total,
                'details': balance_details
            }
            print(f"\nFound balance summary at row {idx}: Date={balance_date}, Total=${balance_total}")
            print(f"  Detail entries: {len(balance_details)}")
        
        # Payment row
        elif col0 == 'pmt':
            pmt_date = parse_date(row[1])
            pmt_amount = parse_amount(row[2])
            pmt_notes = str(row[3]) if not pd.isna(row[3]) else ''
            pmt_invoice_refs = extract_invoice_references(row[3])
            
            payments.append({
                'date': pmt_date,
                'amount': pmt_amount,
                'notes': pmt_notes,
                'invoice_references': pmt_invoice_refs
            })
        
        # Statement row
        elif col0 == 'statement':
            stmt_date = parse_date(row[1])
            stmt_invoice, stmt_amount = parse_statement_detail(row[2])
            
            statements.append({
                'date': stmt_date,
                'invoice': stmt_invoice,
                'amount': stmt_amount
            })
        
        # Invoice row
        elif col0 and col0 != 'nan':
            inv_num = str(row[0]).strip()
            inv_date = parse_date(row[1])
            inv_amount = parse_amount(row[2])
            inv_notes = str(row[3]) if not pd.isna(row[3]) else ''
            
            invoices.append({
                'invoice_number': inv_num,
                'date': inv_date,
                'amount': inv_amount,
                'notes': inv_notes
            })
    
    # Summary statistics
    print("\n" + "="*80)
    print("PARSING RESULTS")
    print("="*80)
    
    print(f"\nInvoices: {len(invoices)}")
    invoice_total = sum(inv['amount'] for inv in invoices if inv['amount'])
    invoice_credits = sum(abs(inv['amount']) for inv in invoices if inv['amount'] and inv['amount'] < 0)
    invoice_net = invoice_total
    
    print(f"  Total invoice amount: ${invoice_total:,.2f}")
    print(f"  Credit notes: ${invoice_credits:,.2f}")
    print(f"  Net invoiced: ${invoice_net:,.2f}")
    print(f"  Date range: {min(inv['date'] for inv in invoices if inv['date'])} to {max(inv['date'] for inv in invoices if inv['date'])}")
    
    print(f"\nBalance Summary:")
    if balance_summary:
        print(f"  Date: {balance_summary['date']}")
        print(f"  Total balance: ${balance_summary['total']:,.2f}")
        print(f"  Invoice details: {len(balance_summary['details'])} items")
        if balance_summary['details']:
            detail_total = sum(d['balance'] for d in balance_summary['details'])
            print(f"  Detail total: ${detail_total:,.2f}")
            print(f"  Sample details:")
            for detail in balance_summary['details'][:5]:
                print(f"    Invoice #{detail['invoice']}: ${detail['balance']:,.2f}")
    
    print(f"\nPayments: {len(payments)}")
    payment_total = sum(abs(pmt['amount']) for pmt in payments if pmt['amount'])
    print(f"  Total payments: ${payment_total:,.2f}")
    print(f"  Date range: {min(pmt['date'] for pmt in payments if pmt['date'])} to {max(pmt['date'] for pmt in payments if pmt['date'])}")
    
    print(f"\nStatements: {len(statements)}")
    
    # Payment-to-invoice analysis
    payments_with_refs = [p for p in payments if p['invoice_references']]
    print(f"\nPayments with invoice references: {len(payments_with_refs)} of {len(payments)}")
    if payments_with_refs:
        total_referenced = sum(abs(p['amount']) for p in payments_with_refs if p['amount'])
        print(f"  Total amount with refs: ${total_referenced:,.2f}")
    
    # Reconciliation
    print("\n" + "="*80)
    print("RECONCILIATION")
    print("="*80)
    
    print(f"\nNet invoiced: ${invoice_net:,.2f}")
    print(f"Total payments: ${payment_total:,.2f}")
    print(f"Balance per summary: ${balance_summary['total']:,.2f}" if balance_summary else "Balance: [not found]")
    
    calc_balance = invoice_net - payment_total
    print(f"\nCalculated balance: ${calc_balance:,.2f}")
    
    if balance_summary:
        diff = calc_balance - balance_summary['total']
        print(f"Difference from summary: ${diff:,.2f}")
        if abs(diff) < 1:
            print("✓ Balance reconciles!")
        else:
            print("⚠ Balance discrepancy detected")
    
    # Sample data
    print("\n" + "="*80)
    print("SAMPLE DATA")
    print("="*80)
    
    print("\nFirst 5 invoices:")
    for inv in invoices[:5]:
        print(f"  #{inv['invoice_number']} | {inv['date']} | ${inv['amount']:,.2f}" if inv['amount'] else f"  #{inv['invoice_number']} | {inv['date']} | [no amount]")
        if inv['notes']:
            print(f"    Notes: {inv['notes'][:60]}")
    
    print("\nFirst 5 payments:")
    for pmt in payments[:5]:
        print(f"  {pmt['date']} | ${abs(pmt['amount']):,.2f}" if pmt['amount'] else f"  {pmt['date']} | [no amount]")
        if pmt['notes']:
            print(f"    Notes: {pmt['notes'][:60]}")
        if pmt['invoice_references']:
            print(f"    Invoice refs: {pmt['invoice_references']}")
    
    # Data quality checks
    print("\n" + "="*80)
    print("DATA QUALITY")
    print("="*80)
    
    missing_amounts = [i for i in invoices if not i['amount']]
    print(f"\nInvoices missing amounts: {len(missing_amounts)}")
    for inv in missing_amounts[:5]:
        print(f"  #{inv['invoice_number']} ({inv['date']})")
    
    duplicate_invoices = {}
    for inv in invoices:
        if inv['invoice_number'] in duplicate_invoices:
            duplicate_invoices[inv['invoice_number']].append(inv)
        else:
            duplicate_invoices[inv['invoice_number']] = [inv]
    
    duplicates = {k: v for k, v in duplicate_invoices.items() if len(v) > 1}
    print(f"\nDuplicate invoice numbers: {len(duplicates)}")
    for inv_num, invs in list(duplicates.items())[:5]:
        print(f"  #{inv_num}: {len(invs)} entries")
        for inv in invs:
            amt_str = f"${inv['amount']:,.2f}" if inv['amount'] else "[no amount]"
            print(f"    {inv['date']} | {amt_str}")
    
    print("\n" + "="*80)
    print("READY FOR DATABASE IMPORT")
    print("="*80)
    print("\nParsed structure includes:")
    print("  - Invoice records (with payment notes from column 3)")
    print("  - Balance summary (date + total + invoice-level detail)")
    print("  - Payment transactions (negative amounts)")
    print("  - Statement entries")
    print("\nWaiting for confirmation before database upload.")

if __name__ == '__main__':
    main()
