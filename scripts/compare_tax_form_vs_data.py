#!/usr/bin/env python3
"""
Compare year-end tax submission form figures against our database.
Generates a PASS/FAIL report showing exact matches and variances.
"""
import sys
from pathlib import Path
from decimal import Decimal

def load_our_data(year):
    """Load our computed figures from the tax year summary CSV."""
    csv_path = Path(__file__).parent.parent / 'exports' / 'cra' / str(year) / f'tax_year_summary_{year}.csv'
    if not csv_path.exists():
        return None
    
    data = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        next(f)  # Skip header
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 2:
                data[parts[0]] = Decimal(parts[1])
    return data

def compare_year(year, form_gst_collected, form_itc, form_net_gst, form_cra_paid=None):
    """Compare form values against database and report matches/diffs."""
    print(f"\n{'='*100}")
    print(f"YEAR {year} TAX FORM COMPARISON")
    print(f"{'='*100}\n")
    
    our_data = load_our_data(year)
    if not our_data:
        print(f"[FAIL] FAIL: No data found for {year} in exports/cra/{year}/")
        return False
    
    our_gst_collected = our_data.get('gst_collected', Decimal('0'))
    our_itc = our_data.get('gst_itc', Decimal('0'))
    our_net_gst = our_gst_collected - our_itc
    our_cra_paid = our_data.get('cra_payments', Decimal('0'))
    
    # Convert form values to Decimal
    form_gst_collected = Decimal(str(form_gst_collected))
    form_itc = Decimal(str(form_itc))
    form_net_gst = Decimal(str(form_net_gst))
    if form_cra_paid is not None:
        form_cra_paid = Decimal(str(form_cra_paid))
    
    all_match = True
    
    # Compare GST Collected
    print(f"📊 GST/HST Collected:")
    print(f"   Form value:     ${form_gst_collected:>14,.2f}")
    print(f"   Database value: ${our_gst_collected:>14,.2f}")
    diff = our_gst_collected - form_gst_collected
    if abs(diff) < Decimal('0.01'):
        print(f"   [OK] MATCH\n")
    else:
        print(f"   [FAIL] VARIANCE: ${diff:>14,.2f}")
        print(f"      {'Database higher' if diff > 0 else 'Form higher'} by ${abs(diff):,.2f}\n")
        all_match = False
    
    # Compare ITCs
    print(f"💰 Input Tax Credits (ITCs):")
    print(f"   Form value:     ${form_itc:>14,.2f}")
    print(f"   Database value: ${our_itc:>14,.2f}")
    diff = our_itc - form_itc
    if abs(diff) < Decimal('0.01'):
        print(f"   [OK] MATCH\n")
    else:
        print(f"   [FAIL] VARIANCE: ${diff:>14,.2f}")
        print(f"      {'Database higher' if diff > 0 else 'Form higher'} by ${abs(diff):,.2f}")
        if our_itc < form_itc:
            print(f"      NOTE: Database ITCs lower - may need to import {year} receipts\n")
        else:
            print(f"      NOTE: Database ITCs higher - form may have excluded some expenses\n")
        all_match = False
    
    # Compare Net GST
    print(f"📈 Net GST/HST Position:")
    print(f"   Form value:     ${form_net_gst:>14,.2f}")
    print(f"   Database value: ${our_net_gst:>14,.2f}")
    diff = our_net_gst - form_net_gst
    if abs(diff) < Decimal('0.01'):
        print(f"   [OK] MATCH\n")
    else:
        print(f"   [FAIL] VARIANCE: ${diff:>14,.2f}")
        print(f"      {'Database higher' if diff > 0 else 'Form higher'} by ${abs(diff):,.2f}\n")
        all_match = False
    
    # Compare CRA Payments if provided
    if form_cra_paid is not None:
        print(f"💳 CRA Payments Made:")
        print(f"   Form value:     ${form_cra_paid:>14,.2f}")
        print(f"   Database value: ${our_cra_paid:>14,.2f}")
        diff = our_cra_paid - form_cra_paid
        if abs(diff) < Decimal('0.01'):
            print(f"   [OK] MATCH\n")
        else:
            print(f"   [FAIL] VARIANCE: ${diff:>14,.2f}")
            print(f"      {'Database higher' if diff > 0 else 'Form higher'} by ${abs(diff):,.2f}")
            if our_cra_paid == 0 and form_cra_paid > 0:
                print(f"      NOTE: Payments may not be properly categorized in banking_transactions\n")
            else:
                print(f"      NOTE: Check CRA payment descriptions in banking data\n")
            all_match = False
    
    print(f"{'='*100}")
    if all_match:
        print(f"[OK] ALL FIELDS MATCH - Data integrity verified for {year}")
    else:
        print(f"[WARN]  VARIANCES DETECTED - Review differences above")
    print(f"{'='*100}\n")
    
    return all_match

def main():
    print("\n" + "="*100)
    print("TAX FORM VS DATABASE COMPARISON TOOL")
    print("="*100)
    print("\nPlease enter the values from your tax submission form:")
    print("(Press Enter to skip a field)\n")
    
    # Get year
    year = input("Year (e.g., 2013, 2014, 2015): ").strip()
    if not year:
        print("[FAIL] Year is required")
        sys.exit(1)
    year = int(year)
    
    # Get GST collected
    gst_collected = input("GST/HST Collected (Box 101 or Line 1): $").strip().replace(',', '')
    if not gst_collected:
        print("[FAIL] GST Collected is required")
        sys.exit(1)
    gst_collected = float(gst_collected)
    
    # Get ITCs
    itc = input("Input Tax Credits (Box 106 or Line 5): $").strip().replace(',', '')
    if not itc:
        itc = '0'
    itc = float(itc)
    
    # Calculate net
    net_gst = gst_collected - itc
    print(f"\n   Calculated Net GST/HST: ${net_gst:,.2f}")
    net_input = input("   Or enter Net GST/HST from form (Box 109 or Line 8): $").strip().replace(',', '')
    if net_input:
        net_gst = float(net_input)
    
    # Get CRA payments (optional)
    cra_paid = input("CRA Payments Made (optional): $").strip().replace(',', '')
    if cra_paid:
        cra_paid = float(cra_paid)
    else:
        cra_paid = None
    
    # Run comparison
    result = compare_year(year, gst_collected, itc, net_gst, cra_paid)
    
    sys.exit(0 if result else 1)

if __name__ == '__main__':
    main()
