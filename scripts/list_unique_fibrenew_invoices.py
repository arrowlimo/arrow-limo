#!/usr/bin/env python3
"""
List unique invoices by date (first occurrence only) to identify monthly billing pattern.
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
    
    # Keep only FIRST occurrence of each invoice number
    seen_invoices = {}
    for entry in invoice_entries:
        inv_num = entry['number']
        if inv_num not in seen_invoices:
            seen_invoices[inv_num] = entry
    
    unique_invoices = sorted(seen_invoices.values(), key=lambda x: x['date'])
    
    print("="*80)
    print("UNIQUE INVOICES BY DATE (First Occurrence Only)")
    print("="*80)
    print()
    
    # Group by year-month
    by_month = defaultdict(list)
    for inv in unique_invoices:
        month_key = (inv['date'].year, inv['date'].month)
        by_month[month_key].append(inv)
    
    # Categorize by amount (rent vs utilities)
    for month_key in sorted(by_month.keys()):
        year, month = month_key
        invoices = by_month[month_key]
        
        month_name = datetime(year, month, 1).strftime('%B %Y')
        print(f"\n{month_name}")
        print("-" * 80)
        
        # Categorize
        rent = [i for i in invoices if i['amount'] and i['amount'] >= Decimal('1000')]
        utilities = [i for i in invoices if i['amount'] and Decimal('100') <= i['amount'] < Decimal('1000')]
        credits = [i for i in invoices if i['amount'] and i['amount'] < Decimal('0')]
        other = [i for i in invoices if not i['amount'] or (i['amount'] < Decimal('100') and i['amount'] >= Decimal('0'))]
        
        # Show rent
        if rent:
            print("  RENT:")
            for inv in rent:
                print(f"    #{inv['number']:6} | {inv['date']} | ${inv['amount']:>10,.2f}")
        
        # Show utilities
        if utilities:
            print("  UTILITIES:")
            for inv in utilities:
                print(f"    #{inv['number']:6} | {inv['date']} | ${inv['amount']:>10,.2f}")
        
        # Show credits
        if credits:
            print("  CREDITS:")
            for inv in credits:
                print(f"    #{inv['number']:6} | {inv['date']} | ${inv['amount']:>10,.2f}")
        
        # Show other
        if other:
            print("  OTHER:")
            for inv in other:
                amt_str = f"${inv['amount']:,.2f}" if inv['amount'] else "[no amount]"
                print(f"    #{inv['number']:6} | {inv['date']} | {amt_str:>12}")
        
        # Summary
        rent_count = len(rent)
        util_count = len(utilities)
        status = "✓" if rent_count == 1 and util_count == 1 else "⚠"
        print(f"  Total: {len(invoices)} invoices ({rent_count} rent, {util_count} util) {status}")
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal unique invoices: {len(unique_invoices)}")
    print(f"Total months with invoices: {len(by_month)}")
    
    # Count standard pattern
    standard_months = 0
    for invoices in by_month.values():
        rent = [i for i in invoices if i['amount'] and i['amount'] >= Decimal('1000')]
        utilities = [i for i in invoices if i['amount'] and Decimal('100') <= i['amount'] < Decimal('1000')]
        if len(rent) == 1 and len(utilities) == 1:
            standard_months += 1
    
    print(f"Months with standard pattern (1 rent + 1 util): {standard_months}")
    print(f"Months with irregularities: {len(by_month) - standard_months}")
    
    # Show rent evolution
    print()
    print("="*80)
    print("RENT AMOUNT TIMELINE")
    print("="*80)
    
    rent_invoices = [inv for inv in unique_invoices if inv['amount'] and inv['amount'] >= Decimal('1000')]
    
    prev_amt = None
    for inv in rent_invoices:
        marker = ""
        if prev_amt and inv['amount'] != prev_amt:
            marker = f" ← CHANGED from ${prev_amt:,.2f}"
        print(f"{inv['date']} | #{inv['number']:6} | ${inv['amount']:>10,.2f}{marker}")
        prev_amt = inv['amount']
    
    # Rent levels
    rent_amounts = [r['amount'] for r in rent_invoices]
    unique_rents = sorted(set(rent_amounts))
    print(f"\nRent levels: {len(unique_rents)}")
    for amt in unique_rents:
        count = sum(1 for r in rent_amounts if r == amt)
        print(f"  ${amt:>10,.2f}: {count} months")

if __name__ == '__main__':
    main()
