#!/usr/bin/env python3
"""
Compare Fibrenew payments to balance summary to verify reconciliation.
"""

import pandas as pd
from decimal import Decimal
from datetime import datetime

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
    df = pd.read_excel(EXCEL_FILE, header=None)
    
    # Extract balance summary (row 90)
    balance_date = parse_date(df.iloc[90, 0])
    balance_total = Decimal(str(df.iloc[90, 2]))
    balance_detail = str(df.iloc[90, 3])
    
    print("="*80)
    print("BALANCE SUMMARY (Row 90)")
    print("="*80)
    print(f"Date: {balance_date}")
    print(f"Total balance: ${balance_total:,.2f}")
    print(f"Detail string: {balance_detail}")
    print()
    
    # Parse balance detail
    parts = balance_detail.split(',')
    balance_invoices = []
    i = 0
    while i < len(parts) - 1:
        try:
            inv = parts[i].strip()
            amt = Decimal(parts[i+1].strip())
            balance_invoices.append({'invoice': inv, 'balance': amt})
            i += 2
        except:
            i += 1
    
    print(f"Balance detail shows {len(balance_invoices)} outstanding invoices:")
    detail_total = Decimal('0')
    for item in balance_invoices:
        print(f"  Invoice #{item['invoice']}: ${item['balance']:,.2f}")
        detail_total += item['balance']
    
    print(f"\nDetail sum: ${detail_total:,.2f}")
    print(f"Summary total: ${balance_total:,.2f}")
    diff = balance_total - detail_total
    print(f"Difference: ${diff:,.2f}")
    if abs(diff) > 1:
        print("⚠ Detail doesn't match summary total!")
    print()
    
    # Extract all invoices
    invoices = []
    for idx, row in df.iterrows():
        col0 = str(row[0]).strip()
        if col0 and col0 not in ['inv', 'pmt', 'statement', 'nan'] and not 'balance' in str(row[1]).lower():
            inv_date = parse_date(row[1])
            try:
                inv_amt = Decimal(str(row[2])) if not pd.isna(row[2]) else None
            except:
                inv_amt = None
            invoices.append({'number': col0, 'date': inv_date, 'amount': inv_amt})
    
    print("="*80)
    print("INVOICE TOTALS")
    print("="*80)
    total_invoiced = sum(inv['amount'] for inv in invoices if inv['amount'])
    print(f"Total invoices: {len(invoices)}")
    print(f"Total invoiced: ${total_invoiced:,.2f}")
    print()
    
    # Extract all payments
    payments = []
    for idx in range(91, len(df)):
        if str(df.iloc[idx, 0]).strip().lower() == 'pmt':
            pmt_date = parse_date(df.iloc[idx, 1])
            try:
                pmt_amt = abs(Decimal(str(df.iloc[idx, 2]).replace('$', '').replace(',', '').strip()))
            except:
                pmt_amt = Decimal('0')
            pmt_notes = str(df.iloc[idx, 3]) if not pd.isna(df.iloc[idx, 3]) else ''
            payments.append({'date': pmt_date, 'amount': pmt_amt, 'notes': pmt_notes})
    
    print("="*80)
    print("PAYMENTS")
    print("="*80)
    pmt_total = sum(p['amount'] for p in payments)
    print(f"Total payments: {len(payments)}")
    print(f"Payment sum: ${pmt_total:,.2f}")
    print()
    
    # Payments after balance date
    payments_after = [p for p in payments if p['date'] and p['date'] > balance_date]
    payments_before = [p for p in payments if p['date'] and p['date'] <= balance_date]
    
    print(f"Payments BEFORE balance date ({balance_date}): {len(payments_before)}")
    pmt_before_total = sum(p['amount'] for p in payments_before)
    print(f"  Total: ${pmt_before_total:,.2f}")
    
    print(f"\nPayments AFTER balance date ({balance_date}): {len(payments_after)}")
    pmt_after_total = sum(p['amount'] for p in payments_after)
    print(f"  Total: ${pmt_after_total:,.2f}")
    print()
    
    for p in payments_after:
        print(f"  {p['date']} | ${p['amount']:,.2f} | {p['notes'][:50] if p['notes'] else ''}")
    
    print()
    print("="*80)
    print("RECONCILIATION CHECK")
    print("="*80)
    
    calc_balance = total_invoiced - pmt_before_total
    print(f"Total invoiced: ${total_invoiced:,.2f}")
    print(f"Payments before {balance_date}: ${pmt_before_total:,.2f}")
    print(f"Calculated balance as of {balance_date}: ${calc_balance:,.2f}")
    print(f"Balance per summary: ${balance_total:,.2f}")
    
    recon_diff = calc_balance - balance_total
    print(f"\nDifference: ${recon_diff:,.2f}")
    
    if abs(recon_diff) < 100:
        print("✓ Balance reconciles (within $100)")
    else:
        print("⚠ Significant balance discrepancy")
        print("\nPossible reasons:")
        print("  - Missing invoices before balance date")
        print("  - Payments not captured")
        print("  - Credits/adjustments not shown")
        print("  - Balance summary represents only SPECIFIC invoices (as shown in detail)")

if __name__ == '__main__':
    main()
