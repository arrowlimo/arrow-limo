#!/usr/bin/env python3
"""
Verify Fibrenew invoices follow expected pattern: 1 rent + 1 utilities per month.
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
    
    # Group by year-month
    by_month = defaultdict(list)
    for inv in excel_invoices:
        month_key = (inv['date'].year, inv['date'].month)
        by_month[month_key].append(inv)
    
    print("="*80)
    print("FIBRENEW INVOICE PATTERN VERIFICATION")
    print("Expected: 1 rent invoice (~$1,575-$1,706) + 1 utilities invoice (~$140-$270)")
    print("="*80)
    print()
    
    # Common rent amounts
    RENT_AMOUNTS = [Decimal('1050.00'), Decimal('1575.00'), Decimal('1706.25'), Decimal('1779.75')]
    
    for month_key in sorted(by_month.keys()):
        year, month = month_key
        invoices = by_month[month_key]
        
        # Categorize by amount
        rent_invoices = []
        utilities = []
        other = []
        
        for inv in invoices:
            if inv['amount']:
                # Rent is typically $1,050-$1,800
                if inv['amount'] >= Decimal('1000'):
                    rent_invoices.append(inv)
                # Utilities typically $100-$500
                elif Decimal('100') <= inv['amount'] <= Decimal('500'):
                    utilities.append(inv)
                # Credits or adjustments
                elif inv['amount'] < Decimal('0'):
                    other.append(inv)
                # Small charges
                else:
                    other.append(inv)
            else:
                other.append(inv)
        
        # Determine status
        status = "✓ OK" if len(rent_invoices) == 1 and len(utilities) == 1 else "⚠ CHECK"
        
        month_name = datetime(year, month, 1).strftime('%B %Y')
        print(f"{month_name:20} | Rent: {len(rent_invoices)} | Utils: {len(utilities)} | Other: {len(other)} | {status}")
        
        # Show details if not standard pattern
        if len(rent_invoices) != 1 or len(utilities) != 1 or len(other) > 0:
            for inv in invoices:
                amt_str = f"${inv['amount']:,.2f}" if inv['amount'] else "[no amount]"
                inv_type = "RENT" if inv['amount'] and inv['amount'] >= Decimal('1000') else \
                           "UTIL" if inv['amount'] and Decimal('100') <= inv['amount'] <= Decimal('500') else \
                           "CRED" if inv['amount'] and inv['amount'] < Decimal('0') else \
                           "????"
                print(f"    #{inv['number']:6} | {inv['date']} | {amt_str:>12} | {inv_type}")
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    
    total_months = len(by_month)
    standard_pattern = sum(1 for invoices in by_month.values() 
                          if len([i for i in invoices if i['amount'] and i['amount'] >= Decimal('1000')]) == 1
                          and len([i for i in invoices if i['amount'] and Decimal('100') <= i['amount'] <= Decimal('500')]) == 1)
    
    print(f"\nTotal months with invoices: {total_months}")
    print(f"Months with standard pattern (1 rent + 1 util): {standard_pattern}")
    print(f"Months with irregularities: {total_months - standard_pattern}")
    
    # Analyze rent amounts over time
    print()
    print("="*80)
    print("RENT AMOUNT CHANGES")
    print("="*80)
    
    rent_by_date = []
    for month_key in sorted(by_month.keys()):
        invoices = by_month[month_key]
        rent = [i for i in invoices if i['amount'] and i['amount'] >= Decimal('1000')]
        if rent:
            for r in rent:
                rent_by_date.append(r)
    
    prev_amt = None
    for inv in rent_by_date:
        if prev_amt and inv['amount'] != prev_amt:
            print(f"{inv['date']} | #{inv['number']} | ${inv['amount']:,.2f} ← CHANGED from ${prev_amt:,.2f}")
        else:
            print(f"{inv['date']} | #{inv['number']} | ${inv['amount']:,.2f}")
        prev_amt = inv['amount']
    
    # Count rent increases
    rent_amounts = [r['amount'] for r in rent_by_date if r['amount']]
    unique_rents = sorted(set(rent_amounts))
    print(f"\nRent levels used: {len(unique_rents)}")
    for amt in unique_rents:
        count = sum(1 for r in rent_amounts if r == amt)
        print(f"  ${amt:,.2f}: {count} months")

if __name__ == '__main__':
    main()
