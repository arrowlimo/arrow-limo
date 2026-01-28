#!/usr/bin/env python3
"""
Generate consolidated multi-year tax summary from individual year CSV files.
Shows total GST/HST position across all years with banking data.
"""
import csv
import os
from pathlib import Path

def main():
    years = [2012, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    base_dir = Path(__file__).parent.parent / 'exports' / 'cra'
    
    print("\n" + "="*100)
    print("MULTI-YEAR TAX SUMMARY (2012, 2017-2025)")
    print("="*100)
    print(f"{'Year':<6} | {'GST Collected':>14} | {'ITCs Claimed':>14} | {'Net Position':>14} | {'CRA Payments':>14} | {'Status':<12}")
    print("-"*100)
    
    total_gst_collected = 0.0
    total_itc_claimed = 0.0
    total_cra_payments = 0.0
    
    for year in years:
        csv_path = base_dir / str(year) / f'tax_year_summary_{year}.csv'
        if not csv_path.exists():
            print(f"{year:<6} | {'N/A':>14} | {'N/A':>14} | {'N/A':>14} | {'N/A':>14} | No data")
            continue
        
        # CSV is in vertical format: metric,value
        data = {}
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row['metric']] = row['value']
        
        gst_collected = float(data.get('gst_collected', '0'))
        itc_claimed = float(data.get('gst_itc', '0'))
        net_gst = gst_collected - itc_claimed
        cra_payments = float(data.get('cra_payments', '0'))
        
        total_gst_collected += gst_collected
        total_itc_claimed += itc_claimed
        total_cra_payments += cra_payments
        
        status = "REFUND DUE" if net_gst < 0 else "OWING" if net_gst > 0 else "BALANCED"
        
        print(f"{year:<6} | ${gst_collected:>13,.2f} | ${itc_claimed:>13,.2f} | ${net_gst:>13,.2f} | ${cra_payments:>13,.2f} | {status:<12}")
    
    print("-"*100)
    total_net = total_gst_collected - total_itc_claimed
    overall_status = "REFUND DUE" if total_net < 0 else "OWING" if total_net > 0 else "BALANCED"
    print(f"{'TOTAL':<6} | ${total_gst_collected:>13,.2f} | ${total_itc_claimed:>13,.2f} | ${total_net:>13,.2f} | ${total_cra_payments:>13,.2f} | {overall_status:<12}")
    print("="*100)
    
    # Analysis
    print("\n📊 KEY FINDINGS:")
    print(f"   • Total Input Tax Credits (ITCs) claimed: ${total_itc_claimed:,.2f}")
    print(f"   • Total GST/HST collected from sales: ${total_gst_collected:,.2f}")
    print(f"   • Net GST/HST position: ${total_net:,.2f} ({overall_status})")
    print(f"   • Total CRA payments made: ${total_cra_payments:,.2f}")
    
    if total_net < 0:
        potential_refund = abs(total_net)
        print(f"\n💰 REFUND STATUS:")
        print(f"   • Potential GST/HST refund available: ${potential_refund:,.2f}")
        print(f"   • CRA payments already made: ${total_cra_payments:,.2f}")
        if total_cra_payments > 0:
            print(f"   • Combined refund potential: ${potential_refund + total_cra_payments:,.2f}")
    
    print("\n[WARN]  NOTE:")
    print("   • P&L shows $0 revenue because sales data is in separate system (LMS/Square)")
    print("   • These ITCs represent legitimate business expenses from banking transactions")
    print("   • Revenue data needs to be integrated from LMS charters and Square payments")
    print("   • Consult accountant before filing - this is expense side only")
    
    print("\n📁 Individual year reports available in: exports/cra/[year]/\n")

if __name__ == '__main__':
    main()
