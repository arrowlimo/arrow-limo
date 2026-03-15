#!/usr/bin/env python3
"""
Batch process top priority Excel files from the archive.

Focus on high-value expense recovery opportunities.
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our validation system
from validate_excel_archive import process_single_file

def process_priority_files():
    """Process the top priority files identified from the archive."""
    
    print("PRIORITY EXCEL FILES BATCH PROCESSING")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Top priority files based on likely expense content
    priority_files = [
        # Banking files (likely expense transactions)
        r"L:\limo\docs\2012-2013 excel\2012 CIBC.xlsm",
        r"L:\limo\docs\2012-2013 excel\2012 Scotia.xlsm",
        
        # Leasing files (vehicle/equipment expenses)
        r"L:\limo\docs\2012-2013 excel\2014 Leasing Summary.xlsx",
        r"L:\limo\docs\2012-2013 excel\2014 Leasing Summary2.xlsx",
        
        # Journal entries (accounting expense data)
        r"L:\limo\docs\2012-2013 excel\Arrow 2013 JE.xlsx",
        
        # Reconciliation files (expense tracking)
        r"L:\limo\docs\2012-2013 excel\2012 Reconcile Cash Receipts.xlsx",
        r"L:\limo\docs\2012-2013 excel\Reconcile 2012 GST.xlsx",
        
        # Payroll files (employee expense data)
        r"L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls",
        
        # Accounts payable (vendor expense data)
        r"L:\limo\docs\2012-2013 excel\Accounts Payable Workbook 2012.xls",
        r"L:\limo\docs\2012-2013 excel\Accounts Payable Workbook 2014.xls",
        
        # Revenue & receipts (may contain expense data)
        r"L:\limo\docs\2012-2013 excel\2013 Revenue & Receipts queries.xlsx",
        
        # Charge summaries (comprehensive data)
        r"L:\limo\docs\2012-2013 excel\chargesummary 2012.xls",
        r"L:\limo\docs\2012-2013 excel\chargesummary2013.xls",
        r"L:\limo\docs\2012-2013 excel\chargesummary2014.xls",
        r"L:\limo\docs\2012-2013 excel\chargesummary2015.xls",
        r"L:\limo\docs\2012-2013 excel\chargesummary2016.xls",
        r"L:\limo\docs\2012-2013 excel\chargesummary2017.xls"
    ]
    
    results = []
    total_potential = 0
    high_value_files = []
    processing_errors = []
    
    print(f"Processing {len(priority_files)} priority files...\n")
    
    for i, file_path in enumerate(priority_files, 1):
        if not os.path.exists(file_path):
            print(f"[FAIL] File not found: {os.path.basename(file_path)}")
            processing_errors.append(f"File not found: {file_path}")
            continue
        
        print(f"[{i:2d}/{len(priority_files)}] {os.path.basename(file_path)}")
        
        try:
            result = process_single_file(file_path, dry_run=True)
            
            if result.get('errors'):
                print(f"   [FAIL] Errors: {'; '.join(result['errors'])}")
                processing_errors.append(f"{os.path.basename(file_path)}: {'; '.join(result['errors'])}")
            else:
                expense_potential = result.get('expense_potential', 0)
                action = result.get('recommended_action', 'unknown')
                
                print(f"   [OK] Potential: ${expense_potential:,.0f} | Action: {action}")
                
                total_potential += expense_potential
                
                if expense_potential > 50000:  # High value threshold
                    high_value_files.append({
                        'filename': os.path.basename(file_path),
                        'full_path': file_path,
                        'potential': expense_potential,
                        'action': action,
                        'sheets': result.get('sheet_count', 0)
                    })
            
            results.append(result)
            
        except Exception as e:
            print(f"   [FAIL] Processing error: {e}")
            processing_errors.append(f"{os.path.basename(file_path)}: {e}")
    
    # Generate summary report
    print(f"\n" + "=" * 70)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 70)
    
    print(f"Files processed: {len(results)}")
    print(f"Processing errors: {len(processing_errors)}")
    print(f"Total expense potential: ${total_potential:,.2f}")
    print(f"High-value files (>$50K): {len(high_value_files)}")
    
    tax_benefit = total_potential * 0.14
    print(f"Estimated tax benefit: ${tax_benefit:,.0f}")
    
    if high_value_files:
        print(f"\n🚀 HIGH-VALUE FILES IDENTIFIED:")
        print("-" * 50)
        
        # Sort by potential value
        high_value_files.sort(key=lambda x: x['potential'], reverse=True)
        
        for i, file_info in enumerate(high_value_files, 1):
            filename = file_info['filename']
            potential = file_info['potential']
            sheets = file_info['sheets']
            action = file_info['action']
            
            print(f"{i:2d}. {filename[:40]:<40} ${potential:>10,.0f} ({sheets} sheets) [{action}]")
        
        # Calculate cumulative impact
        cumulative = 0
        print(f"\n💰 CUMULATIVE IMPACT:")
        for i, file_info in enumerate(high_value_files[:5], 1):  # Top 5
            cumulative += file_info['potential']
            benefit = cumulative * 0.14
            print(f"Top {i} files: ${cumulative:>10,.0f} → ${benefit:>8,.0f} tax benefit")
    
    if processing_errors:
        print(f"\n[WARN]  PROCESSING ISSUES:")
        for error in processing_errors[:10]:  # Show first 10
            print(f"   • {error}")
    
    # Recommendations
    print(f"\n📋 NEXT STEPS:")
    if high_value_files:
        top_file = high_value_files[0]
        print(f"1. Start with: {top_file['filename']} (${top_file['potential']:,.0f} potential)")
        print(f"2. Process top 3 files for ${sum(f['potential'] for f in high_value_files[:3]):,.0f} recovery")
        print(f"3. Create import scripts for each high-value file type")
        print(f"4. Move processed files to uploaded folder")
    else:
        print("1. Review processing errors above")
        print("2. Check file formats and accessibility")
        print("3. Focus on files that processed successfully")
    
    # Save detailed results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"L:\\limo\\batch_processing_report_{timestamp}.json"
    
    try:
        with open(report_filename, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'total_files': len(priority_files),
                'processed_files': len(results),
                'total_potential': total_potential,
                'high_value_files': high_value_files,
                'processing_errors': processing_errors,
                'results': results
            }, f, indent=2, default=str)
        
        print(f"\n[OK] Detailed report saved: {report_filename}")
        
    except Exception as e:
        print(f"\n[FAIL] Could not save report: {e}")
    
    return {
        'total_potential': total_potential,
        'high_value_count': len(high_value_files),
        'top_files': high_value_files[:5]
    }

if __name__ == "__main__":
    results = process_priority_files()
    
    print(f"\n🎯 BATCH PROCESSING COMPLETE!")
    print(f"Identified ${results['total_potential']:,.0f} in expense recovery potential")
    print(f"Found {results['high_value_count']} high-value files for priority processing")