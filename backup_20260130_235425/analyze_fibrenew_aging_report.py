#!/usr/bin/env python3
"""
Re-analyze Fibrenew invoices understanding that multiple entries of same invoice number
represent outstanding balance carried forward, not duplicates.
"""

import pandas as pd
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

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
    
    # Parse all invoice entries
    invoice_entries = []
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
                invoice_entries.append({
                    'number': col0, 
                    'date': inv_date, 
                    'amount': inv_amt,
                    'notes': str(row[3]) if not pd.isna(row[3]) else ''
                })
    
    # Group by invoice number to track each invoice's lifecycle
    invoices_by_number = defaultdict(list)
    for entry in invoice_entries:
        invoices_by_number[entry['number']].append(entry)
    
    print("="*80)
    print("FIBRENEW INVOICE LIFECYCLE ANALYSIS")
    print("Multiple entries = outstanding balance carried forward")
    print("="*80)
    print()
    
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
    
    # Parse balance summary (Aug 2015)
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
    
    # Analyze invoices with multiple entries (outstanding balances)
    print("INVOICES WITH MULTIPLE ENTRIES (Outstanding Balances):")
    print("="*80)
    
    multi_entry_invoices = {num: entries for num, entries in invoices_by_number.items() if len(entries) > 1}
    
    for inv_num in sorted(multi_entry_invoices.keys()):
        entries = sorted(multi_entry_invoices[inv_num], key=lambda x: x['date'])
        
        print(f"\nInvoice #{inv_num}: {len(entries)} entries")
        
        # Show each appearance
        for i, entry in enumerate(entries, 1):
            amt_str = f"${entry['amount']:,.2f}" if entry['amount'] else "[no amount]"
            payment_info = ""
            if entry['notes']:
                payment_info = f" | Payment: {entry['notes']}"
            print(f"  {i}. {entry['date']} | Balance: {amt_str}{payment_info}")
        
        # Check if in Aug 2015 balance summary
        if inv_num in balance_summary:
            print(f"     → Final balance per Aug 2015: ${balance_summary[inv_num]:,.2f} UNPAID")
        
        # Check payment references
        payment_refs = []
        for pmt in excel_payments:
            if pmt['invoice_refs']:
                for ref in pmt['invoice_refs']:
                    if ref['invoice'] == inv_num:
                        payment_refs.append({'date': pmt['date'], 'amount': ref['amount']})
        
        if payment_refs:
            print(f"     → Payments applied:")
            for ref in payment_refs:
                print(f"        {ref['date']}: ${ref['amount']:,.2f}")
    
    # Count unique invoices (not entries)
    unique_invoices = len(invoices_by_number)
    total_entries = len(invoice_entries)
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal unique invoices: {unique_invoices}")
    print(f"Total invoice entries: {total_entries}")
    print(f"Invoices appearing multiple times: {len(multi_entry_invoices)}")
    print(f"  (Outstanding balances carried forward)")
    
    # Show carried forward pattern
    print(f"\nCarried forward counts:")
    carry_forward_counts = defaultdict(int)
    for entries in multi_entry_invoices.values():
        carry_forward_counts[len(entries)] += 1
    
    for count in sorted(carry_forward_counts.keys(), reverse=True):
        print(f"  {carry_forward_counts[count]} invoices appeared {count} times")
    
    # Invoices that were paid off (no longer in Aug 2015 balance)
    paid_invoices = [num for num in invoices_by_number.keys() if num not in balance_summary]
    print(f"\nInvoices PAID OFF (not in Aug 2015 balance): {len(paid_invoices)}")
    print(f"Invoices STILL OUTSTANDING (in Aug 2015 balance): {len(balance_summary)}")
    
    print()
    print("="*80)
    print("INTERPRETATION")
    print("="*80)
    print("\nThis is an AGING REPORT showing:")
    print("  - Original invoice issuance date")
    print("  - Outstanding balance carried forward each period")
    print("  - Payment notes when partial/full payments applied")
    print("  - Final Aug 2015 balance summary = 7 unpaid invoices")
    print("\nThe multiple entries are NOT duplicates - they track unpaid balances")
    print("over time until the invoice is paid in full.")

if __name__ == '__main__':
    main()
