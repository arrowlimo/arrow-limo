#!/usr/bin/env python3
"""
Generate 2009 charge summary CSV from almsdata.charters table.

Uses the recreate_charge_summary_report.py logic to produce a CSV
matching the format used for 2010/2011/2012 charge summaries.

Output: L:\limo\recreated_2009_charge_summary.csv
"""
import sys
import os

# Add parent directory to path to import recreate_charge_summary_report
sys.path.insert(0, r'L:\limo')

from recreate_charge_summary_report import generate_sample_report

def main():
    print("=" * 80)
    print("GENERATING 2009 CHARGE SUMMARY CSV")
    print("=" * 80)
    
    year = 2009
    output_file = r"L:\limo\recreated_2009_charge_summary.csv"
    
    print(f"\n📊 Generating charge summary for {year}...")
    report_df = generate_sample_report(year)
    
    if report_df is None or len(report_df) == 0:
        print(f"\n[FAIL] No data found for {year}")
        print("   Check if charters table contains 2009 records.")
        return 1
    
    # Save to CSV
    report_df.to_csv(output_file, index=False)
    print(f"\n[OK] Saved {len(report_df):,} records to: {output_file}")
    
    # Show summary
    print(f"\n📊 SUMMARY:")
    print(f"   Records:      {len(report_df):,}")
    print(f"   Service Fee:  ${report_df['Service Fee'].sum():,.2f}")
    print(f"   Gratuity:     ${report_df['Gratuity'].sum():,.2f}")
    print(f"   GST:          ${report_df['G.S.T.'].sum():,.2f}")
    print(f"   Total:        ${report_df['Total'].sum():,.2f}")
    
    print("\n" + "=" * 80)
    print("[OK] 2009 CHARGE SUMMARY GENERATION COMPLETE")
    print("=" * 80)
    print(f"\nNext step: Run scripts/import_charge_summary_2009.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
